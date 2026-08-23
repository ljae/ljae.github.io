import 'package:flutter/material.dart';

import '../core/theme.dart';
import '../data/repository.dart';

/// 순위 추이. 위가 1위다.
///
/// 순위는 낮을수록 좋아서 축을 뒤집는다 — 값이 올라간 그림이 '올랐다'로
/// 읽혀야 한다. 뒤집지 않으면 매번 눈으로 번역해야 한다.
///
/// 점이 하나뿐이면 선을 그리지 않는다. 점 하나를 이어 놓고 추이라 부르는
/// 것은 없는 이야기를 만드는 셈이다.
class RankHistoryChart extends StatelessWidget {
  final List<RankPoint> points;
  final double height;
  const RankHistoryChart({super.key, required this.points, this.height = 120});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    if (points.length < 2) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: AppSpace.md),
        child: Text(
          points.isEmpty
              ? '아직 이력이 없습니다.'
              : '집계를 시작한 날입니다. 추이는 이틀째부터 보입니다.',
          style: text.bodyMedium,
        ),
      );
    }
    return SizedBox(
      height: height,
      child: LayoutBuilder(
        builder: (context, c) => CustomPaint(
          size: Size(c.maxWidth, height),
          painter: _RankPainter(
            points: points,
            line: AppColors.navyBright,
            grid: Theme.of(context).dividerColor,
            label: Theme.of(context).textTheme.bodySmall?.color ??
                AppColors.mist,
          ),
        ),
      ),
    );
  }
}

class _RankPainter extends CustomPainter {
  final List<RankPoint> points;
  final Color line;
  final Color grid;
  final Color label;
  _RankPainter({
    required this.points,
    required this.line,
    required this.grid,
    required this.label,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final ranks = [
      for (final p in points)
        if (p.rank != null) p.rank!,
    ];
    if (ranks.length < 2) return;

    var best = ranks.reduce((a, b) => a < b ? a : b);
    var worst = ranks.reduce((a, b) => a > b ? a : b);
    // 변동이 없으면 납작한 선이 화면 끝에 붙는다. 위아래로 한 칸 벌린다.
    if (best == worst) {
      best = (best - 1).clamp(1, 1 << 20);
      worst = worst + 1;
    }

    const padL = 34.0, padR = 8.0, padT = 10.0, padB = 18.0;
    final w = size.width - padL - padR;
    final h = size.height - padT - padB;
    if (w <= 0 || h <= 0) return;

    double x(int i) => padL + w * (i / (points.length - 1));
    // 순위는 낮을수록 좋다 → 위로 간다.
    double y(int rank) => padT + h * ((rank - best) / (worst - best));

    final gridPaint = Paint()
      ..color = grid
      ..strokeWidth = 1;
    for (final r in {best, worst}) {
      final yy = y(r);
      canvas.drawLine(Offset(padL, yy), Offset(size.width - padR, yy), gridPaint);
      final tp = TextPainter(
        text: TextSpan(
          text: '$r위',
          style: TextStyle(fontSize: 10, color: label, fontFamily: 'Paperlogy'),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, Offset(padL - tp.width - 5, yy - tp.height / 2));
    }

    final path = Path();
    var started = false;
    for (var i = 0; i < points.length; i++) {
      final r = points[i].rank;
      if (r == null) continue;
      final o = Offset(x(i), y(r));
      if (!started) {
        path.moveTo(o.dx, o.dy);
        started = true;
      } else {
        path.lineTo(o.dx, o.dy);
      }
    }
    canvas.drawPath(
        path,
        Paint()
          ..color = line
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2
          ..strokeJoin = StrokeJoin.round);

    // 마지막 점만 강조한다. 지금이 어디인지가 가장 궁금한 값이다.
    final last = points.lastWhere((p) => p.rank != null, orElse: () => points.last);
    if (last.rank != null) {
      final o = Offset(x(points.indexOf(last)), y(last.rank!));
      canvas.drawCircle(o, 4, Paint()..color = line);
      canvas.drawCircle(o, 2, Paint()..color = Colors.white);
    }

    // 양끝 날짜.
    for (final (i, p) in [(0, points.first), (points.length - 1, points.last)]) {
      final tp = TextPainter(
        text: TextSpan(
          text: '${p.day.month}/${p.day.day}',
          style: TextStyle(fontSize: 10, color: label, fontFamily: 'Paperlogy'),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      final dx = (x(i) - tp.width / 2).clamp(padL, size.width - padR - tp.width);
      tp.paint(canvas, Offset(dx, size.height - tp.height));
    }
  }

  @override
  bool shouldRepaint(covariant _RankPainter old) =>
      old.points != points || old.line != line;
}
