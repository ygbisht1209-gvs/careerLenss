import unittest

from backend.skill_gap import analyze_skill_gaps, normalize_skill_name


class SkillGapAnalysisTests(unittest.TestCase):
    def test_normalizes_skill_name_variations(self):
        self.assertEqual(normalize_skill_name(" Postgres "), "PostgreSQL")
        self.assertEqual(normalize_skill_name("RESTful APIs"), "REST APIs")
        self.assertEqual(normalize_skill_name("cpp"), "C++")
        self.assertIsNone(normalize_skill_name("Rust"))

    def test_overlapping_aliases_do_not_inflate_requirement_frequency(self):
        result = analyze_skill_gaps("Node.js and Node services are part of the role.")

        node = next(item for item in result["skills"] if item["name"] == "Node.js")
        self.assertEqual(node["requirement_mentions"], 2)

    def test_javascript_short_alias_requires_programming_context(self):
        ambiguous = analyze_skill_gaps("JS is mentioned in the job description.")
        contextual = analyze_skill_gaps("JS and React are used in this web role.")
        node_runtime_only = analyze_skill_gaps("Node.js is preferred for this role.")

        self.assertNotIn("JavaScript", {item["name"] for item in ambiguous["skills"]})
        self.assertIn("JavaScript", {item["name"] for item in contextual["skills"]})
        self.assertNotIn("JavaScript", {
            item["name"] for item in node_runtime_only["skills"]
        })
        self.assertIn("Node.js", {
            item["name"] for item in node_runtime_only["skills"]
        })

    def test_extracts_distinct_recognized_job_requirements(self):
        result = analyze_skill_gaps(
            "We need PostgreSQL/Postgres, SQL, and FastAPI experience for this role."
        )

        self.assertEqual(
            {item["name"] for item in result["skills"]},
            {"PostgreSQL", "SQL", "FastAPI"},
        )
        self.assertEqual(result["summary"]["total_required_skills"], 3)
        postgres = next(item for item in result["skills"] if item["name"] == "PostgreSQL")
        self.assertEqual(postgres["requirement_mentions"], 2)

    def test_classifies_contextual_resume_evidence_as_demonstrated(self):
        result = analyze_skill_gaps(
            "Python and Flask are required to build REST APIs for this position.",
            resume_text="Projects: Built a Flask REST API with Python for a course project.",
        )

        flask = next(item for item in result["skills"] if item["name"] == "Flask")
        self.assertEqual(flask["status"], "Demonstrated")
        self.assertEqual(flask["evidence"][0]["source"], "Résumé")
        self.assertIn("Built a Flask REST API", flask["evidence"][0]["excerpt"])
        self.assertIn("not an independent verification", flask["explanation"])

    def test_a_skill_mention_without_context_needs_assessment(self):
        result = analyze_skill_gaps(
            "Python and PostgreSQL knowledge required for this position.",
            user_text="Python, Postgres",
        )

        postgres = next(item for item in result["skills"] if item["name"] == "PostgreSQL")
        self.assertEqual(postgres["status"], "Needs assessment")
        self.assertEqual(postgres["evidence"][0]["source"], "Skills you listed")
        self.assertIn("not describe", postgres["explanation"])

    def test_project_skill_tags_are_not_mastery_but_project_context_is_cited(self):
        tagged_only = analyze_skill_gaps(
            "Python is required for this position.",
            project_evidence=[{
                "title": "API project",
                "description": "A small web service.",
                "skills": ["Python"],
            }],
        )
        contextual = analyze_skill_gaps(
            "Python is required for this position.",
            project_evidence=[{
                "title": "API project",
                "description": "A small web service.",
                "contribution": "Built a Python API and wrote tests.",
                "skills": ["Python"],
            }],
        )

        self.assertEqual(tagged_only["skills"][0]["status"], "Needs assessment")
        self.assertIn("not independently verified", tagged_only["skills"][0]["evidence"][0]["source"])
        self.assertEqual(contextual["skills"][0]["status"], "Demonstrated")
        self.assertIn("Portfolio project: API project", contextual["skills"][0]["evidence"][0]["source"])

    def test_absence_is_reported_as_no_evidence_not_lack_of_skill(self):
        result = analyze_skill_gaps(
            "This role requires Docker and teamwork in project delivery."
        )

        self.assertTrue(all(item["status"] == "No evidence found" for item in result["skills"]))
        self.assertTrue(all("does not mean you lack" in item["explanation"] for item in result["skills"]))
        self.assertEqual(result["summary"]["skills_with_supporting_evidence"], 0)
        self.assertEqual(result["summary"]["no_evidence_found"], 2)

    def test_summary_and_recommendations_are_explainable(self):
        result = analyze_skill_gaps(
            "FastAPI, SQL, PostgreSQL, and Docker are used in this role.",
            experience_text="Built and tested one FastAPI endpoint.",
        )

        self.assertEqual(result["summary"]["total_required_skills"], 4)
        self.assertEqual(result["summary"]["skills_with_supporting_evidence"], 1)
        self.assertEqual(result["summary"]["no_evidence_found"], 3)
        self.assertTrue(result["summary"]["priority_skills"])
        fastapi = next(item for item in result["skills"] if item["name"] == "FastAPI")
        self.assertTrue(fastapi["next_action"])
        self.assertEqual(
            fastapi["learning_sequence"],
            ["Python fundamentals", "SQL", "FastAPI", "PostgreSQL integration", "REST API project", "Docker"],
        )
        self.assertIn("does not verify proficiency", result["note"])

    def test_unrecognized_description_has_empty_result_without_fake_scores(self):
        result = analyze_skill_gaps("A role requiring a passion for innovation and curiosity.")

        self.assertEqual(result["skills"], [])
        self.assertEqual(result["summary"]["total_required_skills"], 0)
        self.assertNotIn("score", result)


if __name__ == "__main__":
    unittest.main()
