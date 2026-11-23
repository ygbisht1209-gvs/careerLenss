create table if not exists public.applications (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
    title text not null check (char_length(btrim(title)) between 1 and 100),
    company text not null check (char_length(btrim(company)) between 1 and 100),
    applied_on date not null,
    status text not null default 'Applied'
        check (status in ('Applied', 'Under Review', 'Interview', 'Offer', 'Rejected')),
    job_url text not null default '',
    follow_up_on date,
    notes text not null default '',
    created_at timestamptz not null default now()
);

alter table public.applications
    add column if not exists job_url text not null default '',
    add column if not exists follow_up_on date,
    add column if not exists notes text not null default '';

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conrelid = 'public.applications'::regclass
            and conname = 'applications_job_url_length'
    ) then
        alter table public.applications
            add constraint applications_job_url_length
            check (char_length(job_url) <= 2048);
    end if;
    if not exists (
        select 1
        from pg_constraint
        where conrelid = 'public.applications'::regclass
            and conname = 'applications_notes_length'
    ) then
        alter table public.applications
            add constraint applications_notes_length
            check (char_length(notes) <= 2000);
    end if;
    if not exists (
        select 1
        from pg_constraint
        where conrelid = 'public.applications'::regclass
            and conname = 'applications_follow_up_after_applied'
    ) then
        alter table public.applications
            add constraint applications_follow_up_after_applied
            check (follow_up_on is null or follow_up_on >= applied_on);
    end if;
end;
$$;

create index if not exists applications_user_applied_on_idx
    on public.applications (user_id, applied_on desc);
create index if not exists applications_user_status_idx
    on public.applications (user_id, status);
create index if not exists applications_user_follow_up_idx
    on public.applications (user_id, follow_up_on)
    where follow_up_on is not null;

alter table public.applications enable row level security;

drop policy if exists "Users can view their applications" on public.applications;
create policy "Users can view their applications"
    on public.applications for select to authenticated
    using ((select auth.uid()) = user_id);

drop policy if exists "Users can add their applications" on public.applications;
create policy "Users can add their applications"
    on public.applications for insert to authenticated
    with check ((select auth.uid()) = user_id);

drop policy if exists "Users can update their applications" on public.applications;
create policy "Users can update their applications"
    on public.applications for update to authenticated
    using ((select auth.uid()) = user_id)
    with check ((select auth.uid()) = user_id);

drop policy if exists "Users can delete their applications" on public.applications;
create policy "Users can delete their applications"
    on public.applications for delete to authenticated
    using ((select auth.uid()) = user_id);

create table if not exists public.career_profiles (
    user_id uuid primary key references auth.users (id) on delete cascade,
    current_position text not null default '',
    target_role text not null default '',
    headline text not null default '',
    about text not null default '',
    skills text[] not null default '{}',
    location text not null default '',
    phone text not null default '',
    education text not null default '',
    updated_at timestamptz not null default now()
);

alter table public.career_profiles
    add column if not exists current_position text not null default '',
    add column if not exists location text not null default '',
    add column if not exists phone text not null default '',
    add column if not exists education text not null default '';

alter table public.career_profiles enable row level security;

create or replace function public.set_career_profile_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists set_career_profile_updated_at on public.career_profiles;
create trigger set_career_profile_updated_at
    before update on public.career_profiles
    for each row execute function public.set_career_profile_updated_at();

drop policy if exists "Users can view their career profile" on public.career_profiles;
create policy "Users can view their career profile"
    on public.career_profiles for select to authenticated
    using ((select auth.uid()) = user_id);

drop policy if exists "Users can create their career profile" on public.career_profiles;
create policy "Users can create their career profile"
    on public.career_profiles for insert to authenticated
    with check ((select auth.uid()) = user_id);

drop policy if exists "Users can update their career profile" on public.career_profiles;
create policy "Users can update their career profile"
    on public.career_profiles for update to authenticated
    using ((select auth.uid()) = user_id)
    with check ((select auth.uid()) = user_id);

grant select, insert, update, delete on public.applications to authenticated;
grant select, insert, update on public.career_profiles to authenticated;

create table if not exists public.user_accounts (
    user_id uuid primary key references auth.users (id) on delete cascade,
    account_type text not null check (account_type in ('job_seeker', 'job_provider')),
    display_name text not null default '',
    recruiter_title text not null default '',
    created_at timestamptz not null default now()
);

alter table public.user_accounts
    add column if not exists recruiter_title text not null default '';

alter table public.user_accounts enable row level security;

drop policy if exists "Users can view their account type" on public.user_accounts;
create policy "Users can view their account type"
    on public.user_accounts for select to authenticated
    using ((select auth.uid()) = user_id);

revoke all on public.user_accounts from anon, authenticated;
grant select on public.user_accounts to authenticated;
grant update (recruiter_title) on public.user_accounts to authenticated;

drop policy if exists "Authenticated users can view employer recruiter profiles"
    on public.user_accounts;
create policy "Authenticated users can view employer recruiter profiles"
    on public.user_accounts for select to authenticated
    using (account_type = 'job_provider');

drop policy if exists "Employers can update their recruiter title"
    on public.user_accounts;
create policy "Employers can update their recruiter title"
    on public.user_accounts for update to authenticated
    using (
        (select auth.uid()) = user_id
        and account_type = 'job_provider'
    )
    with check (
        (select auth.uid()) = user_id
        and account_type = 'job_provider'
    );

create or replace function public.handle_new_career_account()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
    requested_type text;
begin
    requested_type := new.raw_user_meta_data ->> 'account_type';
    if requested_type is null or requested_type not in ('job_seeker', 'job_provider') then
        requested_type := 'job_seeker';
    end if;

    insert into public.user_accounts (user_id, account_type, display_name)
    values (
        new.id,
        requested_type,
        coalesce(new.raw_user_meta_data ->> 'full_name', '')
    )
    on conflict (user_id) do nothing;
    return new;
end;
$$;

drop trigger if exists create_career_account_after_signup on auth.users;
create trigger create_career_account_after_signup
    after insert on auth.users
    for each row execute function public.handle_new_career_account();

insert into public.user_accounts (user_id, account_type, display_name)
select
    id,
    case
        when raw_user_meta_data ->> 'account_type' = 'job_provider' then 'job_provider'
        else 'job_seeker'
    end,
    coalesce(raw_user_meta_data ->> 'full_name', '')
from auth.users
on conflict (user_id) do nothing;

create or replace function public.sync_career_account_display_name()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
    update public.user_accounts
    set display_name = coalesce(new.raw_user_meta_data ->> 'full_name', '')
    where user_id = new.id;
    return new;
end;
$$;

drop trigger if exists sync_career_account_display_name_after_auth_update on auth.users;
create trigger sync_career_account_display_name_after_auth_update
    after update of raw_user_meta_data on auth.users
    for each row
    when (new.raw_user_meta_data is distinct from old.raw_user_meta_data)
    execute function public.sync_career_account_display_name();

create or replace function public.is_job_provider()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.user_accounts
        where user_id = (select auth.uid())
          and account_type = 'job_provider'
    );
$$;

create or replace function public.is_job_seeker()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.user_accounts
        where user_id = (select auth.uid())
          and account_type = 'job_seeker'
    );
$$;

revoke all on function public.is_job_provider() from public, anon;
revoke all on function public.is_job_seeker() from public, anon;
grant execute on function public.is_job_provider() to authenticated;
grant execute on function public.is_job_seeker() to authenticated;

create table if not exists public.job_listings (
    id uuid primary key default gen_random_uuid(),
    provider_id uuid not null default auth.uid()
        references auth.users (id) on delete cascade,
    title text not null check (char_length(btrim(title)) between 2 and 120),
    company text not null check (char_length(btrim(company)) between 2 and 120),
    location text not null check (char_length(btrim(location)) between 2 and 120),
    workplace_type text not null check (workplace_type in ('On-site', 'Hybrid', 'Remote')),
    employment_type text not null check (employment_type in ('Full-time', 'Part-time', 'Contract', 'Internship')),
    description text not null check (char_length(btrim(description)) between 40 and 12000),
    requirements text not null default '' check (char_length(requirements) <= 8000),
    status text not null default 'draft' check (status in ('draft', 'published', 'closed')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create or replace function public.owns_job_listing(_listing_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.job_listings
        where id = _listing_id
          and provider_id = (select auth.uid())
    );
$$;

revoke all on function public.owns_job_listing(uuid) from public, anon;
grant execute on function public.owns_job_listing(uuid) to authenticated;

create index if not exists job_listings_status_created_idx
    on public.job_listings (status, created_at desc);
create index if not exists job_listings_provider_created_idx
    on public.job_listings (provider_id, created_at desc);

alter table public.job_listings enable row level security;

drop policy if exists "Users can browse published job listings" on public.job_listings;
create policy "Users can browse published job listings"
    on public.job_listings for select to authenticated
    using (status = 'published' or (select auth.uid()) = provider_id);

drop policy if exists "Providers can create their job listings" on public.job_listings;
create policy "Providers can create their job listings"
    on public.job_listings for insert to authenticated
    with check (
        (select auth.uid()) = provider_id
        and (select public.is_job_provider())
    );

drop policy if exists "Providers can update their job listings" on public.job_listings;
create policy "Providers can update their job listings"
    on public.job_listings for update to authenticated
    using (
        (select auth.uid()) = provider_id
        and (select public.is_job_provider())
    )
    with check (
        (select auth.uid()) = provider_id
        and (select public.is_job_provider())
    );

drop policy if exists "Providers can delete their job listings" on public.job_listings;
create policy "Providers can delete their job listings"
    on public.job_listings for delete to authenticated
    using (
        (select auth.uid()) = provider_id
        and (select public.is_job_provider())
    );

drop trigger if exists set_job_listing_updated_at on public.job_listings;
create trigger set_job_listing_updated_at
    before update on public.job_listings
    for each row execute function public.set_career_profile_updated_at();

revoke all on public.job_listings from anon, authenticated;
grant select, insert, update, delete on public.job_listings to authenticated;

create table if not exists public.job_applications (
    id uuid primary key default gen_random_uuid(),
    job_id uuid not null references public.job_listings (id) on delete cascade,
    applicant_id uuid not null default auth.uid()
        references auth.users (id) on delete cascade,
    job_title text not null check (char_length(btrim(job_title)) between 2 and 120),
    company text not null check (char_length(btrim(company)) between 2 and 120),
    applicant_name text not null check (char_length(btrim(applicant_name)) between 1 and 80),
    applicant_email text not null check (char_length(btrim(applicant_email)) between 3 and 254),
    resume_path text,
    cover_note text not null default '' check (char_length(cover_note) <= 4000),
    status text not null default 'Submitted',
    created_at timestamptz not null default now(),
    unique (job_id, applicant_id)
);

alter table public.job_applications add column if not exists resume_path text;
alter table public.job_applications drop constraint if exists job_applications_status_check;
update public.job_applications
set status = case status
    when 'In review' then 'CV review'
    when 'Declined' then 'Rejected'
    else status
end;
alter table public.job_applications
    add constraint job_applications_status_check
    check (status in ('Submitted', 'CV review', 'Shortlisted', 'Interview', 'Offer', 'Hired', 'Rejected', 'Withdrawn'));

create index if not exists job_applications_job_created_idx
    on public.job_applications (job_id, created_at desc);
create index if not exists job_applications_applicant_created_idx
    on public.job_applications (applicant_id, created_at desc);

alter table public.job_applications enable row level security;

create or replace function public.owns_job_application(_application_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.job_applications as application
        join public.job_listings as listing on listing.id = application.job_id
        where application.id = _application_id
          and listing.provider_id = (select auth.uid())
    );
$$;

create or replace function public.can_access_application_resume(_object_name text)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.job_applications as application
        where application.resume_path = _object_name
          and (storage.foldername(_object_name))[1] = application.applicant_id::text
          and (
              application.applicant_id = (select auth.uid())
              or (select public.owns_job_listing(application.job_id))
          )
    );
$$;

revoke all on function public.owns_job_application(uuid) from public, anon;
revoke all on function public.can_access_application_resume(text) from public, anon;
grant execute on function public.owns_job_application(uuid) to authenticated;
grant execute on function public.can_access_application_resume(text) to authenticated;

drop policy if exists "Applicants and listing providers can view applications" on public.job_applications;
create policy "Applicants and listing providers can view applications"
    on public.job_applications for select to authenticated
    using (
        (select auth.uid()) = applicant_id
        or (select public.owns_job_listing(job_id))
    );

drop policy if exists "Job seekers can apply to published listings" on public.job_applications;
create policy "Job seekers can apply to published listings"
    on public.job_applications for insert to authenticated
    with check (
        (select auth.uid()) = applicant_id
        and (select public.is_job_seeker())
        and exists (
            select 1
            from public.job_listings
            where job_listings.id = job_applications.job_id
              and job_listings.status = 'published'
              and job_listings.provider_id <> (select auth.uid())
        )
    );

drop policy if exists "Providers can update application status for their listings" on public.job_applications;
create policy "Providers can update application status for their listings"
    on public.job_applications for update to authenticated
    using (
        (select public.is_job_provider())
        and (select public.owns_job_listing(job_id))
    )
    with check (
        (select public.is_job_provider())
        and (select public.owns_job_listing(job_id))
    );

drop policy if exists "Applicants can withdraw their own applications" on public.job_applications;
create policy "Applicants can withdraw their own applications"
    on public.job_applications for update to authenticated
    using (
        (select auth.uid()) = applicant_id
        and status not in ('Hired', 'Rejected', 'Withdrawn')
    )
    with check (
        (select auth.uid()) = applicant_id
        and status = 'Withdrawn'
    );

revoke all on public.job_applications from anon, authenticated;
grant select, insert on public.job_applications to authenticated;
grant update (status) on public.job_applications to authenticated;

create table if not exists public.application_reviews (
    application_id uuid primary key
        references public.job_applications (id) on delete cascade,
    provider_id uuid not null default auth.uid()
        references auth.users (id) on delete cascade,
    reviewer_notes text not null default '' check (char_length(reviewer_notes) <= 4000),
    interview_at timestamptz,
    updated_at timestamptz not null default now()
);

alter table public.application_reviews enable row level security;

drop policy if exists "Providers can view reviews for their applications" on public.application_reviews;
create policy "Providers can view reviews for their applications"
    on public.application_reviews for select to authenticated
    using (
        provider_id = (select auth.uid())
        and (select public.owns_job_application(application_id))
    );

drop policy if exists "Providers can create reviews for their applications" on public.application_reviews;
create policy "Providers can create reviews for their applications"
    on public.application_reviews for insert to authenticated
    with check (
        provider_id = (select auth.uid())
        and (select public.owns_job_application(application_id))
    );

drop policy if exists "Providers can update reviews for their applications" on public.application_reviews;
create policy "Providers can update reviews for their applications"
    on public.application_reviews for update to authenticated
    using (
        provider_id = (select auth.uid())
        and (select public.owns_job_application(application_id))
    )
    with check (
        provider_id = (select auth.uid())
        and (select public.owns_job_application(application_id))
    );

drop trigger if exists set_application_review_updated_at on public.application_reviews;
create trigger set_application_review_updated_at
    before update on public.application_reviews
    for each row execute function public.set_career_profile_updated_at();

revoke all on public.application_reviews from anon, authenticated;
grant select, insert, update on public.application_reviews to authenticated;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('application-resumes', 'application-resumes', false, 5242880, array['application/pdf'])
on conflict (id) do update
set public = false,
    file_size_limit = 5242880,
    allowed_mime_types = array['application/pdf'];

drop policy if exists "Applicants can upload their own application resumes" on storage.objects;
create policy "Applicants can upload their own application resumes"
    on storage.objects for insert to authenticated
    with check (
        bucket_id = 'application-resumes'
        and (storage.foldername(name))[1] = (select auth.uid())::text
    );

drop policy if exists "Applicants and listing providers can view application resumes" on storage.objects;
create policy "Applicants and listing providers can view application resumes"
    on storage.objects for select to authenticated
    using (
        bucket_id = 'application-resumes'
        and (select public.can_access_application_resume(name))
    );

drop policy if exists "Applicants can remove their own application resumes" on storage.objects;
create policy "Applicants can remove their own application resumes"
    on storage.objects for delete to authenticated
    using (
        bucket_id = 'application-resumes'
        and (storage.foldername(name))[1] = (select auth.uid())::text
    );

create table if not exists public.application_material_drafts (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null default auth.uid()
        references auth.users (id) on delete cascade,
    job_id uuid not null references public.job_listings (id) on delete cascade,
    bullets jsonb not null default '[]'::jsonb,
    cover_letter text not null
        check (char_length(btrim(cover_letter)) between 40 and 12000),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (user_id, job_id)
);

alter table public.application_material_drafts
    add constraint application_material_bullet_count
    check (jsonb_array_length(bullets) <= 8);

create index if not exists application_material_drafts_user_updated_idx
    on public.application_material_drafts (user_id, updated_at desc);

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
    using ((select auth.uid()) = user_id and (select public.is_job_seeker()));

drop policy if exists "Job seekers can save their application materials"
    on public.application_material_drafts;
create policy "Job seekers can save their application materials"
    on public.application_material_drafts for insert to authenticated
    with check ((select auth.uid()) = user_id and (select public.is_job_seeker()));

drop policy if exists "Job seekers can update their application materials"
    on public.application_material_drafts;
create policy "Job seekers can update their application materials"
    on public.application_material_drafts for update to authenticated
    using ((select auth.uid()) = user_id and (select public.is_job_seeker()))
    with check ((select auth.uid()) = user_id and (select public.is_job_seeker()));

drop policy if exists "Job seekers can delete their application materials"
    on public.application_material_drafts;
create policy "Job seekers can delete their application materials"
    on public.application_material_drafts for delete to authenticated
    using ((select auth.uid()) = user_id and (select public.is_job_seeker()));

revoke all on public.application_material_drafts from anon, authenticated;
grant select, insert, update, delete on public.application_material_drafts to authenticated;
