from datetime import datetime, timedelta, timezone
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
        with app_module._GEMINI_RATE_LIMIT_LOCK:
            app_module._GEMINI_RATE_LIMIT_WINDOWS.clear()
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
        response.read.return_value = b'{"id":"11111111-1111-4111-8111-111111111111"}'
        self.auth_request = patch("backend.app.urlopen", return_value=response)
        self.auth_urlopen = self.auth_request.start()
        self.addCleanup(self.auth_request.stop)

    def post_interview_prep(self, payload):
        with patch.object(app_module, "verify_supabase_job_seeker", return_value=None):
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
        self.assertIn(b'id="provider-response-summary"', page.data)
        self.assertIn(b'id="provider-listing-status-filter"', page.data)
        self.assertIn(b'id="provider-applicant-search"', page.data)
        self.assertIn(b'id="job-application-response-metrics"', page.data)
        self.assertIn(b'href="#star-story-bank"', page.data)
        self.assertIn(b'id="star-story-form"', page.data)
        self.assertIn(b"not sent to Gemini", page.data)
        self.assertIn(b'not a hiring score or a hiring recommendation', page.data)
        self.assertIn(b'id="provider-applicant-board"', page.data)
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
        self.assertIn(b'id="job-location-filter"', page.data)
        self.assertIn(b'id="job-match-filter"', page.data)
        self.assertIn(b'id="application-sort"', page.data)
        self.assertIn(b'id="dashboard-profile-checklist"', page.data)
        self.assertIn(b'id="dashboard-application-statuses"', page.data)
        self.assertIn(b'id="skill-evidence-found-list"', page.data)
        self.assertIn(b'id="skill-needs-assessment-list"', page.data)
        self.assertIn(b'id="skill-no-evidence-list"', page.data)
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
        review_policy = schema.split(
            "alter table public.application_reviews enable row level security", 1
        )[1].split(
            "drop trigger if exists set_application_review_updated_at", 1
        )[0]
        self.assertIn("Providers can view reviews for their applications", review_policy)
        self.assertIn("provider_id = (select auth.uid())", review_policy)
        self.assertNotIn("Applicants can view", review_policy)

    def test_saved_jobs_migration_has_owner_scoped_rls(self):
        migration = (
            Path(__file__).parents[1]
            / "backend"
            / "migrations"
            / "phase18_saved_jobs.sql"
        ).read_text(encoding="utf-8")

        self.assertIn("create table if not exists public.saved_jobs", migration)
        self.assertIn("alter table public.saved_jobs enable row level security", migration)
        self.assertIn("user_id = (select auth.uid())", migration)
        self.assertIn("(select public.is_job_seeker())", migration)
        self.assertIn("create policy \"Job seekers can view their saved jobs\"", migration)
        self.assertIn("create policy \"Job seekers can save jobs\"", migration)
        self.assertIn("create policy \"Job seekers can remove saved jobs\"", migration)

    def test_star_story_migration_limits_access_and_text_to_the_owner(self):
        migration = (
            Path(__file__).parents[1]
            / "backend"
            / "migrations"
            / "phase25_star_story_bank.sql"
        ).read_text(encoding="utf-8")

        self.assertIn("create table if not exists public.star_stories", migration)
        self.assertIn("alter table public.star_stories enable row level security", migration)
        self.assertIn("user_id = (select auth.uid())", migration)
        self.assertNotIn("is_job_provider", migration)
        self.assertIn("(select public.is_job_seeker())", migration)
        self.assertIn("for select", migration)
        self.assertIn("for insert", migration)
        self.assertIn("for update", migration)
        self.assertIn("for delete", migration)
        self.assertIn("star_stories_total_text_limit", migration)
        self.assertIn("star_story_skill_tags_valid", migration)
        self.assertIn("notify pgrst, 'reload schema'", migration)
        policies = migration.split(
            "alter table public.star_stories enable row level security", 1
        )[1].split("revoke all on public.star_stories", 1)[0]
        self.assertEqual(policies.count("(select auth.uid())"), 5)
        self.assertEqual(policies.count("(select public.is_job_seeker())"), 5)

    def test_employer_response_migration_exposes_only_thresholded_aggregates(self):
        migration = (
            Path(__file__).parents[1]
            / "backend"
            / "migrations"
            / "phase26_employer_response_transparency.sql"
        ).read_text(encoding="utf-8")

        self.assertIn("create index if not exists application_status_events_app_response_idx", migration)
        self.assertIn("create or replace function public.get_job_responsiveness", migration)
        self.assertIn("create or replace function public.get_provider_response_metrics", migration)
        self.assertIn("Listing providers can view their application status history", migration)
        self.assertIn("(select public.is_job_provider())", migration)
        self.assertIn("(select public.owns_job_listing(application.job_id))", migration)
        self.assertIn("listing.status = 'published'", migration)
        self.assertIn("listing.provider_id = auth.uid()", migration)
        self.assertIn("where listing.provider_id = auth.uid()", migration)
        self.assertIn("revoke all on public.application_status_events from public, anon, authenticated", migration)
        self.assertIn("grant select on public.application_status_events to authenticated", migration)
        self.assertNotIn("for insert to authenticated", migration)
        self.assertNotIn("for update to authenticated", migration)
        self.assertEqual(migration.count("security definer"), 2)
        self.assertEqual(migration.count("set search_path = ''"), 2)
        self.assertEqual(migration.count("sample_size, 0) >= 5"), 3)
        self.assertEqual(migration.count("percentile_cont(0.5)"), 2)
        self.assertIn("'Rejected'", migration)
        self.assertNotIn("'Withdrawn'", migration)
        self.assertIn("grant execute on function public.get_job_responsiveness(uuid)", migration)
        self.assertIn("grant execute on function public.get_provider_response_metrics()", migration)
        self.assertIn("notify pgrst, 'reload schema';", migration)
        self.assertNotIn("applicant_name", migration)
        self.assertNotIn("applicant_email", migration)

    def test_application_status_history_migration_is_applicant_scoped_and_audits_changes(self):
        migration = (
            Path(__file__).parents[1]
            / "backend"
            / "migrations"
            / "phase19_application_status_history.sql"
        ).read_text(encoding="utf-8")

        self.assertIn("create table if not exists public.application_status_events", migration)
        self.assertIn("alter table public.application_status_events enable row level security", migration)
        self.assertIn("applicant_id = (select auth.uid())", migration)
        self.assertIn("(select public.is_job_seeker())", migration)
        self.assertIn("after insert or update on public.job_applications", migration)
        self.assertIn("status = 'Submitted'", migration)
        self.assertIn("notify pgrst, 'reload schema';", migration)
        self.assertNotIn("for insert to authenticated", migration.split(
            "alter table public.application_status_events enable row level security", 1
        )[1].split("revoke all on public.application_status_events", 1)[0])

    def test_resume_versions_migration_limits_access_to_the_owner_and_selected_application_version(self):
        repository_root = Path(__file__).parents[1]
        migration = (
            repository_root
            / "backend"
            / "migrations"
            / "phase22_resume_versions.sql"
        ).read_text(encoding="utf-8")
        template = (
            repository_root / "backend" / "templates" / "index.html"
        ).read_text(encoding="utf-8")
        script = (
            repository_root / "backend" / "static" / "script.js"
        ).read_text(encoding="utf-8")

        self.assertIn("create table if not exists public.resume_versions", migration)
        self.assertIn("alter table public.resume_versions enable row level security", migration)
        self.assertIn("user_id = (select auth.uid())", migration)
        self.assertIn("(select public.is_job_seeker())", migration)
        self.assertIn("application.resume_version_id = resume_versions.id", migration)
        self.assertIn("(select public.owns_job_listing(application.job_id))", migration)
        self.assertIn("version.user_id = (select auth.uid())", migration)
        self.assertIn("version.storage_path = job_applications.resume_path", migration)
        self.assertIn("char_length(label) <= 100", migration)
        seeker_read_policy = migration.split(
            'create policy "Job seekers can view their résumé versions"', 1
        )[1].split("drop policy", 1)[0]
        self.assertIn("user_id = (select auth.uid())", seeker_read_policy)
        self.assertIn("(select public.is_job_seeker())", seeker_read_policy)
        self.assertIn("notify pgrst, 'reload schema';", migration)
        self.assertIn('id="resume-version-select"', template)
        self.assertIn('name="resume_version_id"', template)
        self.assertIn('id="resume-manager-form"', template)
        self.assertIn('careerApi("/api/resumes"', script)
        self.assertNotIn('from("resume_versions").insert', script)
        self.assertNotIn('.from("application-resumes").upload', script)
        self.assertNotIn('.from("application-resumes").remove', script)
        self.assertIn("resume_version_id: resumeVersionId", script)
        self.assertNotIn("service_role", migration + script)

    def test_resume_management_migration_enforces_owner_limit_and_safe_detachment(self):
        repository_root = Path(__file__).parents[1]
        migration = (
            repository_root
            / "backend"
            / "migrations"
            / "phase28_resume_version_management.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("add column if not exists file_size bigint", migration)
        self.assertIn("file_size between 1 and 5242880", migration)
        self.assertIn("pg_advisory_xact_lock", migration)
        self.assertIn(">= 10", migration)
        self.assertIn('for update to authenticated', migration)
        self.assertIn('for delete to authenticated', migration)
        self.assertIn("on delete set null", (
            repository_root
            / "backend"
            / "migrations"
            / "phase22_resume_versions.sql"
        ).read_text(encoding="utf-8").lower())
        self.assertIn("version.user_id = (select auth.uid())", migration)
        self.assertIn("(select public.is_job_seeker())", migration)
        self.assertIn("count(application.id) >= 5", migration)
        self.assertIn("count(application.id) filter", migration)
        self.assertIn("'Shortlisted', 'Interview', 'Offer', 'Hired'", migration)
        self.assertIn("when count(application.id) >= 5 then round", migration)
        self.assertIn("else null", migration)
        self.assertIn("applications_sent", migration)
        self.assertIn("shortlisted_or_better", migration)
        self.assertIn("notify pgrst, 'reload schema';", migration)
        self.assertNotIn("applicant_email", migration)
        self.assertNotIn("applicant_name", migration)
        self.assertNotIn("applicant_id", migration)

    def test_resume_pdf_upload_requires_pdf_type_size_and_magic_bytes(self):
        file = MagicMock()
        file.filename = "resume.pdf"
        file.mimetype = "application/pdf"
        file.read.return_value = b"%PDF-1.4 example"
        self.assertEqual(app_module.read_pdf_upload(file), b"%PDF-1.4 example")
        file.read.assert_called_once_with(app_module.MAX_FILE_SIZE + 1)

        file.filename = "resume.txt"
        with self.assertRaisesRegex(ValueError, "Only PDF"):
            app_module.read_pdf_upload(file)

        file.filename = "resume.pdf"
        file.mimetype = "text/plain"
        with self.assertRaisesRegex(ValueError, "Only PDF"):
            app_module.read_pdf_upload(file)

        file.mimetype = "application/pdf"
        file.read.return_value = b"x" * (app_module.MAX_FILE_SIZE + 1)
        with self.assertRaisesRegex(ValueError, "5 MB"):
            app_module.read_pdf_upload(file)

        file.read.return_value = b"not a PDF"
        with self.assertRaisesRegex(ValueError, "valid PDF"):
            app_module.read_pdf_upload(file)

    def test_resume_creation_requires_seeker_role_and_validated_upload(self):
        unauthenticated = self.client.post("/api/resumes")
        self.assertEqual(unauthenticated.status_code, 401)

        denied = ({"error": "Job seekers only."}, 403)
        with patch.object(
            app_module,
            "verify_supabase_job_seeker_identity",
            return_value=(None, denied),
        ), patch.object(app_module, "supabase_rest_request") as rest_request:
            response = self.client.post(
                "/api/resumes",
                headers={"Authorization": "Bearer provider-session"},
                data={"label": "Backend v2"},
            )
        self.assertEqual(response.status_code, 403)
        rest_request.assert_not_called()

        user = {"id": "11111111-1111-4111-8111-111111111111"}
        with (
            patch.object(
                app_module,
                "verify_supabase_job_seeker_identity",
                return_value=(user, None),
            ),
            patch.object(app_module, "supabase_rest_request") as rest_request,
            patch.object(app_module, "supabase_storage_request") as storage_request,
        ):
            missing_label = self.client.post(
                "/api/resumes",
                headers={"Authorization": "Bearer seeker-session"},
                data={
                    "resume": (io.BytesIO(create_pdf("Resume")), "resume.pdf", "application/pdf")
                },
            )
            bad_magic = self.client.post(
                "/api/resumes",
                headers={"Authorization": "Bearer seeker-session"},
                data={
                    "label": "Backend v2",
                    "resume": (io.BytesIO(b"not a PDF"), "resume.pdf", "application/pdf"),
                },
            )
        self.assertEqual(missing_label.status_code, 400)
        self.assertEqual(bad_magic.status_code, 400)
        rest_request.assert_not_called()
        storage_request.assert_not_called()

    def test_resume_identity_verification_uses_authenticated_user_and_seeker_role(self):
        auth_response = MagicMock()
        auth_response.__enter__.return_value = auth_response
        auth_response.read.return_value = (
            b'{"id":"11111111-1111-4111-8111-111111111111"}'
        )
        role_response = MagicMock()
        role_response.__enter__.return_value = role_response
        role_response.read.return_value = b"true"
        with app_module.app.test_request_context(
            headers={"Authorization": "Bearer resume-session"}
        ), patch(
            "backend.app.urlopen",
            side_effect=[auth_response, role_response],
        ) as supabase_urlopen:
            user, error = app_module.verify_supabase_job_seeker_identity()

        self.assertIsNone(error)
        self.assertEqual(user["id"], "11111111-1111-4111-8111-111111111111")
        self.assertEqual(supabase_urlopen.call_count, 2)
        self.assertTrue(
            supabase_urlopen.call_args_list[0].args[0].full_url.endswith(
                "/auth/v1/user"
            )
        )
        self.assertTrue(
            supabase_urlopen.call_args_list[1].args[0].full_url.endswith(
                "/rest/v1/rpc/is_job_seeker"
            )
        )
        self.assertEqual(
            supabase_urlopen.call_args_list[1].args[0].get_header("Authorization"),
            "Bearer resume-session",
        )

    def test_resume_creation_uploads_with_current_user_and_records_file_size(self):
        user_id = "11111111-1111-4111-8111-111111111111"
        version_id = "22222222-2222-4222-8222-222222222222"
        expected = {
            "id": version_id,
            "label": "Backend v2",
            "storage_path": f"{user_id}/versions/{version_id}.pdf",
            "file_size": len(create_pdf("Resume")),
            "created_at": "2026-11-24T12:00:00Z",
        }
        with (
            patch.object(
                app_module,
                "verify_supabase_job_seeker_identity",
                return_value=({"id": user_id}, None),
            ),
            patch.object(
                app_module,
                "supabase_rest_request",
                side_effect=[(200, []), (201, [expected])],
            ) as rest_request,
            patch.object(
                app_module,
                "supabase_storage_request",
                return_value=(200, {}),
            ) as storage_request,
            patch.object(app_module.uuid, "uuid4", return_value=version_id),
        ):
            response = self.client.post(
                "/api/resumes",
                headers={"Authorization": "Bearer seeker-session"},
                data={
                    "label": "Backend v2",
                    "resume": (
                        io.BytesIO(create_pdf("Resume")),
                        "resume.pdf",
                        "application/pdf",
                    ),
                },
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["resume"], expected)
        self.assertNotIn("user_id", response.json["resume"])
        self.assertEqual(storage_request.call_args.args[0], "POST")
        self.assertEqual(storage_request.call_args.args[1], expected["storage_path"])
        self.assertEqual(storage_request.call_args.args[2], create_pdf("Resume"))
        insert_payload = rest_request.call_args_list[1].kwargs["payload"]
        self.assertEqual(insert_payload["file_size"], len(create_pdf("Resume")))
        self.assertNotIn("user_id", insert_payload)

    def test_resume_storage_upload_forwards_public_key_and_current_bearer_only(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.read.return_value = b'{"Key":"resume"}'
        with app_module.app.test_request_context(
            headers={"Authorization": "Bearer current-user-token"}
        ), patch("backend.app.urlopen", return_value=response) as storage_urlopen:
            status, payload = app_module.supabase_storage_request(
                "POST",
                "11111111-1111-4111-8111-111111111111/versions/"
                "22222222-2222-4222-8222-222222222222.pdf",
                b"%PDF-1.4",
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"Key": "resume"})
        storage_request = storage_urlopen.call_args.args[0]
        self.assertIn("/storage/v1/object/application-resumes/", storage_request.full_url)
        self.assertEqual(
            storage_request.get_header("Authorization"),
            "Bearer current-user-token",
        )
        self.assertEqual(storage_request.get_header("Apikey"), "public-key")
        self.assertEqual(storage_request.get_header("Content-type"), "application/pdf")
        self.assertEqual(storage_request.data, b"%PDF-1.4")

    def test_resume_list_is_limited_and_returns_only_rls_visible_metadata(self):
        versions = [{
            "id": "22222222-2222-4222-8222-222222222222",
            "label": "Backend v2",
            "storage_path": (
                "11111111-1111-4111-8111-111111111111/versions/"
                "22222222-2222-4222-8222-222222222222.pdf"
            ),
            "file_size": len(create_pdf("Resume")),
            "created_at": "2026-11-24T12:00:00Z",
        }]
        with (
            patch.object(app_module, "verify_supabase_job_seeker", return_value=None),
            patch.object(
                app_module,
                "supabase_rest_request",
                return_value=(200, versions),
            ) as rest_request,
        ):
            response = self.client.get(
                "/api/resumes",
                headers={"Authorization": "Bearer seeker-session"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["resumes"], versions)
        self.assertEqual(response.json["limit"], 10)
        self.assertNotIn("user_id", response.json["resumes"][0])
        self.assertEqual(
            rest_request.call_args.args[0],
            "resume_versions?select=id,label,storage_path,file_size,created_at"
            "&order=created_at.desc&limit=11",
        )

    def test_resume_creation_enforces_ten_version_limit_before_upload(self):
        user_id = "11111111-1111-4111-8111-111111111111"
        versions = [{"id": str(index)} for index in range(10)]
        with (
            patch.object(
                app_module,
                "verify_supabase_job_seeker_identity",
                return_value=({"id": user_id}, None),
            ),
            patch.object(app_module, "supabase_rest_request", return_value=(200, versions)),
            patch.object(app_module, "supabase_storage_request") as storage_request,
        ):
            response = self.client.post(
                "/api/resumes",
                headers={"Authorization": "Bearer seeker-session"},
                data={
                    "label": "Backend v11",
                    "resume": (
                        io.BytesIO(create_pdf("Resume")),
                        "resume.pdf",
                        "application/pdf",
                    ),
                },
            )
        self.assertEqual(response.status_code, 409)
        self.assertIn("10 résumé versions", response.json["error"])
        storage_request.assert_not_called()

    def test_resume_insights_return_aggregates_without_applicant_data(self):
        record = {
            "resume_version_id": "22222222-2222-4222-8222-222222222222",
            "label": "Backend v2",
            "created_at": "2026-11-24T12:00:00Z",
            "applications_sent": 5,
            "shortlisted_or_better": 2,
            "shortlist_rate": 40.0,
            "sufficient_data": True,
        }
        with (
            patch.object(app_module, "verify_supabase_job_seeker", return_value=None),
            patch.object(
                app_module,
                "supabase_rest_request",
                return_value=(200, [record]),
            ) as rest_request,
        ):
            response = self.client.get(
                "/api/resumes/insights",
                headers={"Authorization": "Bearer seeker-session"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["insights"], [record])
        self.assertNotIn("applicant_id", response.get_data(as_text=True))
        self.assertNotIn("applicant_email", response.get_data(as_text=True))
        self.assertEqual(rest_request.call_args.args[0], "rpc/get_resume_version_insights")
        self.assertEqual(rest_request.call_args.kwargs["payload"], {})

        with (
            patch.object(app_module, "verify_supabase_job_seeker", return_value=None),
            patch.object(app_module, "supabase_rest_request", return_value=(200, [])),
        ):
            empty = self.client.get(
                "/api/resumes/insights",
                headers={"Authorization": "Bearer seeker-session"},
            )
        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.json["insights"], [])

    def test_resume_management_endpoints_require_authentication(self):
        version_id = "22222222-2222-4222-8222-222222222222"
        responses = [
            self.client.get("/api/resumes"),
            self.client.post("/api/resumes"),
            self.client.patch(f"/api/resumes/{version_id}", json={"label": "Updated"}),
            self.client.delete(f"/api/resumes/{version_id}"),
            self.client.get("/api/resumes/insights"),
        ]
        self.assertEqual([response.status_code for response in responses], [401] * 5)

    def test_resume_rename_validates_label_and_uses_owner_scoped_update(self):
        version_id = "22222222-2222-4222-8222-222222222222"
        version = {
            "id": version_id,
            "label": "Backend v2",
            "storage_path": "11111111-1111-4111-8111-111111111111/versions/"
            f"{version_id}.pdf",
            "file_size": len(create_pdf("Resume")),
            "created_at": "2026-11-24T12:00:00Z",
        }
        with (
            patch.object(app_module, "verify_supabase_job_seeker", return_value=None),
            patch.object(
                app_module,
                "supabase_rest_request",
                return_value=(200, [version]),
            ) as rest_request,
        ):
            renamed = self.client.patch(
                f"/api/resumes/{version_id}",
                headers={"Authorization": "Bearer seeker-session"},
                json={"label": "Backend v2"},
            )
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(renamed.json["resume"], version)
        self.assertEqual(rest_request.call_args.args[0], (
            "resume_versions?select=id,label,storage_path,file_size,created_at"
            f"&id=eq.{version_id}"
        ))
        self.assertEqual(rest_request.call_args.kwargs["payload"], {"label": "Backend v2"})

        with (
            patch.object(app_module, "verify_supabase_job_seeker", return_value=None),
            patch.object(app_module, "supabase_rest_request") as unused_request,
        ):
            invalid = self.client.patch(
                f"/api/resumes/{version_id}",
                headers={"Authorization": "Bearer seeker-session"},
                json={"label": "x" * 101},
            )
        self.assertEqual(invalid.status_code, 400)
        unused_request.assert_not_called()

    def test_resume_delete_detaches_application_version_and_retains_submitted_file(self):
        version_id = "22222222-2222-4222-8222-222222222222"
        version = {
            "id": version_id,
            "storage_path": f"11111111-1111-4111-8111-111111111111/versions/{version_id}.pdf",
        }
        with (
            patch.object(app_module, "verify_supabase_job_seeker", return_value=None),
            patch.object(
                app_module,
                "supabase_rest_request",
                side_effect=[
                    (200, [version]),
                    (200, [{"id": "application-1"}]),
                    (204, None),
                ],
            ) as rest_request,
            patch.object(app_module, "supabase_storage_request") as storage_request,
        ):
            response = self.client.delete(
                f"/api/resumes/{version_id}",
                headers={"Authorization": "Bearer seeker-session"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"deleted": True, "file_retained": True})
        self.assertEqual(rest_request.call_count, 3)
        self.assertEqual(rest_request.call_args_list[2].kwargs["method"], "DELETE")
        storage_request.assert_not_called()

    def test_notification_calendar_migration_notifies_each_status_transition(self):
        repository_root = Path(__file__).parents[1]
        migration = (
            repository_root
            / "backend"
            / "migrations"
            / "phase23_notification_calendar_enhancements.sql"
        ).read_text(encoding="utf-8")
        notifications = (
            repository_root
            / "backend"
            / "migrations"
            / "phase16_provider_applicant_ranking.sql"
        ).read_text(encoding="utf-8")

        self.assertIn("create or replace function public.notify_application_status_change()", migration)
        self.assertIn("old.status is distinct from new.status", migration)
        self.assertNotIn("new.status in (", migration)
        self.assertIn("new.status = 'Withdrawn' and auth.uid() = new.applicant_id", migration)
        self.assertIn("select provider_id into recipient_id", migration)
        self.assertIn("'from_status', old.status", migration)
        self.assertIn("'status', new.status", migration)
        self.assertIn("new.id::text || ':' || gen_random_uuid()::text", migration)
        self.assertIn("notify pgrst, 'reload schema';", migration)

        read_policy = notifications.split(
            'create policy "Users can view their notifications"', 1
        )[1].split(";", 1)[0]
        self.assertIn("(select auth.uid()) = user_id", read_policy)

    def test_interview_slot_migration_scopes_owners_and_serializes_bookings(self):
        migration = (
            Path(__file__).parents[1]
            / "backend"
            / "migrations"
            / "phase24_interview_slot_booking.sql"
        ).read_text(encoding="utf-8")
        select_policy = migration.split(
            'create policy "Applicants and listing providers can view interview slots"',
            1,
        )[1].split(";", 1)[0]

        self.assertIn(
            "create table if not exists public.application_interview_slots",
            migration,
        )
        self.assertIn(
            "alter table public.application_interview_slots enable row level security",
            migration,
        )
        self.assertIn("provider_id = (select auth.uid())", select_policy)
        self.assertIn("(select public.is_job_provider())", select_policy)
        self.assertIn("(select public.owns_job_application(application_id))", select_policy)
        self.assertIn("application.applicant_id = (select auth.uid())", select_policy)
        self.assertIn(
            "application_interview_slots_one_booked_per_application",
            migration,
        )
        self.assertIn("pg_advisory_xact_lock", migration)
        self.assertIn("other_slot.starts_at < slot.starts_at + interval '30 minutes'", migration)
        self.assertIn("pg_catalog.now()", migration)
        self.assertIn("notification_type in (", migration)
        self.assertIn("'interview_slot_available'", migration)
        self.assertIn("'interview_slot_unavailable'", migration)
        self.assertIn("'interview_cancelled'", migration)
        self.assertIn("public.is_job_seeker()", migration)
        self.assertIn("public.is_job_provider()", migration)
        self.assertIn("notify pgrst, 'reload schema';", migration)
        self.assertNotIn("using (true)", select_policy)

    def test_rejection_feedback_migration_separates_applicant_feedback_from_private_reviews(self):
        migration = (
            Path(__file__).parents[1]
            / "backend"
            / "migrations"
            / "phase20_rejection_feedback.sql"
        ).read_text(encoding="utf-8")

        self.assertIn("create table if not exists public.application_rejection_feedback", migration)
        self.assertIn("alter table public.application_rejection_feedback enable row level security", migration)
        self.assertIn("provider_id = (select auth.uid())", migration)
        self.assertIn("applicant_id = (select auth.uid())", migration)
        self.assertIn("(select public.owns_job_application(application_id))", migration)
        self.assertIn("application.status = 'Rejected'", migration)
        self.assertIn("char_length(feedback) <= 1000", migration)
        self.assertIn("notify pgrst, 'reload schema';", migration)
        self.assertNotIn("reviewer_notes", migration)

    def test_structured_rejection_migration_enforces_atomic_updates_and_safe_reads(self):
        migration = (
            Path(__file__).parents[1]
            / "backend"
            / "migrations"
            / "phase27_structured_rejection_feedback.sql"
        ).read_text(encoding="utf-8")

        self.assertIn("add column if not exists rejection_reason text", migration)
        self.assertIn("add column if not exists rejection_note_shared boolean not null default false", migration)
        self.assertIn("char_length(rejection_note) <= 500", migration)
        for reason in (
            "skills_gap",
            "experience_level",
            "position_filled",
            "role_requirements_changed",
            "application_incomplete",
            "other",
        ):
            self.assertIn(f"'{reason}'", migration)
        self.assertIn("create or replace function public.update_job_application_status_with_rejection", migration)
        self.assertIn("public.owns_job_listing(target_application.job_id)", migration)
        self.assertIn("delete from public.application_rejection_feedback", migration)
        self.assertIn('create policy "Providers can view rejection feedback for their applications"', migration)
        self.assertIn('drop policy if exists "Applicants can view their rejection feedback"', migration)
        self.assertIn("and application.applicant_id = auth.uid()", migration)
        self.assertIn(
            "when feedback.rejection_note_shared then feedback.rejection_note",
            migration,
        )
        self.assertIn("and char_length(feedback.feedback) <= 500", migration)
        self.assertIn("revoke insert, update, delete on public.application_rejection_feedback", migration)
        self.assertIn("notify pgrst, 'reload schema';", migration)
        self.assertNotIn("reviewer_notes", migration)

    def test_rls_contracts_scope_private_data_and_keep_review_notes_provider_only(self):
        repository_root = Path(__file__).parents[1]
        schema = (repository_root / "backend" / "supabase_schema.sql").read_text(
            encoding="utf-8"
        )
        migrations = repository_root / "backend" / "migrations"
        materials = (migrations / "phase15_application_materials.sql").read_text(
            encoding="utf-8"
        )
        notifications = (migrations / "phase16_provider_applicant_ranking.sql").read_text(
            encoding="utf-8"
        )
        saved_jobs = (migrations / "phase18_saved_jobs.sql").read_text(
            encoding="utf-8"
        )

        self.assertIn("(select auth.uid()) = user_id", materials)
        self.assertIn("(select auth.uid()) = user_id", notifications)
        self.assertIn("user_id = (select auth.uid())", saved_jobs)
        self.assertIn("(select public.is_job_seeker())", saved_jobs)
        notification_read_policy = notifications.split(
            'create policy "Users can view their notifications"', 1
        )[1].split(";", 1)[0]
        notification_update_policy = notifications.split(
            'create policy "Users can mark their notifications read"', 1
        )[1].split(";", 1)[0]
        self.assertIn("(select auth.uid()) = user_id", notification_read_policy)
        self.assertIn("(select auth.uid()) = user_id", notification_update_policy)

        review_policy = schema.split(
            "create policy \"Providers can view reviews for their applications\"", 1
        )[1].split(";", 1)[0]
        self.assertIn("provider_id = (select auth.uid())", review_policy)
        self.assertIn("(select public.owns_job_application(application_id))", review_policy)
        self.assertNotIn("applicant_id", review_policy)

        resume_policy = schema.split(
            "create or replace function public.can_access_application_resume", 1
        )[1].split("$$;", 1)[0]
        self.assertIn("application.applicant_id = (select auth.uid())", resume_policy)
        self.assertIn("(select public.owns_job_listing(application.job_id))", resume_policy)

    def test_saving_a_job_uses_database_owner_default_and_rls(self):
        job_id = "63d0cc2a-a48b-4e42-9ed1-26579a0678c3"
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(
            app_module,
            "supabase_rest_request",
            return_value=(201, [{"job_id": job_id}]),
        ) as proxy:
            response = self.client.post(
                "/api/saved-jobs",
                headers={"Authorization": "Bearer seeker-session"},
                json={"job_id": job_id},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(proxy.call_args.kwargs["payload"], {"job_id": job_id})
        self.assertNotIn("user_id", proxy.call_args.kwargs["payload"])

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

    def test_skill_gap_rejects_non_pdf_mime_and_files_over_five_mib(self):
        base = {
            "target_role": "Backend Developer",
            "job_description": "Python and Flask experience are required for this role.",
        }
        with patch.object(app_module, "verify_supabase_job_seeker", return_value=None):
            wrong_mime = self.post_skill_gap({
                **base,
                "resume": (io.BytesIO(b"%PDF-1.4"), "resume.pdf", "text/plain"),
            })
            oversized = self.post_skill_gap({
                **base,
                "resume": (
                    io.BytesIO(b"x" * (app_module.MAX_FILE_SIZE + 1)),
                    "resume.pdf",
                    "application/pdf",
                ),
            })

        self.assertEqual(wrong_mime.status_code, 400)
        self.assertIn("PDF", wrong_mime.json["error"])
        self.assertEqual(oversized.status_code, 400)
        self.assertIn("5 MB", oversized.json["error"])

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

    def test_star_story_routes_require_authentication_and_seeker_role(self):
        story_id = "00000000-0000-0000-0000-000000000001"
        unauthenticated = [
            self.client.get("/api/star-stories"),
            self.client.post("/api/star-stories", json={}),
            self.client.patch(f"/api/star-stories/{story_id}", json={}),
            self.client.delete(f"/api/star-stories/{story_id}"),
        ]
        self.assertTrue(all(response.status_code == 401 for response in unauthenticated))

        forbidden = ({"error": "Job seekers only."}, 403)
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=forbidden
        ), patch.object(app_module, "supabase_rest_request") as proxy:
            denied = [
                self.client.get("/api/star-stories", headers={"Authorization": "Bearer test"}),
                self.client.post("/api/star-stories", headers={"Authorization": "Bearer test"}, json={}),
                self.client.patch(
                    f"/api/star-stories/{story_id}",
                    headers={"Authorization": "Bearer test"},
                    json={},
                ),
                self.client.delete(
                    f"/api/star-stories/{story_id}",
                    headers={"Authorization": "Bearer test"},
                ),
            ]

        self.assertTrue(all(response.status_code == 403 for response in denied))
        proxy.assert_not_called()

    def test_star_story_routes_support_empty_create_update_and_delete(self):
        story_id = "00000000-0000-0000-0000-000000000001"
        payload = {
            "title": "Improved a team handoff",
            "situation": "Requests were delayed between two teams.",
            "task": "I needed to clarify ownership.",
            "action": "I introduced a shared checklist and weekly review.",
            "result": "The teams reported fewer missed handoffs.",
            "skill_tags": ["Communication", "communication", "Planning"],
        }
        saved = {"id": story_id, **payload, "skill_tags": ["Communication", "Planning"]}
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(
            app_module,
            "supabase_rest_request",
            side_effect=[(200, []), (201, [saved]), (200, [saved]), (200, [saved])],
        ) as proxy:
            empty = self.client.get(
                "/api/star-stories", headers={"Authorization": "Bearer test"}
            )
            created = self.client.post(
                "/api/star-stories",
                headers={"Authorization": "Bearer test"},
                json=payload,
            )
            updated = self.client.patch(
                f"/api/star-stories/{story_id}",
                headers={"Authorization": "Bearer test"},
                json=payload,
            )
            deleted = self.client.delete(
                f"/api/star-stories/{story_id}",
                headers={"Authorization": "Bearer test"},
            )

        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.json, [])
        self.assertEqual(created.status_code, 200)
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(proxy.call_args_list[0].args[0], (
            "star_stories?select=id,title,situation,task,action,result,skill_tags,"
            "created_at,updated_at&order=updated_at.desc"
        ))
        self.assertEqual(
            proxy.call_args_list[1].kwargs["payload"]["skill_tags"],
            ["Communication", "Planning"],
        )
        self.assertNotIn("user_id", proxy.call_args_list[1].kwargs["payload"])
        self.assertEqual(proxy.call_args_list[2].kwargs["method"], "PATCH")
        self.assertEqual(proxy.call_args_list[3].kwargs["method"], "DELETE")

    def test_star_story_routes_reject_invalid_content_and_report_missing_rows(self):
        story_id = "00000000-0000-0000-0000-000000000001"
        valid = {
            "title": "Improved a team handoff",
            "situation": "Requests were delayed between two teams.",
            "task": "I needed to clarify ownership.",
            "action": "I introduced a shared checklist and weekly review.",
            "result": "The teams reported fewer missed handoffs.",
            "skill_tags": ["Communication"],
        }
        invalid_payloads = [
            {**valid, "skill_tags": ["tag"] * 13},
            {**valid, "skill_tags": ["x" * 51]},
            {**valid, "situation": " "},
            {**valid, "action": "a" * 1601},
            {**valid, "user_id": "untrusted"},
            {
                **valid,
                "title": "t" * 120,
                "situation": "s" * 1200,
                "task": "t" * 1200,
                "action": "a" * 1600,
                "result": "r" * 1200,
            },
        ]
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(app_module, "supabase_rest_request") as proxy:
            responses = [
                self.client.post(
                    "/api/star-stories",
                    headers={"Authorization": "Bearer test"},
                    json=payload,
                )
                for payload in invalid_payloads
            ]
            proxy.return_value = (200, [])
            missing_update = self.client.patch(
                f"/api/star-stories/{story_id}",
                headers={"Authorization": "Bearer test"},
                json=valid,
            )
            missing_delete = self.client.delete(
                f"/api/star-stories/{story_id}",
                headers={"Authorization": "Bearer test"},
            )
            invalid_id = self.client.delete(
                "/api/star-stories/not-a-uuid",
                headers={"Authorization": "Bearer test"},
            )

        self.assertTrue(all(response.status_code == 400 for response in responses))
        self.assertEqual(missing_update.status_code, 404)
        self.assertEqual(missing_delete.status_code, 404)
        self.assertEqual(invalid_id.status_code, 400)
        self.assertEqual(proxy.call_count, 2)

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

    def test_job_match_what_if_requires_seeker_and_validates_skills(self):
        job_id = "11111111-1111-4111-8111-111111111111"
        path = f"/api/job-recommendations/{job_id}/what-if"
        unauthenticated = self.client.post(
            path,
            json={"add_skills": ["Python"], "remove_skills": []},
        )
        forbidden = ({"error": "Job seekers only."}, 403)
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=forbidden
        ) as verify_seeker, patch.object(app_module, "supabase_rest_request") as proxy:
            denied = self.client.post(
                path,
                headers={"Authorization": "Bearer provider-token"},
                json={"add_skills": ["Python"], "remove_skills": []},
            )
        self.assertEqual(unauthenticated.status_code, 401)
        self.assertEqual(denied.status_code, 403)
        verify_seeker.assert_called_once()
        proxy.assert_not_called()

        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(app_module, "supabase_rest_request") as proxy:
            invalid = self.client.post(
                path,
                headers={"Authorization": "Bearer seeker-token"},
                json={"add_skills": ["not a supported skill"], "remove_skills": []},
            )
        self.assertEqual(invalid.status_code, 400)
        proxy.assert_not_called()

    def test_job_match_what_if_returns_explainable_ephemeral_scores(self):
        job_id = "11111111-1111-4111-8111-111111111111"
        job = {
            "id": job_id,
            "title": "Backend Developer",
            "company": "Example",
            "description": "Required: Python and PostgreSQL.",
            "requirements": "",
        }
        profile = {
            "skills": ["Python"],
            "headline": "",
            "about": "Built Python tools for a class project.",
        }
        with (
            patch.object(app_module, "verify_supabase_job_seeker", return_value=None),
            patch.object(
                app_module,
                "supabase_rest_request",
                side_effect=[
                    (200, [job]),
                    (200, [profile]),
                    (200, []),
                ],
            ) as proxy,
            patch.object(
                app_module, "fetch_portfolio_projects", return_value=([], True, None)
            ),
        ):
            response = self.client.post(
                f"/api/job-recommendations/{job_id}/what-if",
                headers={"Authorization": "Bearer seeker-token"},
                json={"add_skills": ["postgres"], "remove_skills": []},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["baseline_score"], 50)
        self.assertEqual(response.json["simulated_score"], 68)
        self.assertEqual(response.json["delta"], 18)
        self.assertEqual(response.json["added_skills"], ["PostgreSQL"])
        self.assertEqual(profile["skills"], ["Python"])
        self.assertIn("does not verify proficiency", response.json["note"])
        self.assertEqual(
            [call.kwargs.get("method", "GET") for call in proxy.call_args_list],
            ["GET", "GET", "GET"],
        )

    def test_job_match_what_if_hides_unpublished_or_inaccessible_jobs(self):
        job_id = "11111111-1111-4111-8111-111111111111"
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(
            app_module,
            "supabase_rest_request",
            return_value=(200, []),
        ) as proxy:
            response = self.client.post(
                f"/api/job-recommendations/{job_id}/what-if",
                headers={"Authorization": "Bearer seeker-token"},
                json={"add_skills": ["Python"], "remove_skills": []},
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(proxy.call_count, 1)
        self.assertIn("status=eq.published", proxy.call_args.args[0])

    def test_job_match_what_if_keeps_insufficient_baseline_unscored(self):
        job_id = "11111111-1111-4111-8111-111111111111"
        job = {
            "id": job_id,
            "title": "Developer",
            "company": "Example",
            "description": "Python is required.",
            "requirements": "",
        }
        with (
            patch.object(app_module, "verify_supabase_job_seeker", return_value=None),
            patch.object(
                app_module,
                "supabase_rest_request",
                side_effect=[
                    (200, [job]),
                    (200, [{"skills": [], "headline": "", "about": ""}]),
                    (200, []),
                ],
            ),
            patch.object(
                app_module, "fetch_portfolio_projects", return_value=([], True, None)
            ),
        ):
            response = self.client.post(
                f"/api/job-recommendations/{job_id}/what-if",
                headers={"Authorization": "Bearer seeker-token"},
                json={"add_skills": ["Python"], "remove_skills": []},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json["baseline_score"])
        self.assertEqual(response.json["simulated_score"], 35)
        self.assertIsNone(response.json["delta"])

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
            "&order=updated_at.desc&limit=500"
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

    def test_interview_prep_rejects_provider_role(self):
        with patch.object(
            app_module,
            "verify_supabase_job_seeker",
            return_value=({"error": "Job seekers only."}, 403),
        ):
            response = self.client.post(
                "/api/interview-prep",
                headers={"Authorization": "Bearer provider-session"},
                json={
                    "role": "Data Analyst",
                    "job_description": "SQL and analytics experience required for this role.",
                },
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json["error"], "Job seekers only.")

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
        with patch.object(app_module, "verify_supabase_job_seeker", return_value=None):
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

    def test_application_materials_bound_profile_and_job_text_before_gemini(self):
        job_id = "00000000-0000-0000-0000-000000000001"
        responses = [
            (200, [{"id": job_id, "title": "Engineer", "description": "Role"}]),
            (200, [{}]),
            (200, []),
            (200, []),
        ]
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(
            app_module, "GEMINI_API_KEY", "test-key"
        ), patch.object(
            app_module, "MAX_APPLICATION_MATERIALS_INPUT_LENGTH", 1
        ), patch.object(
            app_module, "supabase_rest_request", side_effect=responses
        ), patch.object(app_module, "urlopen") as gemini_request:
            response = self.client.post(
                "/api/application-materials",
                headers={"Authorization": "Bearer seeker-session"},
                json={"job_id": job_id, "consent": True},
            )

        self.assertEqual(response.status_code, 413)
        self.assertIn("input limit", response.json["error"])
        gemini_request.assert_not_called()

    def test_application_materials_share_gemini_rate_limit(self):
        job_id = "00000000-0000-0000-0000-000000000001"
        responses = [
            (200, [{"id": job_id, "title": "Engineer", "description": "Role"}]),
            (200, [{}]),
            (200, []),
            (200, []),
        ]
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(
            app_module, "GEMINI_API_KEY", "test-key"
        ), patch.object(
            app_module, "GEMINI_REQUESTS_PER_MINUTE", 0
        ), patch.object(
            app_module, "supabase_rest_request", side_effect=responses
        ), patch.object(app_module, "urlopen") as gemini_request:
            response = self.client.post(
                "/api/application-materials",
                headers={"Authorization": "Bearer seeker-session"},
                json={"job_id": job_id, "consent": True},
            )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["Retry-After"], "60")
        gemini_request.assert_not_called()

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

    def test_ai_assist_rate_limiter_returns_json_429_and_retry_after(self):
        payload = {
            "task": "resume_feedback",
            "role": "Data Analyst",
            "text": "A resume excerpt with enough characters for useful feedback.",
            "consent": True,
        }
        with patch.object(app_module, "GEMINI_API_KEY", "test-key"), patch.object(
            app_module, "GEMINI_REQUESTS_PER_MINUTE", 0
        ), patch.object(
            app_module, "verify_supabase_user", return_value=(True, None)
        ), patch.object(app_module, "urlopen") as gemini_request:
            response = self.post_ai_assist(payload)

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["Retry-After"], "60")
        self.assertIn("error", response.json)
        gemini_request.assert_not_called()

    def test_gemini_rate_limiter_caps_each_hashed_session(self):
        bearer = "Bearer distinct-session-token"
        with app_module.app.test_request_context(
            headers={"Authorization": bearer}
        ), patch.object(app_module, "GEMINI_REQUESTS_PER_MINUTE", 1):
            with app_module._GEMINI_RATE_LIMIT_LOCK:
                app_module._GEMINI_RATE_LIMIT_WINDOWS.clear()
            first = app_module.consume_gemini_request()
            second = app_module.consume_gemini_request()
            stored_keys = tuple(app_module._GEMINI_RATE_LIMIT_WINDOWS)

        self.assertIsNone(first)
        self.assertEqual(second, 60)
        self.assertEqual(len(stored_keys), 1)
        self.assertNotIn(bearer.encode("utf-8"), stored_keys)
        with app_module._GEMINI_RATE_LIMIT_LOCK:
            app_module._GEMINI_RATE_LIMIT_WINDOWS.clear()

    def test_api_errors_are_json_and_unexpected_logs_exclude_exception_details(self):
        missing = self.client.get("/api/not-a-route")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.mimetype, "application/json")
        self.assertIn("error", missing.json)

        private_detail = "private-user-data-and-token"
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(
            app_module,
            "supabase_rest_request",
            side_effect=RuntimeError(private_detail),
        ), self.assertLogs(app_module.app.logger, level="ERROR") as captured:
            failed = self.client.get(
                "/api/saved-jobs",
                headers={"Authorization": "Bearer test-session"},
            )

        self.assertEqual(failed.status_code, 500)
        self.assertEqual(failed.mimetype, "application/json")
        self.assertNotIn(private_detail, failed.get_data(as_text=True))
        self.assertNotIn(private_detail, "\n".join(captured.output))
        self.assertNotIn("test-session", "\n".join(captured.output))

    def test_calendar_text_escapes_carriage_returns_and_newlines(self):
        value = app_module.ics_escape("Interview\r\nATTENDEE:unexpected")

        self.assertEqual(value, r"Interview\nATTENDEE:unexpected")

    def test_interview_calendar_requires_authentication_and_valid_application_id(self):
        denied = ({"error": "Authentication required."}, 401)
        with patch.object(
            app_module, "verify_supabase_user", return_value=(None, denied)
        ), patch.object(app_module, "supabase_rest_request") as proxy:
            response = self.client.get(
                "/api/job-applications/11111111-1111-4111-8111-111111111111/interview.ics"
            )
        self.assertEqual(response.status_code, 401)
        proxy.assert_not_called()

        with patch.object(
            app_module, "verify_supabase_user", return_value=({"id": "seeker"}, None)
        ), patch.object(app_module, "supabase_rest_request") as proxy:
            invalid = self.client.get("/api/job-applications/not-a-uuid/interview.ics")
        self.assertEqual(invalid.status_code, 400)
        proxy.assert_not_called()

    def test_interview_calendar_exports_only_an_accessible_application_with_an_interview(self):
        application_id = "11111111-1111-4111-8111-111111111111"
        application = {
            "id": application_id,
            "job_title": "Backend Developer",
            "company": "Example Co",
        }
        interview_at = "2026-12-01T10:00:00Z"
        with (
            patch.object(
                app_module, "verify_supabase_user", return_value=({"id": "seeker"}, None)
            ),
            patch.object(
                app_module,
                "supabase_rest_request",
                side_effect=[
                    (200, [application]),
                    (200, []),
                    (200, [{"interview_at": interview_at}]),
                ],
            ) as proxy,
        ):
            response = self.client.get(
                f"/api/job-applications/{application_id}/interview.ics",
                headers={"Authorization": "Bearer session-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/calendar")
        self.assertIn("DTSTART:20261201T100000Z", response.get_data(as_text=True))
        self.assertIn("SUMMARY:Interview: Backend Developer", response.get_data(as_text=True))
        self.assertEqual(proxy.call_count, 3)

        with (
            patch.object(
                app_module, "verify_supabase_user", return_value=({"id": "other-user"}, None)
            ),
            patch.object(
                app_module,
                "supabase_rest_request",
                side_effect=[(200, []), (200, []), (200, [])],
            ),
        ):
            hidden = self.client.get(
                f"/api/job-applications/{application_id}/interview.ics",
                headers={"Authorization": "Bearer other-session"},
            )
        self.assertEqual(hidden.status_code, 404)
        self.assertIn("No interview date", hidden.json["error"])

        with (
            patch.object(
                app_module,
                "verify_supabase_user",
                return_value=({"id": "provider", "account_type": "job_provider"}, None),
            ),
            patch.object(
                app_module,
                "supabase_rest_request",
                side_effect=[
                    (200, [application]),
                    (200, []),
                    (200, [{"interview_at": interview_at}]),
                ],
            ),
        ):
            provider_calendar = self.client.get(
                f"/api/job-applications/{application_id}/interview.ics",
                headers={"Authorization": "Bearer provider-session"},
            )
        self.assertEqual(provider_calendar.status_code, 200)

    def test_interview_slot_routes_enforce_roles_and_validate_provider_input(self):
        unauthenticated = ({"error": "Sign in first."}, 401)
        with patch.object(
            app_module,
            "verify_supabase_job_seeker",
            return_value=unauthenticated,
        ), patch.object(app_module, "supabase_rest_request") as proxy:
            no_session = self.client.get("/api/job-applications/interview-slots")
        self.assertEqual(no_session.status_code, 401)
        proxy.assert_not_called()

        denied = ({"error": "Job providers only."}, 403)
        with patch.object(
            app_module, "verify_supabase_job_provider", return_value=denied
        ), patch.object(app_module, "supabase_rest_request") as proxy:
            response = self.client.get(
                "/api/provider/interview-slots",
                headers={"Authorization": "Bearer seeker-token"},
            )
        self.assertEqual(response.status_code, 403)
        proxy.assert_not_called()

        with patch.object(
            app_module,
            "verify_supabase_job_seeker",
            return_value=({"error": "Job seekers only."}, 403),
        ), patch.object(app_module, "supabase_rest_request") as proxy:
            seeker_denied = self.client.get(
                "/api/job-applications/interview-slots",
                headers={"Authorization": "Bearer provider-token"},
            )
        self.assertEqual(seeker_denied.status_code, 403)
        proxy.assert_not_called()

        with patch.object(
            app_module, "verify_supabase_job_provider", return_value=None
        ), patch.object(app_module, "supabase_rest_request") as proxy:
            invalid = self.client.post(
                "/api/provider/job-applications/11111111-1111-4111-8111-111111111111/interview-slots",
                headers={"Authorization": "Bearer provider-token"},
                json={"starts_at": "tomorrow"},
            )
        self.assertEqual(invalid.status_code, 400)
        proxy.assert_not_called()

    def test_provider_can_offer_a_future_interview_slot_and_empty_lists_are_supported(self):
        application_id = "11111111-1111-4111-8111-111111111111"
        slot = {
            "id": "22222222-2222-4222-8222-222222222222",
            "application_id": application_id,
            "status": "available",
        }
        starts_at = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        with (
            patch.object(
                app_module, "verify_supabase_job_provider", return_value=None
            ),
            patch.object(
                app_module,
                "supabase_rest_request",
                side_effect=[
                    (200, []),
                    (201, [slot]),
                    (200, {"id": slot["id"], "status": "cancelled"}),
                ],
            ) as proxy,
        ):
            empty = self.client.get(
                "/api/provider/interview-slots",
                headers={"Authorization": "Bearer provider-token"},
            )
            created = self.client.post(
                f"/api/provider/job-applications/{application_id}/interview-slots",
                headers={"Authorization": "Bearer provider-token"},
                json={"starts_at": starts_at},
            )
            cancelled = self.client.post(
                f"/api/provider/interview-slots/{slot['id']}/cancel",
                headers={"Authorization": "Bearer provider-token"},
            )

        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.json["slots"], [])
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json["slot"], slot)
        self.assertNotIn("provider_id", proxy.call_args_list[1].kwargs["payload"])
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(
            proxy.call_args_list[2].args[0],
            "rpc/cancel_provider_interview_slot",
        )

    def test_applicant_can_book_and_cancel_a_slot_and_conflicts_are_safe(self):
        slot_id = "22222222-2222-4222-8222-222222222222"
        booked = {"id": slot_id, "status": "booked"}
        cancelled = {"id": slot_id, "status": "cancelled"}
        with (
            patch.object(
                app_module, "verify_supabase_job_seeker", return_value=None
            ),
            patch.object(
                app_module,
                "supabase_rest_request",
                side_effect=[
                    (200, []),
                    (200, booked),
                    (200, cancelled),
                ],
            ) as proxy,
        ):
            empty = self.client.get(
                "/api/job-applications/interview-slots",
                headers={"Authorization": "Bearer seeker-token"},
            )
            booking = self.client.post(
                f"/api/job-applications/interview-slots/{slot_id}/book",
                headers={"Authorization": "Bearer seeker-token"},
            )
            cancellation = self.client.post(
                f"/api/job-applications/interview-slots/{slot_id}/cancel",
                headers={"Authorization": "Bearer seeker-token"},
            )

        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.json["slots"], [])
        self.assertEqual(booking.status_code, 200)
        self.assertEqual(cancellation.status_code, 200)
        self.assertEqual(proxy.call_args_list[1].args[0], "rpc/book_application_interview_slot")
        self.assertEqual(proxy.call_args_list[2].args[0], "rpc/cancel_application_interview_slot")

        with (
            patch.object(
                app_module, "verify_supabase_job_seeker", return_value=None
            ),
            patch.object(
                app_module,
                "supabase_rest_request",
                return_value=(400, {"code": "23505"}),
            ),
        ):
            conflict = self.client.post(
                f"/api/job-applications/interview-slots/{slot_id}/book",
                headers={"Authorization": "Bearer seeker-token"},
            )
        self.assertEqual(conflict.status_code, 409)
        self.assertNotIn("23505", conflict.json["error"])

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

    def test_provider_listing_routes_reject_non_providers(self):
        forbidden = ({"error": "Job providers only."}, 403)
        paths = (
            ("/api/provider/job-listings/11111111-1111-4111-8111-111111111111/duplicate", "post"),
            ("/api/provider/job-listings/11111111-1111-4111-8111-111111111111/status", "patch"),
        )
        with patch.object(
            app_module, "verify_supabase_job_provider", return_value=forbidden
        ) as verify_provider, patch.object(app_module, "supabase_rest_request") as proxy:
            responses = [
                getattr(self.client, method)(
                    path,
                    headers={"Authorization": "Bearer seeker-token"},
                    json={"status": "published"} if method == "patch" else None,
                )
                for path, method in paths
            ]

        self.assertEqual([response.status_code for response in responses], [403, 403])
        self.assertEqual(verify_provider.call_count, 2)
        proxy.assert_not_called()

    def test_provider_listing_status_and_duplicate_routes_validate_and_execute(self):
        listing_id = "11111111-1111-4111-8111-111111111111"
        listing = {
            "title": "Backend Developer",
            "company": "Example Co",
            "location": "Remote",
            "workplace_type": "Remote",
            "employment_type": "Full-time",
            "description": "A detailed role description for an experienced Python backend developer.",
            "requirements": "Required: Python",
        }
        duplicate = {**listing, "title": "Backend Developer (copy)", "status": "draft"}
        with (
            patch.object(app_module, "verify_supabase_job_provider", return_value=None),
            patch.object(
                app_module,
                "supabase_rest_request",
                side_effect=[
                    (200, [{**listing, "status": "published"}]),
                    (200, [listing]),
                    (201, [duplicate]),
                ],
            ) as proxy,
        ):
            updated = self.client.patch(
                f"/api/provider/job-listings/{listing_id}/status",
                headers={"Authorization": "Bearer provider-token"},
                json={"status": "published"},
            )
            copied = self.client.post(
                f"/api/provider/job-listings/{listing_id}/duplicate",
                headers={"Authorization": "Bearer provider-token"},
            )

        self.assertEqual(updated.status_code, 200)
        self.assertEqual(copied.status_code, 201)
        self.assertEqual(copied.json["job"]["status"], "draft")
        self.assertTrue(copied.json["job"]["title"].endswith("(copy)"))
        self.assertEqual(proxy.call_args_list[0].kwargs["method"], "PATCH")
        self.assertEqual(proxy.call_args_list[1].args[0], f"job_listings?select=title,company,location,workplace_type,employment_type,description,requirements&id=eq.{listing_id}")
        self.assertEqual(proxy.call_args_list[2].kwargs["payload"]["status"], "draft")

    def test_provider_review_route_rejects_job_seekers(self):
        forbidden = ({"error": "Job providers only."}, 403)
        with patch.object(
            app_module, "verify_supabase_job_provider", return_value=forbidden
        ) as verify_provider, patch.object(
            app_module, "supabase_rest_request"
        ) as proxy:
            response = self.client.get(
                "/api/provider/application-reviews",
                headers={"Authorization": "Bearer seeker-token"},
            )

        self.assertEqual(response.status_code, 403)
        self.assertNotIn("reviewer_notes", response.get_data(as_text=True))
        verify_provider.assert_called_once()
        proxy.assert_not_called()

    def test_provider_rejection_status_requires_valid_reason_and_bounded_note(self):
        application_id = "11111111-1111-4111-8111-111111111111"
        path = f"/api/provider/job-applications/{application_id}/status"
        request_headers = {"Authorization": "Bearer provider-token"}
        forbidden = ({"error": "Job providers only."}, 403)
        with patch.object(
            app_module, "verify_supabase_job_provider", return_value=forbidden
        ) as verify_provider, patch.object(app_module, "supabase_rest_request") as proxy:
            denied = self.client.patch(path, headers=request_headers, json={"status": "Rejected"})
        self.assertEqual(denied.status_code, 403)
        verify_provider.assert_called_once()
        proxy.assert_not_called()

        with patch.object(
            app_module, "verify_supabase_job_provider", return_value=None
        ), patch.object(app_module, "supabase_rest_request") as proxy:
            missing = self.client.patch(path, headers=request_headers, json={"status": "Rejected"})
            invalid = self.client.patch(
                path,
                headers=request_headers,
                json={"status": "Rejected", "rejection_reason": "not_a_reason"},
            )
            long_note = self.client.patch(
                path,
                headers=request_headers,
                json={
                    "status": "Rejected",
                    "rejection_reason": "other",
                    "rejection_note": "x" * 501,
                },
            )
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(long_note.status_code, 400)
        proxy.assert_not_called()

    def test_provider_rejection_status_saves_atomically_with_opt_in_sharing(self):
        application_id = "11111111-1111-4111-8111-111111111111"
        request_headers = {"Authorization": "Bearer provider-token"}
        rpc_result = {
            "application_id": application_id,
            "status": "Rejected",
            "rejection_reason": "skills_gap",
            "rejection_note": "The role requires hands-on production experience.",
            "rejection_note_shared": True,
            "rejected_at": "2026-04-04T10:00:00Z",
        }
        with (
            patch.object(app_module, "verify_supabase_job_provider", return_value=None),
            patch.object(
                app_module,
                "supabase_rest_request",
                side_effect=[
                    (200, [{
                        "id": application_id,
                        "job_title": "Backend Engineer",
                        "company": "Example",
                        "applicant_email": "seeker@example.com",
                    }]),
                    (200, rpc_result),
                ],
            ) as proxy,
            patch.object(app_module, "send_notification_email") as send_email,
        ):
            response = self.client.patch(
                f"/api/provider/job-applications/{application_id}/status",
                headers=request_headers,
                json={
                    "status": "Rejected",
                    "rejection_reason": "skills_gap",
                    "rejection_note": "  The role requires hands-on production experience.  ",
                    "rejection_note_shared": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["application"], rpc_result)
        self.assertEqual(
            proxy.call_args_list[1].args[0],
            "rpc/update_job_application_status_with_rejection",
        )
        self.assertEqual(
            proxy.call_args_list[1].kwargs["payload"],
            {
                "_application_id": application_id,
                "_status": "Rejected",
                "_rejection_reason": "skills_gap",
                "_rejection_note": "The role requires hands-on production experience.",
                "_rejection_note_shared": True,
            },
        )
        send_email.assert_called_once()
        self.assertNotIn("reviewer_notes", response.get_data(as_text=True))

    def test_non_owner_provider_cannot_update_application_stage(self):
        application_id = "11111111-1111-4111-8111-111111111111"
        with patch.object(
            app_module, "verify_supabase_job_provider", return_value=None
        ), patch.object(
            app_module,
            "supabase_rest_request",
            return_value=(200, []),
        ) as proxy:
            response = self.client.patch(
                f"/api/provider/job-applications/{application_id}/status",
                headers={"Authorization": "Bearer other-provider-token"},
                json={
                    "status": "Rejected",
                    "rejection_reason": "other",
                },
            )
        self.assertEqual(response.status_code, 404)
        proxy.assert_called_once()

    def test_provider_stage_change_sends_no_rejection_fields_to_clear_old_feedback(self):
        application_id = "11111111-1111-4111-8111-111111111111"
        with (
            patch.object(app_module, "verify_supabase_job_provider", return_value=None),
            patch.object(
                app_module,
                "supabase_rest_request",
                side_effect=[
                    (200, [{
                        "id": application_id,
                        "job_title": "Backend Engineer",
                        "company": "Example",
                        "applicant_email": "seeker@example.com",
                    }]),
                    (200, {
                        "application_id": application_id,
                        "status": "Interview",
                        "rejection_reason": None,
                        "rejection_note": None,
                        "rejection_note_shared": False,
                        "rejected_at": None,
                    }),
                ],
            ) as proxy,
            patch.object(app_module, "send_notification_email"),
        ):
            response = self.client.patch(
                f"/api/provider/job-applications/{application_id}/status",
                headers={"Authorization": "Bearer provider-token"},
                json={"status": "Interview"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(proxy.call_args_list[1].kwargs["payload"]["_rejection_reason"])
        self.assertIsNone(proxy.call_args_list[1].kwargs["payload"]["_rejection_note"])

    def test_applicant_rejection_feedback_is_seeker_only_and_redacts_unshared_note(self):
        application_id = "11111111-1111-4111-8111-111111111111"
        path = f"/api/job-applications/{application_id}/rejection-feedback"
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(app_module, "supabase_rest_request") as proxy:
            proxy.return_value = (200, [])
            inaccessible = self.client.get(
                path, headers={"Authorization": "Bearer other-seeker-token"}
            )
        self.assertEqual(inaccessible.status_code, 404)
        proxy.assert_called_once()

        unshared_feedback = {
            "rejection_reason": "skills_gap",
            "rejection_note": None,
            "rejected_at": "2026-04-04T10:00:00Z",
            "job_title": "Backend Engineer",
            "job_description": "Build services and deploy them safely.",
            "job_requirements": "Python and production operations experience.",
        }
        with (
            patch.object(app_module, "verify_supabase_job_seeker", return_value=None),
            patch.object(
                app_module,
                "supabase_rest_request",
                return_value=(200, [unshared_feedback]),
            ) as proxy,
        ):
            visible = self.client.get(
                path, headers={"Authorization": "Bearer seeker-token"}
            )
        self.assertEqual(visible.status_code, 200)
        self.assertIsNone(visible.json["feedback"]["rejection_note"])
        self.assertEqual(visible.json["feedback"]["rejection_reason"], "skills_gap")
        self.assertNotIn("reviewer_notes", visible.get_data(as_text=True))
        self.assertNotIn("applicant_id", visible.get_data(as_text=True))
        self.assertNotIn("applicant_email", visible.get_data(as_text=True))
        self.assertNotIn("private note", visible.get_data(as_text=True))
        self.assertEqual(
            proxy.call_args.kwargs["payload"],
            {"_application_id": application_id},
        )

        shared_feedback = {
            **unshared_feedback,
            "rejection_note": "The provider opted to share this note.",
        }
        with (
            patch.object(app_module, "verify_supabase_job_seeker", return_value=None),
            patch.object(
                app_module,
                "supabase_rest_request",
                return_value=(200, [shared_feedback]),
            ),
        ):
            shared = self.client.get(
                path, headers={"Authorization": "Bearer seeker-token"}
            )
        self.assertEqual(shared.status_code, 200)
        self.assertEqual(
            shared.json["feedback"]["rejection_note"],
            "The provider opted to share this note.",
        )

    def test_applicant_rejection_feedback_empty_state_and_role_check(self):
        application_id = "11111111-1111-4111-8111-111111111111"
        path = f"/api/job-applications/{application_id}/rejection-feedback"
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(
            app_module,
            "supabase_rest_request",
            return_value=(200, [{
                "rejection_reason": None,
                "rejection_note": None,
                "rejected_at": None,
                "job_title": "Backend Engineer",
                "job_description": "Build services and deploy them safely.",
                "job_requirements": "",
            }]),
        ):
            empty = self.client.get(
                path, headers={"Authorization": "Bearer seeker-token"}
            )
        self.assertEqual(empty.status_code, 200)
        self.assertIsNone(empty.json["feedback"]["rejection_reason"])
        self.assertIsNone(empty.json["feedback"]["rejection_note"])

        with patch.object(
            app_module,
            "verify_supabase_job_seeker",
            return_value=({"error": "Job seekers only."}, 403),
        ) as verify_seeker, patch.object(app_module, "supabase_rest_request") as proxy:
            forbidden = self.client.get(
                path, headers={"Authorization": "Bearer provider-token"}
            )
        self.assertEqual(forbidden.status_code, 403)
        verify_seeker.assert_called_once()
        proxy.assert_not_called()

    def test_provider_applicant_evidence_rejects_job_seekers(self):
        forbidden = ({"error": "Job providers only."}, 403)
        with patch.object(
            app_module, "verify_supabase_job_provider", return_value=forbidden
        ) as verify_provider, patch.object(app_module, "supabase_rest_request") as proxy:
            response = self.client.get(
                "/api/provider-applicant-evidence",
                headers={"Authorization": "Bearer seeker-token"},
            )

        self.assertEqual(response.status_code, 403)
        self.assertNotIn("reviewer_notes", response.get_data(as_text=True))
        verify_provider.assert_called_once()
        proxy.assert_not_called()

    def test_provider_application_stage_and_interview_routes_reject_job_seekers(self):
        forbidden = ({"error": "Job providers only."}, 403)
        application_id = "11111111-1111-4111-8111-111111111111"
        with patch.object(
            app_module, "verify_supabase_job_provider", return_value=forbidden
        ) as verify_provider, patch.object(app_module, "supabase_rest_request") as proxy:
            stage = self.client.patch(
                f"/api/provider/job-applications/{application_id}/status",
                headers={"Authorization": "Bearer seeker-token"},
                json={"status": "Interview"},
            )
            interview = self.client.post(
                f"/api/provider/application-reviews/{application_id}",
                headers={"Authorization": "Bearer seeker-token"},
                json={"reviewer_notes": "private", "interview_at": "2026-12-01T10:00:00Z"},
            )

        self.assertEqual(stage.status_code, 403)
        self.assertEqual(interview.status_code, 403)
        self.assertEqual(verify_provider.call_count, 2)
        proxy.assert_not_called()

    def test_application_status_timeline_requires_a_job_seeker(self):
        response = self.client.get(
            "/api/job-applications/11111111-1111-4111-8111-111111111111/timeline"
        )
        self.assertEqual(response.status_code, 401)

        with patch.object(
            app_module,
            "verify_supabase_job_seeker",
            return_value=({"error": "Job seekers only."}, 403),
        ) as verify_seeker, patch.object(app_module, "supabase_rest_request") as proxy:
            forbidden = self.client.get(
                "/api/job-applications/11111111-1111-4111-8111-111111111111/timeline",
                headers={"Authorization": "Bearer provider-token"},
            )

        self.assertEqual(forbidden.status_code, 403)
        verify_seeker.assert_called_once()
        proxy.assert_not_called()

    def test_application_status_timeline_validates_id_and_isolates_inaccessible_applications(self):
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(app_module, "supabase_rest_request") as proxy:
            proxy.return_value = (200, [])
            invalid = self.client.get(
                "/api/job-applications/not-a-uuid/timeline",
                headers={"Authorization": "Bearer seeker-token"},
            )
            inaccessible = self.client.get(
                "/api/job-applications/11111111-1111-4111-8111-111111111111/timeline",
                headers={"Authorization": "Bearer seeker-token"},
            )

        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(inaccessible.status_code, 404)
        self.assertEqual(proxy.call_count, 1)

    def test_application_status_timeline_returns_ordered_events_without_private_notes(self):
        application_id = "11111111-1111-4111-8111-111111111111"
        with (
            patch.object(app_module, "verify_supabase_job_seeker", return_value=None),
            patch.object(
                app_module,
                "supabase_rest_request",
                side_effect=[
                    (200, [{
                        "id": application_id,
                        "status": "Interview",
                        "created_at": "2026-04-02T09:00:00Z",
                    }]),
                    (200, [
                        {
                            "from_status": "Shortlisted",
                            "to_status": "Interview",
                            "changed_at": "2026-04-03T11:00:00Z",
                        },
                        {
                            "from_status": None,
                            "to_status": "Submitted",
                            "changed_at": "2026-04-02T09:00:00Z",
                        },
                    ]),
                ],
            ) as proxy,
        ):
            response = self.client.get(
                f"/api/job-applications/{application_id}/timeline",
                headers={"Authorization": "Bearer seeker-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["history_complete"])
        self.assertEqual(response.json["current_status"], "Interview")
        self.assertEqual(
            [event["to_status"] for event in response.json["events"]],
            ["Submitted", "Interview"],
        )
        self.assertNotIn("reviewer_notes", response.get_data(as_text=True))
        self.assertIn("application_status_events?select=from_status,to_status,changed_at", proxy.call_args_list[1].args[0])

    def test_application_status_timeline_marks_legacy_history_as_incomplete(self):
        application_id = "11111111-1111-4111-8111-111111111111"
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(
            app_module,
            "supabase_rest_request",
            side_effect=[
                (200, [{
                    "id": application_id,
                    "status": "Interview",
                    "created_at": "2025-11-02T09:00:00Z",
                }]),
                (200, []),
            ],
        ):
            response = self.client.get(
                f"/api/job-applications/{application_id}/timeline",
                headers={"Authorization": "Bearer seeker-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json["history_complete"])
        self.assertEqual(response.json["events"], [])
        self.assertEqual(response.json["current_status"], "Interview")
        self.assertEqual(response.json["submitted_at"], "2025-11-02T09:00:00Z")

    def test_response_metrics_routes_require_authentication_and_account_roles(self):
        job_id = "11111111-1111-4111-8111-111111111111"
        unauthenticated = [
            self.client.get("/api/jobs/responsiveness"),
            self.client.get(f"/api/jobs/{job_id}/responsiveness"),
            self.client.get("/api/provider/response-metrics"),
        ]
        self.assertTrue(all(response.status_code == 401 for response in unauthenticated))

        seeker_forbidden = ({"error": "Job seekers only."}, 403)
        provider_forbidden = ({"error": "Job providers only."}, 403)
        with (
            patch.object(
                app_module, "verify_supabase_job_seeker", return_value=seeker_forbidden
            ),
            patch.object(
                app_module, "verify_supabase_job_provider", return_value=provider_forbidden
            ),
            patch.object(app_module, "supabase_rest_request") as proxy,
        ):
            denied = [
                self.client.get(
                    "/api/jobs/responsiveness",
                    headers={"Authorization": "Bearer provider-token"},
                ),
                self.client.get(
                    f"/api/jobs/{job_id}/responsiveness",
                    headers={"Authorization": "Bearer provider-token"},
                ),
                self.client.get(
                    "/api/provider/response-metrics",
                    headers={"Authorization": "Bearer seeker-token"},
                ),
            ]

        self.assertEqual([response.status_code for response in denied], [403, 403, 403])
        proxy.assert_not_called()

    def test_job_responsiveness_rejects_malformed_listing_ids(self):
        with (
            patch.object(app_module, "verify_supabase_job_seeker", return_value=None),
            patch.object(app_module, "supabase_rest_request") as proxy,
        ):
            response = self.client.get(
                "/api/jobs/not-a-uuid/responsiveness",
                headers={"Authorization": "Bearer seeker-token"},
            )

        self.assertEqual(response.status_code, 400)
        proxy.assert_not_called()

    def test_response_metrics_batch_and_detail_routes_expose_only_thresholded_summaries(self):
        job_id = "11111111-1111-4111-8111-111111111111"
        metrics = {
            "job_id": job_id,
            "response_rate": 60.0,
            "median_first_response_days": 2.5,
            "sample_size": 5,
            "sufficient_data": True,
        }
        with (
            patch.object(app_module, "verify_supabase_job_seeker", return_value=None),
            patch.object(
                app_module, "supabase_rest_request", return_value=(200, [metrics])
            ) as proxy,
        ):
            batch = self.client.get(
                "/api/jobs/responsiveness",
                headers={"Authorization": "Bearer seeker-token"},
            )
            detail = self.client.get(
                f"/api/jobs/{job_id}/responsiveness",
                headers={"Authorization": "Bearer seeker-token"},
            )

        self.assertEqual(batch.status_code, 200)
        self.assertEqual(batch.json, {"metrics": [metrics]})
        self.assertEqual(
            detail.json,
            {
                "response_rate": 60.0,
                "median_first_response_days": 2.5,
                "sample_size": 5,
                "sufficient_data": True,
            },
        )
        self.assertNotIn("applicant_id", json.dumps(batch.json))
        self.assertNotIn("applicant_name", json.dumps(batch.json))
        self.assertEqual(
            proxy.call_args_list[0].args[0], "rpc/get_job_responsiveness"
        )
        self.assertEqual(proxy.call_args_list[0].kwargs["payload"], {"_job_id": None})
        self.assertEqual(
            proxy.call_args_list[1].kwargs["payload"], {"_job_id": job_id}
        )

    def test_response_metrics_preserve_odd_even_medians_and_zero_application_state(self):
        job_id = "11111111-1111-4111-8111-111111111111"
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ):
            for sample_size, median in ((5, 3.0), (6, 2.5)):
                metrics = {
                    "job_id": job_id,
                    "response_rate": 50.0,
                    "median_first_response_days": median,
                    "sample_size": sample_size,
                    "sufficient_data": True,
                }
                with patch.object(
                    app_module, "supabase_rest_request", return_value=(200, [metrics])
                ):
                    response = self.client.get(
                        f"/api/jobs/{job_id}/responsiveness",
                        headers={"Authorization": "Bearer seeker-token"},
                    )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.json["median_first_response_days"], median
                )

            insufficient_responses = []
            for sample_size in (4, 0):
                metrics = {
                    "job_id": job_id,
                    "response_rate": None,
                    "median_first_response_days": None,
                    "sample_size": sample_size,
                    "sufficient_data": False,
                }
                with patch.object(
                    app_module,
                    "supabase_rest_request",
                    return_value=(200, [metrics]),
                ):
                    insufficient_responses.append(self.client.get(
                        f"/api/jobs/{job_id}/responsiveness",
                        headers={"Authorization": "Bearer seeker-token"},
                    ))

        for empty in insufficient_responses:
            self.assertEqual(empty.status_code, 200)
            self.assertIsNone(empty.json["response_rate"])
            self.assertIsNone(empty.json["median_first_response_days"])
            self.assertFalse(empty.json["sufficient_data"])
        self.assertEqual(insufficient_responses[-1].json["sample_size"], 0)

    def test_provider_response_metrics_are_owner_role_checked_and_support_empty_samples(self):
        empty_metrics = {
            "response_rate": None,
            "median_first_response_days": None,
            "sample_size": 0,
            "sufficient_data": False,
        }
        with (
            patch.object(app_module, "verify_supabase_job_provider", return_value=None),
            patch.object(
                app_module,
                "supabase_rest_request",
                return_value=(200, [empty_metrics]),
            ) as proxy,
        ):
            response = self.client.get(
                "/api/provider/response-metrics",
                headers={"Authorization": "Bearer provider-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, empty_metrics)
        self.assertEqual(
            proxy.call_args.args[0], "rpc/get_provider_response_metrics"
        )

    def test_application_analytics_requires_a_job_seeker_and_handles_insufficient_history(self):
        forbidden = ({"error": "Job seekers only."}, 403)
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=forbidden
        ) as verify_seeker, patch.object(app_module, "supabase_rest_request") as proxy:
            denied = self.client.get(
                "/api/application-analytics",
                headers={"Authorization": "Bearer provider-token"},
            )
        self.assertEqual(denied.status_code, 403)
        verify_seeker.assert_called_once()
        proxy.assert_not_called()

        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(
            app_module, "supabase_rest_request", return_value=(200, [])
        ):
            empty = self.client.get(
                "/api/application-analytics",
                headers={"Authorization": "Bearer seeker-token"},
            )
        self.assertEqual(empty.status_code, 200)
        self.assertIsNone(empty.json["average_first_response_hours"])
        self.assertEqual(empty.json["measured_applications"], 0)
        self.assertTrue(empty.json["complete"])

    def test_application_analytics_calculates_only_complete_provider_response_timelines(self):
        events = [
            {
                "application_id": "11111111-1111-4111-8111-111111111111",
                "from_status": "Submitted",
                "to_status": "CV review",
                "changed_at": "2026-04-03T09:00:00Z",
            },
            {
                "application_id": "11111111-1111-4111-8111-111111111111",
                "from_status": None,
                "to_status": "Submitted",
                "changed_at": "2026-04-02T09:00:00Z",
            },
            {
                "application_id": "22222222-2222-4222-8222-222222222222",
                "from_status": None,
                "to_status": "Submitted",
                "changed_at": "2026-04-02T09:00:00Z",
            },
            {
                "application_id": "33333333-3333-4333-8333-333333333333",
                "from_status": None,
                "to_status": "Submitted",
                "changed_at": "2026-04-02T09:00:00Z",
            },
            {
                "application_id": "33333333-3333-4333-8333-333333333333",
                "from_status": "Submitted",
                "to_status": "Withdrawn",
                "changed_at": "2026-04-02T10:00:00Z",
            },
        ]
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(
            app_module, "supabase_rest_request", return_value=(200, events)
        ) as proxy:
            response = self.client.get(
                "/api/application-analytics",
                headers={"Authorization": "Bearer seeker-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["average_first_response_hours"], 24.0)
        self.assertEqual(response.json["measured_applications"], 1)
        self.assertTrue(response.json["complete"])
        self.assertIn("manual tracker entries", response.json["calculation"])
        self.assertIn("application_status_events?select=application_id", proxy.call_args.args[0])

    def test_application_analytics_does_not_report_a_truncated_event_window(self):
        events = [
            {
                "application_id": "11111111-1111-4111-8111-111111111111",
                "from_status": None,
                "to_status": "Submitted",
                "changed_at": "2026-04-02T09:00:00Z",
            }
            for _ in range(1000)
        ]
        with patch.object(
            app_module, "verify_supabase_job_seeker", return_value=None
        ), patch.object(
            app_module, "supabase_rest_request", return_value=(200, events)
        ):
            response = self.client.get(
                "/api/application-analytics",
                headers={"Authorization": "Bearer seeker-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json["complete"])
        self.assertIsNone(response.json["average_first_response_hours"])
        self.assertEqual(response.json["measured_applications"], 0)

    def test_application_analytics_migration_adds_rerunnable_lookup_index(self):
        migration = (
            Path(__file__).parents[1]
            / "backend"
            / "migrations"
            / "phase21_application_analytics.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("create index if not exists application_status_events_applicant_changed_idx", migration)
        self.assertIn("applicant_id, changed_at, application_id", migration)
        self.assertIn("notify pgrst, 'reload schema';", migration)

    def test_first_response_calculation_skips_legacy_timelines_and_negative_durations(self):
        result = app_module.calculate_first_response_time_hours([
            {
                "application_id": "legacy",
                "from_status": "CV review",
                "to_status": "Interview",
                "changed_at": "2026-04-02T12:00:00Z",
            },
            {
                "application_id": "negative",
                "from_status": None,
                "to_status": "Submitted",
                "changed_at": "2026-04-02T12:00:00Z",
            },
            {
                "application_id": "negative",
                "from_status": "Submitted",
                "to_status": "Interview",
                "changed_at": "2026-04-02T11:00:00Z",
            },
        ])
        self.assertEqual(
            result,
            {"average_hours": None, "measured_applications": 0},
        )

    def test_provider_can_set_interview_date_and_private_reviewer_notes(self):
        application_id = "11111111-1111-4111-8111-111111111111"
        interview_at = "2026-12-01T10:00:00Z"
        review = {
            "application_id": application_id,
            "reviewer_notes": "Ask about Python project experience.",
            "interview_at": interview_at,
        }
        with (
            patch.object(app_module, "verify_supabase_job_provider", return_value=None),
            patch.object(
                app_module,
                "supabase_rest_request",
                side_effect=[
                    (200, [{
                        "id": application_id,
                        "job_title": "Backend Developer",
                        "company": "Example Co",
                        "applicant_email": "candidate@example.com",
                    }]),
                    (200, []),
                    (201, [review]),
                ],
            ) as proxy,
            patch.object(app_module, "send_notification_email") as send_email,
        ):
            response = self.client.post(
                f"/api/provider/application-reviews/{application_id}",
                headers={"Authorization": "Bearer provider-token"},
                json={
                    "reviewer_notes": review["reviewer_notes"],
                    "interview_at": interview_at,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["review"]["interview_at"], interview_at)
        self.assertEqual(response.json["review"]["reviewer_notes"], review["reviewer_notes"])
        self.assertEqual(proxy.call_args_list[2].kwargs["payload"], review)
        send_email.assert_called_once()

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
