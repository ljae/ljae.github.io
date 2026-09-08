# 교재 랭킹·후기 — 설계 메모 (2026-09-07, 착수 전)

학원 다음은 교재다. '초4 사고력은 어느 문제집으로' 가 학부모의 다음 질문이고,
후기는 이미 우리 코퍼스에 있다(캐시 5만 글 중 '최상위수학' 은 학원이 아니라
**문제집**으로 6건이 걸려 학원 셋의 근거가 됐다). 이 문서는 무엇을 재사용하고
무엇을 새로 만드는지, 그리고 **학원에서 배운 함정 중 교재에 그대로 옮겨 오는
것**을 적는다. 코드는 아직 없다.

## 한 줄 정의

    교재 = (이름, 출판사, 시리즈, 과목, 학년 구간, 단계) 를 가진 엔티티.
    점수 = 평판 60 + 화제성 40 (예체능·기타와 같은 두 기둥 산식).
    투명성·진입난이도는 없다 — 교재에는 공시도 레벨테스트도 없다. 0 이 아니라 null.

## 재사용하는 것 (바꾸지 않는다)

| 층 | 그대로 쓰는 것 | 이유 |
|---|---|---|
| 수집 | `naver.search` · `mention_store`(키 접두 `tb:`) · `discovery` · `coverage` | 같은 API, 같은 회차 순환 |
| 게이트 | `analyze.name_candidates` · `is_relevant` · `RivalIndex` · `trade_seam` · `nameaudit` | 이름을 글에 잇는 문제는 동일 |
| 분해 | `claims.py` 의 사실 카드 틀(인용문 필수, id 는 알맹이) | 종류만 다르다(아래) |
| 채점 | `scoring.reputation` · `momentum` · 코호트 z점수 · Kish · `audit_contribution` | 두 기둥 산식은 이미 있다(`NON_ACADEMIC_WEIGHTS`) |
| 검수 | `mention_reviews` · `crawl_rules` · 질문 큐 · 위키 frontmatter · 글 노드 | 키가 `url_hash|entity_key` 라 그대로 |
| 대장 | `cases.py`(`entity_type: textbook`) · `tests/cases`(`entity_type`) · 에이전트 | 이미 엔티티 중립 |
| 앱 | `Score` · `Evidence` · `ClaimEvidence` · `FactCard` · `AspectStat` · `Meta.weights` · 實錄 조형 | 모델을 복제하지 않는다 |

## 새로 만드는 것

1. **시드** `pipeline/data/textbooks.yaml` — 자동 생성이 불가능하다. 학원의
   `techtree.yaml` 처럼 사람이 적는다.
   ```yaml
   - id: tb-cheonjae-choisangwi-math        # 안정 id. ISBN 은 판마다 달라 키로 못 쓴다
     name: 최상위수학
     publisher: 천재교육
     series: 최상위
     subject: math
     grade_bands: [elem_high]
     stages: [math_el_competition]           # techtree 단계 id — 로드맵에 그대로 앉는다
     aliases: [최상위 수학, 최상수학]
     level: 심화                              # 개념 · 유형 · 심화 · 경시 (사람이 적는 상대 난도)
   ```
2. **엔티티 어댑터** `pipeline/edutree/textbooks.py` — 시드를 `academies` 와 같은
   행 모양으로 편다(`id`·`name`·`brand`(=series)·`aliases`·`subjects`·
   `grade_bands`·`stages`·`region_id: null`). 게이트·채점 함수는 행 모양만 본다.
3. **교재 전용 사실 종류** — `claims.FACT_KINDS` 에 더한다. 학원의 숙제량·수업
   횟수는 교재에 없다.
   ```
   fact.tb_pages_per_day   하루 분량(쪽)      fact.tb_weeks     완주 기간(주)
   fact.tb_level_fit       '초4 상위권에 맞다' 류 학년·수준 적합 언급 (값 없음, 인용만)
   fact.tb_pair            함께 쓰는 교재 (값 = 다른 교재 id)  ← 교재의 '진급 관계'
   ```
   `fact.tb_pair` 가 교재의 테크트리다 — '디딤돌 → 최상위 → 경시' 는 후기가
   실제로 말하는 순서이고, 학원의 `techtree.yaml` 처럼 큐레이션으로 뼈대를 두되
   후기의 짝 언급을 `stageCounts` 처럼 채움 정도로 보여준다.
4. **앱** — `textbooks.json` + `textbookDataProvider`(`mapDataProvider` 처럼 늦게
   읽는다), `/textbook`·`/textbook/:id` 라우트, 로드맵 단계 시트에 '이 단계의
   교재' 절(학원 목록 아래, 같은 근거 등급 표기). 상단 메뉴 자리는 '산식' 을
   설명란 링크로 내리면서 비워 두었다.
5. **Supabase** — `user_reviews.academy_key` 를 `(target_type, target_key)` 로
   넓힌다(마이그레이션 15). `bookmarks`·`corrections`·`evidence_reports` 도 같은
   짝으로. `on delete cascade` 는 걸지 않는다 — 학원에서 배운 대로, 사람이 쓴
   것이 매달린 표는 지우지 않는다.

## 학원에서 배운 것 중 교재에 그대로 오는 함정

- **이름이 곧 검색어이고, 이름이 흔하면 오염원이다.** '개념원리'·'쎈'·'디딤돌'
  은 브랜드이자 일상어에 가깝다. `is_generic_academy` 의 목록을 교재용으로 따로
  둔다(`GENERIC_TEXTBOOK_PARTS`). 표지 낱말도 다르다 — '레테·원장' 이 아니라
  '풀었·채점·오답·정답률·권'.
- **학원 이름과 교재 이름이 겹친다.** 최상위수학(학원 3곳 · 문제집), 개념폴리아
  (학원 · 교재 브랜드), 시매쓰(학원 · 교재). 같은 글이 학원 근거이자 교재 근거가
  될 수 있고, 그것은 오류가 아니다 — 단 **한 글은 한 엔티티에 대해 한 가지만**
  말한다는 규칙(과목 하나·학급 하나)을 엔티티 종류에도 건다: 이름 곁 ±45자에
  '학원·다니' 가 있으면 학원 글, '풀었·권·페이지' 가 있으면 교재 글, 둘 다면
  둘 다, 둘 다 없으면 어느 쪽에도 안 붙인다.
- **지점 문제는 없지만 판(版) 문제가 있다.** '최상위수학 2015개정' 과 '2022개정'
  은 다른 책이고 후기도 갈린다. 지점 게이트의 '제목이 우선' 규칙을 판 표기에
  그대로 쓴다 — 제목에 판이 있으면 그 판에만, 없으면 시리즈 공통(형제가 있으면
  근거로 쓰지 않는다는 2026-09-05 규칙도 동일).
- **표본 0 은 '없다'.** 새 교재는 대부분 근거가 없다. 점수를 내지 않고 '등록부 ·
  미수집' 과 같은 세 층으로 적는다.
- **광고가 학원보다 많다.** 출판사·서점·인강 제휴 글이 후기 꼴을 하고 있다.
  `flag_near_duplicates`·`flag_author_bursts` 는 그대로 쓰되 `PROMO_PHRASES` 에
  '증정·이벤트·구매링크·할인' 을 더한다. 버스트에 발견일을 쓰지 않는다는
  규칙도 같다.
- **가중치는 실효 기여로 검증한다.** 두 기둥이라도 σ 가 다르면 한 기둥이
  지배한다. 첫 회차에 `audit_contribution` 을 교재 코호트에도 건다.

## 착수 순서 (각 단계가 홀로 배포 가능해야 한다)

1. 시드 30권(수학·영어 초등 위주) + 어댑터 + 게이트 통과 수 측정만. 화면 없음.
2. 채점 + `textbooks.json` + 로드맵 단계 시트의 '이 단계의 교재' 절.
3. `/textbook` 목록·상세(근거 발췌·사실 카드·이의). 정정 창구 연결.
4. 학원실록 자체 후기(`user_reviews`) 확장.

**하지 않는다:** 구매 링크·제휴, 가격 비교, 정답률 같은 만들어낼 수 없는 값,
'최악의 교재'. 학원과 같은 원칙이다.
