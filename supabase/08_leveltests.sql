-- 레벨테스트 일정판 (2026-08)
-- 실행: 07_verified_reviews.sql 다음

-- 학부모가 학원 정보에서 가장 시간에 쫓기며 찾는 것이 레테 일정이다.
-- 디스쿨 같은 폐쇄 커뮤니티가 이 정보를 쥐고 있는 이유이기도 하다.
-- 검색되지 않는 정보를 구조화하는 것이 우리가 할 수 있는 일이다.
--
-- ★ 출처를 반드시 남긴다.
--   학원 공지(official)와 학부모 제보(tip)는 확실성이 다르다. 섞어 놓고
--   '일정'이라 부르면, 헛걸음의 책임이 우리에게 온다.

create table if not exists level_tests (
  id           uuid primary key default gen_random_uuid(),
  academy_key  text not null,                    -- NEIS 학원지정번호
  academy_name text not null,
  test_date    date,                             -- 미정이면 null
  date_note    text,                             -- '매월 첫 주 토요일' 처럼 고정 일정
  target_band  text check (target_band in ('elem_low','elem_high','middle','high')),
  subject      text check (subject in ('math','english','korean','science','etc')),
  apply_from   date,
  apply_until  date,
  detail       text,
  link         text,
  source_kind  text not null default 'tip',      -- official(학원 공지) | tip(제보)
  submitted_by uuid,                             -- 제보자 (있으면)
  status       text not null default 'pending',  -- pending | published | rejected
  created_at   timestamptz not null default now()
);

create index if not exists level_tests_upcoming
  on level_tests (test_date) where status = 'published';
create index if not exists level_tests_academy
  on level_tests (academy_key) where status = 'published';

alter table level_tests enable row level security;

-- 게시된 일정은 누구나 본다. 제보는 로그인 사용자만.
-- 게시 여부는 운영자가 정한다 — 검증 없는 일정이 그대로 뜨면
-- 학부모가 헛걸음한다.
drop policy if exists lt_read on level_tests;
create policy lt_read on level_tests
  for select using (status = 'published');

drop policy if exists lt_insert on level_tests;
create policy lt_insert on level_tests
  for insert with check (
    auth.uid() = submitted_by
    and char_length(academy_name) between 2 and 100
    and status = 'pending'
  );
