---
id: cd-16c9deeb
source: claim_dispute
source_id: 16c9deeb-1c94-4b42-9821-808131795635
source_status: open
entity_type: academy
entity_key: "3000040050"
entity_name: 새로운학원
reported_at: 2026-08-31
reason: other
claim_id: 1562b04c5e196b82
claim_kind: sel.waitlist
# ↓ 상태 기계. 에이전트·사람이 바꾼다. 엔진은 요약·감사에만 읽는다.
status: verified              # open → triaged → fixed → verified → closed | declined
category: relevance
resolution: [code, wiki, fixture]            # post | wiki | rule | code | fixture | data | none
fixture: tests/cases/hist-2026-09-03-saeroun-phrase.yaml
landed_in: 0c2e61f3f
---
# 새로운학원 — 기타

## 신고
<!-- auto:report -->
- 주장 종류: sel.waitlist
- 인용문: 학원에서 얼굴을 맞고 왔다는데요ㅜㅜ 저희 아이는 2학년이고요~ 저번주 금요일날 학원 같은 반 4학년 오빠한테 싸대기를 맞았다고 했어요~ 그동안.
- 내용:
  > 학폭에 관한 글로 전혀 상관없는 글입니다.
<!-- /auto:report -->

## 진단


### 2026-09-07
- 종류: relevance — 이름 전체가 학원 이야기 속의 구(句). '새로운학원' 을 정규화하면 '새로운 학원' 과 같은 글자열이 되어, 학원을 옮기고·고르고·운영하는 이야기가 전부 이 학원의 근거가 됐다(CLAUDE.md '이름이 학원 이야기 속의 구(句)일 때', 위키 3000040050.md 산문).
- 신고 명사: '상관없는 글' = **근거 글이 남의 이야기**. 주장 값(sel.waitlist)이 틀린 게 아니라 그 글이 이 학원 글이 아니다 → claim 이 아니라 relevance.
- 이 사례의 글: https://cafe.naver.com/mom79/1161785 '학원에서 일어난 일입니다.(학폭 관련 질문)' — 초2 아이가 학원에서 맞은 학폭 상담글. 진입난이도 '대기' 근거가 될 자리가 없다. 8/30 산출물(935e05d9a) selectivityEvidence 에 claimId 1562b04c5e196b82 로 실려 있었고, 8/31 산출물(ba10cd4fa)부터 빠졌다.
- 같은 학원의 같은 원인 사례: cd-538cfb43(학원 인수·양도 글, sel.full) · cd-ef661f28(청라 스터디 카페 홍보글, sel.test_exists) · cd-0f8817c9(천안 불당동 동명 학원 — 구 + 타지역 동, sel.test_exists). 넷 다 8/30 산출물의 네 주장이고 신고일이 같다(8/31).
- 채점 대상 여부: academies.json 에 있다(subjects [general] · notRanked '과목 미상' · 표본 0 · selectivity null · selectivityEvidence 0, 8c39e4ea8). 표본 이력(커밋별): 8/30 166 → 8/31 20(근거 5) → 9/3 24 → 9/4 **0** → 9/5 0.
- 재현(현재 코드): 후보 = name_candidates − weak_candidates = {'새로운학원'}('새로운' 은 weak), generic=True. 네 인용문을 '새로운 학원'(띄어씀) 이 든 글로 재구성해 `analyze.is_relevant` 에 넣으면 **전부 False**(generic=False 면 True — 옛 경로). 픽스처 문장('레벨테스트란? … 새로운 학원 상담이') 도 False. 붙여 쓴 글은 표지가 곁에 있을 때만 True 인데, 위키 `unusable` 이 `wiki.apply_gate`(wiki.py:183-197) 에서 이 학원의 글을 전부 버리고(재현: kept 0 · dropped 1) build.py:1112 가 수집 대상에서도 뺀다 → 표본 0 이 정직한 상태다.

- 이미 고침 — 커밋 2d6f39205 (2026-09-04 18:25 KST, `analyze.trade_seam` · `_marker_near` 자리 전부 가림 · `foreign_dong`) + 8/31 7f6ca1049 (`GENERIC_NAME_PARTS` '새로운', analyze.py:310) + 위키 `pipeline/wiki/academies/3000040050.md` frontmatter `generic: true` · `unusable: true` · 픽스처 `pipeline/tests/cases/hist-2026-09-03-saeroun-phrase.yaml` (tests/test_cases.py 46 passed).
- 데이터에도 반영됨(data_lag 아님): 9/4 dd27c73b0 부터 표본 0 · selectivityEvidence 0, 현재 8c39e4ea8(9/5) 동일. 2d6f39205 는 9/3 데이터(3007660a9)에는 없고 9/4 데이터(dd27c73b0)에 들어 있다(`git merge-base --is-ancestor`).
- 남은 일: Supabase claim_disputes 는 운영자가 /admin 에서 판정(에이전트는 쓰지 않는다). 사례 frontmatter `source_status: open` 그대로.
- 담당: gate-relevance (조치할 코드 없음 — 확인·닫기만). 예상 조치층: none(이미 code+wiki+fixture).


## 조치
(담당 gate-* 에이전트가 쓴다 — 무엇을 어느 층(판정·위키·규칙·코드)에 바꿨는지, 같은 원인의 다른 학원은 몇 곳인지, 픽스처 경로)

## 확인


### 2026-09-08
- 수정 커밋 실재: 7f6ca1049 (08-31 22:31 KST, `GENERIC_NAME_PARTS` '새로운') · 2d6f39205 (09-04 18:25 KST, `trade_seam` · `_marker_near` 전부 가림 · `foreign_dong`). 2d6f39205 ⊄ 3007660a9(9/3 데이터) · ⊂ dd27c73b0(9/4, 첫 반영) · ⊂ 8c39e4ea8 · ⊂ 0c2e61f3f (`git merge-base --is-ancestor`).
- 위키: pipeline/wiki/academies/3000040050.md frontmatter `generic: true` · `unusable: true` 확인.
- 픽스처: tests/cases/hist-2026-09-03-saeroun-phrase.yaml 존재. `pytest tests/test_cases.py -k "daegi or jeongsang or saeroun"` 4 passed · test_cases.py 전체 17 passed.
- 야간 산출물(캐시 아님): origin/main 마지막 데이터 커밋 **0c2e61f3f** (09-07 22:25 UTC, run 34164667543; 진단이 본 8c39e4ea8 보다 3회차 뒤). 3000040050: 표본 **0** · notRanked '과목 미상' · subjects [general] · selectivityEvidence 0 · evidence 0 · claim_id 1562b04c5e196b82 0건 · '학폭' 0건 (학폭·싸대기·인수하기·스터디카페·청라·불당동 전부 0). 8c39e4ea8 동일. 표본 이력(회차별): 8/29 168 → 8/30 166 → 8/31 20(7f6ca1049) → 9/3 24 → 9/4 **0**(dd27c73b0) → 9/5 0(notRanked 부터) → 9/7 0.
- 야간 로그(09-07): '일상어 이름 학원 12곳' 줄에 `새로운학원(mokdong) 표본 0 · 순위 밖` · 글 노드 이탈에 새로운학원 235장(unusable 게이트가 전부 버림 — 의도된 결과) · 지점 게이트 '목록에 없는 동 828건 제외'(foreign_dong 작동) · 전수 점검 5,337곳 고유 ✓ · 관련성 게이트 169,057 → 27,074 · 범위 감사 오분류 0·단계⊄구간 25·구간 모름 702·과목 미상 268 · 근거 품질 2,112/2,113 · deploy workflow_run 연쇄 성공(0c2e61f3f).
- 반대쪽: 목동 순위권 44(9/3) → 47(9/4) → 50(9/7) · 전체 154 → 159 → 177. 잃은 곳 없음.
- pytest(작업 트리 코드 — build.py 미커밋 수정 47줄 포함): **280 passed · 1 failed** tests/test_selection.py::test_순위권은_주기가_지났을_때만_다시_보고_그_자리를_안_본_곳에_준다. 원인: `monkeypatch.setattr(coverage, "date", …, raising=False)` 가 무효 — coverage 모듈에 `date` 이름이 없고 days_since 가 함수 안에서 import 해 실제 오늘을 쓴다. recent 의 last_at 2026-09-01 이 09-08 에 정확히 REFRESH_DAYS(7) 이라 오늘부터 깨짐(datetime.date 를 09-02 로 고정하고 같은 함수를 부르면 통과 — 증명함). 이 사례와 무관.
- **status 보류(triaged 유지)**: 규칙 '테스트가 하나라도 실패한 채 verified 로 올리지 않는다'. selection 담당이 테스트 모의(`datetime.date` 또는 `days_since(today=)`)를 고쳐 녹색이 되면 그대로 `status: verified` 로 올릴 것 — 아래 확인은 전부 끝났고 resolution·fixture·landed_in 은 채워 두었다.
- ★ tests/cases/*.yaml · tests/test_cases.py · edutree/cases.py · wiki/cases/ 는 아직 **미커밋(untracked)**. 커밋 전에는 이 기계에만 있는 회귀망이다.
- Supabase claim_disputes 는 건드리지 않음(운영자 /admin).

### 2026-09-08
- 선정 테스트의 달력 의존(test_selection.py, coverage.days_since 모의)을 고쳐 전부 통과 → verified · landed_in 0c2e61f3f(9/7 야간)

