create index if not exists application_status_events_applicant_changed_idx
    on public.application_status_events (
        applicant_id, changed_at, application_id
    );

notify pgrst, 'reload schema';
