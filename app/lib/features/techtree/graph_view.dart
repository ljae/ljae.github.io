import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../core/theme.dart';
import '../../data/models.dart';
import '../../data/repository.dart';
import '../../widgets/common.dart';

/// 테크트리 그래프.
///
/// 노드 좌표는 큐레이션 데이터의 depth(가로) / lane(세로)에서 결정론적으로
/// 나온다. 자동 레이아웃(force-directed 등)을 쓰지 않는 이유는, 이 그래프가
/// "학년이 올라가며 왼쪽에서 오른쪽으로 진행한다"는 의미를 담고 있어서
/// 위치 자체가 정보이기 때문이다. 매번 같은 자리에 있어야 읽힌다.
class TechTreeGraph extends StatefulWidget {
  final Track track;
  final EduTreeData data;
  final String regionId;
  final ValueChanged<Stage> onStageTap;

  const TechTreeGraph({
    super.key,
    required this.track,
    required this.data,
    required this.regionId,
    required this.onStageTap,
  });

  @override
  State<TechTreeGraph> createState() => _TechTreeGraphState();
}

class _TechTreeGraphState extends State<TechTreeGraph> {
  static const nodeW = 236.0;
  static const nodeH = 132.0;
  static const hGap = 76.0;
  static const vGap = 28.0;
  static const pad = 32.0;

  final _controller = TransformationController();
  String? _hovered;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Map<String, Offset> _layout() {
    // lane 값이 듬성듬성해도 화면에서는 촘촘히 붙도록 인덱스로 압축한다.
    final lanes = widget.track.stages.map((s) => s.lane).toSet().toList()..sort();
    final laneIndex = {for (var i = 0; i < lanes.length; i++) lanes[i]: i};

    return {
      for (final s in widget.track.stages)
        s.id: Offset(
          pad + s.depth * (nodeW + hGap),
          pad + laneIndex[s.lane]! * (nodeH + vGap),
        )
    };
  }

  @override
  Widget build(BuildContext context) {
    final positions = _layout();
    final maxX =
        positions.values.map((o) => o.dx).fold(0.0, math.max) + nodeW + pad;
    final maxY =
        positions.values.map((o) => o.dy).fold(0.0, math.max) + nodeH + pad;

    return InteractiveViewer(
      transformationController: _controller,
      minScale: 0.45,
      maxScale: 2.2,
      boundaryMargin: const EdgeInsets.all(120),
      constrained: false,
      child: SizedBox(
        width: maxX,
        height: maxY,
        child: Stack(children: [
          Positioned.fill(
            child: CustomPaint(
              painter: _EdgePainter(
                edges: widget.track.edges,
                positions: positions,
                nodeSize: const Size(nodeW, nodeH),
                highlighted: _hovered,
              ),
            ),
          ),
          for (final stage in widget.track.stages)
            Positioned(
              left: positions[stage.id]!.dx,
              top: positions[stage.id]!.dy,
              width: nodeW,
              height: nodeH,
              child: _StageNode(
                stage: stage,
                academies: widget.data
                    .academiesForStage(stage.id, regionId: widget.regionId),
                subject: widget.track.subject,
                hovered: _hovered == stage.id,
                onHover: (v) => setState(() => _hovered = v ? stage.id : null),
                onTap: () => widget.onStageTap(stage),
              ),
            ),
        ]),
      ),
    );
  }
}

class _EdgePainter extends CustomPainter {
  final List<StageEdge> edges;
  final Map<String, Offset> positions;
  final Size nodeSize;
  final String? highlighted;

  _EdgePainter({
    required this.edges,
    required this.positions,
    required this.nodeSize,
    this.highlighted,
  });

  @override
  void paint(Canvas canvas, Size size) {
    for (final edge in edges) {
      final from = positions[edge.from];
      final to = positions[edge.to];
      if (from == null || to == null) continue;

      final start = Offset(from.dx + nodeSize.width, from.dy + nodeSize.height / 2);
      final end = Offset(to.dx, to.dy + nodeSize.height / 2);

      final active =
          highlighted != null && (edge.from == highlighted || edge.to == highlighted);
      final color = switch (edge.type) {
        EdgeType.accelerated => AppColors.gold,
        EdgeType.alternative => AppColors.mist,
        EdgeType.standard => AppColors.navyBright,
      };

      final paint = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = active ? 2.8 : 1.7
        ..strokeCap = StrokeCap.round
        ..color = color.withValues(alpha: active ? 0.95 : 0.42);

      // 수평으로 빠져나갔다 들어오는 3차 베지어. 계층 그래프에서 가장 읽기 쉽다.
      final dx = (end.dx - start.dx).abs();
      final control = math.max(48.0, dx * 0.45);
      final path = Path()
        ..moveTo(start.dx, start.dy)
        ..cubicTo(start.dx + control, start.dy, end.dx - control, end.dy,
            end.dx, end.dy);

      if (edge.type == EdgeType.alternative) {
        _drawDashed(canvas, path, paint);
      } else {
        canvas.drawPath(path, paint);
      }
      _drawArrow(canvas, end, paint..style = PaintingStyle.fill);
    }
  }

  void _drawDashed(Canvas canvas, Path path, Paint paint) {
    const dash = 7.0, gap = 5.0;
    for (final metric in path.computeMetrics()) {
      var distance = 0.0;
      while (distance < metric.length) {
        canvas.drawPath(
            metric.extractPath(distance, math.min(distance + dash, metric.length)),
            paint);
        distance += dash + gap;
      }
    }
  }

  void _drawArrow(Canvas canvas, Offset tip, Paint paint) {
    const s = 5.0;
    final path = Path()
      ..moveTo(tip.dx, tip.dy)
      ..lineTo(tip.dx - s * 1.6, tip.dy - s * 0.8)
      ..lineTo(tip.dx - s * 1.6, tip.dy + s * 0.8)
      ..close();
    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(_EdgePainter old) =>
      old.highlighted != highlighted || old.edges != edges;
}

class _StageNode extends StatelessWidget {
  final Stage stage;
  final List<Academy> academies;
  final String subject;
  final bool hovered;
  final ValueChanged<bool> onHover;
  final VoidCallback onTap;

  const _StageNode({
    required this.stage,
    required this.academies,
    required this.subject,
    required this.hovered,
    required this.onHover,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final accent = AppColors.subjects[subject] ?? AppColors.navy;
    final text = Theme.of(context).textTheme;
    final flagship = academies.where((a) => a.isFlagshipOf(stage.id)).toList();
    final shown = [...flagship, ...academies.where((a) => !flagship.contains(a))]
        .take(3)
        .toList();

    return MouseRegion(
      onEnter: (_) => onHover(true),
      onExit: (_) => onHover(false),
      child: GestureDetector(
        onTap: onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 140),
          decoration: BoxDecoration(
            color: dark ? AppColors.darkSurface : AppColors.surface,
            borderRadius: BorderRadius.circular(AppRadius.md),
            border: Border.all(
              color: hovered ? accent : (dark ? AppColors.darkLine : AppColors.line),
              width: hovered ? 1.8 : 1,
            ),
            boxShadow: [
              BoxShadow(
                color: accent.withValues(alpha: hovered ? 0.16 : 0.05),
                blurRadius: hovered ? 20 : 8,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          padding: const EdgeInsets.all(13),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(children: [
                Container(width: 3, height: 15, color: accent),
                const SizedBox(width: 7),
                Expanded(
                  child: Text(stage.title,
                      style: text.titleMedium?.copyWith(fontSize: 14.5),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis),
                ),
                Chip2(stage.gradeLabel, color: accent),
              ]),
              if (stage.subtitle != null) ...[
                const SizedBox(height: 3),
                Text(stage.subtitle!,
                    style: text.bodySmall?.copyWith(fontSize: 11.5),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis),
              ],
              const Spacer(),
              if (shown.isEmpty)
                Text('이 학군에 등록된 학원 없음',
                    style: text.bodySmall?.copyWith(fontSize: 11))
              else
                ...shown.map((a) => Padding(
                      padding: const EdgeInsets.only(top: 3),
                      child: Row(children: [
                        if (a.isFlagshipOf(stage.id))
                          const Icon(Icons.star_rounded,
                              size: 11, color: AppColors.gold)
                        else
                          const Icon(Icons.circle,
                              size: 4, color: AppColors.mist),
                        const SizedBox(width: 5),
                        Expanded(
                          child: Text(a.displayName,
                              style: text.bodySmall?.copyWith(
                                  fontSize: 11.5,
                                  color: dark
                                      ? const Color(0xFFC9D3DA)
                                      : AppColors.inkSoft),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis),
                        ),
                        Text(a.score.total.toStringAsFixed(0),
                            style: text.bodySmall?.copyWith(
                                fontSize: 10.5, fontWeight: FontWeight.w700)),
                      ]),
                    )),
              if (academies.length > 3)
                Padding(
                  padding: const EdgeInsets.only(top: 3),
                  child: Text('+${academies.length - 3}곳 더',
                      style: text.bodySmall
                          ?.copyWith(fontSize: 10.5, color: accent)),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
