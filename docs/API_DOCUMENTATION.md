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

## 2. Public endpoints

### `GET /`

- **Purpose:** Render the CareerLens single-page interface.
- **Authentication:** None.
- **Success:** `200 text/html`; `Cache-Control: no-store`.
- **Possible errors:** Standard Flask/server errors.

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

### `POST /api/analyze-resume`

- **Purpose:** Compare readable PDF text with a supplied job description.
- **Authentication:** Any authenticated Supabase user.
- **Input:** Multipart fields `resume` (PDF, max 5 MiB) and
  `job_description` (non-empty text).
- **Success:** `200` with `score` (integer), `matched_keywords` (string
  array), `missing_keywords` (string array), `suggestions` (string array), and
  `note` (method limitation).
- **Errors:** `400` for missing/invalid file, unreadable/encrypted/no-text PDF,
  or unusable job description; `401` unauthenticated/expired session; `413`
  request limit; `502`/`503` authentication service errors.
- **Data handling:** Analysis PDF is parsed in memory and is not stored by this
  route. Score is keyword overlap, not an ATS score.

### `POST /api/skill-gap`

- **Purpose:** Explain recognized skill evidence for a target role.
- **Authentication:** Authenticated job seeker.
- **Input:** Multipart fields:
  - `target_role` (2–120 characters)
  - `job_description` (40–12,000 characters)
  - optional `skills` (up to 12,000 characters)
  - optional `experience` (up to 12,000 characters)
  - optional `resume` (PDF, max 5 MiB)
- **Success:** `200` with `target_role`, `skills` array, `summary`, `note`, and
  `portfolio_evidence_available`. Skill entries include requirement excerpt,
  evidence status, evidence excerpts, explanation, next action, and learning
  sequence.
- **Errors:** `400` invalid input/PDF; `401` unauthenticated; `403` not a
  seeker; `502`/`503` Supabase role, portfolio, or connectivity failure.
- **Data handling:** Submitted analysis text/PDF is not persisted by Flask.

### `POST /api/interview-prep`

- **Purpose:** Generate a deterministic interview practice pack.
- **Authentication:** Any authenticated Supabase user.
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
  `interview_answer`, `career_coach`, `improve_job_description`, and
  `interview_kit`. Career-coach text has a 2-character minimum; other tasks
  require 40 characters.
- **Success:** `200 {"answer": "..."}`.
- **Errors:** `400` invalid payload, unsupported task, invalid text, or missing
  consent; `401` unauthenticated/expired session; `403` non-provider invoking
  employer task; `502` invalid provider response/model/key; `503` missing
  Gemini configuration, timeout, or provider availability/rate limit.
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

## 5. Learning endpoints

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

## 6. Portfolio endpoints

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

## 7. Data operations not exposed as Flask routes

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

