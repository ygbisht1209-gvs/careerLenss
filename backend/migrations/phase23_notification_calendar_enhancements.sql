create or replace function public.notify_application_status_change()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
    recipient_id uuid;
    notification_title text;
    notification_body text;
begin
    if old.status is distinct from new.status then
        recipient_id := new.applicant_id;
        notification_title := 'Application status updated';
        notification_body := format('%s at %s moved from %s to %s.',
            new.job_title, new.company, old.status, new.status);

        if new.status = 'Withdrawn' and auth.uid() = new.applicant_id then
            select provider_id into recipient_id
            from public.job_listings
            where id = new.job_id;
            notification_title := 'Applicant withdrew';
            notification_body := format('An applicant withdrew from %s at %s.',
                new.job_title, new.company);
        end if;

        if recipient_id is null then
            return new;
        end if;

        insert into public.notifications (
            user_id, notification_type, title, body, data, dedupe_key
        ) values (
            recipient_id,
            'status_change',
            notification_title,
            notification_body,
            jsonb_build_object(
                'application_id', new.id,
                'job_id', new.job_id,
                'from_status', old.status,
                'status', new.status
            ),
            new.id::text || ':' || gen_random_uuid()::text
        ) on conflict do nothing;
    end if;
    return new;
end;
$$;

revoke all on function public.notify_application_status_change()
    from public, anon;

notify pgrst, 'reload schema';
