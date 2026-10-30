import re


SKILL_AREAS = (
    (
        "Python",
        ("python", "pandas", "django", "flask"),
        "How would you structure a Python solution for a task in this role? Explain "
        "your design choices, error handling, and how you would test it.",
        "What would you change if the input size or failure rate increased?",
    ),
    (
        "SQL and databases",
        ("sql", "postgresql", "mysql", "database", "database design"),
        "Describe how you would investigate and improve a slow database query. "
        "Which measurements and indexes would you consider?",
        "How would you verify that the change improved performance without changing results?",
    ),
    (
        "JavaScript",
        ("javascript", "typescript", "node.js", "nodejs"),
        "How would you design a reliable JavaScript feature that remains responsive "
        "when requests fail or return slowly?",
        "How would you test loading, success, empty, and error states?",
    ),
    (
        "Frontend development",
        ("react", "html", "css", "accessibility", "responsive design"),
        "How would you build an accessible, responsive interface for the kind of "
        "users described in this role?",
        "How would you check keyboard use, small screens, and assistive technology?",
    ),
    (
        "APIs and backend",
        ("api", "rest", "flask", "django", "backend", "microservices"),
        "How would you design an API endpoint for a feature in this role, including "
        "validation, authorization, and useful error responses?",
        "How would you prevent duplicate work or protect data when requests are retried?",
    ),
    (
        "Cloud and DevOps",
        ("aws", "azure", "gcp", "cloud", "docker", "kubernetes", "ci/cd"),
        "Walk me through how you would deploy and monitor a change safely using the "
        "cloud or delivery tools mentioned in this role.",
        "What signals would tell you to roll back, and how would you do that?",
    ),
    (
        "Data analysis",
        ("data analysis", "analytics", "excel", "tableau", "power bi", "visualization"),
        "How would you turn an ambiguous data question into a trustworthy analysis "
        "and a clear recommendation?",
        "How would you check data quality and explain uncertainty to a stakeholder?",
    ),
    (
        "Machine learning",
        ("machine learning", "scikit-learn", "tensorflow", "pytorch", "model"),
        "How would you choose and evaluate a model for a problem in this role, and "
        "how would you check that it generalizes?",
        "What baseline, evaluation metric, and monitoring would you use?",
    ),
    (
        "Testing and quality",
        ("testing", "pytest", "unit tests", "integration tests", "quality assurance"),
        "How would you decide what to test for a change in this role, from unit "
        "behavior through integration?",
        "Which failure cases would you prioritize and why?",
    ),
    (
        "Security",
        ("security", "authentication", "authorization", "encryption", "privacy"),
        "What security and privacy risks would you look for when building a feature "
        "in this role?",
        "How would you validate authorization and avoid exposing sensitive data?",
    ),
    (
        "Project and stakeholder management",
        ("project management", "stakeholder", "roadmap", "agile", "scrum"),
        "How would you turn a broad stakeholder request into a scoped, deliverable "
        "plan while communicating trade-offs?",
        "What would you do if priorities changed after work had started?",
    ),
    (
        "Communication and collaboration",
        ("communication", "collaboration", "cross-functional", "teamwork"),
        "How do you make a complex decision understandable to teammates with "
        "different areas of expertise?",
        "Tell me about a time feedback changed your approach.",
    ),
)

BEHAVIORAL_QUESTIONS = (
    (
        "Tell me about a piece of work most relevant to this role. What was your "
        "specific contribution, and what changed because of it?",
        "What evidence or feedback supports the result?",
    ),
    (
        "Describe a time you had to learn an unfamiliar tool or subject to complete "
        "a task. How did you make progress?",
        "What would you do differently if you had to learn it again?",
    ),
    (
        "Tell me about a disagreement or difficult collaboration. How did you "
        "handle it and what was the outcome?",
        "What did you learn about working with that person or team?",
    ),
)

SCENARIO_QUESTIONS = (
    (
        "Imagine you join this role and receive an unclear request with a short "
        "deadline. How would you clarify the goal, prioritize, and communicate risk?",
        "What would you deliver first, and how would you confirm it meets the need?",
    ),
    (
        "A result from your work is challenged by a teammate or stakeholder. How "
        "would you investigate the concern and decide what to do next?",
        "How would you communicate if the evidence showed your original conclusion was wrong?",
    ),
)

PREPARATION_CHECKLIST = (
    "Choose two or three truthful examples and outline each with Situation, Task, "
    "Action, and Result.",
    "For every focus area, prepare one example of work you have done and one "
    "question you still want to ask.",
    "Review the role description and connect your experience to its stated "
    "responsibilities; do not claim skills you cannot demonstrate.",
    "Prepare concise questions about the team, success measures, and the role's "
    "first few months.",
    "Test your audio, camera, connection, and interview location before the meeting.",
)


def _count_phrase(text, phrase):
    pattern = rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])"
    return len(re.findall(pattern, text, flags=re.IGNORECASE))


def build_interview_prep(role, company, job_description):
    """Build a reproducible interview practice pack from user-provided role text."""
    normalized_description = job_description.casefold()
    focus_areas = []
    for label, aliases, prompt, follow_up in SKILL_AREAS:
        mentions = sum(_count_phrase(normalized_description, alias) for alias in aliases)
        if mentions:
            focus_areas.append({
                "name": label,
                "mentions": mentions,
                "question": prompt,
                "follow_up": follow_up,
            })
    focus_areas.sort(key=lambda item: (-item["mentions"], item["name"]))

    role_name = role.strip()
    company_name = company.strip()
    questions = []
    for area in focus_areas[:5]:
        questions.append({
            "category": "Role focus",
            "focus": area["name"],
            "question": area["question"],
            "follow_up": area["follow_up"],
        })
    for question, follow_up in BEHAVIORAL_QUESTIONS:
        questions.append({
            "category": "Behavioral",
            "focus": "Experience and reflection",
            "question": question,
            "follow_up": follow_up,
        })
    for question, follow_up in SCENARIO_QUESTIONS:
        questions.append({
            "category": "Situational",
            "focus": "Judgment and communication",
            "question": question,
            "follow_up": follow_up,
        })

    return {
        "role": role_name,
        "company": company_name,
        "focus_areas": [
            {"name": area["name"], "mentions": area["mentions"]}
            for area in focus_areas[:8]
        ],
        "questions": questions,
        "checklist": list(PREPARATION_CHECKLIST),
        "note": (
            "Practice prompts are generated from repeated terms in the job "
            "description. They are preparation ideas, not predictions of an "
            "employer's actual interview."
        ),
    }
