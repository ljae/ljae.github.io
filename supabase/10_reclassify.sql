-- 검수: '제외' 말고 '재분류'
--
-- 네 학원을 비교하는 글이 한 학원에만 근거로 붙는 일이 있다. 지금은
-- 반려밖에 못 해서, 글은 멀쩡한데 통째로 버려졌다. 어느 학원 글인지
-- 사람이 아는데도 그 정보를 못 남긴 것이다.
--
-- verdict='reclassified' 는 '이 학원의 근거는 아니다'(반려와 같은 효과)이고,
-- reassign_to 는 '대신 이 학원들의 근거다'를 담는다. 둘은 별개다 —
-- 네 곳 중 한 곳은 맞고 세 곳이 틀린 경우가 있다.
alter table public.mention_reviews
  add column if not exists reassign_to text[];

comment on column public.mention_reviews.reassign_to is
  '이 글을 근거로 삼아야 할 학원 id 들. 파이프라인이 다음 수집에서 붙인다.';

create index if not exists mention_reviews_reassign_idx
  on public.mention_reviews using gin (reassign_to)
  where reassign_to is not null;
