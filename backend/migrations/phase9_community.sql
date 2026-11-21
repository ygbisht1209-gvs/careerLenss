create table if not exists public.community_posts (
    id uuid primary key default gen_random_uuid(),
    author_id uuid not null default auth.uid()
        references auth.users (id) on delete cascade,
    title text not null
        check (char_length(btrim(title)) between 5 and 160),
    body text not null
        check (char_length(btrim(body)) between 10 and 5000),
    category text not null
        check (category in (
            'Career advice',
            'Interview tips',
            'Job search',
            'Skill building',
            'Hiring',
            'Success stories'
        )),
    status text not null default 'open'
        check (status in ('open', 'closed')),
    is_pinned boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.community_comments (
    id uuid primary key default gen_random_uuid(),
    post_id uuid not null references public.community_posts (id) on delete cascade,
    author_id uuid not null default auth.uid()
        references auth.users (id) on delete cascade,
    body text not null
        check (char_length(btrim(body)) between 2 and 2000),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.community_reactions (
    post_id uuid not null references public.community_posts (id) on delete cascade,
    user_id uuid not null default auth.uid()
        references auth.users (id) on delete cascade,
    reaction text not null check (reaction in ('helpful', 'insightful', 'congrats')),
    created_at timestamptz not null default now(),
    primary key (post_id, user_id, reaction)
);

create table if not exists public.community_saved_posts (
    post_id uuid not null references public.community_posts (id) on delete cascade,
    user_id uuid not null default auth.uid()
        references auth.users (id) on delete cascade,
    created_at timestamptz not null default now(),
    primary key (post_id, user_id)
);

create index if not exists community_posts_feed_idx
    on public.community_posts (is_pinned desc, created_at desc);
create index if not exists community_posts_category_idx
    on public.community_posts (category, created_at desc);
create index if not exists community_comments_post_idx
    on public.community_comments (post_id, created_at);
create index if not exists community_reactions_post_idx
    on public.community_reactions (post_id);

create or replace function public.set_community_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists set_community_posts_updated_at on public.community_posts;
create trigger set_community_posts_updated_at
    before update on public.community_posts
    for each row execute function public.set_community_updated_at();

drop trigger if exists set_community_comments_updated_at on public.community_comments;
create trigger set_community_comments_updated_at
    before update on public.community_comments
    for each row execute function public.set_community_updated_at();

alter table public.community_posts enable row level security;
alter table public.community_comments enable row level security;
alter table public.community_reactions enable row level security;
alter table public.community_saved_posts enable row level security;

drop policy if exists "Authenticated users can read community author names"
    on public.user_accounts;
create policy "Authenticated users can read community author names"
    on public.user_accounts for select to authenticated
    using (true);

drop policy if exists "Authenticated users can read community posts"
    on public.community_posts;
create policy "Authenticated users can read community posts"
    on public.community_posts for select to authenticated
    using (true);

drop policy if exists "Authenticated users can create community posts"
    on public.community_posts;
create policy "Authenticated users can create community posts"
    on public.community_posts for insert to authenticated
    with check ((select auth.uid()) = author_id);

drop policy if exists "Authors can update their community posts"
    on public.community_posts;
create policy "Authors can update their community posts"
    on public.community_posts for update to authenticated
    using ((select auth.uid()) = author_id)
    with check ((select auth.uid()) = author_id);

drop policy if exists "Authors can delete their community posts"
    on public.community_posts;
create policy "Authors can delete their community posts"
    on public.community_posts for delete to authenticated
    using ((select auth.uid()) = author_id);

drop policy if exists "Authenticated users can read community comments"
    on public.community_comments;
create policy "Authenticated users can read community comments"
    on public.community_comments for select to authenticated
    using (true);

drop policy if exists "Authenticated users can create community comments"
    on public.community_comments;
create policy "Authenticated users can create community comments"
    on public.community_comments for insert to authenticated
    with check (
        (select auth.uid()) = author_id
        and exists (
            select 1 from public.community_posts
            where id = post_id and status = 'open'
        )
    );

drop policy if exists "Authors can update their community comments"
    on public.community_comments;
create policy "Authors can update their community comments"
    on public.community_comments for update to authenticated
    using ((select auth.uid()) = author_id)
    with check ((select auth.uid()) = author_id);

drop policy if exists "Authors can delete their community comments"
    on public.community_comments;
create policy "Authors can delete their community comments"
    on public.community_comments for delete to authenticated
    using ((select auth.uid()) = author_id);

drop policy if exists "Authenticated users can read community reactions"
    on public.community_reactions;
create policy "Authenticated users can read community reactions"
    on public.community_reactions for select to authenticated
    using (true);

drop policy if exists "Users can manage their community reactions"
    on public.community_reactions;
create policy "Users can manage their community reactions"
    on public.community_reactions for all to authenticated
    using ((select auth.uid()) = user_id)
    with check ((select auth.uid()) = user_id);

drop policy if exists "Users can read their saved community posts"
    on public.community_saved_posts;
create policy "Users can read their saved community posts"
    on public.community_saved_posts for select to authenticated
    using ((select auth.uid()) = user_id);

drop policy if exists "Users can manage their saved community posts"
    on public.community_saved_posts;
create policy "Users can manage their saved community posts"
    on public.community_saved_posts for all to authenticated
    using ((select auth.uid()) = user_id)
    with check ((select auth.uid()) = user_id);

revoke all on public.community_posts from anon, authenticated;
revoke all on public.community_comments from anon, authenticated;
revoke all on public.community_reactions from anon, authenticated;
revoke all on public.community_saved_posts from anon, authenticated;

grant select, insert, update, delete on public.community_posts to authenticated;
grant select, insert, update, delete on public.community_comments to authenticated;
grant select, insert, delete on public.community_reactions to authenticated;
grant select, insert, delete on public.community_saved_posts to authenticated;
