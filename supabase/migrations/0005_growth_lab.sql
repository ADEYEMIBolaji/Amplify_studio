-- Growth Lab — FR-028 (historical baseline import needs somewhere to put
-- "available tags" for a post that has no project to carry them).

alter table public.social_posts
  add column tags_json jsonb not null default '{}'::jsonb;
