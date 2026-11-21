"use strict";

require("../backend/static/learning-ui.js");

const assert = require("node:assert/strict");
const test = require("node:test");
const {
    filterLearningResources,
    groupLearningPlan,
    getLearningPlanSkills,
    formatLearningDate
} = globalThis.CareerLensLearningUi;

const resources = [
    {
        id: "python",
        title: "Python basics",
        skill_tags: ["Python", "REST APIs"],
        category: { slug: "programming", name: "Programming" },
        difficulty: "Beginner"
    },
    {
        id: "sql",
        title: "Database practice",
        skill_tags: ["SQL", "PostgreSQL"],
        category: { slug: "databases", name: "Databases" },
        difficulty: "Intermediate"
    }
];

test("search matches resource titles and skill tags without case sensitivity", () => {
    assert.deepEqual(
        filterLearningResources(resources, {
            query: "postgresql",
            category: "all",
            difficulty: "all"
        }).map((resource) => resource.id),
        ["sql"]
    );
    assert.deepEqual(
        filterLearningResources(resources, {
            query: "PYTHON",
            category: "all",
            difficulty: "all"
        }).map((resource) => resource.id),
        ["python"]
    );
});

test("category and difficulty filters combine with the search", () => {
    assert.deepEqual(
        filterLearningResources(resources, {
            query: "practice",
            category: "databases",
            difficulty: "Intermediate"
        }).map((resource) => resource.id),
        ["sql"]
    );
    assert.deepEqual(
        filterLearningResources(resources, {
            query: "",
            category: "programming",
            difficulty: "Advanced"
        }),
        []
    );
});

test("learning plans are grouped by their persisted status", () => {
    const groups = groupLearningPlan([
        { id: "one", status: "not_started" },
        { id: "two", status: "in_progress" },
        { id: "three", status: "completed" }
    ]);
    assert.deepEqual(Object.keys(groups), ["not_started", "in_progress", "completed"]);
    assert.deepEqual(groups.in_progress.map((item) => item.id), ["two"]);
    assert.deepEqual(groups.completed.map((item) => item.id), ["three"]);
    assert.deepEqual(groupLearningPlan([]).completed, []);
});

test("plan skills are unique and combine actual saved resource tags", () => {
    assert.deepEqual(
        getLearningPlanSkills([
            { resource: { skill_tags: ["SQL", "Python"] } },
            { resource: { skill_tags: ["sql", "Docker"] } },
            { resource: null }
        ]),
        ["Docker", "Python", "SQL"]
    );
    assert.deepEqual(getLearningPlanSkills([]), []);
});

test("last-updated values are formatted and missing or invalid dates are explicit", () => {
    assert.notEqual(formatLearningDate("2026-02-14T12:00:00Z"), "Date unavailable");
    assert.equal(formatLearningDate("not-a-date"), "Date unavailable");
    assert.equal(formatLearningDate(null), "Date unavailable");
});
