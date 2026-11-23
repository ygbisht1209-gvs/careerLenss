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
const jobDialog = document.getElementById("job-dialog");
const jobForm = document.getElementById("job-form");
const jobApplicationDialog = document.getElementById("job-application-dialog");
const jobApplicationForm = document.getElementById("job-application-form");
const statuses = ["Applied", "Under Review", "Interview", "Offer", "Rejected"];
const accountTypes = ["job_seeker", "job_provider"];

let supabaseClient = null;
let currentUser = null;
let authMode = "sign-in";
let currentApplications = [];
let currentCareerProfile = {};
let careerProjects = [];
let portfolioAvailable = true;
let editingProjectId = null;
let dashboardSources = {};
let loadingUserId = null;
let maxResumeBytes = 5 * 1024 * 1024;
let editingApplicationId = null;
let currentInterviewPack = null;
let currentAccountType = null;
let currentJobListings = [];
let jobMatches = new Map();
let jobProfileSummary = null;
let currentJobApplications = [];
let currentApplicationReviews = new Map();
let currentApplicantMatches = new Map();
let currentNotifications = [];
let seekerApplications = [];
let editingJobId = null;
let applyingToJobId = null;
let learningResources = [];
let learningPlan = [];
let latestSkillGapResult = null;
let latestLearningRecommendations = null;
let learningRecommendationError = "";

function setMessage(element, message, kind = "") {
    if (!element) return;
    element.textContent = message;
    element.classList.toggle("error", kind === "error");
    element.classList.toggle("success", kind === "success");
}

function createIcon(name) {
    const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
    icon.classList.add("icon");
    icon.setAttribute("aria-hidden", "true");
    icon.setAttribute("focusable", "false");
    use.setAttribute("href", `#icon-${name}`);
    icon.appendChild(use);
    return icon;
}

function activatePageFromHash() {
    const pageViews = [...document.querySelectorAll("[data-page-view]")];
    const allowedPages = pageViews.filter((page) => {
        const allowedTypes = (page.dataset.accountTypes || page.dataset.accountType || "")
            .split(/\s+/).filter(Boolean);
        return !allowedTypes.length || allowedTypes.includes(currentAccountType);
    });
    const pageId = window.location.hash.slice(1) || "dashboard";
    const activePage = allowedPages.find((page) => page.id === pageId)
        || allowedPages.find((page) => page.id === (currentAccountType === "job_provider" ? "provider-dashboard" : "dashboard"));
    if (!activePage) return;

    if (window.location.hash !== `#${activePage.id}`) {
        window.history.replaceState(null, "", `#${activePage.id}`);
    }

    const pageChanged = !activePage.classList.contains("active");
    pageViews.forEach((page) => {
        const isActive = page === activePage;
        page.hidden = !isActive;
        page.classList.toggle("active", isActive);
    });
    document.querySelectorAll(".nav-link").forEach((link) => {
        const linkTypes = (link.dataset.accountTypes || link.dataset.accountType || "")
            .split(/\s+/).filter(Boolean);
        const permitted = !linkTypes.length || linkTypes.includes(currentAccountType);
        link.hidden = !permitted;
        const isActive = link.getAttribute("href") === `#${activePage.id}`;
        link.classList.toggle("active", isActive);
        if (isActive) {
            link.setAttribute("aria-current", "page");
        } else {
            link.removeAttribute("aria-current");
        }
    });
    const profileLink = document.getElementById("sidebar-profile-link");
    const isProfilePage = ["my-profile", "employer-profile"].includes(activePage.id);
    profileLink.classList.toggle("active", isProfilePage);
    if (isProfilePage) {
        profileLink.setAttribute("aria-current", "page");
    } else {
        profileLink.removeAttribute("aria-current");
    }
    document.querySelectorAll("[data-nav-account-type]").forEach((label) => {
        label.hidden = label.dataset.navAccountType !== currentAccountType;
    });
    document.getElementById("page-title").textContent = activePage.dataset.pageTitle;

    if (pageChanged) {
        const mainContent = document.getElementById("main-content");
        const behavior = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
        const scrollTarget = getComputedStyle(mainContent).overflowY === "visible" ? window : mainContent;
        scrollTarget.scrollTo({ top: 0, behavior });
    }
}

function configureAiTaskOptions() {
    const taskSelect = document.getElementById("ai-task");
    const taskLabel = document.getElementById("ai-task-label");
    const tabs = document.querySelector(".ai-assistant-tabs");
    const isSeeker = currentAccountType === "job_seeker";
    taskSelect.hidden = isSeeker;
    taskLabel.hidden = isSeeker;
    if (tabs) tabs.hidden = !isSeeker;
    const options = [...taskSelect.options];
    options.forEach((option) => {
        option.hidden = Boolean(
            option.dataset.accountType
            && option.dataset.accountType !== currentAccountType
        );
    });
    if (taskSelect.selectedOptions[0]?.hidden) {
        taskSelect.value = options.find((option) => !option.hidden)?.value || "";
    }
}

async function setupSupabase() {
    const authSubmit = document.getElementById("auth-submit");
    authSubmit.disabled = true;
    const authCallback = new URLSearchParams(window.location.hash.slice(1));
    if (authCallback.has("error") || authCallback.has("error_code")) {
        const errorCode = authCallback.get("error_code");
        const expiredLink = errorCode === "otp_expired";
        const message = expiredLink
            ? "This email link has expired or was already used. For account verification, enter your email and request a fresh link below. For password recovery, request a new reset email."
            : "This authentication link could not be used. Sign in or request a new email link, then try again.";
        document.getElementById("resend-confirmation").hidden = !expiredLink;
        window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
        setMessage(authMessage, message, "error");
    }

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

    try {
        supabaseClient = window.supabase.createClient(url, anonKey, {
            auth: {
                autoRefreshToken: true,
                persistSession: true,
                detectSessionInUrl: true
            }
        });
    } catch (error) {
        setMessage(authMessage, "Could not initialize Supabase authentication. Check the project URL and public anon key in backend/.env, then restart CareerLens.", "error");
        return;
    }

    authSubmit.disabled = false;

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
    currentCareerProfile = {};
    careerProjects = [];
    portfolioAvailable = true;
    editingProjectId = null;
    dashboardSources = {};
    currentAccountType = null;
    currentJobListings = [];
    jobMatches = new Map();
    jobProfileSummary = null;
    learningResources = [];
    learningPlan = [];
    latestSkillGapResult = null;
    latestLearningRecommendations = null;
    learningRecommendationError = "";
    populateSkillJobListings();
    currentJobApplications = [];
    currentApplicationReviews = new Map();
    currentApplicantMatches = new Map();
    currentNotifications = [];
    const notificationCount = document.getElementById("notification-count");
    if (notificationCount) notificationCount.hidden = true;
    seekerApplications = [];
    editingJobId = null;
    applyingToJobId = null;
    jobForm.reset();
    jobApplicationForm.reset();
    if (jobDialog.open) jobDialog.close();
    if (jobApplicationDialog.open) jobApplicationDialog.close();
    applicationSearch.value = "";
    applicationFilter.value = "all";
    renderApplications();
    document.getElementById("profile-form").reset();
    document.getElementById("my-profile-form").reset();
    setMessage(document.getElementById("my-profile-message"), "");
    document.getElementById("employer-profile-form").reset();
    setMessage(document.getElementById("employer-profile-message"), "");
    document.getElementById("portfolio-form").reset();
    document.getElementById("portfolio-project-list").replaceChildren();
    document.getElementById("portfolio-empty").hidden = false;
    resetPortfolioEditor();
    document.getElementById("skill-form").reset();
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
    document.getElementById("my-profile-email").value = "";
    document.getElementById("employer-profile-email").value = "";
    document.getElementById("sidebar-profile-link").hidden = true;
    document.getElementById("sidebar-profile-link").href = "#my-profile";
    document.getElementById("sidebar-profile-link").setAttribute("aria-label", "Open profile");
    document.getElementById("provider-job-filter").value = "all";
    document.getElementById("provider-applicant-filter").value = "all";
    document.getElementById("job-search").value = "";
    document.getElementById("job-type-filter").value = "all";
    document.getElementById("job-sort").value = "relevance";
    const profileGuidance = document.getElementById("job-profile-guidance");
    profileGuidance.hidden = true;
    profileGuidance.textContent = "";
    document.getElementById("skill-job-listing").value = "";
    document.getElementById("profile-stat").textContent = "Build it";
    document.getElementById("skill-count").textContent = "--";
    document.getElementById("skill-results").hidden = true;
    document.getElementById("skill-gap-list").replaceChildren();
    setMessage(document.getElementById("app-message"), "");
    setMessage(document.getElementById("profile-message"), "");
    setMessage(document.getElementById("portfolio-message"), "");
    setMessage(document.getElementById("dashboard-message"), "");
    setMessage(document.getElementById("skill-message"), "");
    setMessage(document.getElementById("job-board-message"), "");
    setMessage(document.getElementById("provider-jobs-message"), "");
    setMessage(document.getElementById("provider-applicants-message"), "");
    setMessage(document.getElementById("my-job-applications-message"), "");
    document.getElementById("job-board-list").replaceChildren();
    document.getElementById("provider-job-list").replaceChildren();
    document.getElementById("provider-applicant-board").replaceChildren();
    document.getElementById("my-job-application-list").replaceChildren();
    document.getElementById("learning-resource-list").replaceChildren();
    document.getElementById("learning-in-progress-list").replaceChildren();
    document.getElementById("learning-completed-list").replaceChildren();
    document.getElementById("learning-not-started-list").replaceChildren();
    document.getElementById("learning-targeted-skills").replaceChildren();
    document.getElementById("learning-recommendations-list").replaceChildren();
    document.getElementById("learning-search").value = "";
    document.getElementById("learning-category-filter").value = "all";
    document.getElementById("learning-difficulty-filter").value = "all";
    setMessage(document.getElementById("learning-message"), "");
    setMessage(document.getElementById("skill-learning-message"), "");
    renderLearningWorkspace();
    renderDashboard();
}

async function openWorkspace(user) {
    if (currentUser && currentUser.id !== user.id) {
        clearWorkspaceData();
    }
    currentUser = user;
    authScreen.hidden = true;
    workspace.hidden = false;
    updateProfileIdentity(user);
    document.getElementById("my-profile-email").value = user.email || "";

    if (loadingUserId === user.id) return;
    loadingUserId = user.id;
    try {
        const { data, error } = await supabaseClient
            .from("user_accounts")
            .select("account_type")
            .eq("user_id", user.id)
            .maybeSingle();
        if (error) throw error;
        if (!data || !accountTypes.includes(data.account_type)) {
            throw new Error("Your CareerLens account type is missing. Run the latest backend/supabase_schema.sql in your Supabase SQL Editor, then sign in again.");
        }
        currentAccountType = data.account_type;
        const profileLink = document.getElementById("sidebar-profile-link");
        profileLink.hidden = false;
        profileLink.href = currentAccountType === "job_provider" ? "#employer-profile" : "#my-profile";
        profileLink.setAttribute(
            "aria-label",
            currentAccountType === "job_provider" ? "Open Employer Profile" : "Open My Profile"
        );
        configureAiTaskOptions();
        activatePageFromHash();
        if (currentAccountType === "job_provider") {
            await Promise.all([loadEmployerProfile(), loadProviderWorkspace()]);
            await loadNotifications();
        } else {
            dashboardSources = {
                profile: null,
                manualApplications: null,
                careerApplications: null,
                recommendations: null,
                learning: null,
                portfolio: null
            };
            renderDashboard();
            await Promise.all([
                loadApplications(),
                loadProfile(),
                loadSeekerApplications(),
                loadJobBoard(),
                loadLearningWorkspace(),
                loadPortfolioProjects(),
                loadNotifications(),
            ]);
        }
    } catch (error) {
        loadingUserId = null;
        setMessage(document.getElementById("app-message"), supabaseErrorMessage(error), "error");
    }
}

function updateProfileIdentity(user) {
    const displayName = user.user_metadata?.full_name || user.email?.split("@")[0] || "Career Explorer";
    document.getElementById("profile-name").textContent = displayName;
    document.getElementById("profile-email").textContent = user.email || "";
    document.getElementById("profile-avatar").textContent = displayName.trim().slice(0, 2).toUpperCase();
    const nameInput = document.getElementById("my-profile-name");
    if (nameInput) nameInput.value = user.user_metadata?.full_name || displayName;
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
    document.getElementById("account-type-selector").hidden = !signingUp;
    if (signingUp) {
        authForm.querySelector('input[name="account_type"][value="job_seeker"]').checked = true;
    }
    document.getElementById("auth-submit").textContent = signingUp ? "Create account" : "Sign in";
    document.getElementById("forgot-password").hidden = signingUp;
    setMessage(authMessage, "");
}

async function handleAuthSubmit(event) {
    event.preventDefault();
    if (!supabaseClient) {
        setMessage(authMessage, "Supabase authentication is not ready. Check your connection, reload CareerLens, and wait for the Sign in button to become enabled.", "error");
        return;
    }

    const formData = new FormData(authForm);
    const email = String(formData.get("email") || "").trim();
    const password = String(formData.get("password") || "");
    const button = document.getElementById("auth-submit");
    button.disabled = true;
    setMessage(authMessage, authMode === "sign-up" ? "Creating your account..." : "Signing in...");

    try {
        if (authMode === "sign-up") {
            const fullName = String(formData.get("name") || "").trim();
            const accountType = String(formData.get("account_type") || "job_seeker");
            if (!accountTypes.includes(accountType)) {
                throw new Error("Choose whether you are joining as a job seeker or job provider.");
            }
            const { data, error } = await supabaseClient.auth.signUp({
                email,
                password,
                options: {
                    data: { full_name: fullName, account_type: accountType },
                    emailRedirectTo: window.location.origin
                }
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
        button.disabled = !supabaseClient;
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

async function resendSignupConfirmation() {
    if (!supabaseClient) return;
    const email = document.getElementById("auth-email").value.trim();
    const button = document.getElementById("resend-confirmation");
    if (!email) {
        setMessage(authMessage, "Enter your email address first.", "error");
        document.getElementById("auth-email").focus();
        return;
    }

    button.disabled = true;
    try {
        const { error } = await supabaseClient.auth.resend({
            type: "signup",
            email,
            options: { emailRedirectTo: window.location.origin }
        });
        if (error) throw error;
        setMessage(authMessage, "If that address has an unverified account, a new verification link is on its way.", "success");
    } catch (error) {
        setMessage(authMessage, error.message || "Could not resend the verification email.", "error");
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
    const errorText = `${error?.message || ""} ${error?.details || ""}`;
    if (
        /user_accounts\.recruiter_title does not exist/i.test(errorText)
        || /recruiter_title.*user_accounts.*schema cache/i.test(errorText)
    ) {
        return "The employer profile field is missing. In the same Supabase project configured by backend/.env, run backend/migrations/phase11_employer_profile.sql, then reload CareerLens.";
    }
    if (/user_accounts|job_listings|job_applications|application_reviews|application-resumes|bucket not found/i.test(`${error?.message || ""} ${error?.details || ""}`)) {
        return "CareerLens could not find the latest hiring tables or private résumé storage. In the Supabase project configured in backend/.env, run the latest backend/supabase_schema.sql from the SQL Editor, then reload the app.";
    }
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
        dashboardSources.manualApplications = true;
        renderApplications();
        renderDashboard();
        return true;
    } catch (error) {
        if (currentUser?.id !== userId) return false;
        setMessage(document.getElementById("app-message"), supabaseErrorMessage(error), "error");
        applicationList.replaceChildren();
        dashboardSources.manualApplications = false;
        renderDashboard();
        return false;
    }
}

async function loadProviderWorkspace() {
    const userId = currentUser?.id;
    if (!userId) return;
    const [jobsResult, applicationsResult, reviewsResult] = await Promise.all([
        supabaseClient.from("job_listings").select("*").order("created_at", { ascending: false }),
        supabaseClient
            .from("job_applications")
            .select("id,job_id,applicant_id,applicant_name,applicant_email,cover_note,resume_path,status,created_at,job_listings(title,company)")
            .order("created_at", { ascending: false }),
        supabaseClient
            .from("application_reviews")
            .select("application_id,reviewer_notes,interview_at")
    ]);
    if (currentUser?.id !== userId) return;
    if (jobsResult.error) throw jobsResult.error;
    if (applicationsResult.error) throw applicationsResult.error;
    if (reviewsResult.error) throw reviewsResult.error;
    currentJobListings = jobsResult.data || [];
    currentJobApplications = applicationsResult.data || [];
    currentApplicationReviews = new Map(
        (reviewsResult.data || []).map((review) => [review.application_id, review])
    );
    currentApplicantMatches = new Map();
    try {
        const rankingResult = await careerApi("/api/provider-applicant-rankings");
        (rankingResult.rankings || []).forEach((ranking) => {
            currentApplicantMatches.set(ranking.application_id, ranking.match);
        });
    } catch (error) {
        setMessage(
            document.getElementById("provider-applicants-message"),
            error.message || "Applicant evidence rankings are unavailable.",
            "error"
        );
    }
    renderProviderWorkspace();
}

async function loadSeekerApplications() {
    const userId = currentUser?.id;
    if (!userId) return;
    const { data, error } = await supabaseClient
        .from("job_applications")
        .select("id,job_id,job_title,company,status,resume_path,created_at")
        .order("created_at", { ascending: false });
    if (currentUser?.id !== userId) return;
    if (error) {
        dashboardSources.careerApplications = false;
        setMessage(document.getElementById("my-job-applications-message"), supabaseErrorMessage(error), "error");
        renderDashboard();
        return;
    }
    seekerApplications = data || [];
    dashboardSources.careerApplications = true;
    renderSeekerApplications();
    renderDashboard();
}

async function loadJobBoard() {
    const userId = currentUser?.id;
    if (!userId || currentAccountType !== "job_seeker") return;
    setMessage(
        document.getElementById("job-board-message"),
        "Comparing your profile with published jobs..."
    );
    try {
        const result = await careerApi("/api/job-recommendations");
        if (currentUser?.id !== userId) return;
        if (!result || !Array.isArray(result.jobs) || !result.profile) {
            throw new Error("The recommendation service returned an unexpected response.");
        }
        const providerIds = [...new Set(
            result.jobs.map((job) => job?.provider_id).filter(Boolean)
        )];
        const recruiterProfilesResult = providerIds.length
            ? await supabaseClient
                .from("user_accounts")
                .select("user_id,display_name,recruiter_title")
                .in("user_id", providerIds)
            : { data: [], error: null };
        if (currentUser?.id !== userId) return;
        const recruiterProfiles = new Map(
            (recruiterProfilesResult.data || [])
                .map((profile) => [profile.user_id, profile])
        );
        currentJobListings = result.jobs.map((job) => ({
            ...job,
            recruiter_profile: recruiterProfiles.get(job.provider_id) || null
        }));
        jobMatches = new Map(
            result.jobs.filter((job) => job?.id && job.match)
                .map((job) => [job.id, job.match])
        );
        jobProfileSummary = result.profile;
        dashboardSources.recommendations = true;
        populateSkillJobListings();
        populateApplicationMaterialJobs();
        renderJobBoard();
        const guidance = document.getElementById("job-profile-guidance");
        const missing = jobProfileSummary.missing_fields || [];
        const messages = [];
        if (recruiterProfilesResult.error) {
            messages.push(
                `Recruiter details are unavailable: ${supabaseErrorMessage(recruiterProfilesResult.error)}`
            );
        }
        if (!jobProfileSummary.complete && missing.length) {
            messages.push(
                `Your profile is incomplete (${missing.join(", ")} missing). Recommendations may be less informative until you add genuine profile skills and experience. Update your profile in My Profile.`
            );
        }
        if (jobProfileSummary.learning_records_available === false) {
            messages.push(
                "Learning-plan records are unavailable, so saved learning activity is not included in these explanations."
            );
        }
        if (jobProfileSummary.portfolio_evidence_available === false) {
            messages.push(
                "Private portfolio projects are not included. Install the Phase 5 portfolio migration to use project evidence."
            );
        }
        guidance.hidden = !messages.length;
        guidance.textContent = messages.join(" ");
        setMessage(document.getElementById("job-board-message"), "");
        renderDashboard();
    } catch (error) {
        if (currentUser?.id !== userId) return;
        currentJobListings = [];
        jobMatches = new Map();
        jobProfileSummary = null;
        dashboardSources.recommendations = false;
        const guidance = document.getElementById("job-profile-guidance");
        guidance.hidden = true;
        guidance.textContent = "";
        populateSkillJobListings();
        setMessage(
            document.getElementById("job-board-message"),
            error.message || "Could not load job recommendations.",
            "error"
        );
        renderJobBoard();
        renderDashboard();
    }
}

function populateApplicationMaterialJobs() {
    const select = document.getElementById("application-material-job");
    if (!select) return;
    const selected = select.value;
    select.replaceChildren();
    select.add(new Option("Choose a listing", ""));
    currentJobListings
        .filter((job) => job.status === "published")
        .forEach((job) => select.add(new Option(`${job.title} · ${job.company}`, job.id)));
    if (currentJobListings.some((job) => job.id === selected)) {
        select.value = selected;
    }
}

async function loadApplicationMaterials(jobId) {
    const message = document.getElementById("application-material-message");
    const result = document.getElementById("application-material-result");
    result.hidden = true;
    if (!jobId) {
        setMessage(message, "");
        return;
    }
    setMessage(message, "Loading saved materials...");
    try {
        const { data: { session }, error: sessionError } = await supabaseClient.auth.getSession();
        if (sessionError) throw sessionError;
        if (!session) throw new Error("Your session has expired. Please sign in again.");
        const response = await fetch(`/api/application-materials/${encodeURIComponent(jobId)}`, {
            headers: { Authorization: `Bearer ${session.access_token}` }
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || "Could not load saved materials.");
        if (payload) {
            renderApplicationMaterials(payload);
            setMessage(message, "Saved draft loaded.", "success");
        } else {
            setMessage(message, "No saved draft yet. Generate one for this job.");
        }
    } catch (error) {
        setMessage(message, error.message || "Could not load saved materials.", "error");
    }
}

function renderApplicationMaterials(payload) {
    const job = currentJobListings.find((listing) => listing.id === payload.job_id);
    document.getElementById("application-material-job-title").textContent =
        job ? `${job.title} · ${job.company}` : "Selected job";
    const list = document.getElementById("application-material-bullets");
    list.replaceChildren();
    (payload.bullets || []).forEach((bullet) => {
        const item = document.createElement("li");
        item.textContent = bullet;
        list.appendChild(item);
    });
    document.getElementById("application-material-cover-letter").textContent =
        payload.cover_letter || "";
    document.getElementById("application-material-result").hidden = false;
}

async function generateApplicationMaterials(event) {
    event.preventDefault();
    const jobId = document.getElementById("application-material-job").value;
    const consent = document.getElementById("application-material-consent");
    const message = document.getElementById("application-material-message");
    const button = document.getElementById("application-material-submit");
    if (!jobId) {
        setMessage(message, "Choose a published job listing.", "error");
        return;
    }
    if (!consent.checked) {
        setMessage(message, "Confirm consent before sending the profile and job details to Gemini.", "error");
        return;
    }
    button.disabled = true;
    setMessage(message, "Using your profile and portfolio evidence to draft application materials...");
    try {
        const { data: { session }, error: sessionError } = await supabaseClient.auth.getSession();
        if (sessionError) throw sessionError;
        if (!session) throw new Error("Your session has expired. Please sign in again.");
        const response = await fetch("/api/application-materials", {
            method: "POST",
            headers: {
                Authorization: `Bearer ${session.access_token}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ job_id: jobId, consent: consent.checked })
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || "Could not generate application materials.");
        renderApplicationMaterials(payload);
        setMessage(message, "Tailored draft generated and saved.", "success");
    } catch (error) {
        setMessage(message, error.message || "Could not generate application materials.", "error");
    } finally {
        consent.checked = false;
        button.disabled = false;
    }
}

async function copyApplicationMaterials() {
    const bullets = [...document.querySelectorAll("#application-material-bullets li")]
        .map((item) => `• ${item.textContent}`)
        .join("\n");
    const coverLetter = document.getElementById("application-material-cover-letter").textContent;
    try {
        await navigator.clipboard.writeText(`${bullets}\n\nCover Letter\n\n${coverLetter}`);
        setMessage(document.getElementById("application-material-message"), "Résumé bullets and cover letter copied.", "success");
    } catch (error) {
        setMessage(document.getElementById("application-material-message"), "Could not access the clipboard.", "error");
    }
}

function populateSkillJobListings() {
    const select = document.getElementById("skill-job-listing");
    select.replaceChildren();
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "Enter a job description below";
    select.appendChild(placeholder);
    currentJobListings.forEach((job) => {
        const option = document.createElement("option");
        option.value = job.id;
        option.textContent = `${job.title} · ${job.company}`;
        select.appendChild(option);
    });
}

function fillSkillAnalysisFromJob() {
    const job = currentJobListings.find(
        (listing) => listing.id === document.getElementById("skill-job-listing").value
    );
    if (!job) return;
    document.getElementById("skill-target-role").value = job.title;
    document.getElementById("skill-job-description").value =
        [job.description, job.requirements].filter(Boolean).join("\n\n");
}

function renderProviderWorkspace() {
    renderProviderJobs();
    renderProviderApplicants();
    renderProviderMetrics();
}

function renderProviderMetrics() {
    const open = currentJobListings.filter((job) => job.status === "published").length;
    const closed = currentJobListings.filter((job) => job.status === "closed").length;
    const review = currentJobApplications.filter((application) =>
        ["Submitted", "CV review", "Shortlisted", "Interview"].includes(application.status)
    ).length;
    document.getElementById("provider-open-count").textContent = String(open);
    document.getElementById("provider-applicant-count").textContent = String(currentJobApplications.length);
    document.getElementById("provider-review-count").textContent = String(review);
    document.getElementById("provider-closed-count").textContent = String(closed);

    const recent = document.getElementById("provider-recent-applicants");
    recent.replaceChildren();
    currentJobApplications.slice(0, 4).forEach((application) => {
        const row = document.createElement("article");
        row.className = "provider-applicant-row";
        const details = document.createElement("div");
        const name = document.createElement("strong");
        name.textContent = application.applicant_name;
        const role = document.createElement("small");
        role.textContent = application.job_listings?.title || "Job listing";
        details.append(name, role);
        const status = document.createElement("span");
        status.className = "job-status";
        status.textContent = application.status;
        row.append(details, status);
        recent.appendChild(row);
    });
    if (!currentJobApplications.length) {
        recent.appendChild(createEmptyState("No applications yet", "Publish a job to start receiving applications."));
    }
}

function createEmptyState(title, message) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    const icon = document.createElement("div");
    icon.className = "empty-icon";
    icon.appendChild(createIcon("search"));
    const heading = document.createElement("strong");
    heading.textContent = title;
    const description = document.createElement("p");
    description.textContent = message;
    empty.append(icon, heading, description);
    return empty;
}

function createMatchSkillList(title, skills) {
    const section = document.createElement("section");
    section.className = "job-match-skill-group";
    const heading = document.createElement("h4");
    heading.textContent = title;
    section.appendChild(heading);
    if (!skills.length) {
        const empty = document.createElement("p");
        empty.textContent = "No explicitly classified skills in this group.";
        section.appendChild(empty);
        return section;
    }

    const list = document.createElement("ul");
    skills.forEach((skill) => {
        const item = document.createElement("li");
        const label = document.createElement("strong");
        label.textContent = `${skill.name} · ${skill.status}`;
        item.appendChild(label);
        const excerpt = document.createElement("p");
        excerpt.textContent = `Job listing: ${skill.excerpt}`;
        item.appendChild(excerpt);
        skill.evidence.forEach((evidence) => {
            const evidenceText = document.createElement("p");
            evidenceText.textContent = `${evidence.source}: ${evidence.excerpt}`;
            item.appendChild(evidenceText);
        });
        const explanation = document.createElement("p");
        explanation.textContent = skill.explanation;
        item.appendChild(explanation);
        list.appendChild(item);
    });
    section.appendChild(list);
    return section;
}

function createJobMatchDetails(job, match) {
    const details = document.createElement("details");
    details.className = "job-match-details";
    const summary = document.createElement("summary");
    summary.textContent = "Why this job is recommended";
    details.appendChild(summary);

    const explanation = document.createElement("div");
    explanation.className = "job-match-explanation";
    const score = document.createElement("p");
    score.className = "job-match-score-explanation";
    score.textContent = match.score === null
        ? "Profile alignment score unavailable. Add saved profile skills or experience to compare against recognized requirements."
        : `Profile-to-job evidence alignment: ${match.score}/100. Required skills carry 80% of the score and preferred skills 20% when both are present. Demonstrated profile context counts as 100%, a listed skill without context as 35%, and no evidence found as 0%.`;
    explanation.appendChild(score);
    explanation.append(
        createMatchSkillList("Required skills", match.required_skills || []),
        createMatchSkillList("Preferred skills", match.preferred_skills || [])
    );

    const otherSkills = match.other_skill_mentions || [];
    if (otherSkills.length) {
        const other = document.createElement("p");
        other.className = "job-match-other-skills";
        other.textContent = `Other skill mentions not used in the score (not explicitly marked required or preferred): ${otherSkills.map((skill) => skill.name).join(", ")}.`;
        explanation.appendChild(other);
    }

    if ((match.next_steps || []).length) {
        const nextHeading = document.createElement("h4");
        nextHeading.textContent = "Suggested next steps";
        const nextSteps = document.createElement("ul");
        match.next_steps.forEach((step) => {
            const item = document.createElement("li");
            item.textContent = step;
            nextSteps.appendChild(item);
        });
        explanation.append(nextHeading, nextSteps);
    }

    const limitations = document.createElement("ul");
    limitations.className = "job-match-limitations";
    (match.limitations || []).forEach((limitation) => {
        const item = document.createElement("li");
        item.textContent = limitation;
        limitations.appendChild(item);
    });
    explanation.appendChild(limitations);

    const learningSkills = [
        ...(match.required_skills || []),
        ...(match.preferred_skills || [])
    ].filter((skill) => skill.status !== "Demonstrated");
    if (learningSkills.length) {
        const learningHeading = document.createElement("h4");
        learningHeading.textContent = "Learning resources for skills to investigate";
        const learningMessage = document.createElement("p");
        learningMessage.className = "job-learning-message";
        learningMessage.setAttribute("role", "status");
        learningMessage.setAttribute("aria-live", "polite");
        const learningList = document.createElement("div");
        learningList.className = "job-learning-resource-list";
        const button = document.createElement("button");
        button.className = "secondary-button";
        button.type = "button";
        button.textContent = "Find matching learning resources";
        button.addEventListener("click", async () => {
            button.disabled = true;
            learningMessage.classList.remove("error", "success");
            learningMessage.textContent = "Finding resources in the learning catalogue...";
            learningList.replaceChildren();
            try {
                const resources = await careerApi("/api/learning/recommendations", {
                    method: "POST",
                    body: JSON.stringify({
                        skills: learningSkills.map(({ name, status }) => ({ name, status }))
                    })
                });
                if (!Array.isArray(resources)) {
                    throw new Error("The learning service returned an unexpected response.");
                }
                if (!resources.length) {
                    learningMessage.textContent = "No matching resources are currently available in the learning catalogue.";
                    return;
                }
                learningMessage.textContent = "";
                resources.forEach((resource) => {
                    learningList.appendChild(createLearningResourceCard(resource, {
                        matchedSkills: resource.matched_skills || [],
                        feedbackMessageId: "learning-message"
                    }));
                });
            } catch (error) {
                learningMessage.textContent =
                    error.message || "Could not load matching learning resources.";
                learningMessage.classList.add("error");
            } finally {
                button.disabled = false;
            }
        });
        explanation.append(learningHeading, button, learningMessage, learningList);
    }

    details.appendChild(explanation);
    return details;
}

function createJobCard(job, { provider = false, application = null, match = null } = {}) {
    const card = document.createElement("article");
    card.className = provider ? "provider-job-card" : "job-card";
    const matchDetails = match || (job.id ? jobMatches.get(job.id) : null);
    const heading = document.createElement("div");
    heading.className = "job-card-heading";
    const identity = document.createElement("div");
    const title = document.createElement("h3");
    title.textContent = job.title;
    const company = document.createElement("p");
    company.textContent = job.company;
    identity.append(title, company);
    const recruiter = job.recruiter_profile;
    if (!provider && recruiter && (recruiter.display_name || recruiter.recruiter_title)) {
        const recruiterDetails = document.createElement("p");
        recruiterDetails.className = "job-card-recruiter";
        recruiterDetails.textContent = [
            "Recruiter",
            [recruiter.display_name, recruiter.recruiter_title].filter(Boolean).join(" · ")
        ].join(": ");
        identity.appendChild(recruiterDetails);
    }
    heading.appendChild(identity);

    const status = document.createElement("span");
    const statusLabel = application?.status || job.status || "Published";
    status.className = `job-status status-${statusLabel.toLowerCase().replaceAll(" ", "-")}`;
    status.textContent = statusLabel;
    heading.appendChild(status);
    if (!provider && matchDetails) {
        const score = document.createElement("span");
        score.className = "job-match-score";
        score.textContent = matchDetails.score === null
            ? "Profile match unavailable"
            : `${matchDetails.score}/100 alignment`;
        heading.appendChild(score);
    }
    card.appendChild(heading);

    const metadata = document.createElement("div");
    metadata.className = "job-card-metadata";
    [job.location, job.workplace_type, job.employment_type].filter(Boolean).forEach((value) => {
        const tag = document.createElement("span");
        tag.textContent = value;
        metadata.appendChild(tag);
    });
    card.appendChild(metadata);

    if (provider) {
        const description = document.createElement("p");
        description.className = "job-card-description";
        description.textContent = job.description;
        card.appendChild(description);
        const actions = document.createElement("div");
        actions.className = "job-card-actions";
        const edit = document.createElement("button");
        edit.className = "secondary-button";
        edit.type = "button";
        edit.textContent = "Edit";
        edit.addEventListener("click", () => openJobDialog(job));
        actions.appendChild(edit);
        const statusSelect = document.createElement("select");
        statusSelect.setAttribute("aria-label", `Listing status for ${job.title}`);
        [["draft", "Draft"], ["published", "Published"], ["closed", "Closed"]].forEach(([value, label]) => {
            const option = document.createElement("option");
            option.value = value;
            option.textContent = label;
            option.selected = job.status === value;
            statusSelect.appendChild(option);
        });
        statusSelect.addEventListener("change", () => updateJobStatus(job.id, statusSelect.value, statusSelect));
        actions.appendChild(statusSelect);
        card.appendChild(actions);
        return card;
    }

    if (matchDetails) {
        card.appendChild(createJobMatchDetails(job, matchDetails));
    }
    const tailorButton = document.createElement("button");
    tailorButton.type = "button";
    tailorButton.className = "secondary-button";
    tailorButton.textContent = "Tailor resume & cover letter";
    tailorButton.addEventListener("click", () => {
        window.location.hash = "application-materials";
        document.getElementById("application-material-job").value = job.id;
        loadApplicationMaterials(job.id);
    });
    card.appendChild(tailorButton);

    if (application) {
        const applicationDate = document.createElement("p");
        applicationDate.className = "job-application-date";
        applicationDate.textContent = `Applied ${formatApplicationDate(application.created_at.slice(0, 10))}`;
        card.append(applicationDate);
        if (!["Hired", "Rejected", "Withdrawn"].includes(application.status)) {
            const withdraw = document.createElement("button");
            withdraw.className = "secondary-button withdraw-application-button";
            withdraw.type = "button";
            withdraw.textContent = "Withdraw application";
            withdraw.setAttribute("aria-label", `Withdraw application for ${job.title}`);
            withdraw.addEventListener("click", () => withdrawJobApplication(application, withdraw));
            card.appendChild(withdraw);
        }
        return card;
    }

    const description = document.createElement("p");
    description.className = "job-card-description";
    description.textContent = job.description;
    card.appendChild(description);
    if (job.requirements) {
        const requirements = document.createElement("details");
        const summary = document.createElement("summary");
        summary.textContent = "View requirements";
        const requirementsText = document.createElement("p");
        requirementsText.textContent = job.requirements;
        requirements.append(summary, requirementsText);
        card.appendChild(requirements);
    }
    const apply = document.createElement("button");
    apply.className = "primary-button";
    apply.type = "button";
    apply.textContent = application ? "Application submitted" : "Apply for this job";
    apply.disabled = Boolean(application);
    apply.addEventListener("click", () => openJobApplication(job));
    card.appendChild(apply);
    return card;
}

function renderProviderJobs() {
    const list = document.getElementById("provider-job-list");
    list.replaceChildren();
    if (!currentJobListings.length) {
        list.appendChild(createEmptyState("Your first role starts here", "Create a listing to introduce your opportunity to job seekers."));
    } else {
        currentJobListings.forEach((job) => list.appendChild(createJobCard(job, { provider: true })));
    }
    updateProviderJobFilter();
}

function updateProviderJobFilter() {
    const filter = document.getElementById("provider-job-filter");
    const selected = filter.value;
    filter.replaceChildren(new Option("All job listings", "all"));
    currentJobListings.forEach((job) => filter.add(new Option(`${job.title} · ${job.company}`, job.id)));
    filter.value = currentJobListings.some((job) => job.id === selected) ? selected : "all";
}

function renderProviderApplicants() {
    const list = document.getElementById("provider-applicant-board");
    const recent = document.getElementById("provider-recent-applicants");
    const jobId = document.getElementById("provider-job-filter").value;
    const statusFilter = document.getElementById("provider-applicant-filter").value;
    const filtered = currentJobApplications.filter((application) =>
        (jobId === "all" || application.job_id === jobId)
        && (statusFilter === "all" || application.status === statusFilter)
    );
    filtered.sort((first, second) => {
        const firstScore = currentApplicantMatches.get(first.id)?.score;
        const secondScore = currentApplicantMatches.get(second.id)?.score;
        return (secondScore ?? -1) - (firstScore ?? -1);
    });
    list.replaceChildren();
    if (!filtered.length) {
        list.appendChild(createEmptyState("No applicants to show", "Applications appear here when someone applies to one of your published jobs."));
        return;
    }
    filtered.forEach((application) => {
        const card = document.createElement("article");
        card.className = "provider-applicant-card";
        const details = document.createElement("div");
        details.className = "provider-applicant-details";
        const name = document.createElement("h3");
        name.textContent = application.applicant_name;
        const email = document.createElement("a");
        email.href = `mailto:${application.applicant_email}`;
        email.textContent = application.applicant_email;
        const role = document.createElement("p");
        role.textContent = `${application.job_listings?.title || "Job listing"} · ${application.job_listings?.company || ""}`;
        const note = document.createElement("p");
        note.className = "provider-cover-note";
        note.textContent = application.cover_note || "No message included.";
        details.append(name, email, role, note);
        const match = currentApplicantMatches.get(application.id);
        if (match) {
            const matchScore = document.createElement("span");
            matchScore.className = "job-match-score";
            matchScore.textContent = match.score === null
                ? "Alignment unavailable"
                : `${match.score}/100 evidence alignment`;
            details.appendChild(matchScore);
            details.appendChild(createApplicantMatchDetails(match));
        }
        const resume = document.createElement("button");
        resume.type = "button";
        resume.className = "secondary-button applicant-resume-button";
        resume.disabled = !application.resume_path;
        resume.textContent = application.resume_path ? "View résumé / CV" : "No résumé attached";
        if (application.resume_path) {
            resume.addEventListener("click", () => openApplicantResume(application, resume));
        }
        details.appendChild(resume);
        const status = document.createElement("select");
        status.setAttribute("aria-label", `Application status for ${application.applicant_name}`);
        ["Submitted", "CV review", "Shortlisted", "Interview", "Offer", "Hired", "Rejected"].forEach((value) => {
            const option = new Option(value, value, false, value === application.status);
            status.appendChild(option);
        });
        status.addEventListener("change", () => updateJobApplicationStatus(application.id, status.value, status));
        const date = document.createElement("small");
        date.textContent = formatApplicationDate(application.created_at.slice(0, 10));
        const review = currentApplicationReviews.get(application.id);
        const reviewPanel = document.createElement("div");
        reviewPanel.className = "applicant-review-panel";
        const reviewHeading = document.createElement("strong");
        reviewHeading.textContent = "Private hiring notes";
        const interviewLabel = document.createElement("label");
        interviewLabel.textContent = "Interview date (optional)";
        const interviewInput = document.createElement("input");
        interviewInput.type = "datetime-local";
        interviewInput.setAttribute("aria-label", `Interview date for ${application.applicant_name}`);
        interviewInput.value = review?.interview_at ? toLocalDateTimeValue(review.interview_at) : "";
        interviewLabel.appendChild(interviewInput);
        const notesLabel = document.createElement("label");
        notesLabel.textContent = "Reviewer notes (only visible to your hiring team)";
        const notesInput = document.createElement("textarea");
        notesInput.rows = 3;
        notesInput.maxLength = 4000;
        notesInput.placeholder = "Record role-related strengths, questions, and next steps...";
        notesInput.value = review?.reviewer_notes || "";
        notesLabel.appendChild(notesInput);
        const saveReview = document.createElement("button");
        saveReview.type = "button";
        saveReview.className = "secondary-button";
        saveReview.textContent = "Save review notes";
        saveReview.addEventListener("click", () => saveApplicationReview(application.id, notesInput, interviewInput, saveReview));
        reviewPanel.append(reviewHeading, interviewLabel, notesLabel, saveReview);
        card.append(details, status, date, reviewPanel);
        list.appendChild(card);
    });
}

function createApplicantMatchDetails(match) {
    const details = document.createElement("details");
    details.className = "job-match-details applicant-match-details";
    const summary = document.createElement("summary");
    summary.textContent = "View evidence breakdown";
    details.appendChild(summary);
    const explanation = document.createElement("div");
    explanation.className = "job-match-explanation";
    const score = document.createElement("p");
    score.className = "job-match-score-explanation";
    score.textContent = match.score === null
        ? "No alignment score is shown because the applicant has no saved profile evidence for recognized requirements."
        : `Evidence alignment: ${match.score}/100. Required skills carry 80% and preferred skills 20% when both groups are present.`;
    explanation.append(
        score,
        createMatchSkillList("Required skills", match.required_skills || []),
        createMatchSkillList("Preferred skills", match.preferred_skills || [])
    );
    const limitations = document.createElement("ul");
    limitations.className = "job-match-limitations";
    (match.limitations || []).forEach((limitation) => {
        const item = document.createElement("li");
        item.textContent = limitation;
        limitations.appendChild(item);
    });
    explanation.appendChild(limitations);
    details.appendChild(explanation);
    return details;
}

async function openApplicantResume(application, button) {
    const preview = window.open("about:blank", "_blank");
    if (!preview) {
        setMessage(document.getElementById("provider-applicants-message"), "Allow pop-ups to open the résumé in a new tab.", "error");
        return;
    }
    preview.opener = null;
    button.disabled = true;
    try {
        const { data, error } = await supabaseClient.storage
            .from("application-resumes")
            .createSignedUrl(application.resume_path, 300);
        if (error) throw error;
        preview.location.href = data.signedUrl;
    } catch (error) {
        preview.close();
        setMessage(document.getElementById("provider-applicants-message"), supabaseErrorMessage(error), "error");
    } finally {
        button.disabled = false;
    }
}

function toLocalDateTimeValue(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

async function saveApplicationReview(applicationId, notesInput, interviewInput, button) {
    const previousLabel = button.textContent;
    button.disabled = true;
    button.textContent = "Saving...";
    try {
        await careerApi(`/api/provider/application-reviews/${applicationId}`, {
            method: "POST",
            body: JSON.stringify({
                reviewer_notes: notesInput.value.trim(),
                interview_at: interviewInput.value ? new Date(interviewInput.value).toISOString() : null
            })
        });
        currentApplicationReviews.set(applicationId, {
            application_id: applicationId,
            reviewer_notes: notesInput.value.trim(),
            interview_at: interviewInput.value ? new Date(interviewInput.value).toISOString() : null
        });
        setMessage(document.getElementById("provider-applicants-message"), "Private review notes saved.", "success");
        await loadNotifications();
    } catch (error) {
        setMessage(document.getElementById("provider-applicants-message"), supabaseErrorMessage(error), "error");
    } finally {
        button.disabled = false;
        button.textContent = previousLabel;
    }
}

function renderJobBoard() {
    const list = document.getElementById("job-board-list");
    const query = document.getElementById("job-search").value.trim().toLocaleLowerCase();
    const type = document.getElementById("job-type-filter").value;
    const sort = document.getElementById("job-sort").value;
    const appliedIds = new Set(seekerApplications.map((application) => application.job_id));
    const filtered = currentJobListings.filter((job) =>
        (type === "all" || job.employment_type === type)
        && (!query || `${job.title} ${job.company} ${job.location} ${job.description} ${job.requirements}`
            .toLocaleLowerCase().includes(query))
    );
    filtered.sort((first, second) => {
        if (sort === "newest") {
            return String(second.created_at || "").localeCompare(String(first.created_at || ""));
        }
        const firstScore = jobMatches.get(first.id)?.score;
        const secondScore = jobMatches.get(second.id)?.score;
        if (firstScore === null || firstScore === undefined) {
            return secondScore === null || secondScore === undefined ? 0 : 1;
        }
        if (secondScore === null || secondScore === undefined) return -1;
        return secondScore - firstScore;
    });
    list.replaceChildren();
    if (!filtered.length) {
        const hasLoadError = document.getElementById("job-board-message").classList.contains("error");
        list.appendChild(createEmptyState(
            hasLoadError ? "Recommendations unavailable" : "No jobs found",
            hasLoadError
                ? "Your application and learning workflows are unchanged. Try reloading this page later."
                : currentJobListings.length
                    ? "Try another search or employment type."
                    : "No published opportunities are available right now. Try a different filter or check again later."
        ));
        return;
    }
    filtered.forEach((job) => {
        const application = appliedIds.has(job.id) ? seekerApplications.find((item) => item.job_id === job.id) : null;
        list.appendChild(createJobCard(job, { application, match: jobMatches.get(job.id) }));
    });
}

function renderSeekerApplications() {
    const list = document.getElementById("my-job-application-list");
    list.replaceChildren();
    if (!seekerApplications.length) {
        list.appendChild(createEmptyState("No CareerLens applications yet", "Browse provider listings and apply to see their status here."));
        return;
    }
    seekerApplications.forEach((application) => {
        const job = { title: application.job_title, company: application.company };
        list.appendChild(createJobCard(job, { application }));
    });
    renderJobBoard();
}

async function withdrawJobApplication(application, button) {
    if (!window.confirm(`Withdraw your application for ${application.job_title}? The employer will see that it was withdrawn.`)) {
        return;
    }
    const userId = currentUser?.id;
    if (!userId) return;
    button.disabled = true;
    try {
        const { error } = await supabaseClient
            .from("job_applications")
            .update({ status: "Withdrawn" })
            .eq("id", application.id)
            .eq("applicant_id", userId);
        if (error) throw error;
        if (currentUser?.id !== userId) return;
        setMessage(document.getElementById("my-job-applications-message"), "Your application has been withdrawn.", "success");
        await loadSeekerApplications();
    } catch (error) {
        setMessage(document.getElementById("my-job-applications-message"), supabaseErrorMessage(error), "error");
    } finally {
        button.disabled = false;
    }
}

function openJobDialog(job = null) {
    editingJobId = job?.id || null;
    jobForm.reset();
    document.getElementById("job-dialog-title").textContent = job ? "Edit job listing" : "Post a job";
    document.getElementById("job-submit").textContent = job ? "Save changes" : "Save job";
    if (job) {
        for (const field of ["title", "company", "location", "workplace_type", "employment_type", "description", "requirements", "status"]) {
            jobForm.elements[field].value = job[field] || "";
        }
    } else {
        jobForm.elements.company.value = currentUser?.user_metadata?.company_name || "";
    }
    setMessage(document.getElementById("job-form-message"), "");
    jobDialog.showModal();
}

function openJobApplication(job) {
    applyingToJobId = job.id;
    jobApplicationForm.reset();
    document.getElementById("job-application-title").textContent = `Apply: ${job.title}`;
    document.getElementById("candidate-name").value =
        currentUser?.user_metadata?.full_name || "";
    document.getElementById("candidate-email").value = currentUser?.email || "";
    setMessage(document.getElementById("job-application-message"), "");
    jobApplicationDialog.showModal();
}

async function saveJobListing(event) {
    event.preventDefault();
    const button = document.getElementById("job-submit");
    button.disabled = true;
    const values = new FormData(jobForm);
    const payload = Object.fromEntries([
        "title", "company", "location", "workplace_type", "employment_type", "description", "requirements", "status"
    ].map((key) => [key, String(values.get(key) || "").trim()]));
    try {
        const result = editingJobId
            ? await supabaseClient.from("job_listings").update(payload).eq("id", editingJobId)
            : await supabaseClient.from("job_listings").insert(payload);
        if (result.error) throw result.error;
        jobDialog.close();
        await loadProviderWorkspace();
        setMessage(document.getElementById("provider-jobs-message"), "Job listing saved.", "success");
    } catch (error) {
        setMessage(document.getElementById("job-form-message"), supabaseErrorMessage(error), "error");
    } finally {
        button.disabled = false;
    }
}

async function updateJobStatus(id, status, control) {
    control.disabled = true;
    try {
        const { error } = await supabaseClient.from("job_listings").update({ status }).eq("id", id);
        if (error) throw error;
        await loadProviderWorkspace();
        setMessage(document.getElementById("provider-jobs-message"), "Listing status updated.", "success");
    } catch (error) {
        setMessage(document.getElementById("provider-jobs-message"), supabaseErrorMessage(error), "error");
        control.value = currentJobListings.find((job) => job.id === id)?.status || "draft";
    } finally {
        control.disabled = false;
    }
}

async function submitJobApplication(event) {
    event.preventDefault();
    if (!applyingToJobId) return;
    const button = document.getElementById("job-application-submit");
    button.disabled = true;
    const values = new FormData(jobApplicationForm);
    const resumeFile = values.get("resume");
    if (!(resumeFile instanceof File) || !resumeFile.name) {
        setMessage(document.getElementById("job-application-message"), "Choose your résumé as a PDF before applying.", "error");
        button.disabled = false;
        return;
    }
    if (resumeFile.size > maxResumeBytes) {
        setMessage(document.getElementById("job-application-message"), `The résumé PDF must be ${Math.floor(maxResumeBytes / 1024 / 1024)} MB or smaller.`, "error");
        button.disabled = false;
        return;
    }
    if (!resumeFile.name.toLowerCase().endsWith(".pdf")
        || (resumeFile.type && resumeFile.type !== "application/pdf")) {
        setMessage(document.getElementById("job-application-message"), "Upload a PDF résumé file.", "error");
        button.disabled = false;
        return;
    }
    if (!document.getElementById("candidate-consent").checked) {
        setMessage(document.getElementById("job-application-message"), "Confirm that you want to share your application and résumé with this provider.", "error");
        button.disabled = false;
        return;
    }
    if (!currentUser?.id) {
        setMessage(document.getElementById("job-application-message"), "Your session has expired. Please sign in again.", "error");
        button.disabled = false;
        return;
    }
    const payload = {
        job_id: applyingToJobId,
        job_title: currentJobListings.find((job) => job.id === applyingToJobId)?.title || "",
        company: currentJobListings.find((job) => job.id === applyingToJobId)?.company || "",
        applicant_name: String(values.get("applicant_name") || "").trim(),
        applicant_email: String(values.get("applicant_email") || "").trim(),
        cover_note: String(values.get("cover_note") || "").trim()
    };
    const resumePath = `${currentUser.id}/${applyingToJobId}/${crypto.randomUUID()}.pdf`;
    try {
        const signature = new TextDecoder().decode(await resumeFile.slice(0, 5).arrayBuffer());
        if (signature !== "%PDF-") {
            throw new Error("This file does not appear to be a valid PDF.");
        }
        setMessage(document.getElementById("job-application-message"), "Uploading your résumé...");
        const upload = await supabaseClient.storage
            .from("application-resumes")
            .upload(resumePath, resumeFile, {
                cacheControl: "300",
                contentType: "application/pdf",
                upsert: false
            });
        if (upload.error) throw upload.error;

        const { error } = await supabaseClient.from("job_applications").insert({
            ...payload,
            resume_path: resumePath
        });
        if (error) {
            const cleanup = await supabaseClient.storage.from("application-resumes").remove([resumePath]);
            if (cleanup.error) {
                throw new Error(`${error.message} The uploaded résumé could not be cleaned up; contact support.`);
            }
            if (error.code === "23505") throw new Error("You have already applied for this job.");
            throw error;
        }
        jobApplicationDialog.close();
        setMessage(document.getElementById("job-board-message"), "Application submitted. You can follow its status in My applications.", "success");
        await Promise.all([loadSeekerApplications(), loadJobBoard()]);
    } catch (error) {
        setMessage(document.getElementById("job-application-message"), supabaseErrorMessage(error), "error");
    } finally {
        button.disabled = false;
    }
}

async function updateJobApplicationStatus(id, status, control) {
    control.disabled = true;
    try {
        await careerApi(`/api/provider/job-applications/${id}/status`, {
            method: "PATCH",
            body: JSON.stringify({ status })
        });
        const application = currentJobApplications.find((item) => item.id === id);
        if (application) application.status = status;
        renderProviderWorkspace();
        setMessage(document.getElementById("provider-applicants-message"), `Applicant moved to ${status}.`, "success");
        await loadNotifications();
    } catch (error) {
        setMessage(document.getElementById("provider-applicants-message"), supabaseErrorMessage(error), "error");
        const application = currentJobApplications.find((item) => item.id === id);
        if (application) control.value = application.status;
    } finally {
        control.disabled = false;
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
                <div class="empty-icon"><svg class="icon" aria-hidden="true"><use href="#icon-clock"></use></svg></div>
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
            link.append(document.createTextNode("Job posting "), createIcon("arrow-up-right"));
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
        edit.append(createIcon("edit"), document.createTextNode("Edit"));
        edit.setAttribute("aria-label", `Edit ${application.title} at ${application.company}`);
        edit.addEventListener("click", () => openApplicationDialog(application));
        const remove = document.createElement("button");
        remove.className = "delete-application";
        remove.type = "button";
        remove.append(createIcon("trash"), document.createTextNode("Remove"));
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
        .select("current_position,headline,about,target_role,skills,location,phone,education")
        .maybeSingle();
    if (currentUser?.id !== userId) return;
    if (error) {
        dashboardSources.profile = false;
        setMessage(document.getElementById("app-message"), supabaseErrorMessage(error), "error");
        renderDashboard();
        return;
    }
    currentCareerProfile = data || {};
    dashboardSources.profile = true;
    document.getElementById("my-profile-current-role").value = currentCareerProfile.current_position || "";
    document.getElementById("my-profile-target-role").value = currentCareerProfile.target_role || "";
    document.getElementById("my-profile-headline").value = currentCareerProfile.headline || "";
    document.getElementById("my-profile-about").value = currentCareerProfile.about || "";
    document.getElementById("my-profile-skills").value = (currentCareerProfile.skills || []).join(", ");
    document.getElementById("my-profile-location").value = currentCareerProfile.location || "";
    document.getElementById("my-profile-phone").value = currentCareerProfile.phone || "";
    document.getElementById("my-profile-education").value = currentCareerProfile.education || "";
    document.getElementById("skill-target-role").value = currentCareerProfile.target_role || "";
    document.getElementById("current-skills").value = (currentCareerProfile.skills || []).join(", ");
    if (
        currentCareerProfile.headline
        || currentCareerProfile.about
        || currentCareerProfile.target_role
    ) {
        document.getElementById("profile-stat").textContent = "Ready";
    }
    renderDashboard();
}

async function loadEmployerProfile() {
    const userId = currentUser?.id;
    if (!userId) return;
    const { data, error } = await supabaseClient
        .from("user_accounts")
        .select("display_name,recruiter_title")
        .eq("user_id", userId)
        .maybeSingle();
    if (currentUser?.id !== userId) return;
    if (error) {
        setMessage(
            document.getElementById("employer-profile-message"),
            supabaseErrorMessage(error),
            "error"
        );
        return;
    }
    if (!data) {
        setMessage(
            document.getElementById("employer-profile-message"),
            "Could not find your employer account profile.",
            "error"
        );
        return;
    }
    document.getElementById("employer-profile-name").value =
        currentUser.user_metadata?.full_name || data.display_name || "";
    document.getElementById("employer-profile-title").value = data.recruiter_title || "";
    document.getElementById("employer-profile-email").value = currentUser.email || "";
    document.getElementById("employer-profile-phone").value =
        currentUser.user_metadata?.recruiter_phone || "";
}

async function saveEmployerProfile(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector("button[type='submit']");
    button.disabled = true;
    const fullName = document.getElementById("employer-profile-name").value.trim();
    const recruiterTitle = document.getElementById("employer-profile-title").value.trim();
    const phone = document.getElementById("employer-profile-phone").value.trim();
    const message = document.getElementById("employer-profile-message");
    if (!fullName || !recruiterTitle) {
        setMessage(message, "Enter your name and job title.", "error");
        button.disabled = false;
        return;
    }

    try {
        const { data, error } = await supabaseClient.auth.updateUser({
            data: {
                ...currentUser.user_metadata,
                full_name: fullName,
                recruiter_phone: phone
            }
        });
        if (error) throw error;
        if (!data.user) throw new Error("The updated account was not returned.");
        currentUser = data.user;
        updateProfileIdentity(currentUser);
    } catch (error) {
        setMessage(message, `Could not save your private contact details: ${error.message}`, "error");
        button.disabled = false;
        return;
    }

    const { error } = await supabaseClient
        .from("user_accounts")
        .update({ recruiter_title: recruiterTitle })
        .eq("user_id", currentUser.id);
    if (error) {
        setMessage(
            message,
            `Your name and private phone were saved, but your public job title could not be saved: ${supabaseErrorMessage(error)}`,
            "error"
        );
        button.disabled = false;
        return;
    }
    setMessage(message, "Your employer profile has been saved.", "success");
    button.disabled = false;
}

async function saveMyProfile(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector("button[type='submit']");
    button.disabled = true;
    const fullName = document.getElementById("my-profile-name").value.trim();
    if (!fullName) {
        setMessage(document.getElementById("my-profile-message"), "Enter your name.", "error");
        document.getElementById("my-profile-name").focus();
        button.disabled = false;
        return;
    }
    const payload = {
        user_id: currentUser.id,
        current_position: document.getElementById("my-profile-current-role").value.trim(),
        target_role: document.getElementById("my-profile-target-role").value.trim(),
        headline: document.getElementById("my-profile-headline").value.trim(),
        about: document.getElementById("my-profile-about").value.trim(),
        skills: document.getElementById("my-profile-skills").value
            .split(/[,;\n]/).map((skill) => skill.trim()).filter(Boolean),
        location: document.getElementById("my-profile-location").value.trim(),
        phone: document.getElementById("my-profile-phone").value.trim(),
        education: document.getElementById("my-profile-education").value.trim()
    };

    try {
        const { error } = await supabaseClient
            .from("career_profiles")
            .upsert(payload, { onConflict: "user_id" });
        if (error) throw error;
    } catch (error) {
        setMessage(
            document.getElementById("my-profile-message"),
            `Could not save your profile details: ${supabaseErrorMessage(error)}`,
            "error"
        );
        button.disabled = false;
        return;
    }

    currentCareerProfile = { ...currentCareerProfile, ...payload };
    document.getElementById("current-skills").value = payload.skills.join(", ");
    document.getElementById("skill-target-role").value = payload.target_role;

    let nameUpdateError = "";
    if (fullName !== (currentUser.user_metadata?.full_name || "")) {
        try {
            const { data, error } = await supabaseClient.auth.updateUser({
                data: { ...currentUser.user_metadata, full_name: fullName }
            });
            if (error) throw error;
            if (!data.user) throw new Error("The updated account was not returned.");
            currentUser = data.user;
            updateProfileIdentity(currentUser);
        } catch (error) {
            nameUpdateError = supabaseErrorMessage(error);
        }
    }

    document.getElementById("profile-stat").textContent = payload.headline ? "Ready" : "In progress";
    setMessage(
        document.getElementById("my-profile-message"),
        nameUpdateError
            ? `Career details were saved, but your name could not be updated: ${nameUpdateError}`
            : "Your profile has been saved.",
        nameUpdateError ? "error" : "success"
    );
    button.disabled = false;
    renderDashboard();
    await loadJobBoard();
}

function resetPortfolioEditor() {
    editingProjectId = null;
    document.getElementById("portfolio-form").reset();
    document.getElementById("project-submit").textContent = "Add project";
    document.getElementById("project-cancel-edit").hidden = true;
}

async function loadPortfolioProjects() {
    const userId = currentUser?.id;
    if (!userId) return;
    setMessage(document.getElementById("portfolio-message"), "Loading your private projects...");
    try {
        const projects = await careerApi("/api/portfolio/projects");
        if (currentUser?.id !== userId) return;
        if (!Array.isArray(projects)) {
            throw new Error("The portfolio service returned an unexpected response.");
        }
        careerProjects = projects;
        portfolioAvailable = true;
        dashboardSources.portfolio = true;
        renderPortfolioProjects();
        setMessage(document.getElementById("portfolio-message"), "");
        renderDashboard();
        return true;
    } catch (error) {
        if (currentUser?.id !== userId) return;
        careerProjects = [];
        portfolioAvailable = false;
        dashboardSources.portfolio = false;
        renderPortfolioProjects();
        setMessage(
            document.getElementById("portfolio-message"),
            error.message || "Could not load your private portfolio.",
            "error"
        );
        renderDashboard();
        return false;
    }
}

function renderPortfolioProjects() {
    const list = document.getElementById("portfolio-project-list");
    list.replaceChildren();
    careerProjects.forEach((project) => {
        const card = document.createElement("article");
        card.className = "portfolio-project-card";
        const title = document.createElement("h4");
        title.textContent = project.title;
        card.appendChild(title);

        const description = document.createElement("p");
        description.textContent = project.description;
        card.appendChild(description);
        if (project.contribution) {
            const contribution = document.createElement("p");
            contribution.textContent = `Your contribution: ${project.contribution}`;
            card.appendChild(contribution);
        }

        if (Array.isArray(project.skills) && project.skills.length) {
            const skills = document.createElement("p");
            skills.className = "learning-resource-meta";
            skills.textContent = `Self-reported skills: ${project.skills.join(", ")}`;
            card.appendChild(skills);
        }

        const dates = [project.started_on, project.completed_on].filter(Boolean);
        if (dates.length) {
            const dateLine = document.createElement("p");
            dateLine.className = "learning-resource-meta";
            dateLine.textContent = dates.join(" – ");
            card.appendChild(dateLine);
        }
        if (project.project_url) {
            const link = document.createElement("a");
            link.href = project.project_url;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            link.textContent = "View project";
            card.appendChild(link);
        }

        const controls = document.createElement("div");
        controls.className = "portfolio-project-controls";
        const editButton = document.createElement("button");
        editButton.type = "button";
        editButton.className = "secondary-button";
        editButton.textContent = "Edit";
        editButton.addEventListener("click", () => editPortfolioProject(project));
        const deleteButton = document.createElement("button");
        deleteButton.type = "button";
        deleteButton.className = "secondary-button";
        deleteButton.textContent = "Delete";
        deleteButton.addEventListener("click", () =>
            deletePortfolioProject(project, deleteButton)
        );
        controls.append(editButton, deleteButton);
        card.appendChild(controls);
        list.appendChild(card);
    });
    document.getElementById("portfolio-empty").hidden =
        careerProjects.length > 0 || !portfolioAvailable;
}

function editPortfolioProject(project) {
    editingProjectId = project.id;
    document.getElementById("project-title").value = project.title || "";
    document.getElementById("project-description").value = project.description || "";
    document.getElementById("project-contribution").value = project.contribution || "";
    document.getElementById("project-skills").value =
        Array.isArray(project.skills) ? project.skills.join(", ") : "";
    document.getElementById("project-url").value = project.project_url || "";
    document.getElementById("project-started-on").value = project.started_on || "";
    document.getElementById("project-completed-on").value = project.completed_on || "";
    document.getElementById("project-submit").textContent = "Save changes";
    document.getElementById("project-cancel-edit").hidden = false;
    document.getElementById("project-title").focus();
}

async function savePortfolioProject(event) {
    event.preventDefault();
    const button = document.getElementById("project-submit");
    button.disabled = true;
    const payload = {
        title: document.getElementById("project-title").value.trim(),
        description: document.getElementById("project-description").value.trim(),
        contribution: document.getElementById("project-contribution").value.trim(),
        skills: document.getElementById("project-skills").value
            .split(/[,;\n]/).map((skill) => skill.trim()).filter(Boolean),
        project_url: document.getElementById("project-url").value.trim(),
        started_on: document.getElementById("project-started-on").value || null,
        completed_on: document.getElementById("project-completed-on").value || null
    };
    const wasEditing = Boolean(editingProjectId);
    try {
        const path = editingProjectId
            ? `/api/portfolio/projects/${encodeURIComponent(editingProjectId)}`
            : "/api/portfolio/projects";
        await careerApi(path, {
            method: editingProjectId ? "PATCH" : "POST",
            body: JSON.stringify(payload)
        });
        resetPortfolioEditor();
        const projectsLoaded = await loadPortfolioProjects();
        await loadJobBoard();
        if (projectsLoaded) {
            setMessage(
                document.getElementById("portfolio-message"),
                wasEditing ? "Your project has been updated." : "Your project has been added.",
                "success"
            );
        }
    } catch (error) {
        setMessage(
            document.getElementById("portfolio-message"),
            error.message || "Could not save this project.",
            "error"
        );
    } finally {
        button.disabled = false;
    }
}

async function deletePortfolioProject(project, button) {
    if (!window.confirm(`Delete "${project.title}" from your private portfolio?`)) return;
    button.disabled = true;
    try {
        await careerApi(
            `/api/portfolio/projects/${encodeURIComponent(project.id)}`,
            { method: "DELETE" }
        );
        const projectsLoaded = await loadPortfolioProjects();
        await loadJobBoard();
        if (projectsLoaded) {
            setMessage(document.getElementById("portfolio-message"), "Project deleted.", "success");
        }
    } catch (error) {
        setMessage(
            document.getElementById("portfolio-message"),
            error.message || "Could not delete this project.",
            "error"
        );
    } finally {
        button.disabled = false;
    }
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

function renderDashboard() {
    const message = document.getElementById("dashboard-message");
    const profileLoaded = dashboardSources.profile === true;
    if (!profileLoaded) {
        document.getElementById("dashboard-profile-completion").textContent =
            dashboardSources.profile === false ? "Unavailable" : "Loading";
        document.getElementById("dashboard-profile-detail").textContent =
            dashboardSources.profile === false
                ? "Profile data could not be loaded"
                : "Loading your profile...";
    }

    const summary = CareerLensDashboardUi.summarizeCareerDashboard({
        profile: currentCareerProfile,
        projects: careerProjects,
        learningPlan,
        manualApplications: currentApplications,
        careerApplications: seekerApplications,
        recommendations: currentJobListings,
        learningAvailable: dashboardSources.learning === true,
        portfolioAvailable: portfolioAvailable && dashboardSources.portfolio === true
    });

    if (profileLoaded) {
        document.getElementById("dashboard-profile-completion").textContent =
            `${summary.profile.completeness}%`;
        document.getElementById("dashboard-profile-detail").textContent =
            `${summary.profile.completeFields} of ${summary.profile.totalFields} fields complete`;
    }
    document.getElementById("dashboard-project-count").textContent =
        dashboardSources.portfolio === null
            ? "Loading"
            : portfolioAvailable ? String(summary.projects.count) : "Unavailable";
    document.getElementById("dashboard-project-skills").textContent =
        dashboardSources.portfolio === null
            ? "Loading your private projects..."
            : portfolioAvailable
            ? `${summary.profile.projectSkillsCount} distinct user-listed skills`
            : "Portfolio setup required";
    document.getElementById("dashboard-learning-count").textContent =
        dashboardSources.learning === null
            ? "Loading"
            : dashboardSources.learning === false
                ? "Unavailable"
                : String(summary.learning.total);
    document.getElementById("dashboard-learning-detail").textContent =
        dashboardSources.learning === null
            ? "Loading your learning plan..."
            : dashboardSources.learning === false
                ? "Learning data could not be loaded"
                : `${summary.learning.inProgress} in progress · ${summary.learning.completed} self-reported completed`;

    const applicationsLoaded = dashboardSources.manualApplications === true
        && dashboardSources.careerApplications === true;
    const applicationsLoading = dashboardSources.manualApplications === null
        || dashboardSources.careerApplications === null;
    document.getElementById("dashboard-application-count").textContent =
        applicationsLoaded
            ? String(summary.applications.manual.total + summary.applications.careerLens.total)
            : applicationsLoading ? "Loading" : "Unavailable";
    document.getElementById("dashboard-application-detail").textContent =
        applicationsLoaded
            ? `Manual: ${summary.applications.manual.total} total, ${summary.applications.manual.inProgress} active, ${summary.applications.manual.interviews} interviews, ${summary.applications.manual.offers} offers · CareerLens: ${summary.applications.careerLens.total} total, ${summary.applications.careerLens.inProgress} active, ${summary.applications.careerLens.interviews} interviews, ${summary.applications.careerLens.offers} offers · ${summary.profile.linkedResumeCount} linked private résumés`
            : applicationsLoading
                ? "Loading application data..."
                : "One or more application sources could not be loaded";

    const actionsList = document.getElementById("dashboard-actions");
    actionsList.replaceChildren();
    const actions = profileLoaded
        ? CareerLensDashboardUi.getCareerNextActions(summary)
        : [];
    actions.forEach((action) => {
        const item = document.createElement("li");
        const link = document.createElement("a");
        link.href = action.href;
        link.textContent = action.label;
        const detail = document.createElement("p");
        detail.textContent = action.detail;
        item.append(link, detail);
        actionsList.appendChild(item);
    });
    document.getElementById("dashboard-actions-empty").hidden =
        actions.length > 0 || dashboardSources.profile !== true;

    const recommendations = document.getElementById("dashboard-recommendations");
    recommendations.replaceChildren();
    summary.recommendations.forEach((job) => {
        const card = document.createElement("article");
        card.className = "dashboard-recommendation-card";
        const title = document.createElement("h4");
        title.textContent = job.title || "Published role";
        const company = document.createElement("p");
        company.textContent = [job.company, job.location].filter(Boolean).join(" · ");
        const explanation = document.createElement("p");
        explanation.textContent = job.match.score === null
            ? "Add profile or project evidence to see an alignment indicator."
            : `${job.match.score}% evidence alignment · Not a measure of competence or hiring probability`;
        const link = document.createElement("a");
        link.href = "#browse-jobs";
        link.textContent = "Review opportunity";
        card.append(title, company, explanation, link);
        recommendations.appendChild(card);
    });
    const recommendationEmpty = document.getElementById("dashboard-recommendations-empty");
    recommendationEmpty.hidden = summary.recommendations.length > 0;
    recommendationEmpty.textContent =
        dashboardSources.recommendations === null
            ? "Loading recommendations..."
            : dashboardSources.recommendations === false
                ? "Recommendations could not be loaded. Open the job board to see the service error."
                : "No published opportunities are available to recommend yet.";

    const projectList = document.getElementById("dashboard-projects");
    projectList.replaceChildren();
    summary.projects.recent.forEach((project) => {
        const card = document.createElement("article");
        card.className = "dashboard-project-card";
        const title = document.createElement("h4");
        title.textContent = project.title || "Portfolio project";
        const skills = document.createElement("p");
        const projectSkills = Array.isArray(project.skills) ? project.skills : [];
        skills.textContent = projectSkills.length
            ? `User-listed skills: ${projectSkills.join(", ")}`
            : "No skills listed";
        const link = document.createElement("a");
        link.href = "#my-profile";
        link.textContent = "Edit portfolio";
        card.append(title, skills, link);
        projectList.appendChild(card);
    });
    const projectEmpty = document.getElementById("dashboard-projects-empty");
    projectEmpty.hidden = summary.projects.recent.length > 0;
    projectEmpty.textContent = dashboardSources.portfolio === null
        ? "Loading your projects..."
        : dashboardSources.portfolio === false
            ? "Portfolio projects could not be loaded. Check the portfolio setup message in My Profile."
            : "Add a project to see recent contributions and user-listed skills here.";

    const sourceErrors = [];
    if (dashboardSources.portfolio === false) {
        sourceErrors.push("portfolio setup or data unavailable");
    }
    if (dashboardSources.learning === false) sourceErrors.push("learning data unavailable");
    if (dashboardSources.profile === false) sourceErrors.push("profile data unavailable");
    if (
        dashboardSources.manualApplications === false
        || dashboardSources.careerApplications === false
    ) sourceErrors.push("application data unavailable");
    if (dashboardSources.recommendations === false) {
        sourceErrors.push("recommendations unavailable");
    }
    setMessage(
        message,
        sourceErrors.length ? `Dashboard data: ${sourceErrors.join("; ")}.` : ""
    );
}

async function careerApi(path, options = {}) {
    const { data: { session }, error } = await supabaseClient.auth.getSession();
    if (error) throw error;
    if (!session) throw new Error("Your session has expired. Please sign in again.");

    const headers = { Authorization: `Bearer ${session.access_token}` };
    if (options.body) headers["Content-Type"] = "application/json";
    const response = await fetch(path, {
        ...options,
        headers: { ...headers, ...(options.headers || {}) }
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "The request could not be completed.");
    return payload;
}

async function loadNotifications() {
    try {
        const result = await careerApi("/api/notifications");
        currentNotifications = Array.isArray(result.notifications) ? result.notifications : [];
        renderNotifications();
    } catch (error) {
        setMessage(document.getElementById("notifications-message"), error.message || "Could not load notifications.", "error");
    }
}

function renderNotifications() {
    const list = document.getElementById("notification-list");
    if (!list) return;
    const unread = currentNotifications.filter((item) => !item.read_at).length;
    const count = document.getElementById("notification-count");
    if (count) {
        count.textContent = String(unread);
        count.hidden = unread === 0;
    }
    list.replaceChildren();
    if (!currentNotifications.length) {
        list.appendChild(createEmptyState("You’re all caught up", "New application updates and reminders will appear here."));
        return;
    }
    currentNotifications.forEach((notification) => {
        const card = document.createElement("article");
        card.className = `notification-card${notification.read_at ? " is-read" : ""}`;
        const heading = document.createElement("strong");
        heading.textContent = notification.title;
        const body = document.createElement("p");
        body.textContent = notification.body;
        const actions = document.createElement("div");
        actions.className = "notification-actions";
        if (notification.data?.application_id && notification.notification_type === "interview_scheduled") {
            const calendar = document.createElement("button");
            calendar.type = "button";
            calendar.className = "secondary-button";
            calendar.textContent = "Add to calendar (.ics)";
            calendar.addEventListener("click", () => downloadInterviewCalendar(notification.data.application_id, calendar));
            actions.appendChild(calendar);
        }
        if (!notification.read_at && !String(notification.id).startsWith("follow-up:")) {
            const read = document.createElement("button");
            read.type = "button";
            read.className = "text-button";
            read.textContent = "Mark read";
            read.addEventListener("click", () => markNotificationRead(notification.id));
            actions.appendChild(read);
        }
        card.append(heading, body, actions);
        list.appendChild(card);
    });
}

async function markNotificationRead(id) {
    try {
        await careerApi(`/api/notifications/${id}/read`, { method: "PATCH" });
        currentNotifications = currentNotifications.map((item) => item.id === id ? { ...item, read_at: new Date().toISOString() } : item);
        renderNotifications();
    } catch (error) {
        setMessage(document.getElementById("notifications-message"), error.message, "error");
    }
}

async function downloadInterviewCalendar(applicationId, button) {
    const previous = button.textContent;
    button.disabled = true;
    button.textContent = "Preparing...";
    try {
        const { data: { session }, error } = await supabaseClient.auth.getSession();
        if (error || !session) throw error || new Error("Your session has expired. Please sign in again.");
        const response = await fetch(`/api/job-applications/${applicationId}/interview.ics`, { headers: { Authorization: `Bearer ${session.access_token}` } });
        if (!response.ok) {
            const payload = await response.json();
            throw new Error(payload.error || "Could not create the calendar file.");
        }
        const blob = await response.blob();
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = "careerlens-interview.ics";
        link.click();
        URL.revokeObjectURL(link.href);
    } catch (error) {
        setMessage(document.getElementById("notifications-message"), error.message, "error");
    } finally {
        button.disabled = false;
        button.textContent = previous;
    }
}

async function loadLearningWorkspace() {
    const message = document.getElementById("learning-message");
    const userId = currentUser?.id;
    document.getElementById("learning-catalogue-empty").hidden = true;
    document.getElementById("learning-plan-empty").hidden = true;
    setMessage(message, "Loading the resource catalogue and your learning plan...");
    try {
        const [resources, plan] = await Promise.all([
            careerApi("/api/learning/resources"),
            careerApi("/api/learning/plan")
        ]);
        if (currentUser?.id !== userId) return;
        if (!Array.isArray(resources) || !Array.isArray(plan)) {
            throw new Error("The learning service returned an unexpected response.");
        }
        learningResources = resources;
        learningPlan = plan;
        dashboardSources.learning = true;
        renderLearningWorkspace();
        setMessage(message, "");
    } catch (error) {
        learningResources = [];
        learningPlan = [];
        dashboardSources.learning = false;
        renderLearningWorkspace();
        renderDashboard();
        setMessage(message, error.message || "Could not load the learning workspace.", "error");
    }
}

function createLearningResourceCard(
    resource,
    { matchedSkills = [], showAdd = true, feedbackMessageId = "learning-message" } = {}
) {
    const card = document.createElement("article");
    card.className = "learning-resource-card";

    const heading = document.createElement("div");
    heading.className = "learning-resource-heading";
    const title = document.createElement("h4");
    title.textContent = resource.title || "Learning resource";
    const difficulty = document.createElement("span");
    difficulty.className = "learning-resource-difficulty";
    difficulty.textContent = resource.difficulty || "Level not listed";
    heading.append(title, difficulty);
    card.appendChild(heading);

    const categoryName = resource.category?.name || "Uncategorized";
    const meta = document.createElement("p");
    meta.className = "learning-resource-meta";
    meta.textContent = [resource.provider, categoryName, resource.resource_type]
        .filter(Boolean).join(" · ");
    card.appendChild(meta);

    const description = document.createElement("p");
    description.className = "learning-resource-description";
    description.textContent = resource.description || "";
    card.appendChild(description);

    if (Array.isArray(resource.objectives) && resource.objectives.length) {
        const objectives = document.createElement("p");
        objectives.className = "learning-resource-objectives";
        objectives.textContent = `Learning objectives: ${resource.objectives.join("; ")}`;
        card.appendChild(objectives);
    }

    const tags = document.createElement("ul");
    tags.className = "learning-resource-tags";
    (resource.skill_tags || []).forEach((tag) => {
        const item = document.createElement("li");
        item.textContent = tag;
        tags.appendChild(item);
    });
    if (tags.childElementCount) card.appendChild(tags);

    if (matchedSkills.length) {
        const matchNote = document.createElement("p");
        matchNote.className = "learning-resource-meta";
        matchNote.textContent = `Matches skills to investigate: ${matchedSkills.join(", ")}`;
        card.appendChild(matchNote);
    }

    const actions = document.createElement("div");
    actions.className = "learning-resource-actions";
    let resourceUrl;
    try {
        resourceUrl = new URL(resource.resource_url);
    } catch {
        resourceUrl = null;
    }
    if (resourceUrl && ["http:", "https:"].includes(resourceUrl.protocol)) {
        const link = document.createElement("a");
        link.className = "learning-resource-link";
        link.href = resourceUrl.href;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = "Open original resource";
        actions.appendChild(link);
    } else {
        const unavailable = document.createElement("span");
        unavailable.className = "learning-resource-meta";
        unavailable.textContent = "Resource link unavailable.";
        actions.appendChild(unavailable);
    }

    if (showAdd) {
        const inPlan = learningPlan.some((item) => item.resource_id === resource.id);
        const addButton = document.createElement("button");
        addButton.className = "primary-button";
        addButton.type = "button";
        addButton.disabled = inPlan;
        addButton.textContent = inPlan ? "In your plan" : "Add to learning plan";
        addButton.addEventListener("click", () =>
            addLearningResource(resource.id, addButton, feedbackMessageId, resource)
        );
        actions.appendChild(addButton);
    }
    card.appendChild(actions);
    return card;
}

function renderLearningRecommendations(result) {
    const matches = latestLearningRecommendations || [];
    const dashboardList = document.getElementById("learning-recommendations-list");
    const analysisList = document.getElementById("skill-learning-list");
    const dashboardEmpty = document.getElementById("learning-recommendations-empty");
    const analysisEmpty = document.getElementById("skill-learning-empty");
    dashboardEmpty.classList.remove("error", "success");
    analysisEmpty.classList.remove("error", "success");
    dashboardList.replaceChildren();
    analysisList.replaceChildren();
    matches.forEach((resource) => {
        const matchedSkills = resource.matched_skills || [];
        dashboardList.appendChild(createLearningResourceCard(resource, { matchedSkills }));
        analysisList.appendChild(createLearningResourceCard(resource, {
            matchedSkills,
            feedbackMessageId: "skill-learning-message"
        }));
    });
    if (!result) {
        dashboardEmpty.hidden = false;
        dashboardEmpty.textContent =
            "Run Skill Gap Analysis to see resource recommendations connected to that analysis. The result is kept for this browser session only.";
        analysisEmpty.hidden = false;
        analysisEmpty.textContent = "Run Skill Gap Analysis to connect requirements with learning resources.";
    } else if (learningRecommendationError) {
        dashboardEmpty.hidden = false;
        dashboardEmpty.textContent = learningRecommendationError;
        dashboardEmpty.classList.add("error");
        analysisEmpty.hidden = false;
        analysisEmpty.textContent = learningRecommendationError;
        analysisEmpty.classList.add("error");
    } else if (latestLearningRecommendations === null) {
        dashboardEmpty.hidden = false;
        dashboardEmpty.textContent = "Finding resources that match the skills from your analysis...";
        analysisEmpty.hidden = false;
        analysisEmpty.textContent = "Finding matching learning resources...";
    } else {
        dashboardEmpty.hidden = matches.length > 0;
        dashboardEmpty.textContent = "No matching catalogue resources are available for this analysis yet.";
        analysisEmpty.hidden = matches.length > 0;
        analysisEmpty.textContent = "No matching catalogue resources are available for this analysis yet.";
    }
}

async function loadLearningRecommendations(result) {
    latestLearningRecommendations = null;
    learningRecommendationError = "";
    renderLearningRecommendations(result);
    try {
        const recommendations = await careerApi("/api/learning/recommendations", {
            method: "POST",
            body: JSON.stringify({
                skills: result.skills.map(({ name, status }) => ({ name, status }))
            })
        });
        if (latestSkillGapResult !== result) return;
        if (!Array.isArray(recommendations)) {
            throw new Error("The recommendation service returned an unexpected response.");
        }
        latestLearningRecommendations = recommendations;
        renderLearningRecommendations(result);
    } catch (error) {
        if (latestSkillGapResult !== result) return;
        learningRecommendationError = error.message || "Could not load learning recommendations.";
        renderLearningRecommendations(result);
    }
}

function renderLearningWorkspace() {
    const total = learningPlan.length;
    const inProgress = learningPlan.filter((item) => item.status === "in_progress").length;
    const completed = learningPlan.filter((item) => item.status === "completed").length;
    document.getElementById("learning-total-count").textContent = String(total);
    document.getElementById("learning-in-progress-count").textContent = String(inProgress);
    document.getElementById("learning-completed-count").textContent = String(completed);
    document.getElementById("learning-completion-rate").textContent =
        total ? `${Math.round(completed / total * 100)}%` : "--";

    const groups = CareerLensLearningUi.groupLearningPlan(learningPlan);
    [
        ["in_progress", "learning-in-progress-list", "learning-in-progress-empty", "learning-in-progress-section"],
        ["completed", "learning-completed-list", "learning-completed-empty", "learning-completed-section"],
        ["not_started", "learning-not-started-list", "learning-not-started-empty", "learning-not-started-section"]
    ].forEach(([status, listId, emptyId, sectionId]) => {
        const list = document.getElementById(listId);
        list.replaceChildren();
        groups[status].forEach((item) => list.appendChild(createLearningPlanCard(item)));
        document.getElementById(emptyId).hidden = groups[status].length > 0;
        document.getElementById(sectionId).hidden = groups[status].length === 0;
    });
    document.getElementById("learning-plan-empty").hidden = total > 0;

    const targetedSkills = CareerLensLearningUi.getLearningPlanSkills(learningPlan);
    const skillsList = document.getElementById("learning-targeted-skills");
    skillsList.replaceChildren();
    targetedSkills.forEach((skill) => {
        const tag = document.createElement("li");
        tag.textContent = skill;
        skillsList.appendChild(tag);
    });
    document.getElementById("learning-targeted-skills-empty").hidden =
        targetedSkills.length > 0;

    const categoryFilter = document.getElementById("learning-category-filter");
    const selectedCategory = categoryFilter.value || "all";
    const categories = new Map();
    learningResources.forEach((resource) => {
        if (resource.category?.slug && resource.category?.name) {
            categories.set(resource.category.slug, resource.category.name);
        }
    });
    categoryFilter.replaceChildren(new Option("All categories", "all"));
    [...categories.entries()].sort((first, second) =>
        first[1].localeCompare(second[1])
    ).forEach(([slug, name]) => categoryFilter.add(new Option(name, slug)));
    categoryFilter.value = categories.has(selectedCategory) ? selectedCategory : "all";

    const filteredResources = CareerLensLearningUi.filterLearningResources(
        learningResources,
        {
            query: document.getElementById("learning-search").value,
            category: categoryFilter.value,
            difficulty: document.getElementById("learning-difficulty-filter").value
        }
    );

    const resourceList = document.getElementById("learning-resource-list");
    resourceList.replaceChildren();
    filteredResources.forEach((resource) =>
        resourceList.appendChild(createLearningResourceCard(resource))
    );
    document.getElementById("learning-resource-count").textContent =
        learningResources.length
            ? `Showing ${filteredResources.length} of ${learningResources.length} resources`
            : "";
    const catalogueEmpty = document.getElementById("learning-catalogue-empty");
    catalogueEmpty.hidden = filteredResources.length > 0;
    if (learningResources.length && !filteredResources.length) {
        catalogueEmpty.textContent = "No resources match these filters. Try another search or category.";
    } else {
        catalogueEmpty.textContent =
            "No learning resources are available yet. Ask the project administrator to add verified resources to the catalogue.";
    }

    renderLearningRecommendations(latestSkillGapResult);
    renderDashboard();
}

function createLearningPlanCard(item) {
    const resource = item.resource || {
        title: "Resource no longer available",
        description: "This catalogue item is unavailable. You can remove it from your plan.",
        skill_tags: []
    };
    const card = createLearningResourceCard(resource, { showAdd: false });
    const status = document.createElement("span");
    status.className = "learning-resource-meta";
    status.textContent = item.status === "completed"
        ? "Self-reported as completed"
        : item.status === "in_progress" ? "In progress" : "Not started";
    card.insertBefore(status, card.lastElementChild);
    const updated = document.createElement("p");
    updated.className = "learning-resource-meta";
    const updatedAt = item.updated_at || item.created_at;
    updated.textContent = `Last updated: ${CareerLensLearningUi.formatLearningDate(updatedAt)}`;
    card.insertBefore(updated, card.lastElementChild);

    const controls = document.createElement("div");
    controls.className = "learning-plan-controls";
    const statusLabel = document.createElement("label");
    statusLabel.textContent = "Progress";
    const statusSelect = document.createElement("select");
    statusSelect.setAttribute("aria-label", `Progress for ${resource.title || "learning resource"}`);
    [
        ["not_started", "Not started"],
        ["in_progress", "In progress"],
        ["completed", "Completed (self-reported)"]
    ].forEach(([value, label]) => {
        const option = new Option(label, value);
        option.selected = item.status === value;
        statusSelect.add(option);
    });
    statusLabel.appendChild(statusSelect);

    const dateLabel = document.createElement("label");
    dateLabel.textContent = "Target date";
    const dateInput = document.createElement("input");
    dateInput.type = "date";
    dateInput.value = item.target_completion_date || "";
    dateInput.setAttribute("aria-label", `Target completion date for ${resource.title || "learning resource"}`);
    dateLabel.appendChild(dateInput);

    const saveButton = document.createElement("button");
    saveButton.className = "secondary-button";
    saveButton.type = "button";
    saveButton.textContent = "Save progress";
    saveButton.addEventListener("click", () =>
        updateLearningPlanItem(item.id, statusSelect.value, dateInput.value, saveButton)
    );

    const removeButton = document.createElement("button");
    removeButton.className = "secondary-button";
    removeButton.type = "button";
    removeButton.textContent = "Remove";
    removeButton.addEventListener("click", () => removeLearningPlanItem(item.id, removeButton));
    controls.append(statusLabel, dateLabel, saveButton, removeButton);
    card.appendChild(controls);
    return card;
}

async function addLearningResource(
    resourceId, button, feedbackMessageId, resourceDetails = null
) {
    const message = document.getElementById(feedbackMessageId);
    button.disabled = true;
    setMessage(message, "Adding resource to your plan...");
    try {
        const result = await careerApi("/api/learning/plan", {
            method: "POST",
            body: JSON.stringify({ resource_id: resourceId })
        });
        if (!Array.isArray(result) || !result[0]) {
            throw new Error("The resource could not be added to your learning plan.");
        }
        const resource = learningResources.find((item) => item.id === resourceId)
            || resourceDetails;
        learningPlan = [{ ...result[0], resource }, ...learningPlan];
        renderLearningWorkspace();
        button.textContent = "In your plan";
        setMessage(message, "Resource added to your learning plan.", "success");
    } catch (error) {
        setMessage(message, error.message || "Could not add this resource.", "error");
        button.disabled = false;
    }
}

async function updateLearningPlanItem(itemId, status, targetDate, button) {
    button.disabled = true;
    try {
        const result = await careerApi(`/api/learning/plan/${encodeURIComponent(itemId)}`, {
            method: "PATCH",
            body: JSON.stringify({ status, target_completion_date: targetDate || null })
        });
        if (!Array.isArray(result) || !result[0]) {
            throw new Error("The learning-plan item could not be updated.");
        }
        learningPlan = learningPlan.map((item) => item.id === itemId
            ? { ...result[0], resource: item.resource }
            : item);
        renderLearningWorkspace();
        setMessage(document.getElementById("learning-message"), "Learning progress saved.", "success");
    } catch (error) {
        setMessage(document.getElementById("learning-message"), error.message || "Could not save your learning progress.", "error");
        button.disabled = false;
    }
}

async function removeLearningPlanItem(itemId, button) {
    button.disabled = true;
    try {
        await careerApi(`/api/learning/plan/${encodeURIComponent(itemId)}`, {
            method: "DELETE"
        });
        learningPlan = learningPlan.filter((item) => item.id !== itemId);
        renderLearningWorkspace();
        setMessage(document.getElementById("learning-message"), "Resource removed from your learning plan.", "success");
    } catch (error) {
        setMessage(document.getElementById("learning-message"), error.message || "Could not remove this resource.", "error");
        button.disabled = false;
    }
}

function renderSkillGapResults(result) {
    latestSkillGapResult = result;
    latestLearningRecommendations = null;
    learningRecommendationError = "";
    const summary = result.summary;
    document.getElementById("skill-result-title").textContent =
        `Recognized requirements for ${result.target_role}`;
    document.getElementById("skill-total-count").textContent = String(summary.total_required_skills);
    document.getElementById("skill-evidence-count").textContent =
        String(summary.skills_with_supporting_evidence);
    document.getElementById("skill-assessment-count").textContent = String(summary.needs_assessment);
    document.getElementById("skill-no-evidence-count").textContent = String(summary.no_evidence_found);
    document.getElementById("skill-gap-note").textContent = result.note;
    const priorityPanel = document.getElementById("skill-priority-panel");
    priorityPanel.hidden = !summary.priority_skills.length;
    document.getElementById("skill-priority-list").textContent =
        summary.priority_skills.join(", ");

    const gapList = document.getElementById("skill-gap-list");
    gapList.replaceChildren();
    if (!result.skills.length) {
        gapList.appendChild(createEmptyState(
            "No supported skills recognized",
            "The job description did not match a skill in CareerLens’ current vocabulary. Add clear skills or requirements to the description and try again."
        ));
    }
    result.skills.forEach((skill) => {
        const card = document.createElement("article");
        card.className = "skill-gap-card";
        const heading = document.createElement("div");
        heading.className = "skill-gap-card-heading";
        const name = document.createElement("h4");
        name.textContent = skill.name;
        const status = document.createElement("span");
        status.className = `skill-evidence-status status-${skill.status.toLowerCase().replaceAll(" ", "-")}`;
        status.textContent = skill.status;
        heading.append(name, status);
        card.appendChild(heading);

        const required = document.createElement("p");
        required.className = "skill-requirement";
        required.textContent = `Job requirement: ${skill.requirement_excerpt}`;
        card.appendChild(required);

        const explanation = document.createElement("p");
        explanation.textContent = skill.explanation;
        card.appendChild(explanation);

        if (skill.evidence.length) {
            const evidenceTitle = document.createElement("strong");
            evidenceTitle.className = "skill-evidence-title";
            evidenceTitle.textContent = "Your supplied evidence";
            const evidenceList = document.createElement("ul");
            skill.evidence.forEach((evidence) => {
                const item = document.createElement("li");
                const source = document.createElement("strong");
                source.textContent = `${evidence.source}: `;
                item.append(source, document.createTextNode(evidence.excerpt));
                evidenceList.appendChild(item);
            });
            card.append(evidenceTitle, evidenceList);
        } else {
            const noEvidence = document.createElement("p");
            noEvidence.className = "muted-text";
            noEvidence.textContent = "No supporting mention was found in the text supplied for this analysis.";
            card.appendChild(noEvidence);
        }

        const gap = document.createElement("p");
        gap.className = "skill-gap-explanation";
        gap.textContent = skill.gap_explanation;
        card.appendChild(gap);

        const action = document.createElement("p");
        action.className = "skill-next-action";
        const actionLabel = document.createElement("strong");
        actionLabel.textContent = "Recommended next step: ";
        action.append(actionLabel, document.createTextNode(skill.next_action));
        card.appendChild(action);

        if (skill.learning_sequence.length) {
            const sequence = document.createElement("p");
            sequence.className = "skill-learning-sequence";
            sequence.textContent = `Possible learning sequence: ${skill.learning_sequence.join(" → ")}`;
            card.appendChild(sequence);
        }
        gapList.appendChild(card);
    });

    document.getElementById("skill-count").textContent = String(
        summary.needs_assessment + summary.no_evidence_found
    );
    document.getElementById("skill-results").hidden = false;
    renderLearningRecommendations(result);
}

async function renderSkillAnalysis(event) {
    event.preventDefault();
    const button = document.getElementById("skill-analyze-button");
    const message = document.getElementById("skill-message");
    button.disabled = true;
    document.getElementById("skill-results").hidden = true;
    setMessage(message, "Analyzing the job requirements and supplied evidence...");
    try {
        const { data: { session }, error: sessionError } = await supabaseClient.auth.getSession();
        if (sessionError) throw sessionError;
        if (!session) throw new Error("Your session has expired. Please sign in again.");

        const formData = new FormData(document.getElementById("skill-form"));
        formData.set("skills", document.getElementById("current-skills").value);
        const response = await fetch("/api/skill-gap", {
            method: "POST",
            headers: { Authorization: ["Bearer", session.access_token].join(" ") },
            body: formData
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "Could not analyze these skills.");
        renderSkillGapResults(result);
        setMessage(message, "Skill analysis complete. Review the evidence and correct anything that needs updating.", "success");
        await loadLearningRecommendations(result);
    } catch (error) {
        setMessage(message, error.message || "Could not analyze these skills.", "error");
    } finally {
        button.disabled = false;
    }
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

document.querySelectorAll("[data-auth-mode]").forEach((tab) => {
    tab.addEventListener("click", () => setAuthMode(tab.dataset.authMode));
});
authForm.addEventListener("submit", handleAuthSubmit);
document.getElementById("password-update-form").addEventListener("submit", updatePassword);
document.getElementById("forgot-password").addEventListener("click", sendPasswordReset);
document.getElementById("resend-confirmation").addEventListener("click", resendSignupConfirmation);
document.getElementById("sign-out").addEventListener("click", signOut);
document.getElementById("learning-search").addEventListener("input", renderLearningWorkspace);
document.getElementById("learning-category-filter").addEventListener("change", renderLearningWorkspace);
document.getElementById("learning-difficulty-filter").addEventListener("change", renderLearningWorkspace);
document.getElementById("learning-filter-form").addEventListener("submit", (event) => event.preventDefault());
document.querySelectorAll("[data-open-job-form]").forEach((button) => {
    button.addEventListener("click", () => openJobDialog());
});
document.getElementById("close-job-dialog").addEventListener("click", () => jobDialog.close());
jobDialog.addEventListener("close", () => {
    editingJobId = null;
    jobForm.reset();
});
jobForm.addEventListener("submit", saveJobListing);
document.getElementById("close-job-application").addEventListener("click", () => jobApplicationDialog.close());
jobApplicationDialog.addEventListener("close", () => {
    applyingToJobId = null;
    jobApplicationForm.reset();
});
jobApplicationForm.addEventListener("submit", submitJobApplication);
document.getElementById("job-search").addEventListener("input", renderJobBoard);
document.getElementById("job-type-filter").addEventListener("change", renderJobBoard);
document.getElementById("job-sort").addEventListener("change", renderJobBoard);
document.getElementById("provider-job-filter").addEventListener("change", renderProviderApplicants);
document.getElementById("provider-applicant-filter").addEventListener("change", renderProviderApplicants);
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
document.getElementById("my-profile-form").addEventListener("submit", saveMyProfile);
document.getElementById("employer-profile-form").addEventListener("submit", saveEmployerProfile);
document.getElementById("portfolio-form").addEventListener("submit", savePortfolioProject);
document.getElementById("project-cancel-edit").addEventListener("click", resetPortfolioEditor);
document.getElementById("skill-form").addEventListener("submit", renderSkillAnalysis);
document.getElementById("skill-job-listing")?.addEventListener("change", fillSkillAnalysisFromJob);
document.getElementById("application-material-job")?.addEventListener("change", (event) => loadApplicationMaterials(event.target.value));
document.getElementById("application-materials-form")?.addEventListener("submit", generateApplicationMaterials);
document.getElementById("application-material-copy")?.addEventListener("click", copyApplicationMaterials);
interviewPrepForm.addEventListener("submit", generateInterviewPack);
aiAssistForm.addEventListener("submit", submitAIAssist);
document.getElementById("download-interview-pack").addEventListener("click", downloadInterviewPack);
document.querySelectorAll(".ai-assistant-tab").forEach((button) => {
    button.addEventListener("click", () => {
        document.querySelectorAll(".ai-assistant-tab").forEach((tab) => {
            const active = tab === button;
            tab.classList.toggle("is-active", active);
            tab.setAttribute("aria-selected", String(active));
        });
        const task = button.dataset.aiTask;
        const text = document.getElementById("ai-text");
        document.getElementById("ai-task").value = task;
        text.minLength = task === "ask_question" ? 2 : 40;
        text.placeholder = task === "ask_question"
            ? "Ask a career question and include any context that would help."
            : "Paste the résumé excerpt or interview answer you want help with.";
        document.getElementById("ai-role").value = task === "ask_question" ? "Career guidance" : "";
    });
});
document.querySelectorAll(".nav-link").forEach((link) => {
    link.addEventListener("click", (event) => {
        event.preventDefault();
        if (window.location.hash === link.getAttribute("href")) {
            activatePageFromHash();
            return;
        }
        window.location.hash = link.getAttribute("href");
    });
});
document.querySelectorAll('a[href^="#"]:not(.nav-link)').forEach((link) => {
    link.addEventListener("click", (event) => {
        const pageId = link.getAttribute("href").slice(1);
        if (!document.getElementById(pageId)?.matches("[data-page-view]")) return;
        event.preventDefault();
        if (window.location.hash === `#${pageId}`) {
            activatePageFromHash();
            return;
        }
        window.location.hash = pageId;
    });
});
window.addEventListener("hashchange", activatePageFromHash);
activatePageFromHash();

setupSupabase();
