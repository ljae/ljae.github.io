# Sol 구현 인계 — 연락처·학부모의 소리·‘다음 장’ 오프닝

2026-10-18 · V2 · **S0~S5 제품 코드 구현·로컬 검증 완료 / 운영 적용 전**. [현재 구현·운영 안내](PARENT_DECISION_IMPLEMENTATION.md), [검증 기록](reports/parent-v2-implementation-2026-10-18.md)을 먼저 읽는다. 아래는 최초 인계와 작업 기준을 보존한 기록이다. 이후 세션에서 Sol 모델을 선택하고 아래 프롬프트를 사용한다. 이번 설계 작업 중 Sol을 실행하거나 모델을 바꾸지 않았다. 기존 프로젝트 에이전트는 `model: inherit`를 유지한다. 실행 환경마다 모델 식별자가 다를 수 있으므로 설정에 임의의 모델 문자열을 박지 않는다.

## 바로 사용할 프롬프트

```text
학원실록의 부모 의사결정 V2 설계를 현재 저장소에 구현하라.
읽을 문서:
- docs/PARENT_DECISION_DESIGN.md
- docs/PARENT_VOICE_DESIGN.md
- docs/PARENT_DECISION_SOL_HANDOFF.md
- docs/PARENT_DECISION_AGENTS.md
- docs/reports/parent-contact-voice-redesign-2026-10-18.md
- docs/evals/parent-decision-cases.yaml
화면 참조: docs/prototypes/parent-decision.html (가상 자료·전송 없는 시안).

git status와 적용되는 프로젝트 지침을 읽고 기존 사용자 변경을 보존하라.
이 문서의 S0~S5를 순서대로 구현하고, 실제 코드·검증 결과를 보고하라.
현재 Flutter·Python·정적 HTML·Supabase를 유지하라.
예산 입력·금액 추정·가격 비교·가격순 정렬·비용 적합 판정은 만들지 마라.
비용은 직접 문의할 질문으로만 제공하라.

오프닝은 ‘우리 아이의 다음 장’. 검색·기존 딥링크를 지연시키지 마라.
연락처는 해당 지점의 실제 값과 출처를 쓰고 모르는 날짜를 생성하지 마라.
AcademyDetail의 evaluated/listed 둘 다 처리하고 없는 연락처는 공백 상태로 남겨라.
기존 ContactCard/ConsultChecklist/연락 함수를 확장하되 안전 URL과 실패 처리를 공용화하라.
TreeScore·게이트·학년 근거·canonical·등록부 ID를 보존하라.

학부모의 소리는 신규 비공개 접수와 접수증 조회, 관리자 검토, 검수된 개선 기록으로 구현하라.
기존 정정·근거 신고·수강 후기의 권한과 경로를 약화시키지 마라.
백엔드 미설정·전송 실패는 접수 성공으로 표시하지 마라.
운영 원문·개인 정보·접수 비밀값을 Git/공개 JSON/URL/이벤트/로그에 쓰지 마라.
자동 학원 연락·예약 대행·학부모 의견의 자동 공개는 구현하지 마라.

인증·로컬 DB 도구가 없으면 만들 수 있는 코드/스키마/계약/테스트를 끝내고
실행하지 못한 통합 검증을 명시하라. 해당 기능 플래그는 꺼 둔다.
실제 통합 검증을 fixture 성공으로 대신했다고 말하지 마라.
S0~S5 밖의 P1 추천 엔진·가족 공유·네이티브 전용 기능은 범위에 넣지 마라.
설계 YAML 파싱을 제품 회귀 통과라고 보고하지 마라.
이 프롬프트의 범위는 로컬 구현과 릴리스 준비이며 운영 배포·DB 적용·외부 발송은 포함하지 않는다.
```

## 1. 현재 코드에서 출발할 것

| 기존 파일 | 재사용과 주의점 |
|---|---|
| `app/lib/features/home/home_page.dart`, `core/theme.dart`, `widgets/annals.dart` | 현재 탐색 상태·브랜드 토큰을 유지하며 오프닝 추가. 문서의 HTML을 iframe으로 넣지 않음 |
| `app/lib/core/router.dart`, `core/selection_route.dart`, `widgets/app_shell.dart` | 기존 경로·학교 문맥·admin 로그인 복귀 보존 |
| `app/lib/data/academy_detail.dart`, `models.dart`, `repository.dart` | evaluated/listed 분리. RegistryEntry에는 현재 tel/homepage 없음 |
| `app/lib/features/academy/contact.dart` | ContactCard·ConsultChecklist. 존재하지 않는 ContactActions 클래스를 가정하지 않음 |
| `app/lib/widgets/contact.dart` | callAcademy/copyTel/openHomepage. openHomepage가 공용 안전 URL 검사를 우회하고 있으므로 통일 |
| `pipeline/edutree/public_page_model.py`, `pipeline/seo.py`, `pipeline/seo_templates/` | 정적 상세와 Flutter의 연락처·출처 표현 일치. 기존 safe_url/safe_phone 정책은 실제 정상 번호 반례와 함께 점검 |
| `app/lib/data/corrections.dart`, `reviews.dart`, `reservations.dart` | 정정/후기/근거 신고/행동 로그 재사용. 남아 있는 ReservationService는 예약 UI 복원 근거가 아님 |
| `supabase/06_corrections_tags.sql`, `09_admin_review.sql`, `14_reservations_reports.sql` | 제약·RLS·is_admin 검토. 새 일반 의견용 테이블 분리 |
| `app/lib/features/admin/admin_page.dart`, `data/admin.dart` | 기존 관리자 인증과 메뉴를 확장. 클라이언트 관리자 플래그로 권한 대체 금지 |

로컬 기준: 평가 학원 2,868건 중 tel 2,154·homepage 1,114, 등록부 전용 2,483건에는 두 필드 없음. [해시 포함 원장](reports/parent-contact-baseline-2026-10-18.json). 구현 시작 시 다시 측정하고 달라지면 당시 값을 기록한다. 수치는 유효 연락처 수가 아니라 값 존재 수다.

## 2. 단계별 변경과 수락 조건

### S0 — 기준선과 실패 재현

- git diff·사용 가능한 Flutter/Python/Node/Supabase 도구 확인. 기존 실행 지침에 따라 영향 범위 테스트를 한 번 실행.
- 학원 평가/등록부/alias/없는 ID/지연 로딩 사례 확보. 연락처 원출처·날짜 메타데이터의 실제 존재 범위 확인.
- `homepage` 로그를 앱에서 전송하지만 선언 SQL 허용 목록에는 없는 불일치 재현. 운영 DB 미조회면 그대로 명시.
- 후보 연락처의 잘못된 지점·빈 값·무효 URL·형식 불명 상태를 확인. 데이터를 채워 넣기 위한 자동 검색은 범위 밖.
- 산출물: `docs/reports/parent-v2-implementation-<date>.md`에 기준선, 변경 범위, 도구 제약.

### S1 — 홈과 탐색

- 기존 home 파일을 확장하고 필요하면 신규 `features/home/parent_opening.dart`로 분리. 실제 이름은 저장소 관례에 맞춰 조정 가능.
- Paperlogy·기존 녹색 토큰, 여백·큰 제목·기록장 시각 표현. 고민 선택은 질문 문맥에만 사용.
- 지역·과목·학년·이름 검색 연결. 첫 화면의 CTA를 폰트/모션 로딩이 막지 않음. 오프닝 재생 완료를 진입 조건으로 두지 않음.
- 상태: 초기/선택/건너뛰기/모션 축소/다크/좁은 화면. 탐색에서 돌아오면 기존 선택 유지.
- 수락: PD20/21/31/32. 정적 상세 직접 방문이 오프닝으로 강제 이동하지 않음.

### S2 — 비교와 연락

- 신규 제안 `app/lib/data/parent_decision.dart`, `contact_view_model.dart`, `features/compare/compare_page.dart` + 기존 card/detail/router 변경.
- 비교 공개 ID 최대 3개, 중복 제거, 없는 ID 안내, 320px 세로 비교. 원문 근거와 unknown 표시.
- 연락 adapter는 평가/등록부 둘 다 지원. 등록부는 연락처 없음이 정상 결과이며 원자료 확인 후에만 필드 확장.
- 기존 연락 함수를 adapter 입력으로 공용화하고 모든 호출부를 맞춘다. http(s)·host·userinfo 검사, phone 검증·번호 표시, 복사 실패·외부 실행 실패 처리.
- 번호/URL의 값·원출처 대조일·전화 연결 상태는 서로 구별. 기존 JSON만으로 ‘오늘 확인’ 배지 금지.
- 질문 복사, 해당 지점 이름 표시, 비용 문의 문구. 연락 행동이 데이터 로깅 실패 때문에 막히지 않음.
- 신규 migration에서 academy_actions 허용 목록에 homepage를 추가. 과거 reserve 행을 삭제하거나 예약 UI를 되살리지 않음. 변경 전후 실제 enum/check 이름을 확인하며 재실행 가능하게 작성.
- 정적 상세 연락 계약에도 동일 안전 정책/문구 적용. 기존 canonical·경로·주요 내용 hash의 의미 유지.
- 수락: PD01~24 중 연락/비교 관련 및 PD39~41. 등록부 로딩을 not_found로 잠깐 표시하는 경우도 실패.

### S3 — 비공개 의견 백엔드

- 새 migration `supabase/16_parent_voice.sql` 제안. 시작 시 번호 충돌 확인 후 다음 번호 사용. 기존 migration 파일을 소급 수정하지 않음.
- 테이블/RLS/관리자 감사·공개 개선 모델. anon/authenticated의 원문 직접 접근 전부 차단.
- 제안 `supabase/functions/parent-voice/`에 submit/status/delete 및 검증·제한 모듈. 서버 키 환경변수명·로컬 실행법·CORS origin·신뢰 프록시 설정을 문서화. 값은 커밋하지 않음.
- PARENT_VOICE_DESIGN의 idempotency/receipt/TTL/error 계약을 구현. 정규화·hash·비밀 비교·상태 전이는 클라이언트에 맡기지 않음.
- 운영자 상태 변경 API 또는 제한된 RPC는 DB에서 is_admin을 검사하고 허용 전이·감사 기록을 트랜잭션 처리. 원문 수정은 별도 명시 행동.
- 보관 기한 정리 작업과 테스트. 초기에는 실행 가능한 관리 명령+스케줄 설정 예제를 제공하고 자동 스케줄이 활성화됐다고 주장하지 않음.
- 수락: PD25~30/33~38/42. 로컬 DB·실제 함수 통합 결과와 순수 검증 단위 테스트를 구별.

### S4 — 의견 UI와 운영자 화면

- 신규 제안 `app/lib/data/parent_voice.dart`, `features/feedback/parent_voice_sheet.dart`, `features/admin/parent_voice_page.dart`.
- 유형 필수/메모 선택/맥락 선택, 원문 비공개 안내, 기존 정정/후기/근거 신고로의 명시적 전환.
- 미설정/네트워크 오류/입력 수정/요청 제한/전송 중/접수됨/접수증 분실/조회 실패 상태. 서버 확인 전 성공 표시 금지.
- receiptSecret은 URL/이벤트/에러 로그에 넣지 않음. 탭 보관 불가 환경에서 복사 대안, 복사 실패도 안내.
- 관리자 큐·분류·중복 연결·사유·검증 링크, 공개 개선 기록 별도 발행. 원문은 공개 컴포넌트 입력에 전달하지 않음.
- 신규 공개 개선 내역이 없을 때 빈 상태. 예시 학원·시안 의견을 운영 seed로 넣지 않음.
- 수락: PD25~30/33~38 + 폼 키보드·모달 초점/읽기 순서.

### S5 — 통합 검증과 릴리스 준비

- Flutter analyze + 변경 모델/widget 회귀, router/공용 연락 위젯이면 전체 Flutter 회귀.
- 정적 exporter 변경이면 관련 Python 회귀와 ID/canonical/연락 계약 비교. 점수 산출물 불변 확인.
- API: anon/일반 로그인/admin/잘못된 receipt 각 권한, 직접 REST 우회, 재시도 경쟁·제한·삭제·보관 정리의 실제 통합 테스트.
- 브라우저 320/375/768/1440px, 200% 확대, 키보드·스크린리더 점검·다크·reduced motion, 실제 기기 tel 실패 대안. 모의 launch 성공과 실제 통화 확인을 구별.
- 동일 네트워크/기기 조건 성능 전후 비교. 설정·스키마·플래그 rollback과 사용자 영향 기록.
- 수락 시나리오 YAML은 테스트 명세다. 실제 생산 함수·UI를 실행한 검사만 통과로 보고.

## 3. 플래그·실패·복귀

`parentOpeningEnabled`, `parentCompareEnabled`, `parentVoiceEnabled`는 **신규 제안**. 기존 feature flag 방식이 있으면 그 방식으로 구현한다. 운영 기본 off, 개발/테스트에서 on. 기존 연락 버그 수정은 플래그 없이 기존 경로도 개선해야 한다.

| 문제 | 동작 |
|---|---|
| 오프닝/비교 끄기 | 기존 탐색·상세·연락 기능 사용 가능 |
| 의견 API 미설정/장애 | 탐색 계속, 의견 접수 불가 안내, 성공 시뮬레이션 없음 |
| UI부터 먼저 배포 | API capability 없으면 voice off. 클라이언트 검증만으로 접수 허용하지 않음 |
| DB migration만 적용 | 기존 기능 영향 없음. 신규 원문 테이블은 비공개 유지 |
| 롤백 | 플래그 off/이전 앱 배포. 접수 자료 삭제를 rollback 수단으로 쓰지 않음 |

정적 공개 파일에는 의견·비밀·관리자 내역이 없어야 한다. 운영 DB migration/함수 배포는 별도 요청 시에만 실제 적용하고 검증한다. 공개 개선 발행은 실제 변경의 운영 반영 증거를 확인한 후 진행한다.

## 4. 완료 보고 형식

- 구현한 단계와 실제 변경 파일, 현재 제품 동작.
- 실행한 검사와 결과, 실패를 수정한 내용, 미실행 검사와 원인.
- 연락처/가격/개인정보/학원 ID/기존 점수 보존 여부.
- 필요한 배포 환경 설정과 기본 off인 기능, 운영 반영 여부.
- 남은 일은 구체적인 입력·설정·검사 단위로 기록. ‘전체 완료’와 ‘로컬 구현 완료’를 혼동하지 않음.

문서·시안 검토만으로 구현 완료를 선언하지 않는다. 현재는 실제 코드와 로컬 검증이 추가된 상태이며 운영 반영은 별도다.
