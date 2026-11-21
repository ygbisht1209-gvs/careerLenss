create table if not exists public.learning_categories (
    slug text primary key check (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
    name text not null unique check (char_length(btrim(name)) between 1 and 80)
);

create table if not exists public.learning_resources (
    id uuid primary key default gen_random_uuid(),
    category_slug text not null references public.learning_categories (slug)
        on update cascade on delete restrict,
    title text not null check (char_length(btrim(title)) between 1 and 160),
    description text not null check (char_length(btrim(description)) between 1 and 2000),
    provider text not null check (char_length(btrim(provider)) between 1 and 120),
    resource_url text not null check (
        char_length(resource_url) <= 2048
        and resource_url ~ '^https?://[^[:space:]]+$'
    ),
    difficulty text not null check (
        difficulty in ('Beginner', 'Intermediate', 'Advanced', 'All levels')
    ),
    resource_type text not null check (
        resource_type in ('course', 'documentation', 'tutorial', 'practice', 'video', 'other')
    ),
    skill_tags text[] not null default '{}'
        check (cardinality(skill_tags) <= 30),
    objectives text[] not null default '{}'
        check (cardinality(objectives) <= 20),
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.user_learning_plans (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null default auth.uid()
        references auth.users (id) on delete cascade,
    resource_id uuid not null
        references public.learning_resources (id) on delete restrict,
    status text not null default 'not_started'
        check (status in ('not_started', 'in_progress', 'completed')),
    target_completion_date date,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint user_learning_plans_one_resource unique (user_id, resource_id)
);

create index if not exists learning_resources_active_category_idx
    on public.learning_resources (category_slug, difficulty)
    where is_active;
create index if not exists learning_resources_skill_tags_idx
    on public.learning_resources using gin (skill_tags);
create index if not exists user_learning_plans_user_updated_idx
    on public.user_learning_plans (user_id, updated_at desc);

create or replace function public.set_learning_plan_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists set_learning_resources_updated_at
    on public.learning_resources;
create trigger set_learning_resources_updated_at
    before update on public.learning_resources
    for each row execute function public.set_learning_plan_updated_at();

drop trigger if exists set_user_learning_plans_updated_at
    on public.user_learning_plans;
create trigger set_user_learning_plans_updated_at
    before update on public.user_learning_plans
    for each row execute function public.set_learning_plan_updated_at();

alter table public.learning_categories enable row level security;
alter table public.learning_resources enable row level security;
alter table public.user_learning_plans enable row level security;

create or replace function public.saved_learning_resource(_resource_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.user_learning_plans
        where resource_id = _resource_id
          and user_id = (select auth.uid())
    );
$$;

create or replace function public.active_learning_resource(_resource_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.learning_resources
        where id = _resource_id
          and is_active
    );
$$;

revoke all on function public.saved_learning_resource(uuid) from public, anon;
revoke all on function public.active_learning_resource(uuid) from public, anon;
grant execute on function public.saved_learning_resource(uuid) to authenticated;
grant execute on function public.active_learning_resource(uuid) to authenticated;

drop policy if exists "Job seekers can view learning categories"
    on public.learning_categories;
create policy "Job seekers can view learning categories"
    on public.learning_categories for select to authenticated
    using ((select public.is_job_seeker()));

drop policy if exists "Job seekers can view active or saved learning resources"
    on public.learning_resources;
create policy "Job seekers can view active or saved learning resources"
    on public.learning_resources for select to authenticated
    using (
        (select public.is_job_seeker())
        and (
            is_active
            or (select public.saved_learning_resource(learning_resources.id))
        )
    );

drop policy if exists "Job seekers can view their learning plan"
    on public.user_learning_plans;
create policy "Job seekers can view their learning plan"
    on public.user_learning_plans for select to authenticated
    using (
        (select auth.uid()) = user_id
        and (select public.is_job_seeker())
    );

drop policy if exists "Job seekers can add to their learning plan"
    on public.user_learning_plans;
create policy "Job seekers can add to their learning plan"
    on public.user_learning_plans for insert to authenticated
    with check (
        (select auth.uid()) = user_id
        and (select public.is_job_seeker())
        and (select public.active_learning_resource(resource_id))
    );

drop policy if exists "Job seekers can update their learning plan"
    on public.user_learning_plans;
create policy "Job seekers can update their learning plan"
    on public.user_learning_plans for update to authenticated
    using (
        (select auth.uid()) = user_id
        and (select public.is_job_seeker())
    )
    with check (
        (select auth.uid()) = user_id
        and (select public.is_job_seeker())
    );

drop policy if exists "Job seekers can remove from their learning plan"
    on public.user_learning_plans;
create policy "Job seekers can remove from their learning plan"
    on public.user_learning_plans for delete to authenticated
    using (
        (select auth.uid()) = user_id
        and (select public.is_job_seeker())
    );

revoke all on public.learning_categories from anon, authenticated;
revoke all on public.learning_resources from anon, authenticated;
revoke all on public.user_learning_plans from anon, authenticated;
grant select on public.learning_categories, public.learning_resources to authenticated;
grant select, delete on public.user_learning_plans to authenticated;
grant insert (resource_id, status, target_completion_date)
    on public.user_learning_plans to authenticated;
grant update (status, target_completion_date)
    on public.user_learning_plans to authenticated;
