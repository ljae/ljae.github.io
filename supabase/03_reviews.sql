-- 학원실록 자체 후기 — 앱이 실제로 쓰는 형태에 맞춘 조정
-- 실행: 01_schema.sql, 02_functions.sql 다음

-- 앱은 학원을 NEIS 학원지정번호(문자열)로 식별한다. 최초 스키마는 내부 uuid 를
-- 참조하게 돼 있었는데, 정적 번들만으로 도는 화면에서는 uuid 를 알 수 없다.
-- 그래서 후기는 지정번호를 그대로 키로 쓴다.
alter table user_reviews
  add column if not exists academy_key text;

update user_reviews r
set academy_key = a.aca_asnum
from academies a
where r.academy_id = a.id and r.academy_key is null;

alter table user_reviews
  alter column academy_id drop not null;

create unique index if not exists user_reviews_academy_author
  on user_reviews (academy_key, author_id);

create index if not exists user_reviews_academy_published
  on user_reviews (academy_key) where status = 'published';

-- 가입 즉시 프로필이 생기도록. 없으면 후기 작성에서 외래키 오류가 난다.
create or replace function handle_new_user()
returns trigger
language plpgsql
security definer
as $$
begin
  insert into profiles (id, nickname)
  values (
    new.id,
    -- 이메일 앞부분을 기본 닉네임으로. 전체 주소를 노출하지 않는다.
    coalesce(split_part(new.email, '@', 1), '학부모') || '님'
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function handle_new_user();

-- 후기 읽기는 공개, 쓰기는 본인만. (01_schema.sql 의 정책을 academy_key 기준으로)
drop policy if exists public_read on user_reviews;
create policy public_read on user_reviews
  for select using (status = 'published');

-- 학원별 후기 요약 — 평판 점수에 반영할 때 파이프라인이 읽는다.
create or replace view v_review_summary as
select
  academy_key,
  count(*)                       as review_count,
  round(avg(rating)::numeric, 2) as avg_rating,
  max(created_at)                as latest_at
from user_reviews
where status = 'published' and academy_key is not null
group by academy_key;

grant select on v_review_summary to anon, authenticated;
