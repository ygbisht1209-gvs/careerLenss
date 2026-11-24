alter table public.resume_versions
    add column if not exists file_size bigint;

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conrelid = 'public.resume_versions'::regclass
          and conname = 'resume_versions_file_size_check'
    ) then
        alter table public.resume_versions
            add constraint resume_versions_file_size_check
            check (file_size is null or file_size between 1 and 5242880);
    end if;
end
$$;

create or replace function public.enforce_resume_version_limit()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    perform pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(new.user_id::text, 0)
    );

    if (
        select count(*)
        from public.resume_versions as version
        where version.user_id = new.user_id
    ) >= 10 then
        raise exception 'A maximum of 10 résumé versions is allowed.'
            using errcode = '23514';
    end if;

    return new;
end;
$$;

drop trigger if exists enforce_resume_version_limit
    on public.resume_versions;
create trigger enforce_resume_version_limit
    before insert on public.resume_versions
    for each row execute function public.enforce_resume_version_limit();

drop policy if exists "Job seekers can create their résumé versions"
    on public.resume_versions;
create policy "Job seekers can create their résumé versions"
    on public.resume_versions for insert to authenticated
    with check (
        user_id = (select auth.uid())
        and (select public.is_job_seeker())
        and split_part(storage_path, '/', 1) = (select auth.uid())::text
        and split_part(storage_path, '/', 2) = 'versions'
        and file_size between 1 and 5242880
    );

drop policy if exists "Job seekers can rename their résumé versions"
    on public.resume_versions;
create policy "Job seekers can rename their résumé versions"
    on public.resume_versions for update to authenticated
    using (
        user_id = (select auth.uid())
        and (select public.is_job_seeker())
    )
    with check (
        user_id = (select auth.uid())
        and (select public.is_job_seeker())
    );

drop policy if exists "Job seekers can delete unlinked résumé versions"
    on public.resume_versions;
drop policy if exists "Job seekers can delete their résumé versions"
    on public.resume_versions;
create policy "Job seekers can delete their résumé versions"
    on public.resume_versions for delete to authenticated
    using (
        user_id = (select auth.uid())
        and (select public.is_job_seeker())
    );

grant update (label) on public.resume_versions to authenticated;

create or replace function public.get_resume_version_insights()
returns table (
    resume_version_id uuid,
    label text,
    created_at timestamptz,
    applications_sent bigint,
    shortlisted_or_better bigint,
    shortlist_rate numeric,
    sufficient_data boolean
)
language sql
stable
security definer
set search_path = ''
as $$
    select
        version.id,
        version.label,
        version.created_at,
        count(application.id)::bigint as applications_sent,
        count(application.id) filter (
            where application.status in ('Shortlisted', 'Interview', 'Offer', 'Hired')
        )::bigint as shortlisted_or_better,
        case
            when count(application.id) >= 5 then round(
                count(application.id) filter (
                    where application.status in ('Shortlisted', 'Interview', 'Offer', 'Hired')
                ) * 100.0 / count(application.id),
                1
            )
            else null
        end as shortlist_rate,
        count(application.id) >= 5 as sufficient_data
    from public.resume_versions as version
    left join public.job_applications as application
        on application.resume_version_id = version.id
    where version.user_id = (select auth.uid())
      and (select public.is_job_seeker())
    group by version.id, version.label, version.created_at
    order by version.created_at desc, version.id;
$$;

revoke all on function public.get_resume_version_insights()
    from public, anon, authenticated;
grant execute on function public.get_resume_version_insights()
    to authenticated;

revoke all on function public.enforce_resume_version_limit()
    from public, anon, authenticated;

notify pgrst, 'reload schema';
