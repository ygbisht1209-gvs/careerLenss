import io
import json
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from backend import app as app_module


def create_pdf(text):
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream.encode())} >>\nstream\n{stream}\nendstream",
    ]
    document = "%PDF-1.4\n"
    offsets = [0]
    for index, item in enumerate(objects, start=1):
        offsets.append(len(document.encode()))
        document += f"{index} 0 obj\n{item}\nendobj\n"
    xref_offset = len(document.encode())
    document += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    document += "".join(f"{offset:010} 00000 n \n" for offset in offsets[1:])
    document += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    )
    return document.encode()


class CareerLensApiTests(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()
        self.url_patch = patch.object(
            app_module, "SUPABASE_URL", "https://example.supabase.co"
        )
        self.key_patch = patch.object(app_module, "SUPABASE_ANON_KEY", "public-key")
        self.url_patch.start()
        self.key_patch.start()
        self.addCleanup(self.url_patch.stop)
        self.addCleanup(self.key_patch.stop)

        response = MagicMock()
        response.__enter__.return_value = response
        self.auth_request = patch("backend.app.urlopen", return_value=response)
        self.auth_urlopen = self.auth_request.start()
        self.addCleanup(self.auth_request.stop)

    def post_resume(self, content, filename="resume.pdf", job_description="Python SQL"):
        return self.client.post(
            "/api/analyze-resume",
            headers={"Authorization": "Bearer valid-session"},
            data={
                "resume": (io.BytesIO(content), filename),
                "job_description": job_description,
            },
            content_type="multipart/form-data",
        )

    def post_interview_prep(self, payload):
        return self.client.post(
            "/api/interview-prep",
            headers={"Authorization": "Bearer valid-session"},
            json=payload,
        )

    def post_ai_assist(self, payload):
        return self.client.post(
            "/api/ai-assist",
            headers={"Authorization": "Bearer ai-test-token"},
            json=payload,
        )

    def test_home_and_public_config(self):
        page = self.client.get("/")
        config = self.client.get("/api/config")

        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.headers["Cache-Control"], "no-store")
        self.assertIn(b"CareerLens", page.data)
        self.assertIn(b"Career AI Studio", page.data)
        self.assertIn(b"ai-assist-form", page.data)
        self.assertIn(b"ai-consent", page.data)
        self.assertEqual(config.status_code, 200)
        self.assertEqual(config.json["supabaseUrl"], "https://example.supabase.co")
        self.assertEqual(config.json["supabaseAnonKey"], "public-key")
        self.assertEqual(config.headers["Cache-Control"], "no-store")

    def test_config_reports_missing_supabase_values(self):
        with patch.object(app_module, "SUPABASE_URL", ""):
            response = self.client.get("/api/config")

        self.assertEqual(response.status_code, 503)
        self.assertIn("not configured", response.json["error"])

    def test_resume_analysis_requires_configuration_and_bearer_token(self):
        with patch.object(app_module, "SUPABASE_ANON_KEY", ""):
            missing_config = self.client.post("/api/analyze-resume")
        missing_token = self.client.post("/api/analyze-resume")

        self.assertEqual(missing_config.status_code, 503)
        self.assertEqual(missing_token.status_code, 401)
        self.auth_urlopen.assert_not_called()

    def test_resume_analysis_rejects_missing_or_invalid_upload_fields(self):
        missing_file = self.client.post(
            "/api/analyze-resume",
            headers={"Authorization": "Bearer valid-session"},
            data={"job_description": "Python SQL"},
        )
        unsupported_file = self.post_resume(b"not a pdf", "resume.txt")
        missing_description = self.post_resume(create_pdf("Python SQL"), job_description="")

        self.assertEqual(missing_file.status_code, 400)
        self.assertIn("upload", missing_file.json["error"].lower())
        self.assertEqual(unsupported_file.status_code, 400)
        self.assertIn("PDF", unsupported_file.json["error"])
        self.assertEqual(missing_description.status_code, 400)

    def test_resume_analysis_rejects_oversized_and_unreadable_pdfs(self):
        oversized = self.post_resume(b"x" * (app_module.MAX_FILE_SIZE + 1))
        unreadable = self.post_resume(b"not a PDF")

        self.assertEqual(oversized.status_code, 400)
        self.assertIn("5 MB", oversized.json["error"])
        self.assertEqual(unreadable.status_code, 400)
        self.assertIn("couldn't read", unreadable.json["error"])

    def test_resume_analysis_returns_keyword_match_and_suggestions(self):
        response = self.post_resume(
            create_pdf("Python developer SQL data analysis"),
            job_description="Python SQL data analysis",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["score"], 100)
        self.assertEqual(response.json["matched_keywords"], ["analysis", "data", "python", "sql"])
        self.assertEqual(response.json["missing_keywords"], [])
        self.assertTrue(response.json["suggestions"])
        self.assertIn("not an official ATS score", response.json["note"])

    def test_resume_analysis_rejects_job_descriptions_without_keywords(self):
        response = self.post_resume(
            create_pdf("Python developer with relevant experience"),
            job_description="the and for",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("keywords", response.json["error"].lower())

    def test_expired_supabase_session_is_reported_as_unauthorized(self):
        self.auth_request.stop()
        expired = HTTPError(
            "https://example.supabase.co/auth/v1/user",
            401,
            "Unauthorized",
            {},
            io.BytesIO(b"{}"),
        )
        self.auth_request = patch("backend.app.urlopen", side_effect=expired)
        self.auth_urlopen = self.auth_request.start()
        self.addCleanup(self.auth_request.stop)

        response = self.post_resume(create_pdf("Python SQL"))

        self.assertEqual(response.status_code, 401)
        self.assertIn("session has expired", response.json["error"])

    def test_interview_prep_requires_a_valid_session(self):
        response = self.client.post(
            "/api/interview-prep",
            json={
                "role": "Data Analyst",
                "job_description": "SQL and analytics experience required for this role.",
            },
        )

        self.assertEqual(response.status_code, 401)

    def test_interview_prep_returns_targeted_questions_and_checklist(self):
        response = self.post_interview_prep({
            "role": "Backend Developer",
            "company": "Example Co",
            "job_description": (
                "Build Python and Flask services, design SQL database queries, "
                "write tests, and collaborate with product and engineering teams."
            ),
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["role"], "Backend Developer")
        self.assertEqual(response.json["company"], "Example Co")
        focus_names = [area["name"] for area in response.json["focus_areas"]]
        self.assertIn("Python", focus_names)
        self.assertIn("SQL and databases", focus_names)
        categories = {question["category"] for question in response.json["questions"]}
        self.assertEqual(categories, {"Role focus", "Behavioral", "Situational"})
        self.assertTrue(all(question["question"] and question["follow_up"]
                            for question in response.json["questions"]))
        self.assertGreaterEqual(len(response.json["checklist"]), 4)
        self.assertIn("not predictions", response.json["note"])

    def test_interview_prep_validates_json_and_input_limits(self):
        not_json = self.client.post(
            "/api/interview-prep",
            headers={"Authorization": "Bearer valid-session"},
            data="not json",
            content_type="text/plain",
        )
        short_description = self.post_interview_prep({
            "role": "Developer",
            "job_description": "Too short",
        })
        long_role = self.post_interview_prep({
            "role": "x" * 121,
            "job_description": "A valid description " * 4,
        })
        long_description = self.post_interview_prep({
            "role": "Developer",
            "job_description": "x" * 12001,
        })
        invalid_company = self.post_interview_prep({
            "role": "Developer",
            "company": 123,
            "job_description": "A valid description " * 4,
        })

        self.assertEqual(not_json.status_code, 400)
        self.assertEqual(short_description.status_code, 400)
        self.assertEqual(long_role.status_code, 400)
        self.assertEqual(long_description.status_code, 400)
        self.assertEqual(invalid_company.status_code, 400)

    def test_ai_assist_requires_configuration_and_explicit_consent(self):
        payload = {
            "task": "resume_feedback",
            "role": "Data Analyst",
            "text": "A resume excerpt with enough characters for useful feedback.",
            "consent": True,
        }
        with patch.object(app_module, "GEMINI_API_KEY", ""):
            missing_key = self.post_ai_assist(payload)
        with patch.object(app_module, "GEMINI_API_KEY", "test-key"):
            no_consent = self.post_ai_assist({**payload, "consent": False})

        self.assertEqual(missing_key.status_code, 503)
        self.assertIn("GEMINI_API_KEY", missing_key.json["error"])
        self.assertEqual(no_consent.status_code, 400)
        self.assertIn("Confirm", no_consent.json["error"])
        self.assertEqual(self.auth_urlopen.call_count, 2)

    def test_ai_assist_validates_task_role_and_text(self):
        valid = {
            "task": "resume_feedback",
            "role": "Data Analyst",
            "text": "A resume excerpt with enough characters for useful feedback.",
            "consent": True,
        }
        with patch.object(app_module, "GEMINI_API_KEY", "test-key"):
            invalid_task = self.post_ai_assist({**valid, "task": []})
            short_text = self.post_ai_assist({**valid, "text": "Too short"})
            long_text = self.post_ai_assist({**valid, "text": "x" * 8001})
            long_role = self.post_ai_assist({**valid, "role": "x" * 121})

        self.assertEqual(invalid_task.status_code, 400)
        self.assertEqual(short_text.status_code, 400)
        self.assertEqual(long_text.status_code, 400)
        self.assertEqual(long_role.status_code, 400)
        self.assertEqual(self.auth_urlopen.call_count, 4)

    def test_ai_assist_sends_consented_text_server_side_and_returns_answer(self):
        provider_response = MagicMock()
        provider_response.__enter__.return_value = provider_response
        provider_response.read.return_value = (
            b'{"status":"completed","steps":[{"type":"model_output","content":'
            b'[{"type":"text","text":"Use a measurable example."}]}]}'
        )
        payload = {
            "task": "resume_feedback",
            "role": "Data Analyst",
            "text": "A resume excerpt with enough characters for useful feedback.",
            "consent": True,
        }
        with (
            patch.object(app_module, "GEMINI_API_KEY", "server-only-test-key"),
            patch.object(
                app_module,
                "urlopen",
                side_effect=[self.auth_urlopen.return_value, provider_response],
            ) as urlopen_mock,
        ):
            response = self.post_ai_assist(payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["answer"], "Use a measurable example.")
        provider_request = urlopen_mock.call_args_list[1].args[0]
        self.assertEqual(
            provider_request.get_header("X-goog-api-key"),
            "server-only-test-key",
        )
        self.assertEqual(
            provider_request.full_url,
            "https://generativelanguage.googleapis.com/v1beta/interactions",
        )
        request_payload = json.loads(provider_request.data.decode("utf-8"))
        prompt = request_payload["input"]
        self.assertIn(payload["text"], prompt)
        self.assertEqual(request_payload["model"], app_module.GEMINI_MODEL)
        self.assertEqual(request_payload["generation_config"]["thinking_level"], "low")
        self.assertFalse(request_payload["store"])
        self.assertEqual(urlopen_mock.call_args_list[1].kwargs["timeout"], 30)

    def test_ai_assist_reports_provider_rate_limits_without_exposing_provider_body(self):
        rate_limit = HTTPError(
            "https://generativelanguage.googleapis.com/",
            429,
            "Too Many Requests",
            {},
            io.BytesIO(b'{"error":"private provider details"}'),
        )
        payload = {
            "task": "interview_kit",
            "role": "Backend Developer",
            "text": "Create structured questions for this role using the description.",
            "consent": True,
        }
        with (
            patch.object(app_module, "GEMINI_API_KEY", "test-key"),
            patch.object(
                app_module,
                "urlopen",
                side_effect=[self.auth_urlopen.return_value, rate_limit],
            ),
        ):
            response = self.post_ai_assist(payload)

        self.assertEqual(response.status_code, 503)
        self.assertIn("temporarily busy", response.json["error"])
        self.assertNotIn("private provider details", response.get_data(as_text=True))

    def test_ai_assist_explains_when_model_is_unavailable(self):
        model_not_found = HTTPError(
            "https://generativelanguage.googleapis.com/",
            404,
            "Not Found",
            {},
            io.BytesIO(b'{"error":"model no longer available"}'),
        )
        payload = {
            "task": "resume_feedback",
            "role": "Data Analyst",
            "text": "A resume excerpt with enough characters for useful feedback.",
            "consent": True,
        }
        with (
            patch.object(app_module, "GEMINI_API_KEY", "test-key"),
            patch.object(
                app_module,
                "urlopen",
                side_effect=[self.auth_urlopen.return_value, model_not_found],
            ),
        ):
            response = self.post_ai_assist(payload)

        self.assertEqual(response.status_code, 502)
        self.assertIn("configured Gemini model is unavailable", response.json["error"])
        self.assertNotIn("model no longer available", response.get_data(as_text=True))

    def test_ai_assist_handles_provider_timeout_and_invalid_json(self):
        payload = {
            "task": "interview_answer",
            "role": "Product Designer",
            "text": "I led a design project and improved the user onboarding flow.",
            "consent": True,
        }
        with (
            patch.object(app_module, "GEMINI_API_KEY", "test-key"),
            patch.object(
                app_module,
                "urlopen",
                side_effect=[
                    self.auth_urlopen.return_value,
                    TimeoutError("provider timed out"),
                ],
            ),
        ):
            timeout_response = self.post_ai_assist(payload)

        invalid_provider_response = MagicMock()
        invalid_provider_response.__enter__.return_value = invalid_provider_response
        invalid_provider_response.read.return_value = b"not-json"
        with (
            patch.object(app_module, "GEMINI_API_KEY", "test-key"),
            patch.object(
                app_module,
                "urlopen",
                side_effect=[self.auth_urlopen.return_value, invalid_provider_response],
            ),
        ):
            invalid_json_response = self.post_ai_assist(payload)

        self.assertEqual(timeout_response.status_code, 503)
        self.assertIn("Could not reach Gemini", timeout_response.json["error"])
        self.assertEqual(invalid_json_response.status_code, 502)
        self.assertIn("unreadable response", invalid_json_response.json["error"])


if __name__ == "__main__":
    unittest.main()
