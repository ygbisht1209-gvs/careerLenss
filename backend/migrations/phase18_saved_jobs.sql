create table if not exists public.saved_jobs (
    user_id uuid not null references auth.users(id) on delete cascade,
    job_id uuid not null references public.job_listings(id) on delete cascade,
    created_at timestamptz not null default timezone('utc', now()),
    primary key (user_id, job_id)
);

alter table public.saved_jobs enable row level security;

drop policy if exists "Job seekers can view their saved jobs" on public.saved_jobs;
create policy "Job seekers can view their saved jobs"
on public.saved_jobs
for select
to authenticated
using (
    user_id = (select auth.uid())
    and (select public.is_job_seeker())
);

drop policy if exists "Job seekers can save jobs" on public.saved_jobs;
create policy "Job seekers can save jobs"
on public.saved_jobs
for insert
to authenticated
with check (
    user_id = (select auth.uid())
    and (select public.is_job_seeker())
);

drop policy if exists "Job seekers can remove saved jobs" on public.saved_jobs;
create policy "Job seekers can remove saved jobs"
on public.saved_jobs
for delete
to authenticated
using (
    user_id = (select auth.uid())
    and (select public.is_job_seeker())
);
