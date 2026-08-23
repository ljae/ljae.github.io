import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme.dart';
import '../../data/models.dart';
import '../../data/repository.dart';
import 'techtree_page.dart' show showStageSheet;

/// 통합 로드맵 — 연령 축 하나 위에 네 과목을 나란히 놓는다.
///
/// 과목·구간별 트리는 '지금 내 아이 구간'을 보는 데 좋지만, 5세 영어 →
/// 6세 수학 → 7세 국어 → 초4 재편이라는 전체 흐름은 과목을 나란히
/// 놓아야 보인다. 세로가 나이, 가로가 과목이다. 카드의 세로 위치와
/// 길이가 곧 시작 나이와 지속 기간이다 — 표를 읽는 게 아니라 지도를
/// 보게 하는 것이 목적이다.
///
/// 유아 단계(영유)는 방향 안내일 뿐이라 점선 테두리로 구분하고,
/// 눌러도 랭킹으로 이어지지 않는다.
class RoadmapView extends ConsumerWidget {
  final EduTreeData data;
  final String regionId;
  const RoadmapView({super.key, required this.data, required this.regionId});

  static const _minGrade = -2; // 5세
  static const _maxGrade = 12; // 고3
  static const _unitH = 62.0; // 학년 1칸 높이
  static const _axisW = 52.0;
  static const _gap = 10.0;

  double _y(num grade) => (grade - _minGrade) * _unitH;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final roadmap = data.roadmap;
    if (roadmap.isEmpty) {
      return const Center(child: Text('로드맵 데이터가 없습니다'));
    }
    final subjects = ['english', 'math', 'korean', 'science']
        .where((s) => roadmap.stages.any((st) => st.subject == s))
        .toList();

    final totalH = _y(_maxGrade + 1) + 20;

    return LayoutBuilder(builder: (context, c) {
      // 좁은 화면에서는 가로 스크롤로 도망가게 한다. 네 과목을 억지로
      // 구겨 넣으면 카드가 글자 하나 폭이 된다.
      final colW = ((c.maxWidth - _axisW - _gap * subjects.length) /
              subjects.length)
          .clamp(150.0, 340.0);
      final contentW = _axisW + (colW + _gap) * subjects.length;

      return SingleChildScrollView(
        child: SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: SizedBox(
            width: contentW,
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const SizedBox(height: AppSpace.md),
              // 과목 헤더
              Row(children: [
                const SizedBox(width: _axisW),
                for (final s in subjects)
                  Container(
                    width: colW,
                    margin: const EdgeInsets.only(right: _gap),
                    padding: const EdgeInsets.symmetric(vertical: 7),
                    decoration: BoxDecoration(
                      color: (AppColors.subjects[s] ?? AppColors.slate)
                          .withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(AppRadius.sm),
                    ),
                    child: Center(
                      child: Text(subjectNames[s] ?? s,
                          style: Theme.of(context)
                              .textTheme
                              .titleMedium
                              ?.copyWith(
                                  color: AppColors.subjects[s],
                                  fontWeight: FontWeight.w800)),
                    ),
                  ),
              ]),
              const SizedBox(height: 6),
              SizedBox(
                height: totalH,
                child: Stack(children: [
                  // 연령 눈금 + 이정표
                  for (var g = _minGrade; g <= _maxGrade; g++)
                    Positioned(
                      top: _y(g),
                      left: 0,
                      right: 0,
                      child: _GradeRow(
                        grade: g,
                        milestone: roadmap.milestones
                            .where((m) => m.grade == g)
                            .firstOrNull,
                      ),
                    ),
                  // 경로선 — 카드 아래에 깔린다
                  Positioned.fill(
                    child: CustomPaint(
                      painter: _EdgePainter(
                        roadmap: roadmap,
                        subjects: subjects,
                        colW: colW,
                        gap: _gap,
                        axisW: _axisW,
                        yOf: _y,
                        lineColor: Theme.of(context).dividerColor,
                      ),
                    ),
                  ),
                  // 단계 카드
                  for (final st in roadmap.stages)
                    if (subjects.contains(st.subject))
                      _positioned(context, st, subjects, colW),
                ]),
              ),
              const SizedBox(height: AppSpace.xl),
            ]),
          ),
        ),
      );
    });
  }

  Widget _positioned(BuildContext context, RoadmapStage st,
      List<String> subjects, double colW) {
    final col = subjects.indexOf(st.subject);
    // 같은 과목 안에서 기간이 겹치는 단계는 lane(0/1)으로 좌우를 나눈다.
    final overlaps = data.roadmap.stages.any((o) =>
        o.id != st.id &&
        o.subject == st.subject &&
        o.gradeMin <= st.gradeMax &&
        o.gradeMax >= st.gradeMin);
    final laneW = overlaps ? (colW - 4) / 2 : colW;
    final left = _axisW +
        col * (colW + _gap) +
        (overlaps && st.lane > 0 ? laneW + 4 : 0);

    return Positioned(
      top: _y(st.gradeMin) + 2,
      left: left,
      width: laneW,
      height: (st.gradeMax - st.gradeMin + 1) * _unitH - 6,
      child: _StageCard(stage: st, data: data, regionId: regionId),
    );
  }
}

class _GradeRow extends StatelessWidget {
  final int grade;
  final RoadmapMilestone? milestone;
  const _GradeRow({required this.grade, this.milestone});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return SizedBox(
      height: RoadmapView._unitH,
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        SizedBox(
          width: RoadmapView._axisW,
          child: Padding(
            padding: const EdgeInsets.only(top: 2, right: 8),
            child: Text(Stage.gradeName(grade),
                textAlign: TextAlign.right,
                style: text.bodySmall?.copyWith(
                    fontSize: 11,
                    fontWeight:
                        milestone != null ? FontWeight.w800 : FontWeight.w400,
                    color: milestone != null ? AppColors.gold : null)),
          ),
        ),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Divider(
                height: 1,
                color: milestone != null
                    ? AppColors.gold.withValues(alpha: 0.55)
                    : Theme.of(context).dividerColor.withValues(alpha: 0.5)),
            if (milestone != null)
              Padding(
                padding: const EdgeInsets.only(top: 2),
                child: Tooltip(
                  message: milestone!.note,
                  child: Text('◆ ${milestone!.label}',
                      style: text.bodySmall?.copyWith(
                          fontSize: 10,
                          color: AppColors.gold,
                          fontWeight: FontWeight.w700)),
                ),
              ),
          ]),
        ),
      ]),
    );
  }
}

class _StageCard extends StatelessWidget {
  final RoadmapStage stage;
  final EduTreeData data;
  final String regionId;
  const _StageCard(
      {required this.stage, required this.data, required this.regionId});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final accent = AppColors.subjects[stage.subject] ?? AppColors.slate;

    // 로드맵에서 랭킹으로 이어지는 고리 — 이 단계 담당 학원 중 상위.
    // 유아 단계는 랭킹과 연결하지 않는다.
    final tops = stage.roadmapOnly
        ? const <Academy>[]
        : data
            .academiesForStage(stage.id, regionId: regionId)
            .where((a) => a.score.isRanked)
            .take(2)
            .toList();

    final full = data.stageById[stage.id];

    return InkWell(
      borderRadius: BorderRadius.circular(AppRadius.sm),
      onTap: full == null
          ? null
          : () => showStageSheet(context, full, data, regionId),
      child: Container(
        padding: const EdgeInsets.fromLTRB(9, 7, 9, 7),
        decoration: BoxDecoration(
          color: dark ? AppColors.darkSurface : AppColors.surface,
          borderRadius: BorderRadius.circular(AppRadius.sm),
          border: Border.all(
            color: stage.roadmapOnly
                ? AppColors.mist
                : accent.withValues(alpha: 0.55),
            width: stage.roadmapOnly ? 1 : 1.4,
          ),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Container(width: 3, height: 12, color: accent),
            const SizedBox(width: 5),
            Expanded(
              child: Text(stage.title,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: text.labelLarge
                      ?.copyWith(fontSize: 12.5, height: 1.25)),
            ),
          ]),
          const SizedBox(height: 2),
          Text(stage.gradeLabel,
              style: text.bodySmall?.copyWith(fontSize: 10)),
          if (stage.roadmapOnly)
            Expanded(
              child: Align(
                alignment: Alignment.bottomLeft,
                child: Text('로드맵 안내 · 순위 없음',
                    style: text.bodySmall
                        ?.copyWith(fontSize: 9.5, color: AppColors.mist)),
              ),
            )
          else if (tops.isNotEmpty)
            Expanded(
              child: Align(
                alignment: Alignment.bottomLeft,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    for (final a in tops)
                      Padding(
                        padding: const EdgeInsets.only(top: 1),
                        child: Row(children: [
                          const Icon(Icons.star_rounded,
                              size: 10, color: AppColors.gold),
                          const SizedBox(width: 3),
                          Expanded(
                            child: Text(a.displayName,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: text.bodySmall?.copyWith(
                                    fontSize: 10.5,
                                    color: dark
                                        ? Colors.white70
                                        : AppColors.inkSoft)),
                          ),
                          Text(a.score.total.toStringAsFixed(0),
                              style: text.bodySmall?.copyWith(
                                  fontSize: 10.5,
                                  fontWeight: FontWeight.w700)),
                        ]),
                      ),
                  ],
                ),
              ),
            ),
        ]),
      ),
    );
  }
}

/// 단계 사이 경로선. 같은 과목 안의 연결만 그린다 —
/// 과목을 가로지르는 선까지 그리면 지도가 실타래가 된다.
class _EdgePainter extends CustomPainter {
  final Roadmap roadmap;
  final List<String> subjects;
  final double colW;
  final double gap;
  final double axisW;
  final double Function(num) yOf;
  final Color lineColor;

  _EdgePainter({
    required this.roadmap,
    required this.subjects,
    required this.colW,
    required this.gap,
    required this.axisW,
    required this.yOf,
    required this.lineColor,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final byId = {for (final s in roadmap.stages) s.id: s};
    final paint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.4;

    double centerX(RoadmapStage st) {
      final col = subjects.indexOf(st.subject);
      final overlaps = roadmap.stages.any((o) =>
          o.id != st.id &&
          o.subject == st.subject &&
          o.gradeMin <= st.gradeMax &&
          o.gradeMax >= st.gradeMin);
      final laneW = overlaps ? (colW - 4) / 2 : colW;
      return axisW +
          col * (colW + gap) +
          (overlaps && st.lane > 0 ? laneW + 4 : 0) +
          laneW / 2;
    }

    for (final e in roadmap.edges) {
      final a = byId[e.from];
      final b = byId[e.to];
      if (a == null || b == null) continue;
      if (a.subject != b.subject) continue;
      if (!subjects.contains(a.subject)) continue;

      paint.color = switch (e.type) {
        EdgeType.accelerated => AppColors.gold,
        EdgeType.alternative => lineColor,
        _ => AppColors.navyBright.withValues(alpha: 0.5),
      };

      final start = Offset(centerX(a), yOf(a.gradeMax + 1) - 4);
      final end = Offset(centerX(b), yOf(b.gradeMin) + 2);
      final mid = (start.dy + end.dy) / 2;
      canvas.drawPath(
        Path()
          ..moveTo(start.dx, start.dy)
          ..cubicTo(start.dx, mid, end.dx, mid, end.dx, end.dy),
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _EdgePainter old) =>
      old.colW != colW || old.roadmap != roadmap;
}
