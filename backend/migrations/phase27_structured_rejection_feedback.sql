alter table public.application_rejection_feedback
    add column if not exists rejection_reason text,
    add column if not exists rejection_note text not null default '',
    add column if not exists rejection_note_shared boolean not null default false,
    add column if not exists rejected_at timestamptz;

alter table public.application_rejection_feedback
    drop constraint if exists application_rejection_feedback_rejection_reason_check;
alter table public.application_rejection_feedback
    add constraint application_rejection_feedback_rejection_reason_check
    check (
        rejection_reason is null
        or rejection_reason in (
            'skills_gap', 'experience_level', 'position_filled',
            'role_requirements_changed', 'application_incomplete', 'other'
        )
    );

alter table public.application_rejection_feedback
    drop constraint if exists application_rejection_feedback_rejection_note_check;
alter table public.application_rejection_feedback
    add constraint application_rejection_feedback_rejection_note_check
    check (char_length(rejection_note) <= 500);

alter table public.application_rejection_feedback enable row level security;

drop policy if exists "Applicants can view their rejection feedback"
    on public.application_rejection_feedback;
drop policy if exists "Providers can view rejection feedback for their applications"
    on public.application_rejection_feedback;
create policy "Providers can view rejection feedback for their applications"
    on public.application_rejection_feedback for select to authenticated
    using (
        provider_id = (select auth.uid())
        and (select public.is_job_provider())
        and (select public.owns_job_application(application_id))
    );

drop policy if exists "Providers can create rejection feedback for their applications"
    on public.application_rejection_feedback;
drop policy if exists "Providers can update rejection feedback for their applications"
    on public.application_rejection_feedback;
revoke insert, update, delete on public.application_rejection_feedback
    from public, anon, authenticated;

create or replace function public.update_job_application_status_with_rejection(
    _application_id uuid,
    _status text,
    _rejection_reason text default null,
    _rejection_note text default null,
    _rejection_note_shared boolean default false
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
    target_application record;
    prior_rejected_at timestamptz;
begin
    if auth.uid() is null or not public.is_job_provider() then
        raise exception using errcode = '42501', message = 'Provider access required.';
    end if;

    if _status is null or _status not in (
        'Submitted', 'CV review', 'Shortlisted', 'Interview', 'Offer', 'Hired', 'Rejected'
    ) then
        raise exception using errcode = '22023', message = 'Invalid application status.';
    end if;

    if _status = 'Rejected' then
        if _rejection_reason is null or _rejection_reason not in (
            'skills_gap', 'experience_level', 'position_filled',
            'role_requirements_changed', 'application_incomplete', 'other'
        ) then
            raise exception using errcode = '22023', message = 'A valid rejection reason is required.';
        end if;
        if _rejection_note is null or char_length(_rejection_note) > 500 then
            raise exception using errcode = '22023', message = 'Rejection note must be 500 characters or fewer.';
        end if;
        if _rejection_note_shared is null then
            raise exception using errcode = '22023', message = 'Rejection note sharing must be specified.';
        end if;
    end if;

    select id, job_id, applicant_id, status
    into target_application
    from public.job_applications
    where id = _application_id
    for update;

    if not found then
        raise exception using errcode = '42501', message = 'Application unavailable.';
    end if;
    if not public.owns_job_listing(target_application.job_id) then
        raise exception using errcode = '42501', message = 'Application unavailable.';
    end if;

    update public.job_applications
    set status = _status
    where id = _application_id;

    if _status = 'Rejected' then
        select rejection_feedback.rejected_at
        into prior_rejected_at
        from public.application_rejection_feedback as rejection_feedback
        where rejection_feedback.application_id = _application_id;

        insert into public.application_rejection_feedback (
            application_id,
            applicant_id,
            provider_id,
            reason_codes,
            feedback,
            rejection_reason,
            rejection_note,
            rejection_note_shared,
            rejected_at
        )
        values (
            _application_id,
            target_application.applicant_id,
            auth.uid(),
            array[]::text[],
            '',
            _rejection_reason,
            _rejection_note,
            _rejection_note_shared,
            coalesce(prior_rejected_at, now())
        )
        on conflict (application_id) do update
        set applicant_id = excluded.applicant_id,
            provider_id = excluded.provider_id,
            reason_codes = array[]::text[],
            feedback = '',
            rejection_reason = excluded.rejection_reason,
            rejection_note = excluded.rejection_note,
            rejection_note_shared = excluded.rejection_note_shared,
            rejected_at = coalesce(prior_rejected_at, excluded.rejected_at);
    else
        delete from public.application_rejection_feedback
        where application_id = _application_id;
    end if;

    return jsonb_build_object(
        'application_id', _application_id,
        'status', _status,
        'rejection_reason', case when _status = 'Rejected' then _rejection_reason else null end,
        'rejection_note', case when _status = 'Rejected' then _rejection_note else null end,
        'rejection_note_shared', case when _status = 'Rejected' then _rejection_note_shared else false end,
        'rejected_at', case
            when _status = 'Rejected' then coalesce(prior_rejected_at, now())
            else null
        end
    );
end;
$$;

revoke all on function public.update_job_application_status_with_rejection(
    uuid, text, text, text, boolean
) from public, anon;
grant execute on function public.update_job_application_status_with_rejection(
    uuid, text, text, text, boolean
) to authenticated;

create or replace function public.get_applicant_rejection_feedback(_application_id uuid)
returns table (
    rejection_reason text,
    rejection_note text,
    rejected_at timestamptz,
    job_title text,
    job_description text,
    job_requirements text
)
language sql
security definer
set search_path = ''
as $$
    select
        coalesce(
            feedback.rejection_reason,
            case
                when cardinality(feedback.reason_codes) = 1 then
                    case feedback.reason_codes[1]
                        when 'skills_alignment' then 'skills_gap'
                        when 'experience_level' then 'experience_level'
                        when 'role_requirements' then 'role_requirements_changed'
                        when 'availability' then 'other'
                        when 'other' then 'other'
                    end
            end
        ),
        case
            when feedback.rejection_note_shared then feedback.rejection_note
            when feedback.rejection_reason is null
                and char_length(feedback.feedback) <= 500
                then nullif(feedback.feedback, '')
            else null
        end,
        feedback.rejected_at,
        listing.title,
        listing.description,
        listing.requirements
    from public.job_applications as application
    join public.job_listings as listing on listing.id = application.job_id
    left join public.application_rejection_feedback as feedback
        on feedback.application_id = application.id
    where application.id = _application_id
      and application.applicant_id = auth.uid()
      and application.status = 'Rejected'
      and public.is_job_seeker();
$$;

revoke all on function public.get_applicant_rejection_feedback(uuid)
    from public, anon;
grant execute on function public.get_applicant_rejection_feedback(uuid)
    to authenticated;

notify pgrst, 'reload schema';
