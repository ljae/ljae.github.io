---
id: cd-d21e3add
source: claim_dispute
source_id: d21e3add-aa61-48cb-b152-18fe1d0a1ead
source_status: open
entity_type: academy
entity_key: "1000036728"
entity_name: 대치청담어학학원
reported_at: 2026-08-30
reason: other
claim_id: bfe86c6221551978
claim_kind: sel.waitlist
# ↓ 상태 기계. 에이전트·사람이 바꾼다. 엔진은 요약·감사에만 읽는다.
status: verified              # open → triaged → fixed → verified → closed | declined
category: relevance
resolution: [code, fixture]            # post | wiki | rule | code | fixture | data | none
fixture: tests/cases/cd-d21e3add.yaml
landed_in: 0c2e61f3f
---
# 대치청담어학학원 — 기타

## 신고
<!-- auto:report -->
- 주장 종류: sel.waitlist
- 인용문: ▶상가임대 사무실임대 기본 현황◀
- 내용:
  > 부동산 상가 임대 글입니다. 전혀 관련없는 글입니다.
<!-- /auto:report -->

## 진단


### 2026-09-08
- 종류: relevance — 광고(업소 명부·부동산). 두 글자 별칭 '청담' 이 '청담동'·'청담신사(상가전문 상호)' 에 걸려 글이 통과했고, 그 안에서 '사무실임대 기본' → flat '임대**기본**' 의 '대기' 가 `sel.waitlist` 가 됐다. 두 겹이다.
- 원문: https://blog.naver.com/carshop0802/222851987127 — 제목 '[강남 대치동 대로변 학원 병원 2층임대]강남 대치동 학원밀집지역 ....'(2022-08-18, url_hash 1b9eec241474dfd42e27d68603617222). `.cache/blog_texts.json` 본문 1,822자에 '청담' 6곳 전부 '청담신사'·'청담동' — 학원 표지가 곁에 없다. 제목의 '대치동' 때문에 '글이 이 권역을 밝힘' 으로 1000036728 에 직접 붙었다(위키 posts/1b9eec24….md auto:edges).
- 이미 고침 — 커밋 · 픽스처:
  1. 관련성: `analyze._short_ok`(analyze.py:485, 커밋 dc810da8b 2026-09-02) — 두 글자 이름은 곁에 학원 표지가 있을 때만. 재현: 현재 코드로 `is_relevant` = **False**(API 스니펫·블로그 본문 모두 name_spans 0). 회귀: tests/test_relevance.py:42 ('청담동 카페' → 0).
  2. 주장: `claims._contiguous`(claims.py:493, 커밋 e36d7f469 2026-08-29 23:02) — 재현: flat 462자리 '임대기본' contiguous=False, 본문 전체에 주장 0건. 픽스처 hist-2026-08-29-daegi-contiguous.yaml('8대 기능성').
  - 데이터: 인용문은 8/29 데이터(b44721bd4)에 들어가 8/30 데이터(56ebeb55b 09:52Z)에서 빠졌다. 신고일 8/30 은 그 사이 — 당시엔 data_lag 였다. 지금 HEAD(8c39e4ea8 9/5)·origin/main(0c2e61f3f 9/7) 어느 쪽 selectivityEvidence·evidence 에도 없다.
- 남은 것: 이 원문으로 굳힌 relevance 픽스처가 없다(기존 것은 '청담동 카페' 한 줄). 위키 posts/1b9eec24….md 는 드리프트로 남아 있다(posts_drifted 4,704건 중 하나) — 정상이며 조치 불요. 주장 bfe86c6221551978 은 산출물에 없으니 Supabase 이의는 '이미 고침' 으로 닫으면 된다(사람이).
- 담당: gate-relevance (픽스처만) · 원인 코드 변경 없음
- 픽스처 초안(tests/cases/cd-d21e3add.yaml, 원문 그대로):
  ```yaml
  case: cd-d21e3add
  entity_type: academy
  kind: relevance
  why: |
    두 글자 별칭 '청담' 이 '청담동'·'청담신사 상가전문' 에 걸려 대치동 상가 임대 광고가
    대치청담어학학원 근거가 됐고, '사무실임대 기본' 의 '임대기본' 이 대기·웨이팅 사건이 됐다.
    _short_ok(9/2) 가 글을 버리고 _contiguous(8/29) 가 사건을 버린다.
  academy: {name: 대치청담어학학원, brand: 청담어학원, aliases: [청담], region_id: daechi}
  mention:
    title: "[강남 대치동 대로변 학원 병원 2층임대]강남 대치동 학원밀집지역 ...."
    snippet: "청담신사 상가전문입니다. 강남대치동 학원임대 학원밀집지역 대로변 학원임대 대치사거리 학원임대... 대치동 영어학원 대치동 수학학원 대치동 보습학원 대치동 병원임대 건물컨디션 최상급 노출효과..."
  expect: {relevant: false}
  ```
  (claim 쪽은 같은 제목에 본문 '▶상가임대 사무실임대 기본 현황◀ ◆위치: 강남구 청담동' 을 넣고 `claim_kinds_exclude: [sel.waitlist]` 로 한 장 더 둘 수 있다.)


## 조치


### 2026-09-08
- 재현(HEAD 348a07e33, 2026-09-08): 후보 6개(대치청담어학·대치청담어학학원·청담·청담어학·청담어학원·청담어학학원), 일상어 아님. 진단의 초안 스니펫·`.cache/blog_texts.json` 본문 1,822자·앞머리 300자·인용 구간(524~780자) 전부 `name_spans` **0 → is_relevant False**. `claims.extract` 0건 — 이름을 인용문 곁에 강제로 두어도 sel.waitlist 0건. 두 겹(`analyze._short_ok` dc810da8b · `claims._contiguous` e36d7f469)이 이미 막고 있다.
- 조치 층: **픽스처만.** 코드·위키·규칙·판정 변경 없음. 진단의 '데이터 지연' 판단 그대로(신고일 8/30 은 8/29 데이터와 8/30 데이터 사이).
- 픽스처 3장(원문 그대로, 블로그 본문에서 자름):
  - `tests/cases/cd-d21e3add.yaml` — relevance, 본문 앞머리('청담신사 상가전문입니다' + 학원임대 나열) → relevant false
  - `tests/cases/cd-d21e3add-real.yaml` — 반대쪽. '청담어학원 레테 후기' + '청담 레테 봤어요' → relevant true (두 글자 호칭을 길이로 자르지 않는다는 경계)
  - `tests/cases/cd-d21e3add-claim.yaml` — claim, 신고자가 본 인용문 '▶상가임대 사무실임대 기본 현황◀' 구간 → sel.waitlist 없음
- 같은 원인의 노출(캐시 수치, `app/assets/data/academies.json` 채점 대상 1,159곳): 두 글자 별칭 보유 18곳 — 정상 5 · 청담 4 · 띵킹 2 · 시대 2 · 폴리 2 · 강대·필즈·소마 1. '청담' 은 대치청담어학학원·서초청담어학원·청담어학원 2곳. `_short_ok` 는 전역 규칙이라 신고 학원만이 아니라 18곳 전부 같은 문턱을 지난다.
- 테스트: `tests/test_cases.py` 20 passed(17 → 20), 전체 284 passed. `--from-cache` 는 돌리지 않았다 — 코드 변경이 없어 캐시 수치가 달라질 것이 없다. 야간 산출물 확인은 pipeline-verifier 몫.
- Supabase 는 쓰지 않았다. 이의 `claim_disputes` d21e3add-aa61-… 는 **운영자가 /admin 에서 '이미 고침' 으로 닫는다.** 주장 bfe86c6221551978 은 8/30 데이터(56ebeb55b)부터 산출물에 없다. 위키 `posts/1b9eec24….md` 는 드리프트로 남는 것이 정상(조치 불요).


## 확인


### 2026-09-08
- case-triage 재현: 9/7 야간 산출물(0c2e61f3f)에 인용문 없음 · 두 겹(_short_ok dc810da8b · _contiguous e36d7f469) 모두 데이터 커밋 안 → verified

