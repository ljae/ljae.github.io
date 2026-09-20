"""학년 필터가 랭킹에서 사용할 수 있는지 확인하는 감사 도구.

학년을 확인하지 못한 학원은 과목 전체 랭킹에는 남을 수 있지만 학년별
목록에서는 제외된다. 이 모듈은 그 상태를 오류로 복원하지 않고, 과목별
학년 자료가 누락되거나 서로 섞이는 경우만 배포 전에 차단한다.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .grade_targets import BANDS


def _value(row, snake, camel, default=None):
    return row.get(snake, row.get(camel, default))


def audit_rows(rows):
    """Return a JSON-serialisable structural and coverage audit report."""
    errors = []
    warnings = []
    subjects = Counter()
    bands = Counter()
    ranked_without_grade = Counter()
    grade_rows = 0

    for row in rows:
        ident = str(row.get("id", row.get("academyId", "?")))
        name = row.get("name", row.get("displayName", ident))
        label = f"{name} ({ident})"
        row_subjects = list(_value(row, "subjects", "subjects", []) or [])
        global_bands = set(_value(row, "grade_bands", "gradeBands", []) or [])
        mapping = _value(row, "grade_bands_by_subject", "gradeBandsBySubject", {})
        if not isinstance(mapping, dict):
            errors.append(f"{label}: 과목별 학년 맵이 객체가 아님")
            mapping = {}
        unknown_global = global_bands - set(BANDS)
        if unknown_global:
            errors.append(f"{label}: 알 수 없는 전역 학년 {sorted(unknown_global)}")
        missing = [s for s in row_subjects if s not in mapping]
        if missing:
            errors.append(f"{label}: 과목별 학년 맵 누락 {sorted(missing)}")
        union = set()
        for subject in row_subjects:
            values = mapping.get(subject, []) or []
            if not isinstance(values, list):
                errors.append(f"{label}/{subject}: 학년 값이 목록이 아님")
                values = []
            invalid = set(values) - set(BANDS)
            if invalid:
                errors.append(f"{label}/{subject}: 알 수 없는 학년 {sorted(invalid)}")
            subject_bands = set(values) & set(BANDS)
            union |= subject_bands
            subjects[subject] += 1
            for band in subject_bands:
                bands[(subject, band)] += 1
        # 과목을 아직 분류하지 못한 등록부 행은 전역 학년만 보유할 수
        # 있다. 과목이 있는 행에서만 전역/과목별 일치를 강제한다.
        if row_subjects and union and global_bands != union:
            errors.append(
                f"{label}: 전역 학년과 과목별 학년 불일치 "
                f"(global={sorted(global_bands)}, subjects={sorted(union)})"
            )
        if global_bands:
            grade_rows += 1

        scores = _value(row, "subject_scores", "subjectScores", {}) or {}
        for subject, score in scores.items():
            if (score or {}).get("is_ranked") or (score or {}).get("isRanked"):
                if not set(mapping.get(subject, []) or []):
                    ranked_without_grade[subject] += 1

    for subject, count in ranked_without_grade.items():
        warnings.append(
            f"{subject}: 과목 랭킹 학원 {count}곳에 대상학년 근거가 없어 "
            "학년 필터에서는 제외됨"
        )
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "total": len(rows),
        "withAnyGrade": grade_rows,
        "subjects": dict(subjects),
        "bands": {f"{s}:{b}": n for (s, b), n in sorted(bands.items())},
        "rankedWithoutGrade": dict(ranked_without_grade),
    }


def audit_export(asset_dir: Path):
    rows = []
    for name in ("academies.json", "registry.json"):
        rows.extend(json.loads((asset_dir / name).read_text(encoding="utf-8")))
    return audit_rows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-dir", type=Path)
    args = parser.parse_args()
    from . import config
    report = audit_export(args.asset_dir or config.EXPORT_DIR)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
