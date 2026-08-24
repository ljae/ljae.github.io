-- 참조 글 검수 (2026-08)
-- 실행: 08_leveltests.sql 다음
--
-- 랭킹이 커뮤니티 글에서 나오는 이상, 어떤 글을 근거로 삼았는지 사람이
-- 확인할 수 있어야 한다. 자동 필터는 '윤도영 학원'과 '뮤지컬 배우 윤도영'을
-- 구분하지 못한다 — 학원명이 본문에 있는지만 보기 때문이다.
--
-- ★ 이 표의 목적은 두 가지다.
--   1) 지금 당장 오염된 근거를 빼는 것
--   2) 판정이 쌓여 **크롤러 규칙이 되는 것** — 사람이 계속 누르게 두면
--      그건 자동화가 아니라 노동이다. 판정에서 규칙을 뽑아 다음 수집에
--      반영한다.

create table if not exists mention_reviews (
  url_hash     text primary key,            -- 언급 식별자 (파이프라인과 동일)
  academy_key  text not null,
  academy_name text,
  title        text,
  snippet      text,
  source       text,                        -- naver_blog | naver_cafe | …
  source_url   text,
  posted_at    date,
  verdict      text not null,               -- pending | confirmed | rejected
  reject_reason text,                       -- 아래 REJECT_REASONS 참고
  note         text,
  reviewed_at  timestamptz,
  created_at   timestamptz not null default now()
);

create index if not exists mention_reviews_pending
  on mention_reviews (academy_key) where verdict = 'pending';
create index if not exists mention_reviews_verdict
  on mention_reviews (verdict);

-- 판정에서 뽑아낸 규칙. 파이프라인이 매 수집마다 읽어 적용한다.
-- 사람이 만든 규칙이라 근거를 설명할 수 있고, 되돌릴 수도 있다.
create table if not exists crawl_rules (
  id          uuid primary key default gen_random_uuid(),
  scope       text not null default 'global',  -- global | academy
  academy_key text,                            -- scope=academy 일 때만
  kind        text not null,                   -- exclude_keyword | require_keyword | exclude_domain
  pattern     text not null,
  reason      text not null,                   -- 왜 넣었는지. 빈 규칙은 받지 않는다
  hits        int not null default 0,          -- 실제로 걸러낸 건수(효과 확인용)
  active      boolean not null default true,
  created_at  timestamptz not null default now(),
  unique (scope, academy_key, kind, pattern)
);

alter table mention_reviews enable row level security;
alter table crawl_rules enable row level security;

-- 운영자 표시. 이메일을 코드에 박지 않고 표로 둔다 — 바뀔 때 배포가
-- 필요 없고, 누가 운영자인지 한 곳에서 보인다.
create table if not exists admins (
  user_id  uuid primary key,
  email    text,
  added_at timestamptz not null default now()
);
alter table admins enable row level security;

create or replace function is_admin()
returns boolean language sql stable security definer as $$
  select exists (select 1 from admins where user_id = auth.uid())
$$;

-- 검수 표는 로그인한 운영자만 읽고 쓴다. anon 은 정책이 없어 기본 거부.
drop policy if exists mr_admin_all on mention_reviews;
create policy mr_admin_all on mention_reviews
  for all using (is_admin()) with check (is_admin());

drop policy if exists cr_admin_all on crawl_rules;
create policy cr_admin_all on crawl_rules
  for all using (is_admin()) with check (is_admin());

drop policy if exists admins_self on admins;
create policy admins_self on admins
  for select using (user_id = auth.uid());

-- 운영자 등록은 SQL 로만 한다(화면에서 스스로 올릴 수 없어야 한다):
--   insert into admins (user_id, email)
--   select id, email from auth.users where email = 'you@example.com';
