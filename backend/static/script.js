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
    renderApplications();
    document.getElementById("profile-form").reset();
    document.getElementById("skill-form").reset();
    document.getElementById("ats-form").reset();
    document.getElementById("coach-form").reset();
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
    if (
        error?.code === "42P01" ||
        error?.code === "PGRST205" ||
        error?.message?.includes("schema cache")
    ) {
        return "The CareerLens database tables are not set up yet. Follow the Supabase SQL setup in README.md.";
    }
    return error?.message || "Could not load your account data.";
}

async function loadApplications() {
    const userId = currentUser?.id;
    if (!userId) return;
    const { data, error } = await supabaseClient
        .from("applications")
        .select("id,title,company,applied_on,status")
        .order("applied_on", { ascending: false });
    if (currentUser?.id !== userId) return;
    if (error) {
        setMessage(document.getElementById("app-message"), supabaseErrorMessage(error), "error");
        applicationList.innerHTML = "";
        return;
    }
    currentApplications = data;
    renderApplications();
}

function renderApplications() {
    applicationList.replaceChildren();
    applicationCount.textContent = String(currentApplications.length);
    if (!currentApplications.length) {
        applicationList.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">◷</div>
                <strong>Your job search starts here.</strong>
                <p>Add an application to begin tracking your progress.</p>
            </div>`;
        return;
    }

    currentApplications.forEach((application) => {
        const row = document.createElement("div");
        row.className = "application-row";
        const details = document.createElement("div");
        const title = document.createElement("strong");
        title.textContent = application.title;
        const company = document.createElement("small");
        company.textContent = application.company;
        details.append(title, company);

        const date = document.createElement("span");
        date.textContent = new Date(`${application.applied_on}T00:00:00`).toLocaleDateString();
        const status = document.createElement("select");
        status.setAttribute("aria-label", `Status for ${application.title} at ${application.company}`);
        statuses.forEach((name) => {
            const option = document.createElement("option");
            option.value = name;
            option.textContent = name;
            option.selected = name === application.status;
            status.appendChild(option);
        });
        status.addEventListener("change", () => updateApplicationStatus(application.id, status.value));

        const remove = document.createElement("button");
        remove.className = "delete-application";
        remove.type = "button";
        remove.textContent = "Remove";
        remove.setAttribute("aria-label", `Remove ${application.title} at ${application.company}`);
        remove.addEventListener("click", () => deleteApplication(application.id));
        row.append(details, date, status, remove);
        applicationList.appendChild(row);
    });
}

function localDateValue() {
    const now = new Date();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const day = String(now.getDate()).padStart(2, "0");
    return `${now.getFullYear()}-${month}-${day}`;
}

async function saveApplication(event) {
    event.preventDefault();
    const button = applicationForm.querySelector("button[type='submit']");
    button.disabled = true;
    setMessage(document.getElementById("application-message"), "Saving...");
    const values = new FormData(applicationForm);
    const record = {
        title: String(values.get("title") || "").trim(),
        company: String(values.get("company") || "").trim(),
        applied_on: values.get("applied_on"),
        status: values.get("status")
    };
    const { error } = await supabaseClient.from("applications").insert(record);
    button.disabled = false;
    if (error) {
        setMessage(document.getElementById("application-message"), supabaseErrorMessage(error), "error");
        return;
    }
    applicationDialog.close();
    applicationForm.reset();
    document.getElementById("application-date").value = localDateValue();
    await loadApplications();
}

async function updateApplicationStatus(id, status) {
    const { error } = await supabaseClient.from("applications").update({ status }).eq("id", id);
    if (error) {
        setMessage(document.getElementById("app-message"), supabaseErrorMessage(error), "error");
        await loadApplications();
    }
}

async function deleteApplication(id) {
    const { error } = await supabaseClient.from("applications").delete().eq("id", id);
    if (error) {
        setMessage(document.getElementById("app-message"), supabaseErrorMessage(error), "error");
        return;
    }
    currentApplications = currentApplications.filter((application) => application.id !== id);
    renderApplications();
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
    document.getElementById("application-date").value = localDateValue();
    setMessage(document.getElementById("application-message"), "");
    applicationDialog.showModal();
});
document.getElementById("close-application-dialog").addEventListener("click", () => applicationDialog.close());
applicationForm.addEventListener("submit", saveApplication);
document.getElementById("profile-form").addEventListener("submit", saveProfile);
document.getElementById("skill-form").addEventListener("submit", renderSkillAnalysis);
document.getElementById("ats-form").addEventListener("submit", analyzeResume);
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
