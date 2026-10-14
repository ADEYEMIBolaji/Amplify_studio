-- FR-023(c): Owner-pasted verse text, stored alongside the reference and
-- labelled as Owner-supplied when expanded (never treated as the local
-- public-domain WEB source).

alter table public.scripture_references
  add column pasted_text text;
