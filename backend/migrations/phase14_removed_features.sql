drop table if exists public.community_saved_posts;
drop table if exists public.community_reactions;
drop table if exists public.community_comments;
drop table if exists public.community_posts;

alter table public.career_profiles
    drop column if exists linkedin_target_role_draft,
    drop column if exists linkedin_headline_draft,
    drop column if exists linkedin_about_draft;

notify pgrst, 'reload schema';
