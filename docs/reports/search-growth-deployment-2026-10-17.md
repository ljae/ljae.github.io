# 검색 성장 구현 · Sol 운영 배포 기록

2026-10-17. Astra Extra High 독립 검토의 웹 배포 승인 후 Sol 모델로 main 반영, GitHub Pages 배포, 기존 Supabase 복구와 검색 분석 DB 적용을 완료했다.

## 반영과 배포

- 구현 커밋: `995a332a9e65ad7ef22dc6fd2e785abdaa6a8b7e`.
- 배포 커밋: `7b8e206a5eeb763ebc6c4d4c4a9e63a7358a7df8`.
- [성공한 Pages 실행](https://github.com/ljae/ljae.github.io/actions/runs/39015656459): 2026-10-17 17:01 KST 배포 완료. 실제 사이트: <https://openedu4u.com/>.
- 최초 실행 `39015549340`은 새 테스트의 `prefer_const_constructors` 3건 때문에 배포 전에 중단됐다. `const MaterialApp` 1줄을 수정하고 정적 분석 clean 및 해당 파일 13개 회귀 통과 후 다시 배포했다.
- 성공 CI에서 Flutter 정적 분석, 전체 127개 테스트, 릴리스 웹 빌드, Python 검색 계약 16개 회귀가 통과했다. 구현 단계 전체 Python 회귀는 733개였다.
- 학원 점수·순위 계산과 `app/assets/data` 원본은 이번 커밋에서 변경하지 않았다. stage에 로컬 인증 값, `.cache`, ZIP, SQLite가 없음을 확인했다.

## 공개 산출물 확인

실제 운영 HTTP에서 홈, 한선영어학원 상세, 목동 허브가 200을 반환했다. 사이트맵 canonical URL은 **5,517개**이며, 검증된 호환 URL **10개 전부** HTTP 200·대장의 canonical 일치·사이트맵 제외를 확인했다.

- [한선영어학원 상세](https://openedu4u.com/a/3000046567.html): 반포·영어, 공시 상태와 주소, 미확인 학년/비용을 표시한다.
- [대치필 이전 URL](https://openedu4u.com/a/3000050666.html): 통합 안내와 현재 학원 내용을 제공하며 canonical은 `https://openedu4u.com/a/1000036516.html`이다. HTTP 리다이렉트가 아닌 호환 HTML이다.
- [목동 허브](https://openedu4u.com/g/mokdong.html): 탐색 CTA가 `/#/rank?region=mokdong`으로 연결된다.

실제 배포 artifact의 `main.dart.js`와 운영 응답의 SHA-256은 모두 `7b6c6b2fdd9d20955acc216de9994c8614d66c482fa0036c75da871c88a5640d`로 일치했다. Pages artifact 경로에서 `.env`, SQLite, ledger, snapshot, 비공개 report 등의 후보가 발견되지 않았다.

`search-pages-manifest` artifact `12095000965`를 내려받아 canonical 5,517개·호환 10개·issues 0개를 확인했다. 이 기능의 첫 배포이므로 이전 artifact가 없다는 bootstrap 경고가 기록됐다. 배포 성공 후 `search-pages-manifest-v1-39015656459` 캐시 저장도 성공했다. 다음 배포부터 이 성공 원장이 URL 삭제 검사와 lastmod 이력의 기준이다.

## 실제 브라우저 확인

Ego Lite의 기존 task space 12, p2를 재사용했다.

1. 정적 한선 상세에서 **앱에서 정보·정정 안내 보기**를 눌렀다. 앱에서 한선영어학원·반포 문맥, 공시 정원 644명, 미확인 학년, 공시 정보만 제공한다는 설명이 보이는 것을 스크린샷으로 확인했다.
2. 이전 대치필 URL에서 현재 정보 통합 안내와 canonical을 확인했다.
3. 목동 허브의 **목동 학원 탐색**을 눌러 `/#/rank?region=mokdong`, 목동 선택 및 목동 학원 목록 표시를 확인했다.
4. `/#/admin/growth`에 비로그인 상태로 진입하면 **검색 분석은 운영자 로그인 후 사용할 수 있습니다**가 나온다. 로그인 버튼은 `/admin`의 이메일 로그인 폼으로 이동하며 분석 자료는 노출하지 않았다. 로그인 메일은 발송하지 않았다.
5. 운영 홈으로 돌아가 실제 앱 진입을 확인했다.

배포 전부터 열어 둔 p2의 HTTP 캐시에 기존 JS가 남아 최초 진입에서는 구버전 상세가 보였다. 사용자 캐시를 삭제하지 않고 해당 Page의 `Network.setCacheDisabled` 후 reload해 새 번들을 확인했다. 서버 응답의 `Cache-Control: max-age=600`을 관측했으며 위 artifact hash 비교로 운영 배포가 최신임을 검증했다.

## Supabase 복구와 비공개 게시

기존 운영 프로젝트의 `INACTIVE` 상태를 확인하고 공식 [프로젝트 restore API](https://supabase.com/docs/reference/api/v1-restore-a-project)를 1회 호출했다. `COMING_UP → RESTORING → ACTIVE_HEALTHY` 전환과 호스트 DNS 복구를 확인했다. 유료 플랜 변경·다른 프로젝트 변경은 수행하지 않았다.

복구 중에는 SQL API에서 일시적으로 public 테이블과 auth 사용자가 없는 상태가 관측됐고, 한 차례 선행 SQL 요청은 DB 연결 거부로 실패했다. 이 시점의 결과를 최종 상태로 사용하지 않았다. `ACTIVE_HEALTHY`에서 재확인한 결과 기존 public 테이블, auth 사용자 6명, 관리자 1명, 관리자 예약 1건 및 `public.is_admin()`이 모두 복원돼 있었다. 선행 관리자 migration은 적용하지 않았으며 로컬 초안도 제거했다.

이후 [15_search_growth.sql](../../supabase/15_search_growth.sql)만 Management API SQL 요청으로 적용해 HTTP 201 성공을 확인했다. 네 개 growth 테이블의 RLS가 모두 활성화됐고 기존 관리자 수 1명도 유지됐다. 기존 정정·검토 데이터나 관리자 등록은 변경하지 않았다.

로컬 비공개 원장에서 실제 CSV 성과 스냅샷 두 개를 환경변수로 인증해 게시했다. 두 요청 모두 `published: true`였으며 서버 키로 원격 DB를 재조회해 다음 총계를 확인했다. 검색어 원문과 원본 ZIP은 공개 배포 자료에 넣지 않았다.

| 기간 | 클릭 | 노출 |
|---|---:|---:|
| 2026-08-21~2026-10-14 | 121 | 5,439 |
| 2026-09-17~2026-10-14 | 5 | 188 |

실제 익명 API 키로 네 개 growth 테이블 조회와 `growth_overview` RPC를 요청해 **모두 HTTP 401**로 거부됨을 확인했다. 역할별 세부 전이·멱등성·버전 충돌·실험군 겹침은 PGlite 회귀에서도 통과했다.

## 정기 수집과 남은 확인

**후속 완료:** 아래는 최초 배포 시점의 상태다. 같은 날 OAuth 설정, 실제 API 28일 수집·게시, 인증된 관리자 화면 확인을 모두 완료했다. 최신 결과와 실행 증거는 [운영 연결 검증](search-growth-operational-verification-2026-10-17.md)을 따른다.

[정기 분석 workflow 실제 실행](https://github.com/ljae/ljae.github.io/actions/runs/39015558499)은 성공했다. Python 계약 16개와 PGlite migration 재적용·RLS·RPC 권한·게시 중복 방지·버전 충돌·배포 확인 게이트·실험군 분리 검증을 수행했고, 수집 단계는 OAuth 인증 미설정 때문에 건너뛰었다.

- `GSC_CLIENT_ID`, `GSC_CLIENT_SECRET`, `GSC_REFRESH_TOKEN`은 로컬/CI에 아직 없다. 읽기 전용 OAuth 설정 후 실제 Google API 정기 수집과 권한을 검증해야 한다. 현재는 CSV 수입과 비공개 게시까지 완료된 상태다.
- 기존 관리자 계정은 복원됐지만 브라우저에 로그인된 관리자 세션이 없어 **로그인 후 분석 UI의 실제 운영 데이터 표시**는 이번 배포에서 검증하지 않았다. 로그인 보호, 원격 게시·조회, 실제 익명 차단은 확인했다.

검색 성과 개선이나 09-03 급감의 원인을 이번 배포 성공만으로 판정하지 않는다.
