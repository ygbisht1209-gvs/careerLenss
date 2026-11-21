alter table public.user_accounts
    add column if not exists recruiter_title text not null default '';

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

notify pgrst, 'reload schema';
