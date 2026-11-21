# CareerLens Technical Documentation

## 1. Repository structure

```text
.
├── backend/
│   ├── app.py                         # Flask app, API routes, validation/proxies
│   ├── interview_prep.py              # Deterministic interview practice pack
│   ├── job_matching.py                # Job requirement extraction and score
│   ├── learning.py                    # Learning recommendation matching
│   ├── skill_gap.py                   # Skill vocabulary and evidence analysis
│   ├── static/
│   │   ├── script.js                  # Auth, Supabase workflows, UI integration
│   │   ├── dashboard-ui.js            # Dashboard aggregation helpers
│   │   ├── learning-ui.js             # Learning display helpers
│   │   └── style.css                  # Styling and responsive rules
│   ├── templates/index.html           # Single-page application shell
│   ├── supabase_schema.sql             # Base schema, RLS, Storage policies
│   └── migrations/
│       ├── phase3_learning.sql         # Learning catalogue and user plans
│       └── phase5_portfolio.sql        # Private portfolio projects
├── docs/                               # Academic and technical documentation
├── tests/
│   ├── test_app.py                     # Flask API/validation tests
│   ├── test_job_matching.py
│   ├── test_learning.py
│   ├── test_skill_gap.py
│   ├── test_recommendation_evaluation.py
│   ├── test_dashboard_ui.cjs
│   └── test_learning_ui.cjs
├── requirements.txt
├── .python-version
└── README.md
```

`backend/.env.example` is a placeholder-only template. Do not copy real values
into tracked files. `backend/.env` is ignored by Git.

## 2. Architecture

The browser loads a Flask-rendered HTML shell and static assets. It uses
Supabase JavaScript v2 from a CDN for authentication and direct, user-token
database/storage operations. Selected analytical and CRUD functions use Flask
API routes; Flask validates a Supabase bearer token and forwards permitted
database operations using that user's token. RLS policies are defined in the
SQL files. Optional Gemini requests are made server-side after explicit
consent. No service-role key is required.

Résumé analysis parses an uploaded PDF in memory. Application résumés are
uploaded directly from the browser to the private Supabase Storage bucket.
CareerLens does not depend on a persistent local filesystem for application
records or resume files.

## 3. Prerequisites and installation

- Python 3.12 is the repository's tested/pinned runtime.
- Node.js is needed only for JavaScript tests.
- A Supabase project is required for account-backed features.
- Gemini is optional.

From the repository root:

```bash
python3.12 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```

Python dependencies are pinned in `requirements.txt`: Flask, Gunicorn,
`pypdf`, and `python-dotenv`.

## 4. Environment configuration

Create `backend/.env` from the placeholder file without overwriting an existing
local configuration:

```bash
if [ ! -e backend/.env ]; then cp backend/.env.example backend/.env; fi
```

Configure these values locally (or through a hosting provider's secret
settings):

| Variable | Required | Meaning |
|---|---|---|
| `SUPABASE_URL` | Yes for authentication/data features | Supabase project URL |
| `SUPABASE_ANON_KEY` | Yes for authentication/data features | Public anon/publishable key; never use a service-role key |
| `GEMINI_API_KEY` | No | Enables optional Gemini features |
| `GEMINI_MODEL` | No | Gemini model name; defaults in code to `gemini-3.6-flash` |

Do not display or commit actual environment values. Restart Flask after
changing the local file.

## 5. Database and authentication configuration

In the Supabase SQL Editor, review and run the base schema
[`../backend/supabase_schema.sql`](../backend/supabase_schema.sql). For
optional feature tables, run `phase3_learning.sql` and
`phase5_portfolio.sql` after the base schema. Do not execute migrations
automatically from the application or against a production project without
review.

In Supabase Authentication URL Configuration, set the Site URL and redirect
allowlist for the local or deployed application origin. For local startup, the
README documents `http://127.0.0.1:5000` and `http://localhost:5000`.

The schema files define RLS and a private `application-resumes` bucket. This
documentation does not certify the live project's applied schema or policy
state. Never disable RLS or make the résumé bucket public to bypass setup.

## 6. Local execution

From the repository root:

```bash
./.venv/bin/python -m flask --app backend/app.py run --host 127.0.0.1 --port 5000
```

Then open `http://127.0.0.1:5000`. The Flask CLI command is for development,
not a production server.

The production WSGI command documented for Render is:

```bash
gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 60 backend.app:app
```

Render's `PORT` is a host-provided variable. Deployment and live-site checks
are not performed by this documentation.

## 7. Tests

```bash
./.venv/bin/python -m unittest discover -s tests -v
node --test tests/*.cjs
node --check backend/static/script.js
node --check backend/static/dashboard-ui.js
node --check backend/static/learning-ui.js
./.venv/bin/python -m pip check
```

See [`TESTING_SUMMARY.md`](TESTING_SUMMARY.md) for the dated observed results
and the distinction between mocked tests and live-service tests.

## 8. Troubleshooting

- **Authentication configuration error:** check variable names and project URL;
  restart Flask after local edits. Do not share the anon key in reports.
- **Redirect or email-link failure:** confirm Supabase Site URL/redirect
  allowlist matches the exact local/deployed origin.
- **Missing table/resource errors:** confirm the intended Supabase project is
  configured and apply the reviewed base schema or feature migration manually.
- **Learning catalogue is empty:** the migration creates the schema, not
  sample resources; an administrator must curate verified catalogue records.
- **Résumé rejected:** analysis expects an unlocked, readable PDF within the
  configured 5 MiB limit; scanned image-only PDFs may have no extractable text.
- **Gemini unavailable:** set a valid optional server-side key and supported
  model; non-Gemini features do not require Gemini.
- **Provider/seeker feature unavailable:** confirm the account type and that
  the relevant migration/policies are installed. Frontend hiding is not a
  substitute for RLS.

## 9. Limitations

No live Supabase/Gemini project or deployment is verified by the repository's
local test suite. RLS tests inspect SQL source rather than executing database
policies. There is no automated browser end-to-end or viewport test suite.
Matching uses deterministic heuristics and a limited vocabulary. The learning
catalogue is SQL-managed, not administered through the UI.

