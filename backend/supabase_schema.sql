create table if not exists public.applications (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
    title text not null check (char_length(btrim(title)) between 1 and 100),
    company text not null check (char_length(btrim(company)) between 1 and 100),
    applied_on date not null,
    status text not null default 'Applied'
        check (status in ('Applied', 'Under Review', 'Interview', 'Offer', 'Rejected')),
    created_at timestamptz not null default now()
);

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
    target_role text not null default '',
    headline text not null default '',
    about text not null default '',
    skills text[] not null default '{}',
    updated_at timestamptz not null default now()
);

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
