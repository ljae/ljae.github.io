-- 전화·레벨테스트 예약 요청 · 잘못 붙은 근거 신고 · 행동 기록 (2026-09)
-- 실행: 13_claim_disputes.sql 다음
--
-- 학부모가 학원 정보에서 다음에 하는 일은 둘이다 — 전화를 걸거나,
-- 레벨테스트를 잡거나. 지금까지 화면은 전화번호를 글자로만 보여 줬다.
-- 이 셋은 전부 **접수만** 한다. 예약을 대신 확정하지 않는다 — 학원과
-- 제휴가 없고, 확정처럼 보이는 접수는 헛걸음의 책임을 우리에게 가져온다.
--
-- 세 표 모두 로그인 없이 넣는다(corrections 와 같은 이유 — 가입을 요구하면
-- 창구가 아니라 문턱이다). 읽기는 운영자뿐이다. 접수 목록이 공개되면
-- 그 자체가 학원 평가처럼 읽힌다.

-- ── 1) 레벨테스트 예약 요청 ────────────────────────────────────
--
-- 운영자가 학원에 대신 연락해 일정을 잇는다. status 가 곧 처리 대장이다.
create table if not exists test_reservations (
  id            uuid primary key default gen_random_uuid(),
  academy_key   text not null,
  academy_name  text not null,
  parent_name   text,
  contact       text not null,                 -- 회신 연락처. 공개되지 않는다
  child_band    text check (child_band in ('elem_low','elem_high','middle','high')),
  subject       text check (subject in ('math','english','korean','science','arts','etc')),
  preferred     text,                          -- 희망 일시(자유 서술)
  note          text,
  status        text not null default 'open'
    check (status in ('open','contacted','done','declined')),
  handler_note  text,
  created_at    timestamptz not null default now(),
  handled_at    timestamptz
);

create index if not exists test_reservations_open
  on test_reservations (created_at desc) where status = 'open';
create index if not exists test_reservations_academy
  on test_reservations (academy_key);

alter table test_reservations enable row level security;

drop policy if exists tr_insert on test_reservations;
create policy tr_insert on test_reservations
  for insert with check (
    char_length(academy_key) between 1 and 64
    and char_length(academy_name) between 1 and 120
    and char_length(contact) between 5 and 200
    and char_length(coalesce(parent_name, '')) <= 60
    and char_length(coalesce(preferred, '')) <= 300
    and char_length(coalesce(note, '')) <= 1000
    and status = 'open'
  );

drop policy if exists tr_admin on test_reservations;
create policy tr_admin on test_reservations
  for all to authenticated
  using (is_admin()) with check (is_admin());


-- ── 2) 잘못 붙은 근거 신고 ─────────────────────────────────────
--
-- 상세 화면의 근거 줄마다 '이 학원 글이 아니에요' 를 받는다. 접수는 반영이
-- 아니다 — 파이프라인이 신고된 글을 **질문 큐 맨 앞**에 올리고, 운영자의
-- 답이 판정·규칙이 된다(questions.py). 익명 신고가 곧 삭제가 되면 학원이
-- 불리한 글만 지우는 통로가 된다.
create table if not exists evidence_reports (
  id           uuid primary key default gen_random_uuid(),
  url_hash     text not null,                   -- 언급 식별자 (파이프라인과 동일)
  academy_key  text not null,
  source_url   text,
  title        text,
  reason       text not null
    check (reason in ('other_academy','not_review','ad','outdated','other')),
  note         text,
  status       text not null default 'open'
    check (status in ('open','queued','applied','declined')),
  created_at   timestamptz not null default now()
);

create index if not exists evidence_reports_open
  on evidence_reports (created_at desc) where status = 'open';
create index if not exists evidence_reports_key
  on evidence_reports (url_hash, academy_key);

alter table evidence_reports enable row level security;

drop policy if exists er_insert on evidence_reports;
create policy er_insert on evidence_reports
  for insert with check (
    char_length(url_hash) between 8 and 64
    and char_length(academy_key) between 1 and 64
    and char_length(coalesce(note, '')) <= 500
    and status = 'open'
  );

drop policy if exists er_admin on evidence_reports;
create policy er_admin on evidence_reports
  for all to authenticated
  using (is_admin()) with check (is_admin());


-- ── 3) 행동 기록 ───────────────────────────────────────────────
--
-- 전화 버튼·예약 버튼을 누른 사실만 남긴다. 누가 눌렀는지는 남기지 않는다.
-- 파이프라인이 30일 창으로 세어 **수집 우선순위**에만 쓴다(demand 와 같은
-- 층) — 점수에는 쓰지 않는다. 학부모가 전화를 거는 학원은 우리가 근거를
-- 더 찾아야 할 학원이지, 점수가 높은 학원이 아니다.
create table if not exists academy_actions (
  id           bigserial primary key,
  academy_key  text not null,
  action       text not null
    check (action in ('call','reserve','copy_tel','map')),
  created_at   timestamptz not null default now()
);

create index if not exists academy_actions_recent
  on academy_actions (created_at desc);

alter table academy_actions enable row level security;

drop policy if exists aa_insert on academy_actions;
create policy aa_insert on academy_actions
  for insert with check (char_length(academy_key) between 1 and 64);

drop policy if exists aa_admin on academy_actions;
create policy aa_admin on academy_actions
  for select to authenticated using (is_admin());

-- 운영자·파이프라인용 집계. 최근 30일.
create or replace view v_academy_action_counts
with (security_invoker = true) as
select academy_key, action, count(*) as n
from academy_actions
where created_at >= now() - interval '30 days'
group by academy_key, action;

revoke all on v_academy_action_counts from anon;
grant select on v_academy_action_counts to authenticated;
