# CareerLens API Documentation

## 1. Conventions

These routes are defined by `backend/app.py`. Unless marked public, clients
must send a Supabase access token:

```http
Authorization: Bearer <Supabase access token>
```

JSON endpoints require `Content-Type: application/json`. File-analysis
endpoints use `multipart/form-data`. Responses use JSON. The app forwards
authenticated database access with the caller's token; database access remains
subject to Supabase grants and RLS. Status/error details below reflect route
logic in the repository; actual behavior of a remote Supabase project has not
been verified.

API errors use `{"error": "..."}` JSON responses, including Flask 404/405/413
errors and sanitized unexpected 500 errors. Error logs contain endpoint and
exception-type metadata or upstream status/code values; they do not include
request bodies, tokens, résumé text, or personal data. The total request body
is capped at 5 MiB plus multipart overhead. Gemini-backed routes share a
five-request-per-minute cap per authenticated session. A keyed hash of the
bearer token is held in memory per Flask process; the cap is not distributed
across multiple Gunicorn workers or instances.

### `GET /api/application-materials/<job_id>`

- **Purpose:** Load the signed-in job seeker's saved résumé bullets and cover letter for one listing.
- **Authentication:** Authenticated job seeker.
- **Success:** `200` with `job_id`, `bullets`, `cover_letter`, and `updated_at`, or `null` when no draft exists.

### `POST /api/application-materials`

- **Purpose:** Generate and privately save job-specific résumé bullets and a cover letter from the signed-in profile, portfolio, and published listing.
- **Authentication:** Authenticated job seeker.
- **Input JSON:** `job_id` (UUID) and `consent: true`.
- **Input size:** The serialized saved profile, up to 50 projects, and selected
  job details are capped at 16,000 characters in aggregate.
- **Success:** `200` with `job_id`, `bullets`, and `cover_letter`.
- **Errors:** `413` when the saved profile/job input exceeds its cap; `429` when
  the Gemini request cap is reached; `502`/`503` for invalid provider output or
  provider/configuration failures.
- **Data handling:** The profile and listing are assembled server-side and sent to Gemini only after consent. The generated draft is saved in the private `application_material_drafts` table.

## 2. Public endpoints

### `GET /`

- **Purpose:** Render the CareerLens single-page interface.
- **Authentication:** None.
- **Success:** `200 text/html`; `Cache-Control: no-store`.
- **Possible errors:** Standard HTML errors outside `/api/`; API errors use the
  JSON shape documented above.

### `GET /api/config`

- **Purpose:** Return public Supabase client configuration and maximum resume
  size.
- **Authentication:** None.
- **Success:** `200 application/json`:

  ```json
  {
    "supabaseUrl": "https://YOUR_PROJECT_ID.supabase.co",
    "supabaseAnonKey": "YOUR_PUBLIC_ANON_OR_PUBLISHABLE_KEY",
    "maxResumeBytes": 5242880
  }
  ```

- **Errors:** `503` if `SUPABASE_URL` or `SUPABASE_ANON_KEY` is unset.
- **Security:** The anon/publishable key is public by design and depends on
  RLS. Do not put a service-role key here.

## 3. Authenticated analysis endpoints

### `POST /api/skill-gap`

- **Purpose:** Explain recognized skill evidence for a target role.
- **Authentication:** Authenticated job seeker.
- **Input:** Multipart fields:
  - `target_role` (2–120 characters)
  - `job_description` (40–12,000 characters)
  - optional `skills` (up to 12,000 characters)
  - optional `experience` (up to 12,000 characters)
  - optional `resume` (PDF with PDF or octet-stream MIME type, max 5 MiB;
    parsed in memory and not persisted by Flask)
- **Success:** `200` with `target_role`, `skills` array, `summary`, `note`, and
  `portfolio_evidence_available`. Skill entries include requirement excerpt,
  evidence status, evidence excerpts, explanation, next action, and learning
  sequence.
- **Errors:** `400` invalid input/PDF; `401` unauthenticated; `403` not a
  seeker; `502`/`503` Supabase role, portfolio, or connectivity failure.
- **Data handling:** Submitted analysis text/PDF is not persisted by Flask.

### `POST /api/interview-prep`

- **Purpose:** Generate a deterministic interview practice pack.
- **Authentication:** Authenticated job seeker.
- **Input JSON:** `role` (2–120 chars), optional `company` (up to 120 chars),
  `job_description` (40–12,000 chars).
- **Success:** `200` with role/company, focus areas, questions, checklist, and
  explanatory note.
- **Errors:** `400` invalid JSON or fields; `401` unauthenticated or expired
  session; `502`/`503` auth-service failure.
- **Processing:** Uses local fixed question templates and keyword/focus
  matching; no Gemini call.

### `POST /api/ai-assist`

- **Purpose:** Optional Gemini career assistance.
- **Authentication:** Any authenticated user; employer-only tasks additionally
  require provider role.
- **Input JSON:** `task`, `role` (2–120 chars), `text` (maximum 8,000 chars),
  and `consent: true`. Supported tasks are `resume_feedback`,
  `interview_answer`, `ask_question`, `improve_job_description`, and
  `interview_kit`. Ask-a-question text has a 2-character minimum; other tasks
  require 40 characters.
- **Success:** `200 {"answer": "..."}`.
- **Errors:** `400` invalid payload, unsupported task, invalid text, or missing
  consent; `401` unauthenticated/expired session; `403` non-provider invoking
  employer task; `429` local request cap; `502` invalid/oversized provider
  response/model/key; `503` missing Gemini configuration, timeout, or provider
  availability/rate limit.
- **Data handling:** Consent is checked per request. Flask sends user text to
  Google's Interactions API using a server-side key and `store: false`.

## 4. Job recommendations

### `GET /api/job-recommendations`

- **Purpose:** Return published job listings with evidence explanations.
- **Authentication:** Authenticated job seeker.
- **Input:** No query parameters are required.
- **Success:** `200` object with:
  - `jobs`: listing records augmented with `match`
  - `profile`: completeness, missing fields, and source availability flags
  - `scoring`: status values, weights, and limitations
- **Errors:** `401` unauthenticated; `403` not a seeker; `502`/`503` when
  required Supabase records fail or are malformed. Missing recognized optional
  learning/portfolio migrations are reported or omitted as handled in code.
- **Data sources:** User-scoped career profile, portfolio projects, learning
  records, and published job listings.

### `POST /api/job-recommendations/<job_id>/what-if`

- **Purpose:** Recalculate one published listing's deterministic alignment
  after hypothetical additions/removals from the caller's saved skill list.
- **Authentication:** Authenticated job seeker; the listing and profile data
  are read through the caller's bearer token and RLS.
- **Input JSON:** Optional `add_skills` and `remove_skills` arrays, with up to
  20 recognized skills per array. A skill cannot appear in both.
- **Success:** `200` with baseline/simulated scores, their delta when both
  scores are available, and the simulated required/preferred evidence.
- **Persistence:** None. No profile changes or simulation history are saved.
- **Limitations:** A hypothetical listed skill is not evidence of proficiency;
  results are descriptive alignment, not a hiring prediction.

### Employer response transparency

These endpoints require the manual Phase 26 migration after the base schema
and Phase 19 application status-history migration. Their database functions
return aggregates only; no applicant ID, name, email, or per-application row
is returned. Phase 26 also permits providers to read status-history rows only
for applications on listings they own; applicants retain access to their own
history, and clients cannot insert or update history rows.

- `GET /api/jobs/responsiveness` requires an authenticated job seeker and
  returns `{ "metrics": [...] }` for published listings. Each entry contains
  `job_id`, `response_rate`, `median_first_response_days`, `sample_size`, and
  `sufficient_data`.
- `GET /api/jobs/<job_id>/responsiveness` is seeker-only and returns the same
  summary fields without `job_id`. Unpublished or unavailable listings return
  `404`.
- `GET /api/provider/response-metrics` requires a job provider and returns one
  pooled aggregate across only that provider's listings.
- If fewer than five applications exist, both calculated values are `null`
  and `sufficient_data` is `false`; zero applications return a sample size of
  `0`. With sufficient data, the response rate counts applications that
  reached a later stage or rejection, and the median uses the first recorded
  response timestamp. Withdrawn-only changes are not responses.
- Phase 19 status history is append-only and is not backfilled. Older
  applications can contribute their current later stage to the rate, while
  their missing historical response timestamp cannot contribute to the median.
  These summaries are descriptive, not hiring predictions.

### Saved jobs

All three routes require an authenticated job seeker and the
`backend/migrations/phase18_saved_jobs.sql` migration. Supabase supplies the
row owner from `auth.uid()`; callers cannot choose a `user_id`.

- `GET /api/saved-jobs` returns the caller's bookmarks.
- `POST /api/saved-jobs` accepts exactly `{"job_id": "<UUID>"}`.
- `DELETE /api/saved-jobs/<job_id>` removes one caller-owned bookmark.
- RLS scopes reads/writes to the current job-seeker account. The policy tests
  are source-contract assertions; live isolation requires a Supabase test
  project.

## 5. STAR story bank

All routes require an authenticated job seeker and the
`backend/migrations/phase25_star_story_bank.sql` migration. RLS scopes each row
to its `user_id`; the caller cannot supply or change that owner.

- `GET /api/star-stories` returns the caller's stories ordered by most recently
  updated. An empty bank is returned as `[]`.
- `POST /api/star-stories` accepts `title`, `situation`, `task`, `action`,
  `result`, and `skill_tags`. Text sections are length-limited and their
  combined content is capped at 1,700 characters. At most 12 skill tags of
  1–50 characters are accepted.
- `PATCH /api/star-stories/<story_id>` accepts the same complete story shape
  and updates only a caller-owned row.
- `DELETE /api/star-stories/<story_id>` removes only a caller-owned row.
- Stories are self-reported, not verified evidence of proficiency. Interview
  Prep can insert a selected story into browser-only answer notes; this
  integration does not send the story to Gemini or persist the notes.

## 6. Provider, notification, and interview routes

All `/api/provider/...` routes verify the provider role in Flask and continue
to rely on Supabase RLS for listing/application ownership.

- `GET /api/provider-applicant-evidence` returns required/preferred skill
  classifications and evidence for candidates who applied to the provider's
  listings. It is an informational text-alignment indicator, not a hiring
  score or decision.
- `POST /api/provider/job-listings/<job_id>/duplicate` creates a copy as a
  draft. `PATCH /api/provider/job-listings/<job_id>/status` accepts a JSON
  `status` of `draft`, `published`, or `closed`.
- `GET /api/provider/application-reviews` returns provider-private notes and
  interview dates for owned applications.
- `PATCH /api/provider/job-applications/<application_id>/status` accepts a
  valid hiring-stage `status`. Setting `Rejected` also requires exactly one
  `rejection_reason` from `skills_gap`, `experience_level`, `position_filled`,
  `role_requirements_changed`, `application_incomplete`, or `other`. Optional
  `rejection_note` is limited to 500 characters; `rejection_note_shared`
  defaults to `false`. The Phase 27 database function changes the application
  stage and rejection details in one transaction. Moving to another stage
  clears the rejection record.
- `POST /api/provider/application-reviews/<application_id>` accepts
  `reviewer_notes` (maximum 4,000 characters) and optional ISO timestamp
  `interview_at`. Applicants cannot read review notes under the schema's RLS
  policy.
- `GET /api/provider/application-rejection-feedback` returns rejection reasons
  and notes, including private notes, only to the provider who owns each
  application. The compatibility route `POST
  /api/provider/job-applications/<application_id>/rejection-feedback` accepts
  the same single-reason fields as the status endpoint. Both routes require
  Phases 20 and 27; direct client writes to the feedback table are revoked.
- `GET /api/job-applications/<application_id>/rejection-feedback` is seeker-only
  and owner-scoped. It returns the reason and role details for the seeker's
  rejected application; the note is `null` unless the provider opted to share
  it. A feedback object with a `null` reason indicates no structured data is
  available for that legacy rejection; a non-owner receives 404. Its database
  function returns no applicant identity or private reviewer notes, and RLS
  denies direct applicant reads of the feedback table; only this owner-checked
  function returns the limited applicant-visible projection.
- `GET /api/notifications` and
  `PATCH /api/notifications/<notification_id>/read` are available to
  authenticated account types; RLS scopes notification rows to their owner.
  The Phase 23 migration records each application-stage transition for the
  applicant and sends a withdrawal notice to the listing provider. Install
  `backend/migrations/phase23_notification_calendar_enhancements.sql` after
  Phase 16 to enable those additions.
- `GET /api/provider/interview-slots` and
  `POST /api/provider/job-applications/<application_id>/interview-slots`
  require a provider account. Creation accepts only a timezone-aware ISO
  `starts_at`, at least five minutes and at most one year in the future.
  Offered slots last 30 minutes. `DELETE /api/provider/interview-slots/<slot_id>`
  removes an unbooked slot; `POST
  /api/provider/interview-slots/<slot_id>/cancel` cancels a booked slot.
- `GET /api/job-applications/interview-slots`,
  `POST /api/job-applications/interview-slots/<slot_id>/book`, and
  `POST /api/job-applications/interview-slots/<slot_id>/cancel` require a job
  seeker account. RLS and database functions verify the application owner;
  concurrent bookings are serialized and overlapping bookings for the same
  provider are rejected. The migration notifies applicants when times are
  offered or removed and notifies both parties about bookings and
  cancellations. Apply
  `backend/migrations/phase24_interview_slot_booking.sql` after Phases 16 and
  23.
- `GET /api/job-applications/<application_id>/timeline` requires an
  authenticated job seeker and the
  `backend/migrations/phase19_application_status_history.sql` migration. It
  returns only the caller's current application status, submission timestamp,
  and recorded status events. The migration captures future transitions;
  legacy transition dates are not reconstructed, and `history_complete` is
  false when the available events do not prove a complete timeline.
- `GET /api/application-analytics` requires an authenticated job seeker and
  returns the mean first-response time only for applications with both a
  recorded submission and first provider transition. Applicant withdrawals,
  manual tracker records, legacy histories without both events, and truncated
  event sets are excluded. The response is descriptive, not a hiring
  prediction; `average_first_response_hours` is `null` when no complete sample
  exists. Run `backend/migrations/phase21_application_analytics.sql` after
  Phase 19 for the event lookup index.
- `GET /api/job-applications/<application_id>/interview.ics` returns a calendar
  file only when the authenticated caller can access the application and an
  interview date is available. Both the applicant and listing provider can
  download the event; the provider workspace exposes a calendar action for
  scheduled interviews. Booked interview slots take precedence over a legacy
  manually-set date, and a cancelled slot is no longer exportable.
- Résumé version metadata is stored in `public.resume_versions` after applying
  `backend/migrations/phase22_resume_versions.sql`. Job seekers read and create
  their own version records through Supabase with RLS; applications reference
  the selected `resume_version_id`. Providers can read version metadata and
  private storage objects only when that version is attached to one of their
  applications. Legacy applications with `resume_version_id = null` continue
  to use their existing `resume_path`.

Provider review queries are bounded, and applicant evidence is read only for
applicants on the current provider's listings. These API-level role checks do
not replace the database's RLS ownership checks.

## 7. Learning endpoints

All learning endpoints require an authenticated job seeker.

### `GET /api/learning/resources`

- **Purpose:** Read active learning resources and category data.
- **Success:** `200` JSON array of resources.
- **Errors:** `401`, `403`, `502`/`503` for auth, role, schema, or service
  failures.

### `GET /api/learning/plan`

- **Purpose:** Read the caller's learning plan with linked resource fields.
- **Success:** `200` JSON array.
- **Errors:** `401`, `403`, `502`/`503`.
- **Ownership:** RLS in the Phase 3 migration is intended to scope plan rows to
  the authenticated user.

### `POST /api/learning/recommendations`

- **Purpose:** Match analyzed needs to active resource tags.
- **Input JSON:** Exactly `{"skills": [...]}`; up to 100 objects, each with
  `name` (1–120 chars) and `status` in `Demonstrated`, `Needs assessment`,
  `No evidence found`.
- **Success:** `200` JSON array of matching resources with `matched_skills`.
- **Errors:** `400` invalid input; `401`/`403`; `502`/`503` resource/database
  failures.
- **Processing:** Deterministic; only `Needs assessment` and `No evidence
  found` are recommendation needs.

### `POST /api/learning/plan`

- **Purpose:** Add a resource to the caller's personal plan.
- **Input JSON:** `resource_id` UUID; optional allowed `status` and
  `target_completion_date` (`YYYY-MM-DD` or null).
- **Success:** `200` JSON array containing the created plan row.
- **Errors:** `400` invalid fields/date/UUID; `401`/`403`; `404` resource
  unavailable; `409` duplicate; `502`/`503` service/schema error.

### `PATCH /api/learning/plan/<plan_id>`

- **Purpose:** Update allowed plan fields.
- **Input JSON:** At least one of `status` (`not_started`, `in_progress`,
  `completed`) and `target_completion_date`.
- **Success:** `200` JSON array with updated row.
- **Errors:** `400` invalid UUID/payload; `401`/`403`; `404` no row returned;
  `502`/`503` remote service/schema failure.

### `DELETE /api/learning/plan/<plan_id>`

- **Purpose:** Remove a plan row.
- **Input:** UUID path parameter.
- **Success:** `200` JSON response from the Supabase proxy (normally an array).
- **Errors:** `400` invalid UUID; `401`/`403`; `404` no row returned; `502`/
  `503` service/schema failure.

## 8. Portfolio endpoints

All portfolio endpoints require an authenticated job seeker and the Phase 5
portfolio table.

Project JSON fields are exactly `title`, `description`, `skills`,
`contribution`, `project_url`, `started_on`, and `completed_on`. Length and
date constraints are validated by Flask; URL, ownership, and row policies are
also defined in SQL.

### `GET /api/portfolio/projects`

- **Purpose:** List the caller's private projects.
- **Success:** `200` JSON array.
- **Errors:** `401`/`403`; `502` service error; `503` if migration is missing.

### `POST /api/portfolio/projects`

- **Purpose:** Create a project; client-supplied owner IDs are not accepted.
- **Success:** `200` JSON array from the PostgREST representation.
- **Errors:** `400` invalid JSON/fields; `401`/`403`; `502` remote error;
  `503` missing migration.

### `PATCH /api/portfolio/projects/<project_id>`

- **Purpose:** Replace the validated project payload for the selected UUID.
- **Success:** `200` JSON array.
- **Errors:** `400` invalid UUID/payload; `401`/`403`; `404` no matching row;
  `502`/`503`.

### `DELETE /api/portfolio/projects/<project_id>`

- **Purpose:** Delete the selected project UUID.
- **Success:** `200` JSON proxy response.
- **Errors:** `400` invalid UUID; `401`/`403`; `404` no matching row;
  `502`/`503`.

## 9. Data operations not exposed as Flask routes

The browser uses Supabase JavaScript directly for authentication and several
table/storage operations. These are not Flask endpoints:

- Auth: sign-up/sign-in, email resend, password reset/update, sign-out.
- `career_profiles`, `applications`, and `user_accounts` access.
- Provider `job_listings`, `job_applications`, and `application_reviews`
  access.
- Seeker job applications and résumé object upload/removal in
  `application-resumes`.

These operations depend on Supabase client behavior, SQL grants, and RLS.
Their live request/response behavior is not verified by this API document.

