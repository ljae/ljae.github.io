# 설정 체크리스트

지금 상태에서도 앱과 웹은 **완전히 동작합니다**(샘플 데이터 모드).
아래 단계를 밟으면 실제 데이터로 전환됩니다. 순서대로 하지 않아도 되고,
하나씩 켤 때마다 그 부분만 실데이터로 바뀝니다.

현재 상태 확인:

```bash
python3 pipeline/run.py --check
```

---

## 1단계 — NEIS 학원 데이터 (가장 먼저, 가장 중요)

학원의 이름·주소·정원·교습비·등록상태가 여기서 옵니다.
**투명성 점수(25%) 전체가 이 데이터에 걸려 있고**, 학원이 "공식 검증" 배지를
받는 근거도 이것뿐입니다.

인증키 발급·조회: **https://open.neis.go.kr/portal/myPage/actKeyPage.do**

1. 위 주소로 이동 (로그인 필요 — 없으면 회원가입, 무료)
2. **인증키 신청** 클릭
3. 신청서 작성
   - 활용 목적: `학원 정보 조회 서비스`
   - 활용 구분: `웹사이트 개발`
4. 발급된 인증키 복사 — 심사 없이 즉시 발급됩니다

같은 페이지에서 이미 발급받은 키를 다시 확인하거나 재발급할 수 있습니다.

> 키 없이도 하루 1,000건까지 호출되지만, 4개 학군을 다 훑으려면 부족합니다.

---

## 2단계 — 네이버 검색 API (평판 35% · 화제성 20%)

### ⚠ 먼저 알아야 할 것: 콘솔이 두 개입니다

네이버가 검색 API를 **개발자센터 → NAVER API Hub** 로 옮기는 중입니다.
두 곳 모두 `Client ID` + `Client Secret` 한 쌍을 주지만 **도메인·경로·인증 헤더가
전부 다릅니다.** 도메인만 바꿔서는 동작하지 않습니다.

| | 신규 (권장) | 기존 |
|---|---|---|
| 콘솔 | **console.ncloud.com/naver-api-hub/application** | developers.naver.com/apps |
| 도메인 | `naverapihub.apigw.ntruss.com` | `openapi.naver.com` |
| 경로 | `/search/v1/cafearticle` | `/v1/search/cafearticle.json` |
| 헤더 | `X-NCP-APIGW-API-KEY-ID`<br>`X-NCP-APIGW-API-KEY` | `X-Naver-Client-Id`<br>`X-Naver-Client-Secret` |
| 지원 종료 | — | **2027-06-30** |

**어느 쪽 키를 넣어도 파이프라인은 그대로 동작합니다.** 두 방식을 모두
구현해 두었고, 첫 호출에서 실제로 통하는 쪽을 자동으로 찾습니다
(`NAVER_API_MODE=auto`, 기본값).

이 프로젝트가 쓰는 **카페글·블로그·지식iN 검색은 이관 후에도 계속 제공됩니다.**
(2026-07-31 종료된 것은 쇼핑·도서·전문자료 검색이며, 우리는 쓰지 않습니다.)

### NAVER API Hub 에서 발급 (신규)

1. **https://console.ncloud.com/naver-api-hub/application** 접속
2. **Application 등록** 클릭
3. 이용약관(AI·NAVER API + NAVER API 서비스) 동의
4. Application 이름: `에듀트리`
5. 사용할 API로 **검색(Search)** 선택
6. 등록 완료 후 **Client ID / Client Secret** 확인

> 키 하나로 검색·쇼핑인사이트·트렌드를 함께 쓸 수 있습니다.
> NCP는 결제수단 등록을 요구할 수 있으니 무료 한도를 확인하세요.

### 개발자센터에서 발급 (기존, 2027-06 까지)

1. https://developers.naver.com/apps/#/register
2. 애플리케이션 이름 `에듀트리`, 사용 API **검색** 체크
3. 비로그인 오픈 API 환경 → `WEB 설정` → `https://openedu4u.com`

> 한도: 하루 25,000회. 학원 83곳 × 질의 5 × 소스 3 ≈ 1,245회라 넉넉합니다.

---

## 3단계 — .env 파일 만들기

저장소 루트에 `.env` 를 만드세요. **`.gitignore`에 있어 커밋되지 않습니다.**
키는 이 파일에만 두고, 채팅·이슈·커밋에 붙여넣지 마세요.

```bash
cp .env.example .env
```

```ini
NEIS_API_KEY=1단계에서_받은_인증키
NAVER_CLIENT_ID=2단계에서_받은_ID
NAVER_CLIENT_SECRET=2단계에서_받은_시크릿
# 자동 감지가 기본값. 필요할 때만 hub 또는 legacy 로 고정하세요.
# NAVER_API_MODE=hub
```

### 키가 맞는지 바로 확인

```bash
python3 pipeline/run.py --test
```

실제로 한 번씩 호출해서 결과를 보여줍니다 — NEIS는 몇 건이 조회되는지,
네이버는 두 방식 중 어느 쪽이 통하는지, 카페글이 실제로 수신되는지까지.
`✓` 가 뜨면 본 수집을 돌립니다:

```bash
python3 pipeline/run.py
```

---

## 4단계 — GitHub Actions 자동 수집

매일 새벽 4시(KST)에 자동으로 수집·채점하고 커밋합니다.

저장소 → **Settings → Secrets and variables → Actions → New repository secret** 에서
`.env` 와 같은 이름으로 세 개를 등록하세요.

| Secret 이름 | 값 |
|---|---|
| `NEIS_API_KEY` | 1단계 인증키 |
| `NAVER_CLIENT_ID` | 2단계 ID |
| `NAVER_CLIENT_SECRET` | 2단계 시크릿 |

---

## 5단계 — GitHub Pages 배포 전환 ⚠️ 수동 설정 필요

**이 한 가지는 제가 대신 할 수 없습니다.** 저장소 설정에서 직접 바꿔주세요.

저장소 → **Settings → Pages → Build and deployment → Source** 를
`Deploy from a branch` 에서 **`GitHub Actions`** 로 변경.

바꾸고 나면 `main` 에 푸시할 때마다:
- `openedu4u.com/` → 에듀트리 (Flutter 웹)
- `openedu4u.com/openedu/` → 기존 Open Edu 사이트 (그대로 보존)

> 이걸 바꾸기 전까지는 기존 방식(브랜치 배포)이 유지되므로, 루트에 빌드
> 산출물이 없어 사이트가 비어 보일 수 있습니다. 전환은 한 번만 하면 됩니다.

---

## 6단계 — Supabase (사용자 계정 · 후기 · 정정 요청)

정적 데이터만으로도 테크트리와 랭킹은 완전히 동작합니다.
**로그인, 사용자 후기, 즐겨찾기, 정정 요청 저장**이 필요할 때 진행하세요.

1. https://supabase.com/dashboard → **New project**
   - Region: `Northeast Asia (Seoul)` 선택 (지연시간)
2. 프로젝트 생성 후 **SQL Editor** 에서 순서대로 실행
   ```
   supabase/01_schema.sql
   supabase/02_functions.sql
   ```
   > `postgis` 확장이 막히면 `01_schema.sql` 의 해당 줄과 `geography` 컬럼을
   > 주석 처리하세요. 지도는 좌표 없이도 동작합니다.
3. **Settings → API** 에서 값 복사 → `.env` 에 추가
   ```ini
   SUPABASE_URL=https://xxxx.supabase.co
   SUPABASE_SERVICE_KEY=eyJ...   # service_role 키. 절대 앱에 넣지 마세요
   ```
4. 업로드
   ```bash
   python3 pipeline/sync_supabase.py
   ```

> `service_role` 키는 RLS를 우회합니다. 파이프라인(서버)에서만 쓰고,
> Flutter 앱에는 반드시 `anon` 키를 쓰세요.

---

## 7단계 (선택) — 카페 심층 수집

**기본적으로 꺼져 있습니다. 서비스는 이것 없이도 전 기능이 동작합니다.**

네이버 검색 API는 카페글의 *스니펫*까지만 줍니다. 후기 본문 전체를 보려면
로그인 세션이 필요한데, 이는 네이버 이용약관에 어긋나고 계정 정지·법적
분쟁의 소지가 있습니다. 그래서 이 모듈은:

- 자동 로그인을 하지 않습니다. 아이디·비밀번호를 받지도, 저장하지도 않습니다.
- GitHub Actions 등 CI에서는 실행 자체가 거부됩니다.
- 산출물은 집계 신호로만 반영되고, 원문은 저장하지 않습니다.

### 방식 A — 로컬 HTML 인제스트 (권장)

브라우저에서 직접 열어 저장한 카페 페이지를 폴더에 모아두면 그것만 읽습니다.
자동 접속이 없어 약관·차단 문제에서 자유롭습니다.

```bash
mkdir -p ~/edutree_cafe_pages
export EDUTREE_ENABLE_CAFE_SCRAPER=1
export EDUTREE_CAFE_HTML_DIR=~/edutree_cafe_pages
python3 pipeline/run.py --with-cafe
```

### 방식 B — 로그인된 브라우저 프로필 재사용

```bash
pip install playwright && playwright install chromium
```

`pipeline/edutree/cafe_local.py` 의 `collect_with_browser()` 를 쓰되,
**실행 전 약관과 robots.txt 를 직접 확인하시고 본인 판단으로 사용하세요.**
헤드리스로 돌지 않도록(사람이 보고 있도록) 의도적으로 만들어 두었습니다.

---

## 8단계 — 모바일 앱 빌드

```bash
cd app

# Android
flutter build appbundle --release

# iOS (Xcode 필요)
flutter build ipa --release
```

스토어 등록 전 확인할 것:
- `app/ios/Runner/Info.plist`, `app/android/app/src/main/AndroidManifest.xml` 의 앱 이름
- 앱 아이콘 (현재 Flutter 기본값)
- 개인정보처리방침 URL — **두 스토어 모두 필수**. `/method` 페이지를 확장해 쓰면 됩니다.

---

## 문제가 생기면

| 증상 | 확인할 것 |
|---|---|
| `--check` 에서 계속 `✗` | `.env` 가 저장소 **루트**에 있는지, 키 앞뒤 공백 |
| NEIS가 0곳 반환 | `regions.yaml` 의 `sigungu` 표기가 NEIS 행정구역명과 일치하는지 |
| 네이버 429 | 일일 한도 초과. 다음날 재시도하거나 앱을 하나 더 등록 |
| 점수가 전부 비슷함 | 표본 부족. 정상입니다 — 베이지안 축소가 평균으로 당기는 중 |
| 웹은 되는데 앱이 데이터를 못 읽음 | `app/assets/data/` 가 `pubspec.yaml` assets에 있는지 |
