import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Skill:
    name: str
    aliases: tuple[str, ...]
    next_action: str
    learning_sequence: tuple[str, ...] = ()


SKILLS = (
    Skill("Python", ("python",), "Write a small script that reads input, handles errors, and includes tests."),
    Skill("C++", ("c++", "cpp", "c plus plus"), "Solve a focused programming exercise, then implement a small feature in C++."),
    Skill("Java", ("java",), "Build a small Java application and add tests for its core behavior."),
    Skill("JavaScript", ("javascript", "js"), "Build a small interactive feature and test success, loading, and error states."),
    Skill("TypeScript", ("typescript", "ts"), "Convert a small JavaScript feature to TypeScript and define its data types."),
    Skill("HTML", ("html", "html5"), "Create a semantic page and check its structure with a validator."),
    Skill("CSS", ("css", "css3"), "Style a small responsive page and verify it at mobile and desktop widths."),
    Skill("React", ("react", "react.js", "reactjs"), "Build a small component-driven interface with loading and error states."),
    Skill("Node.js", ("node.js", "nodejs", "node"), "Create a small Node.js service and test its request handling."),
    Skill("SQL", ("sql",), "Practice joins, aggregation, and subqueries using a small sample dataset."),
    Skill("PostgreSQL", ("postgresql", "postgres"), "Create a small relational schema and practice queries, constraints, and indexes."),
    Skill("MySQL", ("mysql",), "Create a small relational schema and practice queries and constraints."),
    Skill("MongoDB", ("mongodb", "mongo db"), "Model a small document collection and practice queries and validation."),
    Skill(
        "FastAPI",
        ("fastapi", "fast api"),
        "Build and test a small FastAPI endpoint with validation.",
        ("Python fundamentals", "SQL", "FastAPI", "PostgreSQL integration", "REST API project", "Docker"),
    ),
    Skill("Flask", ("flask",), "Build a small Flask route with input validation and tests."),
    Skill("Django", ("django",), "Build a small Django feature and test its model and request behavior."),
    Skill("REST APIs", ("rest api", "rest apis", "restful api", "restful apis"), "Design and test a small REST endpoint with clear validation and error responses."),
    Skill("Git", ("git", "version control"), "Practice branching, commits, merges, and resolving a simple conflict."),
    Skill("Docker", ("docker", "containerization", "containers"), "Package a small application in a Docker image and run it locally."),
    Skill("Kubernetes", ("kubernetes", "k8s"), "Complete a local deployment exercise and inspect service and pod behavior."),
    Skill("AWS", ("aws", "amazon web services"), "Choose one AWS service relevant to the role and complete a small guided exercise."),
    Skill("Azure", ("azure", "microsoft azure"), "Choose one Azure service relevant to the role and complete a small guided exercise."),
    Skill("Google Cloud", ("google cloud", "gcp"), "Choose one Google Cloud service relevant to the role and complete a small guided exercise."),
    Skill("Linux", ("linux",), "Practice shell navigation, file permissions, processes, and basic scripting."),
    Skill("Excel", ("excel", "microsoft excel"), "Practice formulas, filters, and a small summary using sample data."),
    Skill("Data analysis", ("data analysis", "data analytics", "analytics"), "Analyze a small dataset and write down the question, method, and limitations."),
    Skill("Pandas", ("pandas",), "Load and clean a small dataset with Pandas, then explain each transformation."),
    Skill("NumPy", ("numpy",), "Use NumPy arrays for a small numerical task and check the result against a simple baseline."),
    Skill("Machine learning", ("machine learning", "ml"), "Train and evaluate a simple model on sample data, documenting the baseline and limitations."),
    Skill("Scikit-learn", ("scikit-learn", "sklearn", "scikit learn"), "Build a small Scikit-learn pipeline and evaluate it with an appropriate split."),
    Skill("TensorFlow", ("tensorflow", "tensor flow"), "Complete a small TensorFlow model exercise and record its evaluation method."),
    Skill("PyTorch", ("pytorch", "py torch"), "Build a small PyTorch training loop and verify it on a simple dataset."),
    Skill("Testing", ("testing", "unit testing", "software testing"), "Add unit tests for normal, boundary, and failure cases in a small feature."),
    Skill("Pytest", ("pytest", "py.test"), "Write Pytest tests for a function, including invalid input and edge cases."),
    Skill("Communication", ("communication", "written communication", "verbal communication"), "Prepare a concise example of explaining a decision to a different audience."),
    Skill("Teamwork", ("teamwork", "team work", "collaboration"), "Reflect on a team task and document your contribution and how you handled feedback."),
    Skill("Problem-solving", ("problem-solving", "problem solving"), "Work through a relevant problem and write down your approach, trade-offs, and result."),
    Skill("Project management", ("project management", "project planning"), "Plan a small deliverable with milestones, risks, and a brief status update."),
)


def _skill_pattern(alias):
    if alias == "js":
        return re.compile(
            r"(?<![a-z0-9.])js(?![a-z0-9.])",
            re.IGNORECASE,
        )
    return re.compile(
        rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])",
        re.IGNORECASE,
    )
    _JAVASCRIPT_CONTEXT_CUES = re.compile(
        r"\b(javascript|node(?:\.js)?|react|typescript|ecmascript|"
        r"front[\s-]?end|browser|web development|html|css)\b",
        re.IGNORECASE,
    )


def normalize_skill_name(value):
    normalized = re.sub(r"[\s_-]+", " ", value.strip().casefold())
    for skill in SKILLS:
        if normalized == skill.name.casefold() or any(
            normalized == re.sub(r"[\s_-]+", " ", alias.casefold())
            for alias in skill.aliases
        ):
            return skill.name
    return None


def _skill_matches(text, skill):
    candidates = {}
    for alias in skill.aliases:
        for match in _skill_pattern(alias).finditer(text):
            if (
                skill.name == "JavaScript"
                and alias == "js"
                and not _JAVASCRIPT_CONTEXT_CUES.search(text)
            ):
                continue
            candidates[(match.start(), match.end())] = match
    ordered = sorted(candidates.values(), key=lambda match: (match.start(), -match.end()))
    matches = []
    for match in ordered:
        if matches and match.start() < matches[-1].end():
            continue
        matches.append(match)
    return matches


def _source_segments(text):
    return [
        segment.strip()
        for segment in re.split(r"[\r\n]+|(?<=[.!?])\s+", text)
        if segment.strip()
    ]


def _excerpt(text, match_start, match_end, limit=240):
    if len(text) <= limit:
        return text
    start = max(0, match_start - 90)
    end = min(len(text), max(match_end + 90, start + limit))
    if end - start > limit:
        end = start + limit
    excerpt = text[start:end].strip()
    if start:
        excerpt = "…" + excerpt
    if end < len(text):
        excerpt += "…"
    return excerpt


_CONTEXT_CUES = re.compile(
    r"\b("
    r"built|build|created|developed|implemented|designed|used|applied|"
    r"maintained|deployed|analyzed|analysed|tested|wrote|programmed|"
    r"integrated|automated|configured|managed|led|contributed|delivered|"
    r"supported|completed|coursework|course|certification|certified|"
    r"project|projects|experience|internship|employment|work"
    r")\b",
    re.IGNORECASE,
)
_JAVASCRIPT_CONTEXT_CUES = re.compile(
    r"\b(javascript|node(?:\.js)?|react|typescript|ecmascript|"
    r"front[\s-]?end|browser|web development|html|css)\b",
    re.IGNORECASE,
)


def analyze_skill_gaps(
    job_description, user_text="", resume_text="", experience_text="",
    project_evidence=(),
):
    user_sources = []
    if resume_text.strip():
        user_sources.append(("Résumé", resume_text))
    if user_text.strip():
        user_sources.append(("Skills you listed", user_text))
    if experience_text.strip():
        user_sources.append(("Experience you provided", experience_text))
    for project in project_evidence:
        if not isinstance(project, dict):
            continue
        title = project.get("title")
        title = title.strip() if isinstance(title, str) else "Untitled project"
        for field, label in (
            ("description", "description"),
            ("contribution", "contribution"),
        ):
            text = project.get(field)
            if isinstance(text, str) and text.strip():
                user_sources.append((
                    f"Portfolio project: {title} ({label}; self-reported)",
                    text.strip(),
                ))
        skills = project.get("skills")
        if isinstance(skills, list):
            listed_skills = [
                skill.strip()
                for skill in skills
                if isinstance(skill, str) and skill.strip()
            ]
            if listed_skills:
                user_sources.append((
                    f"Skills listed for portfolio project: {title} "
                    "(self-reported, not independently verified)",
                    ", ".join(listed_skills),
                ))

    requirements = []
    for skill in SKILLS:
        requirement_matches = _skill_matches(job_description, skill)
        if not requirement_matches:
            continue

        evidence = []
        mentions = []
        contextual_evidence_found = False
        for source_name, source_text in user_sources:
            for segment in _source_segments(source_text):
                matches = _skill_matches(segment, skill)
                if not matches:
                    continue
                mentions.append((source_name, segment, matches[0]))
                if _CONTEXT_CUES.search(segment):
                    contextual_evidence_found = True
                    evidence.append({
                        "source": source_name,
                        "excerpt": _excerpt(segment, matches[0].start(), matches[0].end()),
                    })

        if contextual_evidence_found:
            status = "Demonstrated"
            explanation = (
                "The supplied text connects this skill to an activity. This is "
                "self-reported context, not an independent verification of proficiency."
            )
            next_action = (
                "Review the cited example and add a truthful outcome or artifact "
                "that makes your contribution clear."
            )
        elif mentions:
            status = "Needs assessment"
            source_name, segment, match = mentions[0]
            evidence.append({
                "source": source_name,
                "excerpt": _excerpt(segment, match.start(), match.end()),
            })
            explanation = (
                "The skill is mentioned, but the supplied text does not describe "
                "how you used or practiced it. A short exercise or concrete example "
                "would help clarify your experience."
            )
            next_action = (
                "Complete a focused exercise or assessment, then add a specific "
                "project, course, or work example if it reflects your experience."
            )
        else:
            status = "No evidence found"
            explanation = (
                "No mention was found in the profile, portfolio, résumé, or "
                "experience text supplied for this analysis. This does not mean "
                "you lack the skill."
            )
            next_action = skill.next_action

        requirement_segment = next(
            (
                segment for segment in _source_segments(job_description)
                if _skill_matches(segment, skill)
            ),
            job_description,
        )
        segment_matches = _skill_matches(requirement_segment, skill)
        requirements.append({
            "name": skill.name,
            "required": True,
            "requirement_mentions": len(requirement_matches),
            "requirement_excerpt": _excerpt(
                requirement_segment,
                segment_matches[0].start(),
                segment_matches[0].end(),
            ),
            "status": status,
            "evidence": evidence,
            "explanation": explanation,
            "gap_explanation": (
                "Contextual evidence was found; review whether it represents the "
                "level the role expects."
                if status == "Demonstrated"
                else (
                    "The skill is listed, but evidence of using it is not clear yet."
                    if status == "Needs assessment"
                    else "Evidence is not present in the supplied text; investigate before drawing conclusions."
                )
            ),
            "next_action": next_action,
            "learning_sequence": list(skill.learning_sequence),
        })

    requirements.sort(key=lambda item: (-item["requirement_mentions"], item["name"]))
    demonstrated = sum(item["status"] == "Demonstrated" for item in requirements)
    needs_assessment = sum(item["status"] == "Needs assessment" for item in requirements)
    no_evidence = sum(item["status"] == "No evidence found" for item in requirements)
    priorities = [
        item["name"]
        for item in requirements
        if item["status"] != "Demonstrated"
    ][:3]

    return {
        "skills": requirements,
        "summary": {
            "total_required_skills": len(requirements),
            "skills_with_supporting_evidence": demonstrated,
            "needs_assessment": needs_assessment,
            "no_evidence_found": no_evidence,
            "priority_skills": priorities,
        },
        "note": (
            "This deterministic analysis recognizes a limited built-in skill "
            "vocabulary. It uses text mentions and context only; it does not verify "
            "proficiency, establish that an unmentioned skill is absent, or predict "
            "hiring outcomes. Résumé and experience text are processed for this "
            "request and are not saved by CareerLens."
        ),
    }
