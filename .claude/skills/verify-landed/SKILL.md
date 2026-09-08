---
name: verify-landed
description: 고친 것이 실제 사이트 데이터·배포에 반영됐는지 확인한다 — 수정 커밋과 마지막 야간 데이터 커밋의 선후, origin/main 산출물에서 신고 학원의 값, 배포 연쇄 여부. 신고를 닫기 전에, 또는 '고쳤는데 그대로다' 는 말을 들었을 때 쓴다.
---

# 반영 확인

코드 수정과 데이터 반영은 **다른 사건**이다. 야간 워크플로는 기본 브랜치에서
돌고, 수정이 main 에 들어온 시각이 마지막 갱신보다 늦으면 한 회차를 통째로
기다린다(실측 3시간 반 차이로 다음 날까지 옛 데이터). 앱 수정은 데이터가 아니라
**배포**다 — 봇 커밋은 push 트리거를 못 깨우므로 `workflow_run` 연쇄가 붙는다.

## 절차

```bash
git fetch origin main
# 1) 수정이 main 에 있나
git log origin/main --oneline -5 -- pipeline/edutree app/lib
# 2) 마지막 데이터 커밋이 수정 **뒤**인가
git log origin/main -3 --format='%h %ci %s' -- app/assets/data
# 3) 산출물에서 신고 학원의 값
git show origin/main:app/assets/data/academies.json | jq -c '.[] | select(.id=="<id>") | {displayName, subjects, gradeBands, sample: .score.sampleSize, total: .score.total, rank: .score.rankInRegion, notRanked}'
# 4) 배포가 붙었나 (수집 성공 → deploy workflow_run)
gh run list --workflow=deploy.yml --limit 3
gh run list --workflow=collect.yml --limit 3
```

- 데이터 커밋이 수정보다 **이르면** 아직 반영 전이다. 사례는 `fixed` 로 두고
  `## 확인` 에 '야간 대기(데이터 커밋 <sha> 는 수정 이전)' 이라 적는다.
- 반영됐으면 사례 `status: verified`, `landed_in: <데이터 커밋 sha>`.
  ```bash
  cd pipeline && ../.venv/bin/python -c "from edutree import cases; cases.set_fields('<id>', status='verified', landed_in='<sha>')"
  ```
- 반영됐는데 값이 그대로면 **증상만 고친 것**이다 — 사례를 `triaged` 로 되돌리고
  `## 진단` 에 '원인 재검토' 를 적어 case-triage 부터 다시.
- 화면이 그대로라는 말이 오면 서비스워커 캐시부터 의심한다(`index.html` 이
  매 로드 등록 해제하지만, 옛 탭은 새로고침이 필요하다).
