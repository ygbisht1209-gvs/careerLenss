# CareerLens

CareerLens is a local Flask career workspace. Supabase provides email/password
accounts and private cloud storage for application tracking and career profiles.

## Set up Supabase once

1. Create a Supabase project at <https://supabase.com>.
2. In **Project Settings → API**, copy the project URL and the public anon
   (publishable) key. Never put a `service_role` or secret key in this app.
3. In the Supabase **SQL Editor**, run the contents of
   [`backend/supabase_schema.sql`](backend/supabase_schema.sql). The tables use
   Row Level Security so each signed-in user can access only their own rows.
   If you already set up CareerLens, run the updated SQL file again to add the
   application follow-up, job link, and notes fields. The script is safe to
   rerun. Confirm the editor reports success before reloading the app.
4. In **Authentication → URL Configuration**, set the local Site URL to
   `http://127.0.0.1:5000` and add both of these redirect URLs:
   `http://127.0.0.1:5000` and `http://localhost:5000`.

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

The Gemini key is optional for the rest of the app, but required for Career AI
Studio. Create or view it in [Google AI Studio](https://aistudio.google.com/apikey).
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
must remain open while you use the app. To stop it, press **Ctrl+C** there.

Do not open `backend/templates/index.html` directly or use VS Code **Go Live**.
Live Server serves static files and does not run Flask or render its templates.

## Run automated tests

From the repository root, run:

```bash
./.venv/bin/python -m unittest discover -s tests -v
```

The tests cover configuration, authentication gating, resume-upload validation,
PDF parsing, analysis results, and mocked Gemini behavior. Tests do not contact
Supabase or Gemini.
GitHub Actions runs the same tests and checks the frontend JavaScript syntax on
every push and pull request.

If the dashboard says Supabase cannot find `public.applications`, check that
the Supabase project open in the SQL Editor is the same project whose URL is in
`backend/.env`. Run the full schema file in that project's SQL Editor, wait for
a successful result, and then reload CareerLens.

## Features

- Supabase email/password sign-up, sign-in, email verification, password reset,
  and sign-out.
- Private per-account application tracking and career profile storage.
- An application pipeline with editable records, status filters, search,
  follow-up reminders, notes, job links, summary metrics, and CSV export.
- An authenticated Interview Prep Studio that creates role-focused question
  sets, practice notes, progress tracking, and a downloadable interview
  checklist from a job description. Input text is processed for the request
  and is not stored; prompts are practice ideas, not interview predictions.
- PDF resume keyword comparison (the uploaded PDF is processed for the request
  and is not stored).
- Interview Prep Studio builds a structured practice pack from a job
  description, with role-focused questions, STAR planning notes, progress
  tracking, and a downloadable worksheet. Prompts are generated locally from
  matched job-description terms; they are not predictions or AI advice.
- LinkedIn profile drafting workspace and target-role skill keyword comparison.
- Built-in guided career-coaching prompts. This is a local, rule-based coach,
  not a connected generative AI service.
- Optional Career AI Studio powered by Gemini for job seekers (resume feedback and
  interview-answer coaching) and employers (job-description improvements and
  structured interview kits). The selected tool, target role, and text are sent
  to Google only when the user explicitly consents for that request. CareerLens
  does not store the AI request; Google's data-handling terms apply. Outputs are
  suggestions, not employment decisions.

CareerLens is currently configured as a local Flask app. The Flask development
server is intended for local use only. Configure Supabase's Site URL and
redirect allowlist for the address where you run the app.
