-- Parent decision V2. Apply after 09 and 14. No academy scores are changed.
begin;
alter table public.academy_actions drop constraint if exists academy_actions_action_check;
alter table public.academy_actions add constraint academy_actions_action_check
  check (action in ('call','reserve','copy_tel','map','homepage'));

create table if not exists public.parent_feedback (
  id uuid primary key default gen_random_uuid(),
  request_id uuid not null unique,
  receipt_secret_hash text check (receipt_secret_hash ~ '^[a-f0-9]{64}$'),
  payload_hash text check (payload_hash ~ '^[a-f0-9]{64}$'),
  category text not null check (category in ('missing_info','discovery_compare','contact','feature_request','other')),
  note text check (char_length(note) <= 400),
  page_type text check (page_type in ('home','search','compare','academy','other')),
  academy_id text,
  status text not null default 'received' check(status in ('received','triaged','planned','in_progress','resolved','declined','duplicate')),
  version integer not null default 1,
  safe_resolution text check (char_length(safe_resolution)<=400),
  internal_resolution text check (char_length(internal_resolution)<=1000),
  duplicate_of uuid references public.parent_feedback(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz,
  check (duplicate_of is distinct from id)
);
create index if not exists parent_feedback_queue on public.parent_feedback(status,created_at,id);
create table if not exists public.parent_feedback_audit (
  id bigint generated always as identity primary key,
  feedback_id uuid references public.parent_feedback(id) on delete cascade,
  from_status text,
  to_status text not null,
  actor uuid,
  created_at timestamptz not null default now()
);
create table if not exists public.parent_improvements (
  id uuid primary key default gen_random_uuid(),
  title text not null check (char_length(trim(title)) between 1 and 100),
  summary text not null check (char_length(trim(summary)) between 1 and 600),
  commit_sha text not null check (commit_sha ~ '^[a-f0-9]{7,40}$'),
  deploy_ref text not null check (char_length(trim(deploy_ref)) between 1 and 200),
  verification_url text not null check (verification_url ~ '^https://openedu4u\.com/[^[:space:]]*$'),
  verified_at timestamptz not null check (verified_at <= now()),
  published_at timestamptz not null default now()
);
create table if not exists public.parent_improvement_feedback (
  improvement_id uuid references public.parent_improvements(id) on delete cascade,
  feedback_id uuid references public.parent_feedback(id) on delete cascade,
  primary key(improvement_id,feedback_id)
);
create table if not exists public.parent_voice_limits (
  bucket text not null,
  window_start timestamptz not null,
  count integer not null,
  primary key(bucket,window_start)
);

alter table public.parent_feedback enable row level security;
alter table public.parent_feedback_audit enable row level security;
alter table public.parent_improvements enable row level security;
alter table public.parent_improvement_feedback enable row level security;
alter table public.parent_voice_limits enable row level security;
revoke all on public.parent_feedback,public.parent_feedback_audit,public.parent_improvement_feedback,public.parent_voice_limits,public.parent_improvements from public,anon,authenticated;
revoke all on sequence public.parent_feedback_audit_id_seq from public,anon,authenticated;
grant all on public.parent_feedback,public.parent_feedback_audit,public.parent_improvements,public.parent_improvement_feedback,public.parent_voice_limits to service_role;
grant usage,select on sequence public.parent_feedback_audit_id_seq to service_role;
grant select on public.parent_improvements to anon,authenticated;
drop policy if exists parent_improvements_public on public.parent_improvements;
create policy parent_improvements_public on public.parent_improvements for select to anon,authenticated using(true);

create or replace function public.parent_voice_submit(p_request_id uuid,p_secret_hash text,p_payload_hash text,p_category text,p_note text,p_page_type text default null,p_academy_id text default null)
returns jsonb language plpgsql security definer set search_path=public,pg_temp as $$
declare r parent_feedback; fresh boolean;
begin
  if coalesce(auth.role(),'') <> 'service_role' then raise exception 'SERVICE_REQUIRED'; end if;
  if p_secret_hash is null or p_secret_hash !~ '^[a-f0-9]{64}$' or p_payload_hash is null or p_payload_hash !~ '^[a-f0-9]{64}$' then raise exception 'INVALID_INPUT'; end if;
  if p_academy_id is not null and not exists(select 1 from academies where aca_asnum=p_academy_id) then raise exception 'UNKNOWN_ACADEMY'; end if;
  insert into parent_feedback(request_id,receipt_secret_hash,payload_hash,category,note,page_type,academy_id)
  values(p_request_id,p_secret_hash,p_payload_hash,p_category,p_note,p_page_type,p_academy_id)
  on conflict(request_id) do nothing returning * into r;
  fresh := found;
  if not fresh then
    select * into r from parent_feedback where request_id=p_request_id for update;
    if r.deleted_at is not null or r.receipt_secret_hash is distinct from p_secret_hash or r.payload_hash is distinct from p_payload_hash then raise exception 'REQUEST_CONFLICT'; end if;
  end if;
  return jsonb_build_object('receiptId',r.id,'status','received','createdAt',r.created_at,'created',fresh);
end $$;

create or replace function public.parent_voice_receipt(p_id uuid,p_secret_hash text,p_delete boolean default false)
returns jsonb language plpgsql security definer set search_path=public,pg_temp as $$
declare r parent_feedback;
begin
  if coalesce(auth.role(),'') <> 'service_role' then raise exception 'SERVICE_REQUIRED'; end if;
  select * into r from parent_feedback where id=p_id and receipt_secret_hash=p_secret_hash and deleted_at is null for update;
  if not found then raise exception 'RECEIPT_NOT_FOUND'; end if;
  if p_delete then
    update parent_feedback set note=null,page_type=null,academy_id=null,receipt_secret_hash=null,payload_hash=null,internal_resolution=null,safe_resolution=null,deleted_at=now(),updated_at=now(),version=version+1 where id=r.id;
    return '{}'::jsonb;
  end if;
  return jsonb_build_object('status',r.status,'safeResolution',r.safe_resolution,'updatedAt',r.updated_at);
end $$;

create or replace function public.parent_voice_rate(p_key text,p_lane text,p_limit int,p_global_limit int)
returns boolean language plpgsql security definer set search_path=public,pg_temp as $$
declare w timestamptz := to_timestamp(floor(extract(epoch from now())/600)*600); n int; g int;
begin
  if coalesce(auth.role(),'') <> 'service_role' then raise exception 'SERVICE_REQUIRED'; end if;
  if p_key !~ '^[a-f0-9]{64}$' or p_lane not in ('submit','access') or p_limit not between 1 and 100 or p_global_limit not between 1 and 10000 then raise exception 'INVALID_LIMIT'; end if;
  insert into parent_voice_limits(bucket,window_start,count) values(p_lane||':global',w,1)
    on conflict(bucket,window_start) do update set count=least(parent_voice_limits.count+1,10001) returning count into g;
  insert into parent_voice_limits(bucket,window_start,count) values(p_lane||':'||p_key,w,1)
    on conflict(bucket,window_start) do update set count=least(parent_voice_limits.count+1,101) returning count into n;
  return n<=p_limit and g<=p_global_limit;
end $$;

create or replace function public.parent_voice_admin_queue(p_page int default 0)
returns setof public.parent_feedback language plpgsql security definer set search_path=public,pg_temp as $$
begin
  if not coalesce(public.is_admin(),false) then raise exception 'ADMIN_REQUIRED'; end if;
  if p_page not between 0 and 10000 then raise exception 'INVALID_PAGE'; end if;
  -- Receipt credentials and hashes never leave the server, including admin APIs.
  return query select id,request_id,null::text,null::text,category,note,page_type,academy_id,status,version,safe_resolution,internal_resolution,duplicate_of,created_at,updated_at,deleted_at
    from parent_feedback where deleted_at is null order by created_at,id limit 25 offset p_page*25;
end $$;

create or replace function public.parent_voice_transition(p_id uuid,p_version int,p_status text,p_safe_resolution text,p_internal_resolution text default '',p_duplicate_of uuid default null)
returns void language plpgsql security definer set search_path=public,pg_temp as $$
declare r parent_feedback;
begin
  if not coalesce(public.is_admin(),false) then raise exception 'ADMIN_REQUIRED'; end if;
  select * into r from parent_feedback where id=p_id and deleted_at is null for update;
  if not found then raise exception 'NOT_FOUND'; end if;
  if r.version<>p_version then raise exception 'VERSION_CONFLICT'; end if;
  if not ((r.status='received' and p_status='triaged') or
    (r.status='triaged' and p_status in ('planned','declined','duplicate')) or
    (r.status='planned' and p_status='in_progress') or
    (r.status='in_progress' and p_status='resolved') or
    (r.status in ('planned','in_progress','resolved','declined','duplicate') and p_status='triaged')) then raise exception 'INVALID_TRANSITION'; end if;
  if length(trim(coalesce(p_safe_resolution,'')))=0 then raise exception 'RESOLUTION_REQUIRED'; end if;
  if p_status='duplicate' and (p_duplicate_of is null or p_duplicate_of=p_id or not exists(select 1 from parent_feedback where id=p_duplicate_of and deleted_at is null)) then raise exception 'DUPLICATE_TARGET_REQUIRED'; end if;
  update parent_feedback set status=p_status,safe_resolution=trim(p_safe_resolution),internal_resolution=p_internal_resolution,
    duplicate_of=case when p_status='duplicate' then p_duplicate_of else null end,updated_at=now(),version=version+1 where id=r.id;
  insert into parent_feedback_audit(feedback_id,from_status,to_status,actor) values(r.id,r.status,p_status,auth.uid());
end $$;

create or replace function public.parent_voice_publish(p_feedback_id uuid,p_title text,p_summary text,p_commit text,p_deploy_ref text,p_url text,p_verified_at timestamptz default now())
returns uuid language plpgsql security definer set search_path=public,pg_temp as $$
declare fid uuid; result uuid;
begin
  if not coalesce(public.is_admin(),false) then raise exception 'ADMIN_REQUIRED'; end if;
  select id into fid from parent_feedback where id=p_feedback_id and status='resolved' and deleted_at is null for update;
  if not found then raise exception 'RESOLVED_REQUIRED'; end if;
  if exists(select 1 from parent_improvement_feedback where feedback_id=fid) then raise exception 'ALREADY_PUBLISHED'; end if;
  insert into parent_improvements(title,summary,commit_sha,deploy_ref,verification_url,verified_at)
  values(p_title,p_summary,p_commit,p_deploy_ref,p_url,p_verified_at) returning id into result;
  insert into parent_improvement_feedback values(result,fid);
  insert into parent_feedback_audit(feedback_id,from_status,to_status,actor) values(fid,'resolved','published',auth.uid());
  return result;
end $$;

create or replace function public.parent_voice_cleanup()
returns jsonb language plpgsql security definer set search_path=public,pg_temp as $$
declare purged int; redacted int;
begin
  if coalesce(auth.role(),'') <> 'service_role' then raise exception 'SERVICE_REQUIRED'; end if;
  delete from parent_voice_limits where window_start<now()-interval '24 hours';
  delete from parent_feedback where created_at<now()-interval '180 days'; get diagnostics purged=row_count;
  update parent_feedback set note=null,page_type=null,academy_id=null,internal_resolution=null
    where created_at<now()-interval '90 days' and (note is not null or page_type is not null or academy_id is not null or internal_resolution is not null);
  get diagnostics redacted=row_count;
  return jsonb_build_object('purged',purged,'redacted',redacted);
end $$;

revoke all on function public.parent_voice_submit(uuid,text,text,text,text,text,text),public.parent_voice_receipt(uuid,text,boolean),public.parent_voice_rate(text,text,int,int),public.parent_voice_cleanup() from public,anon,authenticated;
grant execute on function public.parent_voice_submit(uuid,text,text,text,text,text,text),public.parent_voice_receipt(uuid,text,boolean),public.parent_voice_rate(text,text,int,int),public.parent_voice_cleanup() to service_role;
revoke all on function public.parent_voice_admin_queue(int),public.parent_voice_transition(uuid,int,text,text,text,uuid),public.parent_voice_publish(uuid,text,text,text,text,text,timestamptz) from public,anon;
grant execute on function public.parent_voice_admin_queue(int),public.parent_voice_transition(uuid,int,text,text,text,uuid),public.parent_voice_publish(uuid,text,text,text,text,text,timestamptz) to authenticated;
commit;
