create table if not exists public.application_rejection_feedback (
    application_id uuid primary key
        references public.job_applications (id) on delete cascade,
    applicant_id uuid not null
        references auth.users (id) on delete cascade,
    provider_id uuid not null default auth.uid()
        references auth.users (id) on delete cascade,
    reason_codes text[] not null default array[]::text[]
        check (
            cardinality(reason_codes) <= 5
            and reason_codes <@ array[
                'skills_alignment', 'experience_level', 'availability',
                'role_requirements', 'other'
            ]::text[]
        ),
    feedback text not null default ''
        check (char_length(feedback) <= 1000),
    updated_at timestamptz not null default now()
);

alter table public.application_rejection_feedback enable row level security;

drop policy if exists "Providers can view rejection feedback for their applications"
    on public.application_rejection_feedback;
create policy "Providers can view rejection feedback for their applications"
    on public.application_rejection_feedback for select to authenticated
    using (
        provider_id = (select auth.uid())
        and (select public.is_job_provider())
        and (select public.owns_job_application(application_id))
    );

drop policy if exists "Applicants can view their rejection feedback"
    on public.application_rejection_feedback;
create policy "Applicants can view their rejection feedback"
    on public.application_rejection_feedback for select to authenticated
    using (
        applicant_id = (select auth.uid())
        and (select public.is_job_seeker())
        and exists (
            select 1
            from public.job_applications as application
            where application.id = application_rejection_feedback.application_id
              and application.applicant_id = (select auth.uid())
              and application.status = 'Rejected'
        )
    );

drop policy if exists "Providers can create rejection feedback for their applications"
    on public.application_rejection_feedback;
create policy "Providers can create rejection feedback for their applications"
    on public.application_rejection_feedback for insert to authenticated
    with check (
        provider_id = (select auth.uid())
        and (select public.is_job_provider())
        and (select public.owns_job_application(application_id))
        and exists (
            select 1
            from public.job_applications as application
            where application.id = application_rejection_feedback.application_id
              and application.applicant_id = application_rejection_feedback.applicant_id
              and application.status = 'Rejected'
        )
    );

drop policy if exists "Providers can update rejection feedback for their applications"
    on public.application_rejection_feedback;
create policy "Providers can update rejection feedback for their applications"
    on public.application_rejection_feedback for update to authenticated
    using (
        provider_id = (select auth.uid())
        and (select public.is_job_provider())
        and (select public.owns_job_application(application_id))
    )
    with check (
        provider_id = (select auth.uid())
        and (select public.is_job_provider())
        and (select public.owns_job_application(application_id))
        and exists (
            select 1
            from public.job_applications as application
            where application.id = application_rejection_feedback.application_id
              and application.applicant_id = application_rejection_feedback.applicant_id
              and application.status = 'Rejected'
        )
    );

drop trigger if exists set_application_rejection_feedback_updated_at
    on public.application_rejection_feedback;
create trigger set_application_rejection_feedback_updated_at
    before update on public.application_rejection_feedback
    for each row execute function public.set_career_profile_updated_at();

revoke all on public.application_rejection_feedback from public, anon, authenticated;
grant select, insert, update on public.application_rejection_feedback to authenticated;

notify pgrst, 'reload schema';
