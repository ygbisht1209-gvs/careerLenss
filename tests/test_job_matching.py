import unittest

from backend.job_matching import (
    build_job_recommendations,
    build_job_what_if,
    extract_job_requirements,
)


class JobMatchingTests(unittest.TestCase):
    def test_extracts_only_supported_skills_and_separates_explicit_preferences(self):
        requirements = extract_job_requirements(
            "The team builds services with Docker and JavaScript.",
            "Required: PostgreSQL. Preferred: Docker. JavaScript experience is a plus.",
        )

        self.assertEqual(
            [(item["name"], item["category"]) for item in requirements],
            [
                ("Docker", "preferred"),
                ("JavaScript", "preferred"),
                ("PostgreSQL", "required"),
            ],
        )
        self.assertNotIn("Python", {item["name"] for item in requirements})

    def test_requirement_headings_apply_to_following_skill_lines(self):
        requirements = extract_job_requirements(
            "",
            "Required qualifications:\n- Postgres\n"
            "Preferred skills:\n- RESTful API",
        )

        self.assertEqual(
            [(item["name"], item["category"]) for item in requirements],
            [("PostgreSQL", "required"), ("REST APIs", "preferred")],
        )

    def test_profile_evidence_explanation_and_weighted_score_are_deterministic(self):
        job = {
            "id": "job-1",
            "title": "Backend Developer",
            "company": "Example",
            "description": "Required: Python and SQL. Preferred: Docker.",
            "requirements": "",
        }
        profile = {
            "target_role": "Backend Developer",
            "skills": ["Python", "SQL"],
            "headline": "",
            "about": "Built a Python service and used SQL for a class project.",
        }

        first = build_job_recommendations([job], profile)
        second = build_job_recommendations([job], profile)
        match = first["jobs"][0]["match"]

        self.assertEqual(first, second)
        self.assertTrue(first["profile"]["complete"])
        self.assertEqual(match["score"], 80)
        self.assertEqual(
            [item["status"] for item in match["required_skills"]],
            ["Demonstrated", "Demonstrated"],
        )
        self.assertEqual(
            match["preferred_skills"][0]["status"], "No evidence found"
        )
        self.assertTrue(match["relevant_evidence"])
        self.assertIn("not an independent", match["required_skills"][0]["explanation"])

    def test_what_if_simulation_is_deterministic_and_does_not_mutate_profile(self):
        job = {
            "id": "job-1",
            "title": "Backend Developer",
            "company": "Example",
            "description": "Required: Python and SQL.",
            "requirements": "",
        }
        profile = {
            "skills": ["Python"],
            "headline": "",
            "about": "Built Python tools for a class project.",
        }

        first = build_job_what_if(job, profile, add_skills=["SQL"])
        second = build_job_what_if(job, profile, add_skills=["SQL"])

        self.assertEqual(first, second)
        self.assertEqual(first["baseline_score"], 50)
        self.assertEqual(first["simulated_score"], 68)
        self.assertEqual(first["delta"], 18)
        self.assertEqual(first["added_skills"], ["SQL"])
        self.assertEqual(profile["skills"], ["Python"])
        self.assertEqual(
            first["simulated_match"]["required_skills"][1]["status"],
            "Needs assessment",
        )

    def test_empty_profile_and_unclassified_mentions_do_not_get_misleading_scores(self):
        result = build_job_recommendations(
            [{
                "id": "job-1",
                "title": "Developer",
                "company": "Example",
                "description": "Python and Flask are used by the team.",
                "requirements": "",
            }],
            {},
        )

        match = result["jobs"][0]["match"]
        self.assertIsNone(match["score"])
        self.assertEqual(match["required_skills"], [])
        self.assertEqual(
            {item["name"] for item in match["other_skill_mentions"]},
            {"Python", "Flask"},
        )
        self.assertTrue(result["profile"]["missing_fields"])
        self.assertTrue(any("not available" in item for item in match["limitations"]))

    def test_unmatched_profile_skill_is_not_claimed_as_demonstrated(self):
        result = build_job_recommendations(
            [{
                "id": "job-1",
                "title": "Data Analyst",
                "company": "Example",
                "description": "Required: Python. Preferred: SQL.",
                "requirements": "",
            }],
            {"skills": ["Python"], "headline": "", "about": ""},
        )

        match = result["jobs"][0]["match"]
        self.assertEqual(match["required_skills"][0]["status"], "Needs assessment")
        self.assertEqual(match["preferred_skills"][0]["status"], "No evidence found")
        self.assertEqual(match["score"], 28)
        self.assertTrue(match["next_steps"])

    def test_private_project_context_is_used_but_tags_alone_are_not_mastery(self):
        project = {
            "title": "API project",
            "description": "A small web service.",
            "contribution": "Built a Python API and wrote tests.",
            "skills": ["Python"],
        }
        result = build_job_recommendations(
            [{
                "id": "job-1",
                "title": "Developer",
                "company": "Example",
                "description": "Required: Python.",
                "requirements": "",
            }],
            {"project_evidence": [project]},
        )

        match = result["jobs"][0]["match"]
        self.assertEqual(match["required_skills"][0]["status"], "Demonstrated")
        self.assertIn("Portfolio project: API project", match["required_skills"][0]["evidence"][0]["source"])
        self.assertTrue(result["profile"]["portfolio_evidence_available"])

    def test_empty_job_listings_are_preserved(self):
        self.assertEqual(
            build_job_recommendations([], {})["jobs"],
            [],
        )

    def test_missing_job_description_uses_structured_requirements_or_no_score(self):
        result = build_job_recommendations(
            [
                {
                    "id": "requirements-only",
                    "title": "Analyst",
                    "company": "Example",
                    "description": "",
                    "requirements": "Required: SQL.",
                },
                {
                    "id": "empty",
                    "title": "Role",
                    "company": "Example",
                    "description": "",
                    "requirements": "",
                },
            ],
            {"skills": ["SQL"], "headline": "", "about": ""},
        )
        by_id = {job["id"]: job["match"] for job in result["jobs"]}

        self.assertEqual(
            by_id["requirements-only"]["required_skills"][0]["name"],
            "SQL",
        )
        self.assertEqual(by_id["requirements-only"]["score"], 35)
        self.assertIsNone(by_id["empty"]["score"])

    def test_jobs_sort_by_score_then_newest_with_unscored_items_last(self):
        jobs = [
            {
                "id": "unscored",
                "title": "Unscored",
                "company": "Example",
                "description": "A collaborative role.",
                "requirements": "",
                "created_at": "2026-03-01T00:00:00Z",
            },
            {
                "id": "zero",
                "title": "Zero",
                "company": "Example",
                "description": "SQL required.",
                "requirements": "",
                "created_at": "2026-03-02T00:00:00Z",
            },
            {
                "id": "top",
                "title": "Top",
                "company": "Example",
                "description": "Python required.",
                "requirements": "",
                "created_at": "2025-01-01T00:00:00Z",
            },
        ]
        result = build_job_recommendations(
            jobs,
            {"about": "Built a Python service.", "skills": []},
        )

        self.assertEqual(
            [job["id"] for job in result["jobs"]],
            ["top", "zero", "unscored"],
        )


if __name__ == "__main__":
    unittest.main()
