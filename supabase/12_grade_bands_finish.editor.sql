-- 학년 구간 전환 마무리 (2026-08-26)
--
-- 05_grade_bands.sql 이 라이브 DB 에 적용되지 않은 채로 남아 있었다.
-- 그 결과 야간 수집이 매번 마지막 단계에서 실패했다:
--
--     tracks 업서트 실패 400: Could not find the 'grade_band' column
--                             of 'tracks' in the schema cache
--
-- 수집·채점은 이미 끝난 뒤라 JSON 과 사이트는 멀쩡했고 Supabase 미러만
-- 낡아 있었다. 그래서 오래 눈에 안 띄었다.
--
-- ★ 05 는 컬럼만 바꾸고 **뷰와 RPC 를 놓쳤다.** academies.school_levels 를
--   바꾸면 v_ranking 은 계속 돌지만 출력 컬럼 이름이 옛 이름으로 남는다
--   (뷰의 출력 이름은 만들 때 고정된다). ranking_for 의 파라미터 이름도
--   마찬가지다. 둘 다 create or replace 로는 못 바꾸므로 다시 만든다.
--
-- 이 파일은 **여러 번 돌려도 안전하다.** 각 단계가 이미 됐는지 보고 건넌다.


-- ── 1. 컬럼 이름 ────────────────────────────────────────────────
do $$
begin
  if exists (select 1 from information_schema.columns
              where table_schema='public' and table_name='academies'
                and column_name='school_levels') then
    alter table academies rename column school_levels to grade_bands;
  end if;
  if exists (select 1 from information_schema.columns
              where table_schema='public' and table_name='tracks'
                and column_name='school_level') then
    alter table tracks rename column school_level to grade_band;
  end if;
  if exists (select 1 from information_schema.columns
              where table_schema='public' and table_name='board_posts'
                and column_name='school_level') then
    alter table board_posts rename column school_level to grade_band;
  end if;
end $$;

-- ── 2. 값 옮기기 ────────────────────────────────────────────────
-- 기존 elementary 는 어느 쪽인지 알 수 없으니 둘 다로 둔다. 좁혀 넣으면
-- 없는 정보를 만들어 내는 셈이라, 넓게 두고 다음 수집에서 정해진다.
update academies
   set grade_bands = array_remove(grade_bands, 'elementary')
                     || array['elem_low', 'elem_high']
 where grade_bands @> array['elementary'];

update tracks      set grade_band = 'elem_low' where grade_band = 'elementary';
update board_posts set grade_band = 'elem_low' where grade_band = 'elementary';

-- ── 3. 뷰·RPC 를 새 이름에 맞춘다 ───────────────────────────────
-- 함수가 뷰에 의존하므로 함수를 먼저 지운다.
drop function if exists public.ranking_for(text, text, text, int);
drop view     if exists public.v_ranking;

create view public.v_ranking as
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

-- 뷰를 다시 만들면 권한이 사라진다. 지우기 전 상태 그대로 돌려놓는다.
grant select, insert, update, delete, truncate, references, trigger
   on public.v_ranking to anon, authenticated, service_role, postgres;

create function public.ranking_for(
  p_region  text,
  p_subject text default null,
  p_band    text default null,
  p_limit   int  default 50
)
returns setof public.v_ranking
language sql
stable
as $fn$
  select *
  from v_ranking
  where region_id = p_region
    and (p_subject is null or subjects @> array[p_subject])
    and (p_band    is null or grade_bands @> array[p_band])
  order by total desc
  limit p_limit;
$fn$;

grant execute on function public.ranking_for(text, text, text, int)
   to anon, authenticated, service_role, postgres;
