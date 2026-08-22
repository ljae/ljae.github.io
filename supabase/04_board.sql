-- 학원실록 게시판
--
-- 설계 원칙: 글이 통계로 이어지는 것이 보여야 한다.
-- 학부모가 쓴 글이 학원에 연결되고, 그 연결이 트리스코어에 반영되고,
-- 반영된 결과가 다시 게시판에 리포트로 돌아온다. 이 순환이 눈에 보이지
-- 않으면 게시판은 그냥 또 하나의 죽은 커뮤니티가 된다.

create table if not exists board_posts (
  id            uuid primary key default uuid_generate_v4(),
  category      text not null default 'talk',
    -- talk 수다 | question 질문 | review 후기 | report 리포트(자동) | guide 해설
  region_id     text references regions(id),
  school_level  text,                      -- elementary | middle | high
  subject       text,                      -- math | english | korean | science
  title         text not null check (char_length(title) between 2 and 120),
  body          text not null check (char_length(body) between 5 and 20000),

  author_id     uuid references profiles(id) on delete set null,
  -- 학원실록이 만든 글. 사람 글인 척하지 않기 위해 명시적으로 구분한다.
  is_official   boolean not null default false,
  official_kind text,                      -- weekly_report | stage_guide | seed_question

  -- 이 글이 언급하는 학원들. 통계 반영의 연결 고리.
  academy_keys  text[] not null default '{}',

  view_count    int not null default 0,
  comment_count int not null default 0,
  status        text not null default 'published',   -- published | hidden
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
create index if not exists board_posts_recent
  on board_posts (created_at desc) where status = 'published';
create index if not exists board_posts_region
  on board_posts (region_id, created_at desc) where status = 'published';
create index if not exists board_posts_academies
  on board_posts using gin (academy_keys);

create table if not exists board_comments (
  id          uuid primary key default uuid_generate_v4(),
  post_id     uuid not null references board_posts(id) on delete cascade,
  author_id   uuid references profiles(id) on delete set null,
  body        text not null check (char_length(body) between 2 and 4000),
  status      text not null default 'published',
  created_at  timestamptz not null default now()
);
create index if not exists board_comments_post
  on board_comments (post_id, created_at);

-- 댓글 수를 글에 반영. 목록에서 매번 세지 않기 위해서.
create or replace function bump_comment_count()
returns trigger language plpgsql security definer as $$
begin
  if tg_op = 'INSERT' then
    update board_posts set comment_count = comment_count + 1 where id = new.post_id;
  elsif tg_op = 'DELETE' then
    update board_posts set comment_count = greatest(0, comment_count - 1)
    where id = old.post_id;
  end if;
  return null;
end; $$;

drop trigger if exists trg_comment_count on board_comments;
create trigger trg_comment_count
  after insert or delete on board_comments
  for each row execute function bump_comment_count();

-- ── 통계 연결 ────────────────────────────────────────────────
-- 게시판 언급을 학원별로 집계한다. 파이프라인이 이 뷰를 읽어
-- 트리스코어의 평판·화제성에 반영한다.
create or replace view v_board_mentions as
select
  key                                        as academy_key,
  count(*)                                   as post_count,
  count(*) filter (where p.created_at > now() - interval '90 days') as recent_count,
  max(p.created_at)                          as latest_at,
  sum(p.comment_count)                       as comment_total
from board_posts p, unnest(p.academy_keys) as key
where p.status = 'published' and p.is_official = false
group by key;

grant select on v_board_mentions to anon, authenticated;

-- ── RLS ──────────────────────────────────────────────────────
alter table board_posts    enable row level security;
alter table board_comments enable row level security;

drop policy if exists board_read on board_posts;
create policy board_read on board_posts
  for select using (status = 'published');

drop policy if exists board_write on board_posts;
create policy board_write on board_posts
  for insert with check (auth.uid() = author_id and is_official = false);

drop policy if exists board_edit on board_posts;
create policy board_edit on board_posts
  for update using (auth.uid() = author_id);

drop policy if exists comment_read on board_comments;
create policy comment_read on board_comments
  for select using (status = 'published');

drop policy if exists comment_write on board_comments;
create policy comment_write on board_comments
  for insert with check (auth.uid() = author_id);

drop policy if exists comment_edit on board_comments;
create policy comment_edit on board_comments
  for update using (auth.uid() = author_id);

-- 조회수 증가 (로그인 없이도 가능해야 하므로 함수로 연다)
create or replace function bump_view(p_id uuid)
returns void language sql security definer as $$
  update board_posts set view_count = view_count + 1 where id = p_id;
$$;
grant execute on function bump_view(uuid) to anon, authenticated;
