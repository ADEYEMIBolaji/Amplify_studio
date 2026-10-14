-- Platform constraint configuration — FR-026. Seeded defaults per the FRD
-- FR-026 table; explicitly NOT assumed correct — must be verified against
-- current platform documentation before launch (decision D-07).

create table public.platform_limits (
  id uuid primary key default gen_random_uuid(),
  platform text not null unique check (platform in ('instagram', 'tiktok', 'facebook', 'x')),
  caption_max_chars integer not null,
  caption_max_chars_premium integer,
  duration_max_seconds integer not null,
  duration_max_seconds_premium integer,
  hashtag_max_count integer,
  aspect_ratio text not null default '9:16',
  verified boolean not null default false,
  notes text,
  updated_at timestamptz not null default now()
);

insert into public.platform_limits
  (platform, caption_max_chars, caption_max_chars_premium, duration_max_seconds, duration_max_seconds_premium, hashtag_max_count, notes)
values
  ('instagram', 2200, null, 180, null, 30, 'Reels. Seeded from FRD FR-026 table; verify before launch.'),
  ('tiktok', 4000, null, 600, null, 30, 'Seeded from FRD FR-026 table; verify before launch.'),
  ('facebook', 2200, null, 90, null, 30, 'Reels limit changes frequently — FRD marks this "configurable; verify". Seeded as a placeholder.'),
  ('x', 280, 25000, 140, 10800, null, '2:20 (140s) non-Premium per FRD; Premium figures are placeholders pending verification. No public hashtag cap, enforced via caption length only.');

-- Account flags (e.g. X Premium) live on brand_profiles.platform_flags_json,
-- already present from the Week 1 migration — no schema change needed there.
