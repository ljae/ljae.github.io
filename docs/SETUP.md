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

## 7단계 (선택) — 후기 텍스트 더 깊게 보기

검색 API 는 120자 남짓의 스니펫만 준다. 감성과 관점을 제대로 읽기엔 얕다.
깊이를 더하는 방법은 위험도 순으로 셋이며, **앞의 둘은 이미 자동으로 돈다.**

전체 배경과 학군별 카페 목록은 [DATA.md](DATA.md) 참고.

### 자동 (설정 불필요)

**블로그 본문** — 네이버 블로그는 공개돼 있어 로그인 없이 전문을 가져온다.
정지당할 계정 자체가 없다. 스니펫 120자 → 평균 2,000자 이상.
`python3 pipeline/run.py` 에 포함돼 있고, 생략하려면 `--skip-blog-text`.

**발견 시점 기록** — 카페글 검색 API 는 작성일을 주지 않아 수집분의 91%가
날짜 없이 들어온다. 매일 도는 수집 자체를 시계로 쓴다. 어제 없던 URL 이
오늘 보이면 최근 글이다. 크롤링도 한도 소모도 없고, **매일 돌수록 정확해진다.**

### 수동 (선택) — 카페 목록 페이지로 날짜 보강

브라우저에서 카페 검색 결과 페이지를 저장해 폴더에 모아두면, 거기서
(링크, 날짜) 쌍만 뽑아냅니다. 개별 글을 열지 않으므로 트래픽이 3% 수준입니다.

```python
from edutree import cafe_dates
found = cafe_dates.ingest_saved_pages("~/edutree_cafe_pages")
cafe_dates.merge(found)          # 이후 수집부터 자동 반영
```

### 권장하지 않음 — 카페 본문 대량 수집

`pipeline/edutree/cafe_local.py` 에 남겨 두었지만 기본 꺼짐이고 CI 실행을
거부합니다. 이유는 셋입니다.

1. **규모가 안 맞습니다.** 12,000건 이상을 개별로 열면 13시간 넘게 걸리고
   그 전에 차단됩니다. 야간 자동 수집에 넣을 수 없습니다.
2. **계정 위험이 실질적입니다.** 자동화로 정지되면 등업 등급까지 잃습니다.
   몇 주 걸려 쌓은 접근 권한을 데이터 한 칸과 바꿀 이유가 없습니다.
3. **약관 문제.** 공개 서비스가 여기에 의존하면 방어할 수 없습니다.

굳이 쓰신다면 직접 저장한 HTML 만 읽는 방식(A)을 권합니다.

```bash
export EDUTREE_ENABLE_CAFE_SCRAPER=1
export EDUTREE_CAFE_HTML_DIR=~/edutree_cafe_pages
python3 pipeline/run.py --with-cafe
```

### 참고: 지식iN 활성화

현재 NCP 애플리케이션에 **지식iN 이 꺼져 있어** 해당 소스는 자동 제외됩니다.
콘솔에서 검색 API 목록에 지식iN 을 추가하면 다음 수집부터 신호가 하나 늘어납니다.

---

## 8단계 (선택) — 네이버 지도 · Supabase 앱 연결

여기서부터는 **브라우저에 노출되는 키**를 다룹니다. 앞의 키들과 성격이 다릅니다.

| 키 | 어디에 두나 | 노출 | 무엇으로 보호하나 |
|---|---|---|---|
| `NEIS_API_KEY` | `.env` (서버) | ✗ | 노출 금지 |
| `NAVER_CLIENT_SECRET` | `.env` (서버) | ✗ | 노출 금지 |
| `SUPABASE_SERVICE_KEY` | `.env` (서버) | ✗ | **RLS 우회** — 절대 앱에 넣지 마세요 |
| `NAVER_MAP_CLIENT_SECRET` | `.env` (서버) | ✗ | 지오코딩 전용 |
| `NAVER_MAP_KEY_ID` | 앱 빌드 | **✓ 공개** | 콘솔 도메인 허용목록 |
| `SUPABASE_ANON_KEY` | 앱 빌드 | **✓ 공개** | RLS 정책 |

아래 두 개는 **공개돼도 되는 키**입니다. 숨길 수 없고, 숨길 필요도 없습니다.
저장소에 커밋하지 않는 이유는 유출 방지가 아니라 키 교체 시 코드를 안 고치기
위해서입니다.

### 8-1. 네이버 지도

1. https://console.ncloud.com → **Services → Application Services → Maps**
2. **Application 등록**
3. 사용 API에서 **Web Dynamic Map** 과 **Geocoding** 을 함께 선택
   (지도 표시는 Dynamic Map, 학원 주소 → 좌표 변환은 Geocoding)
4. **Web 서비스 URL** 에 도메인을 등록 — 여기 없는 도메인에서는 인증 실패합니다
   ```
   https://openedu4u.com
   http://localhost:8080
   ```
5. 발급된 **Client ID / Client Secret** 을 `.env` 에

```ini
NAVER_MAP_CLIENT_ID=발급받은_ID
NAVER_MAP_CLIENT_SECRET=발급받은_시크릿
```

좌표를 채웁니다(주소는 거의 안 바뀌므로 한 번만 오래 걸립니다):

```bash
python3 pipeline/run.py
```

> **지도가 안 뜬다면** 브라우저 콘솔에 `네이버 지도 인증 실패` 가 찍힙니다.
> 대부분 4번의 도메인 등록 누락입니다. 키가 없거나 인증에 실패하면 앱은
> 기존 모식도 지도로 자동 전환되므로 화면이 깨지지는 않습니다.

### 8-2. Supabase (자체 후기·로그인)

6단계에서 프로젝트를 만들었다면 **Settings → API** 에서 `anon`(= publishable) 키를
가져옵니다. `service_role` 이 아닙니다 — 그건 RLS 를 우회하므로 앱에 들어가면
안 됩니다.

```ini
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=eyJ...        # 또는 sb_publishable_...
```

SQL Editor 에서 후기용 스키마를 마저 실행합니다:

```
supabase/03_reviews.sql
```

**Authentication → Providers** 에서 **Email** 을 켜두세요. 후기 작성은 이메일
링크 로그인만 씁니다(비밀번호를 만들지 않습니다). 카카오·구글은 나중에
같은 화면에서 공급자를 추가하면 붙습니다.

**Authentication → URL Configuration → Site URL** 에 `https://openedu4u.com`
을 넣어야 로그인 링크가 제대로 돌아옵니다.

자체 후기는 평판 점수에 함께 반영됩니다. 스크랩한 커뮤니티 글보다 신뢰도를
높게(0.9) 주는데, 로그인·구조화된 별점·학원당 1인 1건이라는 조건이 붙어
있기 때문입니다. 파이프라인은 후기 **본문을 가져가지 않고** 별점 평균과
건수만 읽습니다(`v_review_summary`).

### 8-3. 로컬에서 실행

앱 키는 빌드 시점에 주입됩니다.

```bash
cd app
flutter run -d chrome \
  --dart-define=SUPABASE_URL=$SUPABASE_URL \
  --dart-define=SUPABASE_ANON_KEY=$SUPABASE_ANON_KEY \
  --dart-define=NAVER_MAP_KEY_ID=$NAVER_MAP_CLIENT_ID
```

지도 SDK 키는 HTML 에 들어가야 해서 `--dart-define` 으로는 닿지 않습니다.
로컬에서 지도까지 보려면 `app/web/index.html` 의 `__NAVER_MAP_KEY_ID__` 를
잠시 실제 값으로 바꾸세요. **바꾼 채로 커밋하지 마세요.**

### 8-4. 배포용 시크릿

저장소 → Settings → Secrets and variables → Actions

| Secret | 용도 |
|---|---|
| `NAVER_MAP_KEY_ID` | 지도 SDK (index.html 에 주입) |
| `SUPABASE_URL` | 앱 |
| `SUPABASE_ANON_KEY` | 앱 |

배포 워크플로가 index.html 치환과 `--dart-define` 주입을 모두 처리합니다.
시크릿이 없으면 지도는 모식도로, 게시판 기능은 꺼진 채로 배포됩니다.

---

## 9단계 — 모바일 앱 빌드

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
