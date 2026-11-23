import io
import json
import unittest
from pathlib import Path
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

    def post_skill_gap(self, data, project_response=([], False, None)):
        with patch.object(
            app_module, "fetch_portfolio_projects", return_value=project_response
        ):
            return self.client.post(
                "/api/skill-gap",
                headers={"Authorization": "Bearer test-token"},
                data=data,
                content_type="multipart/form-data",
            )

    def test_home_and_public_config(self):
        page = self.client.get("/")
        config = self.client.get("/api/config")

        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.headers["Cache-Control"], "no-store")
        self.assertIn(b"CareerLens", page.data)
        self.assertIn(b"AI Assistant", page.data)
        self.assertIn(b"R\xc3\xa9sum\xc3\xa9 Feedback", page.data)
        self.assertIn(b"Interview Answers", page.data)
        self.assertIn(b"Ask a Question", page.data)
        self.assertNotIn(b"Career Coach", page.data)
        self.assertNotIn(b"Career AI Studio", page.data)
        self.assertNotIn(b"Community", page.data)
        self.assertNotIn(b"LinkedIn Optimizer", page.data)
        self.assertNotIn(b"assistant-workspace", page.data)
        self.assertIn(b"ai-assist-form", page.data)
        self.assertIn(b"ai-consent", page.data)
        self.assertIn(b'id="candidate-resume"', page.data)
        self.assertIn(b'id="candidate-consent"', page.data)
        self.assertIn(b'id="application-stage-guide"', page.data)
        self.assertIn(b"private hiring notes", page.data.lower())
        self.assertIn(b'name="account_type"', page.data)
        self.assertIn(b'value="job_seeker"', page.data)
        self.assertIn(b'value="job_provider"', page.data)
        self.assertIn(b'id="provider-applicants"', page.data)
        self.assertIn(
            b'value="improve_job_description" data-account-type="job_provider"',
            page.data,
        )
        self.assertIn(
            b'value="resume_feedback" data-account-type="job_seeker"',
            page.data,
        )
        self.assertIn(b'id="browse-jobs"', page.data)
        self.assertIn(b'id="application-materials"', page.data)
        self.assertIn(b'id="application-material-job"', page.data)
        self.assertIn(b'id="application-material-bullets"', page.data)
        self.assertIn(b'id="application-material-cover-letter"', page.data)
        self.assertIn(b'id="sidebar-profile-link" href="#my-profile"', page.data)
        self.assertIn(b'aria-label="Open profile"', page.data)
        self.assertIn(b'id="my-profile" data-page-view data-page-title="My Profile"', page.data)
        self.assertIn(b'id="my-profile-form"', page.data)
        self.assertIn(b'id="my-profile-current-role"', page.data)
        self.assertIn(b'id="my-profile-skills"', page.data)
        self.assertIn(b'id="my-profile-education"', page.data)
        self.assertIn(b'id="my-profile-location"', page.data)
        self.assertIn(b'id="my-profile-phone"', page.data)
        self.assertIn(b'href="#employer-profile" data-account-type="job_provider"', page.data)
        self.assertIn(
            b'id="employer-profile" data-page-view data-page-title="Employer profile"',
            page.data,
        )
        self.assertIn(b'id="employer-profile-form"', page.data)
        self.assertIn(b'id="employer-profile-title"', page.data)
        self.assertIn(b'id="employer-profile-phone"', page.data)
        self.assertIn(b"Your name and job title appear on your published job listings.", page.data)
        my_profile_section = page.data.split(b'id="my-profile" data-page-view', 1)[1].split(
            b'id="interview-prep-workspace"', 1
        )[0]
        self.assertIn(b'id="my-profile-form"', my_profile_section)
        self.assertIn(b'id="portfolio-form"', my_profile_section)
        self.assertIn(b'id="current-skills"', page.data)
        self.assertIn(b"Edit skills in My Profile", page.data)
        self.assertIn(b'id="job-sort"', page.data)
        self.assertIn(b'id="job-profile-guidance"', page.data)
        self.assertIn(b"Profile alignment is based on explicit job skill requirements", page.data)
        self.assertIn(b'id="skill-job-listing"', page.data)
        self.assertIn(b'id="skill-experience"', page.data)
        self.assertIn(b'href="#learning-workspace"', page.data)
        self.assertIn(b'id="learning-resource-list"', page.data)
        self.assertIn(b'id="learning-in-progress-list"', page.data)
        self.assertIn(b'id="learning-completed-list"', page.data)
        self.assertIn(b'id="learning-not-started-list"', page.data)
        self.assertIn(b'id="skill-learning-list"', page.data)
        self.assertIn(b"does not mark a resource complete when you open it", page.data)
        self.assertIn(b'data-nav-account-type="job_seeker">CAREER TOOLS', page.data)
        self.assertIn(b'data-nav-account-type="job_provider">HIRING', page.data)
        self.assertIn(b'id="resend-confirmation"', page.data)
        self.assertEqual(config.status_code, 200)
        self.assertEqual(config.json["supabaseUrl"], "https://example.supabase.co")
        self.assertEqual(config.json["supabaseAnonKey"], "public-key")
        self.assertEqual(config.headers["Cache-Control"], "no-store")

    def test_application_resume_access_requires_the_applicants_storage_folder(self):
        schema_path = Path(__file__).parents[1] / "backend" / "supabase_schema.sql"
        schema = schema_path.read_text(encoding="utf-8")

        self.assertIn(
            "and (storage.foldername(_object_name))[1] = application.applicant_id::text",
            schema,
        )

    def test_private_data_rls_policies_keep_owner_and_role_boundaries(self):
        repository_root = Path(__file__).parents[1]
        schema = (repository_root / "backend" / "supabase_schema.sql").read_text(
            encoding="utf-8"
        )
        learning = (
            repository_root / "backend" / "migrations" / "phase3_learning.sql"
        ).read_text(encoding="utf-8")
        portfolio = (
            repository_root / "backend" / "migrations" / "phase5_portfolio.sql"
        ).read_text(encoding="utf-8")

        for table in (
            "applications",
            "career_profiles",
            "user_accounts",
            "job_listings",
            "job_applications",
            "application_reviews",
            "application_material_drafts",
        ):
            self.assertIn(
                f"alter table public.{table} enable row level security", schema
            )
        for table, sql in (
            ("user_learning_plans", learning),
            ("career_projects", portfolio),
        ):
            self.assertIn(
                f"alter table public.{table} enable row level security", sql
            )
            self.assertIn("(select auth.uid()) = user_id", sql)
            self.assertIn("(select public.is_job_seeker())", sql)

        self.assertIn("(select auth.uid()) = applicant_id", schema)
        self.assertIn("(select public.owns_job_listing(job_id))", schema)
        self.assertIn("provider_id = (select auth.uid())", schema)
        self.assertIn("(select public.owns_job_application(application_id))", schema)

    def test_employer_profile_public_title_stays_separate_from_private_contacts(self):
        repository_root = Path(__file__).parents[1]
        schema = (repository_root / "backend" / "supabase_schema.sql").read_text(
            encoding="utf-8"
        )
        migration = (
            repository_root
            / "backend"
            / "migrations"
            / "phase11_employer_profile.sql"
        ).read_text(encoding="utf-8")

        self.assertIn("recruiter_title text not null default ''", schema)
        self.assertIn("grant update (recruiter_title)", migration)
        self.assertIn("using (account_type = 'job_provider')", migration)
        self.assertIn("(select auth.uid()) = user_id", migration)
        self.assertNotIn("email", migration)
        self.assertNotIn("phone", migration)
        self.assertIn("set public = false", schema)

    def test_config_reports_missing_supabase_values(self):
        with patch.object(app_module, "SUPABASE_URL", ""):
            response = self.client.get("/api/config")

        self.assertEqual(response.status_code, 503)
        self.assertIn("not configured", response.json["error"])

    def test_skill_gap_requires_authentication_and_job_seeker_role(self):
        unauthenticated = self.client.post("/api/skill-gap")
        with patch.object(
            app_module,
            "verify_supabase_job_seeker",
            return_value=("Job seekers only.", 403),
        ):
            provider = self.post_skill_gap({
                "target_role": "Backend Developer",
                "job_description": "This role requires Python and SQL experience.",
            })

        self.assertEqual(unauthenticated.status_code, 401)
        self.assertEqual(provider.status_code, 403)

    def test_skill_gap_validates_input_lengths_and_required_fields(self):
        with patch.object(app_module, "verify_supabase_job_seeker", return_value=None):
            missing = self.post_skill_gap({"target_role": "Developer"})
            too_long = self.post_skill_gap({
                "target_role": "Developer",
                "job_description": "Python " * 2000,
            })

        self.assertEqual(missing.status_code, 400)
        self.assertIn("job description", missing.json["error"].lower())
        self.assertEqual(too_long.status_code, 400)
        self.assertIn("12,000", too_long.json["error"])

    def test_skill_gap_uses_resume_and_experience_with_explainable_results(self):
        with patch.object(app_module, "verify_supabase_job_seeker", return_value=None):
            response = self.post_skill_gap({
                "target_role": "Backend Developer",
                "skills": "SQL, Python",
                "experience": "Built a Flask API with PostgreSQL for a class project.",
                "job_description": "Python, Flask, PostgreSQL, SQL, and Docker experience is required.",
                "resume": (
                    io.BytesIO(create_pdf("Developed Python scripts for data cleanup.")),
                    "resume.pdf",
                ),
            })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["summary"]["total_required_skills"], 5)
        self.assertEqual(response.json["summary"]["skills_with_supporting_evidence"], 3)
        self.assertEqual(response.json["summary"]["needs_assessment"], 1)
        self.assertEqual(response.json["summary"]["no_evidence_found"], 1)
        sql = next(item for item in response.json["skills"] if item["name"] == "SQL")
        self.assertEqual(sql["status"], "Needs assessment")
        docker = next(item for item in response.json["skills"] if item["name"] == "Docker")
        self.assertEqual(docker["status"], "No evidence found")
        self.assertIn("does not mean you lack", docker["explanation"])

    def test_skill_gap_can_analyze_without_resume_or_profile_skills(self):
        with patch.object(app_module, "verify_supabase_job_seeker", return_value=None):
            response = self.post_skill_gap({
                "target_role": "Backend Developer",
                "job_description": "This role requires Python and Docker experience.",
            })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["summary"]["no_evidence_found"], 2)

    def test_skill_gap_rejects_unreadable_or_text_empty_resume(self):
        with patch.object(app_module, "verify_supabase_job_seeker", return_value=None):
            unreadable = self.post_skill_gap({
                "target_role": "Backend Developer",
                "job_description": "Python and Flask experience are required for this role.",
                "resume": (io.BytesIO(b"not a PDF"), "resume.pdf"),
            })
            empty_text = self.post_skill_gap({
                "target_role": "Backend Developer",
                "job_description": "Python and Flask experience are required for this role.",
                "resume": (io.BytesIO(create_pdf("")), "resume.pdf"),
            })

        self.assertEqual(unreadable.status_code, 400)
        self.assertIn("couldn't read", unreadable.json["error"])
        self.assertEqual(empty_text.status_code, 400)
        self.assertIn("No readable text", empty_text.json["error"])

    def test_skill_gap_role_check_uses_authenticated_supabase_rpc(self):
        rpc_response = MagicMock()
        rpc_response.__enter__.return_value = rpc_response
        rpc_response.read.return_value = b"true"
        with app_module.app.test_request_context(
            headers={"Authorization": "Bearer seeker-session"}
        ), patch.object(
            app_module, "verify_supabase_user", return_value=(True, None)
        ), patch(
            "backend.app.urlopen", return_value=rpc_response
        ) as supabase_request:
            result = app_module.verify_supabase_job_seeker()

        self.assertIsNone(result)
        request = supabase_request.call_args.args[0]
        self.assertTrue(request.full_url.endswith("/rest/v1/rpc/is_job_seeker"))
        self.assertEqual(request.get_header("Authorization"), "Bearer seeker-session")

    def test_skill_gap_role_check_rejects_non_seeker_rpc_result(self):
        rpc_response = MagicMock()
        rpc_response.__enter__.return_value = rpc_response
        rpc_response.read.return_value = b"false"
        with app_module.app.test_request_context(
            headers={"Authorization": "Bearer provider-session"}
        ), patch.object(
            app_module, "verify_supabase_user", return_value=(True, None)
        ), patch(
            "backend.app.urlopen", return_value=rpc_response
        ):
            result = app_module.verify_supabase_job_seeker()

        self.assertEqual(result[1], 403)

    def test_job_recommendations_require_a_job_seeker_session(self):
        unauthenticated = self.client.get("/api/job-recommendations")
        role_error = ({"error": "Job seekers only."}, 403)
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=role_error
        ), patch.object(app_module, "supabase_rest_request") as proxy:
            provider = self.client.get(
                "/api/job-recommendations",
                headers={"Authorization": "******"},
            )

        self.assertEqual(unauthenticated.status_code, 401)
        self.assertEqual(provider.status_code, 403)
        proxy.assert_not_called()

    def test_job_recommendations_load_private_profile_and_published_jobs(self):
        profile = [{
            "target_role": "Backend Developer",
            "headline": "",
            "about": "Built a Python API for a course project.",
            "skills": ["Python"],
        }]
        jobs = [{
            "id": "job-1",
            "title": "Backend Developer",
            "company": "Example",
            "description": "Required: Python. Preferred: Docker.",
            "requirements": "",
            "created_at": "2026-01-01T00:00:00Z",
        }]
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(
            app_module,
            "supabase_rest_request",
            side_effect=[(200, profile), (200, []), (200, jobs), (200, [])],
        ) as proxy:
            response = self.client.get(
                "/api/job-recommendations",
                headers={"Authorization": "******"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["jobs"][0]["id"], "job-1")
        self.assertEqual(response.json["jobs"][0]["match"]["score"], 80)
        self.assertTrue(response.json["jobs"][0]["match"]["relevant_evidence"])
        self.assertIn("career_profiles?", proxy.call_args_list[0].args[0])
        self.assertIn("career_projects?", proxy.call_args_list[1].args[0])
        self.assertIn("status=eq.published", proxy.call_args_list[2].args[0])
        self.assertIn("user_learning_plans?", proxy.call_args_list[3].args[0])
        self.assertEqual(
            proxy.call_args_list[0].args[0],
            "career_profiles?select=target_role,headline,about,skills",
        )

    def test_authenticated_supabase_proxy_forwards_the_current_bearer_token(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.read.return_value = b"[]"
        with app_module.app.test_request_context(
            headers={"Authorization": "Bearer user-session-token"}
        ), patch.object(
            app_module, "urlopen", return_value=response
        ) as supabase_request:
            status, payload = app_module.supabase_rest_request(
                "career_profiles?select=skills"
            )

        forwarded_request = supabase_request.call_args.args[0]
        self.assertEqual(status, 200)
        self.assertEqual(payload, [])
        self.assertEqual(
            forwarded_request.full_url,
            "https://example.supabase.co/rest/v1/career_profiles?select=skills",
        )
        self.assertEqual(
            forwarded_request.get_header("Authorization"),
            "Bearer user-session-token",
        )
        self.assertEqual(forwarded_request.get_header("Apikey"), "public-key")

    def test_job_recommendations_handle_empty_profiles_and_jobs(self):
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(
            app_module,
            "supabase_rest_request",
            side_effect=[(200, []), (200, []), (200, []), (200, [])],
        ):
            response = self.client.get(
                "/api/job-recommendations",
                headers={"Authorization": "******"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["jobs"], [])
        self.assertFalse(response.json["profile"]["complete"])

    def test_job_recommendations_use_learning_plans_without_claiming_mastery(self):
        profile = [{
            "target_role": "Backend Developer",
            "headline": "",
            "about": "",
            "skills": ["Python"],
        }]
        jobs = [{
            "id": "job-1",
            "title": "Backend Developer",
            "company": "Example",
            "description": "Required: Python. Preferred: Docker.",
            "requirements": "",
        }]
        learning_records = [{
            "status": "completed",
            "resource": {
                "title": "Docker Foundations",
                "skill_tags": ["Docker"],
            },
        }]
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(
            app_module,
            "supabase_rest_request",
            side_effect=[
                (200, profile),
                (200, []),
                (200, jobs),
                (200, learning_records),
            ],
        ):
            response = self.client.get(
                "/api/job-recommendations",
                headers={"Authorization": "******"},
            )

        match = response.json["jobs"][0]["match"]
        docker = match["preferred_skills"][0]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(docker["status"], "Needs assessment")
        self.assertEqual(
            docker["evidence"][0]["source"],
            "Learning plan (self-reported)",
        )
        self.assertIn("not verified skill proficiency", docker["evidence"][0]["excerpt"])

    def test_portfolio_projects_are_validated_and_saved_without_client_owner_ids(self):
        project = {
            "id": "project-id",
            "title": "API project",
            "description": "A small API project.",
            "skills": ["Python", "SQL"],
            "contribution": "Built and tested API routes.",
            "project_url": "https://example.com/project",
            "started_on": "2025-01-01",
            "completed_on": "2025-02-01",
        }
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(
            app_module, "supabase_rest_request", return_value=(201, [project])
        ) as proxy:
            response = self.client.post(
                "/api/portfolio/projects",
                headers={"Authorization": "******"},
                json={key: value for key, value in project.items() if key != "id"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, [project])
        self.assertEqual(proxy.call_args.args[0], "career_projects")
        self.assertEqual(proxy.call_args.kwargs["method"], "POST")
        self.assertEqual(
            proxy.call_args.kwargs["payload"]["skills"], ["Python", "SQL"]
        )
        self.assertNotIn("user_id", proxy.call_args.kwargs["payload"])

    def test_portfolio_projects_reject_invalid_urls_dates_and_unexpected_fields(self):
        valid = {
            "title": "API project",
            "description": "A small API project.",
            "skills": ["Python"],
            "contribution": "",
            "project_url": "",
            "started_on": None,
            "completed_on": None,
        }
        invalid_payloads = [
            {**valid, "project_url": "javascript:alert(1)"},
            {**valid, "completed_on": "2024-01-01", "started_on": "2025-01-01"},
            {**valid, "user_id": "untrusted"},
        ]
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(app_module, "supabase_rest_request") as proxy:
            responses = [
                self.client.post(
                    "/api/portfolio/projects",
                    headers={"Authorization": "******"},
                    json=payload,
                )
                for payload in invalid_payloads
            ]

        self.assertTrue(all(response.status_code == 400 for response in responses))
        proxy.assert_not_called()

    def test_portfolio_updates_and_deletes_are_scoped_to_the_validated_project_id(self):
        project_id = "00000000-0000-0000-0000-000000000001"
        project = {
            "title": "API project",
            "description": "A small API project.",
            "skills": ["Python"],
            "contribution": "",
            "project_url": "",
            "started_on": None,
            "completed_on": None,
        }
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(
            app_module,
            "supabase_rest_request",
            side_effect=[(200, [project]), (200, [project])],
        ) as proxy:
            updated = self.client.patch(
                f"/api/portfolio/projects/{project_id}",
                headers={"Authorization": "Bearer test-token"},
                json=project,
            )
            deleted = self.client.delete(
                f"/api/portfolio/projects/{project_id}",
                headers={"Authorization": "Bearer test-token"},
            )
            invalid_id = self.client.delete(
                "/api/portfolio/projects/not-a-uuid",
                headers={"Authorization": "Bearer test-token"},
            )

        self.assertEqual(updated.status_code, 200)
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(invalid_id.status_code, 400)
        self.assertEqual(
            proxy.call_args_list[0].args[0],
            f"career_projects?id=eq.{project_id}",
        )
        self.assertEqual(proxy.call_args_list[0].kwargs["method"], "PATCH")
        self.assertEqual(
            proxy.call_args_list[1].args[0],
            f"career_projects?id=eq.{project_id}",
        )
        self.assertEqual(proxy.call_args_list[1].kwargs["method"], "DELETE")

    def test_portfolio_project_api_requires_job_seeker_and_reports_missing_migration(self):
        role_error = ({"error": "Job seekers only."}, 403)
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=role_error
        ), patch.object(app_module, "supabase_rest_request") as proxy:
            forbidden = self.client.get(
                "/api/portfolio/projects",
                headers={"Authorization": "******"},
            )
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(
            app_module,
            "supabase_rest_request",
            return_value=(404, {"code": "PGRST205"}),
        ):
            missing = self.client.get(
                "/api/portfolio/projects",
                headers={"Authorization": "******"},
            )

        self.assertEqual(forbidden.status_code, 403)
        proxy.assert_not_called()
        self.assertEqual(missing.status_code, 503)
        self.assertIn("phase5_portfolio.sql", missing.json["error"])

    def test_job_recommendations_continue_when_optional_learning_tables_are_missing(self):
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(
            app_module,
            "supabase_rest_request",
            side_effect=[
                (200, []),
                (200, []),
                (200, []),
                (400, {"code": "PGRST205"}),
            ],
        ):
            response = self.client.get(
                "/api/job-recommendations",
                headers={"Authorization": "******"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json["profile"]["learning_records_available"])

    def test_job_recommendations_surface_schema_and_database_errors(self):
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(
            app_module,
            "supabase_rest_request",
            return_value=(400, {"code": "PGRST205"}),
        ):
            schema_error = self.client.get(
                "/api/job-recommendations",
                headers={"Authorization": "******"},
            )
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(
            app_module,
            "supabase_rest_request",
            return_value=(503, {"code": "SERVICE_UNAVAILABLE"}),
        ):
            service_error = self.client.get(
                "/api/job-recommendations",
                headers={"Authorization": "******"},
            )

        self.assertEqual(schema_error.status_code, 503)
        self.assertIn("supabase_schema.sql", schema_error.json["error"])
        self.assertEqual(service_error.status_code, 503)
        self.assertIn("temporarily unavailable", service_error.json["error"])

    def test_learning_catalogue_and_plan_require_a_job_seeker_session(self):
        unauthenticated = self.client.get("/api/learning/resources")
        role_error = ({"error": "Job seekers only."}, 403)
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=role_error
        ), patch.object(app_module, "learning_supabase_request") as supabase_request:
            provider = self.client.get(
                "/api/learning/plan",
                headers={"Authorization": "Bearer provider-token"},
            )

        self.assertEqual(unauthenticated.status_code, 401)
        self.assertEqual(provider.status_code, 403)
        supabase_request.assert_not_called()

    def test_learning_catalogue_and_plan_are_loaded_through_authenticated_proxy(self):
        resources = [{
            "id": "resource-id",
            "title": "Verified SQL documentation",
            "skill_tags": ["SQL"],
        }]
        plan = [{
            "id": "plan-id",
            "resource_id": "resource-id",
            "status": "in_progress",
            "resource": resources[0],
        }]
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(
            app_module,
            "learning_supabase_request",
            side_effect=[(200, resources), (200, plan)],
        ) as proxy:
            catalogue_response = self.client.get(
                "/api/learning/resources",
                headers={"Authorization": "Bearer seeker-token"},
            )
            plan_response = self.client.get(
                "/api/learning/plan",
                headers={"Authorization": "Bearer seeker-token"},
            )

        self.assertEqual(catalogue_response.status_code, 200)
        self.assertEqual(catalogue_response.json, resources)
        self.assertEqual(plan_response.status_code, 200)
        self.assertEqual(plan_response.json, plan)
        self.assertIn("is_active=eq.true", proxy.call_args_list[0].args[0])
        self.assertEqual(proxy.call_args_list[1].args[0], (
            "user_learning_plans?select=id,resource_id,status,"
            "target_completion_date,created_at,updated_at,"
            "resource:learning_resources(id,title,description,provider,"
            "resource_url,difficulty,resource_type,skill_tags,objectives,"
            "category:learning_categories(name,slug))"
            "&order=updated_at.desc"
        ))

    def test_empty_learning_catalogue_and_plan_return_real_empty_lists(self):
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(
            app_module,
            "learning_supabase_request",
            side_effect=[(200, []), (200, [])],
        ):
            catalogue = self.client.get(
                "/api/learning/resources",
                headers={"Authorization": "Bearer seeker-token"},
            )
            plan = self.client.get(
                "/api/learning/plan",
                headers={"Authorization": "Bearer seeker-token"},
            )

        self.assertEqual(catalogue.status_code, 200)
        self.assertEqual(catalogue.json, [])
        self.assertEqual(plan.status_code, 200)
        self.assertEqual(plan.json, [])

    def test_learning_database_failures_are_reported_without_provider_details(self):
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(
            app_module,
            "learning_supabase_request",
            return_value=(503, {"code": "SERVICE_UNAVAILABLE", "details": "private"}),
        ):
            response = self.client.get(
                "/api/learning/plan",
                headers={"Authorization": "Bearer seeker-token"},
            )

        self.assertEqual(response.status_code, 502)
        self.assertIn("temporarily unavailable", response.json["error"])
        self.assertNotIn("private", response.get_data(as_text=True))

    def test_learning_workspace_reports_when_manual_migration_is_missing(self):
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(
            app_module,
            "learning_supabase_request",
            return_value=(404, {"code": "PGRST205", "message": "database detail"}),
        ):
            response = self.client.get(
                "/api/learning/resources",
                headers={"Authorization": "Bearer seeker-token"},
            )

        self.assertEqual(response.status_code, 503)
        self.assertIn("phase3_learning.sql", response.json["error"])
        self.assertNotIn("database detail", response.get_data(as_text=True))

    def test_learning_recommendations_match_catalogue_tags_to_unverified_needs(self):
        resources = [
            {
                "id": "docker-resource",
                "title": "Containers overview",
                "skill_tags": ["Docker"],
            },
            {
                "id": "python-resource",
                "title": "Python overview",
                "skill_tags": ["Python"],
            },
        ]
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(
            app_module, "learning_supabase_request", return_value=(200, resources)
        ):
            response = self.client.post(
                "/api/learning/recommendations",
                headers={"Authorization": "Bearer seeker-token"},
                json={
                    "skills": [
                        {"name": "Docker", "status": "No evidence found"},
                        {"name": "Python", "status": "Demonstrated"},
                    ]
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json), 1)
        self.assertEqual(response.json[0]["id"], "docker-resource")
        self.assertEqual(response.json[0]["matched_skills"], ["Docker"])

    def test_learning_recommendations_validate_assessment_input(self):
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(app_module, "learning_supabase_request") as proxy:
            response = self.client.post(
                "/api/learning/recommendations",
                headers={"Authorization": "Bearer seeker-token"},
                json={"skills": [{"name": "SQL", "status": "confirmed weak"}]},
            )
            malformed = self.client.post(
                "/api/learning/recommendations",
                headers={"Authorization": "Bearer seeker-token"},
                json={"skills": [{"name": "SQL", "status": []}]},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(malformed.status_code, 400)
        proxy.assert_not_called()

    def test_learning_plan_add_validates_and_creates_only_allowed_fields(self):
        resource_id = "63d0cc2a-a48b-4e42-9ed1-26579a0678c3"
        created_plan = [{"id": "plan-id", "resource_id": resource_id}]
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(
            app_module,
            "learning_supabase_request",
            return_value=(201, created_plan),
        ) as proxy:
            response = self.client.post(
                "/api/learning/plan",
                headers={"Authorization": "Bearer seeker-token"},
                json={
                    "resource_id": resource_id,
                    "status": "in_progress",
                    "target_completion_date": "2027-01-15",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, created_plan)
        self.assertEqual(proxy.call_args.kwargs["method"], "POST")
        self.assertEqual(proxy.call_args.kwargs["payload"], {
            "resource_id": resource_id,
            "status": "in_progress",
            "target_completion_date": "2027-01-15",
        })

        for invalid_payload in (
            {"resource_id": "not-a-uuid"},
            {"resource_id": resource_id, "status": "verified"},
            {"resource_id": resource_id, "target_completion_date": "tomorrow"},
            {"resource_id": resource_id, "user_id": "another-user"},
            {"resource_id": resource_id, "status": []},
        ):
            with patch.object(
                app_module, "verify_supabase_job_seeker", return_value=None
            ), patch.object(app_module, "learning_supabase_request") as invalid_proxy:
                invalid_response = self.client.post(
                    "/api/learning/plan",
                    headers={"Authorization": "Bearer seeker-token"},
                    json=invalid_payload,
                )
            self.assertEqual(invalid_response.status_code, 400)
            invalid_proxy.assert_not_called()

    def test_learning_plan_rejects_duplicate_and_unknown_resources(self):
        resource_id = "63d0cc2a-a48b-4e42-9ed1-26579a0678c3"
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(
            app_module,
            "learning_supabase_request",
            return_value=(409, {"code": "23505"}),
        ):
            duplicate = self.client.post(
                "/api/learning/plan",
                headers={"Authorization": "Bearer seeker-token"},
                json={"resource_id": resource_id},
            )
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(
            app_module,
            "learning_supabase_request",
            return_value=(400, {"code": "23503"}),
        ):
            unknown = self.client.post(
                "/api/learning/plan",
                headers={"Authorization": "Bearer seeker-token"},
                json={"resource_id": resource_id},
            )

        self.assertEqual(duplicate.status_code, 409)
        self.assertIn("already", duplicate.json["error"])
        self.assertEqual(unknown.status_code, 404)
        self.assertIn("unavailable", unknown.json["error"])

    def test_learning_plan_updates_and_removes_only_the_selected_user_item(self):
        plan_id = "63d0cc2a-a48b-4e42-9ed1-26579a0678c3"
        updated = [{"id": plan_id, "status": "completed"}]
        removed = [{"id": plan_id}]
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(
            app_module,
            "learning_supabase_request",
            side_effect=[(200, updated), (200, removed)],
        ) as proxy:
            update_response = self.client.patch(
                f"/api/learning/plan/{plan_id}",
                headers={"Authorization": "Bearer seeker-token"},
                json={"status": "completed", "target_completion_date": None},
            )
            delete_response = self.client.delete(
                f"/api/learning/plan/{plan_id}",
                headers={"Authorization": "Bearer seeker-token"},
            )

        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(proxy.call_args_list[0].args[0], f"user_learning_plans?id=eq.{plan_id}")
        self.assertEqual(proxy.call_args_list[0].kwargs["method"], "PATCH")
        self.assertEqual(proxy.call_args_list[1].kwargs["method"], "DELETE")

    def test_learning_plan_missing_or_malformed_ids_are_reported(self):
        valid_id = "63d0cc2a-a48b-4e42-9ed1-26579a0678c3"
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(
            app_module, "learning_supabase_request", return_value=(200, [])
        ):
            missing = self.client.patch(
                f"/api/learning/plan/{valid_id}",
                headers={"Authorization": "Bearer seeker-token"},
                json={"status": "in_progress"},
            )
            malformed = self.client.delete(
                "/api/learning/plan/not-a-uuid",
                headers={"Authorization": "Bearer seeker-token"},
            )

        self.assertEqual(missing.status_code, 404)
        self.assertEqual(malformed.status_code, 400)

    def test_learning_migration_enforces_private_plans_and_admin_catalogue(self):
        migration_path = Path(__file__).parents[1] / "backend" / "migrations" / "phase3_learning.sql"
        migration = migration_path.read_text(encoding="utf-8")
        self.assertIn("constraint user_learning_plans_one_resource unique (user_id, resource_id)", migration)
        self.assertIn("(select auth.uid()) = user_id", migration)
        self.assertIn("(select public.is_job_seeker())", migration)
        self.assertIn("revoke all on public.learning_resources from anon, authenticated", migration)
        self.assertIn("grant update (status, target_completion_date)", migration)
        self.assertNotIn("insert into public.learning_resources", migration.lower())

    def test_verified_resource_seed_is_rerunnable_and_keeps_client_writes_disabled(self):
        migration_path = (
            Path(__file__).parents[1]
            / "backend"
            / "migrations"
            / "phase12_verified_resources.sql"
        )
        migration = migration_path.read_text(encoding="utf-8")
        self.assertIn("on conflict (slug) do update", migration)
        self.assertIn("where not exists", migration)
        self.assertIn("https://docs.python.org/3/tutorial/", migration)
        self.assertIn("https://docs.docker.com/learn/", migration)
        self.assertIn("https://www.typescriptlang.org/docs/handbook/intro.html", migration)
        self.assertIn("https://sqlbolt.com/", migration)
        self.assertIn("https://docs.cypress.io/app/get-started/why-cypress", migration)
        self.assertIn("https://docs.oracle.com/javase/tutorial/", migration)
        self.assertIn("https://kubernetes.io/docs/tutorials/kubernetes-basics/", migration)
        self.assertIn("https://playwright.dev/docs/intro", migration)
        self.assertIn("https://owasp.org/www-project-web-security-testing-guide/", migration)
        self.assertIn("('data-structures-algorithms', 'Data structures and algorithms')", migration)
        self.assertIn("('system-design', 'System design')", migration)
        self.assertIn("('data-science', 'Data science')", migration)
        self.assertIn("('artificial-intelligence', 'Artificial intelligence')", migration)
        self.assertIn("('machine-learning', 'Machine learning')", migration)
        self.assertIn("https://developers.google.com/machine-learning/crash-course", migration)
        self.assertIn("https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/", migration)
        self.assertIn("notify pgrst, 'reload schema'", migration)

    def test_learning_policy_repair_uses_security_definer_helpers(self):
        migration_path = (
            Path(__file__).parents[1]
            / "backend"
            / "migrations"
            / "phase13_learning_policy_fix.sql"
        )
        migration = migration_path.read_text(encoding="utf-8")
        self.assertIn("security definer", migration)
        self.assertIn("saved_learning_resource", migration)
        self.assertIn("active_learning_resource", migration)
        self.assertNotIn("exists (\n                select 1\n                from public.user_learning_plans", migration)
        self.assertIn("notify pgrst, 'reload schema'", migration)

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

    def test_application_materials_require_explicit_consent_and_valid_job_id(self):
        with patch.object(app_module, "verify_supabase_job_seeker", return_value=None):
            no_consent = self.client.post(
                "/api/application-materials",
                headers={"Authorization": "Bearer valid-session"},
                json={"job_id": "00000000-0000-0000-0000-000000000001", "consent": False},
            )
            invalid_job = self.client.post(
                "/api/application-materials",
                headers={"Authorization": "Bearer valid-session"},
                json={"job_id": "not-a-uuid", "consent": True},
            )

        self.assertEqual(no_consent.status_code, 400)
        self.assertIn("Confirm", no_consent.json["error"])
        self.assertEqual(invalid_job.status_code, 400)
        self.assertIn("valid identifier", invalid_job.json["error"])

    def test_retired_feature_routes_are_not_exposed(self):
        for path in ("/api/analyze-resume", "/api/community/posts"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 404, path)

    def test_community_removal_migration_is_review_only_and_rerunnable(self):
        repository_root = Path(__file__).parents[1]
        migration = (
            repository_root
            / "backend"
            / "migrations"
            / "phase17_remove_community.sql"
        ).read_text(encoding="utf-8")

        self.assertIn("drop table if exists public.community_posts cascade", migration.lower())
        self.assertIn("drop policy if exists", migration.lower())
        self.assertIn("notify pgrst, 'reload schema'", migration.lower())
        self.assertIn("run manually in supabase after review", migration.lower())
        self.assertNotIn("service_role", migration.lower())

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
            short_coaching_question = self.post_ai_assist({
                **valid,
                "task": "ask_question",
                "text": "?",
            })
            long_text = self.post_ai_assist({**valid, "text": "x" * 8001})
            long_role = self.post_ai_assist({**valid, "role": "x" * 121})

        self.assertEqual(invalid_task.status_code, 400)
        self.assertEqual(short_text.status_code, 400)
        self.assertEqual(short_coaching_question.status_code, 400)
        self.assertEqual(long_text.status_code, 400)
        self.assertEqual(long_role.status_code, 400)
        self.assertEqual(self.auth_urlopen.call_count, 5)

    def test_ai_assist_restricts_employer_tasks_to_job_providers(self):
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
                "verify_supabase_job_provider",
                return_value=({"error": "Job providers only."}, 403),
            ) as verify_provider,
            patch.object(app_module, "urlopen") as provider_request,
        ):
            response = self.post_ai_assist(payload)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json["error"], "Job providers only.")
        verify_provider.assert_called_once()
        self.assertEqual(provider_request.call_count, 1)
        self.assertIn("/auth/v1/user", provider_request.call_args.args[0].full_url)

    def test_job_provider_role_check_uses_supabase_rpc_and_denies_non_providers(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b"false"
        with app_module.app.test_request_context(
            headers={"Authorization": "Bearer test-token"}
        ), patch.object(
            app_module, "urlopen", return_value=response
        ) as supabase_request:
            denied = app_module.verify_supabase_job_provider()

        request = supabase_request.call_args.args[0]
        self.assertEqual(denied[1], 403)
        self.assertIn("job provider accounts", denied[0].get_json()["error"])
        self.assertEqual(
            request.full_url,
            "https://example.supabase.co/rest/v1/rpc/is_job_provider",
        )
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-token")

    def test_ai_assist_allows_authorized_provider_employer_tasks(self):
        provider_response = MagicMock()
        provider_response.__enter__.return_value = provider_response
        provider_response.read.return_value = (
            b'{"status":"completed","steps":[{"type":"model_output","content":'
            b'[{"type":"text","text":"Use consistent role-related questions."}]}]}'
        )
        payload = {
            "task": "improve_job_description",
            "role": "Backend Developer",
            "text": "A job description with enough detail to get useful feedback.",
            "consent": True,
        }
        with (
            patch.object(app_module, "GEMINI_API_KEY", "test-key"),
            patch.object(
                app_module, "verify_supabase_job_provider", return_value=None
            ) as verify_provider,
            patch.object(
                app_module,
                "urlopen",
                side_effect=[self.auth_urlopen.return_value, provider_response],
            ),
        ):
            response = self.post_ai_assist(payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json["answer"], "Use consistent role-related questions."
        )
        verify_provider.assert_called_once()

    def test_ai_assist_accepts_a_short_consented_question(self):
        provider_response = MagicMock()
        provider_response.__enter__.return_value = provider_response
        provider_response.read.return_value = (
            b'{"status":"completed","steps":[{"type":"model_output","content":'
            b'[{"type":"text","text":"Start with one small step."}]}]}'
        )
        payload = {
            "task": "ask_question",
            "role": "Career guidance",
            "text": "I feel stuck.",
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
        self.assertEqual(response.json["answer"], "Start with one small step.")
        prompt = json.loads(urlopen_mock.call_args_list[1].args[0].data)["input"]
        self.assertIn("Answer the user's actual question directly", prompt)
        self.assertIn(payload["text"], prompt)

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

    def test_ai_assist_retries_transient_provider_unavailability(self):
        transient_error = HTTPError(
            "https://generativelanguage.googleapis.com/",
            503,
            "Service Unavailable",
            {},
            io.BytesIO(b'{"error":"temporarily unavailable"}'),
        )
        provider_response = MagicMock()
        provider_response.__enter__.return_value = provider_response
        provider_response.read.return_value = (
            b'{"status":"completed","steps":[{"type":"model_output","content":'
            b'[{"type":"text","text":"Try this revised summary."}]}]}'
        )
        payload = {
            "task": "resume_feedback",
            "role": "Product Designer",
            "text": "Current role: Product Designer. Skills: prototyping and user research.",
            "consent": True,
        }
        with (
            patch.object(app_module, "GEMINI_API_KEY", "server-only-test-key"),
            patch.object(
                app_module,
                "urlopen",
                side_effect=[
                    self.auth_urlopen.return_value,
                    transient_error,
                    provider_response,
                ],
            ) as urlopen_mock,
            patch.object(app_module.time, "sleep") as sleep_mock,
        ):
            response = self.post_ai_assist(payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["answer"], "Try this revised summary.")
        sleep_mock.assert_called_once_with(1)
        self.assertEqual(urlopen_mock.call_count, 3)

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
                app_module, "verify_supabase_job_provider", return_value=None
            ),
            patch.object(
                app_module,
                "urlopen",
                side_effect=[
                    self.auth_urlopen.return_value,
                    rate_limit,
                    rate_limit,
                    rate_limit,
                ],
            ),
            patch.object(app_module.time, "sleep") as sleep_mock,
        ):
            response = self.post_ai_assist(payload)

        self.assertEqual(response.status_code, 503)
        self.assertIn("temporarily busy", response.json["error"])
        self.assertNotIn("private provider details", response.get_data(as_text=True))
        self.assertEqual(sleep_mock.call_count, 2)

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
