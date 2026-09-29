-- ============================================================================
-- Berwaz — Supabase schema
-- Paste this whole file into: Supabase Dashboard → SQL Editor → New query → Run
-- Safe to re-run (idempotent).
-- ============================================================================

-- ─── Profiles ───────────────────────────────────────────────────────────────
-- One row per user, created automatically on signup (trigger below).
create table if not exists public.profiles (
  id          uuid primary key references auth.users(id) on delete cascade,
  handle      text unique,                              -- public URL slug, e.g. "ali"
  display_name text,
  role        text check (role in ('filmmaker','student','researcher','agency','other')),
  bio         text,
  website     text,
  avatar_url  text,
  is_public   boolean not null default true,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

-- Handles: lowercase letters, digits, hyphens, 3–24 chars
alter table public.profiles drop constraint if exists profiles_handle_format;
alter table public.profiles add constraint profiles_handle_format
  check (handle is null or handle ~ '^[a-z0-9][a-z0-9-]{1,22}[a-z0-9]$');

-- ─── Boards ─────────────────────────────────────────────────────────────────
-- frames is an ordered array of frame ids (strings) — matches the site's data model.
create table if not exists public.boards (
  id          uuid primary key default gen_random_uuid(),
  owner       uuid not null references public.profiles(id) on delete cascade,
  name        text not null check (char_length(name) between 1 and 60),
  frames      jsonb not null default '[]'::jsonb,
  is_public   boolean not null default false,
  local_id    text,                                     -- id the board had in localStorage (for merge)
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index if not exists boards_owner_idx on public.boards(owner);
create index if not exists boards_public_idx on public.boards(is_public) where is_public;
create unique index if not exists boards_owner_local_idx on public.boards(owner, local_id) where local_id is not null;

-- ─── Analytics events ───────────────────────────────────────────────────────
-- Anonymous inserts allowed; nobody can read them from the client.
create table if not exists public.events (
  id          bigserial primary key,
  name        text not null,
  props       jsonb not null default '{}'::jsonb,
  user_id     uuid references auth.users(id) on delete set null,
  session_id  text,
  created_at  timestamptz not null default now()
);
create index if not exists events_name_time_idx on public.events(name, created_at desc);

-- ─── updated_at maintenance ─────────────────────────────────────────────────
create or replace function public.touch_updated_at() returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end $$;
drop trigger if exists profiles_touch on public.profiles;
create trigger profiles_touch before update on public.profiles for each row execute function public.touch_updated_at();
drop trigger if exists boards_touch on public.boards;
create trigger boards_touch before update on public.boards for each row execute function public.touch_updated_at();

-- ─── Auto-create a profile on signup ────────────────────────────────────────
create or replace function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = public as $$
declare base text; candidate text; n int := 0;
begin
  -- derive a handle from the email local part
  base := lower(regexp_replace(split_part(new.email, '@', 1), '[^a-z0-9]+', '-', 'g'));
  base := trim(both '-' from base);
  if base is null or char_length(base) < 3 then base := 'user'; end if;
  base := substr(base, 1, 20);
  candidate := base;
  while exists (select 1 from public.profiles where handle = candidate) loop
    n := n + 1; candidate := base || '-' || n;
  end loop;
  insert into public.profiles (id, handle, display_name)
  values (new.id, candidate, split_part(new.email, '@', 1))
  on conflict (id) do nothing;
  return new;
end $$;
drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created after insert on auth.users for each row execute function public.handle_new_user();

-- ─── Row-level security ─────────────────────────────────────────────────────
alter table public.profiles enable row level security;
alter table public.boards   enable row level security;
alter table public.events   enable row level security;

-- profiles: anyone can read public profiles; owners read/update their own
drop policy if exists "profiles read public"  on public.profiles;
drop policy if exists "profiles read own"     on public.profiles;
drop policy if exists "profiles update own"   on public.profiles;
create policy "profiles read public" on public.profiles for select using (is_public);
create policy "profiles read own"    on public.profiles for select using (auth.uid() = id);
create policy "profiles update own"  on public.profiles for update using (auth.uid() = id) with check (auth.uid() = id);

-- boards: owners full control; anyone can read public boards
drop policy if exists "boards read public" on public.boards;
drop policy if exists "boards owner all"   on public.boards;
create policy "boards read public" on public.boards for select using (is_public);
create policy "boards owner all"   on public.boards for all using (auth.uid() = owner) with check (auth.uid() = owner);

-- events: anyone (even anonymous) may insert; no client reads
drop policy if exists "events insert any" on public.events;
create policy "events insert any" on public.events for insert with check (true);

-- ─── Public read helpers (bypass RLS safely for aggregate numbers) ──────────
-- How many boards a frame has been saved to (public + private, counts only).
create or replace function public.frame_save_counts(frame_ids text[])
returns table(frame_id text, saves bigint) language sql security definer stable set search_path = public as $$
  select f.value as frame_id, count(*) as saves
  from public.boards b, jsonb_array_elements_text(b.frames) as f(value)
  where f.value = any(frame_ids)
  group by f.value
$$;
grant execute on function public.frame_save_counts(text[]) to anon, authenticated;

-- Most-saved frames overall (for a future "popular" view / CDF reporting)
create or replace function public.top_saved_frames(lim int default 50)
returns table(frame_id text, saves bigint) language sql security definer stable set search_path = public as $$
  select f.value, count(*) from public.boards b, jsonb_array_elements_text(b.frames) as f(value)
  group by f.value order by count(*) desc limit lim
$$;
grant execute on function public.top_saved_frames(int) to anon, authenticated;

-- Done. Next: Authentication → Providers → Email: enable "Email", disable "Confirm email"
-- if you want magic links to sign in directly; set Site URL and Redirect URLs (see SETUP.md).
