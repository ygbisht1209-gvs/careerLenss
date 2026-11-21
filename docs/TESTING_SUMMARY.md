# CareerLens Testing Summary

**Execution date:** 2026-11-02
**Environment:** Linux, Python 3.12.3, Node.js v24.15.0, repository virtual
environment `.venv`.

## Test commands and observed results

| Command | Observed result |
|---|---|
| `./.venv/bin/python -m unittest discover -s tests -v` | 77 tests ran; `OK`; 0 failures |
| `node --test tests/*.cjs` | 9 tests; 9 passed; 0 failed |
| `node --check backend/static/script.js` | Passed |
| `node --check backend/static/dashboard-ui.js` | Passed |
| `node --check backend/static/learning-ui.js` | Passed |
| `./.venv/bin/python -m py_compile backend/app.py backend/job_matching.py backend/learning.py backend/skill_gap.py` | Passed |
| `./.venv/bin/python -m pip check` | No broken requirements found |
| `git diff --check` | Passed |
| Local Gunicorn on port 5001; HTTP GET `/`, `/api/config`, `/static/script.js` | Each returned HTTP 200; local process stopped after smoke test |
| Integrated browser, local `GET /` | CareerLens title and sign-in controls appeared; no account was used |

**Automated total:** 86 tests discovered across the two test runners; 86 passed
and 0 failed. These totals count unit/API/helper tests, not end-to-end user
journeys.

## Test environment and coverage

Python tests are under `tests/test_*.py` and use `unittest`, Flask's test
client, generated PDF fixtures, and mocked Supabase/Gemini HTTP responses.
They cover role gating, input validation, resume parsing, skill-gap
classification, learning/project payload handling, recommendation behavior,
sanitized errors, and API response logic.

Node tests are `tests/test_dashboard_ui.cjs` and
`tests/test_learning_ui.cjs`; they verify dashboard/learning summary helper
logic with fixtures. `tests/test_recommendation_evaluation.py` contains
hand-authored synthetic examples. These examples do not constitute an
independent or representative evaluation dataset and must not be interpreted
as real-world accuracy.

`test_app.py` includes static SQL text checks for RLS policy contracts. Those
checks do not execute SQL or prove effective grants/policies in a deployed
Supabase database.

## Integration classification

| Area | Test type | Result / limitation |
|---|---|---|
| Flask request handling and validation | Local Flask test client | Passed as listed above |
| Supabase auth/database calls | Mocked HTTP / patched helpers | Contract behavior covered; no real project request |
| Supabase RLS and Storage | Static SQL assertion/source review | No runtime database or object access test |
| Gemini | Mocked HTTP responses | Consent and error handling exercised locally; no real model call |
| Browser rendering | Integrated-browser homepage snapshot | Sign-in title and controls appeared on local Gunicorn |
| Browser job seeker/provider workflow | Not run | Requires test accounts and live Supabase |
| Responsive viewport checks | Not run | No completed width/device checks |
| Deployed website | Not run | No deployment performed |

## Failures, warnings, and blocked checks

- **Automated failures:** 0.
- **Blocked external tests:** live Supabase Auth, database, RLS, Storage,
  redirects, Gemini API, and deployed-site verification require an isolated
  project, credentials, test accounts, or deployment access; none were used.
- **Not run:** cross-account browser flows, end-to-end job application path,
  dashboard/live data consistency, responsive layout, accessibility audit,
  load/performance testing, and dependency vulnerability scanning.
- **Known test output:** Python tests deliberately simulate provider timeouts
  and malformed responses; those cases emit expected exception logs while the
  corresponding tests pass.

## Security checks performed

- Reviewed server-side bearer-token and role checks in `backend/app.py`.
- Reviewed static RLS and Storage policies in the base schema and migrations.
- Verified tests assert selected ownership/role policy fragments.
- Inspected user-content rendering patterns; displayed user content is
  predominantly inserted via DOM text APIs.
- Confirmed `.env` is ignored and no secret-like path is tracked in the Git
  index at the inspection.

These are repository-local checks, not a penetration test or a certification
of live Supabase security.

## Recommended manual verification

Use an isolated Supabase project with no real user data:

1. Review and apply `backend/supabase_schema.sql`.
2. Apply `backend/migrations/phase3_learning.sql` and
   `backend/migrations/phase5_portfolio.sql` if testing those modules.
3. Configure local Site URL and allowed redirect URLs.
4. Create two seeker accounts and two provider accounts with test-only data.
5. Verify cross-user profile, application, learning-plan, and portfolio access
   is denied.
6. Verify provider A cannot access provider B's listing/applicants/reviews.
7. Confirm résumé upload and download work for the applicant and listing
   provider while an unrelated user is denied.
8. Verify auth expiry/sign-out, refresh, and redirect flows in the browser.
9. Optionally test Gemini with synthetic content, a test key, and explicit
   user consent.
10. Capture screenshots only from actual test account sessions; remove
    personal data and tokens before including them in a report.
