---
name: triage-reports
description: 웹에서 들어온 신고(정정 요청·'이 학원 글이 아니에요'·주장 이의)를 사례 대장으로 가져와 진단 → 조치 → 회귀 픽스처 → 검증까지 프로젝트 에이전트로 처리한다. "신고 처리해줘", "사례 대장 돌려줘", "/triage-reports" 에 쓴다.
---

# 신고 처리 — 사례 대장 한 바퀴

웹의 신고 한 건이 **분류 시스템의 개선 한 건**이 되게 하는 절차다. 글 하나를
바로잡는 데서 끝내지 않는다 — 같은 종류가 다시 오지 않도록 규칙·위키·코드에
반영하고, 그 반영을 픽스처로 굳힌다. 대장은 `pipeline/wiki/cases/`, 픽스처는
`pipeline/tests/cases/`, 에이전트는 `.claude/agents/`.

## 절차

1. **접수를 가져온다.**
   ```bash
   .venv/bin/python pipeline/run.py --cases
   ```
   Supabase 키(`.env`)가 있어야 새 접수가 온다. 없으면 파일에 있는 사례만 본다.
   출력의 `[id] 학원 · 사유 · 날짜 · 상태` 줄이 이번에 다룰 목록이다.
   `!` 줄은 감사 경고(오래 열림 · 픽스처 없음 · 근거 없는 verified)다 — 먼저 읽는다.

2. **한 회차 상한 12건.** 질문 큐와 같은 이유다 — 많으면 다시 노동이 된다.
   오래된 것부터, 같은 학원·같은 사유는 묶는다.

3. **진단.** 열린(`open`) 사례마다 `case-triage` 에이전트를 부른다. 프롬프트에는
   사례 파일 경로만 준다. 에이전트가 `category` 와 담당을 `## 진단` 에 적고
   `status: triaged` 로 올린다. **같은 category 로 모인 사례는 담당 에이전트에
   한꺼번에 보낸다** — 신고는 한 곳으로 오지만 원인은 낱말이라 전수로 넓혀야 한다.

4. **조치.** category → 담당:

   | category | 담당 | 조치 층 |
   |---|---|---|
   | relevance | `gate-relevance` | post 판정 → 위키 힌트 → 코드 + 테스트 |
   | branch | `gate-branch` | 시드 brand/alias → 위키 locality → 코드 |
   | subject | `gate-subject` | 시드 과목 → 코드(이음매·힌트) |
   | merge | `gate-merge` | 시드 alias → 위키 moved_to → 코드 |
   | claim | `gate-claims` | claim_verdicts → 코드 |
   | score | `score-audit` | 제안만 (가중치는 사람이 SPEC 과 함께) |
   | display | `app-reviewer` | app/ 코드 + 위젯 테스트 |
   | coverage | `gate-relevance` 에 '선정' 을 명시 | 시드 등록·수요 신호·`select_for_mentions` |
   | data_lag | 고치지 않는다 | `pipeline-verifier` 가 야간 반영을 확인 |
   | other | 사람 | 사례에 질문을 적고 멈춘다 |

   담당 에이전트는 `## 조치` 를 쓰고 픽스처를 남기고 `status: fixed` 로 올린다.
   위키에 적을 것이 생기면 `wiki-curator` 에 넘긴다.

5. **검증.** `fixed` 가 된 사례마다 `pipeline-verifier` 를 부른다. 테스트 전부
   통과 + `--from-cache` 재채점 + 신고 학원 전후 + **반대쪽**(잃은 근거) 확인.
   캐시 수치는 캐시라고 적는다. 야간 산출물 확인은 다음 날 `/verify-landed`.

6. **사람에게 돌려줄 것을 고른다.** 규칙 판정(crawl_rules)·가중치·형제 지점 확인
   (공식 지점 목록) 처럼 사람이 정할 것은 사례 `## 조치` 에 **질문 형태**로 적고
   `status: triaged` 에 둔다. 에이전트가 대신 정하지 않는다.

7. **보고.** 사례 id · 종류 · 조치 층 · 픽스처 · 잃은 근거 여부 · 사람 결정
   대기 항목을 표로. 커밋은 사용자가 요청할 때만 한다.

## 지킬 것

- 사례 파일의 `<!-- auto:report -->` 안과 위키 `auto:*` 블록은 손대지 않는다.
- 증상을 고치고 원인을 안 고치면 신고가 다시 온다 — 신고 문장에서 **명사**를 고른다.
- 조용히 표본이 0 이 되는 수정은 반드시 본문을 열어 본 뒤에만.
- `--from-cache` 는 `OPENEDU_CLAIM_LLM_LIMIT=0 OPENEDU_SUMMARY_PER_RUN=0` 을 붙인다.
- 고친 것은 **다음 야간 산출물**로 확인한다(`git log -- app/assets/data`).
