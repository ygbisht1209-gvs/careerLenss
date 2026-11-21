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

drop policy if exists "Job seekers can add to their learning plan"
    on public.user_learning_plans;
create policy "Job seekers can add to their learning plan"
    on public.user_learning_plans for insert to authenticated
    with check (
        (select auth.uid()) = user_id
        and (select public.is_job_seeker())
        and (select public.active_learning_resource(resource_id))
    );

notify pgrst, 'reload schema';
