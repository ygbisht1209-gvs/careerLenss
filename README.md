# CareerLens

CareerLens is a Flask career workspace. Supabase provides email/password
accounts, database access, and private cloud storage for application tracking
and career profiles.

## Architecture

The browser renders the Flask-served HTML, CSS, and JavaScript. Supabase handles
authentication, database access, and private résumé storage under Row Level
Security policies. Flask provides authenticated API endpoints and processes
uploaded résumé PDFs in memory. Optional Gemini requests are sent by Flask only
after the user opts in; the Gemini key is never sent to the browser. The app
does not require a local database or persistent application disk. Each Gemini
route is capped at five requests per minute per authenticated session in each
Flask process; only a keyed hash of the bearer token is kept in memory. The cap
is not shared across multiple workers or instances.

## Set up Supabase once

1. Create a Supabase project at <https://supabase.com>.
2. In **Project Settings → API**, copy the project URL and the public anon
   (publishable) key. Never put a `service_role` or secret key in this app.
3. In the Supabase **SQL Editor**, run the contents of
   [`backend/supabase_schema.sql`](backend/supabase_schema.sql). The tables use
   Row Level Security so each signed-in user can access only their own rows.
   The schema also creates private résumé storage and provider-only interview
   notes, restricts résumé paths to their applicant's storage folder, and lets
   applicants withdraw their own applications. Re-run the latest full schema
   when upgrading an existing project.
   If you already set up CareerLens, run the updated SQL file again to add the
   dual-user accounts, job listings, and applications tables, as well as any
   earlier application fields. The script is safe to rerun. Confirm the editor
   reports success before reloading the app.
4. In **Authentication → URL Configuration**, set the local Site URL to
   `http://127.0.0.1:5000` and add both of these redirect URLs:
   `http://127.0.0.1:5000` and `http://localhost:5000`.
5. To enable the Learning workspace, run
   [`backend/migrations/phase3_learning.sql`](backend/migrations/phase3_learning.sql)
   in the same project's Supabase SQL Editor after the base schema. This
   rerunnable migration creates an empty verified-resource catalogue and
   per-user learning plans; it does not add sample courses or modify existing
   user data. Do not execute it against production without reviewing it first.
6. To enable private saved-job bookmarks, run
   [`backend/migrations/phase18_saved_jobs.sql`](backend/migrations/phase18_saved_jobs.sql)
   in the same Supabase project. Row Level Security limits saved jobs to the
   signed-in job seeker who created each bookmark.
7. To enable applicant-visible status timelines, run
   [`backend/migrations/phase19_application_status_history.sql`](backend/migrations/phase19_application_status_history.sql)
   in the same Supabase project. RLS limits status history to its applicant.
   The migration records status transitions from the time it is installed;
   earlier transitions are not backfilled because their dates are unavailable.
8. Run
   [`backend/migrations/phase20_rejection_feedback.sql`](backend/migrations/phase20_rejection_feedback.sql)
   to create the rejection-feedback table used by the later structured
   rejection migration. Reviewer notes remain provider-private under separate
   RLS.
9. To optimize recorded application response-time queries, run
   [`backend/migrations/phase21_application_analytics.sql`](backend/migrations/phase21_application_analytics.sql)
   after Phase 19. It adds an index only; no data is seeded.
10. To enable private résumé version tracking, run
    [`backend/migrations/phase22_resume_versions.sql`](backend/migrations/phase22_resume_versions.sql)
    in the same project. Job seekers can reuse saved versions; providers can
    access only the version attached to their application.
11. To notify applicants about every recorded application-stage change and
    providers when an applicant withdraws, run
    [`backend/migrations/phase23_notification_calendar_enhancements.sql`](backend/migrations/phase23_notification_calendar_enhancements.sql)
    after Phase 16. Notifications remain owner-scoped by the existing RLS
    policies. Applicants and listing providers can download an interview date
    as a calendar file when the application and interview are visible to them.
12. To let providers offer 30-minute interview times and applicants book or
    cancel them, run
    [`backend/migrations/phase24_interview_slot_booking.sql`](backend/migrations/phase24_interview_slot_booking.sql)
    after Phases 16 and 23. Database locking prevents a provider from having
    overlapping booked slots, and only the applicant or listing provider can
    view or change the related booking.
13. To enable the private STAR Story Bank, run
    [`backend/migrations/phase25_star_story_bank.sql`](backend/migrations/phase25_star_story_bank.sql)
    in the same project. Job seekers can create, edit, and delete their own
    self-reported stories; row-level security denies other accounts and providers.
14. To enable employer response metrics, run
    [`backend/migrations/phase26_employer_response_transparency.sql`](backend/migrations/phase26_employer_response_transparency.sql)
    after the base schema and Phase 19 status-history migration. It exposes
    thresholded aggregate metrics and provider-scoped reads of stage events;
    status events are not backfilled or client-writable.
15. Phase 27 is also required for the structured rejection workflow described
    in step 8. Run
    [`backend/migrations/phase27_structured_rejection_feedback.sql`](backend/migrations/phase27_structured_rejection_feedback.sql)
    after the base schema and Phase 20. Providers must select one fixed
    rejection reason; notes are capped at 500 characters and are private unless
    explicitly shared. The Phase 27 RPC updates the stage and rejection
    details atomically, and applicant reads redact unshared notes. Migrations
    are manual; the app does not apply them automatically.

The learning catalogue is intentionally administrator-managed through the
Supabase SQL Editor. Add a category and resources only after verifying their
provider, description, skill tags, difficulty, and original HTTP(S) URL. The
application gives authenticated job seekers read access to active resources,
but no client-side role can add or edit catalogue entries. A saved item can
remain visible to its owner if an administrator later deactivates it. Add the
category to `learning_categories` first, then insert a resource into
`learning_resources` with that `category_slug`, its exact provider URL,
canonical `skill_tags`, learning `objectives`, and a verified difficulty and
resource type. Allowed difficulty values are `Beginner`, `Intermediate`,
`Advanced`, and `All levels`; allowed resource types are `course`,
`documentation`, `tutorial`, `practice`, `video`, and `other`. Keep resources
inactive until their details are checked. There is no in-app catalogue editor
or bundled course data in this phase; external link availability is managed by
the provider and catalogue administrator.

To add the initial curated catalogue, run
[`backend/migrations/phase12_verified_resources.sql`](backend/migrations/phase12_verified_resources.sql)
in the same Supabase project. The migration is rerunnable and inserts only
resources whose exact provider URL is not already present. Its resources cover
Python, JavaScript, HTML, CSS, React, Flask, SQL, PostgreSQL, Git, Docker,
Pytest, and Jest.
The catalogue also includes TypeScript, Node.js, Express, HTTP, Supabase,
HTML forms, CSS Grid, GitHub, Docker Compose, unittest, and Cypress material.
It now also includes Java, C++, Go, Rust, Vue.js, Angular, Next.js, Tailwind CSS,
MongoDB, Redis, GitHub Actions, Kubernetes, Linux, Playwright, and web security
testing material.
The catalogue also covers data structures and algorithms, system design, data
science, artificial intelligence, machine learning, deep learning, NLP, and
responsible AI. Resources span beginner practice through advanced architecture
and production concepts.
The seed remains rerunnable: existing URLs are not duplicated, so re-running
the migration will not create duplicate catalogue entries.

Retired Community tables can be removed with the review-only,
rerunnable [`backend/migrations/phase17_remove_community.sql`](backend/migrations/phase17_remove_community.sql).
Review this migration before running it manually in Supabase; CareerLens does
not execute migrations automatically.

If an existing Learning migration shows
`infinite recursion detected in policy for relation "user_learning_plans"`,
run [`backend/migrations/phase13_learning_policy_fix.sql`](backend/migrations/phase13_learning_policy_fix.sql)
once in the same Supabase project. It replaces the cross-dependent RLS policies
with security-definer helper functions.

## Private career dashboard and portfolio

Click the signed-in account card at the bottom of the sidebar to open **My
Profile**, where you can edit your name, current and target roles, headline,
About section, skills, education, location, contact phone, and private projects. Career details are private to
the account.
After the base schema, run
[`backend/migrations/phase10_my_profile.sql`](backend/migrations/phase10_my_profile.sql)
in Supabase to add the profile fields. Run
it in the same Supabase project configured by `backend/.env`; it reloads the
PostgREST schema cache after adding the fields.
For employer accounts, run
[`backend/migrations/phase11_employer_profile.sql`](backend/migrations/phase11_employer_profile.sql)
to enable the Employer Profile page and show recruiters' names and job titles
on published listings. Account email and phone remain private.

After running the base schema, run
[`backend/migrations/phase5_portfolio.sql`](backend/migrations/phase5_portfolio.sql)
in the same project's Supabase SQL Editor to enable private project records.
This rerunnable migration creates no sample data and does not publish projects.
Row Level Security restricts project read/write access to the owning job seeker.
The dashboard portfolio form supports project descriptions, user-described
contributions, user-listed skills, optional HTTP(S) links, and optional dates.
Project tags are self-reported and are not treated as verified proficiency.

The dashboard's profile completeness is the percentage of these five fields
present: target role, headline, a meaningful About section of at least 20
characters, at least one meaningful saved skill, and at least one portfolio
project. Application totals preserve the distinction between the personal
manual tracker and CareerLens submissions; private résumé attachments are
counted only from the user's own CareerLens submissions, without exposing
storage paths. Learning completion remains self-reported. Recommendations and
skill analysis may cite project descriptions and contributions as user-entered
context; skills entered only as project tags remain unverified mentions.

## Explainable job recommendations

The job seeker **Find jobs** page sorts published CareerLens listings by a
deterministic profile-to-job evidence alignment. The feature uses
`job_listings`, the signed-in user's existing `career_profiles` row, and (when
the migrations are installed) that user's private portfolio and learning-plan
records through the authenticated Flask API and existing Supabase row-level
security. Until the Phase 5 migration is installed, portfolio evidence is
omitted and the dashboard displays a setup message. It does not read application
résumés, employer notes, or other users' profiles.

Skills in the listing's structured `requirements` field are treated as required
unless the wording explicitly marks them preferred. Skills in the description
are scored only when the listing explicitly marks them required or preferred;
other recognized mentions are disclosed separately and excluded. Extraction
uses the built-in skill vocabulary and does not invent requirements. The score
weights required skills at 80% and preferred skills at 20% when both groups
exist; otherwise the available group uses the full weight. Contextual profile
evidence counts as 100%, a listed skill or relevant learning-plan record without
supporting context as 35%, and no found evidence as 0%. A course record never
establishes proficiency. The score is a transparent text-alignment indicator,
not an empirically validated measure, competence assessment, official ATS
score, or hiring probability. An empty evidence profile or a listing without
recognized explicit requirements has no score.

Open **Why this job is recommended** on a job card to review the skill
classifications, profile evidence, limitations, and next steps. Learning
suggestions use the existing verified catalogue and can be added to the
existing personal learning plan. Job type filtering, free-text search, both
sort options, and the existing apply/application tracking flow remain
available. Job seekers can test the feature by signing in, saving truthful
skills in **Skill Gap Analysis**, then entering a target role, headline, and
truthful project/work context in **My Profile**. Return to **Find jobs** to
review the updated results. Real listings must already exist in Supabase; the
application does not add sample jobs or learning resources.

## Phase 6 quality assurance

The security review, known limitations, automated test methodology, synthetic
recommendation evaluation, and final demonstration checklist are in
[`PHASE6_QA_REPORT.md`](PHASE6_QA_REPORT.md). Employer-specific Gemini tasks
are role-checked by Flask as well as being surfaced in the employer workspace;
frontend visibility is not an authorization boundary.

The Phase 8 feature inventory, requirements-based test matrix, security review,
executed validation results, and college demonstration guide are in
[`PHASE8_VALIDATION.md`](PHASE8_VALIDATION.md). Mocked tests are distinguished
from checks that still require real Supabase, Gemini, or browser access.

## Project documentation

- [Final Project Report](docs/CareerLens_Final_Project_Report.md)
- [Technical Documentation](docs/TECHNICAL_DOCUMENTATION.md)
- [API Documentation](docs/API_DOCUMENTATION.md)
- [Testing Summary](docs/TESTING_SUMMARY.md)
- [Project Summary](docs/PROJECT_SUMMARY.md)

## Run locally

From the repository root, install the packages, then create
`backend/.env` with your Supabase project's URL and public anon key:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```

Add these lines to `backend/.env`, replacing the example values:

```dotenv
SUPABASE_URL=https://YOUR_PROJECT_ID.supabase.co
SUPABASE_ANON_KEY=YOUR_PUBLIC_ANON_KEY
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
```

The Gemini key is optional for the rest of the app, but required for the
opt-in AI Assistant. Create or view it in
[Google AI Studio](https://aistudio.google.com/apikey).
Keep it in `backend/.env`; never add it to frontend code, commit it, or paste it
into chat. You can optionally set `GEMINI_MODEL` to a supported Gemini model;
the default is `gemini-3.6-flash`. Restart Flask after changing `.env`.

Then start Flask from the repository root:

```bash
./.venv/bin/python -m flask --app backend/app.py run --host 127.0.0.1 --port 5000
```

The app loads `backend/.env` automatically on startup, so you only need to
enter these values once. Keep this file local; do not commit it. Then open
<http://127.0.0.1:5000> and create an account. If email confirmation is enabled,
verify the message sent to your inbox before signing in. The server terminal
must remain open while you use the app and while opening email links that
redirect to localhost. If a verification link expires, return to CareerLens,
enter your email address, and use **Resend verification email**. For an expired
password-reset link, request a new one with **Forgot your password?**. To stop
the server, press **Ctrl+C** in its terminal.

Do not open `backend/templates/index.html` directly or use VS Code **Go Live**.
Live Server serves static files and does not run Flask or render its templates.

## Run with Docker

Build the image from the repository root, then start the container with the
local environment file. Docker passes these values into the container at run
time; the file is excluded from the image:

```bash
docker build -t careerlens .
docker run --rm --name careerlens -p 5000:5000 --env-file backend/.env careerlens
```

Open <http://127.0.0.1:5000>. To use a different container port, set `PORT`
and map the host port to that same container port. Keep `backend/.env` private.

## Run automated tests

From the repository root, run:

```bash
./.venv/bin/python -m unittest discover -s tests -v
```

The tests cover configuration, authentication gating, resume-upload validation,
PDF parsing, skill-gap and explainable job matching, learning recommendations,
provider-only routes, safe API errors, Gemini request caps, and mocked Gemini
behavior. SQL policy tests inspect source contracts only; the suite does not
contact Supabase or Gemini and does not prove live RLS isolation.
GitHub Actions runs the same tests and checks the frontend JavaScript syntax on
every push and pull request.

## Manual demonstration QA checklist

Use an isolated, non-production Supabase project, synthetic data, and two job
seeker accounts plus two job provider accounts. Apply the base schema and the
optional migrations for every feature under test before starting.

- **Authentication and roles:** create/sign in/out each account type; confirm
  job seekers cannot call provider endpoints and providers cannot use seeker-
  only endpoints.
- **Job seekers:** save profile details and a project; check profile
  completeness and application counts; browse jobs, test filters/sorting,
  bookmark a job, and verify only that account sees the bookmark. For a
  synthetic listing, verify response metrics appear on dashboard
  recommendations, listing cards, and the apply detail; they are withheld
  below five applications and shown at five or more.
- **Applications:** submit a harmless PDF (under 5 MB), review the status in the
  tracker, test sorting and overdue follow-up, and confirm delete asks first.
  Save a labeled résumé version, apply using it, then apply to another test job
  with a different version and confirm each provider can access only its
  selected version. Change application stages and confirm the applicant receives
  status notifications; download the interview calendar from the notification.
- **Interview booking:** offer several future times as a provider, book one as
  the applicant, verify an overlapping slot cannot be booked for another
  application with the same provider, and test cancellation from both accounts.
  Confirm both accounts receive the appropriate notification and calendar
  downloads stop working after cancellation.
- **Skills and learning:** analyze a synthetic job description, inspect all
  three evidence groups, add a suggested resource to the learning plan, and
  verify progress is labeled self-reported.
- **STAR stories and interview prep:** create, edit, and delete a private story;
  add it to an interview answer note and confirm the text stays in the browser
  and is not included in the Gemini request. Verify the empty bank state and
  confirm another seeker and a provider cannot read or modify the story.
- **Providers:** create a draft, publish/close it, duplicate it, and verify
  applicant counts. Search/filter applicants, change a stage, and set an
  interview date; download its calendar file and confirm the provider sees
  reviewer notes and the applicant does not. Reject a synthetic application
  with each fixed reason, confirm a reason is required, and save a note with
  sharing off and on. Verify the seeker always sees the reason, sees the note
  only when shared, and can open Skill Gap Analysis with role requirements and
  catalogue suggestions for a `skills_gap` rejection. Check the response
  aggregate on the provider dashboard using only its owned listings. Withdraw
  a test application as a seeker and confirm the provider is notified.
- **Cross-account isolation:** use seeker B and provider B to try accessing
  seeker A's profile, projects, plans, saved jobs, STAR stories, manual
  applications, and submitted interview slots; verify provider B cannot access
  provider A's listings, applicants, slots, reviews, or rejection notes. Use
  seeker B to verify an unshared rejection note from seeker A is not readable.
  Confirm saved résumé versions are private to their owner unless selected on
  an application, and each provider can access only the selected version for
  its own listing.
- **Optional AI:** only with a test key and explicit consent, submit synthetic
  text; verify normal workflows still work without Gemini and that rate-limit
  responses are clear.

These are manual checks to perform; repository tests do not establish that a
configured Supabase project enforces the policies correctly.

If the dashboard says Supabase cannot find `public.applications`, check that
the Supabase project open in the SQL Editor is the same project whose URL is in
`backend/.env`. Run the full schema file in that project's SQL Editor, wait for
a successful result, and then reload CareerLens.

If a job seeker sees submitted applications but the provider's Applicants page
is empty, run the latest full `backend/supabase_schema.sql` in the same
Supabase project. The updated row-level security policy lets providers view
applications only for listings they own. Confirm the SQL Editor reports
success, then reload both accounts.

## Deploy a project demonstration

CareerLens can run as one managed Python web service while continuing to use
Supabase for authentication, PostgreSQL, and storage. The instructions below
use [Render Web Services](https://render.com/docs/web-services); no Docker,
database migration, or extra service is required. Do not treat a successful
deployment as proof that the project is production-ready.

### Configure Render

1. Push the intended deployment commit to the GitHub `main` branch.
2. In Render, choose **New → Web Service**, connect this repository, and select
   `main` as the branch. The repository's `.python-version` pins the runtime to
   Python 3.12, matching the CI test environment.
3. Use **Python 3**, build command `pip install -r requirements.txt`, and start
   command `gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 60 backend.app:app`.
   Render supplies `PORT`; Gunicorn is the production server. Do not use
   `flask run` as the production start command.
4. Set the HTTP health-check path to `/api/config`. It confirms that the public
   Supabase configuration is present; it does not test Supabase connectivity.
5. In the service's environment settings, add:
   - `SUPABASE_URL` — required; the Supabase project URL.
   - `SUPABASE_ANON_KEY` — required; the public anon/publishable key only.
   - `GEMINI_API_KEY` — optional; required only for Gemini-powered features.
   - `GEMINI_MODEL` — optional; defaults to `gemini-3.6-flash`.

   Never configure a Supabase `service_role` or secret key in this application.
   `PORT` is provided by Render and should not be added manually. The
   placeholder-only [`backend/.env.example`](backend/.env.example) shows the
   local variable names; do not copy credentials into the repository.
6. In Supabase **Authentication → URL Configuration**, set **Site URL** to the
   deployed HTTPS origin and add that same origin to the redirect URL allowlist.
   Keep local redirect URLs too if local development will continue. Use the
   exact deployed origin, such as `https://your-service.onrender.com`.
7. In the Supabase SQL Editor, apply
   [`backend/supabase_schema.sql`](backend/supabase_schema.sql), then
   [`backend/migrations/phase3_learning.sql`](backend/migrations/phase3_learning.sql)
   , [`backend/migrations/phase5_portfolio.sql`](backend/migrations/phase5_portfolio.sql),
   and [`backend/migrations/phase15_application_materials.sql`](backend/migrations/phase15_application_materials.sql).
   Review and run SQL manually; deployments do not
   execute migrations. Confirm the private `application-resumes` bucket and
   policies remain enabled. Do not disable RLS or make the bucket public.
8. Create the service and review its **Deploys** and **Logs** pages. Subsequent
   pushes to the selected branch trigger deployments by default. Never include
   environment values, access tokens, or résumé contents in shared logs.

### Local production-startup smoke test

After installing the updated `requirements.txt`, test the production WSGI
command locally with placeholder or valid configuration. For example:

```bash
PORT=5001 ./.venv/bin/gunicorn --bind 127.0.0.1:5001 --workers 1 --timeout 60 backend.app:app
```

In another terminal, check `http://127.0.0.1:5001/` and
`http://127.0.0.1:5001/api/config`. This verifies local startup and static
response behavior only, not connectivity to Supabase or Gemini. Continue using
the Flask command in **Run locally** for development.

### Deployment and live-site verification

After deployment, use dedicated test accounts and non-production records:

- Confirm the home page and static assets load, and refresh a nested workspace.
- Sign in as a job seeker and as a provider; verify their workspaces and role
  permissions are distinct.
- Verify database-backed pages, job listing/application flows, and application
  tracking.
- Upload a harmless test PDF; verify the applicant can access it and an
  unrelated account cannot. Confirm the file is in the private Supabase bucket.
- Where migrations and catalogue data are present, verify learning plans,
  recommendations, dashboard, and portfolio behavior.
- If Gemini is configured, explicitly opt in to an AI request and verify the
  configured feature; otherwise confirm non-AI features still work.
- Check production logs and browser responses for errors without exposing
  credentials, stack traces, or private user data.

These are manual checks, not results already obtained. Local tests do not
substitute for a deployed-site test.

### Hosting limitations and cost

Render's free web-service instances are suitable for a student demonstration,
not production: they spin down after 15 minutes without traffic, may take about
a minute to wake, and have an ephemeral filesystem. CareerLens keeps résumés
and application data in Supabase rather than on that filesystem. Render
documents free-instance, bandwidth, and build-pipeline limits; review the
[current free-instance limitations](https://render.com/docs/free) and
[pricing](https://render.com/pricing) before choosing a plan. Paid usage and
overages may incur charges. No hosting resources have been created by this
project setup.

### Final-year demonstration sequence

Use seeded non-production listings and two test accounts. A short sequence:

1. Sign in as a job seeker; show the profile and run resume/skill-gap analysis
   with a sample PDF and role description.
2. Open **Find jobs**, explain one recommendation's evidence, and submit an
   application; show its status in the tracker.
3. Show a saved learning recommendation and a portfolio project on the
   dashboard.
4. Sign in as the provider; publish a sample role and review the test
   application, demonstrating that provider-only actions are account-scoped.
5. If Gemini is enabled, demonstrate one explicitly consented AI task; otherwise
   show the non-AI workflow and note that Gemini is optional.

Before presenting, verify both accounts, test records, private résumé access,
Supabase migrations, and the deployed redirect configuration. Use no real
applicant data.

## Features

- Supabase email/password sign-up, sign-in, email verification, password reset,
  and sign-out, with a job-seeker or job-provider account type chosen at
  registration.
- Private per-account application tracking and career profile storage.
- Job providers can filter draft, published, and closed listings, duplicate
  listings as drafts, and see an applicant count per listing. The Applicants
  workspace provides search and stage filters, a candidate table, per-applicant
  stage updates, interview scheduling, and an expandable required/preferred
  evidence breakdown. Its deterministic alignment is informational only, not a
  hiring score or recommendation. Flask provider endpoints verify the account
  role, and listing ownership is also enforced by Supabase RLS.
  Job seekers can browse published roles, apply within
  CareerLens, and follow each application. Applicant contact details and
  messages are shared only with the provider for the selected listing.
- Job applications include a required PDF résumé (up to 5 MB) and optional
  introduction. Résumés are stored in a private Supabase bucket and are
  accessible only to the applicant and the provider who owns that listing.
  Job seekers may retain labeled résumé versions and choose which version is
  attached to each application; providers can access only the selected version
  for their listing.
  Providers can review CVs, move candidates through CV review, shortlist,
  interview, offer, hire, or reject stages, add private reviewer notes, and
  optionally record an interview date. Applicants can see their current stage,
  a timestamped status timeline after the Phase 19 migration, and a required
  structured rejection reason after Phases 20 and 27. Optional rejection notes
  are shared only by explicit opt-in; a `skills_gap` reason links to the role's
  requirements and catalogue learning suggestions. Older transitions are
  labeled unavailable rather than assigned guessed dates. Reviewer notes are
  private to the hiring provider and are not included in applicant feedback
  responses.
- An application pipeline with editable records, status filters, search,
  follow-up reminders, notes, job links, summary metrics, and CSV export.
  The seeker dashboard shows counts by the exact recorded status from both the
  personal tracker and CareerLens applications. Average first provider
  response time uses only complete, timestamped CareerLens status histories;
  it excludes manual tracker entries and is descriptive, not predictive.
- Job-specific résumé bullets and a cover-letter draft workspace. Select a
  published listing to generate materials from the saved My Profile and
  portfolio projects. The draft is stored privately per job, and Gemini receives
  profile/job text only after the user consents. Generated claims must be reviewed
  and may not invent experience that is absent from the profile.
- An authenticated Interview Prep Studio that creates role-focused question
  sets, practice notes, progress tracking, and a downloadable interview
  checklist from a job description. Input text is processed for the request
  and is not stored; prompts are practice ideas, not interview predictions.
- A private STAR Story Bank lets job seekers save, edit, and delete concise
  self-reported Situation, Task, Action, and Result examples with optional
  skill tags. Stories are not verified or shared with employers. In Interview
  Prep, a selected story can be added to browser-only answer notes; it is not
  sent to Gemini by that workflow.
- Authenticated, job-seeker-only Skill Gap Analysis compares recognized
  requirements in a job description with profile skills, optional experience
  notes, and an optional uploaded résumé PDF. It distinguishes contextual
  evidence, skill mentions that need assessment, and skills with no evidence
  found; it offers practical next steps without claiming to verify proficiency
  or predict hiring. Analysis inputs are processed for the request and are not
  saved. Recognition uses a built-in skill vocabulary and does not require
  Gemini or a database migration.
- Job seekers can filter Find Jobs by employment type, location, alignment
  level, or saved status and sort by alignment, newest listing, or company.
  Compact match badges and expandable explanations remain tied to deterministic
  evidence. Private saved-job bookmarks require the saved-jobs migration and
  are isolated by account RLS. A what-if panel recalculates deterministic
  alignment after hypothetical skill additions/removals without saving profile
  changes; hypothetical skills do not verify proficiency and are not a hiring
  prediction. This in-memory feature requires no database migration.
- Employer response transparency displays a listing's response rate and median
  first-response time only when at least five applications exist. The provider
  dashboard shows the corresponding pooled aggregate across that provider's
  listings. Calculations use current application stages and recorded Phase 19
  status timestamps; older history is not backfilled, and the median is shown
  only when a response timestamp is available. These are descriptive
  historical metrics, not predictions or hiring recommendations.
- A job-seeker Learning workspace browses the administrator-managed catalogue
  by title/skill, category, and difficulty; shows resource descriptions,
  objectives, skill tags, and original links; and saves a personal plan with
  not-started, in-progress, or self-reported completed status and an optional
  target date; in-progress and completed items are grouped separately, saved
  resource skill tags are summarized, and the last-updated date is shown.
  Skill Gap Analysis recommendations deterministically match
  catalogue skill tags to skills marked “Needs assessment” or “No evidence
  found.” They do not claim those skills are confirmed weaknesses. Completion
  is completed saved items divided by all saved items, and is shown as `--`
  when the plan is empty. Recommendations from an analysis remain in browser
  memory only for the current page session.
- Interview Prep Studio builds a structured practice pack from a job
  description, with role-focused questions, STAR planning notes, progress
  tracking, and a downloadable worksheet. Prompts are generated locally from
  matched job-description terms; they are not predictions or AI advice.
- Optional AI Assistant powered by Gemini with Résumé Feedback, Interview
  Answers, and Ask a Question tabs for job seekers, plus employer job-description
  and interview-kit tools. The selected tool, target role, and text are sent to
  Google only when the user explicitly consents for that request. CareerLens does
  not store the AI request; Google's data-handling terms apply. Outputs are
  suggestions, not employment decisions.

The Flask development server is intended for local use only. For a hosted
deployment, use the production WSGI command above and configure Supabase's Site
URL and redirect allowlist for the deployed HTTPS origin.
