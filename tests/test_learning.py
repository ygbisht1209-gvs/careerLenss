import unittest

from backend.learning import normalize_skill_name, recommend_learning_resources


class LearningRecommendationTests(unittest.TestCase):
    def test_skill_names_are_normalized_for_alias_matching(self):
        self.assertEqual(normalize_skill_name(" Postgres "), "postgresql")
        self.assertEqual(normalize_skill_name("REST API"), "rest apis")
        self.assertEqual(normalize_skill_name("Node JS"), "node.js")

    def test_only_skills_needing_investigation_match_catalogue_resources(self):
        skills = [
            {"name": "Python", "status": "Demonstrated"},
            {"name": "PostgreSQL", "status": "No evidence found"},
            {"name": "Docker", "status": "Needs assessment"},
        ]
        resources = [
            {
                "id": "course-1",
                "title": "Postgres Guide",
                "skill_tags": ["Postgres"],
            },
            {
                "id": "course-2",
                "title": "Containers Introduction",
                "skill_tags": ["Docker", "Linux"],
            },
            {
                "id": "course-3",
                "title": "Python Fundamentals",
                "skill_tags": ["Python"],
            },
            {
                "id": "course-4",
                "title": "Unrelated course",
                "skill_tags": ["Communication"],
            },
        ]

        result = recommend_learning_resources(skills, resources)

        self.assertEqual([item["id"] for item in result], ["course-1", "course-2"])
        self.assertEqual(result[0]["matched_skills"], ["PostgreSQL"])
        self.assertEqual(result[1]["matched_skills"], ["Docker"])
        self.assertNotIn("matched_skills", resources[0])

    def test_no_catalogue_resources_produces_no_recommendations(self):
        result = recommend_learning_resources(
            [{"name": "SQL", "status": "No evidence found"}],
            [],
        )
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
