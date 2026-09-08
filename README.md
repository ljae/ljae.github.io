# 에듀트리 (EduTree)

> 대치 · 목동 · 반포 · 잠실 학원 테크트리
> 운영: [Open Edu](https://openedu4u.com/openedu/)

학원 **목록**이 아니라 학원 사이의 **길**을 보여주는 서비스.
공공데이터로 사실을 검증하고, 커뮤니티 신호로 평판을 읽어
4개 학군의 진학 경로를 한 장의 그래프로 만듭니다.

```
openedu4u.com/          → 에듀트리 (Flutter Web)
openedu4u.com/openedu/  → 기존 Open Edu 사이트 (보존)
```

---

## 빠른 시작

```bash
# 1. 데이터 생성 (키가 없으면 샘플 데이터로 동작)
python3 pipeline/run.py

# 2. 앱 실행
cd app && flutter run -d chrome
```

실제 데이터로 전환하려면 → **[docs/SETUP.md](docs/SETUP.md)**

---

## 구조

| 경로 | 내용 |
|---|---|
| `app/` | Flutter 앱 — 웹 · iOS · Android 단일 코드베이스 |
| `pipeline/` | 수집 · 분석 · 채점 파이프라인 (Python) |
| `pipeline/data/techtree.yaml` | **테크트리 큐레이션 데이터 — 제품의 핵심** |
| `supabase/` | 스키마 · RLS · RPC |
| `openedu/` | 기존 Open Edu 정적 사이트 |
| `docs/SPEC.md` | 제품 사양 · 산식 정의 |
| `docs/SETUP.md` | API 키 발급 체크리스트 |
| `docs/AGENTS.md` | 분류 에이전트 · 사례 대장 운영 절차 |
| `.claude/agents/` · `.claude/skills/` | Claude Code 프로젝트 에이전트 · 슬래시 명령 (커밋 대상) |

---

## 트리스코어

```
TreeScore = 0.35·평판 + 0.20·화제성 + 0.25·투명성 + 0.20·진입난이도
```

산식은 서비스 안에서 전부 공개됩니다 (`/method` — 상단 메뉴가 아니라 첫 화면
'산식' 절의 링크에서 연다). 자세한 정의는
[docs/SPEC.md §4](docs/SPEC.md).

핵심 설계 두 가지:

- **베이지안 축소** — 모든 평판 점수를 같은 지역·과목 코호트 평균 쪽으로
  12건만큼 끌어당깁니다. 후기 3건짜리 학원이 1위로 튀지 않습니다.
- **최소 표본** — 유효 후기 10건 미만은 순위에서 제외하고 별도 목록으로
  보여줍니다. 적은 표본으로 등수를 매기는 건 그 학원에 부당하기 때문입니다.

---

## 데이터 출처

| 소스 | 역할 | 지위 |
|---|---|---|
| [NEIS 학원교습소정보](https://open.neis.go.kr) | 학원 원장 — 이름·주소·정원·교습비·등록상태 | 공공데이터 |
| [네이버 검색 오픈 API](https://developers.naver.com/docs/serviceapi/search/) | 카페글·블로그·지식iN 스니펫 | 공식 API |
| `pipeline/data/techtree.yaml` | 단계 구성과 진급 경로 | 직접 큐레이션 |

테크트리 그래프는 **자동 생성이 불가능합니다.** 어떤 공공데이터도
"소마 → 황소" 같은 진급 관계를 담고 있지 않습니다. 그래서 뼈대는 손으로
만들고, 그 위에 자동 수집한 학원과 점수를 얹는 구조입니다.

---

## 원칙

- 게시물 본문을 저장·재배포하지 않습니다. 원문은 링크로만 안내합니다.
- 작성자 아이디를 저장하지 않습니다. 중복 판별용 해시만 남깁니다.
- 광고비로 순위를 바꾸지 않습니다.
- 표본이 부족한 학원에 순위를 붙이지 않습니다.
- 하위 랭킹("최악의 학원")을 만들지 않습니다.
- 운영사 Open Edu가 영어 교육 사업자임을 서비스 안에 고지합니다.

---

## 개발

```bash
cd app
flutter analyze && flutter test
flutter build web --release
```

파이프라인:

```bash
python3 pipeline/run.py --check      # 자격 증명 상태
python3 pipeline/run.py              # 수집 → 채점 → 앱 번들
python3 pipeline/run.py --from-cache # 저장소·캐시로 재채점 (API 호출 없음)
python3 pipeline/run.py --with-cafe  # 카페 로컬 모듈 포함 (옵트인)
python3 pipeline/corrections_report.py   # 정정 요청 · 이의 · 예약 요청 대장
python3 pipeline/run.py --cases          # 웹 신고 → 사례 대장 (pipeline/wiki/cases)
```

**신고는 사례가 된다.** 웹 신고는 `run.py --cases` 가 파일로 옮기고, Claude Code 의
`/triage-reports` 가 프로젝트 에이전트(`.claude/agents/` — 진단·게이트별 담당·
검증)로 진단 → 조치 → 회귀 픽스처(`pipeline/tests/cases/`)까지 처리한다.
절차와 에이전트 표는 [docs/AGENTS.md](docs/AGENTS.md).

근거는 `pipeline/.cache/mention_store.json.gz` 에 회차마다 쌓인다. 한 번
찾은 후기는 다음 회차에 그 학원이 수집 대상에서 빠져도 남는다 — 채점 대상은
매일 조금씩 는다.

학원 상세의 근거는 **학원 이름이 나온 대목**을 번호([1]·[2]…)와 함께
발췌한다. 잘못 붙은 글은 줄마다 신고할 수 있고, 신고는 운영자 질문 큐 맨
앞에 선다. 전화·레벨테스트 예약 문의는 상세 머리에서 바로 한다(예약은
요청 접수이고 확정은 학원이 한다).
