# 분류 에이전트와 사례 대장 — 신고가 시스템을 키우는 구조 (2026-09-07)

이 문서는 **운영 절차**다. 어떤 신고가 어디로 들어와 무엇이 되어 나가는지,
그 사이에서 Claude Code 의 프로젝트 에이전트가 무엇을 맡는지 적는다.
산식은 `SPEC.md`, 데이터 출처는 `DATA.md`, 반복해서 틀렸던 것은 `CLAUDE.md`.

## 왜 에이전트를 나눴나

후기를 학원에 잇는 일은 하나의 문제가 아니라 **여섯 개의 다른 문제**였다.
CLAUDE.md 의 이력을 보면 같은 증상('근거가 남의 이야기다')에 원인이 게이트·
지점·통합·과목·주장·화면으로 갈리고, 한 원인을 고칠 때마다 반대쪽이 무너졌다.
한 사람(한 에이전트)이 전부를 들고 있으면 매번 처음부터 다시 배운다.

그래서 **문제의 종류마다 담당을 두고, 그 담당의 프롬프트에 그 영역의 이력을
전부 넣었다.** 에이전트 파일은 `.claude/agents/`, 각 파일의 '판정표' 절이
CLAUDE.md 에서 그 영역의 교훈만 추린 것이다. 이력이 늘면 그 절도 는다.

| 에이전트 | 맡는 신고 | 담당 코드 | 고치는가 |
|---|---|---|---|
| `case-triage` | 모든 신고의 첫 판정 — 어느 층인가 | (읽기만) | ✗ 진단만 |
| `gate-relevance` | 근거 글이 남의 이야기(이름·일상어·나열글) | `analyze.py` `nameaudit.py` `evidence.py` | ○ |
| `gate-branch` | 다른 지점·다른 동네 글 | `branches.py` `regions.yaml` 시드 brand | ○ |
| `gate-subject` | 엉뚱한 과목·학년 랭킹 | `build._infer_*` `_subject_text` 단계 매핑 | ○ |
| `gate-merge` | 중복으로 보임 / 남남이 합쳐짐 | `dedupe.py` `assign_display_names` `graph.py` | ○ |
| `gate-claims` | 난이도·사실 카드 값 | `claims.py` `claim_llm.py` | ○ |
| `score-audit` | 점수·등수 자체 | `scoring.py` `SPEC §4` | △ 제안만 |
| `wiki-curator` | 위키 힌트·글 판정·개념 페이지·사례 파일 | `pipeline/wiki/` | ○ 규약대로 |
| `app-reviewer` | 화면(표시 계층·모바일·다크·디자인 언어) | `app/` | ○ |
| `pipeline-verifier` | 고친 것이 먹었는가 | (읽기만) | ✗ 검증만 |

원칙 셋.
1. **진단과 조치를 가른다.** case-triage 는 고치지 않고, gate-* 는 자기 영역
   밖을 고치지 않는다. '순위가 이상하다' 가 바로 산식으로 가지 않고 수집 대상 →
   데이터 지연 → 과목 → 이름 순으로 걸러지는 것이 이 구조의 이유다.
2. **사람이 정할 것은 에이전트가 정하지 않는다.** 가중치(score-audit), 크롤 규칙
   판정(질문 큐), 형제 지점 확인(공식 목록), 위키 `unusable`. 에이전트는
   질문 형태로 남긴다.
3. **고친 것은 픽스처가 된다.** 아래 참고.

## 사례 대장 — 신고 한 건이 개선 한 건이 되는 길

```
 앱 (로그인 불요)                          Supabase
   정정 요청 ────────────────────────────▶ corrections
   '이 학원 글이 아니에요' ─────────────▶ evidence_reports ──▶ (질문 큐 맨 앞, 기존 경로)
   주장 '이의' ─────────────────────────▶ claim_disputes
                                              │
      야간 collect.yml  ──  run.py --cases ───┘   접수 → pipeline/wiki/cases/<id>.md (open)
                                                  파일은 wiki 와 함께 커밋된다
                                              │
      운영자 · Claude Code  /triage-reports   │
        case-triage ───────── 진단 ──────────▶ status: triaged · category
        gate-* / app-reviewer ─ 조치 ────────▶ status: fixed · resolution · fixture
          ├ 판정   posts/<hash>.md · claim_verdicts        (글 하나)
          ├ 위키   academies/<id>.md frontmatter            (학원 하나)
          ├ 규칙   crawl_rules — 질문 큐 경로로만           (사람 판정)
          └ 코드   analyze/branches/build/dedupe/claims + 회귀 테스트 (낱말·패턴)
        ★ 어느 층이든 tests/cases/<id>.yaml 픽스처를 남긴다
        pipeline-verifier ─── 검증 ─────────▶ status: verified · landed_in (야간 커밋 뒤)
                                              │
      매 야간 실행                             │
        run.py → 사례 대장 요약 + 감사 ◀──────┘  오래 열림 · 픽스처 없는 fixed · 근거 없는 verified
        pytest → tests/cases/*.yaml 전부      깨지면 그 신고의 원인이 되살아난 것
```

### 왜 픽스처인가

판정·위키·규칙은 **그 글, 그 학원**을 바로잡는다. 같은 종류가 다른 학원에서
다시 오면 처음부터다. 픽스처는 신고의 원문과 등록값을 그대로 두고 "그 글이 그
학원의 근거인가" 만 묻는다 — 규칙이 어떻게 바뀌든 질문은 변하지 않으므로,
어느 날 누가 게이트를 느슨하게 고치면 그날 테스트가 그 신고를 다시 꺼낸다.
`cases.audit()` 이 픽스처 없는 `fixed` 를 매 실행 경고하는 이유다.

이력에서 골라 둔 첫 픽스처 일곱 장이 `pipeline/tests/cases/hist-*.yaml` 이다
(캔비→폴리 오귀속, '새로운 학원' 구, 로드맵학원 반대쪽, 실용외국어→국어,
정상수학≠정상어학원, 대치학원 알맹이 없음, 세종 글의 지점). 형식은 그 디렉터리의
`README.md`.

### 상태 기계

    open ─▶ triaged ─▶ fixed ─▶ verified ─▶ closed
                 └──────────▶ declined      (신고가 틀렸거나 정책상 안 고침 — 사유를 산문에)

`category` 는 `cases.CATEGORIES` 열 가지, `resolution` 은 post·wiki·rule·code·
fixture·data·none 의 목록. `set_fields` 가 없는 값을 거부한다 — 오타가 조용히
새 상태가 되면 안 된다.

## 명령

```bash
.venv/bin/python pipeline/run.py --cases        # 접수 → 사례 파일, 대장·감사 출력
cd pipeline && ../.venv/bin/python -m pytest -q  # 사례 픽스처 포함 전부
OPENEDU_CLAIM_LLM_LIMIT=0 OPENEDU_SUMMARY_PER_RUN=0 .venv/bin/python pipeline/run.py --from-cache   # 재채점(캐시)
```

Claude Code 스킬(`.claude/skills/`):

| 스킬 | 쓰임 |
|---|---|
| `/triage-reports` | 대장 한 바퀴 — 접수 → 진단 → 조치 → 검증 → 보고 (회차 상한 12건) |
| `/file-case` | 말로 받은 신고를 사례로 적고 바로 진단으로 |
| `/rescore` | `--from-cache` 재채점과 로그에서 읽을 감사 줄 |
| `/verify-landed` | 수정 커밋과 데이터 커밋의 선후, origin/main 산출물, 배포 연쇄 |

## 하네스는 정품이다

Claude Code 의 기본 기능만 쓴다 — 프로젝트 `.claude/agents/*.md`(서브에이전트),
`.claude/skills/*/SKILL.md`(슬래시 명령), `.claude/settings.json`(공용 권한).
전역 `~/.claude` 의 서드파티 스킬·플러그인은 2026-09-07 에 백업으로 옮겼다
(`~/.claude/backups/harness-2026-09-07/`). 프로젝트 수준의 에이전트가 곧 이
저장소의 운영 절차이므로 **커밋한다**(`.gitignore` 가 세션 로컬 상태만 뺀다).

## 교재(textbook)로 넓힐 때

사례 대장·픽스처·에이전트는 `entity_type` 을 갖는다. 후기를 이름으로 잇는
문제는 교재도 같고 — '최상위수학' 은 학원 이름이자 문제집 이름이었다 —
그래서 같은 게이트와 같은 대장을 쓴다. 설계는 `TEXTBOOKS_DESIGN.md`.
