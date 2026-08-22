"""EDSS 대량자료 집계 — 서울 학교 지표 추이.

파일
  0011. 학교총개황            학생수·학급수·교원수 (2009-2025)
  0313/0314. 전출입및학업중단   전입·전출 학생수 (2013-2025)

★ 학교가 익명화돼 있다.
  두 파일 모두 학교명이 없고 식별자는 '개방ID'(10자리)뿐이다. 이 ID 는
  학교알리미 SCHUL_CODE(S010000698)나 NEIS 코드(7010118)와 맞지 않고,
  시군구 컬럼도 없다. 두 파일끼리는 같은 ID 체계라 조인되지만(서울 1,036개교
  일치), 어느 학교인지는 알 수 없다.

  → 학교별 순위는 이 자료로 만들 수 없다. 서울 전체 추이까지가 한계다.
    학교명이 붙은 자료는 EDSS 맞춤형 신청·심사를 거쳐야 한다.

그래도 서울 전체 추이는 그 자체로 쓸모가 있다. 학급당 학생수가 10년 새
어떻게 변했는지, 전입 초과가 언제 꺾였는지는 학군을 고민하는 학부모에게
맥락을 준다. 게시판 리포트 소재로 쓴다.
"""
from __future__ import annotations

import collections
import csv
import json
from pathlib import Path

from . import config

DATA = config.DATA_DIR / "edss"
SEOUL_OFFICE = "서울특별시교육청"

# 학제명이 해마다 달라진다(중학교 → 일반중학교). 학교급으로 묶는다.
def _level(name: str) -> str | None:
    if "초등학교" in name:
        return "elementary"
    if "중학교" in name and "방송" not in name:
        return "middle"
    if "고등학교" in name and "공민" not in name:
        return "high"
    return None


def _num(v) -> int:
    try:
        return int(float(v or 0))
    except (TypeError, ValueError):
        return 0


def build(base_csv: str, transfer_csvs: list[str]) -> dict:
    """서울 학교급×연도 집계를 만든다."""
    stats: dict = collections.defaultdict(
        lambda: {"students": 0, "classes": 0, "teachers": 0,
                 "schools": 0, "in": 0, "out": 0})

    with open(base_csv, encoding="cp949") as f:
        for r in csv.DictReader(f):
            if r.get("시도명") != "서울":
                continue
            lvl = _level(r.get("학제명") or "")
            if not lvl:
                continue
            s = stats[(r["조사년도"], lvl)]
            s["students"] += _num(r.get("학생수"))
            s["classes"] += _num(r.get("학급수"))
            s["teachers"] += _num(r.get("교원수"))
            s["schools"] += 1

    for path in transfer_csvs:
        with open(path, encoding="cp949") as f:
            for r in csv.DictReader(f):
                if r.get("시도교육청명") != SEOUL_OFFICE:
                    continue
                lvl = _level(r.get("학교급명") or "")
                if not lvl:
                    continue
                s = stats[(r["공시년도"], lvl)]
                # 컬럼명이 초중특/고특으로 갈린다
                for k, v in r.items():
                    if "전입학생수" in k:
                        s["in"] += _num(v)
                    elif "전출학생수" in k:
                        s["out"] += _num(v)

    out = []
    for (year, lvl), s in sorted(stats.items()):
        out.append({
            "year": year,
            "level": lvl,
            "schools": s["schools"] or None,
            "students": s["students"] or None,
            "classes": s["classes"] or None,
            "perClass": round(s["students"] / s["classes"], 1) if s["classes"] else None,
            "perTeacher": round(s["students"] / s["teachers"], 1) if s["teachers"] else None,
            "transferIn": s["in"] or None,
            "transferOut": s["out"] or None,
            "netTransfer": (s["in"] - s["out"]) if (s["in"] or s["out"]) else None,
        })

    path = DATA / "seoul_trends.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  EDSS 서울 추이 {len(out)}행 → {path.name}")
    return {"rows": len(out)}


def load() -> list[dict]:
    path = DATA / "seoul_trends.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
