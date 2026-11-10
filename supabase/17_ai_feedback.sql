-- OpenEdu bounded local AI review. Source text never grants edit authority.
begin;
alter table public.board_posts add column if not exists agent_reply text check(char_length(agent_reply)<=600);
alter table public.board_comments add column if not exists agent_reply text check(char_length(agent_reply)<=600);
alter table public.user_reviews add column if not exists agent_reply text check(char_length(agent_reply)<=600);
alter table public.corrections add column if not exists agent_reply text check(char_length(agent_reply)<=600);
alter table public.corrections add column if not exists receipt_hash text;
create table if not exists public.ai_feedback_jobs (
 id uuid primary key default gen_random_uuid(),
 source_kind text not null check(source_kind in ('board_posts','board_comments','user_reviews','corrections','parent_feedback')),
 source_id uuid not null, body_hash text not null,
 state text not null default 'pending' check(state in ('pending','processing','replied','escalated','superseded','uncertain')),
 lease_token uuid, lease_until timestamptz, attempts int not null default 0, attempted_at timestamptz,
 review jsonb, reply text, slack_state text not null default 'none' check(slack_state in ('none','pending','sending','sent','unknown')),
 slack_ts text, created_at timestamptz not null default now(), finished_at timestamptz
);
create index if not exists ai_feedback_pending on public.ai_feedback_jobs(state,created_at);
alter table public.ai_feedback_jobs enable row level security;
revoke all on public.ai_feedback_jobs from public,anon,authenticated;
grant all on public.ai_feedback_jobs to service_role;
create table if not exists public.verified_academy_facts (
 academy_key text primary key, tel text not null check(tel ~ '^[0-9+ ()-]{8,30}$'),
 source_url text not null check(source_url='https://open.neis.go.kr/hub/acaInsTiInfo'),
 checked_at timestamptz not null, job_id uuid references public.ai_feedback_jobs(id),
 active boolean not null default true
);
alter table public.verified_academy_facts enable row level security;
revoke all on public.verified_academy_facts from public,anon,authenticated;
grant select(academy_key,tel,source_url,checked_at,active) on public.verified_academy_facts to anon,authenticated;
grant all on public.verified_academy_facts to service_role;
drop policy if exists verified_facts_public on public.verified_academy_facts;
create policy verified_facts_public on public.verified_academy_facts for select to anon,authenticated using(active and checked_at>now()-interval '30 days');

create or replace function public.ai_feedback_guard() returns trigger language plpgsql set search_path=public,pg_temp as $$
begin
 if coalesce(auth.role(),'')<>'service_role' and
  ((tg_op='INSERT' and new.agent_reply is not null) or (tg_op='UPDATE' and new.agent_reply is distinct from old.agent_reply)) then
  raise exception 'AGENT_FIELD_DENIED';
 end if;
 if tg_op='UPDATE' and new.body is distinct from old.body then new.agent_reply:=null;end if;
 return new;
end $$;
create or replace function public.ai_feedback_source_hash(v jsonb) returns text language sql immutable as $$
 select encode(sha256(convert_to(jsonb_build_array(coalesce(v->>'note',v->>'body'),v->'academy_key',v->'academy_id',v->'claim_type',v->'post_id',v->'page_type',v->'academy_keys')::text,'UTF8')),'hex')
$$;

create or replace function public.ai_feedback_enqueue() returns trigger language plpgsql security definer set search_path=public,pg_temp as $$
declare v jsonb := to_jsonb(new); previous jsonb; note text; field text;
begin
 field:=case when tg_table_name='parent_feedback' then 'note' else 'body' end;
 if tg_op='UPDATE' then
  previous:=to_jsonb(old);
  if ai_feedback_source_hash(v) is not distinct from ai_feedback_source_hash(previous) and v->>'status' is not distinct from previous->>'status' and v->>'deleted_at' is not distinct from previous->>'deleted_at' then return new; end if;
 end if;
 note:=v->>field;
 update ai_feedback_jobs set state='superseded',lease_token=null where source_kind=tg_table_name and source_id=new.id and state in ('pending','processing');
 if note is null or length(trim(note))=0 or v->>'deleted_at' is not null or v->>'status' in ('hidden','resolved','rejected','done','closed','declined','duplicate') or v->>'is_official'='true' then return new; end if;
 -- Agent status changes alone must not trigger another answer.
 if tg_op='UPDATE' and ai_feedback_source_hash(v) is not distinct from ai_feedback_source_hash(previous) then return new; end if;
 if tg_table_name='parent_feedback' and tg_op='UPDATE' then update parent_feedback set safe_resolution=null where id=new.id;end if;
 insert into ai_feedback_jobs(source_kind,source_id,body_hash) values(tg_table_name,new.id,ai_feedback_source_hash(v));
 return new;
end $$;
do $$ declare t text; begin
 foreach t in array array['board_posts','board_comments','user_reviews','corrections'] loop
  execute format('drop trigger if exists ai_feedback_fields on public.%I',t);
  execute format('create trigger ai_feedback_fields before insert or update on public.%I for each row execute function public.ai_feedback_guard()',t);
 end loop;
 foreach t in array array['board_posts','board_comments','user_reviews','corrections','parent_feedback'] loop
  execute format('drop trigger if exists ai_feedback_queue on public.%I',t);
  execute format('create trigger ai_feedback_queue after insert or update on public.%I for each row execute function public.ai_feedback_enqueue()',t);
 end loop;
end $$;

create or replace function public.ai_feedback_claim() returns jsonb language plpgsql security definer set search_path=public,pg_temp as $$
declare j ai_feedback_jobs; v jsonb; tok uuid;
begin
 if coalesce(auth.role(),'')<>'service_role' then raise exception 'SERVICE_REQUIRED'; end if;
 update ai_feedback_jobs set state='uncertain' where state='processing' and lease_until<now();
 -- Enforced shared budget, even if multiple pollers start. Never replay a model attempt.
 perform pg_advisory_xact_lock(hashtext('openedu.feedback.model-budget'));
 if (select count(*) from ai_feedback_jobs where attempts>0 and attempted_at>=date_trunc('day',now() at time zone 'Asia/Seoul') at time zone 'Asia/Seoul')>=12 then return null; end if;
 select * into j from ai_feedback_jobs where state='pending' and attempts=0 order by created_at,id for update skip locked limit 1;
 if not found then return null; end if;
 execute format('select to_jsonb(s) from public.%I s where id=$1',j.source_kind) into v using j.source_id;
 if v is null or v->>'deleted_at' is not null or v->>'status' in ('hidden','resolved','done','closed','rejected') then update ai_feedback_jobs set state='superseded' where id=j.id;return null;end if;
 tok:=gen_random_uuid();update ai_feedback_jobs set state='processing',lease_token=tok,lease_until=now()+interval '5 minutes',attempts=1,attempted_at=now() where id=j.id;
 return jsonb_build_object('id',j.id,'token',tok,'sourceKind',j.source_kind,'sourceId',j.source_id,'body',coalesce(v->>'note',v->>'body'),'academyKey',coalesce(v->>'academy_key',v->>'academy_id'),'claimType',v->>'claim_type');
end $$;

create or replace function public.ai_feedback_finish(p_id uuid,p_token uuid,p_reply text,p_review jsonb,p_escalate boolean,p_phone text default null)
returns text language plpgsql security definer set search_path=public,pg_temp as $$
declare j ai_feedback_jobs;v jsonb;note text;aid text; fld text;
begin
 if coalesce(auth.role(),'')<>'service_role' then raise exception 'SERVICE_REQUIRED';end if;
 select * into j from ai_feedback_jobs where id=p_id for update;
 if not found or j.state<>'processing' or j.lease_token is distinct from p_token or j.lease_until<now() then raise exception 'LEASE_LOST';end if;
 execute format('select to_jsonb(s) from public.%I s where id=$1 for update',j.source_kind) into v using j.source_id;
 note:=coalesce(v->>'note',v->>'body');
 if v is null or v->>'deleted_at' is not null or v->>'status' in ('hidden','resolved','done','closed','rejected') or ai_feedback_source_hash(v) is distinct from j.body_hash then
  update ai_feedback_jobs set state='superseded',lease_token=null where id=j.id;return 'superseded';end if;
 if p_reply is null or char_length(p_reply) not between 5 and 600 or p_review is null or jsonb_typeof(p_review)<>'object' then raise exception 'INVALID_REVIEW';end if;
 if p_phone is not null then
  aid:=v->>'academy_key';
  if j.source_kind<>'corrections' or p_escalate or aid is null or p_review->>'authority' is distinct from 'NEIS' or p_review->>'academyKey' is distinct from aid or p_review->>'verifiedPhone' is distinct from p_phone or p_review->>'sourceUrl' is distinct from 'https://open.neis.go.kr/hub/acaInsTiInfo' or
    p_review->>'checkedAt' is null or not ((p_review->>'checkedAt')::timestamptz between now()-interval '1 hour' and now()+interval '1 minute') then raise exception 'VERIFIED_SOURCE_REQUIRED';end if;
  insert into verified_academy_facts(academy_key,tel,source_url,checked_at,job_id) values(aid,p_phone,p_review->>'sourceUrl',(p_review->>'checkedAt')::timestamptz,j.id)
   on conflict(academy_key) do update set tel=excluded.tel,source_url=excluded.source_url,checked_at=excluded.checked_at,job_id=excluded.job_id,active=true;
 end if;
 fld:=case when j.source_kind='parent_feedback' then 'safe_resolution' else 'agent_reply' end;
 execute format('update public.%I set %I=$1 where id=$2',j.source_kind,fld) using p_reply,j.source_id;
 if j.source_kind='corrections' then update corrections set resolution=p_reply,status=case when p_phone is not null then 'resolved' else 'reviewing' end where id=j.source_id;end if;
 update ai_feedback_jobs set state=case when p_escalate then 'escalated' else 'replied' end,reply=p_reply,review=p_review,finished_at=now(),lease_token=null,slack_state=case when p_escalate then 'pending' else 'none' end where id=j.id;
 return case when p_escalate then 'escalated' else 'replied' end;
end $$;
revoke all on function public.ai_feedback_claim(),public.ai_feedback_finish(uuid,uuid,text,jsonb,boolean,text) from public,anon,authenticated;
grant execute on function public.ai_feedback_claim(),public.ai_feedback_finish(uuid,uuid,text,jsonb,boolean,text) to service_role;

-- Correction receipts expose only the reply, never the contact or request body.
create or replace function public.correction_submit_ai(p_id uuid,p_secret text,p_academy_key text,p_academy_name text,p_requester text,p_contact text,p_kind text,p_body text)
returns jsonb language plpgsql security definer set search_path=public,pg_temp as $$
declare r corrections;
begin
 if num_nonnulls(p_id,p_secret,p_academy_key,p_academy_name,p_requester,p_contact,p_kind,p_body)<>8 or p_secret !~ '^[A-Za-z0-9_-]{43}$' or char_length(p_body) not between 10 and 4000 or char_length(p_contact) not between 5 and 200 or char_length(p_requester) not between 1 and 200 or not (p_academy_key='unmatched' or p_academy_key ~ '^[0-9]{1,20}$') or p_kind not in ('fix','claim','remove','defamation','closed','other') or char_length(p_academy_name) not between 1 and 200 then raise exception 'INVALID_INPUT';end if;
 insert into corrections(id,academy_key,academy_name,requester,contact,claim_type,body,receipt_hash)
 values(p_id,p_academy_key,p_academy_name,p_requester,p_contact,p_kind,p_body,encode(sha256(convert_to(p_secret,'UTF8')),'hex')) on conflict(id) do nothing;
 select * into r from corrections where id=p_id;
 if r.receipt_hash is distinct from encode(sha256(convert_to(p_secret,'UTF8')),'hex') or r.body is distinct from p_body or r.academy_key is distinct from p_academy_key or r.claim_type is distinct from p_kind or r.contact is distinct from p_contact then raise exception 'REQUEST_CONFLICT';end if;
 return jsonb_build_object('id',r.id,'status',r.status,'reply',r.agent_reply);
end $$;
create or replace function public.correction_receipt_ai(p_id uuid,p_secret text)
returns jsonb language plpgsql security definer set search_path=public,pg_temp as $$
declare r corrections;
begin
 if p_secret is null or p_secret !~ '^[A-Za-z0-9_-]{43}$' then raise exception 'RECEIPT_NOT_FOUND';end if;
 select * into r from corrections where id=p_id and receipt_hash=encode(sha256(convert_to(p_secret,'UTF8')),'hex');
 if not found then raise exception 'RECEIPT_NOT_FOUND';end if;
 return jsonb_build_object('id',r.id,'status',r.status,'reply',r.agent_reply);
end $$;
revoke all on function public.correction_submit_ai(uuid,text,text,text,text,text,text,text),public.correction_receipt_ai(uuid,text) from public;
grant execute on function public.correction_submit_ai(uuid,text,text,text,text,text,text,text),public.correction_receipt_ai(uuid,text) to anon,authenticated,service_role;

do $$ declare t text; r record; v jsonb; note text;begin
 foreach t in array array['board_posts','board_comments','user_reviews','corrections','parent_feedback'] loop
  for r in execute format('select to_jsonb(s) as value from public.%I s',t) loop
   v:=r.value;note:=coalesce(v->>'note',v->>'body');
   if note is not null and length(trim(note))>0 and v->>'deleted_at' is null and coalesce(v->>'is_official','false')<>'true' and coalesce(v->>'status','') not in ('hidden','resolved','rejected','done','closed','declined','duplicate') and not exists(select 1 from ai_feedback_jobs where source_kind=t and source_id=(v->>'id')::uuid) then
    insert into ai_feedback_jobs(source_kind,source_id,body_hash) values(t,(v->>'id')::uuid,ai_feedback_source_hash(v));
   end if;
  end loop;
 end loop;
end $$;

commit;
