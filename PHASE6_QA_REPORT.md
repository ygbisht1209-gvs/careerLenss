# CareerLens Phase 6 QA and Security Report

## Scope and architecture

CareerLens is a Flask application with a browser-based JavaScript workspace.
Supabase Auth issues bearer tokens; the browser uses the public anon key for
direct, user-scoped table and private-storage operations. Flask verifies bearer
tokens with Supabase Auth and uses the same user token for its REST requests.
Gemini requests are opt-in, server-side, and send `store: false`.

Implemented workflows observed in the repository include job seeker and
provider workspaces, job listings and applications, private résumé attachments,
manual application tracking, profile and portfolio editing, ATS keyword
comparison, skill-gap analysis, explainable job matching, a learning catalogue
and plan, interview preparation, AI assistance, and provider applicant notes.
This assessment verifies code paths and automated tests, not a live deployment.

## Baseline

Before the Phase 6 code changes:

- Python unittest suite: **71 tests passed**.
- Node UI tests: **9 tests passed**.
- JavaScript syntax checks and `git diff --check` passed.
- The worktree already contained uncommitted changes from prior phases. Those
  changes were preserved.
- Supabase and Gemini behavior in automated tests is mocked. No live database,
  storage, authentication-provider, or Gemini integration test was run.

## Security findings and actions

| Severity | Finding | Status |
|---|---|---|
| Medium | `/api/ai-assist` authenticated users could directly request employer-specific job-description and interview-kit tasks; the route did not enforce provider role. | Fixed: the two employer tasks now require a server-side Supabase provider-role check. Regression tests cover denied seekers, role RPC behavior, and allowed providers. |
| Potential | Employer accounts are self-selected during signup; there is no organization or employer identity verification. | Not treated as a code vulnerability; consider verification before a public launch. |
| Potential | No application-level rate limiting was found for Gemini requests, resume parsing, or other authenticated endpoints. | No rate limiter added: a process-local implementation would be unreliable across workers, and no deployment topology or rate data was available. Apply limits at a suitable deployment boundary before public exposure. |
| Potential | Stored PDFs are private and storage policies scope access to the applicant and listing provider. Upload checks include size, PDF MIME metadata, and a PDF signature in the browser; this does not scan or sanitize document contents. | No antivirus claim is made. Continue treating uploaded documents as untrusted and consider managed malware scanning before public use. |

The reviewed SQL enables RLS for profiles, applications, listings, learning
plans, portfolio projects, provider reviews, and account types. Resume storage
is configured as private, with access checked against an application and the
applicant's storage folder. The browser uses user-scoped tokens rather than a
service-role key. Direct DOM rendering primarily uses `textContent`; dynamic
HTML assignments found in the application list are static empty-state markup.
No confirmed SQL injection, cross-site scripting, or bearer-token logging issue
was found in the inspected paths.

These are source-level findings, not proof of deployed policy behavior. Static
SQL regression checks cannot replace testing the policies with separate
real-world Supabase accounts and storage objects.

## Validation and tests

Automated coverage uses Python `unittest` and Node's built-in test runner.
External services are mocked where used. New tests exercise the employer-task
authorization fix, core RLS policy text invariants, and a synthetic
recommendation evaluation. Python tests do not establish that deployed Supabase
policies, storage configuration, or Gemini credentials are correct.

### Reproducible synthetic evaluation

The evaluation fixtures in `tests/test_recommendation_evaluation.py` are
hand-authored synthetic cases, not real job listings, catalogue records, users,
or an independently annotated dataset.

- **Job skill extraction:** six job-description/requirements examples with
  required, preferred, unspecified, alias, and no-invented-skill cases.
  Micro counts are TP=11, FP=0, FN=0 over unique `(skill, category)` pairs;
  precision=1.00, recall=1.00, F1=1.00.
- **Learning retrieval:** three skills with explicit need statuses and four
  synthetic catalogue resources. Counts are TP=4, FP=0, FN=0 over expected
  `(resource ID, matched skill)` pairs; precision=1.00, recall=1.00, F1=1.00.

Metrics use standard set-based micro precision, recall, and F1:
`TP/(TP+FP)`, `TP/(TP+FN)`, and `2PR/(P+R)`. Empty-denominator values are
defined as 1.0 for these fixtures. These perfect fixture scores only confirm
that these known examples behave as expected; they are not estimates of
real-world accuracy or evidence of improved hiring outcomes. Resource URL
reachability and real catalogue quality were not evaluated.

The synthetic cases exposed a `js` alias false positive inside `Node.js`; the
alias boundary was tightened and a regression test added.

## Final verification

- Python unittest suite: **77 tests passed**.
- Node UI tests: **9 tests passed**.
- JavaScript syntax checks for the app and UI helpers passed.
- Python bytecode compilation and `git diff --check` passed.
- A local Flask startup smoke test returned HTTP 200 for `GET /`.
- `backend/.env` is ignored and not tracked. No secret values were read or
  added to source files.

## Performance and reliability

No performance optimization was made: no production workload, timings, or
representative data volume was available to justify one. Job recommendations
currently process the returned published-job collection in memory, and several
dashboard data reads are separate requests. Pagination or request consolidation
may help at scale but should be measured against realistic data first. No
cross-user cache was introduced.

The automated suite exercises validation and error paths for uploads, AI,
learning, portfolio, and recommendation APIs. Optional service failures are
surfaced. The application has no automated browser end-to-end suite, and no
manual browser workflow was performed for this phase.

## Technical and research summary

- **Problem:** organize job-search workflows and provide transparent, user-
  reviewable evidence comparisons and learning suggestions.
- **Matching:** deterministic skill-vocabulary extraction; explicit required
  and preferred categories; contextual user text, profile and portfolio
  evidence; disclosed limitations and no-score cases for insufficient data.
- **Skill-gap analysis:** compares recognized job skills to supplied text;
  distinguishes contextual self-reported evidence, bare mentions, and no
  evidence. “No evidence” is not a claim that the person lacks a skill.
- **Learning recommendations:** canonicalizes a small set of skill aliases and
  matches needs marked “Needs assessment” or “No evidence found” to catalogue
  skill tags. A course or completion status is not proof of proficiency.
- **Privacy controls:** bearer authentication, role checks for protected Flask
  APIs, owner/role RLS, a private résumé bucket, and server-side Gemini API key.
- **Limitations:** fixed skill vocabulary; heuristic language classification;
  self-reported profile, project, and course data; no validated outcome dataset,
  external-link uptime check, independent security assessment, or production
  load test. No scientific novelty or employment prediction is claimed.
- **Future work:** validate with a consented, independently labeled dataset;
  measure extraction and recommendation quality across roles; add pagination
  based on measured usage; and verify employer identity and upload safety for a
  public deployment.

## Database changes and demonstration checklist

No new Phase 6 database migration is proposed or executed. The existing Phase 5
portfolio and Phase 3 learning migrations remain manual operations. Before a
demonstration, review and run (in order) `backend/supabase_schema.sql`,
`backend/migrations/phase3_learning.sql`, and
`backend/migrations/phase5_portfolio.sql` in the intended Supabase project's SQL
Editor; confirm success and test with separate job-seeker and provider
accounts. Never use a service-role key in the browser.

For a final demonstration, verify: account sign-in and sign-out; role separation;
owner-only profile, application, learning-plan and portfolio access; private
résumé access for the applicant and the correct listing provider; application
submission and status updates; empty and unavailable-service states; matching
explanations and learning links; and Gemini consent and graceful failure with
the server key absent or provider unavailable. No claim is made that these
live-service checks have already been performed.
