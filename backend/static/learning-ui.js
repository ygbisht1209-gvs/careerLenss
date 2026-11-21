"use strict";

function filterLearningResources(resources, filters) {
    const query = filters.query.trim().toLocaleLowerCase();
    return resources.filter((resource) => {
        const matchesQuery = !query ||
            `${resource.title} ${(resource.skill_tags || []).join(" ")}`
                .toLocaleLowerCase().includes(query);
        const matchesCategory = filters.category === "all" ||
            resource.category?.slug === filters.category;
        const matchesDifficulty = filters.difficulty === "all" ||
            resource.difficulty === filters.difficulty;
        return matchesQuery && matchesCategory && matchesDifficulty;
    });
}

function groupLearningPlan(plan) {
    return {
        not_started: plan.filter((item) => item.status === "not_started"),
        in_progress: plan.filter((item) => item.status === "in_progress"),
        completed: plan.filter((item) => item.status === "completed")
    };
}

function getLearningPlanSkills(plan) {
    const skills = new Map();
    plan.forEach((item) => {
        (item.resource?.skill_tags || []).forEach((tag) => {
            const value = typeof tag === "string" ? tag.trim() : "";
            const key = value.toLocaleLowerCase();
            if (value && !skills.has(key)) skills.set(key, value);
        });
    });
    return [...skills.values()].sort((first, second) => first.localeCompare(second));
}

function formatLearningDate(value) {
    if (typeof value !== "string" || !value) return "Date unavailable";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "Date unavailable";
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(date);
}

globalThis.CareerLensLearningUi = Object.freeze({
    filterLearningResources,
    groupLearningPlan,
    getLearningPlanSkills,
    formatLearningDate
});
