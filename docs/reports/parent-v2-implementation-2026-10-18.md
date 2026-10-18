# 학원 선택 V2 제품 구현 검증 기록

2026-10-18 · **코드 구현·로컬 검증 완료 / 운영 적용 전**.
[구현·운영 안내](../PARENT_DECISION_IMPLEMENTATION.md) · [기계 판독 결과](parent-v2-implementation-check-2026-10-18.json)

## 구현 결과

‘우리 아이의 다음 장’ 오프닝에서 선택한 고민을 문의 질문으로 연결하고, 실제 학원 ID 최대 3곳을 항목별로 비교한다. 평가 학원과 등록부 학원을 구분하며 연락처가 없는 경우를 그대로 보여준다. 예산 입력·가격 추정·가격 비교·비용 적합 판정은 만들지 않았다.

전화/홈페이지의 공용 검증·복사 대안과 지점 표시를 보완했다. JSON을 읽은 시각으로 연락처 확인일을 생성하지 않는다. 출처가 상충하는 필드는 연결을 보류하는 adapter 상태를 지원한다. 현재 원자료에는 연락처별 원출처·대조일이 없어 모든 기존 값은 대조일 미확인 상태다. 연락처를 새로 수집하거나 다른 지점으로 채우지 않았다.

학부모 의견은 비공개 API·DB·UI로 구현했다. 접수증 상태/삭제, 같은 요청 재시도, 유형·길이·개인 연락처 입력 검사, 요청 제한, 관리자 상태 전이·검수된 개선 기록 발행, 보관 정리 함수를 포함한다. 일반 의견과 기존 정정·근거 신고·로그인 후기는 다른 경로로 유지한다.

현재 메뉴는 기존 구조에 비교 노트를 연결하고 전역 의견 버튼을 추가했다. 기존 학습 경로·지도·랭킹·학원 URL은 유지한다. 별도 ‘저장’ 페이지나 가족 공유는 추가하지 않았고 비교 ID와 고민만 기기에 보관한다. 웹 외 플랫폼의 저장 adapter는 메모리다.

## 변경 지점

| 범위 | 실제 파일 |
|---|---|
| 홈 | app/lib/features/home/parent_opening.dart, home_page.dart, core/theme.dart |
| 비교·보관 | data/parent_decision.dart, data/browser_store*.dart, features/compare/compare_page.dart, core/router.dart |
| 연락 | data/contact_view_model.dart, widgets/contact.dart, features/academy/contact.dart, academy_page.dart |
| 기존 화면 연결 | widgets/academy_card.dart, app_shell.dart, features/academy/review_section.dart, features/admin/admin_page.dart |
| 의견 | data/parent_voice.dart, features/feedback/parent_voice_page.dart, features/admin/parent_voice_page.dart |
| DB·함수 | supabase/16_parent_voice.sql, config.toml, functions/parent-voice/index.ts, handler.ts |
| 운영·검증 | scripts/parent_voice_cleanup.ts, check_parent_v2_web.cjs, app/test/parent_decision_test.dart, pipeline/tests/parent_voice_sql_test.mjs, test_parent_contact.py |
| 정적 상세 | pipeline/edutree/public_page_model.py, pipeline/seo.py |

## 실제 실행한 검사

| 검사 | 결과와 범위 |
|---|---|
| 구현 전 Flutter 기준선 | 기존 127개 통과 |
| 전체 Flutter, 3개 V2 플래그 on | **142개 통과**. 기존 화면·등록부·근거 연결 회귀 포함 |
| 마지막 UI 보완 후 새 기능 회귀 | **15개 통과**. 320/375/768/1440px × light/dark, 200% 글자 확대, 전송 실패·접수증·등록부 연락 없음 |
| Flutter analyze | 이슈 없음 |
| Flutter web release build | 3개 기능 플래그 on으로 성공. Supabase 키 없는 빌드 |
| Python 공개 상세·연락 정책 | **8개 통과**. canonical/alias·등록부·잘못된 URL·정상 대표번호/끝자리 0000 포함 |
| production handler + PostgreSQL(PGlite) | 통과. 실제 Request/Response 함수와 실제 migration/RPC를 연결. 원문 접근 권한·접수증 격리·멱등·삭제·상태/버전·공개 조건·보관·요청 제한 검사 |
| Deno check | index.ts와 정리 스크립트 통과 |
| 빌드된 웹 Playwright/Chrome | 고민→질문·저장, 비교 링크 최대 3곳 복원, 상세 직접 진입, 준비 중 제출 비활성, Escape 닫기, 4가지 폭·다크·reduced motion 통과. page error/console error 0 |
| 데이터 보존 | 기존 academies.json/registry.json SHA-256이 연락처 기준선과 일치. 점수·게이트·공개 데이터 자산 변경 없음 |

SQL 테스트는 원격 Supabase를 사용하지 않는다. PGlite의 anon/authenticated/service_role(실제 서비스 역할과 같은 BYPASSRLS), 합성 관리자·학원 자료를 사용했다. 함수의 RPC 의존성을 로컬 SQL에 연결한 것이며 호스팅 게이트웨이·PostgREST·외부 인증 통합 검증은 아니다. 보관 정리의 날짜 경계는 실제 로컬 DB 행을 과거로 이동해 검증했다.

전체 회귀의 첫 시도는 macOS 내부 임시 디스크 공간 부족으로 중단됐다. 사용자 파일을 삭제하지 않고 TMPDIR을 외장 볼륨으로 옮겨 재실행했고 통과했다. 코드 오류를 테스트 제외로 우회하지 않았다.

[실제 앱 데스크톱](parent-v2-app-desktop.png) · [실제 앱 모바일](parent-v2-app-mobile.png) · [실제 앱 모바일 비교](parent-v2-app-compare-mobile.png). 이미지의 학원은 로컬 공개 데이터이며 가상 후기나 접수를 넣지 않았다.

## 현재 운영 전제와 남은 검증

- 운영 기본 플래그는 off. 로컬 검토 빌드는 모두 on. 서버 미설정 시 실제 접수·가짜 성공 없음.
- 16 SQL과 Edge Function을 운영 환경에 적용하지 않았다. 서버 비밀·허용 origin·신뢰할 IP 헤더 확인과 스케줄 활성화는 운영 단계에 남아 있다.
- 실제 전화 연결·기기별 외부 앱 실행, 호스팅 로그/백업 보관, 현장 성능 p75·전후 비교, 수동 스크린리더·브라우저 페이지 확대·학부모 참여 과제는 미실행이다. 위젯의 글자 확대 검사와 구별한다.
- 이번 결과는 주 구현 역할의 자체 점검이다. 별도 검증 에이전트를 실행한 독립 검토로 주장하지 않는다.
- 42개 반례 YAML은 명세다. 구현된 범위의 실제 생산 함수·모델·UI/SQL 회귀로 핵심 경로를 검사했으며 P1_only 조건 엔진 사례는 이번 구현 범위가 아니다.

플래그와 환경 설정, 복귀 경로·재실행 명령은 구현·운영 안내에 기록했다. 실제 학부모 의견 수집이나 운영 공개 개선 발행을 이번 작업의 성과로 세지 않는다.
