create table if not exists public.application_interview_slots (
    id uuid primary key default gen_random_uuid(),
    application_id uuid not null
        references public.job_applications (id) on delete cascade,
    provider_id uuid not null default auth.uid()
        references auth.users (id) on delete cascade,
    starts_at timestamptz not null,
    status text not null default 'available'
        check (status in ('available', 'booked', 'cancelled')),
    booked_at timestamptz,
    created_at timestamptz not null default now()
);

create unique index if not exists application_interview_slots_application_time_idx
    on public.application_interview_slots (application_id, starts_at)
    where status in ('available', 'booked');
create unique index if not exists application_interview_slots_one_booked_per_application
    on public.application_interview_slots (application_id)
    where status = 'booked';
create index if not exists application_interview_slots_provider_start_idx
    on public.application_interview_slots (provider_id, starts_at);

alter table public.application_interview_slots enable row level security;

drop policy if exists "Applicants and listing providers can view interview slots"
    on public.application_interview_slots;
create policy "Applicants and listing providers can view interview slots"
    on public.application_interview_slots for select to authenticated
    using (
        (
            provider_id = (select auth.uid())
            and (select public.is_job_provider())
            and (select public.owns_job_application(application_id))
        )
        or (
            (select public.is_job_seeker())
            and exists (
                select 1
                from public.job_applications as application
                where application.id = application_interview_slots.application_id
                  and application.applicant_id = (select auth.uid())
            )
        )
    );

drop policy if exists "Listing providers can create future interview slots"
    on public.application_interview_slots;
create policy "Listing providers can create future interview slots"
    on public.application_interview_slots for insert to authenticated
    with check (
        provider_id = (select auth.uid())
        and (select public.is_job_provider())
        and starts_at > now()
        and status = 'available'
        and booked_at is null
        and (select public.owns_job_application(application_id))
        and exists (
            select 1
            from public.job_applications as application
            where application.id = application_interview_slots.application_id
              and application.status not in ('Hired', 'Rejected', 'Withdrawn')
        )
        and not exists (
            select 1
            from public.application_reviews as review
            where review.application_id = application_interview_slots.application_id
              and review.interview_at is not null
        )
    );

drop policy if exists "Listing providers can remove available interview slots"
    on public.application_interview_slots;
create policy "Listing providers can remove available interview slots"
    on public.application_interview_slots for delete to authenticated
    using (
        provider_id = (select auth.uid())
        and (select public.is_job_provider())
        and status = 'available'
        and (select public.owns_job_application(application_id))
    );

revoke all on public.application_interview_slots from public, anon, authenticated;
grant select, insert, delete on public.application_interview_slots to authenticated;

create or replace function public.guard_interview_slot_insert()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
    perform pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(new.application_id::text, 1)
    );
    perform pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(new.provider_id::text, 0)
    );
    if new.starts_at < pg_catalog.now() + interval '5 minutes'
        or new.starts_at > pg_catalog.now() + interval '1 year'
        or new.status <> 'available' then
        raise exception 'Interview slots must be future and available'
            using errcode = '22023';
    end if;
    if exists (
        select 1
        from public.application_reviews as review
        where review.application_id = new.application_id
          and review.interview_at is not null
    ) then
        raise exception 'Clear the existing interview date before offering slots'
            using errcode = '23514';
    end if;
    if exists (
        select 1
        from public.application_interview_slots as slot
        where slot.provider_id = new.provider_id
          and slot.application_id <> new.application_id
          and slot.status in ('available', 'booked')
          and slot.starts_at < new.starts_at + interval '30 minutes'
          and slot.starts_at > new.starts_at - interval '30 minutes'
    ) or exists (
        select 1
        from public.application_reviews as review
        join public.job_applications as application
          on application.id = review.application_id
        join public.job_listings as listing
          on listing.id = application.job_id
        where listing.provider_id = new.provider_id
          and review.interview_at is not null
          and review.interview_at < new.starts_at + interval '30 minutes'
          and review.interview_at > new.starts_at - interval '30 minutes'
    ) then
        raise exception 'The provider already has an interview at this time'
            using errcode = '23505';
    end if;
    return new;
end;
$$;

drop trigger if exists guard_interview_slot_insert
    on public.application_interview_slots;
create trigger guard_interview_slot_insert
    before insert on public.application_interview_slots
    for each row execute function public.guard_interview_slot_insert();

revoke all on function public.guard_interview_slot_insert()
    from public, anon, authenticated;

alter table public.notifications
    drop constraint if exists notifications_notification_type_check;
alter table public.notifications
    add constraint notifications_notification_type_check
    check (notification_type in (
        'status_change', 'interview_slot_available', 'interview_slot_unavailable',
        'interview_scheduled', 'interview_cancelled', 'follow_up'
    ));

create or replace function public.record_interview_slot_change()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
    application public.job_applications;
begin
    if tg_op = 'DELETE' then
        select * into application
        from public.job_applications
        where id = old.application_id;
        delete from public.notifications
        where notification_type = 'interview_slot_available'
          and data ->> 'slot_id' = old.id::text;
        if application.id is not null
            and application.status not in ('Hired', 'Rejected', 'Withdrawn') then
            insert into public.notifications (
                user_id, notification_type, title, body, data, dedupe_key
            ) values (
                application.applicant_id,
                'interview_slot_unavailable',
                'Interview time removed',
                pg_catalog.format('An offered interview time for %s at %s is no longer available.',
                    application.job_title, application.company),
                pg_catalog.jsonb_build_object(
                    'application_id', old.application_id,
                    'interview_at', old.starts_at,
                    'slot_id', old.id
                ),
                old.id::text || ':unavailable:' || pg_catalog.gen_random_uuid()::text
            ) on conflict do nothing;
        end if;
        return old;
    end if;

    select * into application
    from public.job_applications
    where id = new.application_id;

    if tg_op = 'INSERT' and new.status = 'available' then
        insert into public.notifications (
            user_id, notification_type, title, body, data, dedupe_key
        ) values (
            application.applicant_id,
            'interview_slot_available',
            'Interview time offered',
            pg_catalog.format('A new interview time is available for %s at %s.',
                application.job_title, application.company),
            pg_catalog.jsonb_build_object(
                'application_id', new.application_id,
                'interview_at', new.starts_at,
                'slot_id', new.id
            ),
            new.id::text || ':available:' || pg_catalog.gen_random_uuid()::text
        ) on conflict do nothing;
    elsif tg_op = 'UPDATE'
        and new.status = 'booked'
        and old.status is distinct from new.status then
        insert into public.application_reviews (
            application_id, provider_id, reviewer_notes, interview_at
        ) values (
            new.application_id, new.provider_id, '', new.starts_at
        )
        on conflict (application_id) do update
        set interview_at = excluded.interview_at;

        insert into public.notifications (
            user_id, notification_type, title, body, data, dedupe_key
        ) values (
            new.provider_id,
            'interview_scheduled',
            'Interview slot booked',
            pg_catalog.format('An applicant booked an interview for %s at %s.',
                application.job_title, application.company),
            pg_catalog.jsonb_build_object(
                'application_id', new.application_id,
                'interview_at', new.starts_at,
                'slot_id', new.id
            ),
            new.id::text || ':booked:' || pg_catalog.gen_random_uuid()::text
        ) on conflict do nothing;
    elsif tg_op = 'UPDATE'
        and old.status = 'available'
        and new.status = 'cancelled' then
        delete from public.notifications
        where notification_type = 'interview_slot_available'
          and data ->> 'slot_id' = old.id::text;
        if application.status not in ('Hired', 'Rejected', 'Withdrawn') then
            insert into public.notifications (
                user_id, notification_type, title, body, data, dedupe_key
            ) values (
                application.applicant_id,
                'interview_slot_unavailable',
                'Interview time removed',
                pg_catalog.format('An offered interview time for %s at %s is no longer available.',
                    application.job_title, application.company),
                pg_catalog.jsonb_build_object(
                    'application_id', new.application_id,
                    'interview_at', new.starts_at,
                    'slot_id', new.id
                ),
                new.id::text || ':unavailable:' || pg_catalog.gen_random_uuid()::text
            ) on conflict do nothing;
        end if;
    elsif tg_op = 'UPDATE'
        and old.status = 'booked'
        and new.status = 'cancelled' then
        update public.application_reviews
        set interview_at = null
        where application_id = new.application_id
          and interview_at = old.starts_at;

        delete from public.notifications
        where notification_type = 'interview_scheduled'
          and data ->> 'application_id' = new.application_id::text;

        insert into public.notifications (
            user_id, notification_type, title, body, data, dedupe_key
        ) values
        (
            application.applicant_id,
            'interview_cancelled',
            'Interview cancelled',
            pg_catalog.format('The interview for %s at %s on %s was cancelled.',
                application.job_title, application.company,
                pg_catalog.to_char(new.starts_at at time zone 'UTC', 'Mon DD, YYYY HH24:MI UTC')),
            pg_catalog.jsonb_build_object(
                'application_id', new.application_id,
                'interview_at', old.starts_at,
                'slot_id', new.id
            ),
            new.id::text || ':cancelled:applicant:' || pg_catalog.gen_random_uuid()::text
        ),
        (
            new.provider_id,
            'interview_cancelled',
            'Interview cancelled',
            pg_catalog.format('The interview for %s at %s on %s was cancelled.',
                application.job_title, application.company,
                pg_catalog.to_char(new.starts_at at time zone 'UTC', 'Mon DD, YYYY HH24:MI UTC')),
            pg_catalog.jsonb_build_object(
                'application_id', new.application_id,
                'interview_at', old.starts_at,
                'slot_id', new.id
            ),
            new.id::text || ':cancelled:provider:' || pg_catalog.gen_random_uuid()::text
        ) on conflict do nothing;
    end if;
    return new;
end;
$$;

drop trigger if exists record_interview_slot_change
    on public.application_interview_slots;
create trigger record_interview_slot_change
    after update of status on public.application_interview_slots
    for each row execute function public.record_interview_slot_change();

drop trigger if exists notify_interview_slot_insert
    on public.application_interview_slots;
create trigger notify_interview_slot_insert
    after insert on public.application_interview_slots
    for each row execute function public.record_interview_slot_change();

drop trigger if exists remove_interview_slot_notice
    on public.application_interview_slots;
create trigger remove_interview_slot_notice
    after delete on public.application_interview_slots
    for each row execute function public.record_interview_slot_change();

revoke all on function public.record_interview_slot_change()
    from public, anon, authenticated;

create or replace function public.cancel_slots_for_closed_application()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
    if old.status is distinct from new.status
        and new.status in ('Hired', 'Rejected', 'Withdrawn') then
        update public.application_interview_slots
        set status = 'cancelled', booked_at = null
        where application_id = new.id
          and status in ('available', 'booked');
    end if;
    return new;
end;
$$;

drop trigger if exists cancel_interview_slots_for_closed_application
    on public.job_applications;
create trigger cancel_interview_slots_for_closed_application
    after update of status on public.job_applications
    for each row execute function public.cancel_slots_for_closed_application();

revoke all on function public.cancel_slots_for_closed_application()
    from public, anon, authenticated;

create or replace function public.guard_interview_review_slot_date()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
    booked_start timestamptz;
    has_available_slots boolean;
    owner_provider_id uuid;
begin
    perform pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(new.application_id::text, 1)
    );
    select listing.provider_id into owner_provider_id
    from public.job_applications as application
    join public.job_listings as listing on listing.id = application.job_id
    where application.id = new.application_id;
    if owner_provider_id is not null then
        perform pg_catalog.pg_advisory_xact_lock(
            pg_catalog.hashtextextended(owner_provider_id::text, 0)
        );
    end if;

    select starts_at into booked_start
    from public.application_interview_slots
    where application_id = new.application_id
      and status = 'booked'
    limit 1;

    if found then
        if new.interview_at is distinct from booked_start then
            raise exception 'Manage this interview through its booked slot'
                using errcode = '23514';
        end if;
    else
        select exists (
            select 1
            from public.application_interview_slots
            where application_id = new.application_id
              and status = 'available'
        ) into has_available_slots;
        if has_available_slots and new.interview_at is not null then
            raise exception 'Remove available slots before setting a manual interview date'
                using errcode = '23514';
        end if;
    end if;
    if new.interview_at is not null and owner_provider_id is not null and (
        exists (
            select 1
            from public.application_interview_slots as slot
            where slot.provider_id = owner_provider_id
              and slot.application_id <> new.application_id
              and slot.status = 'booked'
              and slot.starts_at < new.interview_at + interval '30 minutes'
              and slot.starts_at > new.interview_at - interval '30 minutes'
        )
        or exists (
            select 1
            from public.application_reviews as review
            join public.job_applications as application
              on application.id = review.application_id
            join public.job_listings as listing
              on listing.id = application.job_id
            where listing.provider_id = owner_provider_id
              and review.application_id <> new.application_id
              and review.interview_at < new.interview_at + interval '30 minutes'
              and review.interview_at > new.interview_at - interval '30 minutes'
        )
    ) then
        raise exception 'The provider already has an interview at this time'
            using errcode = '23505';
    end if;
    return new;
end;
$$;

drop trigger if exists guard_interview_review_slot_date
    on public.application_reviews;
create trigger guard_interview_review_slot_date
    before insert or update of interview_at on public.application_reviews
    for each row execute function public.guard_interview_review_slot_date();

revoke all on function public.guard_interview_review_slot_date()
    from public, anon, authenticated;

create or replace function public.book_application_interview_slot(_slot_id uuid)
returns public.application_interview_slots
language plpgsql
security definer
set search_path = ''
as $$
declare
    slot public.application_interview_slots;
    application public.job_applications;
begin
    if (select auth.uid()) is null or not (select public.is_job_seeker()) then
        raise exception 'Job seekers only' using errcode = '42501';
    end if;

    select * into slot
    from public.application_interview_slots
    where id = _slot_id and status = 'available'
    for update;
    if not found then
        raise exception 'Interview slot is no longer available' using errcode = 'P0002';
    end if;

    select * into application
    from public.job_applications
    where id = slot.application_id;
    if application.applicant_id <> (select auth.uid())
        or application.status in ('Hired', 'Rejected', 'Withdrawn') then
        raise exception 'Interview slot is not available for this application' using errcode = '42501';
    end if;
    if slot.starts_at <= pg_catalog.now() then
        raise exception 'Interview slot has passed' using errcode = '22023';
    end if;

    perform pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(slot.application_id::text, 1)
    );
    perform pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(slot.provider_id::text, 0)
    );
    if exists (
        select 1
        from public.application_interview_slots as other_slot
        where other_slot.provider_id = slot.provider_id
          and other_slot.status = 'booked'
          and other_slot.id <> slot.id
          and other_slot.starts_at < slot.starts_at + interval '30 minutes'
          and other_slot.starts_at > slot.starts_at - interval '30 minutes'
    ) then
        raise exception 'The provider already has an interview at this time'
            using errcode = '23505';
    end if;
    if exists (
        select 1
        from public.application_reviews as review
        join public.job_applications as other_application
          on other_application.id = review.application_id
        join public.job_listings as listing
          on listing.id = other_application.job_id
        where listing.provider_id = slot.provider_id
          and review.application_id <> slot.application_id
          and review.interview_at < slot.starts_at + interval '30 minutes'
          and review.interview_at > slot.starts_at - interval '30 minutes'
    ) then
        raise exception 'The provider already has an interview at this time'
            using errcode = '23505';
    end if;
    if exists (
        select 1
        from public.application_reviews as review
        where review.application_id = slot.application_id
          and review.interview_at is not null
    ) then
        raise exception 'Clear the existing interview date before booking a slot'
            using errcode = '23514';
    end if;

    update public.application_interview_slots
    set status = 'booked', booked_at = pg_catalog.now()
    where id = slot.id
    returning * into slot;
    update public.application_interview_slots
    set status = 'cancelled', booked_at = null
    where provider_id = slot.provider_id
      and id <> slot.id
      and status = 'available'
      and starts_at < slot.starts_at + interval '30 minutes'
      and starts_at > slot.starts_at - interval '30 minutes';
    return slot;
end;
$$;

create or replace function public.cancel_application_interview_slot(_slot_id uuid)
returns public.application_interview_slots
language plpgsql
security definer
set search_path = ''
as $$
declare
    slot public.application_interview_slots;
begin
    if (select auth.uid()) is null or not (select public.is_job_seeker()) then
        raise exception 'Job seekers only' using errcode = '42501';
    end if;

    select candidate.* into slot
    from public.application_interview_slots as candidate
    join public.job_applications as application
      on application.id = candidate.application_id
    where candidate.id = _slot_id
      and candidate.status = 'booked'
      and candidate.starts_at > pg_catalog.now()
      and application.applicant_id = (select auth.uid())
    for update of candidate;
    if not found then
        raise exception 'Booked interview not found' using errcode = 'P0002';
    end if;

    update public.application_interview_slots
    set status = 'cancelled', booked_at = null
    where id = slot.id
    returning * into slot;
    return slot;
end;
$$;

create or replace function public.cancel_provider_interview_slot(_slot_id uuid)
returns public.application_interview_slots
language plpgsql
security definer
set search_path = ''
as $$
declare
    slot public.application_interview_slots;
begin
    if (select auth.uid()) is null or not (select public.is_job_provider()) then
        raise exception 'Job providers only' using errcode = '42501';
    end if;

    select candidate.* into slot
    from public.application_interview_slots as candidate
    where candidate.id = _slot_id
      and candidate.provider_id = (select auth.uid())
      and candidate.status in ('available', 'booked')
      and (select public.owns_job_application(candidate.application_id))
    for update;
    if not found then
        raise exception 'Interview slot not found' using errcode = 'P0002';
    end if;

    update public.application_interview_slots
    set status = 'cancelled', booked_at = null
    where id = slot.id
    returning * into slot;
    return slot;
end;
$$;

revoke all on function public.book_application_interview_slot(uuid)
    from public, anon;
revoke all on function public.cancel_application_interview_slot(uuid)
    from public, anon;
revoke all on function public.cancel_provider_interview_slot(uuid)
    from public, anon;
grant execute on function public.book_application_interview_slot(uuid)
    to authenticated;
grant execute on function public.cancel_application_interview_slot(uuid)
    to authenticated;
grant execute on function public.cancel_provider_interview_slot(uuid)
    to authenticated;

notify pgrst, 'reload schema';
