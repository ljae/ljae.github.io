---
name: rescore
description: API 호출 없이 캐시·저장소로 파이프라인을 다시 돌려(--from-cache) 산식·게이트 변경의 효과를 잰다. 로그에서 읽어야 할 감사 줄과, 캐시 수치를 야간 수치처럼 적지 않는 규칙을 포함한다. "재채점해줘", "from-cache 돌려줘" 에 쓴다.
---

# 캐시 재채점

```bash
cd /Volumes/ORICO/open_edu
OPENEDU_CLAIM_LLM_LIMIT=0 OPENEDU_SUMMARY_PER_RUN=0 \
  .venv/bin/python pipeline/run.py --from-cache 2>&1 | tee "$CLAUDE_JOB_DIR/tmp/rescore.log"
```

- `.venv`(3.12)로 돈다. `/usr/bin/python3` 는 3.9 라 요약만 꺼진다.
- **LLM 을 끈다.** `--from-cache` 도 사실 추출을 부르고, 키를 비워도
  `GOOGLE_API_KEY` 폴백이 잡힌다.
- 캐시 실행은 수집 시도가 아니다 — coverage·저장소를 **쓰지 않는다.**
  키 없는 환경에서 산출물이 0KB 로 덮이지 않는지(`_would_erase`) 본다.

## 로그에서 읽을 줄 (전부 있어야 한다)

    전수 점검: N곳 모두 고유 ✓          id 유일
    관련성 게이트: A → B건               게이트 통과율. 크게 움직이면 이유를 적는다
    지점 게이트: …                        타권역·형제·지역 불명·목록에 없는 동
    ! 이름만으로 못 가려내는 학원 N곳     알맹이 없는 이름(표본 0)
    일상어 이름 학원 줄(이름·표본·순위)   조였는데 퍼지면 조이는 것이 안 먹는다
    범위 감사: 과목 오분류 · 단계 ⊄ 구간 · 구간 모름 · 과목 미상
    실효 기여 (기둥별 n) · 저울 쏠림      가중치 × σ. 가벼운 기둥이 무거운 기둥을 이기면 경고
    근거 품질 (spacedName)                발췌에 이름 포함 — 만점이면 재고 있는 것이 아니다
    ! 위키: · ! 글 노드: · 결합 재검증     힌트 모순 · 이탈 · 통합 정당성
    사례 대장: … · ! 사례:                 열린 신고 · 픽스처 없는 fixed

## 전후 비교

```bash
for f in <(git show HEAD:app/assets/data/academies.json) app/assets/data/academies.json; do
  jq -c '[.[] | select(.score.isRanked)] | length' "$f"; done      # 순위 진입 수
jq -c '.[] | select(.id=="<id>") | {displayName, subjects, gradeBands, sample: .score.sampleSize, total: .score.total, rank: .score.rankInRegion}' app/assets/data/academies.json
```

**반대쪽을 본다** — 규칙을 조이면 잃는 근거가 생긴다. 순위 진입 수·해당 과목
순위권 수의 전후를 함께 적는다.

## 적을 때

숫자 옆에 **(캐시)** 를 붙인다. '해결됐다' 는 다음 야간 산출물
(`git log -- app/assets/data`, `/verify-landed`)에서만 쓴다. "166 → 0" 이
캐시 수치였고 야간에 20 이 남았던 것이 이 규칙의 유래다.
