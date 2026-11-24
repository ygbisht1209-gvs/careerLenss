"use strict";

require("../backend/static/dashboard-ui.js");

const assert = require("node:assert/strict");
const test = require("node:test");
const {
    hasMeaningfulText,
    summarizeCareerDashboard,
    getCareerNextActions
} = globalThis.CareerLensDashboardUi;

test("profile completeness excludes blanks and placeholder values", () => {
    const summary = summarizeCareerDashboard({
        profile: {
            target_role: "  N/A ",
            headline: "Your headline",
            about: "A meaningful professional summary with actual details.",
            skills: ["", "  "]
        }
    });

    assert.equal(summary.profile.completeFields, 1);
    assert.equal(summary.profile.totalFields, 5);
    assert.equal(summary.profile.completeness, 20);
    assert.equal(hasMeaningfulText("e.g. Enter a role", 2), false);
});

test("dashboard counts learning records and distinct project skills from saved data", () => {
    const summary = summarizeCareerDashboard({
        projects: [
            { title: "First", skills: ["Python", "SQL"] },
            { title: "Second", skills: ["python", "Docker"] }
        ],
        learningPlan: [
            { status: "in_progress", resource: { skill_tags: ["Python", "SQL"] } },
            { status: "completed", resource: { skill_tags: ["SQL"] } },
            { status: "not_started", resource: { skill_tags: ["Docker"] } }
        ]
    });

    assert.equal(summary.projects.count, 2);
    assert.equal(summary.profile.projectSkillsCount, 3);
    assert.deepEqual(summary.learning, {
        total: 3,
        inProgress: 1,
        completed: 1,
        notStarted: 1,
        skills: ["Docker", "Python", "SQL"]
    });
});

test("application sources are summarized separately using their stored statuses", () => {
    const summary = summarizeCareerDashboard({
        manualApplications: [
            { status: "Applied" },
            { status: "Interview" },
            { status: "Offer" },
            { status: "Rejected" }
        ],
        careerApplications: [
            { status: "Submitted", resume_path: "private/path.pdf" },
            { status: "Interview", resume_path: null },
            { status: "Hired", resume_path: "private/another.pdf" },
            { status: "Withdrawn" }
        ]
    });

    assert.deepEqual(summary.applications.manual, {
        total: 4,
        inProgress: 2,
        interviews: 1,
        offers: 1,
        rejected: 1,
        withdrawn: 0,
        hired: 0
    });
    assert.deepEqual(summary.applications.careerLens, {
        total: 4,
        inProgress: 2,
        interviews: 1,
        offers: 0,
        rejected: 0,
        withdrawn: 1,
        hired: 1
    });
    assert.equal(summary.profile.linkedResumeCount, 2);
    assert.deepEqual(summary.applications.statusCounts, [
        { status: "Applied", manual: 1, careerLens: 0, total: 1 },
        { status: "Submitted", manual: 0, careerLens: 1, total: 1 },
        { status: "Interview", manual: 1, careerLens: 1, total: 2 },
        { status: "Offer", manual: 1, careerLens: 0, total: 1 },
        { status: "Hired", manual: 0, careerLens: 1, total: 1 },
        { status: "Rejected", manual: 1, careerLens: 0, total: 1 },
        { status: "Withdrawn", manual: 0, careerLens: 1, total: 1 }
    ]);
    assert.equal(summary.applications.countsComplete, true);
});

test("next actions point to existing features and avoid generic populated actions", () => {
    const summary = summarizeCareerDashboard({
        profile: { skills: ["Python"] },
        learningPlan: [{ status: "in_progress" }],
        recommendations: [{
            id: "job-1",
            title: "Backend Developer",
            match: { score: 75 }
        }],
        manualApplications: [{ status: "Applied" }]
    });

    test("application status counts are unavailable rather than partial at the record limit", () => {
        const summary = summarizeCareerDashboard({
            manualApplications: Array.from({ length: 1000 }, () => ({ status: "Applied" }))
        });
        assert.equal(summary.applications.countsComplete, false);
        assert.deepEqual(summary.applications.statusCounts, [
            { status: "Applied", manual: 1000, careerLens: 0, total: 1000 }
        ]);
    });
    const actions = getCareerNextActions(summary);

    assert.deepEqual(actions.map((action) => action.href), [
        "#my-profile",
        "#my-profile",
        "#skills-workspace",
        "#learning-workspace",
        "#browse-jobs"
    ]);
    assert.equal(actions.length, 5);
});

