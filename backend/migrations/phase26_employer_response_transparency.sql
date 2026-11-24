create index if not exists application_status_events_app_response_idx
    on public.application_status_events (application_id, changed_at);

drop policy if exists "Listing providers can view their application status history"
    on public.application_status_events;
create policy "Listing providers can view their application status history"
    on public.application_status_events for select to authenticated
    using (
        (select public.is_job_provider())
        and exists (
            select 1
            from public.job_applications as application
            where application.id = application_status_events.application_id
                and (select public.owns_job_listing(application.job_id))
        )
    );

revoke all on public.application_status_events from public, anon, authenticated;
grant select on public.application_status_events to authenticated;

create or replace function public.get_job_responsiveness(_job_id uuid default null)
returns table (
    job_id uuid,
    response_rate numeric,
    median_first_response_days numeric,
    sample_size bigint,
    sufficient_data boolean
)
language plpgsql
security definer
set search_path = ''
as $$
begin
    if auth.uid() is null
        or not (
            public.is_job_seeker()
            or public.is_job_provider()
        )
    then
        return;
    end if;

    return query
    with authorized_listings as (
        select listing.id
        from public.job_listings as listing
        where (_job_id is null or listing.id = _job_id)
            and (
                (public.is_job_seeker() and listing.status = 'published')
                or (
                    public.is_job_provider()
                    and listing.provider_id = auth.uid()
                )
            )
    ),
    application_response_events as (
        select
            application.id,
            application.job_id,
            application.status,
            application.created_at,
            min(event.changed_at) filter (
                where event.from_status = 'Submitted'
                    and event.to_status in (
                        'CV review', 'Shortlisted', 'Interview', 'Offer', 'Hired', 'Rejected'
                    )
                    and event.changed_at >= application.created_at
            ) as first_response_at
        from public.job_applications as application
        join authorized_listings as authorized
            on authorized.id = application.job_id
        left join public.application_status_events as event
            on event.application_id = application.id
        group by
            application.id,
            application.job_id,
            application.status,
            application.created_at
    ),
    listing_metrics as (
        select
            response_event.job_id,
            count(*)::bigint as sample_size,
            count(*) filter (
                where response_event.first_response_at is not null
                    or response_event.status in (
                        'CV review', 'Shortlisted', 'Interview', 'Offer', 'Hired', 'Rejected'
                    )
            )::bigint as response_count,
            percentile_cont(0.5) within group (
                order by extract(
                    epoch from (
                        response_event.first_response_at - response_event.created_at
                    )
                ) / 86400.0
            ) filter (
                where response_event.first_response_at is not null
            ) as median_days
        from application_response_events as response_event
        group by response_event.job_id
    )
    select
        listing.id,
        case
            when coalesce(metrics.sample_size, 0) >= 5
                then round(metrics.response_count::numeric * 100
                    / nullif(metrics.sample_size, 0), 2)
            else null
        end,
        case
            when coalesce(metrics.sample_size, 0) >= 5
                then metrics.median_days::numeric
            else null
        end,
        coalesce(metrics.sample_size, 0),
        coalesce(metrics.sample_size, 0) >= 5
    from authorized_listings as listing
    left join listing_metrics as metrics on metrics.job_id = listing.id;
end;
$$;

revoke all on function public.get_job_responsiveness(uuid)
    from public, anon, authenticated;
grant execute on function public.get_job_responsiveness(uuid)
    to authenticated;

create or replace function public.get_provider_response_metrics()
returns table (
    response_rate numeric,
    median_first_response_days numeric,
    sample_size bigint,
    sufficient_data boolean
)
language plpgsql
security definer
set search_path = ''
as $$
begin
    if auth.uid() is null or not public.is_job_provider() then
        return;
    end if;

    return query
    with application_response_events as (
        select
            application.id,
            application.job_id,
            application.status,
            application.created_at,
            min(event.changed_at) filter (
                where event.from_status = 'Submitted'
                and event.to_status in (
                    'CV review', 'Shortlisted', 'Interview', 'Offer', 'Hired', 'Rejected'
                )
                and event.changed_at >= application.created_at
            ) as first_response_at
        from public.job_applications as application
        left join public.application_status_events as event
            on event.application_id = application.id
        join public.job_listings as listing
            on listing.id = application.job_id
        where listing.provider_id = auth.uid()
        group by
            application.id,
            application.job_id,
            application.status,
            application.created_at
    ),
    provider_metrics as (
        select
            count(*)::bigint as sample_size,
            count(*) filter (
                where response_event.first_response_at is not null
                    or response_event.status in (
                        'CV review', 'Shortlisted', 'Interview', 'Offer', 'Hired', 'Rejected'
                    )
            )::bigint as response_count,
            percentile_cont(0.5) within group (
                order by extract(
                    epoch from (
                        response_event.first_response_at - response_event.created_at
                    )
                ) / 86400.0
            ) filter (
                where response_event.first_response_at is not null
            ) as median_days
        from application_response_events as response_event
    )
    select
        case
            when provider_metrics.sample_size >= 5
                then round(provider_metrics.response_count::numeric * 100
                    / nullif(provider_metrics.sample_size, 0), 2)
            else null
        end,
        case
            when provider_metrics.sample_size >= 5
                then provider_metrics.median_days::numeric
            else null
        end,
        provider_metrics.sample_size,
        provider_metrics.sample_size >= 5
    from provider_metrics;
end;
$$;

revoke all on function public.get_provider_response_metrics()
    from public, anon, authenticated;
grant execute on function public.get_provider_response_metrics()
    to authenticated;

notify pgrst, 'reload schema';
