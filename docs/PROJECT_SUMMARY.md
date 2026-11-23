# CareerLens Project Summary

## Overview

CareerLens is a B.Tech CSE minor-project prototype that combines selected
career-planning, job-search, application-tracking, and employer workflows in a
single web application.

## Problem statement

Career profiles, skill comparisons, learning plans, applications, and interview
preparation can be fragmented across separate workflows. CareerLens explores
how these records and tools can be presented together while keeping user data
scoped and explaining the limits of text-based analysis.

## Objectives

- Provide seeker and provider workspaces.
- Track personal applications, profiles, learning plans, and projects.
- Explain recognized skill evidence from profile and résumé context.
- Compare explicit job requirements with profile evidence.
- Support listings, applications, and employer review workflows.
- Offer optional, user-consented Gemini assistance.

## Implemented modules

- Supabase email/password authentication and role-specific UI
- Career profiles and personal application tracker
- Deterministic skill-gap analysis
- Curated learning catalogue and personal learning plans
- Explainable job matching and recommendations
- Provider listings, applications, and applicant review tools
- Private portfolio and dashboard summaries
- Deterministic interview-practice generation
- Optional Gemini career assistance

Résumé authoring and in-app catalogue administration are not implemented.
Live external-service behavior has not been validated.

## Technology stack

Python 3.12, Flask, HTML, CSS, JavaScript, Supabase Auth/PostgreSQL/Storage,
`pypdf`, and optional Google Gemini Interactions API.

## Verified testing status

The recorded local run executed 77 Python tests and 9 Node tests; all 86
passed. Syntax/compilation checks, dependency consistency, whitespace checks,
and a local Gunicorn HTTP smoke test passed. Supabase, Gemini, and deployed
flows were not tested live. Full details are in
[`TESTING_SUMMARY.md`](TESTING_SUMMARY.md).

## Known limitations

The recommendation and skill logic is deterministic and vocabulary-limited,
not a validated proficiency or hiring measure. Résumé analysis requires
readable PDF text and does not perform OCR. Learning catalogue content is
admin-curated in SQL. Live RLS/storage enforcement, browser end-to-end tests,
responsive/accessibility tests, load tests, and user evaluation remain
unverified.

## Future scope

Priorities include safe live integration tests, representative evaluation data,
broader accessibility and responsive checks, improved skill-vocabulary
coverage, catalogue administration, and measured performance evaluation.
These are proposed enhancements, not existing capabilities.

