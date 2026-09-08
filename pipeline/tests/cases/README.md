# 사례 픽스처 — 신고 한 건이 회귀 테스트 한 건이 된다

`pipeline/wiki/cases/<id>.md` 에서 **고친** 사례는 여기 `<id>.yaml` 한 장으로
굳는다. `tests/test_cases.py` 가 이 디렉터리를 전부 읽어 파이프라인의 실제
함수로 돌리고 기대값과 견준다. 픽스처가 다시 통과하지 못하면 그 신고의
원인이 되살아난 것이다.

왜 코드 안의 테스트가 아니라 파일인가: 신고는 사람 말이고 원문은 글이다.
YAML 한 장에 **원문 그대로**와 **학원 등록값 그대로**를 두면, 규칙을 어떻게
바꾸든 "그 글이 그 학원의 근거인가" 라는 질문 자체는 변하지 않는다. 그리고
에이전트가 사례를 닫을 때 파일 한 장을 더 쓰는 것이 테스트 함수를 짓는 것보다
빠뜨리기 어렵다 — `cases.audit()` 이 픽스처 없는 fixed 를 매 실행 경고한다.

## 공통 필드

```yaml
case: er-1a2b3c4d          # 사례 id (wiki/cases/<id>.md). 이력 픽스처는 hist-…
entity_type: academy       # academy | textbook — 교재 랭킹이 붙으면 같은 형식
kind: relevance            # 아래 종류 중 하나
why: |                     # 한 문단. 무엇이 새고 무엇으로 막았나 (근거·수치)
expect: {...}              # 종류별 기대값
```

`expect` 의 키는 세 꼴이다: `x: 값`(정확히 같아야), `x_include: [..]`(전부
들어 있어야), `x_exclude: [..]`(하나도 없어야).

## 종류(kind)

### relevance — 이 글이 이 학원의 근거인가

```yaml
academy: {name: 송파폴리어학원, brand: 폴리어학원, aliases: [], region_id: jamsil}
wiki: {aliases: [], generic: false}         # 선택. 위키 frontmatter 힌트
rivals: [캔비어학원, 청담어학원]              # 선택. 남의 학원 이름 색인
mention: {title: "...", snippet: "..."}
expect: {relevant: false}
```
돌리는 것: `analyze.name_candidates` − `weak_candidates` (+ 위키 aliases),
`is_generic_academy` (또는 위키 generic), `analyze.is_relevant`.

### branch — 어느 지점의 근거인가

```yaml
academies:
  - {id: D, name: 대치정상어학원, region_id: daechi, brand: 정상어학원, dong: 대치동}
  - {id: M, name: 목동정상어학원, region_id: mokdong, brand: 정상어학원, dong: 목동}
locality: {D: [], M: []}                    # 선택. 위키 locality
mention: {title: "...", snippet: "...", academy_key: D}
expect: {kept_for: []}                      # 남은 (글, 학원) 의 학원 id 목록
```
돌리는 것: `branches.apply`.

### subject — 과목·학년 구간

```yaml
academy: {name: 그로튼아카데미학원, realm: "국제화", course: "실용외국어(유아/초·중·고)", crse: ""}
expect: {subjects: [english]}               # 또는 subjects_include / subjects_exclude / bands
```
돌리는 것: `build._infer_subjects`, `build._infer_bands`.

### merge — 두 등록이 한 학원인가

```yaml
rows:
  - {name: 대치정상수학학원, addr: "서울특별시 강남구 도곡로 1", region_id: daechi}
  - {name: 대치1관정상어학원, addr: "서울특별시 강남구 도곡로 1", region_id: daechi}
expect: {merged: false}
```
돌리는 것: `dedupe.apply`. `merged: true` 는 전부 한 묶음, `false` 는 전부 따로.

### claim — 주장 추출

```yaml
academy: {name: 다라영어학원}
mention: {title: "...", snippet: "..."}
expect: {claim_kinds_exclude: [sel.waitlist]}   # 또는 claim_kinds_include
```
돌리는 것: `claims.extract`.

### name — 이름 후보

```yaml
academy: {name: 대치학원}
expect: {candidates: []}                    # 또는 candidates_include / candidates_exclude
```
돌리는 것: `analyze.name_candidates` − `weak_candidates`.

`display`·`score`·`coverage`·`data_lag` 사례에는 픽스처가 없다 — 화면은 위젯
테스트(`app/test`), 산식은 `test_scoring.py` 로 굳힌다.
