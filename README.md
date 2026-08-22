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

---

## 트리스코어

```
TreeScore = 0.35·평판 + 0.20·화제성 + 0.25·투명성 + 0.20·진입난이도
```

산식은 서비스 안에서 전부 공개됩니다 (`/method`). 자세한 정의는
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
python3 pipeline/run.py --with-cafe  # 카페 로컬 모듈 포함 (옵트인)
```
