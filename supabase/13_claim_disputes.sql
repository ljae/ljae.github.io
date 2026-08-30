-- 주장(claim) 이의 접수와 취소 판정 (2026-08)
-- 실행: 12_grade_bands_finish.sql 다음
--
-- posts.py 의 무효화는 글 **전체**를 끈다. 여기는 한 층 아래다 — 그 글의
-- 평판 근거는 살리고 진입난이도 주장만 끈다. 주장이 행이 되면서 가능해졌다.
--
-- ★ claims 표는 만들지 않는다.
--   주장은 매 실행 원자료에서 다시 지어진다. 미러링해 봐야 다음 실행이
--   덮어쓸 값이고, 표가 하나 늘면 그만큼 어긋날 자리가 생긴다. 영속해야
--   하는 것은 **사람의 판정** 뿐이다. posts.py 가 글 페이지에 판정만
--   적어 두고 본문을 저장하지 않는 것과 같은 이유다.
--
-- ★ claim_id 에 외래키를 걸지 않는다.
--   가리키는 표가 없기도 하지만, 걸 수 있어도 걸면 안 된다. 수집 대상은
--   회차마다 순환하므로 이번 회차에 안 뽑힌 학원의 주장이 사라졌다가
--   다음 회차에 돌아온다. cascade 로 판정이 함께 지워지면 사람이 같은
--   글을 두 번 심사하게 된다. academies 를 prune 하지 않는 것과 같은
--   판단이다 — **지우기를 넣기 전에 물을 것: 여기에 사람이 쓴 것이
--   매달려 있는가.**

-- ── 1) 이의 접수 ─────────────────────────────────────────────────
--
-- 앱에서 인용문 옆의 '이의' 를 누르면 여기 쌓인다. 접수는 반영이 아니다.
create table if not exists claim_disputes (
  id           uuid primary key default gen_random_uuid(),
  claim_id     text not null,               -- claims.claim_id (결정적 해시)
  academy_key  text not null,
  claim_kind   text not null,               -- sel.test_failed | fact.homework …
  quote        text,                        -- 접수 시점의 인용문. 판정 화면용
  reason       text not null
    check (reason in ('not_true','outdated','other_academy','ad','other')),
  note         text,
  status       text not null default 'open' -- open | accepted | declined
    check (status in ('open','accepted','declined')),
  created_at   timestamptz not null default now(),
  reviewed_at  timestamptz
);

create index if not exists claim_disputes_open
  on claim_disputes (created_at desc) where status = 'open';
create index if not exists claim_disputes_claim
  on claim_disputes (claim_id);

alter table claim_disputes enable row level security;

-- 접수는 누구나(로그인 불요). corrections 와 같은 이유다 — 이의를 제기하려고
-- 가입해야 한다면 그건 창구가 아니라 문턱이다.
drop policy if exists claim_disputes_insert on claim_disputes;
create policy claim_disputes_insert on claim_disputes
  for insert with check (
    char_length(claim_id) between 8 and 64
    and char_length(academy_key) between 1 and 64
    and char_length(coalesce(note, '')) <= 1000
  );

-- 조회는 운영자만. 접수 목록이 공개되면 그 자체가 학원 평가처럼 읽힌다.
drop policy if exists claim_disputes_admin on claim_disputes;
create policy claim_disputes_admin on claim_disputes
  for all to authenticated
  using (is_admin()) with check (is_admin());


-- ── 2) 취소 판정 ─────────────────────────────────────────────────
--
-- 파이프라인이 매 실행 읽는다. 여기 있는 주장은 다음 빌드에서 빠지고,
-- 그 학원의 점수 → 코호트 평균·표준편차 → 같은 코호트 전 학원의 등수까지
-- 다시 계산된다. 부분 삭제라면 '어디까지 지워야 하나' 를 사람이 판단해야
-- 하지만 매 실행 전부를 다시 짓는 구조라 판단할 것이 없다.
--
-- 행을 지우면 되살아난다. claim_id 가 결정적이라 같은 원문에서 같은 id 가
-- 다시 나오기 때문이다 — 취소를 되돌릴 수 있는 이유가 이것이다.
create table if not exists claim_verdicts (
  claim_id     text primary key,
  academy_key  text not null,
  verdict      text not null default 'revoked'
    check (verdict in ('revoked','stale','confirmed')),
  reason       text not null,               -- 사유 없는 취소는 나중에 지우지도 못한다
  note         text,
  source       text not null default 'admin' -- admin | auto_stale
    check (source in ('admin','auto_stale')),
  dispute_id   uuid references claim_disputes(id) on delete set null,
  created_at   timestamptz not null default now()
);

create index if not exists claim_verdicts_academy
  on claim_verdicts (academy_key);

alter table claim_verdicts enable row level security;

drop policy if exists claim_verdicts_admin on claim_verdicts;
create policy claim_verdicts_admin on claim_verdicts
  for all to authenticated
  using (is_admin()) with check (is_admin());


-- ── 3) 운영자 화면용 뷰 ──────────────────────────────────────────
--
-- 같은 주장에 이의가 여러 건 들어오면 한 줄로 묶어 보여준다. 쪼개 올리면
-- 같은 판단을 여러 번 하게 된다 — 검수 큐를 글 수로 세기로 한 것과 같다.
create or replace view v_claim_disputes
with (security_invoker = true) as
select d.claim_id,
       min(d.academy_key)                       as academy_key,
       min(d.claim_kind)                        as claim_kind,
       min(d.quote)                             as quote,
       count(*)                                 as dispute_count,
       array_agg(distinct d.reason)             as reasons,
       min(d.created_at)                        as first_seen,
       max(d.created_at)                        as last_seen,
       (v.claim_id is not null)                 as decided
from claim_disputes d
left join claim_verdicts v on v.claim_id = d.claim_id
where d.status = 'open'
group by d.claim_id, v.claim_id;

revoke all on v_claim_disputes from anon, authenticated;
grant select on v_claim_disputes to authenticated;
