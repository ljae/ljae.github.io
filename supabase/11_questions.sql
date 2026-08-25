-- 질문 큐 (2026-08)
-- 실행: 10_reclassify.sql 다음
--
-- 글마다 읽는 검수는 관리자 시간이 병목이다. 가치는 판정 한 건이 아니라
-- 규칙 하나에 있다 — 그래서 방향을 뒤집는다. 파이프라인이 판단이 필요한
-- 지점을 찾아 **질문**을 만들고, 답 하나가 규칙·위키 힌트·판정 묶음이 된다.
--
-- kind:
--   confirm_post  경계에 걸린 중요 글 — 이 학원 글이 맞나
--   exclude_word  반려 이력에서 자란 규칙 후보 — 이 낱말이 있으면 제외할까
--   locality      같은 학군 형제 지점의 변별어 — 이 지점을 부르는 동네 말은
--   author        반복 작성자 — 홍보 계정으로 보고 전부 제외할까
--   compare       감성이 갈리는 고신뢰 글 2건 — 어느 쪽이 현재를 더 보여주나
create table if not exists review_questions (
  id           uuid primary key default gen_random_uuid(),
  fingerprint  text unique not null,   -- 같은 질문을 두 번 묻지 않는다
  kind         text not null,
  academy_key  text,
  academy_name text,
  question     text not null,
  payload      jsonb not null default '{}',  -- 근거 글들, 후보 낱말 등
  options      jsonb,                        -- 선택지. null 이면 자유 입력
  priority     real not null default 0,      -- 영향 추정치. 큰 것부터 보여준다
  status       text not null default 'pending',  -- pending|answered|dismissed|applied
  answer       jsonb,
  created_at   timestamptz not null default now(),
  answered_at  timestamptz
);

create index if not exists rq_pending
  on review_questions (priority desc) where status = 'pending';
create index if not exists rq_answered
  on review_questions (kind) where status = 'answered';

alter table review_questions enable row level security;

drop policy if exists rq_admin_all on review_questions;
create policy rq_admin_all on review_questions
  for all to authenticated
  using (is_admin()) with check (is_admin());
