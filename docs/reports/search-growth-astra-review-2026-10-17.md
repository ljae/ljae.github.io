# 검색 성장 구현 · Astra 독립 검증

검토일: 2026-10-17. 대상 작업공간: `/Volumes/ORICO/open_edu`.

**판정: 웹 배포 승인. 현재 수정본에서 미해결 P0/P1을 발견하지 못했다.** 최신 릴리스 빌드도 성공했으므로 Sol 배포 단계로 인계한다. 운영 Supabase 적용·실데이터 게시·GSC 정기 수집의 완료를 승인한 것은 아니다. 원격 DB 연결 장애와 GSC OAuth 미설정은 아래에 별도로 기록한다.

제품 코드는 읽기 전용으로 검토했고 수정·커밋·배포하지 않았다. 발견 사항의 수정은 구현 담당이 수행했다. 이 검토 문서 작성만 별도로 허용받았다.

## 검토 범위

- `SEARCH_GROWTH_DESIGN.md`, `SEARCH_GROWTH_IMPLEMENTATION.md`, `SEARCH_GROWTH_SOL_HANDOFF.md`, 기존 실측 보고서·baseline·HTML 시안과 현재 tracked diff 및 미추적 신규 코드.
- GSC CSV/API의 집계 단위, 재수입, 일자별 원자성, pagination·재시도, 비공개 저장·게시 경로.
- 성장 화면의 인증 상태, provider 캐시, Supabase RLS/RPC, 과제 버전 충돌 및 배포 확인 기록.
- 등록부 상세 resolver, 검색 결과 진입, 지역·과목·학년·학교 복원, 정적 상세의 근거·연락 링크.
- URL alias 원본 근거, canonical, 사이트맵·호환 HTML, 내용 hash 기반 lastmod, CI의 이전 성공 배포 원장 보존.

## 발견 사항과 수정 확인

| 심각도 | 발견 위치 | 재현·실패 조건 | 최종 확인 |
|---|---|---|---|
| P1 | `pipeline/data/url_aliases.json`의 최초 `6244 → 6448` 항목 | 일반명인 피아노교습소에서 서로 다른 원장명과 상세 주소를 도로명만으로 동일 실체로 판단했다. NEIS 원본의 상세 주소도 서로 달라 동일 학원으로 canonical을 확정할 근거가 없었다. | verified 대장에서 제거. 공개 호환 HTML은 11개에서 **10개**로 축소. 나머지 10개는 원본 이름·도로명 건물번호·현재 등록 membership을 대조했고, 다른 층/호수의 관·과정 통합이라는 근거를 대장에 추가했다. |
| P2 | `pipeline/growth/store.py:45`, `app/lib/data/growth.dart:18` | 같은 기간·소스의 수정 스냅샷을 다시 수입하면 checksum ID 오름차순 때문에 과거 스냅샷이 기본 analyze/publish 대상으로 선택됐다. 임시 SQLite에서 새 수치가 있어도 이전 추출일·수치가 먼저 반환되는 것을 재현했다. | 로컬은 `exportedAt DESC, rowid DESC`, UI는 `imported_at DESC`로 보완. 재수입 회귀 포함 관련 테스트 통과. |
| P2 | `pipeline/growth/inventory.py:92` | alias는 사이트맵에서 빠지므로 이전 manifest에도 없었다. 호환 HTML과 mapping을 함께 삭제해도 `removed=[]`로 게이트를 통과했다. | `compatibilityUrls` 보존, 호환 파일·canonical 검사, 이전 호환 URL 삭제 차단 추가. 동일 재현이 `UNEXPECTED_URL_REMOVAL`로 실패하는 것을 독립 확인. |
| P2 | `app/lib/features/academy/academy_page.dart:43` | 최초 `dataProvider` 로딩이 실패하면 재시도가 registry/detail만 무효화해 같은 실패를 다시 받았다. | `dataProvider.hasError`일 때 해당 provider도 무효화. 구현 담당의 실제 재시도 위젯 회귀 통과 보고. |
| P2 | `pipeline/growth/cli.py:116` | 비공개 보고서 출력 제한에서 `openedu/`와 `app/web/`가 빠져 있었다. 이 두 경로에 출력하면 다음 웹 배포에 검색어 원문이 포함될 수 있었다. | 두 공개 원본 경로를 차단 목록에 추가한 코드 확인. 기본 비공개 캐시 출력은 유지. |
| P2 | `.github/workflows/deploy.yml:113` | 성공 manifest 캐시가 사라지면 이전 artifact가 있어도 초기 상태로 진행해 URL 삭제 검사와 lastmod 이력이 재설정됐다. | 캐시 누락 시 main의 성공 실행 artifact 복원, 복원 불가능 시 실패, 최초 artifact 없음만 명시적 bootstrap 경고. 성공본 복원·최초 bootstrap·실패한 실행만 있을 때 차단하는 세 시나리오를 외부 호출 없이 독립 실행해 확인. |

추가 방어도 확인했다. `SelectionRoute`는 현재 URI와 다른 비활성 화면에서 선택 변경으로 이동하지 않도록 제한했다. 실제 `/rank?region=daechi`에서 반포 학원 상세로 이동하는 회귀는 수정 전에도 통과했으므로 이 항목을 확정 결함으로 세지 않았다. Artifact 업로드에는 `include-hidden-files: true`, `if-no-files-found: error`를 명시했다. 명시적 단일 파일 경로의 숨김 상위 폴더 처리에는 구현상 예외가 있어, 최초 제기했던 artifact 제외 우려 역시 확정 P1으로 세지 않았다.

## 독립 실행과 검증 증거

직접 실행:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  pipeline/tests/test_growth.py pipeline/tests/test_growth_gsc.py pipeline/tests/test_search_pages.py
16 passed
```

- 동일 기간 수정 스냅샷의 과거 자료 우선 선택을 임시 SQLite에서 재현했다.
- 호환 URL 삭제의 게이트 누락을 임시 HTML에서 재현하고 수정 후 차단을 확인했다.
- 원장 복원 workflow의 실제 Python 블록을 추출해 합성 GitHub 응답과 ZIP으로 3개 분기를 검증했다. 외부 API나 운영 상태는 변경하지 않았다.
- 최초 alias 11개의 NEIS 캐시 원본과 현재 통합 등록을 대조했다. 명백한 타인 오연결 1개가 제거됐음을 확인했다.
- `git diff --check`에서 오류가 없었다.

구현 담당이 최신 수정본에 대해 전달한 결과이며, 독립 검토자가 중복 실행하지 않은 항목:

- Python 전체 **733개**, Flutter 전체 **127개** 통과, `flutter analyze` 오류 없음.
- 정적 canonical URL **5,517개** 생성 및 내부 링크 검사 통과. 호환 URL **10개**는 사이트맵에서 제외.
- PGlite SQL 회귀에서 migration 재적용, RLS, RPC 권한, 게시 멱등성, 과제 버전 충돌·배포 확인 게이트·실험군 겹침 차단 통과.
- 실제 브라우저에서 정적 한선 상세→앱 상세, 지역 복원, 모바일 상세, 비공개 보고서 기간 전환 확인. 보고서의 121/5,439 및 5/188은 구현 담당이 실자료로 재현했다.
- 최신 전체 릴리스 웹 빌드 성공을 구현 담당이 최종 확인했다.

## 판단의 근거와 운영 한계

사이트 총계는 일별 property 자료로 계산하며 page/query 차원 합계를 더하지 않는다. CSV 기간 자료를 가짜 일별 자료로 나누지 않고, 검색어 가시성·행 제한·원인 미확정을 유지한다. API는 하루의 6개 차원이 모두 성공한 후 partition을 교체하므로 중간 요청 실패가 그 날의 이전 정상 partition을 덮지 않는다.

등록부 전용 상세는 별도 모델을 사용하며 0점 Academy를 만들어내지 않는다. 성장 지표가 기존 학원 점수 산식의 입력으로 연결되는 변경은 발견하지 못했다. 원본 보고서는 기본적으로 비공개 캐시에 남고, 운영 화면의 조회에는 관리자 확인과 DB RLS/RPC 검사가 함께 적용된다. 계정 변경에 따른 provider 캐시 무효화 코드와 회귀를 확인했다.

**원격 운영 완료는 아직 확인하지 않았다.** 구현 담당이 Supabase 프로젝트 호스트 DNS 실패와 Management API SQL preflight 544를 확인했고, 관리 API 프로젝트 목록에서는 해당 프로젝트의 `INACTIVE` 상태를 확인했다고 전달했다. 이번 검토 시점에 원격 migration·보고서 게시 성공은 0건이다. 따라서 웹 배포가 성공해도 `/admin/growth`의 실제 운영 DB 연결·권한을 검증했다고 보고하면 안 된다. 기존 프로젝트 재개 가능 여부와 원격 적용은 배포 담당이 별도로 처리한다.

GSC OAuth CI 비밀 3종도 미설정 상태다. 스케줄 workflow는 연결 대기 상태로 남는 것이 현재의 예상 동작이며, 실제 Google API 수집 성공·실계정 권한·운영 Supabase RLS는 후속 연결 단계에서 확인해야 한다. GitHub Actions 원장 artifact 복원도 합성 분기 검사까지 완료했으며 실제 Actions 실행 결과는 배포 단계에서 확인한다.

배포 후 확인 대상은 공개 정적/앱 상세·10개 호환 canonical·사이트맵과 manifest artifact/cache의 성공 보존이다. 검색 성과 개선, 노출 급감 원인 확정, GSC 정기 운영, DB 적용 성공을 웹 배포 성공과 혼동하지 않는다.
