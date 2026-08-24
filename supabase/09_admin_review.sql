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

-- ── 운영자 예약 등록 ─────────────────────────────────────────────
--
-- 첫 로그인 전에는 auth.users 에 행이 없어 admins 에 넣을 user_id 가 없다.
-- 이메일만 먼저 적어 두고, 가입하는 순간 트리거가 잇는다.
create table if not exists admin_invites (
  email    text primary key,
  added_at timestamptz not null default now()
);
alter table admin_invites enable row level security;
-- 정책 없음 = 아무도 못 읽는다. service_role 로만 관리한다.

create or replace function link_admin_invite()
returns trigger language plpgsql security definer as $$
begin
  if exists (select 1 from admin_invites where email = new.email) then
    insert into admins (user_id, email) values (new.id, new.email)
    on conflict (user_id) do nothing;
  end if;
  return new;
end;
$$;

drop trigger if exists on_auth_user_admin on auth.users;
create trigger on_auth_user_admin
  after insert on auth.users
  for each row execute function link_admin_invite();

-- ★ security definer 함수에는 search_path 를 반드시 못 박는다.
--   호출자(auth 서비스)의 search_path 에는 public 이 없다. 그대로 두면
--   함수가 'profiles' 를 못 찾고, 그 실패가 회원가입 500 으로 나온다.
--   실제로 이것 때문에 로그인 링크 발송이 통째로 막혔다.
alter function handle_new_user()   set search_path = public, auth;
alter function link_admin_invite() set search_path = public, auth;
alter function is_admin()          set search_path = public, auth;
