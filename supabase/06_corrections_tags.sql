-- 정보 정정 창구 정비 + 후기 구조화 태그 (2026-08)
-- 실행: 05_grade_bands.sql 다음

-- ── 1) 학원 관계자 정정 요청 ─────────────────────────────────────
--
-- corrections 테이블은 01_schema.sql 이 이미 만들었다(academy_id uuid 기준).
-- 후기와 같은 이유로 앱은 NEIS 지정번호(문자열)로 학원을 가리키므로
-- academy_key 를 추가하고, 접수에 필요한 열을 채운다.
--
-- 요청은 공개 화면에 노출하지 않고 운영자가 검토한 뒤 데이터에 반영한다.
-- 자동 반영하지 않는다 — 창구가 곧 편집권이 되면 그건 또 다른 왜곡이다.

alter table corrections
  add column if not exists academy_key  text,
  add column if not exists academy_name text,
  add column if not exists requester    text;

alter table corrections alter column academy_id drop not null;

create index if not exists corrections_open
  on corrections (academy_key) where status = 'open';

alter table corrections enable row level security;

-- 접수는 누구나(로그인 불요 — 관계자에게 가입을 강요하지 않는다).
-- 조회는 아무에게도 열지 않는다. service_role 만 본다.
drop policy if exists corrections_insert on corrections;
create policy corrections_insert on corrections
  for insert with check (
    char_length(body) between 10 and 4000
    and char_length(coalesce(contact, '')) between 5 and 200
    and academy_key is not null
  );

-- ── 2) 후기 구조화 태그 ──────────────────────────────────────────
--
-- 자유 서술만으로는 후기가 쌓여도 걸러 볼 수 없다. 학년·과목·키워드를
-- 구조화하면 '초2 학부모의 수학 후기'만 모아 보는 일이 가능해진다.

alter table user_reviews
  add column if not exists grade_band text
    check (grade_band in ('elem_low','elem_high','middle','high')),
  add column if not exists subject text
    check (subject in ('math','english','korean','science','etc')),
  add column if not exists tags text[] not null default '{}';

-- 태그는 정해진 어휘만 받는다. 자유 태그는 곧 스팸 통로가 된다.
create or replace function valid_review_tags(t text[])
returns boolean language sql immutable as $$
  select t <@ array[
    '숙제량_많음','숙제량_적음','관리_꼼꼼','피드백_빠름','레테_어려움',
    '분위기_엄격','분위기_자유로움','시설_좋음','셔틀_운행','상담_친절',
    '교재_자체','선행_위주','내신_위주','소수정예','대형강의'
  ]::text[]
$$;

alter table user_reviews
  drop constraint if exists user_reviews_tags_valid;
alter table user_reviews
  add constraint user_reviews_tags_valid
  check (array_length(tags, 1) is null or
         (array_length(tags, 1) <= 5 and valid_review_tags(tags)));
