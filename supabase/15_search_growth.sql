-- Search growth v1. Reports retain their source grain. Raw queries are private.
-- Apply after 09_admin_review.sql (is_admin). This does not alter academy scores.
begin;

create table if not exists public.growth_reports (
  id text primary key,
  property text not null,
  source text not null check (source in ('gsc_csv','gsc_api_final')),
  search_type text not null,
  range_start date not null,
  range_end date not null check (range_end >= range_start),
  imported_at timestamptz not null default now(),
  snapshot jsonb not null,
  report jsonb not null,
  check (jsonb_typeof(snapshot) = 'object' and jsonb_typeof(report) = 'object')
);
create index if not exists growth_reports_period on public.growth_reports(property, range_end desc, range_start desc);

create table if not exists public.growth_tasks (
  id text primary key,
  property text not null,
  report_id text not null references public.growth_reports(id),
  rule_id text not null,
  subject_key text not null,
  title text not null,
  severity text not null check (severity in ('P0','P1','P2','P3')),
  impact_impressions bigint not null default 0 check (impact_impressions >= 0),
  evidence jsonb not null,
  state text not null default 'proposed' check (state in ('proposed','ready','in_progress','deployed','observing','verified','deferred','rejected','inconclusive','rolled_back')),
  version int not null default 1,
  note text not null default '',
  first_seen timestamptz not null default now(),
  last_seen timestamptz not null default now(),
  unique(property,rule_id,subject_key)
);
create index if not exists growth_tasks_status on public.growth_tasks(property,state,severity,id);

create table if not exists public.growth_changes (
  id uuid primary key default gen_random_uuid(),
  task_id text not null references public.growth_tasks(id),
  commit_sha text not null check (commit_sha ~ '^[0-9a-f]{7,40}$'),
  deploy_id text not null check (length(trim(deploy_id)) > 0),
  verification_url text not null check (verification_url like 'https://openedu4u.com/%'),
  verified_at timestamptz not null default now(),
  created_by uuid not null default auth.uid()
);

create table if not exists public.growth_experiments (
  id uuid primary key default gen_random_uuid(),
  property text not null,
  hypothesis text not null check (length(trim(hypothesis)) >= 10),
  treatment_urls jsonb not null check (jsonb_typeof(treatment_urls) = 'array' and jsonb_array_length(treatment_urls) > 0),
  control_urls jsonb not null default '[]'::jsonb check (jsonb_typeof(control_urls) = 'array'),
  primary_metric text not null check (primary_metric in ('clicks','impressions','ctr','meaningful_detail_session')),
  policy jsonb not null default '{"minImpressions":500,"minClicks":20,"observationDays":28}'::jsonb,
  analysis jsonb,
  verdict text not null default 'observing' check (verdict in ('observing','inconclusive','improved','regressed','unchanged','rolled_back')),
  created_by uuid not null default auth.uid(),
  created_at timestamptz not null default now()
);

alter table public.growth_reports enable row level security;
alter table public.growth_tasks enable row level security;
alter table public.growth_changes enable row level security;
alter table public.growth_experiments enable row level security;

-- No direct client writes. Mutations pass through bounded, audited functions below.
revoke all on public.growth_reports, public.growth_tasks, public.growth_changes, public.growth_experiments from anon, authenticated;
grant select on public.growth_reports, public.growth_tasks, public.growth_changes, public.growth_experiments to authenticated;
grant all on public.growth_reports, public.growth_tasks, public.growth_changes, public.growth_experiments to service_role;
drop policy if exists growth_reports_admin_read on public.growth_reports;
create policy growth_reports_admin_read on public.growth_reports for select to authenticated using (public.is_admin());
drop policy if exists growth_tasks_admin_read on public.growth_tasks;
create policy growth_tasks_admin_read on public.growth_tasks for select to authenticated using (public.is_admin());
drop policy if exists growth_changes_admin_read on public.growth_changes;
create policy growth_changes_admin_read on public.growth_changes for select to authenticated using (public.is_admin());
drop policy if exists growth_experiments_admin_read on public.growth_experiments;
create policy growth_experiments_admin_read on public.growth_experiments for select to authenticated using (public.is_admin());

create or replace function public.growth_publish(p_id text, p_snapshot jsonb, p_report jsonb)
returns jsonb language plpgsql security definer set search_path = public, pg_temp as $$
declare f jsonb; task_key text;
begin
  if coalesce(auth.role(),'') <> 'service_role' then raise exception 'ADMIN_REQUIRED'; end if;
  if p_snapshot->>'kind' is distinct from 'performance' or p_snapshot->>'property' is distinct from p_report->>'property'
     or p_snapshot->'totals' is distinct from p_report->'totals'
     or p_snapshot->'period' is distinct from p_report->'period' then raise exception 'INVALID_REPORT'; end if;
  if exists(select 1 from growth_reports where id=p_id) then
    return jsonb_build_object('id',p_id,'published',false); end if;
  insert into growth_reports(id,property,source,search_type,range_start,range_end,snapshot,report)
  values(p_id,p_snapshot->>'property',p_snapshot->>'source',p_snapshot->>'searchType',
    (p_snapshot->'period'->>'start')::date,(p_snapshot->'period'->>'end')::date,p_snapshot,p_report)
  on conflict(id) do nothing;
  for f in select value from jsonb_array_elements(coalesce(p_report->'findings','[]')) loop
    task_key := md5((p_snapshot->>'property') || '|' || (f->>'ruleId') || '|' || (f->>'subjectKey'));
    insert into growth_tasks(id,property,report_id,rule_id,subject_key,title,severity,impact_impressions,evidence)
    values(task_key,p_snapshot->>'property',p_id,f->>'ruleId',f->>'subjectKey',f->>'title',f->>'severity',
      coalesce((f->'evidence'->>'impressions')::bigint,0),f)
    on conflict(property,rule_id,subject_key) do update set
      report_id=excluded.report_id, title=excluded.title, severity=excluded.severity,
      evidence=excluded.evidence,impact_impressions=excluded.impact_impressions,last_seen=now(),version=growth_tasks.version+1;
  end loop;
  return jsonb_build_object('id',p_id,'published',true);
end $$;
revoke all on function public.growth_publish(text,jsonb,jsonb) from public,anon,authenticated;
grant execute on function public.growth_publish(text,jsonb,jsonb) to service_role;

create or replace function public.growth_overview(p_snapshot_id text)
returns jsonb language plpgsql security definer set search_path = public, pg_temp as $$
declare r growth_reports;
begin
  if not public.is_admin() then raise exception 'ADMIN_REQUIRED'; end if;
  select * into r from growth_reports where id=p_snapshot_id;
  if not found then raise exception 'SOURCE_UNAVAILABLE'; end if;
  return (r.report - 'pages' - 'queries') || jsonb_build_object(
    'pages',(select coalesce(jsonb_agg(value),'[]') from (select value from jsonb_array_elements(r.report->'pages') limit 20) t),
    'queries',(select coalesce(jsonb_agg(value),'[]') from (select value from jsonb_array_elements(r.report->'queries') limit 20) t),
    'pageCount',jsonb_array_length(r.report->'pages'));
end $$;

create or replace function public.growth_transition_task(p_task_id text, p_expected_version int, p_target_state text, p_note text default '')
returns jsonb language plpgsql security definer set search_path = public, pg_temp as $$
declare t growth_tasks; allowed text[];
begin
  if not public.is_admin() then raise exception 'ADMIN_REQUIRED'; end if;
  select * into t from growth_tasks where id=p_task_id for update;
  if not found then raise exception 'SOURCE_UNAVAILABLE'; end if;
  if t.version <> p_expected_version then raise exception 'VERSION_CONFLICT'; end if;
  allowed := case t.state
    when 'proposed' then array['ready','deferred','rejected']
    when 'ready' then array['in_progress','deferred','rejected']
    when 'in_progress' then array['deployed','deferred']
    when 'deployed' then array['observing','rolled_back']
    when 'observing' then array['verified','inconclusive','rolled_back']
    when 'deferred' then array['ready','rejected']
    when 'rolled_back' then array['ready']
    when 'inconclusive' then array['observing','ready']
    when 'verified' then array['ready'] else array[]::text[] end;
  if not (p_target_state = any(allowed)) then raise exception 'INVALID_TRANSITION'; end if;
  if p_target_state in ('deployed','verified') and not exists(select 1 from growth_changes where task_id=t.id) then
    raise exception 'DEPLOY_VERIFICATION_REQUIRED'; end if;
  update growth_tasks set state=p_target_state,note=left(p_note,4000),version=version+1 where id=t.id returning * into t;
  return to_jsonb(t);
end $$;

create or replace function public.growth_record_change(p_task_id text,p_commit_sha text,p_deploy_id text,p_verification_url text)
returns uuid language plpgsql security definer set search_path = public, pg_temp as $$
declare result uuid;
begin
  if not public.is_admin() then raise exception 'ADMIN_REQUIRED'; end if;
  insert into growth_changes(task_id,commit_sha,deploy_id,verification_url)
    values(p_task_id,p_commit_sha,p_deploy_id,p_verification_url) returning id into result;
  return result;
end $$;

create or replace function public.growth_create_experiment(p_property text,p_hypothesis text,p_treatment_urls jsonb,
    p_control_urls jsonb default '[]',p_primary_metric text default 'clicks')
returns uuid language plpgsql security definer set search_path = public, pg_temp as $$
declare result uuid; target text;
begin
  if not public.is_admin() then raise exception 'ADMIN_REQUIRED'; end if;
  if jsonb_array_length(p_treatment_urls)>100 or jsonb_array_length(p_control_urls)>100 then raise exception 'URL_LIMIT'; end if;
  for target in select jsonb_array_elements_text(p_treatment_urls || p_control_urls) loop
    if target not like 'https://openedu4u.com/%' then raise exception 'INVALID_URL'; end if;
  end loop;
  if exists(select 1 from jsonb_array_elements_text(p_treatment_urls) t(value)
    join jsonb_array_elements_text(p_control_urls) c(value) using(value)) then raise exception 'COHORT_OVERLAP'; end if;
  insert into growth_experiments(property,hypothesis,treatment_urls,control_urls,primary_metric)
  values(p_property,p_hypothesis,p_treatment_urls,p_control_urls,p_primary_metric) returning id into result;
  return result;
end $$;

revoke all on function public.growth_overview(text) from public,anon;
revoke all on function public.growth_transition_task(text,int,text,text) from public,anon;
revoke all on function public.growth_record_change(text,text,text,text) from public,anon;
revoke all on function public.growth_create_experiment(text,text,jsonb,jsonb,text) from public,anon;
grant execute on function public.growth_overview(text) to authenticated;
grant execute on function public.growth_transition_task(text,int,text,text) to authenticated;
grant execute on function public.growth_record_change(text,text,text,text) to authenticated;
grant execute on function public.growth_create_experiment(text,text,jsonb,jsonb,text) to authenticated;

commit;
