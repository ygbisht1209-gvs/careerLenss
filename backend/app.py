
import os
import re
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from pypdf import PdfReader

app = Flask(__name__, static_folder="static", template_folder="templates")

load_dotenv(Path(__file__).with_name(".env"))

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE + 128 * 1024
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")

STOP_WORDS = {
    "the", "and", "for", "with", "that", "this", "from",
    "are", "you", "your", "our", "will", "have", "has",
    "was", "were", "their", "they", "job", "work", "role",
    "required", "requirements", "candidate", "ability"
}


def extract_keywords(text):
    words = re.findall(r"[a-zA-Z][a-zA-Z+#.]*", text.lower())
    return {
        word for word in words
        if len(word) > 1 and word not in STOP_WORDS
    }


@app.route("/")
def home():
    return render_template(
        "index.html",
        supabase_url=SUPABASE_URL,
        supabase_anon_key=SUPABASE_ANON_KEY,
    )


@app.route("/api/config")
def public_config():
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return jsonify({"error": "Supabase authentication is not configured."}), 503
    return jsonify({
        "supabaseUrl": SUPABASE_URL,
        "supabaseAnonKey": SUPABASE_ANON_KEY,
        "maxResumeBytes": MAX_FILE_SIZE,
    })


@app.errorhandler(413)
def request_too_large(_error):
    return jsonify({"error": "The PDF must be 5 MB or smaller."}), 413


def verify_supabase_user():
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return None, (jsonify({
            "error": "CareerLens authentication is not configured. Add your Supabase URL and anon key, then restart the app."
        }), 503)

    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return None, (jsonify({"error": "Please sign in before using this tool."}), 401)

    user_request = Request(
        f"{SUPABASE_URL}/auth/v1/user",
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": authorization,
        },
    )
    try:
        with urlopen(user_request, timeout=5) as response:
            return True, None
    except HTTPError as error:
        if error.code in (400, 401, 403):
            return None, (jsonify({"error": "Your session has expired. Please sign in again."}), 401)
        app.logger.warning("Supabase authentication returned HTTP %s", error.code)
        return None, (jsonify({"error": "Authentication service is temporarily unavailable."}), 502)
    except URLError:
        app.logger.exception("Could not reach Supabase to verify the user session")
        return None, (jsonify({"error": "Could not reach the authentication service. Check your connection."}), 503)


@app.route("/api/analyze-resume", methods=["POST"])
def analyze_resume():
    _, error_response = verify_supabase_user()
    if error_response:
        return error_response

    if "resume" not in request.files:
        return jsonify({"error": "Please upload your resume PDF."}), 400

    resume_file = request.files["resume"]
    job_description = request.form.get("job_description", "").strip()

    if not resume_file.filename:
        return jsonify({"error": "Choose a PDF resume first."}), 400

    if not resume_file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are supported."}), 400

    if not job_description:
        return jsonify({"error": "Please paste the job description."}), 400

    pdf_bytes = resume_file.read(MAX_FILE_SIZE + 1)

    if len(pdf_bytes) > MAX_FILE_SIZE:
        return jsonify({"error": "The PDF must be 5 MB or smaller."}), 400

    try:
        reader = PdfReader(BytesIO(pdf_bytes))

        if reader.is_encrypted:
            return jsonify({
                "error": "This PDF is password-protected. Upload an unlocked PDF."
            }), 400

        resume_text = "\n".join(
            page.extract_text() or "" for page in reader.pages
        ).strip()

    except Exception:
        return jsonify({
            "error": "We couldn't read this PDF. Please try another PDF."
        }), 400

    if not resume_text:
        return jsonify({
            "error": "No readable text found. Try a text-based PDF rather than a scanned image."
        }), 400

    resume_keywords = extract_keywords(resume_text)
    job_keywords = extract_keywords(job_description)

    if not job_keywords:
        return jsonify({
            "error": "The job description doesn't contain enough readable keywords."
        }), 400

    matched = sorted(resume_keywords & job_keywords)
    missing = sorted(job_keywords - resume_keywords)

    score = round((len(matched) / len(job_keywords)) * 100) if job_keywords else 0

    suggestions = []

    if missing:
        suggestions.append(
            "Review the missing keywords and add relevant ones where they truthfully reflect your experience."
        )

    if score < 40:
        suggestions.append(
            "Tailor your skills and experience sections more closely to the job requirements."
        )
    elif score < 70:
        suggestions.append(
            "Improve alignment by highlighting relevant projects, tools, and achievements."
        )
    else:
        suggestions.append(
            "Your keyword alignment looks promising. Check that your experience and achievements are clearly explained."
        )

    if len(resume_text.split()) < 150:
        suggestions.append(
            "Your resume text is quite short. Make sure your relevant experience, projects, and education are included."
        )

    return jsonify({
        "score": score,
        "matched_keywords": matched,
        "missing_keywords": missing,
        "suggestions": suggestions,
        "note": "This is a basic keyword-match estimate, not an official ATS score."
    })


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
