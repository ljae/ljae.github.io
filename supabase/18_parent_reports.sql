-- 학부모 제보 — 학원 한 곳에 대한 30초짜리 구조화 답. 로그인 불요.
--
-- 09_admin_review.sql(is_admin) 뒤에 적용한다. 멱등이다 — 두 번 돌려도 같다.
--
-- ★ 이 표는 **점수·순위에 쓰지 않는다.** 파이프라인은 학원별 '서로 다른
--   기기 수' 만 세어 수집 우선순위(demand·actions 와 같은 층)에 보탠다.
--   학부모가 제보한 학원은 근거를 더 찾아야 할 학원이지 점수가 높은 학원이
--   아니다(pipeline/edutree/parent_reports.py).
--
-- ★ 자유 서술 칸도 연락처 칸도 **없다.** 그것이 이 표의 개인정보 설계다.
--   적을 자리가 없으면 아이 이름도 전화번호도 들어올 수 없다. 학년도
--   정확한 학년이 아니라 학년대(grade_band)만 받는다. 열을 더할 때 물을 것:
--   그 열에 사람이 문장을 적을 수 있는가. 있으면 넣지 않는다.
--
-- ★ 익명 클라이언트는 표를 직접 읽지도 쓰지도 못한다. 들어오는 길은
--   submit_parent_report() 하나뿐이고, 그 함수는 ok/duplicate/limited
--   세 낱말 말고는 아무것도 돌려주지 않는다(남의 답·건수를 알 수 없다).
begin;

create table if not exists public.parent_reports (
  id          uuid primary key default gen_random_uuid(),
  -- 같은 요청이 두 번 와도(재시도·더블탭) 한 번만 처리한다.
  request_id  uuid not null unique,
  -- 학원 id = NEIS 학원지정번호. 외래키를 걸지 않는다 — academies 미러에는
  -- 채점 대상만 있고, 제보가 가장 값진 곳은 아직 등록부에만 있는 학원이다.
  academy_key text not null check (academy_key ~ '^[0-9A-Za-z_-]{1,64}$'),
  -- 학년이 아니라 학년대. 정확한 학년은 받지 않는다.
  grade_band  text not null
    check (grade_band in ('elem_low','elem_high','middle','high')),
  subject     text
    check (subject in ('math','english','korean','science','arts','etc')),
  relation    text not null
    check (relation in ('current','past','test_only','consulted')),
  level_test  text
    check (level_test in ('passed','failed','waitlisted','no_test','not_taken')),
  sessions_per_week integer check (sessions_per_week between 1 and 7),
  homework    text check (homework in ('light','medium','heavy')),
  -- 브라우저가 만든 무작위 토큰의 sha256. 사람이 아니라 기기를 가리키고,
  -- 저장소를 비우면 새 값이 된다. 원래 토큰은 서버에 오지 않는다.
  device_hash text not null check (device_hash ~ '^[a-f0-9]{64}$'),
  created_at  timestamptz not null default now(),
  -- 다시 보내면 고쳐 쓴다. 하루 제한이 이 값을 본다.
  updated_at  timestamptz not null default now(),
  -- received 접수 · kept 운영자가 보고 남김 · discarded 버림(집계에서 뺀다)
  status      text not null default 'received'
    check (status in ('received','kept','discarded')),
  -- 한 기기는 한 학원에 한 번만 센다. 다시 보내면 새 행이 아니라 고쳐 쓴다.
  unique (academy_key, device_hash)
);

create index if not exists parent_reports_device_recent
  on public.parent_reports (device_hash, updated_at desc);

-- 하루 전체 상한. 기기 토큰은 지우면 새로 생기므로 기기별 제한만으로는
-- 한 사람이 표를 채우는 것을 못 막는다. 이건 그때 걸리는 마지막 제동이다.
create table if not exists public.parent_report_limits (
  bucket       text not null,
  window_start timestamptz not null,
  count        integer not null,
  primary key (bucket, window_start)
);

alter table public.parent_reports enable row level security;
alter table public.parent_report_limits enable row level security;

revoke all on public.parent_reports, public.parent_report_limits
  from public, anon, authenticated;
grant all on public.parent_reports, public.parent_report_limits to service_role;

-- 운영자는 읽기만. RLS 가 is_admin() 이 아닌 로그인 사용자를 걸러 낸다
-- (정책이 없는 anon 은 권한도 없다). 상태를 바꾸는 것은 service_role 이다.
grant select on public.parent_reports to authenticated;
drop policy if exists parent_reports_admin_read on public.parent_reports;
create policy parent_reports_admin_read on public.parent_reports
  for select to authenticated using (coalesce(public.is_admin(), false));

-- 접수. 돌려주는 값은 셋뿐이다.
--   ok         새로 받았다
--   duplicate  같은 요청이 이미 처리됐거나, 이 기기가 이 학원에 낸 답을
--              새 답으로 고쳐 썼다(한 건으로 센다)
--   limited    이 기기가 하루에 다섯 학원을 넘겼거나 하루 전체 상한에 닿았다
-- 형식이 틀린 입력은 값이 아니라 예외(INVALID_INPUT)다.
create or replace function public.submit_parent_report(
  p_request_id uuid,
  p_academy_key text,
  p_grade_band text,
  p_relation text,
  p_device_hash text,
  p_subject text default null,
  p_level_test text default null,
  p_sessions_per_week integer default null,
  p_homework text default null
) returns text
language plpgsql security definer set search_path = public, pg_temp as $$
declare
  day    timestamptz := date_trunc('day', now());
  others integer;
  total  integer;
  fresh  boolean;
begin
  -- null 은 `not in` 을 조용히 통과하므로 필수 값은 따로 막는다.
  if p_request_id is null
     or p_academy_key is null or p_academy_key !~ '^[0-9A-Za-z_-]{1,64}$'
     or p_device_hash is null or p_device_hash !~ '^[a-f0-9]{64}$'
     or p_grade_band is null
     or p_grade_band not in ('elem_low','elem_high','middle','high')
     or p_relation is null
     or p_relation not in ('current','past','test_only','consulted')
     or (p_subject is not null
         and p_subject not in ('math','english','korean','science','arts','etc'))
     or (p_level_test is not null
         and p_level_test not in ('passed','failed','waitlisted','no_test','not_taken'))
     or (p_sessions_per_week is not null
         and p_sessions_per_week not between 1 and 7)
     or (p_homework is not null
         and p_homework not in ('light','medium','heavy'))
  then
    raise exception 'INVALID_INPUT';
  end if;

  -- 같은 요청의 재전송. 제한을 세기 전에 본다 — 응답을 못 받아 다시 보낸
  -- 것이 하루 몫을 깎으면 안 된다.
  if exists (select 1 from parent_reports where request_id = p_request_id) then
    return 'duplicate';
  end if;

  -- 같은 기기의 요청은 한 줄로 세운다. 안 세우면 동시에 온 여섯 건이
  -- 서로를 못 보고 전부 통과한다.
  perform pg_advisory_xact_lock(hashtextextended(p_device_hash, 0));

  select count(*) into others from parent_reports
   where device_hash = p_device_hash
     and academy_key <> p_academy_key
     and updated_at >= now() - interval '24 hours';
  if others >= 5 then
    return 'limited';
  end if;

  delete from parent_report_limits where window_start < day - interval '7 days';
  insert into parent_report_limits (bucket, window_start, count)
  values ('global', day, 1)
  on conflict (bucket, window_start)
    do update set count = least(parent_report_limits.count + 1, 100000)
  returning count into total;
  if total > 5000 then
    return 'limited';
  end if;

  -- 위의 잠금이 같은 기기를 한 줄로 세웠으므로 이 확인과 아래 쓰기 사이에
  -- 같은 (학원, 기기) 행이 끼어들지 못한다.
  fresh := not exists (select 1 from parent_reports
    where academy_key = p_academy_key and device_hash = p_device_hash);

  insert into parent_reports (request_id, academy_key, grade_band, subject,
    relation, level_test, sessions_per_week, homework, device_hash)
  values (p_request_id, p_academy_key, p_grade_band, p_subject,
    p_relation, p_level_test, p_sessions_per_week, p_homework, p_device_hash)
  on conflict (academy_key, device_hash) do update set
    request_id = excluded.request_id,
    grade_band = excluded.grade_band,
    subject = excluded.subject,
    relation = excluded.relation,
    level_test = excluded.level_test,
    sessions_per_week = excluded.sessions_per_week,
    homework = excluded.homework,
    updated_at = now(),
    -- 버린 답은 다시 보낸다고 되살아나지 않는다. 남긴 답은 내용이
    -- 바뀌었으니 다시 접수 상태로 돌린다.
    status = case when parent_reports.status = 'discarded'
                  then 'discarded' else 'received' end;

  return case when fresh then 'ok' else 'duplicate' end;
exception when unique_violation then
  -- 같은 request_id 가 동시에 두 번 들어온 경우.
  return 'duplicate';
end $$;

revoke all on function public.submit_parent_report(
  uuid, text, text, text, text, text, text, integer, text) from public;
grant execute on function public.submit_parent_report(
  uuid, text, text, text, text, text, text, integer, text)
  to anon, authenticated, service_role;

commit;
