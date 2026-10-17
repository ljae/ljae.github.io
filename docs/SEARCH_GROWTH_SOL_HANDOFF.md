# Sol 구현 인수 문서

상태: 첫 구현 완료. 현재 범위와 검증 결과는 [구현·운영 안내](SEARCH_GROWTH_IMPLEMENTATION.md)에 기록했다. 아래 최초 인수 프롬프트와 전체 작업표는 확장 작업의 기준으로 보존한다. 2026-10-17.

## 바로 사용할 프롬프트

```text
이 저장소의 docs/SEARCH_GROWTH_DESIGN.md를 구현하라.
먼저 docs/reports/search-growth-2026-10-17.md와
docs/reports/search-growth-baseline-2026-10-17.json을 읽어 관측 사실을 확인하라.
docs/prototypes/search-growth.html은 화면/상태 참고용이며 운영 앱이 아니다.

첫 구현 범위는 S0~S2다. 현재 브랜치의 사용자 변경을 보존하고 프로젝트 지침을 따른다.
1. GSC CSV baseline을 재현하는 수입·품질 검사와 노출 급감 사건 원장을 만든다.
2. 등록부 전용 학원 상세를 지원해 정적 상세의 앱 CTA 오류를 고친다.
3. 기존 URL을 유지하면서 정적 상세 v2, 조건을 보존하는 앱 링크,
   검증된 URL alias 대장, 내용 변경 기준 lastmod를 구현한다.
현재 API 인증이 없으면 CSV로 진행하고 인증 없이 만들 수 있는 작업을 끝낸다.

학원 점수/순위 산식과 근거 판정 규칙은 검색 성과로 변경하지 않는다.
미확인 학년·비용·연락처·후기를 추측해서 채우지 않는다.
이미 색인된 /a/{id}.html을 일괄 변경·삭제·noindex하지 않는다.
GitHub Pages의 200 canonical 호환 페이지를 HTTP 301이라고 부르지 않는다.
GSC 전체 총계와 query/page 차원 합계를 섞지 않는다.
현재 3개월 내보내기의 페이지 1000행은 상한 도달 자료다.

각 단계별 의미 있는 회귀 테스트를 통과시키고 Ego Lite로 정적→앱 동선을 확인하라.
검증 결과, 남은 운영 인증/배포 의존성, 다음 단계 범위를 보고하라.
이번 프롬프트만으로 운영 배포·데이터 공개·색인 요청을 수행하지 않는다.
```

## 읽을 파일 순서

1. [실측 보고서](reports/search-growth-2026-10-17.md): 무엇이 사실이고 무엇이 가설인지.
2. [상세 설계](SEARCH_GROWTH_DESIGN.md): 데이터 계약·규칙·화면·배포·테스트.
3. [화면 시안](prototypes/search-growth.html): 운영자 현황·과제 패널·등록부 상세·탐색 흐름.
4. `pipeline/seo.py`, `app/lib/features/academy/academy_page.dart`, `app/lib/core/router.dart`, `app/lib/data/repository.dart`, `app/lib/widgets/app_shell.dart`.
5. `supabase/09_admin_review.sql`, `.github/workflows/deploy.yml`, `docs/PROFILES.md`, `docs/AGENTS.md`, `CLAUDE.md`의 관련 규칙.

## 먼저 해결할 재현 사례

| ID | 현재 상태 | 완료 조건 |
|---|---|---|
| G-001 | 09-03 노출 급감, 원인 미확정 | 사건 전후 집계와 반증/미확인 항목을 함께 기록 |
| G-002 | 한선영어학원 CTA → 앱 not_found | 등록부 데이터로 상세 표시, 새 점수·학년 생성 없음 |
| G-003 | 원웅재물리전문학원도 등록부 전용 | ID `3000054900`을 직접 열어 실제 공시 정보 제공 |
| G-004 | 404 214개 중 93개 identity 연결 후보 | 후보 보고서, 검증한 URL만 호환 처리, 루프/충돌 검사 |
| G-005 | 목동 허브가 bare `/#/rank`로 이동 | 명시된 region/subject/band 복원 및 새로고침 테스트 |
| G-006 | 모든 상세 설명이 교습비 확인 약속 | 가격이 없는 상세의 title/description에 가짜 약속 없음 |
| G-007 | `arts/general` 정적 표시 사전 누락 | 한국어 과목/미확인 의미를 공통 계약으로 표시 |
| G-008 | 매 빌드 전체 lastmod 갱신 | 같은 주요 내용 재빌드 시 날짜 고정 |

`G-002`에서 `registryProvider` 로딩 중 not_found가 잠시 보이는 구현도 실패다. 등록부 정보를 Academy 점수 모델의 0점 객체로 위장하지 않고 별도 detail view model로 표현한다.

## PR 단위 작업표

| PR | 구현 범위 | 변경 예상 위치 | 수락 조건 |
|---|---|---|---|
| 1 | CSV ingest / baseline / 데이터 품질 | `pipeline/growth/`, fixtures | 121/5439, 5/188 재현; 기간 grain/멱등성/상한 처리 |
| 2 | 공개 상세 계약 / 등록부 resolver | `public_page_model.py`, `academy_detail.dart`, AcademyPage/Search | 직접 진입·검색·로딩·오류·없는 ID 구분 |
| 3 | URL inventory / alias 후보 / manifest | `inventory.py`, alias 대장, `seo.py` | 승인된 매핑만 반영, 현재 URL 유지, 의도치 않은 삭제 차단 |
| 4 | 정적 상세 v2 / 사실 기반 메타 / CTA | `seo_templates/`, `seo.py` | JS 없이 핵심 정보·다음 행동, 실제 source 상태 보존 |
| 5 | 조건 링크 / 브라우저 history | router, Selection, 정적 허브 | 목동/트랙/학교 문맥 복원, admin 로그인 복귀 보존 |
| 6 | lastmod / sitemap / 배포 검증 | `seo.py`, deploy workflow | 의미 hash 기준, private growth 데이터 배포 제외 |
| 7 | GSC API / Postgres / RLS | `gsc.py`, `store.py`, 새 SQL, 독립 CI | 완결 partition·재시도·토큰 격리·anon 접근 차단 |
| 8 | 운영자 현황·과제·페이지 | `admin/growth`, `data/growth.dart` | coverage/stale/불확실성, 서버 pagination |
| 9 | 조사 우선순위 / 관련 링크 / 허브 | growth rules, 조사 큐 adapter, templates | GSC를 조사 힌트로만 사용, 랭킹 입력 불변 |
| 10 | 이벤트 / 실험 / 판정 | analytics adapter, experiments | 중복 제거·같은 분모·표본 부족·배포 연결 |

PR 1~6이 첫 구현 묶음이다. 각 PR의 규모는 실제 코드 확인 후 쪼개도 되지만 수락 조건은 유지한다. 첫 공개 파일럿 URL 20개는 최신 데이터에서 선별한다. 과거 상위 검색어를 현재 활성 수요로 취급하지 않는다.

## 보존해야 할 숫자와 한계

- 전체 실측 08-21~10-14: 클릭 121, 노출 5,439.
- 최근 28일 09-17~10-14: 클릭 5, 노출 188.
- 전체 검색어 표: 286행/8클릭/1,355노출. 최근: 12행/0클릭/13노출.
- 전체 페이지 표: 1,000행으로 제한. 최근: 111행.
- 색인 보고 기준 10-12: 5,649 indexed, 319 not indexed, 214 not found.
- 현재 등록부 전용 2,483개. 과거 유입 데이터와 조인한 현재 위험 범위이며 과거 실제 오류 발생 수가 아니다.
- 09-03 전후 404 시계열 증가 없음. 이 사실을 지우고 “404가 급감 원인”이라고 보고하면 안 된다.
- API 권한이나 analytics 운영 설정은 이번 조사에서 준비하지 않았다.

## 데이터와 검증

원본: `pipeline/.cache/search-growth/2026-10-17/` (Git 제외).

파일: `performance-3m.zip`, `performance-28d.zip`, `index-404.zip`, 해제 CSV, URL 검사/상태 기록, `url-migration-candidates.json`, `http-checks.json`.

이 디렉터리가 다른 머신에 없으면 원본 존재를 가정하지 않는다. 공개 보고서의 수치 원장으로 합성 fixture를 만들고, 실수집 결과로 가장하지 않는다. 원본 검색어를 테스트 fixture에 통째로 커밋할 필요는 없다.

Python 변경은 `python -m pytest`로 해당 계약과 기존 관련 회귀를 확인한다. Flutter 변경은 `flutter analyze`, 관련 widget/router 테스트, 기존 회귀, release web build를 확인한다. 명령은 저장소에 실제 설치된 인터프리터/Flutter 경로로 실행한다.

Ego Lite 브라우저 검증: 정적 한선 상세 → 앱 상세, 등록부 검색 → 상세, 목동 허브 → 조건이 적용된 탐색, 390px 화면, 없는 ID, 뒤로가기. 콘솔 조회나 로컬 빌드만으로 배포 완료라고 하지 않는다.

## 완료 보고 형식

```text
완료 범위: Sx / PR 범위
사용자 변화: 실제 진입 URL과 이전/이후 동작
수치 검증: baseline과 ingestion 품질
회귀 검증: 실행한 테스트와 결과
운영 상태: 로컬 / PR / 배포 및 확인 SHA
남은 의존성: 인증·원본·실사용 표본 등 확인된 항목만
다음 단계: 상세 설계의 S번호
```
