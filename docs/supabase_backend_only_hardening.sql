-- Zecro / Supabase backend-only hardening
--
-- This is the idempotent hardening SQL applied to project
-- `mhbyguobbctbskahyfqf` on 2026-10-10. The live project has no migration
-- history, so this file is also the reproducible record of the change. RLS
-- policies change the public Data API contract. The FastAPI service connects
-- with the PostgreSQL/service role and therefore keeps working when these
-- tables are closed to anon/authenticated clients.
--
-- The frontend uses FastAPI and does not query Supabase Data API directly. If
-- that changes, replace the blanket REVOKE with project-scoped policies
-- instead of granting broad access.

begin;

alter table public.projects enable row level security;
alter table public.title_dna enable row level security;
alter table public.corpus_pages enable row level security;
alter table public.global_corpus_indexes enable row level security;
alter table public.global_corpus_pages enable row level security;
alter table public.style_archetypes enable row level security;
alter table public.generation_runs enable row level security;
alter table public.candidates enable row level security;
alter table public.preference_signals enable row level security;
alter table public.taste_models enable row level security;
alter table public.export_artifacts enable row level security;
alter table public.editorial_objects enable row level security;
alter table public.editorial_revisions enable row level security;
alter table public.editorial_events enable row level security;

revoke all on table
  public.projects,
  public.title_dna,
  public.corpus_pages,
  public.global_corpus_indexes,
  public.global_corpus_pages,
  public.style_archetypes,
  public.generation_runs,
  public.candidates,
  public.preference_signals,
  public.taste_models,
  public.export_artifacts,
  public.editorial_objects,
  public.editorial_revisions,
  public.editorial_events
from anon, authenticated;

-- Foreign-key indexes reported missing by the Supabase performance advisor.
create index if not exists candidates_run_id_idx on public.candidates(run_id);
create index if not exists candidates_project_id_idx on public.candidates(project_id);
create index if not exists corpus_pages_project_id_idx on public.corpus_pages(project_id);
create index if not exists editorial_revisions_object_id_idx on public.editorial_revisions(object_id);
create index if not exists export_artifacts_candidate_id_idx on public.export_artifacts(candidate_id);
create index if not exists export_artifacts_project_id_idx on public.export_artifacts(project_id);
create index if not exists generation_runs_project_id_idx on public.generation_runs(project_id);
create index if not exists preference_signals_project_id_idx on public.preference_signals(project_id);

commit;

-- Optional asset hardening after the API is switched from public object URLs
-- to signed URLs or a backend download proxy:
-- update storage.buckets set public = false where id = 'zecro-storage';
