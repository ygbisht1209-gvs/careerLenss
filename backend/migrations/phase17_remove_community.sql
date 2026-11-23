-- Review-only migration: remove the retired Community feature.
-- Run manually in Supabase after review. This file is safe to rerun.

drop policy if exists "Authenticated users can read community author names"
    on public.user_accounts;

-- Dropping the tables with CASCADE removes their RLS policies and triggers.
-- CASCADE plus IF EXISTS keeps this safe after an earlier partial removal.
drop table if exists public.community_saved_posts cascade;
drop table if exists public.community_reactions cascade;
drop table if exists public.community_comments cascade;
drop table if exists public.community_posts cascade;

drop function if exists public.set_community_updated_at();

notify pgrst, 'reload schema';
