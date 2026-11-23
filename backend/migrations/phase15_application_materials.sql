create table if not exists public.application_material_drafts (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null default auth.uid()
        references auth.users (id) on delete cascade,
    job_id uuid not null references public.job_listings (id) on delete cascade,
    bullets jsonb not null default '[]'::jsonb,
    cover_letter text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (user_id, job_id),
    constraint application_material_bullet_count
        check (jsonb_array_length(bullets) <= 8),
    constraint application_material_cover_letter_length
        check (char_length(btrim(cover_letter)) between 40 and 12000)
);

create index if not exists application_material_drafts_user_updated_idx
    on public.application_material_drafts (user_id, updated_at desc);

drop trigger if exists set_application_material_drafts_updated_at
    on public.application_material_drafts;
create trigger set_application_material_drafts_updated_at
    before update on public.application_material_drafts
    for each row execute function public.set_career_profile_updated_at();

drop trigger if exists set_application_material_drafts_updated_at
    on public.application_material_drafts;
create trigger set_application_material_drafts_updated_at
    before update on public.application_material_drafts
    for each row execute function public.set_career_profile_updated_at();

alter table public.application_material_drafts enable row level security;

drop policy if exists "Job seekers can view their application materials"
    on public.application_material_drafts;
create policy "Job seekers can view their application materials"
    on public.application_material_drafts for select to authenticated
    using (
        (select auth.uid()) = user_id
        and (select public.is_job_seeker())
    );

drop policy if exists "Job seekers can save their application materials"
    on public.application_material_drafts;
create policy "Job seekers can save their application materials"
    on public.application_material_drafts for insert to authenticated
    with check (
        (select auth.uid()) = user_id
        and (select public.is_job_seeker())
    );

drop policy if exists "Job seekers can update their application materials"
    on public.application_material_drafts;
create policy "Job seekers can update their application materials"
    on public.application_material_drafts for update to authenticated
    using (
        (select auth.uid()) = user_id
        and (select public.is_job_seeker())
    )
    with check (
        (select auth.uid()) = user_id
        and (select public.is_job_seeker())
    );

drop policy if exists "Job seekers can delete their application materials"
    on public.application_material_drafts;
create policy "Job seekers can delete their application materials"
    on public.application_material_drafts for delete to authenticated
    using (
        (select auth.uid()) = user_id
        and (select public.is_job_seeker())
    );

revoke all on public.application_material_drafts from anon, authenticated;
grant select, insert, update, delete on public.application_material_drafts to authenticated;

notify pgrst, 'reload schema';
