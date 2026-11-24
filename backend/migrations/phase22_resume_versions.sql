create table if not exists public.resume_versions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null default auth.uid()
        references auth.users (id) on delete cascade,
    storage_path text not null unique
        check (
            storage_path ~
            '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/versions/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}[.]pdf$'
        ),
    label text not null default ''
        check (char_length(label) <= 100),
    created_at timestamptz not null default now()
);

alter table public.job_applications
    add column if not exists resume_version_id uuid
        references public.resume_versions (id) on delete set null;

create index if not exists job_applications_resume_version_idx
    on public.job_applications (resume_version_id)
    where resume_version_id is not null;

alter table public.resume_versions enable row level security;

drop policy if exists "Job seekers can view their résumé versions"
    on public.resume_versions;
create policy "Job seekers can view their résumé versions"
    on public.resume_versions for select to authenticated
    using (
        user_id = (select auth.uid())
        and (select public.is_job_seeker())
    );

drop policy if exists "Providers can view selected applicant résumé versions"
    on public.resume_versions;
create policy "Providers can view selected applicant résumé versions"
    on public.resume_versions for select to authenticated
    using (
        (select public.is_job_provider())
        and exists (
            select 1
            from public.job_applications as application
            where application.resume_version_id = resume_versions.id
              and (select public.owns_job_listing(application.job_id))
        )
    );

drop policy if exists "Job seekers can create their résumé versions"
    on public.resume_versions;
create policy "Job seekers can create their résumé versions"
    on public.resume_versions for insert to authenticated
    with check (
        user_id = (select auth.uid())
        and (select public.is_job_seeker())
        and split_part(storage_path, '/', 1) = (select auth.uid())::text
        and split_part(storage_path, '/', 2) = 'versions'
    );

drop policy if exists "Job seekers can delete unlinked résumé versions"
    on public.resume_versions;
create policy "Job seekers can delete unlinked résumé versions"
    on public.resume_versions for delete to authenticated
    using (
        user_id = (select auth.uid())
        and (select public.is_job_seeker())
        and not exists (
            select 1
            from public.job_applications as application
            where application.resume_version_id = resume_versions.id
        )
    );

revoke all on public.resume_versions from public, anon, authenticated;
grant select, insert, delete on public.resume_versions to authenticated;

create or replace function public.can_access_application_resume(_object_name text)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.job_applications as application
        where application.resume_path = _object_name
          and (storage.foldername(_object_name))[1] = application.applicant_id::text
          and (
              application.applicant_id = (select auth.uid())
              or (select public.owns_job_listing(application.job_id))
          )
    ) or exists (
        select 1
        from public.resume_versions as version
        where version.storage_path = _object_name
          and version.user_id = (select auth.uid())
          and (select public.is_job_seeker())
    );
$$;

revoke all on function public.can_access_application_resume(text)
    from public, anon;
grant execute on function public.can_access_application_resume(text)
    to authenticated;

drop policy if exists "Job seekers can apply to published listings"
    on public.job_applications;
create policy "Job seekers can apply to published listings"
    on public.job_applications for insert to authenticated
    with check (
        (select auth.uid()) = applicant_id
        and (select public.is_job_seeker())
        and status = 'Submitted'
        and exists (
            select 1
            from public.job_listings
            where job_listings.id = job_applications.job_id
              and job_listings.status = 'published'
              and job_listings.provider_id <> (select auth.uid())
        )
        and (
            resume_version_id is null
            or exists (
                select 1
                from public.resume_versions as version
                where version.id = job_applications.resume_version_id
                  and version.user_id = (select auth.uid())
                  and version.storage_path = job_applications.resume_path
            )
        )
    );

drop policy if exists "Applicants can remove their own application resumes"
    on storage.objects;
create policy "Applicants can remove their own application resumes"
    on storage.objects for delete to authenticated
    using (
        bucket_id = 'application-resumes'
        and (storage.foldername(name))[1] = (select auth.uid())::text
        and not exists (
            select 1
            from public.job_applications as application
            where application.resume_path = storage.objects.name
              and application.applicant_id = (select auth.uid())
        )
    );

notify pgrst, 'reload schema';
