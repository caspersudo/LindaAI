-- ============================================================
-- LindaAI — Day 2 auth trigger
-- When a new person signs up (a row appears in auth.users), this
-- automatically creates their business (organizations) and their
-- profile (users) so they never see an empty, broken account.
-- Run this in Supabase AFTER 01_schema.sql.
-- ============================================================

create or replace function handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
declare
    new_org_id uuid;
begin
    -- 1. create a business for this person.
    --    default name = the part of their email before the "@".
    insert into organizations (name)
    values (coalesce(nullif(split_part(new.email, '@', 1), ''), 'My business'))
    returning id into new_org_id;

    -- 2. create their profile row, linked to that business.
    insert into users (id, org_id, email, full_name)
    values (
        new.id,
        new_org_id,
        new.email,
        new.raw_user_meta_data ->> 'full_name'
    );

    return new;
end;
$$;

-- fire the function every time a new auth user is created
drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function handle_new_user();
