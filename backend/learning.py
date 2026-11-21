SKILL_ALIASES = {
    "js": "javascript",
    "postgres": "postgresql",
    "postgre sql": "postgresql",
    "rest api": "rest apis",
    "node js": "node.js",
}

LEARNING_NEED_STATUSES = {"Needs assessment", "No evidence found"}


def normalize_skill_name(name):
    normalized = " ".join(
        "".join(character.lower() if character.isalnum() or character in "+#." else " "
                for character in name).split()
    )
    return SKILL_ALIASES.get(normalized, normalized)


def recommend_learning_resources(skill_assessments, resources):
    learning_needs = {}
    for assessment in skill_assessments:
        if assessment["status"] not in LEARNING_NEED_STATUSES:
            continue
        key = normalize_skill_name(assessment["name"])
        if key:
            learning_needs.setdefault(key, assessment["name"])

    recommendations = []
    for resource in resources:
        resource_skills = {
            normalize_skill_name(tag)
            for tag in resource.get("skill_tags", [])
            if isinstance(tag, str)
        }
        matched_skills = [
            name for key, name in learning_needs.items()
            if key in resource_skills
        ]
        if matched_skills:
            recommendations.append({
                **resource,
                "matched_skills": matched_skills,
            })
    return recommendations
