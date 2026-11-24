create table if not exists public.application_status_events (
    id uuid primary key default gen_random_uuid(),
    application_id uuid not null
        references public.job_applications (id) on delete cascade,
    applicant_id uuid not null
        references auth.users (id) on delete cascade,
    from_status text
        check (from_status is null or from_status in (
            'Submitted', 'CV review', 'Shortlisted', 'Interview',
            'Offer', 'Hired', 'Rejected', 'Withdrawn'
        )),
    to_status text not null
        check (to_status in (
            'Submitted', 'CV review', 'Shortlisted', 'Interview',
            'Offer', 'Hired', 'Rejected', 'Withdrawn'
        )),
    changed_at timestamptz not null default now()
);

create index if not exists application_status_events_applicant_idx
    on public.application_status_events (applicant_id, application_id, changed_at);

alter table public.application_status_events enable row level security;

drop policy if exists "Applicants can view their application status history"
    on public.application_status_events;
create policy "Applicants can view their application status history"
    on public.application_status_events for select to authenticated
    using (
        applicant_id = (select auth.uid())
        and (select public.is_job_seeker())
    );

revoke all on public.application_status_events from public, anon, authenticated;
grant select on public.application_status_events to authenticated;

create or replace function public.record_application_status_event()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
    if tg_op = 'INSERT' then
        insert into public.application_status_events (
            application_id, applicant_id, from_status, to_status
        ) values (
            new.id, new.applicant_id, null, new.status
        );
    elsif old.status is distinct from new.status then
        insert into public.application_status_events (
            application_id, applicant_id, from_status, to_status
        ) values (
            new.id, new.applicant_id, old.status, new.status
        );
    end if;
    return new;
end;
$$;

drop trigger if exists record_application_status_event
    on public.job_applications;
create trigger record_application_status_event
    after insert or update on public.job_applications
    for each row execute function public.record_application_status_event();

revoke all on function public.record_application_status_event()
    from public, anon, authenticated;

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
    );

notify pgrst, 'reload schema';
