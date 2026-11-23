-- Provider ranking reads only evidence belonging to a person who applied to one
-- of the provider's listings. Résumés remain in the private storage bucket.

drop policy if exists "Listing providers can view applicant career profiles"
    on public.career_profiles;
create policy "Listing providers can view applicant career profiles"
    on public.career_profiles for select to authenticated
    using (
        exists (
            select 1
            from public.job_applications as application
            join public.job_listings as listing on listing.id = application.job_id
            where application.applicant_id = career_profiles.user_id
              and listing.provider_id = (select auth.uid())
        )
    );

drop policy if exists "Listing providers can view applicant career projects"
    on public.career_projects;
create policy "Listing providers can view applicant career projects"
    on public.career_projects for select to authenticated
    using (
        exists (
            select 1
            from public.job_applications as application
            join public.job_listings as listing on listing.id = application.job_id
            where application.applicant_id = career_projects.user_id
              and listing.provider_id = (select auth.uid())
        )
    );

notify pgrst, 'reload schema';

create table if not exists public.notifications (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null default auth.uid()
        references auth.users (id) on delete cascade,
    notification_type text not null
        check (notification_type in ('status_change', 'interview_scheduled', 'follow_up')),
    title text not null check (char_length(btrim(title)) between 1 and 160),
    body text not null check (char_length(btrim(body)) between 1 and 2000),
    data jsonb not null default '{}'::jsonb,
    dedupe_key text not null,
    read_at timestamptz,
    created_at timestamptz not null default now(),
    unique (user_id, notification_type, dedupe_key)
);

create index if not exists notifications_user_created_idx
    on public.notifications (user_id, created_at desc);
create index if not exists notifications_user_unread_idx
    on public.notifications (user_id, created_at desc)
    where read_at is null;

alter table public.notifications enable row level security;

drop policy if exists "Users can view their notifications" on public.notifications;
create policy "Users can view their notifications"
    on public.notifications for select to authenticated
    using ((select auth.uid()) = user_id);

drop policy if exists "Users can mark their notifications read" on public.notifications;
create policy "Users can mark their notifications read"
    on public.notifications for update to authenticated
    using ((select auth.uid()) = user_id)
    with check ((select auth.uid()) = user_id);

revoke all on public.notifications from anon, authenticated;
grant select, update (read_at) on public.notifications to authenticated;

create or replace function public.notify_application_status_change()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    if old.status is distinct from new.status
        and new.status in ('Shortlisted', 'Interview', 'Rejected') then
        insert into public.notifications (
            user_id, notification_type, title, body, data, dedupe_key
        ) values (
            new.applicant_id,
            'status_change',
            'Application status updated',
            format('%s at %s moved to %s.', new.job_title, new.company, new.status),
            jsonb_build_object(
                'application_id', new.id,
                'job_id', new.job_id,
                'status', new.status
            ),
            new.id::text || ':' || new.status
        ) on conflict do nothing;
    end if;
    return new;
end;
$$;

drop trigger if exists notify_job_application_status_change
    on public.job_applications;
create trigger notify_job_application_status_change
    after update of status on public.job_applications
    for each row execute function public.notify_application_status_change();

create or replace function public.notify_interview_scheduled()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
    application public.job_applications;
begin
    if new.interview_at is not null
        and (tg_op = 'INSERT' or old.interview_at is distinct from new.interview_at) then
        select * into application
        from public.job_applications
        where id = new.application_id;
        insert into public.notifications (
            user_id, notification_type, title, body, data, dedupe_key
        ) values (
            application.applicant_id,
            'interview_scheduled',
            'Interview scheduled',
            format('%s at %s has an interview scheduled for %s.',
                application.job_title, application.company,
                to_char(new.interview_at at time zone 'UTC', 'Mon DD, YYYY HH24:MI UTC')),
            jsonb_build_object(
                'application_id', application.id,
                'interview_at', new.interview_at
            ),
            new.application_id::text || ':' || new.interview_at::text
        ) on conflict do nothing;
    end if;
    return new;
end;
$$;

drop trigger if exists notify_interview_scheduled on public.application_reviews;
create trigger notify_interview_scheduled
    after insert or update of interview_at on public.application_reviews
    for each row execute function public.notify_interview_scheduled();

revoke all on function public.notify_application_status_change() from public, anon;
revoke all on function public.notify_interview_scheduled() from public, anon;

notify pgrst, 'reload schema';
