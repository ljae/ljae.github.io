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

학원의 이름·주소·정원·교습비·등록상태가 여기서 옵니다. **투명성 점수 전체가 이 데이터에 걸려 있습니다.**

1. https://open.neis.go.kr 접속 → 우측 상단 **회원가입** (무료)
2. 로그인 후 상단 **[OpenAPI] → [인증키 신청]**
3. 신청서 작성
   - 활용 목적: `학원 정보 조회 서비스`
   - 활용 구분: `웹사이트 개발`
4. 발급된 인증키 복사 (즉시 발급, 심사 없음)

> 일일 호출 한도가 있습니다. 인증키 없이도 하루 1,000건까지 되지만,
> 4개 학군을 다 훑으려면 키가 필요합니다.

---

## 2단계 — 네이버 검색 API (평판 · 화제성 점수용)

1. https://developers.naver.com/apps/#/register 접속 (네이버 계정 필요)
2. **애플리케이션 이름**: `에듀트리`
3. **사용 API**: `검색` 체크
4. **비로그인 오픈 API 서비스 환경**:
   - `WEB 설정` 추가 → 웹 서비스 URL에 `https://openedu4u.com` 입력
5. 등록하면 **Client ID** 와 **Client Secret** 이 나옵니다

> 한도: 앱당 하루 25,000회. 학원 83곳 × 질의 5개 × 소스 3개 ≈ 1,245회이므로
> 넉넉합니다. 학원 수가 500곳을 넘어가면 수집 주기를 나눠야 합니다.

---

## 3단계 — .env 파일 만들기

저장소 루트에 `.env` 를 만들고 붙여넣으세요. **이 파일은 `.gitignore`에 있어 커밋되지 않습니다.**

```bash
cp .env.example .env
```

```ini
NEIS_API_KEY=여기에_1단계_인증키
NAVER_CLIENT_ID=여기에_2단계_클라이언트_ID
NAVER_CLIENT_SECRET=여기에_2단계_시크릿
```

확인:

```bash
python3 pipeline/run.py --check
```

`✓` 가 뜨면 성공. 이제 실제 수집을 돌립니다:

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
