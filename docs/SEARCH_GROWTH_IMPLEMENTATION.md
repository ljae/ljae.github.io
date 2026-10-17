# 검색 성장 · 구현 및 운영 안내

2026-10-17. 첫 구현 범위는 설계의 S0~S3이며, S4의 조건 복원·허브 연결과 변경/실험 기록도 포함한다. [운영 사이트](https://openedu4u.com/) 배포와 원격 DB 적용, 실제 CSV 스냅샷 2개 비공개 게시를 완료했다. 후속으로 GSC OAuth 정기 수집을 연결하고 API 스냅샷 1개 수집·게시, 로그인한 관리자 화면의 실제 브라우저 검증도 완료했다. 근거는 [배포 기록](reports/search-growth-deployment-2026-10-17.md)과 [운영 연결 검증](reports/search-growth-operational-verification-2026-10-17.md)에 있다.

## 제공하는 기능

| 영역 | 구현 |
|---|---|
| 분석 | GSC ZIP/CSV 수입, SHA 기반 중복 방지, 총계·차원별 기간 집계 구분, 행 제한·검색어 가시성 표시 |
| 진단 | 완결된 일별 자료의 급감 탐지, 원인 미확정 유지, 유입이 있는 학원의 미확인 사실 조사 큐 |
| 정기 수집 | 읽기 전용 OAuth, 날짜별 pagination, 토큰 갱신/재시도, 6개 차원의 원자적 일자 저장 |
| 운영자 UI | `/#/admin/growth`: 관측 기간·지표·일별 그래프·상위 검색어/페이지·개선 과제·실험 기록 |
| 과제 관리 | 중복 과제 방지, 우선순위/노출 정렬, 버전 충돌 감지, 배포 확인 기록을 거친 상태 전이 |
| 상세 복구 | 채점 학원과 등록부 전용 학원 모두 직접 진입·검색 결과에서 상세 표시. 로딩/오류/미존재 구분 |
| 정적 상세 | 확인된 과목·학년 근거·주소·공시 상태, 가능한 연락/위치 행동, 같은 지역·과목 링크 |
| URL | 현재 URL 유지, 확인된 10개 이전 URL 호환 HTML, 앱의 지역/과목/학년 조건·학교 선택 복원 |
| 배포 검사 | canonical·실제 파일·내부 링크·URL 삭제 검사, 주요 내용 hash 기준 lastmod, 직전 성공 배포 원장 보존 |

학원 점수·순위 계산과 기존 판정 규칙은 검색 지표를 입력받지 않는다. 등록부 전용 학원을 0점 Academy 객체로 만들지 않는다.

## 지금 로컬에서 확인

현재 원본으로 만든 [비공개 분석 화면](../pipeline/.cache/growth/report.html)을 브라우저에서 열 수 있다. 이 파일은 Git/배포 대상에서 제외되어 있으며, 다른 머신에는 없을 수 있다.

```bash
# 프로젝트 루트에서 실행. 원본 ZIP은 앞선 Ego Lite 조사에서 내려받은 파일이다.
.venv/bin/python -m pipeline.growth.cli import-csv --input pipeline/.cache/search-growth/2026-10-17/performance-3m.zip --exported-at 2026-10-17
.venv/bin/python -m pipeline.growth.cli import-csv --input pipeline/.cache/search-growth/2026-10-17/performance-28d.zip --exported-at 2026-10-17
.venv/bin/python -m pipeline.growth.cli import-csv --input pipeline/.cache/search-growth/2026-10-17/index-404.zip --exported-at 2026-10-17
.venv/bin/python -m pipeline.growth.cli report
```

실제 재집계는 **121클릭/5,439노출**, **5클릭/188노출**을 재현했다. 전체 기간에는 09-03 급감 사건과 페이지 1,000행 제한이 표시된다. 검색어 표의 클릭을 사이트 총계로 대체하지 않는다.

`analyze --output <private.json>`은 JSON 보고서, `alias-candidates`는 색인 CSV와 현재 등록번호를 연결한 검토 목록이다. SQLite 파일은 `pipeline/.cache/growth/ledger.sqlite`이며 로컬 수입·API 체크포인트용이다. 운영 과제 상태를 별도의 로컬 DB에 복제하지 않는다.

```bash
.venv/bin/python -m pipeline.growth.cli alias-candidates
.venv/bin/python -m pipeline.growth.cli inventory --site-dir _site --previous-manifest pipeline/.cache/growth/page-manifest.json --output pipeline/.cache/growth/check-manifest.json
```

## 운영 연결

기존 Supabase 프로젝트를 재개해 `ACTIVE_HEALTHY`와 기존 관리자/데이터 복원을 확인한 뒤 `15_search_growth.sql`만 적용했다. 기존 관리자 1명·예약 1건을 유지했고 CSV 게시와 GSC OAuth 3종 비밀 설정 등록도 완료했다. 다음은 재구성 시의 절차다.

1. Supabase에서 기존 `09_admin_review.sql` 적용 상태를 확인하고 [15_search_growth.sql](../supabase/15_search_growth.sql)을 적용한다.
2. GSC API를 사용할 Google Cloud 프로젝트에서 읽기 전용 OAuth refresh token을 발급하고 해당 계정의 `sc-domain:openedu4u.com` 접근 권한을 확인한다. 현재 프로젝트는 `openedu-search-growth`이고 OAuth 앱은 프로덕션 상태다. Testing 상태 토큰의 7일 만료를 피하도록 상태를 확인한 후 발급한다.
3. CI 비밀 설정에 `GSC_CLIENT_ID`, `GSC_CLIENT_SECRET`, `GSC_REFRESH_TOKEN`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`를 등록한다. 서버 키는 Flutter 설정으로 전달하지 않는다.
4. 최초에는 실제 CSV와 API가 겹치는 기간·검색 유형의 총계가 비교 가능한지 확인한다. CSV의 `Web (text-based)`와 API `web`은 원 출처 필터를 각각 보존한다.
5. 기존 운영자 계정으로 `/admin`에서 로그인한 뒤 **검색 성장 분석**으로 들어간다. 최초 자료가 없으면 연결 대기 화면이 나온다.

```bash
# 인증 환경변수가 준비된 서버/로컬 실행 환경에서만 사용한다.
.venv/bin/python -m pipeline.growth.cli sync-gsc --start 2026-09-17 --end 2026-10-14
.venv/bin/python -m pipeline.growth.cli publish
```

`publish --snapshot <id>`로 과거 CSV 보고서도 선택해 게시할 수 있다. 수입 결과의 id 또는 로컬 원장에서 확인한 id를 사용한다. 게시 위치는 운영자 전용 DB이며 공개 사이트 JSON이 아니다.

[search-growth.yml](../.github/workflows/search-growth.yml)은 09:30 KST에 PT 기준 3일 전까지의 최근 28일을 수집한다. 인증이 없으면 연결 대기 notice를 남긴다. 분석 작업은 기존 수집·배포 연쇄와 분리되어 있다. OAuth 등록 후 [실제 Actions 실행](https://github.com/ljae/ljae.github.io/actions/runs/39029612029)에서 계약/SQL 권한 검증과 28일 API 수집·DB 게시가 모두 성공했다. 2026-09-17~10-14 API 총계는 CSV와 동일한 5클릭·188노출이며 관리자 화면에서 API 출처로 확인했다. 앞으로는 설정된 cron으로 실행된다.

## 저장 계약의 첫 구현

원 설계의 상세 차원 테이블을 한꺼번에 만들기보다 `growth_reports`에 immutable 원본 스냅샷과 분석 결과를 보존한다. 각 스냅샷 안에서 일별/기간별 grain을 구분한다. 별도 `growth_tasks`, `growth_changes`, `growth_experiments`가 운영 상태를 관리한다. 향후 일별 테이블로 정규화해도 원본 스냅샷과 SHA를 유지할 수 있다.

원본 ZIP은 로컬 비공개 캐시에 남고, DB에는 출처·checksum과 정규화한 전체 스냅샷이 저장된다. 원본 ZIP의 private Storage 업로드/보관기간 자동 정리는 후속 운영 작업이다.

## 이전 URL 확인

404 후보 214개 중 93개가 현재 `registrationIds`에 연결된다. 이 중 NEIS 원본에서 **양쪽 등록의 확인 상태·주소·정규화 이름·지역이 모두 같고 현재 통합 등록에도 포함된 10개**를 [URL 대장](../pipeline/data/url_aliases.json)에 기록했다. 확인 방식과 원본 SHA, 등록명을 보존했다.

예: `/a/3000050666.html`은 동일한 대치필 주소의 현재 학원 정보를 제공하고 `/a/1000036516.html`을 canonical로 선언한다. 이는 GitHub Pages의 **HTTP 200 호환 페이지**다. 나머지 연결 후보 83개와 미연결 121개는 자동 이전하지 않았다. 검토 목록은 비공개 캐시의 `alias-review-pending.json`에 있다.

새로운 통합으로 URL을 제거하려면 확인된 대장 또는 명시적인 lifecycle 처리를 먼저 추가해야 한다. `--allow-removals`는 검토를 완료한 경우의 수동 복구 옵션이다. 일상 배포에서 기본으로 켜지 않는다.

## 검증

- Python 전체 회귀: 733개 통과.
- Flutter 전체 회귀: 127개 통과. 실제 앱 라우터의 지역 복원과 계정 변경 시 관리자 캐시 무효화를 포함한다.
- Flutter 정적 분석: 오류 없음. 릴리스 웹 빌드 성공.
- 정적 canonical URL 5,517개 생성 및 내부 링크 검사 통과. 호환 페이지 10개는 사이트맵에서 제외한다.
- 임시 PostgreSQL(PGlite)에서 migration 2회 적용, 익명/일반 계정 접근 차단, 게시 멱등성, 과제 버전 충돌, 배포 확인 게이트, 실험군 중복 방지를 검증했다. 운영 Supabase에도 migration 적용 후 보고서 2개 게시·재조회와 익명 REST/RPC 접근 차단(401)을 확인했다.
- Ego Lite에서 실제 생성한 분석 보고서의 기간 전환, 한선 정적 상세→앱 상세, 이전 URL canonical, 모바일 정적 상세를 확인했다. 추가 브라우저 확인 결과는 아래 실행 기록을 따른다.

```bash
.venv/bin/python -m pytest -q pipeline/tests
cd app
flutter analyze --no-pub
flutter test --no-pub
flutter build web --release --base-href / --pwa-strategy=none --no-pub
```

SQL 회귀는 프로젝트 의존성을 추가하지 않고 임시 디렉터리에 설치한 `@electric-sql/pglite@0.5.10`으로 실행한다. 같은 검증을 정기 분석 CI에 포함했다.

## 확장 범위

첫 구현은 유입 복구와 실제 자료 기반 진단을 사용할 수 있게 하는 범위다. 원 설계의 3개 학원 비교 화면, 행동 이벤트의 운영 수집기, 실험 자동 효과 판정, 외부 검색 수요 데이터와 대규모 내부 링크 최적화는 확장 단계다. 현재 실험 탭은 가설·대상 URL·대조 URL을 기록하며, 이를 검색 성과가 개선됐다는 판정으로 바꾸지 않는다.


## 독립 검토 반영

Astra Extra High 검토에 따라 타인 명의·상세 주소가 다른 피아노교습소 URL 연결 1건을 제외했다. 나머지 10건은 같은 브랜드·건물의 관/과정 통합이며 이전·현재 층/호수 근거를 보존한다. 같은 기간 재수집 시 최신 스냅샷 선택, 상세 로딩 재시도, 화면 전환 중 URL 복원 방어, 호환 URL 제거 감지, 공개 배포 폴더의 분석 출력 차단을 보완했다. 배포 원장은 캐시 누락 시 성공한 main 배포 artifact에서 복원하고, 최초 bootstrap은 경고로 명시한다.

Ego Lite에서 목동 허브의 탐색 버튼을 눌러 `/#/rank?region=mokdong`과 목동 학원 목록이 표시되는 것을 확인했다. 한선영어학원 상세는 반포 문맥을 복원하며 미확인 학년·수강료를 임의 추정하지 않는다.
