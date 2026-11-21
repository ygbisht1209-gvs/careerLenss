create table if not exists public.career_projects (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null default auth.uid()
        references auth.users (id) on delete cascade,
    title text not null
        check (char_length(btrim(title)) between 2 and 120),
    description text not null
        check (char_length(btrim(description)) between 1 and 2000),
    skills text[] not null default '{}'
        check (
            cardinality(skills) <= 30
            and char_length(array_to_string(skills, '')) <= 2400
        ),
    contribution text not null default ''
        check (char_length(contribution) <= 1200),
    project_url text not null default ''
        check (
            char_length(project_url) <= 2048
            and (
                project_url = ''
                or project_url ~* '^https?://[^[:space:]]+$'
            )
        ),
    started_on date,
    completed_on date,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint career_projects_valid_dates check (
        started_on is null
        or completed_on is null
        or completed_on >= started_on
    )
);

create index if not exists career_projects_user_updated_idx
    on public.career_projects (user_id, updated_at desc);

drop trigger if exists set_career_projects_updated_at
    on public.career_projects;
create trigger set_career_projects_updated_at
    before update on public.career_projects
    for each row execute function public.set_career_profile_updated_at();

alter table public.career_projects enable row level security;

drop policy if exists "Job seekers can view their career projects"
    on public.career_projects;
create policy "Job seekers can view their career projects"
    on public.career_projects for select to authenticated
    using (
        (select auth.uid()) = user_id
        and (select public.is_job_seeker())
    );

drop policy if exists "Job seekers can add their career projects"
    on public.career_projects;
create policy "Job seekers can add their career projects"
    on public.career_projects for insert to authenticated
    with check (
        (select auth.uid()) = user_id
        and (select public.is_job_seeker())
    );

drop policy if exists "Job seekers can update their career projects"
    on public.career_projects;
create policy "Job seekers can update their career projects"
    on public.career_projects for update to authenticated
    using (
        (select auth.uid()) = user_id
        and (select public.is_job_seeker())
    )
    with check (
        (select auth.uid()) = user_id
        and (select public.is_job_seeker())
    );

drop policy if exists "Job seekers can delete their career projects"
    on public.career_projects;
create policy "Job seekers can delete their career projects"
    on public.career_projects for delete to authenticated
    using (
        (select auth.uid()) = user_id
        and (select public.is_job_seeker())
    );

revoke all on public.career_projects from anon, authenticated;
grant select, insert, update, delete on public.career_projects to authenticated;
