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
```

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

## Features

- Supabase email/password sign-up, sign-in, email verification, password reset,
  and sign-out.
- Private per-account application tracking and career profile storage.
- PDF resume keyword comparison (the uploaded PDF is processed for the request
  and is not stored).
- LinkedIn profile drafting workspace and target-role skill keyword comparison.
- Built-in guided career-coaching prompts. This is a local, rule-based coach,
  not a connected generative AI service.

CareerLens is currently configured as a local Flask app. The Flask development
server is intended for local use only. Configure Supabase's Site URL and
redirect allowlist for the address where you run the app.
