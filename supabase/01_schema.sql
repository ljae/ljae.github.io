-- 에듀트리 (EduTree) — 코어 스키마
-- Supabase / PostgreSQL 15+
-- 실행: supabase db push  또는  psql -f supabase/01_schema.sql

create extension if not exists "uuid-ossp";
create extension if not exists pg_trgm;      -- 학원명 유사 매칭
create extension if not exists postgis;      -- 학군 반경 쿼리

-- ─────────────────────────────────────────────────────────────
-- 1. 지역 / 학군
-- ─────────────────────────────────────────────────────────────
create table regions (
  id              text primary key,                    -- 'daechi' | 'mokdong' | 'banpo' | 'jamsil'
  name_ko         text not null,                       -- '대치'
  name_en         text not null,
  sido            text not null default '서울특별시',
  sigungu         text not null,                       -- '강남구'
  dong_list       text[] not null,                     -- ['대치동','도곡동']
  atpt_code       text not null default 'B10',         -- NEIS 시도교육청 코드
  center          geography(point, 4326),              -- 지도 초기 중심
  tagline         text,
  sort_order      int not null default 0
);

-- ─────────────────────────────────────────────────────────────
-- 2. 학원 (NEIS 원장 + 파생 정보)
-- ─────────────────────────────────────────────────────────────
create table academies (
  id                  uuid primary key default uuid_generate_v4(),
  aca_asnum           text unique,                     -- NEIS 학원지정번호. 공식 데이터의 기본키
  name                text not null,
  name_normalized     text not null,                   -- 매칭용: 공백/법인격/지점명 제거
  aliases             text[] default '{}',             -- 커뮤니티 통용 약칭 ('생황', '깊생')
  region_id           text references regions(id),

  -- NEIS acaInsTiInfo 원본 필드 매핑
  realm_sc_nm         text,                            -- 분야구분 (입시검정및보습 등)
  le_ord_nm           text,                            -- 교습계열 (보통교과 등)
  le_crse_list_nm     text,                            -- 교습과정
  reg_stttus_nm       text,                            -- 등록상태 (정상/휴원/폐원)
  estbl_ymd           date,                            -- 개설일자
  tofor_smtot         int,                             -- 정원 합계
  dtm_rcptn_ablty_nmpr_smtot int,                      -- 동시수용인원 합계
  thcc_ctnt           text,                            -- 교습비 내용 (원문)
  tuition_monthly_krw int,                             -- 파싱된 월 교습비 (원)
  road_address        text,
  tel                 text,
  location            geography(point, 4326),

  -- 서비스 파생
  subjects            text[] default '{}',             -- ['math','english']
  grade_bands         text[] default '{}',             -- ['elem_low','elem_high','middle','high']
  logo_url            text,
  is_verified         boolean not null default false,  -- NEIS 매칭 성공 여부
  is_listed           boolean not null default true,   -- 노출 여부 (정정요청 시 false 가능)

  neis_synced_at      timestamptz,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);
create index on academies using gin (name_normalized gin_trgm_ops);
create index on academies using gist (location);
create index on academies (region_id, is_listed);

-- ─────────────────────────────────────────────────────────────
-- 3. 테크트리 그래프  (큐레이션 영역)
-- ─────────────────────────────────────────────────────────────
create table tracks (
  id            text primary key,                      -- 'math_elementary'
  subject       text not null,                         -- math | english | korean | science
  grade_band    text not null,                         -- elem_low | elem_high | middle | high
  title         text not null,                         -- '초등 수학'
  summary       text,
  sort_order    int not null default 0,
  unique (subject, grade_band)
);

create table stages (
  id                  text primary key,                -- 'math_el_thinking'
  track_id            text not null references tracks(id) on delete cascade,
  title               text not null,                   -- '사고력 수학'
  subtitle            text,
  goal                text,                            -- 이 단계의 목표
  exit_criteria       text,                            -- 다음 단계로 넘어가는 기준
  typical_grade_min   int,                             -- 초1=1 … 고3=12
  typical_grade_max   int,
  depth               int not null default 0,          -- 그래프 X축 (진행 순서)
  lane                int not null default 0,          -- 그래프 Y축 (병렬 루트 구분)
  sort_order          int not null default 0
);
create index on stages (track_id, depth);

create table stage_edges (
  id                uuid primary key default uuid_generate_v4(),
  from_stage_id     text not null references stages(id) on delete cascade,
  to_stage_id       text not null references stages(id) on delete cascade,
  condition_text    text,                              -- '초4 겨울, 선행 1년 + 레벨테스트 통과'
  edge_type         text not null default 'standard',  -- standard | accelerated | alternative
  -- 근거: 이 경로를 언급한 커뮤니티 게시물 수. 0이면 UI에서 점선 처리.
  evidence_count    int not null default 0,
  note              text,
  unique (from_stage_id, to_stage_id)
);

create table academy_stages (
  academy_id      uuid not null references academies(id) on delete cascade,
  stage_id        text not null references stages(id) on delete cascade,
  course_name     text,                                -- 대표 강좌/반 이름
  is_flagship     boolean not null default false,      -- 이 단계의 대표 학원
  note            text,
  primary key (academy_id, stage_id)
);

-- ─────────────────────────────────────────────────────────────
-- 4. 커뮤니티 신호  (원문 미저장 — 집계와 링크만)
-- ─────────────────────────────────────────────────────────────
create table mentions (
  id                uuid primary key default uuid_generate_v4(),
  academy_id        uuid not null references academies(id) on delete cascade,
  source            text not null,                     -- naver_cafe | naver_blog | naver_kin | cafe_local
  source_url        text not null,
  url_hash          text not null unique,              -- 중복 수집 방지
  author_hash       text,                              -- 작성자 해시 (동일인 반복 판별용, 원본 미저장)
  title             text,
  snippet           text,                              -- API가 반환한 요약 스니펫만 (전문 저장 금지)
  posted_at         timestamptz,

  -- 분석 결과
  sentiment         real,                              -- [-1, 1]
  credibility       real not null default 0.5,         -- [0, 1]
  spam_score        real not null default 0.0,         -- [0, 1] — 높을수록 광고/바이럴 의심
  aspects           jsonb default '{}',                -- {"강사":0.8,"관리":-0.2,"가격":-0.5}
  is_excluded       boolean not null default false,    -- 스팸 판정 시 점수 반영 제외

  collected_at      timestamptz not null default now()
);
create index on mentions (academy_id, posted_at desc);
create index on mentions (academy_id) where is_excluded = false;

-- 월별 언급량 집계 (화제성 계산용 — 매 수집 후 리프레시)
create materialized view mention_monthly as
select academy_id,
       date_trunc('month', posted_at) as month,
       count(*)                        as mention_count,
       avg(sentiment)                  as avg_sentiment
from mentions
where is_excluded = false and posted_at is not null
group by 1, 2;
create unique index on mention_monthly (academy_id, month);

-- ─────────────────────────────────────────────────────────────
-- 5. 트리스코어
-- ─────────────────────────────────────────────────────────────
create table scores (
  academy_id          uuid primary key references academies(id) on delete cascade,
  total               real not null,                   -- 0–100

  reputation          real,                            -- 35%
  momentum            real,                            -- 20%
  transparency        real,                            -- 25%
  selectivity         real,                            -- 20%

  -- 신뢰도
  sample_size         int not null default 0,          -- 유효 게시물 수
  confidence          text not null default 'low',     -- high | medium | low
  is_ranked           boolean not null default false,  -- sample_size >= 10 인 경우만 순위 노출

  -- 추이
  momentum_direction  text,                            -- rising | stable | falling
  prev_total          real,
  prev_rank           int,

  breakdown           jsonb default '{}',              -- 기둥별 세부 계산 근거 (UI 공개용)
  computed_at         timestamptz not null default now()
);
create index on scores (total desc) where is_ranked = true;

create table score_history (
  academy_id    uuid not null references academies(id) on delete cascade,
  snapshot_date date not null,
  total         real not null,
  rank_in_region int,
  primary key (academy_id, snapshot_date)
);

-- ─────────────────────────────────────────────────────────────
-- 6. 사용자 영역
-- ─────────────────────────────────────────────────────────────
create table profiles (
  id            uuid primary key references auth.users(id) on delete cascade,
  nickname      text not null,
  region_id     text references regions(id),
  child_grades  int[] default '{}',                    -- 자녀 학년
  created_at    timestamptz not null default now()
);

create table user_reviews (
  id            uuid primary key default uuid_generate_v4(),
  academy_id    uuid not null references academies(id) on delete cascade,
  author_id     uuid not null references profiles(id) on delete cascade,
  rating        int not null check (rating between 1 and 5),
  body          text not null check (char_length(body) between 20 and 3000),
  attended_from date,
  attended_to   date,
  aspects       jsonb default '{}',
  status        text not null default 'published',     -- published | hidden | under_review
  created_at    timestamptz not null default now(),
  unique (academy_id, author_id)
);

create table bookmarks (
  user_id     uuid not null references profiles(id) on delete cascade,
  academy_id  uuid not null references academies(id) on delete cascade,
  created_at  timestamptz not null default now(),
  primary key (user_id, academy_id)
);

-- 학원 운영자 정정 요청 (법적 방어선)
create table corrections (
  id            uuid primary key default uuid_generate_v4(),
  academy_id    uuid not null references academies(id) on delete cascade,
  claim_type    text not null,                         -- factual_error | defamation | closed | other
  body          text not null,
  contact       text not null,
  evidence_url  text,
  status        text not null default 'received',      -- received | reviewing | resolved | rejected
  resolution    text,
  created_at    timestamptz not null default now(),
  resolved_at   timestamptz
);

-- ─────────────────────────────────────────────────────────────
-- 7. RLS
-- ─────────────────────────────────────────────────────────────
alter table academies      enable row level security;
alter table scores         enable row level security;
alter table mentions       enable row level security;
alter table stages         enable row level security;
alter table stage_edges    enable row level security;
alter table academy_stages enable row level security;
alter table tracks         enable row level security;
alter table regions        enable row level security;
alter table profiles       enable row level security;
alter table user_reviews   enable row level security;
alter table bookmarks      enable row level security;
alter table corrections    enable row level security;

-- 공개 읽기 (노출 허용된 것만)
create policy public_read on regions        for select using (true);
create policy public_read on tracks         for select using (true);
create policy public_read on stages         for select using (true);
create policy public_read on stage_edges    for select using (true);
create policy public_read on academy_stages for select using (true);
create policy public_read on academies      for select using (is_listed = true);
create policy public_read on scores         for select using (true);
create policy public_read on mentions       for select using (is_excluded = false);
create policy public_read on user_reviews   for select using (status = 'published');

-- 본인 데이터
create policy own_profile   on profiles     for all    using (auth.uid() = id);
create policy own_review    on user_reviews for insert with check (auth.uid() = author_id);
create policy edit_review   on user_reviews for update using (auth.uid() = author_id);
create policy del_review    on user_reviews for delete using (auth.uid() = author_id);
create policy own_bookmark  on bookmarks    for all    using (auth.uid() = user_id);

-- 정정 요청: 누구나 제출 가능, 조회는 관리자만
create policy anyone_submit on corrections  for insert with check (true);
