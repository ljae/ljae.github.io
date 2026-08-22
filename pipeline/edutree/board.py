"""게시판 시드 콘텐츠 생성.

콜드스타트를 남의 글을 베껴 채우는 방식으로는 풀지 않는다. 그건 저작권
문제이기도 하고, 무엇보다 이 서비스가 가진 유일한 자산인 신뢰를 깎는다.
바이럴을 걸러낸다고 공개해 놓고 바이럴을 만드는 셈이 되기 때문이다.

대신 남이 못 쓰는 재료를 쓴다. 학원 3,910곳, 학교 136곳, 커뮤니티 글 2만 건.
여기서 나오는 글은 전부 사실 기반이고, 작성자를 '학원실록'으로 명시한다.

생성물
  weekly_report  주간 리포트 — 언급 급상승, 교습비 분포, 표본 변화
  stage_guide    테크트리 40단계 해설
  seed_question  먼저 던지는 질문 (학부모 답글을 유도하는 시작점)
"""
from __future__ import annotations

import json
import statistics
from datetime import date, datetime, timezone

import requests

from . import config


def _headers() -> dict:
    return {
        "apikey": config.SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {config.SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }


def _load(name: str):
    p = config.EXPORT_DIR / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def _won(v) -> str:
    if not v:
        return "미공개"
    return f"{v // 10000}만원" if v % 10000 == 0 else f"{v:,}원"


# ── 주간 리포트 ────────────────────────────────────────────────
def weekly_reports(academies, regions) -> list[dict]:
    """학군마다 이번 주 리포트 한 건.

    이 글이 게시판의 심장이다. 학부모가 쓴 이야기가 숫자로 어떻게 나타났는지
    돌려주는 자리라서, 여기가 비면 '말해도 반영이 안 되는 곳'이 된다.
    """
    today = date.today().isoformat()
    out = []
    for r in regions:
        rid, name = r["id"], r["name_ko"]
        rows = [a for a in academies
                if a.get("regionId") == rid and a.get("score", {}).get("isRanked")]
        if not rows:
            continue
        rows.sort(key=lambda a: -a["score"]["total"])

        rising = [a for a in rows if a["score"].get("momentumDirection") == "rising"]
        rising.sort(key=lambda a: -a["score"]["momentum"])
        fees = sorted(a["tuitionMonthly"] for a in rows if a.get("tuitionMonthly"))

        body = [
            f"{name} 학군의 이번 주 지표입니다. 모든 수치는 NEIS 공시와 "
            f"커뮤니티 신호에서 자동으로 계산됩니다.",
            "",
            f"■ 순위에 오른 학원 {len(rows)}곳",
            f"유효 표본 {config.MIN_SAMPLE_FOR_RANK}건 이상만 순위에 넣습니다. "
            f"표본이 적은 학원은 점수가 낮아서가 아니라, 적은 근거로 등수를 "
            f"매기는 것이 부당해서 제외합니다.",
            "",
            "■ 트리스코어 상위",
        ]
        for i, a in enumerate(rows[:5], 1):
            s = a["score"]
            body.append(
                f"{i}. {a.get('displayName') or a['name']} — {s['total']:.0f}점 "
                f"(표본 {s['sampleSize']}건, 평판 {s['reputation']:.0f})")

        if rising:
            body += ["", "■ 언급이 늘고 있는 곳"]
            for a in rising[:3]:
                body.append(
                    f"· {a.get('displayName') or a['name']} — "
                    f"화제성 {a['score']['momentum']:.0f}")
            body.append(
                "화제성은 최근 90일 언급량과 12개월 추세로 계산합니다. "
                "좋다/나쁘다가 아니라 '지금 많이 이야기되는가'를 봅니다.")

        if fees:
            body += ["", "■ 월 교습비 분포 (공개된 곳 기준)",
                     f"중앙값 {_won(int(statistics.median(fees)))} · "
                     f"최저 {_won(fees[0])} · 최고 {_won(fees[-1])} "
                     f"({len(fees)}곳 공시)"]

        body += ["",
                 "―――",
                 f"이 글은 학원실록이 데이터에서 자동 생성했습니다. "
                 f"수치에 이상이 있으면 댓글로 알려주세요. "
                 f"여러분이 남긴 글도 다음 주 지표에 반영됩니다."]

        out.append({
            "category": "report",
            "region_id": rid,
            "title": f"[{name}] {today} 주간 학원 지표 — 상위 {len(rows[:5])}곳과 교습비 분포",
            "body": "\n".join(body),
            "is_official": True,
            "official_kind": "weekly_report",
            "academy_keys": [a["id"] for a in rows[:5]],
        })
    return out


# ── 단계 해설 ──────────────────────────────────────────────────
def stage_guides(tracks, academies) -> list[dict]:
    out = []
    for t in tracks:
        for st in t["stages"]:
            rows = [a for a in academies if st["id"] in (a.get("stages") or [])]
            body = [
                f"{t['title']} 테크트리의 '{st['title']}' 단계입니다.",
                "",
            ]
            if st.get("subtitle"):
                body.append(f"■ 한 줄 요약\n{st['subtitle']}")
            if st.get("goal"):
                body += ["", f"■ 이 단계의 목표\n{st['goal']}"]
            if st.get("exit_criteria"):
                body += ["", f"■ 다음 단계로 넘어가는 기준\n{st['exit_criteria']}"]

            grade = st.get("grade") or []
            if len(grade) == 2:
                def lbl(g):
                    return f"초{g}" if g <= 6 else (f"중{g-6}" if g <= 9 else f"고{g-9}")
                body += ["", f"■ 보통 다니는 학년\n{lbl(grade[0])} ~ {lbl(grade[1])}"]

            if rows:
                body += ["", f"■ 이 단계를 담당하는 학원 ({len(rows)}곳 중 일부)"]
                rows.sort(key=lambda a: -(a.get("score", {}).get("total") or 0))
                for a in rows[:6]:
                    body.append(f"· {a.get('displayName') or a['name']}")

            body += ["", "―――",
                     "이 단계에서 고민하신 경험이 있다면 댓글로 남겨 주세요. "
                     "실제 사례가 쌓이면 이 해설도 함께 고쳐 나갑니다."]

            out.append({
                "category": "guide",
                "subject": t["subject"],
                "school_level": t["school_level"],
                "title": f"[{t['title']}] {st['title']} — 언제 시작하고 언제 넘어가나",
                "body": "\n".join(body),
                "is_official": True,
                "official_kind": "stage_guide",
                "academy_keys": [a["id"] for a in rows[:6]],
            })
    return out


# ── 시드 질문 ──────────────────────────────────────────────────
SEED_QUESTIONS = [
    ("math", "elementary", "초4 겨울, 경시를 더 갈지 선행으로 틀지 고민입니다",
     "사고력 학원을 2년 다녔고 지금 초4입니다. 경시 준비를 계속할지, "
     "중등 선행으로 넘어갈지 결정해야 하는 시기라고들 하는데 실제로 겪어보신 분 "
     "이야기가 궁금합니다.\n\n특히 이런 게 알고 싶습니다.\n"
     "· 경시를 접고 선행으로 간 뒤 후회하신 적 있나요\n"
     "· 둘 다 병행하는 게 현실적으로 가능한 학년인가요\n"
     "· 결정할 때 무엇을 기준으로 보셨나요"),
    ("english", "elementary", "어학원 레벨테스트, 몇 번까지 다시 보시나요",
     "레벨테스트에서 원하는 반에 못 들어가면 다시 보게 하시는지 궁금합니다.\n\n"
     "· 재응시로 반이 올라간 경우가 실제로 있었나요\n"
     "· 낮은 반에서 시작해 올라가는 것과 처음부터 맞는 반에 들어가는 것, "
     "어느 쪽이 아이에게 나았나요"),
    ("math", "middle", "중2, 고등 선행 속도를 어떻게 잡으셨나요",
     "내신은 유지되는데 선행 속도가 맞는지 모르겠습니다. 주변은 이미 미적분을 "
     "한다는데 저희는 아직 고1 과정입니다.\n\n"
     "· 선행이 빠른 것과 깊은 것 중 무엇을 우선하셨나요\n"
     "· 속도를 늦추고 다시 다진 경험이 있으시면 결과가 궁금합니다"),
    (None, None, "학원 옮길 때 결정적이었던 이유는 무엇이었나요",
     "성적, 관리, 아이와의 궁합, 거리, 비용 — 여러 가지가 얽히는데 "
     "결국 옮기게 만든 한 가지가 무엇이었는지 궁금합니다.\n\n"
     "옮기고 나서 그 판단이 맞았는지도 함께 들려주시면 좋겠습니다."),
    (None, None, "설명회, 가보면 실제로 도움이 되던가요",
     "설명회를 다녀오면 결국 등록 권유로 끝난다는 이야기도 있고, "
     "커리큘럼을 제대로 볼 수 있는 자리라는 이야기도 있습니다.\n\n"
     "· 다녀와서 판단이 바뀐 적이 있으신가요\n"
     "· 설명회에서 꼭 물어보면 좋은 질문이 있다면요"),
]


def seoul_trend_report() -> list[dict]:
    """서울 학교 지표 추이 리포트.

    EDSS 자료는 학교가 익명화돼 있어 학교별 순위는 못 만들지만,
    서울 전체 추이는 그대로 쓸모가 있다. 학급당 학생수가 10년 새 어떻게
    변했는지는 학군을 고민할 때 실제로 필요한 맥락이다.
    """
    from . import edss
    rows = edss.load()
    if not rows:
        return []

    labels = {"elementary": "초등학교", "middle": "중학교", "high": "고등학교"}
    body = ["서울 학교 지표가 10년 동안 어떻게 변했는지 정리했습니다. "
            "교육부 학교알리미·에듀데이터 공시자료 기준입니다.", ""]

    for lvl, label in labels.items():
        picks = [r for r in rows if r["level"] == lvl
                 and r["year"] in ("2015", "2020", "2025")]
        if not picks:
            continue
        body.append(f"■ {label}")
        for r in sorted(picks, key=lambda x: x["year"]):
            parts = [f"{r['year']}년"]
            if r.get("perClass"):
                parts.append(f"학급당 {r['perClass']}명")
            if r.get("perTeacher"):
                parts.append(f"교원 1인당 {r['perTeacher']}명")
            if r.get("netTransfer") is not None:
                parts.append(f"순유입 {r['netTransfer']:+,}명")
            body.append("  " + " · ".join(parts))
        body.append("")

    body += [
        "■ 읽는 법",
        "학급당 학생수가 줄어드는 것은 교육여건이 나아진 면도 있지만, "
        "학령인구 감소가 더 큰 이유입니다. 서울 초등 학급당 학생수는 "
        "2015년 24.0명에서 2025년 20.1명이 됐습니다.",
        "",
        "순유입은 전입에서 전출을 뺀 값입니다. 서울 초등은 2015년 -2,294명에서 "
        "2025년 -188명으로 순유출이 거의 멎었습니다.",
        "",
        "―――",
        "학교별 수치는 아직 공개하지 못합니다. 이 공시자료는 학교가 익명화돼 "
        "있어(식별자만 있고 학교명이 없습니다) 어느 학교인지 알 수 없기 때문입니다. "
        "추정으로 학교 이름을 붙이지 않겠습니다.",
    ]

    return [{
        "category": "report",
        "title": "[서울] 학교 지표 10년 추이 — 학급당 학생수와 전출입",
        "body": "\n".join(body),
        "is_official": True,
        "official_kind": "trend_report",
        "academy_keys": [],
    }]


def seed_questions() -> list[dict]:
    return [{
        "category": "question",
        "subject": subject,
        "school_level": level,
        "title": title,
        "body": body + "\n\n―――\n학원실록이 먼저 여는 질문입니다. "
                       "댓글로 경험을 나눠 주세요.",
        "is_official": True,
        "official_kind": "seed_question",
        "academy_keys": [],
    } for subject, level, title, body in SEED_QUESTIONS]


# ── 업로드 ─────────────────────────────────────────────────────
# PostgREST 는 배치 안의 객체 키가 전부 같아야 한다.
# 리포트는 region_id 를, 해설은 subject/school_level 을 갖는 식으로 제각각이라
# 빠진 키를 None 으로 채워 모양을 맞춘다.
_FIELDS = ("category", "region_id", "school_level", "subject", "title", "body",
           "is_official", "official_kind", "academy_keys")


def publish(posts: list[dict]) -> int:
    if not config.HAS_SUPABASE or not posts:
        return 0
    url = f"{config.SUPABASE_URL}/rest/v1/board_posts"
    posts = [{k: p.get(k) for k in _FIELDS} for p in posts]
    sent = 0
    for i in range(0, len(posts), 100):
        chunk = posts[i:i + 100]
        resp = requests.post(url, headers=_headers(),
                             data=json.dumps(chunk), timeout=60)
        if resp.status_code >= 300:
            print(f"  게시판 업로드 실패 {resp.status_code}: {resp.text[:200]}")
            break
        sent += len(chunk)
    return sent


def existing_titles() -> set[str]:
    """이미 올라간 공식 글 제목. 매번 같은 글을 다시 올리지 않기 위해."""
    if not config.HAS_SUPABASE:
        return set()
    try:
        resp = requests.get(
            f"{config.SUPABASE_URL}/rest/v1/board_posts",
            params={"select": "title", "is_official": "eq.true", "limit": "5000"},
            headers={"apikey": config.SUPABASE_SERVICE_KEY,
                     "Authorization": f"Bearer {config.SUPABASE_SERVICE_KEY}"},
            timeout=30)
        if resp.status_code == 200:
            return {r["title"] for r in resp.json()}
    except requests.RequestException:
        pass
    return set()


def run() -> dict:
    academies = _load("academies.json")
    regions = _load("regions.json")
    tree = _load("techtree.json")
    tracks = tree.get("tracks", []) if isinstance(tree, dict) else []

    candidates = (weekly_reports(academies, regions)
                  + stage_guides(tracks, academies)
                  + seoul_trend_report()
                  + seed_questions())

    seen = existing_titles()
    fresh = [p for p in candidates if p["title"] not in seen]
    sent = publish(fresh)
    print(f"  게시판 시드: 후보 {len(candidates)}건 중 신규 {len(fresh)}건 등록")
    return {"candidates": len(candidates), "published": sent}
