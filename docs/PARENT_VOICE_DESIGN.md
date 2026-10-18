# 학부모의 소리 — 접수에서 개선 기록까지

2026-10-18 · V2 · **V2 계약 / 코드·로컬 검증 완료, 운영 적용 전**. [구현·운영 안내](PARENT_DECISION_IMPLEMENTATION.md). [전체 설계](PARENT_DECISION_DESIGN.md) · [Sol 인계](PARENT_DECISION_SOL_HANDOFF.md)

## 1. 무엇을 듣는가

학원 평점을 하나 더 받는 기능이 아니라, 학부모가 탐색·비교·문의 과정에서 겪는 문제를 듣는다. 상시 익명 의견만으로 전체 학부모의 수요 순위를 추정하지 않는다. 유입 경로·응답률·표본 편향을 함께 보고, 인터뷰와 실제 과제 관찰로 보완한다.

| 입구 | 처리 경로 | 사용자에게 먼저 알릴 내용 |
|---|---|---|
| 사이트 이용 의견 | 신규 비공개 parent_feedback | 로그인·연락처 없이 가능, 원문 비공개, 모든 제안을 반영한다는 약속 없음 |
| 학원 정보 정정 | 기존 corrections | 기존 폼은 회신 연락처 필요. 단순 의견을 이 폼으로 강제 이동하지 않음 |
| 다른 학원 글/광고/오래된 근거 | 기존 evidence_reports | 해당 근거에 대한 검토 요청이며 자동 삭제가 아님 |
| 실제 수강 경험 | 기존 user_reviews | 로그인과 현재 후기 운영 규칙 적용. 서비스 의견을 후기로 자동 게시하지 않음 |

처음에는 길을 고르게 하되 서비스 의견이 기본이다. 정정/후기 전환은 사용자의 선택으로만 하고 이미 쓴 문장을 자동으로 이중 제출하지 않는다.

## 2. 화면 흐름

1. 전역 ‘학부모의 소리’, 비교 하단의 ‘어떤 정보가 더 필요했나요?’로 연다. 자동 전면 팝업 없음.
2. 필수 유형 하나: `정보가 부족해요 / 찾거나 비교하기 어려워요 / 연락 경로가 불편해요 / 이런 기능이 필요해요 / 기타`.
3. 선택 메모 400자, 현재 페이지 맥락을 붙일 경우 화면에 표시하고 끌 수 있게 함. 기타도 메모 강제하지 않음.
4. “아이 이름·학교 반·전화번호·이메일 등 개인 정보는 적지 마세요. 내용은 운영팀만 확인합니다.” 안내. 전송 전에 공개 범위를 알린다.
5. 서버 접수 성공 뒤만 ‘의견을 접수했습니다’. 접수증은 이번 탭에 보관하며 ‘확인 코드 복사’ 선택 행동 제공. 탭 종료 시 잃을 수 있음을 알린다. 연락처를 대신 수집하지 않음.
6. 접수증으로 상태와 검수된 짧은 처리 사유 확인. ‘검토 중’은 반영 예정이 아니다. 거절·중복도 이유를 설명한다.
7. 공개 ‘학부모 의견으로 바뀐 것’에는 운영자가 작성한 개선 요약·적용일·변경 링크만 표시한다. 실제 공개 기록이 없으면 빈 상태. 원문 인용·가짜 이용자 수·실시간 의견 벽 없음.

노출 빈도: 능동 링크는 항상 사용 가능. 인라인 권유는 한 세션에 한 번, 닫으면 세션 동안 재노출하지 않는다. 전화 클릭 후 자동으로 상담 만족도를 묻지 않는다. 연결·상담 여부를 알 수 없기 때문이다.

UI 상태: `idle → validating → submitting → received`, 실패는 `needs_edit / rate_limited / retryable_error / unavailable`. 네트워크 실패 때 입력 유지, 닫기 전에 삭제 여부를 명확히 표시. 중복 클릭 중에는 제출 잠금, 재시도는 동일 request_id 사용. 공급자 설정이 없으면 ‘현재 의견 접수를 준비 중입니다’와 기존 안내 경로를 표시하며 로컬 성공을 꾸미지 않는다.

## 3. 쓰기 경계와 API 제안

기존 corrections는 academy_key·contact·10자 이상 본문을 요구한다. 일반 의견을 받기 위해 그 제약이나 RLS를 느슨하게 하지 않는다. 새 비공개 테이블과 Supabase Edge Function을 제안한다. 전용 SQL·함수·클라이언트를 구현했다. 배포 설정과 실제 환경의 IP 헤더 신뢰 경계 확인은 운영 적용 전에 필요하다.

- 브라우저 → HTTPS Edge Function → 제한된 입력 검증 → DB 트랜잭션.
- anon/authenticated의 parent_feedback 직접 SELECT/INSERT/UPDATE/DELETE는 차단. RLS와 GRANT를 함께 검증. 서비스 키는 함수 서버에만 둔다.
- 운영자는 기존 `is_admin()` 검증을 통과한 요청으로만 접근. 관리자 판정을 클라이언트 플래그로 하지 않는다.
- 접수증 조회/삭제는 공개 목록 API와 분리. 입력 내용·비밀값을 로그·분석·URL에 쓰지 않는다.

### 신규 엔드포인트 계약

| 경로(제안) | 입력 | 결과 |
|---|---|---|
| POST /functions/v1/parent-voice/submit | requestId, receiptSecret, category, note?, context? | 최초 201, 같은 요청 재시도 200: receiptId, status=received, createdAt |
| POST /functions/v1/parent-voice/status | receiptId, receiptSecret | 200: status, safeResolution?, updatedAt. 원문·내부 메모·다른 ID 노출 없음 |
| POST /functions/v1/parent-voice/delete | receiptId, receiptSecret | 유효 접수증이면 204. 본문·맥락·비밀 해시 삭제, 최소 비식별 감사만 유지 |

requestId는 클라이언트 UUID. receiptSecret은 CSPRNG 32바이트를 base64url로 표현한 43자 문자열. requestId는 비밀이 아니며 그 자체로 조회할 수 없다. 제출 전에 생성하고 성공 시 receiptId와 함께 sessionStorage에 저장한다. 저장이 막히면 메모리 유지+복사 대안을 제공한다. 원문 초안은 sessionStorage에 저장하지 않는다.

서버는 receiptSecret의 SHA-256만 저장한다. 원문 비밀을 반환하거나 로그로 남기지 않는다. 접수 ID와 비밀 쌍을 검증하고, 틀린 쌍·없는 ID는 같은 404로 응답한다. 상태/삭제도 제한을 적용한다. JSON body로 보내고 쿼리 문자열을 쓰지 않는다.

멱등성: requestId unique + 정규화 payloadHash + secretHash를 트랜잭션에서 대조한다. 같은 ID·같은 본문·같은 비밀이면 같은 결과, 같은 ID·다른 값이면 개인정보 없는 409. 타임아웃 후 재시도도 이 규칙. 422 등 접수되지 않은 입력을 고친 경우 새 requestId 생성. 내용이 같은 다른 사람의 요청을 지우지 않는다. 이는 요청 중복 억제이며 사람당 1표 인증이 아니다.

오류: 413 크기 초과, 422 입력 수정, 429 재시도 간격, 503 일시 장애. JSON에 code/message/retryable만 제공하고 DB 오류·내부 쿼리는 숨긴다. 제출 응답이 유실되었으면 같은 요청으로 재시도하게 한다.

### 입력 allowlist

```json
{
  "requestId": "UUID",
  "receiptSecret": "CSPRNG_32_BYTES_BASE64URL",
  "category": "missing_info",
  "note": "선택한 학원을 나란히 보고 싶어요.",
  "context": {"pageType": "compare", "academyId": null}
}
```

category: `missing_info | discovery_compare | contact | feature_request | other`.
pageType: `home | search | compare | academy | other`.
context는 선택 사항. academyId는 실제 알려진 ID와 대조한다. 페이지 전체 URL·검색어·referrer·학년/학교/좌표는 전송하지 않는다. 추가 필드 reject. note는 Unicode code point 기준 최대 400자, 공백 정규화. 요청 전체 UTF-8 8KB 이하. 빈 note는 허용한다.

이메일·전화번호처럼 명확한 개인 식별 내용은 서버에서 입력 수정 요청을 반환하고 원문을 저장하지 않는 기본 검사를 제안한다. 모든 개인 정보를 자동 식별할 수 있다는 보장은 없다. 자유서술은 관리자에게만 보이고, 공개 요약은 별도 검수를 거친다. HTML로 렌더링하지 않으며 링크·스크립트·프롬프트 명령은 데이터로만 취급한다.

## 4. 저장 계약과 악용 억제

parent_feedback 제안 필드:
`id, request_id(unique), receipt_secret_hash, payload_hash, category, note, page_type?, academy_id?, status, created_at, updated_at, owner?, internal_resolution?, safe_resolution?, duplicate_of?, task_ref?`.

`parent_feedback_audit`에는 상태 변화와 담당·시각·사유를 기록한다. 본문을 중복 저장하지 않는다. `parent_improvements`는 별도 공개 모델로 `id, title, summary, published_at, change_ref, verified_at`만 제공한다. 원문/접수 ID 연결은 비공개 관계 테이블에 둔다. 일반 사용자는 공개된 개선 기록만 읽을 수 있다.

초기 제한 제안(운영 후 조정): IP를 서버 비밀키로 HMAC한 단기 키로 제출 10분당 5회, 조회/삭제 10분당 30회. 프록시가 신뢰하는 원본 IP만 사용하고 임의 X-Forwarded-For를 신뢰하지 않는다. 키/카운터 TTL 24시간, 원 IP는 앱 DB에 저장하지 않는다. 공유 네트워크 오차를 감안한 안내·조정 경로를 둔다. CORS는 접근 권한 검증의 대체물이 아니다.

서버 전체 유입 상한과 경보도 배포 설정으로 둔다. 제한 저장소 장애 시 신규 의견은 503, 공개 탐색은 계속 작동. 숫자 제한·보관기간은 법적 기준을 주장하는 값이 아니라 초기 운영 제안이다. 호스팅 플랫폼 자체 로그 보관 설정도 별도 점검한다. CAPTCHA는 실제 악용 증거가 생기면 접근성 대안과 함께 검토한다.

제안 보관: 원문·맥락은 접수 후 90일 뒤 삭제/비식별화, 상태 조회용 비밀 해시와 최소 상태는 180일 후 삭제. 공개 개선 기록은 원문 없이 보존. 기한 작업과 실제 삭제 검증이 구현 완료 조건이다. 삭제 요청 시 먼저 원문·맥락·비밀 해시를 제거하고 외부 화면의 안전한 개선 기록만 유지할 수 있음을 알린다. 본문이 남은 로그/백업이 없는지는 호스팅 보관 정책과 함께 검토하며 즉시 완전 삭제를 약속하지 않는다.

## 5. 운영과 에이전트 연결

상태: `received → triaged → planned → in_progress → resolved`, 또는 `triaged → declined/duplicate`. 잘못 분류된 경우 사유와 이력을 남겨 triaged로 되돌릴 수 있다. resolved는 수정·검증이 끝난 경우다. public publish는 별도 행동이며 자동으로 실행하지 않는다.

초기 운영안: 운영자 한 명이 주 2회 큐를 검토한다. 이는 내부 계획이며 사용자 응답 기한 약속이 아니다. 큐 적체·처리 시간으로 인력과 빈도를 조정한다. 연락 불능·정보 오귀속·개인정보 노출은 우선 확인하고, 잦은 요구만으로 덜 알려진 지역의 문제를 밀어내지 않는다.

1. `parent-insight-researcher`: 접근 권한이 있는 익명화 의견 묶음을 읽고 문제 유형·반례·누락 맥락을 보고. 운영 원문을 Git에 쓰지 않는다.
2. `decision-planner`: 개선 과제와 기준, 기존 신고 담당 연결을 제안. 수신 의견을 검증된 학원 사실로 바꾸지 않는다.
3. 기존 gate 담당/`decision-engineer`/`app-reviewer`: 요청된 변경 구현. 의견 그 자체로 점수·게이트 정답을 바꾸지 않음.
4. `decision-quality-verifier`: 코드/데이터/화면의 실제 결과 검증. 동일 역할 자체 점검은 독립 검증이라고 부르지 않음.
5. 운영자: 검수된 개선 요약을 공개. 사용자 입력을 그대로 출력하거나 AI가 자동 답변·학원에 전달하지 않음.

별도 상시 에이전트 서버를 만들지 않는다. 상태 변경·공개는 인증된 운영자 행동이다. 에이전트는 원인 분류·작업·검증을 돕는 개발 역할이다.

## 6. 판단 지표와 반증

- 노출→폼 시작→서버 접수 완료의 비율. 분모 정의와 수집 동의를 운영 정책에 맞춰 명시한다.
- 접수에서 첫 검토까지 시간, 7일 이상 미검토 수, 잘못 분류된 비율, 개선 후 같은 문제 재발.
- 익명 요청 수는 고유 학부모 수가 아니다. 의견 건수·좋아요로 학원 순위나 교육 품질을 계산하지 않는다.
- 자유서술·접수 ID·비밀값·전화번호는 analytics에 보내지 않는다. 이벤트는 allowlist(page_type, category, result_code)만 쓴다.
- 의견 없음은 만족의 증거가 아니다. 빈 큐를 보여주기 위해 예시 후기를 운영 데이터로 채우지 않는다.

필수 검증: 비관리자 목록 차단, 다른 접수증 조회 차단, 재시도 중복 방지, 전송 실패 때 입력 보존, 비밀 로그 누출 없음, 삭제/보관 기한, 스크립트 텍스트 처리, 원문 없는 공개 개선 기록, 구현되지 않은 백엔드의 허위 성공 없음.
