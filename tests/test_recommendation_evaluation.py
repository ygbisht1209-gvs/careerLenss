import unittest

from backend.job_matching import extract_job_requirements
from backend.learning import recommend_learning_resources


MATCHING_CASES = (
    (
        "Required: Python and PostgreSQL. Preferred: Docker.",
        "",
        {
            ("Python", "required"),
            ("PostgreSQL", "required"),
            ("Docker", "preferred"),
        },
    ),
    (
        "",
        "Required qualifications:\n- RESTful API\nPreferred skills:\n- Node.js",
        {("REST APIs", "required"), ("Node.js", "preferred")},
    ),
    (
        "Experience with React is a plus; SQL is mandatory.",
        "",
        {("React", "preferred"), ("SQL", "required")},
    ),
    (
        "",
        "Must have Python; ideally Flask.",
        {("Python", "required"), ("Flask", "preferred")},
    ),
    (
        "A collaborative role with clear communication.",
        "",
        {("Communication", "unspecified")},
    ),
    (
        "Preferred: Postgres; required: JavaScript.",
        "",
        {("PostgreSQL", "preferred"), ("JavaScript", "required")},
    ),
)


def binary_metrics(predicted, expected):
    true_positives = len(predicted & expected)
    false_positives = len(predicted - expected)
    false_negatives = len(expected - predicted)
    precision = (
        true_positives / (true_positives + false_positives)
        if true_positives + false_positives
        else 1.0
    )
    recall = (
        true_positives / (true_positives + false_negatives)
        if true_positives + false_negatives
        else 1.0
    )
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return {
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


class RecommendationEvaluationTests(unittest.TestCase):
    def test_synthetic_job_skill_categories_match_the_annotated_cases(self):
        expected = set().union(*(case[2] for case in MATCHING_CASES))
        predicted = set()
        for description, requirements, _ in MATCHING_CASES:
            predicted.update(
                (item["name"], item["category"])
                for item in extract_job_requirements(description, requirements)
            )

        self.assertEqual(predicted, expected)
        self.assertEqual(binary_metrics(predicted, expected), {
            "true_positives": 11,
            "false_positives": 0,
            "false_negatives": 0,
            "precision": 1.0,
            "recall": 1.0,
            "f1": 1.0,
        })

    def test_synthetic_learning_recommendations_cover_only_requested_skills(self):
        assessments = [
            {"name": "Python", "status": "Demonstrated"},
            {"name": "PostgreSQL", "status": "No evidence found"},
            {"name": "Docker", "status": "Needs assessment"},
        ]
        resources = [
            {"id": "pg-guide", "title": "PostgreSQL guide", "skill_tags": ["Postgres"]},
            {"id": "docker-course", "title": "Docker basics", "skill_tags": ["Docker"]},
            {
                "id": "combined-resource",
                "title": "Database containers",
                "skill_tags": ["PostgreSQL", "Docker"],
            },
            {"id": "unrelated", "title": "HTML guide", "skill_tags": ["HTML"]},
        ]
        expected = {
            ("pg-guide", "PostgreSQL"),
            ("docker-course", "Docker"),
            ("combined-resource", "PostgreSQL"),
            ("combined-resource", "Docker"),
        }
        recommendations = recommend_learning_resources(assessments, resources)
        predicted = {
            (resource["id"], skill)
            for resource in recommendations
            for skill in resource["matched_skills"]
        }

        self.assertEqual(predicted, expected)
        self.assertEqual(binary_metrics(predicted, expected), {
            "true_positives": 4,
            "false_positives": 0,
            "false_negatives": 0,
            "precision": 1.0,
            "recall": 1.0,
            "f1": 1.0,
        })
        self.assertNotIn("matched_skills", resources[0])


if __name__ == "__main__":
    unittest.main()
