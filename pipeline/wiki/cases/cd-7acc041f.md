---
id: cd-7acc041f
source: claim_dispute
source_id: 7acc041f-05a7-494f-99e3-094ba3b32170
source_status: open
entity_type: academy
entity_key: "1000035161"
entity_name: 대치1관정상어학원
reported_at: 2026-08-29
reason: other
claim_id: 5829ef7990b313fe
claim_kind: sel.waitlist
# ↓ 상태 기계. 에이전트·사람이 바꾼다. 엔진은 요약·감사에만 읽는다.
status: verified              # open → triaged → fixed → verified → closed | declined
category: relevance
resolution: [code, fixture]            # post | wiki | rule | code | fixture | data | none
fixture: tests/cases/hist-2026-08-29-daegi-contiguous.yaml
landed_in: 0c2e61f3f
---
# 대치1관정상어학원 — 기타

## 신고
<!-- auto:report -->
- 주장 종류: sel.waitlist
- 인용문: 하이뮨 프로틴 밸런스 주니어 과학적인 8대 기능성 영양설계 뼈와 근육건강:단백질 칼슘 비타민D 정상적인 면역기능, 에너지: 아연.
- 내용:
  > 영양재 글 입니다. 전혀 상관없는 글입니다.
<!-- /auto:report -->

## 진단


### 2026-09-07
- 종류: relevance — 일상어 별칭('정상'). 부수: claim — 사건 낱말이 공백을 넘어 생김('8대 기능성' → '대기').
- 학원: 채점 대상이다. academies.json 1000035161 · 대치 · english · 표본 66 · 대치 영어 5위/15 · notRanked 없음. registry 에만 있는 것이 아니다.
- 근거(이의 인용문): '하이뮨 프로틴 밸런스 주니어 과학적인 8대 기능성 … 정상적인 면역기능' 이 sel.waitlist(대기·웨이팅) 근거였다. 두 겹이다.
  1. 글이 들어온 경위: 시드 별칭 `정상`(seed_academies.yaml) 이 '정상적인' 에 걸렸다. 이름은 멀쩡하고 별칭만 일상어라 아무 문턱이 없었다. 지역을 안 밝힌 글이라 다섯 지점(대치·목동·서초·잠실·송파)에 함께 붙었다(커밋 본문 실측: 대치 76·서초 153·잠실 92·송파 122건).
  2. 사건이 생긴 경위: `flat` 이 공백을 지워 '8대 기능성' → '8대기능성' → '대기'. 건강식품 광고가 진입난이도 사건이 됐다.
  3. 신고 시점(08-29)에는 통합 오류도 겹쳐 있었다 — `대치정상수학학원`(11410) 이 이 id 에 묶여 있어 수학관 쪽 글까지 이 학원 근거였다.
- 이미 고침 — 커밋 e36d7f469 (2026-08-29 23:02 KST): `analyze.EVERYDAY_ALIASES = ("정상",)` (analyze.py:451, `weak_candidates` :461) · `claims._contiguous` (claims.py:493, 사용 :533). 통합 오류는 커밋 8ff69b379 (2026-08-30): `dedupe._SUFFIX_STRONG` 에서 과목어 제거 — 지금 11410 은 registry 에 math 로 따로 선다.
  픽스처: pipeline/tests/cases/hist-2026-08-29-daegi-contiguous.yaml (claim) · pipeline/tests/cases/hist-2026-08-30-jeongsang-merge.yaml (merge). `pytest tests/test_cases.py -k "daegi or jeongsang"` 3 passed (2026-09-07).
- 데이터 반영 확인(캐시 수치 아님): 마지막 데이터 커밋 8c39e4ea8 (2026-09-05 08:19 UTC) 은 수정 뒤다 → data_lag 아님. academies.json 의 이 학원 레코드에 '하이뮨'·'8대 기능성'·'인테리어'·'도배'·'바이오'·'SGEA'·'신규등록상담' 0건, 이의 7건 중 6건의 claim_id(5829ef79·78a2604b·0b4ac83f·234f42be·807868bc·ed2e1b6c) 0건. selectivityEvidence 6건은 전부 '레벨테스트 있음' 이고 인용문마다 '정상어학원' 이 들어 있다(wooblee700 2021 · neti840 2024 · ilovegodeok · bdmmkids · gangnamchild ×2). 진입난이도 45.0, 사건 {레벨테스트 있음: 6}.
- 같은 원인의 사례: cd-8d1d3886(같은 하이뮨 글, 다른 url) · cd-2dbd8101(인테리어 '정상인지' → sel.full) · cd-b070bbe1(바이오 오일) · cd-39c0e445('신규등록상담하면서 레벨테스트') · cd-0544f857(SGEA 파닉스 모집요강). 전부 별칭 '정상' 으로만 걸린 글이고 지금 산출물에 없다.
- 담당: gate-relevance(별칭) → gate-claims(_contiguous). 둘 다 코드로 끝났다.
- 남은 일: Supabase claim_disputes 7건은 source_status open 그대로(disputeRate null = claim_verdicts 없음). 운영자가 /admin 에서 판정한다(에이전트는 쓰지 않는다). 주장이 이미 사라져 판정은 기록용이다 — 결정적 id 라 같은 글이 다시 들어오면 그때 판정이 붙는다.


## 조치
(담당 gate-* 에이전트가 쓴다 — 무엇을 어느 층(판정·위키·규칙·코드)에 바꿨는지, 같은 원인의 다른 학원은 몇 곳인지, 픽스처 경로)

## 확인


### 2026-09-08
- 수정 커밋 실재: e36d7f469 (2026-08-29 23:02 KST, `analyze.EVERYDAY_ALIASES` '정상' · `claims._contiguous`) · 8ff69b379 (08-30 17:20 KST, hall_key 에서 과목어 제거 → 수학관 분리). 둘 다 첫 반영 데이터 커밋 56ebeb55b(08-30 09:52 UTC) 와 마지막 데이터 커밋 안(`git merge-base --is-ancestor` OK).
- 픽스처: tests/cases/hist-2026-08-29-daegi-contiguous.yaml · hist-2026-08-30-jeongsang-merge.yaml 존재. `pytest tests/test_cases.py -k "daegi or jeongsang or saeroun"` 4 passed · test_cases.py 전체 17 passed.
- 야간 산출물(캐시 아님): origin/main 마지막 데이터 커밋 **0c2e61f3f** (09-07 22:25 UTC, run 34164667543; 진단이 본 8c39e4ea8 보다 3회차 뒤, 마지막 코드 커밋 348a07e33 포함). 1000035161 레코드에 claim_id 5829ef7990b313fe **0건** · '하이뮨' **0건**. 이의 인용문 13종(하이뮨·8대 기능성·인테리어·도배·바이오·SGEA·신규등록상담·학폭·싸대기·인수·스터디카페·청라·불당동)·claimId 10종 전부 0건 — 8c39e4ea8·56ebeb55b 도 동일. selectivityEvidence 6건 전부 sel.test_exists(진입 46.2), 여섯 글 제목 모두 '정상어학원' 포함(인용문 자체에 이름 없는 2건도 제목은 '정상어학원 교육비, 셔틀…'·'…영어 정상어학원').
- 학원 살아 있음: english · 표본 70 · 대치 영어 11위/26 · isRanked true. 진단의 '5위/15 · 표본 66' 은 어느 회차와도 안 맞는다 — 실측 8/29 337(수학관 결합·6위/14) → 8/30 106(6위/15, 첫 반영) → 9/3 112(10위/24) → 9/5~9/7 70(11위/25~26). 9/5 감소는 '지점 불명 글은 근거 못 됨' 규칙(형제 지점 목동·서초·잠실·송파).
- 반대쪽: 대치 영어 순위권 14(8/29) → 15(8/30) → 26(9/7) · 전체 순위권 121 → 177. 잃은 곳 없음.
- 야간 로그(09-07): 전수 점검 5,337곳 고유 ✓ · 관련성 게이트 169,057 → 27,074 · 일상어 별칭 제외 12곳(정상) · 지점 게이트 지역 불명 3,108건 근거 제외·목록에 없는 동 828건 제외 · 범위 감사 오분류 0·단계⊄구간 25·구간 모름 702·과목 미상 268 · 실효 기여 sel 5.41(n=188)/rep 1.64(n=306)/trans 1.50/mom 1.33, 저울 쏠림 3.3배(9/3 이후 알려진 상태) · 근거 품질 2,112/2,113 · 위키 경고 6줄(이 학원 아님) · deploy workflow_run 연쇄 성공(headSha 0c2e61f3f).
- pytest(작업 트리 코드 — build.py 미커밋 수정 47줄 포함): **280 passed · 1 failed** tests/test_selection.py::test_순위권은_주기가_지났을_때만_다시_보고_그_자리를_안_본_곳에_준다. 원인: `monkeypatch.setattr(coverage, "date", …, raising=False)` 가 무효 — coverage 모듈에 `date` 이름이 없고 days_since 가 함수 안에서 import 해 실제 오늘을 쓴다. recent 의 last_at 2026-09-01 이 09-08 에 정확히 REFRESH_DAYS(7) 이라 오늘부터 깨짐(datetime.date 를 09-02 로 고정하고 같은 함수를 부르면 통과 — 증명함). 이 사례와 무관.
- **status 보류(triaged 유지)**: 규칙 '테스트가 하나라도 실패한 채 verified 로 올리지 않는다'. selection 담당이 테스트 모의(`datetime.date` 또는 `days_since(today=)`)를 고쳐 녹색이 되면 그대로 `status: verified` 로 올릴 것 — 아래 확인은 전부 끝났고 resolution·fixture·landed_in 은 채워 두었다.
- ★ tests/cases/*.yaml · tests/test_cases.py · edutree/cases.py · wiki/cases/ 는 아직 **미커밋(untracked)**. 커밋 전에는 이 기계에만 있는 회귀망이다.
- Supabase claim_disputes 는 건드리지 않음(운영자 /admin).

### 2026-09-08
- 선정 테스트의 달력 의존(test_selection.py, coverage.days_since 모의)을 고쳐 전부 통과 → verified · landed_in 0c2e61f3f(9/7 야간)

