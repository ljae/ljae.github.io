# 학부모 의사결정 V2 구현·운영 안내

2026-10-18 · **제품 코드·서버 구성 완료, 웹 릴리스 검증 중**. 최종 운영 반영은 [배포 검증 기록](reports/parent-v2-deployment-2026-10-18.md)을 따른다.
[설계](PARENT_DECISION_DESIGN.md) · [의견 계약](PARENT_VOICE_DESIGN.md) · [구현 검증 기록](reports/parent-v2-implementation-2026-10-18.md)

비교 화면의 후속 변경·검증은 [정보의 의미 개선 기록](reports/parent-comparison-meaning-2026-10-18.md)에 정리했다.

## 구현된 범위

- Flutter ‘우리 아이의 다음 장’ 오프닝, 선택/해제 가능한 고민과 문의 질문 연결. 지역·과목·학년·이름 검색, 기존 상세 직접 유입 유지.
- 공개 ID 최대 3개 비교, 기기 내 선택 보관·초기화, 공개 ID만 담은 비교 링크. 모바일에서는 같은 비교 항목 아래에 후보를 순서대로 배치.
- 평가/등록부 공통 연락 adapter. 안전한 전화·공식 홈페이지, 번호·질문 복사, 실행/클립보드 실패 대안. 필드별 출처 충돌은 해당 행동을 보류. 기존 자료에는 대조일이 없어 날짜를 생성하지 않음.
- 학부모 일반 의견 비공개 접수와 접수증 상태/삭제. 서버 확인 전 성공 표시 없음. 요청 재시도 멱등성, 입력 제한·익명 직접 접근 차단·요청 제한.
- `/admin/parent-voice`: 비공개 의견 큐, 사유·상태 전이·버전 충돌 검사·중복 연결. 수정·검증 완료 의견에 대해 운영 확인을 명시한 뒤 별도로 공개 개선 기록 발행.
- 기존 정정 폼·근거 신고·로그인 후기 경로 재사용. 학원 상세의 의견 창에서 정보 정정·수강 후기 폼으로 직접 이동. 근거 신고는 해당 원문을 선택해 기존 신고 버튼 사용.
- 예산 입력·가격 비교·가격순·비용 적합 판정 없음. 기존 점수·게이트·자료 자산은 변경하지 않음. 비용 질문에 후기의 가격 평가를 답처럼 덧붙이던 기존 체크리스트도 제거.

비교 후속 개선은 과목·학년/관심사 선택 → 대상 반 자료 → 진도·피드백/숙제/입학 준비의 실제 발췌와 선택 관점 → 통학 → 지점별 문의 순서다. 근거 건수만 보여주던 칸을 원문·작성일·과목·학년이 붙은 내용으로 바꾸었다. 모두 자료가 없는 항목은 공통 질문으로 묶고, 개별 문의 복사에는 실제 읽은 자료를 연결한다. `parent_comparison.dart`의 읽기 전용 projection은 원본 데이터·점수·수집 게이트를 수정하지 않는다. 기존 AI 요약을 검증 사실로 복제하지 않는다. P1 조건 엔진·가족 공유는 이번 범위 밖이다.

## 로컬 실행

```sh
cd app
flutter run -d chrome \
  --dart-define=PARENT_OPENING_ENABLED=true \
  --dart-define=PARENT_COMPARE_ENABLED=true \
  --dart-define=PARENT_VOICE_ENABLED=true
```

코드의 플래그 기본값은 세 개 모두 false이며, 운영 `deploy.yml`은 테스트와 빌드에서 세 기능을 명시적으로 켠다. Supabase 설정이 없으면 공개 탐색·비교는 동작하고 의견 전송은 준비 중 상태다. 의견 UI에 성공 시뮬레이션이나 예시 접수를 넣지 않았다.

웹 빌드는 같은 플래그를 `flutter build web`에 전달한다. 빌드 산출물은 `app/build/web/`에 생성되며 Git에 포함하지 않는다. 정적 검색 랜딩은 기존 Python exporter로 생성한다.

## 의견 접수 환경 구성

### 1. 스키마

기존 09/14 스키마와 `is_admin()`이 있는 데이터베이스에 `supabase/16_parent_voice.sql`을 적용한다. SQL Editor 또는 기존 관리용 migration 절차를 사용한다. 현재 저장소의 SQL은 루트에 순서대로 놓여 있으므로 `supabase db push`만으로 기존 파일들이 자동 적용된다고 가정하지 않는다.

운영 적용 전 실제 `academy_actions` check 이름/허용 값을 확인한다. 저장소 선언 이름은 `academy_actions_action_check`다. 16은 homepage 허용을 추가하며 과거 reserve 행을 보존한다. 같은 파일의 재실행은 로컬 PostgreSQL에서 검증했다. 2026-10-18 실제 제약을 조회한 뒤 운영 DB에 16을 적용했다.

비공개 테이블: `parent_feedback`, `parent_feedback_audit`, `parent_improvement_feedback`, `parent_voice_limits`. anon/authenticated 직접 원문 접근은 GRANT/RLS로 차단한다. 관리자는 `is_admin()`을 검사하는 RPC로만 큐·상태를 다룬다. 접수 비밀은 서버에 SHA-256으로만 저장한다.

### 2. Edge Function

엔트리: `supabase/functions/parent-voice/index.ts`. 요청/본문/오류 원문을 로깅하지 않는다. `supabase/config.toml`의 해당 함수는 `verify_jwt=false`다. 익명 접수는 함수 내부의 입력·요청 제한으로, 상태/삭제는 접수증 비밀로 제어한다. 관리자 처리는 이 공개 함수가 아닌 인증된 DB RPC다. [Supabase 함수 설정](https://supabase.com/docs/guides/functions/function-configuration)

서버 전용 설정:

| 이름 | 설정 |
|---|---|
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | Edge 런타임의 서버 환경. 앱 번들·문서·로그에 값을 넣지 않음 |
| `PARENT_VOICE_ENABLED` | 운영 준비와 검증을 마친 뒤 `true` |
| `PARENT_VOICE_ORIGINS` | 실제 앱 origin의 쉼표 목록, 예: `https://openedu4u.com`. 개발 origin은 별도 환경에서만 추가 |
| `PARENT_VOICE_RATE_SECRET` | 서버의 CSPRNG로 만든 32자 이상의 전용 비밀. 코드·저장소 밖에서 관리 |
| `PARENT_VOICE_TRUSTED_IP_HEADER` | 게이트웨이가 덮어쓰는 것이 확인된 단일 IP 헤더 이름. 기본값 없음 |

IP 헤더는 배포 환경에서 위조 입력이 제거/덮어쓰기 되는지 확인하고 설정한다. 임의의 X-Forwarded-For 첫 값을 선택하지 않는다. 현재 구현은 쉼표가 든 체인이나 형식 불명 값을 거부한다. 보장된 단일 헤더가 없다면 신뢰 프록시에서 정규화해야 한다. 설정이 없거나 제한 저장소가 실패하면 503으로 접수를 보류한다.

이 값들은 서버 비밀 설정으로 주입한다. 기능 배포 명령은 프로젝트 연결 후 `supabase functions deploy parent-voice --project-ref YOUR_PROJECT_REF --use-api --no-verify-jwt`. 2026-10-18 운영 함수와 서버 설정을 적용하고 실 API로 접수·상태·삭제 및 익명 권한 차단을 확인했다. 허용 origin은 `https://openedu4u.com`, 단일 IP 헤더는 `cf-connecting-ip`다. 운영 게이트웨이의 이 헤더 위조 차단(403)을 확인했으며, 클라이언트가 바꿀 수 있는 X-Forwarded-For 체인은 사용하지 않는다. 임시 진단 함수·비밀은 검증 후 제거했다.

### 3. 앱 연결

서버 준비 뒤 기존 `SUPABASE_URL`, `SUPABASE_ANON_KEY` 공개 설정과 `PARENT_VOICE_ENABLED=true`로 앱을 빌드한다. 서버의 service key는 앱에 넣지 않는다. 앱은 `functions.invoke('parent-voice/submit')`을 사용한다. `status/delete` 비밀은 JSON 본문에만 담고 URL·분석 이벤트로 보내지 않는다.

의견 초안과 재시도 요청은 메모리에만 둔다. 접수증은 sessionStorage에 보관하고 실패하면 메모리·복사 대안을 안내한다. 현재 웹 외 플랫폼의 저장 adapter는 메모리 보관이므로 앱 종료 후 복원이 필요하면 별도 플랫폼 저장소를 도입해야 한다. 개인 초안을 기기 저장소에 쓰는 기능은 없다.

### 4. 운영과 보관 정리

운영자가 `/admin`에서 로그인한 뒤 ‘학부모 의견 관리’로 이동한다. 일반 계정에는 관리 RPC도 접근을 허용하지 않는다. 상태는 접수→검토→계획→개선 중→수정·검증 완료, 보류/중복 및 재검토 전이를 지원한다.

공개 발행은 완료된 의견만 가능하며 제목·요약·커밋·배포 식별자·실제 확인한 운영 URL과 확인 시각을 요구한다. ‘운영 화면 확인·공개 검수’ 선택도 필요하다. 프로그램이 원격 배포 내용을 자동 인증하는 기능은 아니며 담당자가 직접 확인한 증거를 남기는 절차다. 학부모 원문을 자동 공개하지 않는다.

`parent_voice_cleanup()`은 원문/맥락/내부 메모를 90일 뒤 정리하고, 접수·접수증 해시는 180일 뒤 삭제한다. 제한 카운터는 24시간 뒤 정리한다. 접수증 삭제는 즉시 본문·맥락·비밀 해시를 제거하며 공개 비식별 개선 기록은 유지한다. 감사 표에 본문을 중복 저장하지 않는다.

서버에서 다음 작업을 하루 한 번 스케줄한다. 스크립트는 설정된 관리용 환경만 사용하며 반환된 정리 건수만 출력한다.

```sh
deno run --allow-env=SUPABASE_URL,SUPABASE_SERVICE_ROLE_KEY --allow-net scripts/parent_voice_cleanup.ts
```

`.github/workflows/parent-voice-maintenance.yml`은 기존 서버용 GitHub Secrets로 매일 10:10 KST 정리 RPC를 실행한다. 스케줄은 main 반영 이후 적용되며 최초 실행 결과는 배포 검증 기록에 남긴다. 호스팅 플랫폼의 access log/백업 보관 정책은 별도 운영 설정이다. DB 삭제가 모든 백업의 즉시 삭제를 의미하지 않는다.

## 검증과 복귀

### 다학원 비교 글

`app/assets/research/comparison_articles.json`은 학원 점수·후기 대장과 분리된 수동 검토 링크 목록이다. 현재 공개 본문을 확인한 4편을 연결하며, 모든 학원 조합에 글이 있는 것은 아니다. [조사·연결 판단](reports/parent-comparison-articles-2026-10-18.md)을 함께 읽는다.

- 필수 메타: `id/title/url/author/publishedAt/reviewedAt/subject/gradeBands/status/access/reviewMethod/reason/scopeNote/experienceNote`.
- 학원별 `academies`: `academyId`는 현재 정본 ID, `label`은 글에서 부른 대상, `mapping`은 `address`(주소 대조)/`regional_brand`(지역·브랜드)/`brand`(브랜드만), `locator`는 실제 읽을 본문 절, `criteria`는 그 학원에 대해 설명한 비교 축이다. 브랜드 연결은 검토자가 지정한 ID에만 연결하며 다른 지점으로 확장하지 않는다.
- 축: `curriculum/feedback/homework/atmosphere/entry/routine`. 보여줄 모든 학원에 공통 축 2개 이상이 있어야 한다. 이름 나열·짧은 회상만 있는 대상은 포함하지 않는다. 3곳에 공통 축이 부족하면 3곳 비교로 발행하지 않는다.
- `reviewed/public/full_text`만 공개한다. 검색 발췌만 확인하면 `candidate`, 삭제·로그인·접근 불가로 바뀌면 `access`를 갱신하거나 `status=withdrawn`으로 철회한다. 런타임 링크 상태 자동 점검기는 없다. 정기 검토 및 링크 오류 제보 처리에서 본문을 다시 확인하고 실제 확인일만 갱신한다.
- 학년이 알려진 글은 다른 학년에서 제외한다. 빈 `gradeBands`는 **학년 미확인**이다. 작성 후 2년이 지난 글은 과거 자료임을 표시한다. `reviewedAt`은 학원의 최신 운영 확인일이 아니다.
- 전체 3곳/일부 2곳 범위를 표시하고 빠진 학원 이름을 보여준다. URL 추적·모바일 변형은 중복 제거한다. 주소/브랜드 범위, 수강 경험과 조사 내용, 협찬 여부 미확인을 공개한다.
- 링크 카드와 항목별 읽기 링크로만 사용하며 글의 주장을 학원별 현재 사실·평가점수로 옮기지 않는다. 원문 전체·금액·성별 고정관념을 재게시하지 않는다. 비용은 기존 직접 문의 질문에서만 다룬다.
- 로딩 실패는 다시 시도, 검토한 글 없음은 공백 안내로 구별한다. 원문 열기 실패 시 링크 복사를 제공한다.

실행 회귀: `app/test/comparison_articles_test.dart`와 `scripts/check_parent_comparison_articles_web.cjs`. Playwright 환경 변수는 아래 비교 검사와 같다.

### 실행 검사

- Flutter: `flutter analyze`, 전체 `flutter test`. 활성 플래그 회귀 명령에도 위 세 dart-define을 전달한다.
- Python: `.venv/bin/python -m pytest pipeline/tests/test_search_pages.py pipeline/tests/test_parent_contact.py -q`.
- Edge: `deno check supabase/functions/parent-voice/index.ts scripts/parent_voice_cleanup.ts`.
- HTTP+PostgreSQL: `pipeline/tests/parent_voice_sql_test.mjs` 머리말의 명령. PGlite/tsx는 별도 임시 테스트 설치이며 운영 의존성이 아니다.
- 웹 실제 빌드 검사: `scripts/check_parent_v2_web.cjs`. 로컬 서버의 V2 활성/미설정 Supabase 빌드를 대상으로 한다. `PARENT_V2_WEB_URL`(기본 localhost:8769), `PARENT_V2_PLAYWRIGHT_MODULE`(설치된 playwright), `PARENT_V2_CHROME`(설치된 Chrome 실행 파일), `PARENT_V2_ARTIFACT_DIR`(결과 폴더)를 지정할 수 있다. 기본 Chromium을 쓸 때는 Playwright 브라우저 설치가 필요하다.
- 비교 내용 회귀: `app/test/parent_comparison_test.dart`는 원문 차이·선택 관점·과목/학년/지점 범위·금액 제외·공통 공백·200% 글자를 검사한다. `scripts/check_parent_comparison_web.cjs`는 위와 같은 브라우저 환경 변수로 실제 두 학원의 발췌, 학년 변경, 개별 질문 복사를 확인한다.
- 운영 연결 검사: `scripts/check_parent_release_web.cjs`. `PARENT_V2_VERIFY_VOICE=true`를 명시하면 합성 의견 1건을 실제로 접수·조회·삭제한다. 기본 대상은 운영 도메인이며 `PARENT_V2_PREVIEW_URL=http://127.0.0.1:8769/`를 주면 로컬 산출물만 운영 origin 아래 프록시한다(API는 실제 운영). 접수 비밀·원문은 결과 파일에 저장하지 않는다. 실패 시에도 생성한 합성 의견을 삭제한다. 204 삭제 응답은 `parent_voice_transport_test.dart`가 실제 Supabase SDK 경유로 회귀 검사한다.
- 반례 YAML은 명세이며 실행 테스트가 아니다. 실제 실행 결과와 수동 확인 한계는 보고서에 기록한다.

오프닝/비교/의견은 플래그를 끄면 기존 탐색으로 돌아간다. 기존 연락처 안전성 개선은 플래그와 무관하게 적용된다. 앱을 이전 버전으로 되돌려도 새 비공개 테이블은 비공개로 유지하고 접수 자료를 삭제하지 않는다. DB/함수 장애가 공개 학원 탐색을 막지 않도록 분리했다.
