-- 재원 인증 후기 (2026-08)
-- 실행: 06_corrections_tags.sql 다음

-- 후기의 신뢰도는 '누가 썼는가'에서 온다. 커뮤니티 스니펫과 로그인 후기를
-- 나눈 것과 같은 이유로, 로그인 후기 안에서도 **실제로 다닌 것이 확인된**
-- 글을 구분한다. 경쟁 서비스(런즈)의 재원 인증이 신뢰를 만드는 지점이다.
--
-- ★ 증빙 이미지는 저장하지 않는다.
--   영수증에는 학부모 이름·연락처·카드번호 일부가 찍힌다. 확인이 끝나면
--   남길 이유가 없는 정보다. 운영자가 보고 판정만 남긴다.
--   (스토리지 경로를 잠시 두되, 판정과 동시에 지우는 것을 원칙으로 한다)

alter table user_reviews
  add column if not exists verified boolean not null default false,
  add column if not exists verified_at timestamptz,
  add column if not exists verify_note text;

create index if not exists user_reviews_verified
  on user_reviews (academy_key) where verified;

-- 인증 요청 대기열. 후기와 1:1.
create table if not exists review_verifications (
  id          uuid primary key default gen_random_uuid(),
  review_id   uuid not null references user_reviews(id) on delete cascade,
  author_id   uuid not null,
  evidence_kind text not null default 'receipt',  -- receipt | enrollment | other
  note        text,
  status      text not null default 'pending',    -- pending | approved | rejected
  created_at  timestamptz not null default now(),
  reviewed_at timestamptz,
  unique (review_id)
);

alter table review_verifications enable row level security;

-- 본인 것만 넣고 본인 것만 본다. 판정은 service_role 만.
drop policy if exists rv_insert on review_verifications;
create policy rv_insert on review_verifications
  for insert with check (auth.uid() = author_id);

drop policy if exists rv_read_own on review_verifications;
create policy rv_read_own on review_verifications
  for select using (auth.uid() = author_id);

-- 인증 후기는 평판 가중치를 더 받는다. 파이프라인이 이 값을 읽는다.
comment on column user_reviews.verified is
  '재원 증빙이 확인된 후기. 평판 점수에서 더 높은 신뢰도를 받는다.';

-- 요약 뷰에 인증 건수를 더한다. 파이프라인이 인증분에 더 높은 신뢰도를 준다.
drop view if exists v_review_summary;
create view v_review_summary as
select
  academy_key,
  count(*)                                        as review_count,
  round(avg(rating)::numeric, 2)                  as avg_rating,
  count(*) filter (where verified)                as verified_count,
  round(avg(rating) filter (where verified)::numeric, 2) as verified_avg
from user_reviews
where status = 'published' and academy_key is not null
group by academy_key;
