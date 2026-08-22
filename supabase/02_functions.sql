-- 에듀트리 — 뷰 · RPC · 트리거
-- 실행: 01_schema.sql 이후

-- ─────────────────────────────────────────────────────────────
-- 랭킹 뷰: 앱이 가장 자주 때리는 쿼리. 인덱스가 타도록 단순하게 유지한다.
-- ─────────────────────────────────────────────────────────────
create or replace view v_ranking as
select
  a.id,
  a.name,
  a.region_id,
  a.subjects,
  a.grade_bands,
  a.tuition_monthly_krw,
  a.tofor_smtot        as capacity,
  a.reg_stttus_nm      as registration_status,
  a.is_verified,
  s.total,
  s.reputation,
  s.momentum,
  s.transparency,
  s.selectivity,
  s.sample_size,
  s.confidence,
  s.momentum_direction,
  rank() over (partition by a.region_id order by s.total desc) as rank_in_region
from academies a
join scores s on s.academy_id = a.id
where a.is_listed = true and s.is_ranked = true;

-- ─────────────────────────────────────────────────────────────
-- 지역 × 과목 랭킹 RPC
-- ─────────────────────────────────────────────────────────────
create or replace function ranking_for(
  p_region  text,
  p_subject text default null,
  p_band    text default null,
  p_limit   int  default 50
)
returns setof v_ranking
language sql
stable
as $$
  select *
  from v_ranking
  where region_id = p_region
    and (p_subject is null or subjects @> array[p_subject])
    and (p_band    is null or grade_bands @> array[p_band])
  order by total desc
  limit p_limit;
$$;

-- ─────────────────────────────────────────────────────────────
-- 테크트리 한 트랙을 통째로: 단계 + 엣지 + 단계별 학원
-- 앱의 그래프 화면이 이 함수 하나만 호출하면 되도록 설계했다.
-- ─────────────────────────────────────────────────────────────
create or replace function techtree_for(p_track text, p_region text)
returns jsonb
language sql
stable
as $$
  select jsonb_build_object(
    'track', to_jsonb(t),
    'stages', coalesce((
      select jsonb_agg(
        to_jsonb(st) || jsonb_build_object(
          'academies', coalesce((
            select jsonb_agg(jsonb_build_object(
              'id', a.id, 'name', a.name,
              'total', sc.total,
              'is_flagship', ast.is_flagship,
              'course_name', ast.course_name
            ) order by ast.is_flagship desc, sc.total desc nulls last)
            from academy_stages ast
            join academies a on a.id = ast.academy_id
            left join scores sc on sc.academy_id = a.id
            where ast.stage_id = st.id
              and a.region_id = p_region
              and a.is_listed = true
          ), '[]'::jsonb)
        ) order by st.depth, st.lane)
      from stages st where st.track_id = t.id
    ), '[]'::jsonb),
    'edges', coalesce((
      select jsonb_agg(to_jsonb(e))
      from stage_edges e
      join stages s1 on s1.id = e.from_stage_id
      where s1.track_id = t.id
    ), '[]'::jsonb)
  )
  from tracks t
  where t.id = p_track;
$$;

-- ─────────────────────────────────────────────────────────────
-- 정정 요청이 들어오면 해당 학원에 '검토 중' 상태를 만든다.
-- 제품 약속(7일 내 처리)을 데이터 계층에서 보증하기 위한 장치.
-- ─────────────────────────────────────────────────────────────
alter table academies
  add column if not exists correction_pending boolean not null default false;

create or replace function on_correction_received()
returns trigger
language plpgsql
security definer
as $$
begin
  update academies set correction_pending = true where id = new.academy_id;
  return new;
end;
$$;

drop trigger if exists trg_correction_received on corrections;
create trigger trg_correction_received
  after insert on corrections
  for each row execute function on_correction_received();

create or replace function on_correction_resolved()
returns trigger
language plpgsql
security definer
as $$
begin
  if new.status in ('resolved', 'rejected') and old.status not in ('resolved', 'rejected') then
    new.resolved_at := now();
    -- 미해결 요청이 더 없을 때만 배지를 내린다
    if not exists (
      select 1 from corrections
      where academy_id = new.academy_id
        and id <> new.id
        and status not in ('resolved', 'rejected')
    ) then
      update academies set correction_pending = false where id = new.academy_id;
    end if;
  end if;
  return new;
end;
$$;

drop trigger if exists trg_correction_resolved on corrections;
create trigger trg_correction_resolved
  before update on corrections
  for each row execute function on_correction_resolved();

-- 언급 집계 뷰 갱신 (수집 후 호출)
create or replace function refresh_mention_stats()
returns void
language sql
as $$
  refresh materialized view concurrently mention_monthly;
$$;
