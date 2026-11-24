# CareerLens Testing Summary

**Execution date:** 2026-11-24
**Environment:** Windows, Python 3.12.2, Node.js v23.11.0

## Automated checks

| Command | Result |
|---|---|
| `python -m unittest discover -s tests -v` | 136 tests passed, including response-metric checks and structured rejection validation, ownership, note sharing, and privacy contracts |
| `node --test tests/test_dashboard_ui.cjs tests/test_learning_ui.cjs` | 10 tests passed |
| `node --check backend/static/script.js` | Passed |
| `node --check backend/static/dashboard-ui.js` | Passed |
| `node --check backend/static/learning-ui.js` | Passed |
| `python -m py_compile backend/app.py tests/test_app.py` | Passed |
| Pylance syntax checks for `backend/app.py` and `tests/test_app.py` | No syntax errors |
| Local Flask HTTP smoke test: `GET /`, `GET /api/config` | Both returned HTTP 200 |
| `python -m pip check` | Environment warning: installed `httpcore 1.0.5` requires `h11<0.15`, but `h11 0.16.0` is present. Neither package is pinned in this project's `requirements.txt`. |

Python tests use `unittest`, Flask's test client, generated PDF fixtures, and
mocked Supabase/Gemini calls. Coverage includes input and role validation,
provider-only routes, recommendation and skill-gap logic, safe error responses
and logging, Gemini caps, and SQL policy contracts. Node tests cover dashboard
and learning summary helpers. Résumé-version tests inspect that seeker access
is owner-scoped, provider access requires the version to be selected on an
application for a provider-owned listing, and applications cannot mismatch the
selected version and its storage path. Notification tests verify every
application stage produces an event and interview calendar downloads are
authenticated and limited to applications visible through RLS. Interview-slot
tests inspect seeker/provider ownership policies, conflict locking and overlap
checks, route role validation, empty lists, booking, cancellation, and safe
conflict responses. These migration contract checks do not execute SQL.
STAR story tests cover seeker-only CRUD, text and tag bounds, empty results,
missing rows, owner omission from writes, and RLS policy source conditions.
Interview Prep adds saved stories only to browser-side answer notes; this
workflow does not submit them to Gemini.
Response transparency tests cover seeker/provider authorization, the five-
application threshold, zero applications, mocked odd/even median results,
rejection-stage SQL inclusion, provider ownership, and aggregate-only route
payloads. SQL contract tests assert PostgreSQL's `percentile_cont(0.5)` median
calculation; the migration was not executed against a live database.
Structured rejection tests cover missing and invalid reasons, the 500-character
note limit, atomic provider status updates, non-owner denial, clearing
rejection details on a later stage, seeker-only owner-scoped reads, and
unshared-note redaction. Source-contract checks verify that the Phase 27
security-definer read returns only rejection details and related listing text,
without applicant identities or reviewer notes; the migration was not executed
against PostgreSQL.
Synthetic recommendation examples are authored fixtures, not an independent
or representative accuracy evaluation.

## Security and integration boundaries

The SQL tests assert policy source conditions for user-owned profiles,
applications, projects, learning plans, bookmarks, STAR stories, notifications,
status history, and application materials, and confirm applicant-facing routes
do not expose provider review notes. They inspect SQL text only: they do not
execute SQL or prove that a deployed Supabase project has the expected grants,
policies, migrations, or Storage settings. No live Supabase, Gemini, or
deployed-site request was made as part of these automated tests.

The Flask tests verify bearer-token forwarding and route role checks with
mocks. Gemini tests verify consent, request limiting, bounded input/output,
and sanitized failures without calling Google. No browser-level workflow,
responsive layout, load test, accessibility audit, or vulnerability scan was
performed.

## Manual QA before demonstration

Use an isolated, non-production Supabase project and synthetic records. Follow
the [manual demonstration QA checklist](../README.md#manual-demonstration-qa-checklist)
for both job-seeker and provider accounts. In particular, test two accounts of
each type against profile, project, learning-plan, bookmark, application,
STAR story, listing, reviewer-note, and résumé visibility. Live cross-account
RLS and Storage behavior remains unverified until those checks are run against
the configured Supabase project.
