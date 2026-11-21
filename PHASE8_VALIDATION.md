# CareerLens Phase 8 Validation

**Validation date:** 2026-11-02
**Scope:** Local source, Python/Node tests, static SQL policy review, and local
WSGI startup. No Supabase project, Gemini API, or deployed site was contacted.

## Feature inventory

| Category | Findings |
|---|---|
| Implemented and locally verified | PDF keyword analysis; skill-gap extraction and evidence explanations; deterministic interview-prep generation; deterministic job matching; learning recommendation logic; learning and portfolio Flask API validation/error mapping using mocked Supabase responses; dashboard and learning UI summary helpers. |
| Implemented but not externally verified | Supabase email/password auth, password reset and email verification; profile and manual-application storage; seeker/provider workspaces; provider listing and applicant management; private résumé upload and access; live learning-plan and portfolio CRUD; dashboard data loaded from Supabase; Gemini-backed assistance. Source, API contracts, and relevant RLS policies were reviewed, but real accounts/services were not exercised. |
| Partially implemented | Résumé functionality supports transient PDF analysis and résumé upload with job applications; it does not create or edit résumé documents. Learning resources are administrator-managed in Supabase SQL; there is no in-app catalogue administration UI. |
| Broken | No reproducible broken behavior was found in the inspected source or executed automated tests. This is not a claim that every end-to-end workflow works. |
| Not implemented | Automated browser end-to-end and responsive-viewport tests are not present in the repository. No résumé authoring tool or in-app learning-catalogue editor was found. |
| Blocked by external services | Live Supabase authentication, database/RLS, storage/privacy, redirects, and Gemini behavior; verification on a deployed site. No test accounts or live-service checks were used in this run. |

The README feature descriptions are not treated as integration-test evidence.
Python tests invoke Flask routes with mocked network calls; static SQL tests
check policy text and do not execute PostgreSQL policies.

## Requirements-based test matrix

`PASS` here means the named local automated test passed. Rows marked as mocked
or static do not imply a live integration test. `BLOCKED` means the workflow
requires an external service/test account that was not exercised. `NOT RUN`
means no browser/manual test was performed.

| Test ID | Feature | Preconditions | Action / input | Expected result | Actual result | Status |
|---|---|---|---|---|---|---|
| AUTH-01 | Valid login and logout | Dedicated Supabase test account | Sign in, open workspace, sign out, then try a protected API | Workspace opens; session ends; API denies access | No live auth session/browser test performed | BLOCKED |
| AUTH-02 | Invalid login | Supabase test project | Submit invalid credentials | Safe auth failure; no workspace | No live auth test performed | BLOCKED |
| AUTH-03 | Unauthenticated APIs | Flask test client | Call resume, skill-gap, recommendations, and interview APIs without bearer token | Return 401 without data access | Auth-gating tests passed in Flask client | PASS |
| AUTH-04 | Role-specific API access | Mocked Supabase auth/RPC | Call seeker-only and employer-only endpoints as the wrong role | Return 403 and do not call protected data provider | Role-gating tests passed with mocked RPCs | PASS |
| AUTH-05 | Session after sign-out | Dedicated Supabase test account | Sign out and reuse the prior session against APIs | Requests denied; user data cleared from the workspace | Not exercised in a browser/live service | BLOCKED |
| SEEK-01 | Profile create/update/read | Seeker account and Supabase schema | Save profile fields, reload, and compare stored values | Profile persists only for that user | Browser/database flow not tested | BLOCKED |
| SEEK-02 | Résumé analysis validation | Flask test client; synthetic PDF fixture | Submit valid, missing, wrong-type, oversized, unreadable, and empty PDF inputs | Valid text is analyzed; invalid inputs receive safe 4xx responses | PDF parsing and validation tests passed locally | PASS |
| SEEK-03 | Skill-gap analysis | Mocked role RPC; synthetic PDF | Submit role description with profile/experience/resume evidence and empty evidence | Explainable evidence categories and validation errors | Skill-gap API and extraction tests passed locally | PASS |
| SEEK-04 | Learning catalogue and plan APIs | Mocked authenticated Supabase proxy | Read catalogue/plan, add/update/delete a plan, submit invalid IDs/fields | Valid payloads are forwarded; invalid input rejected; upstream errors sanitized | API contract and recommendation tests passed with mocks | PASS |
| SEEK-05 | Learning-plan ownership | Two Supabase users and Phase 3 migration | Attempt cross-user read/update/delete | RLS permits only owner access | Static policy contract passes; actual RLS not executed | BLOCKED |
| SEEK-06 | Job-board search/filter | Seeker account, real listings, browser | Search, filter, sort, refresh | Listing results/filter state behave as intended | No browser scenario run | NOT RUN |
| SEEK-07 | Explainable matching | Synthetic jobs/profile/project/learning fixtures | Calculate scores and inspect required/preferred evidence | Deterministic score and explanations; no unsupported mastery claim | Job matching and synthetic evaluation tests passed | PASS |
| SEEK-08 | Submit application and track status | Two test accounts, published listing, private bucket | Apply with test PDF; view seeker status and provider view | One application persists; allowed parties see their own data | No live database/storage workflow run | BLOCKED |
| SEEK-09 | Private résumé access | Applicant/provider plus unrelated account | Upload, access as applicant/provider, then attempt unrelated access | Bucket stays private; unrelated user is denied | Static storage policy assertions passed; no live storage request | BLOCKED |
| SEEK-10 | Portfolio create/edit/delete | Seeker account and Phase 5 migration | Create, edit, delete project; attempt malformed ID/URL/owner field | Validation is enforced; RLS scopes records to owner | Mocked Flask CRUD/validation tests and static RLS check passed; no live DB test | PASS (mocked/static) |
| SEEK-11 | Dashboard aggregation | Synthetic dashboard records | Summarize profiles, applications, learning, projects, recommendations | Totals reflect passed records and distinguish application sources | Node dashboard helper tests passed with fixtures | PASS |
| SEEK-12 | Dashboard live-data consistency | Supabase records across features | Change source records, reload dashboard, compare totals | Counts match persisted records | No live/browser test | BLOCKED |
| SEEK-13 | Profile skills into skill analysis | Seeker account/profile | Run analysis using supported profile inputs and project evidence | Only supplied evidence contributes and is explained | Synthetic skill-gap evidence tests passed; not a live profile-to-UI journey | PASS (logic) |
| SEEK-14 | Skill analysis to learning resources | Catalogue fixture and analyzed skills | Recommend against skill tags | Only matching skills needing investigation are recommended | Learning logic and mocked API test passed | PASS (mocked) |
| SEEK-15 | Portfolio evidence in matching | Profile/project/job fixtures | Match project descriptions and project skill tags | Context may support evidence; tags alone do not prove mastery | Job-matching tests passed | PASS |
| EMP-01 | Employer workspace and listing CRUD | Provider account and Supabase schema | Create/edit/publish/close a listing | Provider sees and changes only own listing | Browser and live DB behavior not exercised | BLOCKED |
| EMP-02 | Applicants and status changes | Provider/applicant test accounts | View applicants and update a status | Owning provider can manage the listing’s applications | Browser and live DB behavior not exercised | BLOCKED |
| EMP-03 | Other-employer data isolation | Two providers and Supabase schema | Query/update another provider’s listing, applicant, and review | Access denied by RLS | Static ownership-policy assertions passed; live denial not tested | BLOCKED |
| EMP-04 | Employer-only Gemini tasks | Mocked role RPC/Gemini transport | Call employer tasks as seeker and provider | Seeker denied; provider permitted after validation | Flask authorization tests passed with mocks | PASS (mocked) |
| INT-01 | Gemini request/consent/errors | Mocked Gemini transport | Test consent, response, timeout, invalid JSON, provider error | Consent required; safe response/errors; no provider body leak | Flask Gemini tests passed with mocked transport; no real Gemini request | PASS (mocked) |
| ERR-01 | Database/network errors | Mocked Supabase transport | Return timeout, invalid JSON, schema error, and provider error | Clear safe error; no provider details exposed | Error mapping tests passed with mocks | PASS (mocked) |
| ERR-02 | Empty dashboards/catalogues | Empty fixtures | Load empty record sets | Real empty state, not fabricated data | Flask and Node empty-state/helper tests passed | PASS |
| ERR-03 | Loading/success/failure messages | Browser interaction | Exercise submissions and service failures | User receives understandable status messages | Static source review only; no browser test | NOT RUN |
| UI-01 | Local sign-in page smoke test | Local Gunicorn server | Open `/` in the integrated browser | CareerLens title and sign-in controls render | Browser snapshot showed the expected title, sign-in form, and controls | PASS |
| UX-01 | Responsive desktop/mobile layout | Browser at common viewport sizes | Navigate major pages and dialogs at desktop/mobile widths | No clipped/overlapping controls; usable navigation | Viewport checks could not run because follow-up browser tools could not access the opened page handle | NOT RUN |

## Security review

- **Authentication and authorization:** Flask verifies Supabase bearer tokens for
  its authenticated APIs; seeker-only APIs verify the account role, and
  employer-only Gemini tasks have a server-side provider check. Browser button
  visibility is not the security boundary.
- **Database/storage isolation:** The reviewed SQL enables RLS for profiles,
  manual applications, account types, listings, job applications, provider
  reviews, learning plans, and portfolio rows. The résumé bucket is configured
  private, with policies relating access to the applicant and listing provider.
  These contracts were inspected and partly asserted by tests, not run against
  Supabase.
- **Validation and query construction:** Flask validates UUIDs, dates, URLs,
  payload fields, upload size/type, and text limits. Portfolio and plan API
  filters use validated UUIDs. No raw SQL execution was found in the Flask app;
  database access uses Supabase/PostgREST with the user bearer token.
- **XSS:** User-provided/displayed values are generally assigned with
  `textContent` or DOM nodes. The remaining `innerHTML` sites use fixed empty
  state markup and the locally computed integer résumé score. No exploitable
  user-content sink was identified in the inspected paths.
- **CSRF/CORS:** Flask data APIs use explicit bearer authorization rather than
  cookie-authenticated state changes; no permissive CORS configuration was
  found. Browser auth/storage behavior still needs live-origin verification.
- **Secrets/logging:** `.env` is ignored and no secret-like path is tracked.
  The Supabase public key is exposed to the browser as intended; privileged
  service-role keys must not be used. Gemini prompts are sent only after
  explicit consent. Error responses are sanitized in tested paths.
- **Session cookies/debug:** Flask does not use a server-side login session;
  Supabase handles browser auth. Gunicorn imports the Flask app without debug
  enabled. The direct-run Flask development entry point is for local use only.
- **Findings:** No confirmed security vulnerability or reproducible application
  bug was found in this validation pass. This does not certify external RLS,
  storage, dependency vulnerability status, or production configuration.

## Executed checks and results

| Command | Result |
|---|---|
| `./.venv/bin/python -m unittest discover -s tests -v` | **77 passed, 0 failed** |
| `node --test tests/*.cjs` | **9 passed, 0 failed** |
| `node --check backend/static/script.js` | Passed |
| `node --check backend/static/dashboard-ui.js` | Passed |
| `node --check backend/static/learning-ui.js` | Passed |
| `./.venv/bin/python -m py_compile backend/app.py backend/job_matching.py backend/learning.py backend/skill_gap.py` | Passed |
| `./.venv/bin/python -m pip check` | No broken requirements |
| `git diff --check` | Passed |
| Local Gunicorn on `127.0.0.1:5001`; GET `/`, `/api/config`, `/static/script.js` | All returned HTTP 200; process stopped after smoke test |

**Executed automated total:** 86 tests discovered across the Python and Node
runners; 86 passed, 0 failed. No tests were blocked within those runner
results. The Python suite prints expected exception logs from tests that
deliberately simulate provider timeouts and malformed responses; those tests
pass. There is no configured coverage runner, browser runner, or dependency
vulnerability scanner in this repository.

## Local setup and manual integration checks

From the repository root:

```bash
./.venv/bin/python -m pip install -r requirements.txt
if [ ! -e backend/.env ]; then cp backend/.env.example backend/.env; fi
# Replace placeholders locally; never commit backend/.env.
./.venv/bin/python -m flask --app backend/app.py run --host 127.0.0.1 --port 5000
```

The required variables are `SUPABASE_URL` and `SUPABASE_ANON_KEY`. Optional
Gemini variables are `GEMINI_API_KEY` and `GEMINI_MODEL`. Configure only the
public anon/publishable Supabase key in this app; never a service-role key.

For safe external checks, first use a separate Supabase project with no real
user data. Apply `backend/supabase_schema.sql`, then
`backend/migrations/phase3_learning.sql` and
`backend/migrations/phase5_portfolio.sql` if testing those features. Create two
seeker accounts and two provider accounts with non-production test data. Verify
cross-user and cross-provider access is denied, résumé access is limited to the
applicant and listing provider, and sign-out invalidates the workspace session.
Use Gemini only with a test key and explicitly consented sample text. No SQL or
external data changes were performed for this report.

## Demonstration guide

1. **Overview:** CareerLens consolidates career planning, job discovery,
   applications, skill evidence, learning, and employer workflows. The stack is
   Flask/Python, HTML/CSS/JavaScript, Supabase Auth/PostgreSQL/Storage, and
   optional Gemini.
2. **Start:** Follow the local setup above. Confirm the Supabase Site URL and
   redirect allowlist include `http://127.0.0.1:5000` and
   `http://localhost:5000`.
3. **Seeker journey:** Sign in with a dedicated test seeker; show profile and
   application tracking; analyze a synthetic PDF and job description; explain
   the skill-evidence result; view recommendations and matching explanations;
   save a learning resource and a portfolio project; review dashboard totals.
4. **Employer journey:** Sign in with a separate provider; create/publish a
   non-production listing; review the test seeker’s application; update its
   stage and show provider-only notes if that schema is installed.
5. **Gemini:** If configured, make one explicitly consented request using
   synthetic text. Otherwise show non-AI features and state that Gemini is
   optional.

Do not use real applicant résumés or personal data. If a live service fails,
show the documented safe error and explain that the local automated tests use
mocks; do not substitute fabricated listings or accounts.

## Limitations and next actions

- No real Supabase, Gemini, or deployed-site tests were performed; no browser
  screenshots or responsive viewport checks were produced.
- SQL tests are static contract assertions and do not prove PostgreSQL/RLS
  semantics at runtime.
- The learning catalogue has no in-app administration UI and must be curated
  manually.
- Full role, account-switching, storage, and application workflows require a
  safe isolated Supabase project and dedicated test accounts.
- Before a presentation, prioritize: (1) apply migrations in the test project,
  (2) verify auth redirects, (3) run seeker/provider isolation and résumé
  access checks, (4) test the browser journey on desktop and mobile widths,
  and (5) optionally test Gemini with synthetic content.

Then rerun:

```bash
./.venv/bin/python -m unittest discover -s tests -v
node --test tests/*.cjs
```
