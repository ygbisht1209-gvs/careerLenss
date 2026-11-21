"use strict";

const PLACEHOLDER_VALUES = new Set([
    "n/a",
    "na",
    "none",
    "not provided",
    "not applicable",
    "todo",
    "tbd",
    "your headline",
    "your about section",
    "enter your role",
    "enter your headline",
    "enter your about section"
]);

function hasMeaningfulText(value, minimumLength = 1) {
    if (typeof value !== "string") return false;
    const normalized = value.trim().replace(/\s+/g, " ");
    return normalized.length >= minimumLength
        && !PLACEHOLDER_VALUES.has(normalized.toLocaleLowerCase())
        && !/^e\.g\.?\b/i.test(normalized);
}

function summarizeApplications(applications, type) {
    const items = Array.isArray(applications) ? applications : [];
    const terminal = type === "manual"
        ? new Set(["Offer", "Rejected"])
        : new Set(["Offer", "Hired", "Rejected", "Withdrawn"]);
    return {
        total: items.length,
        inProgress: items.filter((item) => !terminal.has(item.status)).length,
        interviews: items.filter((item) => item.status === "Interview").length,
        offers: items.filter((item) => item.status === "Offer").length,
        rejected: items.filter((item) => item.status === "Rejected").length,
        withdrawn: items.filter((item) => item.status === "Withdrawn").length,
        hired: items.filter((item) => item.status === "Hired").length
    };
}

function summarizeCareerDashboard({
    profile = {},
    projects = [],
    learningPlan = [],
    manualApplications = [],
    careerApplications = [],
    recommendations = [],
    learningAvailable = true,
    portfolioAvailable = true
} = {}) {
    const savedSkills = Array.isArray(profile.skills)
        ? profile.skills.filter((skill) => hasMeaningfulText(skill, 2))
        : [];
    const projectsList = Array.isArray(projects) ? projects : [];
    const projectSkills = new Set(
        projectsList.flatMap((project) =>
            Array.isArray(project.skills)
                ? project.skills.filter((skill) => hasMeaningfulText(skill, 2))
                : []
        ).map((skill) => skill.trim().toLocaleLowerCase())
    );
    const profileFields = [
        hasMeaningfulText(profile.target_role, 2),
        hasMeaningfulText(profile.headline, 3),
        hasMeaningfulText(profile.about, 20),
        savedSkills.length > 0,
        projectsList.length > 0
    ];
    const plan = Array.isArray(learningPlan) ? learningPlan : [];
    const careerItems = Array.isArray(careerApplications) ? careerApplications : [];
    const linkedResumeCount = careerItems.filter(
        (application) => hasMeaningfulText(application.resume_path)
    ).length;

    return {
        profile: {
            completeFields: profileFields.filter(Boolean).length,
            totalFields: profileFields.length,
            completeness: Math.round(
                profileFields.filter(Boolean).length / profileFields.length * 100
            ),
            skillsCount: savedSkills.length,
            projectsCount: projectsList.length,
            projectSkillsCount: projectSkills.size,
            linkedResumeCount
        },
        projects: {
            count: projectsList.length,
            recent: projectsList.slice(0, 3)
        },
        learning: {
            total: plan.length,
            inProgress: plan.filter((item) => item.status === "in_progress").length,
            completed: plan.filter((item) => item.status === "completed").length,
            notStarted: plan.filter((item) => item.status === "not_started").length,
            skills: [...new Set(plan.flatMap((item) =>
                Array.isArray(item.resource?.skill_tags)
                    ? item.resource.skill_tags.filter((skill) =>
                        hasMeaningfulText(skill, 2)
                    )
                    : []
            ).map((skill) => skill.trim()))]
                .sort((first, second) => first.localeCompare(second))
        },
        applications: {
            manual: summarizeApplications(manualApplications, "manual"),
            careerLens: summarizeApplications(careerItems, "careerLens")
        },
        recommendations: Array.isArray(recommendations)
            ? recommendations.filter((job) => job && job.id && job.match).slice(0, 3)
            : [],
        availability: {
            learning: Boolean(learningAvailable),
            portfolio: Boolean(portfolioAvailable)
        }
    };
}

function getCareerNextActions(summary, { skillsAnalyzed = false } = {}) {
    const actions = [];
    if (summary.profile.completeness < 100) {
        actions.push({
            label: "Complete your career profile",
            href: "#my-profile",
            detail: `${summary.profile.completeFields} of ${summary.profile.totalFields} profile fields are complete.`
        });
    }
    if (!summary.profile.projectsCount && summary.availability.portfolio) {
        actions.push({
            label: "Add a portfolio project",
            href: "#my-profile",
            detail: "Record a project and the skills you used."
        });
    }
    if (!summary.learning.total && summary.availability.learning) {
        actions.push({
            label: "Explore learning resources",
            href: "#learning-workspace",
            detail: "Browse the verified catalogue and save a resource to your plan."
        });
    }
    if (!summary.profile.skillsCount) {
        actions.push({
            label: "Add your skills",
            href: "#skills-workspace",
            detail: "List skills you can discuss and support with genuine examples."
        });
    }
    if (!skillsAnalyzed && summary.profile.skillsCount) {
        actions.push({
            label: "Review a target role's skill requirements",
            href: "#skills-workspace",
            detail: "Compare profile and project evidence with a real job description."
        });
    }
    if (summary.learning.inProgress) {
        actions.push({
            label: "Continue a learning activity",
            href: "#learning-workspace",
            detail: `${summary.learning.inProgress} resource${summary.learning.inProgress === 1 ? "" : "s"} marked in progress.`
        });
    }
    if (summary.recommendations.length) {
        actions.push({
            label: `Review a recommended role: ${summary.recommendations[0].title}`,
            href: "#browse-jobs",
            detail: "Open the job board to review the explanation and application options."
        });
    }
    if (summary.applications.manual.total || summary.applications.careerLens.total) {
        actions.push({
            label: "Review application updates",
            href: "#applications",
            detail: "Update statuses and check any follow-up dates."
        });
    }
    return actions.slice(0, 5);
}

globalThis.CareerLensDashboardUi = Object.freeze({
    hasMeaningfulText,
    summarizeCareerDashboard,
    getCareerNextActions
});
