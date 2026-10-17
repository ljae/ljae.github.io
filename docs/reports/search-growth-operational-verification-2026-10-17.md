# 검색 성장 운영 연결 검증 · 2026-10-17

앞선 [배포 기록](search-growth-deployment-2026-10-17.md)에 남아 있던 GSC OAuth 자동 수집과 로그인한 관리자 화면을 확인하는 후속 기록이다.

## 관리자 화면 실데이터 확인

Ego Lite의 운영 사이트에서 기존 관리자 계정으로 `/#/admin/growth`에 접근했다. Supabase 관리자 API의 `generate_link`로 기존 계정용 일회성 링크를 생성해 사용했으며 이메일 발송, 신규 사용자 생성, 관리자 권한 추가는 하지 않았다. 링크 파일은 사용 후 삭제했다. 이 방법은 일반 사용자의 이메일 수신·PKCE 로그인 흐름을 검증한 것은 아니다.

- 최근 CSV 기간(2026-09-17~10-14): 5클릭, 188노출, CTR 2.66%, 페이지 111개 표시.
- 전체 CSV 기간(2026-08-21~10-14)으로 전환: 121클릭, 5,439노출, CTR 2.22%, 페이지 최소 1,000개 표시.
- 개선 과제 탭: 실제 과제 목록과 상세 모달, 근거·검토 메모·상태 변경 동작의 입력 화면 확인. 검증을 위한 가짜 상태 변경은 저장하지 않았다.
- 실험 탭: 현재 기록 없음과 실험 시작 모달의 가설·대상 URL·대조 URL 입력을 확인하고 취소했다. 가짜 실험은 생성하지 않았다.
- 운영 DB에는 기존 실제 자료에서 생성한 사실 확인 과제 54개, 급감 사건 1개, 행 제한 경고 1개가 있다.

## 자동 수집 연결

Google Cloud 프로젝트 `openedu-search-growth`, 앱 `OpenEdu Search Growth`, Desktop OAuth 클라이언트 `OpenEdu GSC Readonly Automation`을 구성했다. Search Console API를 활성화하고 요청 권한은 `https://www.googleapis.com/auth/webmasters.readonly` 하나로 제한했다.

Google Cloud에서 해당 범위가 민감하지 않은 범위로 표시되는 것을 확인했고, 앱 게시 상태를 **프로덕션 단계**로 전환했다. 외부 앱의 Testing 상태에서 발급한 토큰은 일반적으로 7일 뒤 만료되므로 정기 운영용 연결은 전환 후 발급했다. 프로덕션 토큰도 권한 철회 등으로 무효화될 수 있다. [Google OAuth 토큰 만료 안내](https://developers.google.com/identity/protocols/oauth2/#expiration)

실제 Search Console 속성에 접근할 수 있는 기존 Google 계정으로 읽기 전용 동의를 완료했다. 로컬 loopback 콜백은 state 검증과 PKCE를 적용했고, 발급된 범위가 정확히 하나인지 확인했다. 갱신 토큰으로 새 액세스 토큰을 발급하고 `sc-domain:openedu4u.com`의 2026-10-14 확정 일별 자료 조회에 성공했다.

저장소의 `GSC_CLIENT_ID`, `GSC_CLIENT_SECRET`, `GSC_REFRESH_TOKEN` 비밀 설정 등록을 완료했다. 비밀값은 셸 인자나 공개 로그에 넣지 않고 표준 입력으로 전달했다.

## 소개·개인정보 안내 추가 배포

Google OAuth 설정에 필요한 [앱 소개](https://openedu4u.com/openedu/search-growth/)와 [개인정보 안내](https://openedu4u.com/openedu/search-growth/privacy.html)를 추가했다. 해당 분석 도구에만 적용되는 안내로 실제 수집·저장·접근·연결 해제·삭제 문의 방법을 설명한다.

- Sol 구현 → Astra Extra High 검토 승인(P0/P1 없음) → Sol 배포 순서로 진행했다.
- 320/1280px 화면에서 가로 넘침과 이름 없는 링크가 없고, 링크·문서 구조·포커스·색 대비를 검증했다.
- 커밋 `241e5bb5df13023d02b74428c30eed9e5ae6f884`.
- [Pages 배포 성공](https://github.com/ljae/ljae.github.io/actions/runs/39029363150). 두 공개 URL의 HTTP 200, canonical, 승인된 로컬 HTML과 응답 바이트 일치를 확인했다.

## 수집 작업 실행 결과

실제 OAuth를 등록한 후 [정기 분석 작업](https://github.com/ljae/ljae.github.io/actions/runs/39029612029)을 수동 실행했고 **전체 성공**을 확인했다. 이전 연결 대기 실행과 달리 실제 수집·비공개 게시 단계도 건너뛰지 않고 성공했다.

- 데이터 계약 회귀 16개 및 임시 PostgreSQL의 권한·상태 전이 검사 통과.
- PT 기준 2026-09-17~10-14의 28일을 6개 차원으로 수집하고 `dataState=final` 자료를 게시했다.
- API 스냅샷: `c79139e6689db04b62af1e10949a39501c0ccccd33e52e91b95c55296a970740`, `published: true`.
- 운영 DB에서 `gsc_api_final` 출처와 기간, 5클릭·188노출·CTR 2.66%를 재조회했다. 같은 기간 CSV의 클릭·노출·CTR과 일치하고 평균 순위도 부동소수점 표현 차이 외 동일하다. 각 출처의 검색 유형 필터 표기는 보존한다.
- 관리자 화면에서 최신 자료를 다시 읽고 `2026-09-17 ~ 2026-10-14 · API`를 선택해 5클릭·188노출·CTR 2.66%·111페이지를 확인했다. 기존 CSV 2개도 선택할 수 있다.
- 비공개 4개 테이블의 익명 REST 요청이 모두 HTTP 401로 차단되는 것을 다시 확인했다.

정기 실행은 매일 09:30 KST이며 PT 기준 3일 전까지의 최근 28일을 수집한다. 수동 실제 실행을 검증했으며, 미래 cron 실행의 성공을 미리 보증하는 것은 아니다. OAuth 권한 철회 등으로 `AUTH_REQUIRED`가 발생하면 동일한 읽기 전용 범위로 다시 인증하고 GitHub Secrets를 갱신한다.

GitHub 수집 성공 확인 후 로컬 임시 클라이언트 비밀값·갱신 토큰·인증 URL·콜백 도구 파일을 삭제했다. 콜백 서버도 종료됐다. 토큰 값이나 검색어 원문을 공개 문서·배포 파일에 기록하지 않았다.

앞선 배포에서 남긴 **OAuth 정기 수집 연결과 인증된 관리자 UI 확인을 모두 완료했다.** 학원 비교·행동 이벤트 수집·실험 효과 자동 판정 등 원 설계의 확장 범위는 기존 운영 안내와 동일하며 이번 연결 완료의 의미에 포함하지 않는다.
