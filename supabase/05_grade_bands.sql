-- 학교급 → 학년 구간 전환 (2026-08)
--
-- 초등을 예비초~초3 / 초4~초6 으로 갈랐다. 학원가에서 이 둘은 사실상
-- 다른 시장이라 한 덩어리로 두면 학부모가 자기 구간이 아닌 것을 계속 본다.
--
-- 컬럼 이름도 함께 바꾼다. 기존 school_level 은 학교(초등학교·중학교·
-- 고등학교)와 이름이 겹쳐 매번 헷갈렸다. 학원이 받는 학년대는 grade_band.
--
-- 이미 만든 설치본에만 필요하다. 새로 올리는 경우 01/02/04 가 이미 새 이름이다.

alter table if exists academies  rename column school_levels to grade_bands;
alter table if exists tracks     rename column school_level  to grade_band;
alter table if exists board_posts rename column school_level to grade_band;

-- 값 옮기기: 기존 elementary 는 어느 쪽인지 알 수 없으니 둘 다로 둔다.
-- 좁혀 넣으면 없는 정보를 만들어 내는 셈이라, 넓게 두고 다음 수집에서 정해진다.
update academies
   set grade_bands = array_remove(grade_bands, 'elementary')
                     || array['elem_low', 'elem_high']
 where grade_bands @> array['elementary'];

update tracks      set grade_band = 'elem_low' where grade_band = 'elementary';
update board_posts set grade_band = 'elem_low' where grade_band = 'elementary';
