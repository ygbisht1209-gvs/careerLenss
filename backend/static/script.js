"use strict";

const authScreen = document.getElementById("auth-screen");
const workspace = document.getElementById("workspace");
const authForm = document.getElementById("auth-form");
const authMessage = document.getElementById("auth-message");
const setupNotice = document.getElementById("setup-notice");
const applicationList = document.getElementById("application-list");
const applicationCount = document.getElementById("application-count");
const applicationDialog = document.getElementById("application-dialog");
const applicationForm = document.getElementById("application-form");
const applicationSearch = document.getElementById("application-search");
const applicationFilter = document.getElementById("application-filter");
const interviewPrepForm = document.getElementById("interview-prep-form");
const aiAssistForm = document.getElementById("ai-assist-form");
const statuses = ["Applied", "Under Review", "Interview", "Offer", "Rejected"];
const stopWords = new Set([
    "about", "after", "also", "and", "are", "for", "from", "have", "into",
    "job", "our", "required", "role", "that", "the", "their", "these", "this",
    "with", "you", "your"
]);

let supabaseClient = null;
let currentUser = null;
let authMode = "sign-in";
let currentApplications = [];
let loadingUserId = null;
let maxResumeBytes = 5 * 1024 * 1024;
let editingApplicationId = null;
let currentInterviewPack = null;

function setMessage(element, message, kind = "") {
    element.textContent = message;
    element.classList.toggle("error", kind === "error");
    element.classList.toggle("success", kind === "success");
}

async function setupSupabase() {
    if (!window.supabase?.createClient) {
        setMessage(authMessage, "Could not load the authentication client. Check your internet connection and reload.", "error");
        authForm.querySelector("button[type='submit']").disabled = true;
        return;
    }

    let url = workspace.dataset.supabaseUrl;
    let anonKey = workspace.dataset.supabaseAnonKey;
    if (!url || !anonKey) {
        try {
            const response = await fetch("/api/config");
            const config = await response.json();
            if (!response.ok) throw new Error(config.error || "Authentication is not configured.");
            url = config.supabaseUrl;
            anonKey = config.supabaseAnonKey;
            if (Number.isFinite(config.maxResumeBytes) && config.maxResumeBytes > 0) {
                maxResumeBytes = config.maxResumeBytes;
                document.querySelector("label[for='resume-file']").textContent =
                    `Resume (PDF, max ${Math.floor(maxResumeBytes / 1024 / 1024)} MB)`;
            }
        } catch (error) {
            setupNotice.hidden = false;
            setMessage(authMessage, error.message || "Could not load app configuration.", "error");
            authForm.querySelector("button[type='submit']").disabled = true;
            document.getElementById("forgot-password").disabled = true;
            return;
        }
    }

    if (!url || !anonKey) {
        setupNotice.hidden = false;
        authForm.querySelector("button[type='submit']").disabled = true;
        document.getElementById("forgot-password").disabled = true;
        return;
    }

    supabaseClient = window.supabase.createClient(url, anonKey, {
        auth: {
            autoRefreshToken: true,
            persistSession: true,
            detectSessionInUrl: true
        }
    });

    supabaseClient.auth.onAuthStateChange((event, session) => {
        if (!session) {
            currentUser = null;
            loadingUserId = null;
            clearWorkspaceData();
            showAuthScreen();
            if (event === "SIGNED_OUT") {
                setMessage(authMessage, "You have signed out.", "success");
            }
            return;
        }
        if (event === "PASSWORD_RECOVERY") {
            authScreen.hidden = false;
            workspace.hidden = true;
            authForm.hidden = true;
            document.getElementById("password-update-form").hidden = false;
            document.getElementById("forgot-password").hidden = true;
            document.getElementById("auth-title").textContent = "Choose a new password.";
            return;
        }
        queueMicrotask(() => openWorkspace(session.user));
    });
}

function showAuthScreen() {
    workspace.hidden = true;
    authScreen.hidden = false;
}

function clearWorkspaceData() {
    currentApplications = [];
    applicationSearch.value = "";
    applicationFilter.value = "all";
    renderApplications();
    document.getElementById("profile-form").reset();
    document.getElementById("skill-form").reset();
    document.getElementById("ats-form").reset();
    document.getElementById("coach-form").reset();
    interviewPrepForm.reset();
    aiAssistForm.reset();
    document.getElementById("interview-prep-results").hidden = true;
    document.getElementById("interview-prep-message").textContent = "";
    document.getElementById("ai-assist-result").hidden = true;
    document.getElementById("ai-assist-answer").textContent = "";
    setMessage(document.getElementById("ai-assist-message"), "");
    currentInterviewPack = null;
    document.getElementById("profile-name").textContent = "Career Explorer";
    document.getElementById("profile-email").textContent = "Your career workspace";
    document.getElementById("profile-avatar").textContent = "CL";
    document.getElementById("profile-stat").textContent = "Build it";
    document.getElementById("skill-count").textContent = "--";
    document.getElementById("ats-stat").innerHTML = "--<small> / 100</small>";
    document.getElementById("skill-results").hidden = true;
    document.getElementById("ats-results").hidden = true;
    document.getElementById("coach-answer").hidden = true;
    setMessage(document.getElementById("app-message"), "");
    setMessage(document.getElementById("profile-message"), "");
    setMessage(document.getElementById("ats-message"), "");
}

async function openWorkspace(user) {
    if (currentUser && currentUser.id !== user.id) {
        clearWorkspaceData();
    }
    currentUser = user;
    authScreen.hidden = true;
    workspace.hidden = false;
    const displayName = user.user_metadata?.full_name || user.email?.split("@")[0] || "Career Explorer";
    document.getElementById("profile-name").textContent = displayName;
    document.getElementById("profile-email").textContent = user.email || "";
    document.getElementById("profile-avatar").textContent = displayName.trim().slice(0, 2).toUpperCase();

    if (loadingUserId === user.id) return;
    loadingUserId = user.id;
    await Promise.all([loadApplications(), loadProfile()]);
}

function setAuthMode(mode) {
    authMode = mode;
    const signingUp = mode === "sign-up";
    document.querySelectorAll("[data-auth-mode]").forEach((tab) => {
        const selected = tab.dataset.authMode === mode;
        tab.classList.toggle("active", selected);
        tab.setAttribute("aria-selected", String(selected));
    });
    document.getElementById("auth-title").textContent = signingUp ? "Create your account." : "Welcome back.";
    document.getElementById("auth-name").hidden = !signingUp;
    document.getElementById("auth-name-label").hidden = !signingUp;
    document.getElementById("auth-name").required = signingUp;
    document.getElementById("auth-password").autocomplete = signingUp ? "new-password" : "current-password";
    document.getElementById("auth-submit").textContent = signingUp ? "Create account" : "Sign in";
    document.getElementById("forgot-password").hidden = signingUp;
    setMessage(authMessage, "");
}

async function handleAuthSubmit(event) {
    event.preventDefault();
    if (!supabaseClient) return;

    const formData = new FormData(authForm);
    const email = String(formData.get("email") || "").trim();
    const password = String(formData.get("password") || "");
    const button = document.getElementById("auth-submit");
    button.disabled = true;
    setMessage(authMessage, authMode === "sign-up" ? "Creating your account..." : "Signing in...");

    try {
        if (authMode === "sign-up") {
            const fullName = String(formData.get("name") || "").trim();
            const { data, error } = await supabaseClient.auth.signUp({
                email,
                password,
                options: { data: { full_name: fullName }, emailRedirectTo: window.location.origin }
            });
            if (error) throw error;
            if (!data.session) {
                setMessage(authMessage, "Account created. Check your inbox to verify your email, then sign in.", "success");
            }
        } else {
            const { error } = await supabaseClient.auth.signInWithPassword({ email, password });
            if (error) throw error;
        }
    } catch (error) {
        setMessage(authMessage, error.message || "Could not sign in. Please try again.", "error");
    } finally {
        button.disabled = false;
    }
}

async function sendPasswordReset() {
    if (!supabaseClient) return;
    const email = document.getElementById("auth-email").value.trim();
    if (!email) {
        setMessage(authMessage, "Enter your email address first.", "error");
        document.getElementById("auth-email").focus();
        return;
    }

    const button = document.getElementById("forgot-password");
    button.disabled = true;
    try {
        const { error } = await supabaseClient.auth.resetPasswordForEmail(email, {
            redirectTo: window.location.origin
        });
        if (error) throw error;
        setMessage(authMessage, "If an account exists for that address, a password-reset link is on its way.", "success");
    } catch (error) {
        setMessage(authMessage, error.message || "Could not send the reset email.", "error");
    } finally {
        button.disabled = false;
    }
}

async function updatePassword(event) {
    event.preventDefault();
    const newPassword = document.getElementById("new-password").value;
    const confirmation = document.getElementById("confirm-password").value;
    if (newPassword !== confirmation) {
        setMessage(authMessage, "The passwords do not match.", "error");
        return;
    }

    const button = event.currentTarget.querySelector("button[type='submit']");
    button.disabled = true;
    try {
        const { error } = await supabaseClient.auth.updateUser({ password: newPassword });
        if (error) throw error;
        event.currentTarget.reset();
        event.currentTarget.hidden = true;
        authForm.hidden = false;
        document.getElementById("forgot-password").hidden = false;
        await supabaseClient.auth.signOut();
        setMessage(authMessage, "Password updated. Sign in with your new password.", "success");
    } catch (error) {
        setMessage(authMessage, error.message || "Could not update your password.", "error");
    } finally {
        button.disabled = false;
    }
}

async function signOut() {
    if (!supabaseClient) return;
    try {
        const { error } = await supabaseClient.auth.signOut();
        if (error) throw error;
    } catch (error) {
        setMessage(document.getElementById("app-message"), error.message || "Could not sign out.", "error");
    }
}

function supabaseErrorMessage(error) {
    if (error?.code === "42P01" || error?.code === "PGRST205") {
        return "Supabase cannot find the public.applications table. In the Supabase project configured in backend/.env, open SQL Editor, run the full backend/supabase_schema.sql file, wait for it to finish successfully, then reload CareerLens.";
    }
    if (error?.code === "PGRST204" || error?.message?.includes("schema cache")) {
        return "The applications table is missing one or more CareerLens fields. Run the latest backend/supabase_schema.sql in the Supabase SQL Editor, wait for it to finish successfully, then reload CareerLens.";
    }
    return error?.message || "Could not load your account data.";
}

async function loadApplications() {
    const userId = currentUser?.id;
    if (!userId) return false;
    try {
        const { data, error } = await supabaseClient
            .from("applications")
            .select("id,title,company,applied_on,status,job_url,follow_up_on,notes")
            .order("applied_on", { ascending: false });
        if (currentUser?.id !== userId) return false;
        if (error) throw error;
        currentApplications = data;
        renderApplications();
        return true;
    } catch (error) {
        if (currentUser?.id !== userId) return false;
        setMessage(document.getElementById("app-message"), supabaseErrorMessage(error), "error");
        applicationList.replaceChildren();
        return false;
    }
}

function getFilteredApplications() {
    const query = applicationSearch.value.trim().toLocaleLowerCase();
    const selectedStatus = applicationFilter.value;
    return currentApplications.filter((application) => {
        const matchesQuery = !query ||
            `${application.title} ${application.company}`.toLocaleLowerCase().includes(query);
        const matchesStatus = selectedStatus === "all" || application.status === selectedStatus;
        return matchesQuery && matchesStatus;
    });
}

function renderApplicationInsights() {
    const activeApplications = currentApplications.filter(
        (application) => !["Offer", "Rejected"].includes(application.status)
    );
    const interviews = currentApplications.filter((application) => application.status === "Interview").length;
    const offers = currentApplications.filter((application) => application.status === "Offer").length;
    const today = localDateValue();
    const dueFollowUps = activeApplications.filter(
        (application) => application.follow_up_on && application.follow_up_on <= today
    ).length;

    document.getElementById("active-applications").textContent = String(activeApplications.length);
    document.getElementById("interview-applications").textContent = String(interviews);
    document.getElementById("offer-applications").textContent = String(offers);
    document.getElementById("due-followups").textContent = String(dueFollowUps);
    document.querySelector(".follow-up-insight").classList.toggle("has-due-followups", dueFollowUps > 0);

    const pipeline = document.getElementById("application-pipeline");
    pipeline.replaceChildren();
    statuses.forEach((statusName) => {
        const count = currentApplications.filter((application) => application.status === statusName).length;
        const item = document.createElement("div");
        item.className = "pipeline-item";
        const label = document.createElement("span");
        label.textContent = statusName;
        const track = document.createElement("div");
        track.className = "pipeline-track";
        track.setAttribute("role", "meter");
        track.setAttribute("aria-label", `${statusName} applications`);
        track.setAttribute("aria-valuemin", "0");
        track.setAttribute("aria-valuemax", String(Math.max(currentApplications.length, 1)));
        track.setAttribute("aria-valuenow", String(count));
        const fill = document.createElement("span");
        fill.style.width = `${currentApplications.length ? (count / currentApplications.length) * 100 : 0}%`;
        track.appendChild(fill);
        const value = document.createElement("strong");
        value.textContent = String(count);
        item.append(label, track, value);
        pipeline.appendChild(item);
    });
}

function renderApplications() {
    const filteredApplications = getFilteredApplications();
    applicationCount.textContent = String(currentApplications.length);
    renderApplicationInsights();
    document.getElementById("application-result-count").textContent =
        `Showing ${filteredApplications.length} of ${currentApplications.length}`;
    document.getElementById("export-applications").disabled = filteredApplications.length === 0;
    applicationList.replaceChildren();
    if (!currentApplications.length) {
        applicationList.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">◷</div>
                <strong>Your job search starts here.</strong>
                <p>Add an application to begin tracking your progress.</p>
            </div>`;
        return;
    }
    if (!filteredApplications.length) {
        applicationList.innerHTML = `
            <div class="empty-state">
                <strong>No applications match these filters.</strong>
                <p>Try a different search or status.</p>
            </div>`;
        return;
    }

    filteredApplications.forEach((application) => {
        const row = document.createElement("div");
        row.className = "application-row";
        const details = document.createElement("div");
        details.className = "application-details";
        const title = document.createElement("strong");
        title.textContent = application.title;
        const company = document.createElement("small");
        company.textContent = application.company;
        details.append(title, company);
        if (application.notes) {
            const notes = document.createElement("small");
            notes.className = "application-notes";
            notes.textContent = application.notes;
            notes.title = application.notes;
            details.appendChild(notes);
        }
        const jobUrl = getSafeJobUrl(application.job_url);
        if (jobUrl) {
            const link = document.createElement("a");
            link.className = "application-job-link";
            link.href = jobUrl;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            link.textContent = "Job posting ↗";
            link.setAttribute("aria-label", `Open job posting for ${application.title} at ${application.company}`);
            details.appendChild(link);
        }

        const dates = document.createElement("div");
        dates.className = "application-dates";
        const date = document.createElement("span");
        date.textContent = `Applied ${formatApplicationDate(application.applied_on)}`;
        dates.appendChild(date);
        if (application.follow_up_on) {
            const followUp = document.createElement("small");
            const daysUntil = Math.round(
                (new Date(`${application.follow_up_on}T00:00:00`) - new Date(`${localDateValue()}T00:00:00`)) / 86400000
            );
            followUp.className = `follow-up-date${daysUntil < 0 ? " is-overdue" : daysUntil === 0 ? " is-due" : ""}`;
            followUp.textContent = `Follow up ${daysUntil < 0 ? `${Math.abs(daysUntil)}d overdue` : daysUntil === 0 ? "today" : `· ${formatApplicationDate(application.follow_up_on)}`}`;
            dates.appendChild(followUp);
        }
        const status = document.createElement("select");
        status.setAttribute("aria-label", `Status for ${application.title} at ${application.company}`);
        statuses.forEach((name) => {
            const option = document.createElement("option");
            option.value = name;
            option.textContent = name;
            option.selected = name === application.status;
            status.appendChild(option);
        });
        status.addEventListener("change", () => updateApplicationStatus(application.id, status.value, status));

        const actions = document.createElement("div");
        actions.className = "application-actions";
        const edit = document.createElement("button");
        edit.className = "edit-application";
        edit.type = "button";
        edit.textContent = "Edit";
        edit.setAttribute("aria-label", `Edit ${application.title} at ${application.company}`);
        edit.addEventListener("click", () => openApplicationDialog(application));
        const remove = document.createElement("button");
        remove.className = "delete-application";
        remove.type = "button";
        remove.textContent = "Remove";
        remove.setAttribute("aria-label", `Remove ${application.title} at ${application.company}`);
        remove.addEventListener("click", () => deleteApplication(application));
        actions.append(edit, remove);
        row.append(details, dates, status, actions);
        applicationList.appendChild(row);
    });
}

function formatApplicationDate(value) {
    return new Date(`${value}T00:00:00`).toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric"
    });
}

function localDateValue() {
    const now = new Date();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const day = String(now.getDate()).padStart(2, "0");
    return `${now.getFullYear()}-${month}-${day}`;
}

function openApplicationDialog(application = null) {
    editingApplicationId = application?.id || null;
    applicationForm.reset();
    document.getElementById("application-dialog-title").textContent =
        application ? "Edit application" : "Add an application";
    document.getElementById("application-submit").textContent =
        application ? "Save changes" : "Save application";
    document.getElementById("application-date").max = localDateValue();
    if (application) {
        document.getElementById("job-title").value = application.title;
        document.getElementById("company-name").value = application.company;
        document.getElementById("application-date").value = application.applied_on;
        document.getElementById("application-status").value = application.status;
        document.getElementById("application-url").value = application.job_url || "";
        document.getElementById("application-follow-up").value = application.follow_up_on || "";
        document.getElementById("application-notes").value = application.notes || "";
    } else {
        document.getElementById("application-date").value = localDateValue();
    }
    updateFollowUpMinimum();
    setMessage(document.getElementById("application-message"), "");
    applicationDialog.showModal();
}

function updateFollowUpMinimum() {
    document.getElementById("application-follow-up").min =
        document.getElementById("application-date").value;
}

function getSafeJobUrl(value) {
    if (!value) return "";
    try {
        const url = new URL(value);
        return ["http:", "https:"].includes(url.protocol) ? url.href : "";
    } catch {
        return "";
    }
}

async function saveApplication(event) {
    event.preventDefault();
    const button = applicationForm.querySelector("button[type='submit']");
    button.disabled = true;
    const message = document.getElementById("application-message");
    setMessage(message, editingApplicationId ? "Saving changes..." : "Saving...");
    try {
        const values = new FormData(applicationForm);
        const rawJobUrl = String(values.get("job_url") || "").trim();
        const jobUrl = getSafeJobUrl(rawJobUrl);
        if (rawJobUrl && !jobUrl) {
            throw new Error("Enter a valid HTTP or HTTPS job posting URL.");
        }
        const record = {
            title: String(values.get("title") || "").trim(),
            company: String(values.get("company") || "").trim(),
            applied_on: values.get("applied_on"),
            status: values.get("status"),
            job_url: jobUrl,
            follow_up_on: values.get("follow_up_on") || null,
            notes: String(values.get("notes") || "").trim()
        };
        const result = editingApplicationId
            ? await supabaseClient.from("applications").update(record).eq("id", editingApplicationId)
            : await supabaseClient.from("applications").insert(record);
        if (result.error) throw result.error;
        applicationDialog.close();
        applicationForm.reset();
        editingApplicationId = null;
        if (await loadApplications()) {
            setMessage(document.getElementById("app-message"), "Application saved.", "success");
        }
    } catch (error) {
        setMessage(document.getElementById("application-message"), supabaseErrorMessage(error), "error");
    } finally {
        button.disabled = false;
    }
}

async function updateApplicationStatus(id, status, selector) {
    const previous = currentApplications.find((application) => application.id === id)?.status;
    if (selector) selector.disabled = true;
    try {
        const { error } = await supabaseClient.from("applications").update({ status }).eq("id", id);
        if (error) throw error;
        currentApplications = currentApplications.map((application) =>
            application.id === id ? { ...application, status } : application
        );
        renderApplications();
        setMessage(document.getElementById("app-message"), "Application status updated.", "success");
    } catch (error) {
        setMessage(document.getElementById("app-message"), supabaseErrorMessage(error), "error");
        if (selector && previous) selector.value = previous;
    } finally {
        if (selector) selector.disabled = false;
    }
}

async function deleteApplication(application) {
    if (!window.confirm(`Remove ${application.title} at ${application.company} from your tracker?`)) return;
    try {
        const { error } = await supabaseClient.from("applications").delete().eq("id", application.id);
        if (error) throw error;
        currentApplications = currentApplications.filter((item) => item.id !== application.id);
        renderApplications();
        setMessage(document.getElementById("app-message"), "Application removed.", "success");
    } catch (error) {
        setMessage(document.getElementById("app-message"), supabaseErrorMessage(error), "error");
    }
}

function exportApplications() {
    const applications = getFilteredApplications();
    if (!applications.length) return;
    const columns = [
        ["Job title", "title"],
        ["Company", "company"],
        ["Status", "status"],
        ["Date applied", "applied_on"],
        ["Follow-up date", "follow_up_on"],
        ["Job posting URL", "job_url"],
        ["Notes", "notes"]
    ];
    const escapeCsv = (value) => {
        let text = String(value ?? "");
        if (/^[\s\u0000-\u001f]*[=+\-@]/.test(text)) text = `'${text}`;
        return `"${text.replaceAll('"', '""')}"`;
    };
    const csv = [
        columns.map(([label]) => escapeCsv(label)).join(","),
        ...applications.map((application) =>
            columns.map(([, key]) => escapeCsv(application[key])).join(",")
        )
    ].join("\r\n");
    const url = URL.createObjectURL(new Blob(["\ufeff", csv], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `careerlens-applications-${localDateValue()}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function loadProfile() {
    const userId = currentUser?.id;
    if (!userId) return;
    const { data, error } = await supabaseClient
        .from("career_profiles")
        .select("headline,about,target_role,skills")
        .maybeSingle();
    if (currentUser?.id !== userId) return;
    if (error) {
        setMessage(document.getElementById("app-message"), supabaseErrorMessage(error), "error");
        return;
    }
    if (!data) return;
    document.getElementById("profile-target-role").value = data.target_role || "";
    document.getElementById("profile-headline").value = data.headline || "";
    document.getElementById("profile-about").value = data.about || "";
    document.getElementById("skill-target-role").value = data.target_role || "";
    document.getElementById("current-skills").value = (data.skills || []).join(", ");
    if (data.headline || data.about || data.target_role) {
        document.getElementById("profile-stat").textContent = "Ready";
    }
}

async function saveProfile(event) {
    event.preventDefault();
    const button = event.currentTarget.querySelector("button[type='submit']");
    button.disabled = true;
    const payload = {
        user_id: currentUser.id,
        target_role: document.getElementById("profile-target-role").value.trim(),
        headline: document.getElementById("profile-headline").value.trim(),
        about: document.getElementById("profile-about").value.trim(),
        skills: document.getElementById("current-skills").value
            .split(/[,;\n]/).map((skill) => skill.trim()).filter(Boolean)
    };
    const { error } = await supabaseClient.from("career_profiles").upsert(payload, { onConflict: "user_id" });
    button.disabled = false;
    if (error) {
        setMessage(document.getElementById("profile-message"), supabaseErrorMessage(error), "error");
        return;
    }
    document.getElementById("skill-target-role").value = payload.target_role;
    document.getElementById("current-skills").value = payload.skills.join(", ");
    document.getElementById("profile-stat").textContent = payload.headline ? "Ready" : "In progress";
    setMessage(document.getElementById("profile-message"), "Your profile has been saved to your account.", "success");
}

function extractKeywords(text) {
    return new Set(
        text.toLowerCase().match(/[a-z][a-z+#.]{1,}/g)?.filter((word) => !stopWords.has(word)) || []
    );
}

function renderList(element, values, emptyText) {
    element.replaceChildren();
    const items = values.length ? values : [emptyText];
    items.forEach((value) => {
        const item = document.createElement("li");
        item.textContent = value;
        element.appendChild(item);
    });
}

function renderSkillAnalysis(event) {
    event.preventDefault();
    const targetRole = document.getElementById("skill-target-role").value.trim();
    const enteredSkills = document.getElementById("current-skills").value
        .split(/[,;\n]/).map((skill) => skill.trim()).filter(Boolean);
    const currentWords = new Set(enteredSkills.flatMap((skill) => [...extractKeywords(skill)]));
    const targetWords = [...extractKeywords(document.getElementById("skill-job-description").value)];
    const matched = targetWords.filter((word) => currentWords.has(word));
    const missing = targetWords.filter((word) => !currentWords.has(word));
    renderList(document.getElementById("skill-matched"), [...new Set(matched)], "No overlapping terms found yet.");
    renderList(document.getElementById("skill-missing"), [...new Set(missing)], "No additional terms found.");
    document.getElementById("skill-result-title").textContent =
        `Keyword comparison for ${targetRole} · ${new Set(missing).size} terms to explore`;
    document.getElementById("skill-results").hidden = false;
    document.getElementById("skill-count").textContent = String(new Set(missing).size);
}

function renderCoachGuidance(question) {
    const text = question.toLowerCase();
    let heading = "Turn your goal into a small next step";
    let steps = [
        "Write down the outcome you want and a realistic date for it.",
        "Choose one action you can complete in the next 30 minutes.",
        "Ask someone you trust for feedback, then adjust your plan."
    ];
    if (text.includes("interview")) {
        heading = "Prepare for your next interview";
        steps = [
            "Choose three examples that show your impact; structure each as situation, action, and result.",
            "Review the role requirements and prepare one specific example for each important skill.",
            "Prepare two thoughtful questions about the team, success measures, or first 90 days.",
            "Practice concise answers aloud and keep your examples truthful and specific."
        ];
    } else if (text.includes("resume")) {
        heading = "Make your resume clearer and more relevant";
        steps = [
            "Start each experience bullet with a clear action and explain the result.",
            "Prioritize evidence that matches the role; include numbers only when you can support them.",
            "Use consistent dates, headings, and formatting that are easy to scan.",
            "Compare your resume with one target job description and tailor it honestly."
        ];
    } else if (text.includes("learning") || text.includes("skill")) {
        heading = "Build a focused learning plan";
        steps = [
            "Pick one high-priority skill that appears in the roles you want.",
            "Choose a small project where you can practice the skill and produce a visible result.",
            "Set a weekly practice time and a finish date for the project.",
            "Ask a knowledgeable person to review your work and identify the next gap."
        ];
    } else if (text.includes("career") || text.includes("move") || text.includes("plan")) {
        heading = "Plan your next career move";
        steps = [
            "List the work you want more of, the work you want less of, and your non-negotiables.",
            "Compare two realistic role options against those priorities.",
            "Speak with someone doing the work to test your assumptions.",
            "Choose one low-risk experiment—such as a project, course, or informational interview."
        ];
    }
    const answer = document.getElementById("coach-answer");
    answer.replaceChildren();
    const title = document.createElement("h3");
    title.textContent = heading;
    const list = document.createElement("ol");
    steps.forEach((step) => {
        const item = document.createElement("li");
        item.textContent = step;
        list.appendChild(item);
    });
    answer.append(title, list);
    answer.hidden = false;
}

function updatePracticeProgress() {
    const questions = [...document.querySelectorAll(".practice-question-check")];
    const practiced = questions.filter((checkbox) => checkbox.checked).length;
    const percentage = questions.length ? Math.round((practiced / questions.length) * 100) : 0;
    document.getElementById("practice-progress-label").textContent =
        `${practiced} of ${questions.length} practiced`;
    const progress = document.getElementById("practice-progress-bar");
    progress.setAttribute("aria-valuenow", String(percentage));
    progress.querySelector("span").style.width = `${percentage}%`;
}

function renderInterviewPack(pack) {
    currentInterviewPack = pack;
    const title = pack.company
        ? `${pack.role} · ${pack.company}`
        : pack.role;
    document.getElementById("interview-pack-title").textContent = title;
    document.getElementById("interview-pack-note").textContent = pack.note;

    const focusAreas = document.getElementById("interview-focus-areas");
    focusAreas.replaceChildren();
    if (pack.focus_areas.length) {
        pack.focus_areas.forEach((area) => {
            const chip = document.createElement("span");
            chip.className = "focus-area-chip";
            chip.textContent = `${area.name} · ${area.mentions} ${area.mentions === 1 ? "mention" : "mentions"}`;
            focusAreas.appendChild(chip);
        });
    } else {
        const empty = document.createElement("p");
        empty.className = "muted-text";
        empty.textContent = "No predefined technical focus terms were detected; the questions below focus on role examples and problem-solving.";
        focusAreas.appendChild(empty);
    }

    const questionList = document.getElementById("interview-question-list");
    questionList.replaceChildren();
    pack.questions.forEach((item, index) => {
        const card = document.createElement("article");
        card.className = "practice-question-card";
        const heading = document.createElement("div");
        heading.className = "practice-question-heading";
        const number = document.createElement("span");
        number.className = "practice-question-number";
        number.textContent = String(index + 1).padStart(2, "0");
        const category = document.createElement("span");
        category.className = "practice-question-category";
        category.textContent = item.category;
        const focus = document.createElement("span");
        focus.className = "muted-text";
        focus.textContent = item.focus;
        heading.append(number, category, focus);

        const question = document.createElement("h4");
        question.textContent = item.question;
        const followUp = document.createElement("p");
        followUp.className = "practice-follow-up";
        const followUpLabel = document.createElement("strong");
        followUpLabel.textContent = "Think deeper: ";
        followUp.append(followUpLabel, document.createTextNode(item.follow_up));

        const answerLabel = document.createElement("label");
        answerLabel.className = "sr-only";
        answerLabel.htmlFor = `practice-answer-${index}`;
        answerLabel.textContent = `Your answer notes for question ${index + 1}`;
        const answer = document.createElement("textarea");
        answer.id = `practice-answer-${index}`;
        answer.className = "practice-answer";
        answer.rows = 3;
        answer.maxLength = 2000;
        answer.placeholder = "Plan your answer: context, your specific actions, and the result...";

        const practiceLabel = document.createElement("label");
        practiceLabel.className = "practice-question-toggle";
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.className = "practice-question-check";
        checkbox.addEventListener("change", updatePracticeProgress);
        practiceLabel.append(checkbox, document.createTextNode(" Practiced"));
        card.append(heading, question, followUp, answerLabel, answer, practiceLabel);
        questionList.appendChild(card);
    });

    const checklist = document.getElementById("interview-checklist");
    checklist.replaceChildren();
    pack.checklist.forEach((step, index) => {
        const item = document.createElement("li");
        const label = document.createElement("label");
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.className = "interview-checklist-check";
        checkbox.setAttribute("aria-label", `Mark checklist item ${index + 1} complete`);
        label.append(checkbox, document.createTextNode(` ${step}`));
        item.appendChild(label);
        checklist.appendChild(item);
    });
    updatePracticeProgress();
    document.getElementById("interview-prep-results").hidden = false;
    document.getElementById("interview-prep-results").scrollIntoView({
        behavior: "smooth",
        block: "start"
    });
}

async function generateInterviewPack(event) {
    event.preventDefault();
    const button = document.getElementById("generate-interview-prep");
    const message = document.getElementById("interview-prep-message");
    const values = new FormData(interviewPrepForm);
    button.disabled = true;
    setMessage(message, "Building your role-focused practice pack...");
    try {
        const { data: { session }, error: sessionError } = await supabaseClient.auth.getSession();
        if (sessionError) throw sessionError;
        if (!session) throw new Error("Your session has expired. Please sign in again.");
        const response = await fetch("/api/interview-prep", {
            method: "POST",
            headers: {
                Authorization: `Bearer ${session.access_token}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                role: String(values.get("role") || "").trim(),
                company: String(values.get("company") || "").trim(),
                job_description: String(values.get("job_description") || "").trim()
            })
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || "Could not build the interview practice pack.");
        renderInterviewPack(payload);
        setMessage(message, "Your interview practice pack is ready.", "success");
    } catch (error) {
        setMessage(message, error.message || "Could not build the interview practice pack.", "error");
    } finally {
        button.disabled = false;
    }
}

async function submitAIAssist(event) {
    event.preventDefault();
    const formData = new FormData(aiAssistForm);
    const button = document.getElementById("ai-assist-submit");
    const message = document.getElementById("ai-assist-message");
    const consent = document.getElementById("ai-consent");
    button.disabled = true;
    document.getElementById("ai-assist-result").hidden = true;
    setMessage(message, "Sending your selected text to Gemini for suggestions...");
    try {
        const { data: { session }, error: sessionError } = await supabaseClient.auth.getSession();
        if (sessionError) throw sessionError;
        if (!session) throw new Error("Your session has expired. Please sign in again.");
        const response = await fetch("/api/ai-assist", {
            method: "POST",
            headers: {
                Authorization: ["Bearer", session.access_token].join(" "),
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                task: String(formData.get("task") || ""),
                role: String(formData.get("role") || "").trim(),
                text: String(formData.get("text") || "").trim(),
                consent: consent.checked
            })
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || "Gemini could not process this request.");
        document.getElementById("ai-assist-answer").textContent = payload.answer;
        document.getElementById("ai-assist-result").hidden = false;
        setMessage(message, "Your suggestions are ready. Review them carefully.", "success");
    } catch (error) {
        setMessage(message, error.message || "Could not get AI suggestions.", "error");
    } finally {
        consent.checked = false;
        button.disabled = false;
    }
}

function downloadInterviewPack() {
    if (!currentInterviewPack) return;
    const lines = [
        `CareerLens Interview Practice Pack`,
        `Role: ${currentInterviewPack.role}`,
        ...(currentInterviewPack.company ? [`Company: ${currentInterviewPack.company}`] : []),
        "",
        "JOB DESCRIPTION FOCUS AREAS",
        ...(currentInterviewPack.focus_areas.length
            ? currentInterviewPack.focus_areas.map((area) => `- ${area.name} (${area.mentions} mentions)`)
            : ["- No predefined technical focus terms detected"]),
        "",
        "PRACTICE QUESTIONS"
    ];
    [...document.querySelectorAll(".practice-question-card")].forEach((card, index) => {
        lines.push(
            "",
            `${index + 1}. [${card.querySelector(".practice-question-category").textContent}] ${card.querySelector("h4").textContent}`,
            `Think deeper: ${card.querySelector(".practice-follow-up").textContent.replace(/^Think deeper: /, "")}`,
            `Practiced: ${card.querySelector(".practice-question-check").checked ? "Yes" : "No"}`,
            `Answer notes: ${card.querySelector(".practice-answer").value.trim() || "(not written)"}`
        );
    });
    lines.push("", "INTERVIEW-DAY CHECKLIST");
    [...document.querySelectorAll("#interview-checklist li")].forEach((item) => {
        const checkbox = item.querySelector("input");
        lines.push(`- [${checkbox.checked ? "x" : " "}] ${item.textContent.trim()}`);
    });
    lines.push("", currentInterviewPack.note);

    const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "careerlens-interview-practice.txt";
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function analyzeResume(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const formData = new FormData(form);
    const file = formData.get("resume");
    const message = document.getElementById("ats-message");
    const button = document.getElementById("analyze-button");
    if (!(file instanceof File) || !file.name) {
        setMessage(message, "Choose a PDF resume before analyzing.", "error");
        return;
    }
    if (file.size > maxResumeBytes) {
        setMessage(message, `The PDF must be ${Math.floor(maxResumeBytes / 1024 / 1024)} MB or smaller.`, "error");
        return;
    }
    button.disabled = true;
    setMessage(message, "Analyzing your resume...");
    try {
        const { data: { session }, error: sessionError } = await supabaseClient.auth.getSession();
        if (sessionError) throw sessionError;
        if (!session) throw new Error("Your session has expired. Please sign in again.");
        const response = await fetch("/api/analyze-resume", {
            method: "POST",
            headers: { Authorization: `Bearer ${session.access_token}` },
            body: formData
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || "Resume analysis failed.");
        document.getElementById("ats-score").textContent = String(payload.score);
        document.getElementById("ats-stat").innerHTML = `${payload.score}<small> / 100</small>`;
        renderList(document.getElementById("matched-keywords"), payload.matched_keywords || [], "No matched keywords found.");
        renderList(document.getElementById("missing-keywords"), payload.missing_keywords || [], "No missing keywords found.");
        renderList(document.getElementById("ats-suggestions"), payload.suggestions || [], "No suggestions available.");
        document.getElementById("ats-note").textContent = payload.note || "";
        document.getElementById("ats-results").hidden = false;
        setMessage(message, "Resume analysis complete.", "success");
    } catch (error) {
        setMessage(message, error.message || "Could not analyze your resume.", "error");
    } finally {
        button.disabled = false;
    }
}

document.querySelectorAll("[data-auth-mode]").forEach((tab) => {
    tab.addEventListener("click", () => setAuthMode(tab.dataset.authMode));
});
authForm.addEventListener("submit", handleAuthSubmit);
document.getElementById("password-update-form").addEventListener("submit", updatePassword);
document.getElementById("forgot-password").addEventListener("click", sendPasswordReset);
document.getElementById("sign-out").addEventListener("click", signOut);
document.getElementById("add-application").addEventListener("click", () => {
    openApplicationDialog();
});
document.getElementById("close-application-dialog").addEventListener("click", () => applicationDialog.close());
applicationDialog.addEventListener("close", () => {
    editingApplicationId = null;
    applicationForm.reset();
});
document.getElementById("application-date").addEventListener("change", updateFollowUpMinimum);
applicationSearch.addEventListener("input", renderApplications);
applicationFilter.addEventListener("change", renderApplications);
document.getElementById("export-applications").addEventListener("click", exportApplications);
applicationForm.addEventListener("submit", saveApplication);
document.getElementById("profile-form").addEventListener("submit", saveProfile);
document.getElementById("skill-form").addEventListener("submit", renderSkillAnalysis);
document.getElementById("ats-form").addEventListener("submit", analyzeResume);
interviewPrepForm.addEventListener("submit", generateInterviewPack);
aiAssistForm.addEventListener("submit", submitAIAssist);
document.getElementById("download-interview-pack").addEventListener("click", downloadInterviewPack);
document.getElementById("coach-form").addEventListener("submit", (event) => {
    event.preventDefault();
    renderCoachGuidance(document.getElementById("coach-question").value.trim());
});
document.querySelectorAll(".coach-prompt").forEach((button) => {
    button.addEventListener("click", () => {
        const input = document.getElementById("coach-question");
        input.value = button.dataset.prompt;
        renderCoachGuidance(input.value);
    });
});
document.querySelectorAll(".nav-link").forEach((link) => {
    link.addEventListener("click", () => {
        document.querySelectorAll(".nav-link").forEach((item) => item.classList.remove("active"));
        link.classList.add("active");
    });
});

setupSupabase();
