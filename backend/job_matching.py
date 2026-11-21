import re

from backend.skill_gap import (
    SKILLS,
    _excerpt,
    _skill_matches,
    _source_segments,
    analyze_skill_gaps,
    normalize_skill_name,
)


_PREFERRED_CUES = re.compile(
    r"\b(preferred|preferably|desirable|ideally|nice to have|bonus|a plus)\b",
    re.IGNORECASE,
)
_REQUIRED_CUES = re.compile(
    r"\b(required|must|mandatory|essential|minimum|need(?:ed)?|"
    r"proficiency in|experience with)\b",
    re.IGNORECASE,
)
_PREFERRED_SECTION = re.compile(
    r"^\s*[-*]?\s*(?:preferred|nice to have|desirable|bonus)(?:\s+"
    r"(?:skills|qualifications|requirements))?\s*:?\s*$",
    re.IGNORECASE,
)
_REQUIRED_SECTION = re.compile(
    r"^\s*[-*]?\s*(?:required|must have|essential|minimum)(?:\s+"
    r"(?:skills|qualifications|requirements))?\s*:?\s*$",
    re.IGNORECASE,
)
_SCORE_VALUES = {
    "Demonstrated": 1.0,
    "Needs assessment": 0.35,
    "No evidence found": 0.0,
}


def _requirement_category(segment, start, end):
    clause_start = max(
        segment.rfind(delimiter, 0, start) for delimiter in (";", "\n")
    ) + 1
    clause_end = min(
        (
            position
            for delimiter in (";", "\n")
            if (position := segment.find(delimiter, end)) >= 0
        ),
        default=len(segment),
    )
    clause = segment[clause_start:clause_end]
    skill_position = (start + end) // 2 - clause_start
    cues = [
        (match.start(), "preferred")
        for match in _PREFERRED_CUES.finditer(clause)
    ] + [
        (match.start(), "required")
        for match in _REQUIRED_CUES.finditer(clause)
    ]
    relevant_cues = [
        cue for cue in cues
        if abs(cue[0] - skill_position) <= 100
    ]
    if relevant_cues:
        return min(
            relevant_cues,
            key=lambda cue: (abs(cue[0] - skill_position), cue[1] == "required"),
        )[1]
    return "unspecified"


def extract_job_requirements(description, requirements=""):
    """Extract canonical skills, honoring explicit preference wording."""
    extracted = {}
    for source, text in (
        ("requirements", requirements),
        ("description", description),
    ):
        if not isinstance(text, str) or not text.strip():
            continue
        section_category = None
        lines = text.splitlines() or [text]
        for line in lines:
            heading = line.strip().lstrip("-* ").strip("*").strip()
            if _PREFERRED_SECTION.fullmatch(heading):
                section_category = "preferred"
                continue
            if _REQUIRED_SECTION.fullmatch(heading):
                section_category = "required"
                continue
            for segment in _source_segments(line):
                for skill in SKILLS:
                    for match in _skill_matches(segment, skill):
                        category = _requirement_category(
                            segment, match.start(), match.end()
                        )
                        if category == "unspecified":
                            category = section_category or (
                                "required" if source == "requirements" else "unspecified"
                            )
                        current = extracted.get(skill.name)
                        if current is None or (
                            current["category"] == "unspecified"
                            or category == "required"
                        ):
                            extracted[skill.name] = {
                                "name": skill.name,
                                "category": category,
                                "excerpt": _excerpt(
                                    segment, match.start(), match.end()
                                ),
                            }
    return sorted(extracted.values(), key=lambda item: item["name"].casefold())


def _assessment_by_skill(assessments, requirements):
    included = {item["name"] for item in requirements}
    return {
        assessment["name"]: assessment
        for assessment in assessments
        if assessment["name"] in included
    }


def _score(required_skills, preferred_skills, has_profile_evidence):
    if not has_profile_evidence or not (required_skills or preferred_skills):
        return None

    required_weight = 0.8 if required_skills and preferred_skills else 1.0
    preferred_weight = 0.2 if required_skills and preferred_skills else 1.0
    score = 0.0
    if required_skills:
        score += required_weight * sum(
            _SCORE_VALUES[item["status"]] for item in required_skills
        ) / len(required_skills)
    if preferred_skills:
        score += preferred_weight * sum(
            _SCORE_VALUES[item["status"]] for item in preferred_skills
        ) / len(preferred_skills)
    return round(score * 100)


def build_job_recommendations(
    jobs, profile, learning_records=(), learning_records_available=True
):
    """Build deterministic, evidence-aware explanations for published jobs."""
    profile = profile if isinstance(profile, dict) else {}
    if not isinstance(learning_records, (list, tuple)):
        learning_records = []
    listed_skills = profile.get("skills")
    if not isinstance(listed_skills, list):
        listed_skills = []
    listed_skills = [
        skill.strip()
        for skill in listed_skills
        if isinstance(skill, str) and skill.strip()
    ]

    profile_context = "\n".join(
        value.strip()
        for value in (profile.get("headline"), profile.get("about"))
        if isinstance(value, str) and value.strip()
    )
    project_evidence = profile.get("project_evidence")
    if not isinstance(project_evidence, (list, tuple)):
        project_evidence = []
    has_profile_evidence = bool(listed_skills or profile_context or project_evidence)
    profile_complete = bool(
        profile_context
        and listed_skills
        and isinstance(profile.get("target_role"), str)
        and profile["target_role"].strip()
    )
    missing_profile_fields = [
        label
        for label, available in (
            ("skills", bool(listed_skills)),
            ("headline or about", bool(profile_context)),
            ("target role", bool(
                isinstance(profile.get("target_role"), str)
                and profile["target_role"].strip()
            )),
        )
        if not available
    ]

    planned_skills = {}
    for record in learning_records:
        if not isinstance(record, dict):
            continue
        resource = record.get("resource")
        if not isinstance(resource, dict):
            continue
        title = resource.get("title")
        status = record.get("status")
        tags = resource.get("skill_tags")
        if (
            not isinstance(title, str)
            or status not in {"not_started", "in_progress", "completed"}
            or not isinstance(tags, list)
        ):
            continue
        for tag in tags:
            if isinstance(tag, str):
                name = normalize_skill_name(tag)
                if name:
                    planned_skills.setdefault(name, (title, status))

    recommendations = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        description = job.get("description")
        requirements_text = job.get("requirements")
        description = description if isinstance(description, str) else ""
        requirements_text = requirements_text if isinstance(requirements_text, str) else ""
        extracted = extract_job_requirements(description, requirements_text)
        classified = [item for item in extracted if item["category"] != "unspecified"]
        analysis = analyze_skill_gaps(
            "\n".join((requirements_text, description)),
            user_text=", ".join(listed_skills),
            experience_text=profile_context,
            project_evidence=project_evidence,
        )
        assessments = _assessment_by_skill(analysis["skills"], classified)

        skill_details = []
        for requirement in classified:
            assessment = assessments.get(requirement["name"])
            if assessment is None:
                continue
            if (
                assessment["status"] == "No evidence found"
                and requirement["name"] in planned_skills
            ):
                resource_title, plan_status = planned_skills[requirement["name"]]
                plan_status_label = plan_status.replace("_", " ")
                assessment["status"] = "Needs assessment"
                assessment["evidence"] = [{
                    "source": "Learning plan (self-reported)",
                    "excerpt": (
                        f'Saved resource "{resource_title}" is marked '
                        f"{plan_status_label}. This records a plan status, "
                        "not verified skill proficiency."
                    ),
                }]
                assessment["explanation"] = (
                    "A related resource appears in your learning plan. A saved "
                    "or completed resource does not verify proficiency; add a "
                    "genuine example of applying the skill."
                )
                assessment["next_action"] = (
                    "Apply the learning material in a small project or exercise, "
                    "then add a truthful example to your profile."
                )
            skill_details.append({
                **requirement,
                "status": assessment["status"],
                "evidence": assessment["evidence"],
                "explanation": assessment["explanation"],
                "next_action": assessment["next_action"],
            })

        required_skills = [
            item for item in skill_details if item["category"] == "required"
        ]
        preferred_skills = [
            item for item in skill_details if item["category"] == "preferred"
        ]
        unspecified_skills = [
            item for item in extracted if item["category"] == "unspecified"
        ]
        gaps = [
            item for item in skill_details
            if item["status"] != "Demonstrated"
        ]
        next_steps = []
        for item in gaps:
            if item["status"] == "Needs assessment":
                step = (
                    f"Add a genuine project, work, or learning example showing "
                    f"how you used {item['name']}."
                )
            else:
                step = item["next_action"]
            if step not in next_steps:
                next_steps.append(step)
            if len(next_steps) == 3:
                break

        limitations = [
            "This comparison uses saved profile and private portfolio text; "
            "portfolio skills and descriptions are user-entered and do not verify "
            "proficiency. It does not read private application résumés."
        ]
        limitations.append(
            "Learning-plan resources can indicate a topic being explored, but "
            "saved or completed courses are not treated as proof of proficiency."
        )
        if not learning_records_available:
            limitations.append(
                "Learning-plan records were unavailable and were not included "
                "in this comparison."
            )
        limitations.append(
            "Experience duration, education, and personal location or work-type "
            "preferences are not scored because the current profile has no "
            "corresponding structured data."
        )
        if unspecified_skills:
            limitations.append(
                "Skill mentions without explicit required/preferred wording are "
                "shown separately and do not affect the score."
            )
        if not classified:
            limitations.append(
                "No recognized skill was explicitly marked required or preferred, "
                "so a relevance score is not available."
            )
        if not has_profile_evidence:
            limitations.append(
                "Add profile skills or experience context before interpreting "
                "a score; none is shown for an empty evidence profile."
            )

        match = {
            "score": _score(
                required_skills, preferred_skills, has_profile_evidence
            ),
            "required_skills": required_skills,
            "preferred_skills": preferred_skills,
            "other_skill_mentions": unspecified_skills,
            "relevant_evidence": [
                evidence
                for item in skill_details
                for evidence in item["evidence"]
            ],
            "limitations": limitations,
            "next_steps": next_steps,
        }
        recommendations.append({**job, "match": match})

    recommendations.sort(
        key=lambda job: str(job.get("title") or "").casefold()
    )
    recommendations.sort(
        key=lambda job: str(job.get("created_at") or ""),
        reverse=True,
    )
    recommendations.sort(
        key=lambda job: (
            job["match"]["score"]
            if job["match"]["score"] is not None
            else -1
        ),
        reverse=True,
    )
    return {
        "jobs": recommendations,
        "profile": {
            "complete": profile_complete,
            "missing_fields": missing_profile_fields,
            "learning_records_available": learning_records_available,
            "portfolio_evidence_available": profile.get(
                "portfolio_evidence_available", True
            ),
        },
        "scoring": {
            "demonstrated": 1.0,
            "needs_assessment": 0.35,
            "no_evidence_found": 0.0,
            "required_weight": 0.8,
            "preferred_weight": 0.2,
            "note": (
                "A deterministic profile-to-job evidence alignment indicator, "
                "not a measure of competence, ATS score, or hiring probability. "
                "When a job has only one explicitly classified skill group, that "
                "group uses the full score weight."
            ),
        },
    }
