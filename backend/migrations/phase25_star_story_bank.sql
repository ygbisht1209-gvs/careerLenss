create or replace function public.star_story_skill_tags_valid(tags text[])
returns boolean
language sql
immutable
as $$
    select tags is not null
        and cardinality(tags) <= 12
        and coalesce(
            (select bool_and(
                tag is not null
                and char_length(btrim(tag)) between 1 and 50
            )
             from unnest(tags) as tag),
            true
        );
$$;

create table if not exists public.star_stories (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
    title text not null check (char_length(btrim(title)) between 1 and 120),
    situation text not null check (char_length(btrim(situation)) between 1 and 1200),
    task text not null check (char_length(btrim(task)) between 1 and 1200),
    action text not null check (char_length(btrim(action)) between 1 and 1600),
    result text not null check (char_length(btrim(result)) between 1 and 1200),
    skill_tags text[] not null default '{}'::text[],
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint star_stories_total_text_limit check (
        char_length(title) + char_length(situation) + char_length(task)
        + char_length(action) + char_length(result) <= 1700
    ),
    constraint star_stories_skill_tags_valid check (
        public.star_story_skill_tags_valid(skill_tags)
    )
);

alter table public.star_stories
    drop constraint if exists star_stories_skill_tags_valid;
alter table public.star_stories
    add constraint star_stories_skill_tags_valid check (
        public.star_story_skill_tags_valid(skill_tags)
    );

alter table public.star_stories enable row level security;

drop policy if exists "Job seekers can read their own STAR stories"
    on public.star_stories;
create policy "Job seekers can read their own STAR stories"
    on public.star_stories for select to authenticated
    using (user_id = (select auth.uid()) and (select public.is_job_seeker()));

drop policy if exists "Job seekers can create their own STAR stories"
    on public.star_stories;
create policy "Job seekers can create their own STAR stories"
    on public.star_stories for insert to authenticated
    with check (user_id = (select auth.uid()) and (select public.is_job_seeker()));

drop policy if exists "Job seekers can update their own STAR stories"
    on public.star_stories;
create policy "Job seekers can update their own STAR stories"
    on public.star_stories for update to authenticated
    using (user_id = (select auth.uid()) and (select public.is_job_seeker()))
    with check (user_id = (select auth.uid()) and (select public.is_job_seeker()));

drop policy if exists "Job seekers can delete their own STAR stories"
    on public.star_stories;
create policy "Job seekers can delete their own STAR stories"
    on public.star_stories for delete to authenticated
    using (user_id = (select auth.uid()) and (select public.is_job_seeker()));

revoke all on public.star_stories from public, anon, authenticated;
grant select, insert, update, delete on public.star_stories to authenticated;

create or replace function public.set_star_story_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists set_star_story_updated_at on public.star_stories;
create trigger set_star_story_updated_at
    before update on public.star_stories
    for each row execute function public.set_star_story_updated_at();

notify pgrst, 'reload schema';
