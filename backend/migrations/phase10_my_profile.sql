alter table public.career_profiles
    add column if not exists current_position text not null default '',
    add column if not exists location text not null default '',
    add column if not exists phone text not null default '',
    add column if not exists education text not null default '',
    add column if not exists linkedin_target_role_draft text,
    add column if not exists linkedin_headline_draft text,
    add column if not exists linkedin_about_draft text;

notify pgrst, 'reload schema';

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
