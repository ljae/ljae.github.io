import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme.dart';
import '../../data/models.dart';
import '../../data/repository.dart';
import '../../widgets/common.dart';

/// 학군 지도.
///
/// 외부 지도 SDK를 쓰지 않는다. API 키·요금·오프라인 문제를 지고 갈 만큼
/// 얻는 게 없기 때문이다. 필요한 정보는 "어느 학군에 어떤 과목이 얼마나
/// 몰려 있는가"이고, 그건 실제 위경도를 상대 좌표로 옮긴 모식도로 충분하다.
class MapPage extends ConsumerWidget {
  const MapPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(dataProvider);
    return async.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text('$e')),
      data: (data) => ListView(
        padding: const EdgeInsets.symmetric(vertical: AppSpace.lg),
        children: [
          ContentWidth(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SectionHeader('학군 지도',
                    subtitle: '한강 이남 4개 학군의 상대 위치와 과목별 밀도'),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(AppSpace.lg),
                    child: AspectRatio(
                      aspectRatio: 16 / 9,
                      child: _RegionMap(data: data),
                    ),
                  ),
                ),
                const SizedBox(height: AppSpace.lg),
                for (final region in data.regions)
                  _RegionBreakdown(region: region, data: data),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _RegionMap extends ConsumerWidget {
  final EduTreeData data;
  const _RegionMap({required this.data});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final selected = ref.watch(selectionProvider).regionId;

    return LayoutBuilder(builder: (context, constraints) {
      final lats = data.regions.map((r) => r.lat);
      final lngs = data.regions.map((r) => r.lng);
      final minLat = lats.reduce(math.min), maxLat = lats.reduce(math.max);
      final minLng = lngs.reduce(math.min), maxLng = lngs.reduce(math.max);
      const inset = 90.0;

      Offset project(Region r) {
        final x = (r.lng - minLng) / ((maxLng - minLng).abs() < 1e-9 ? 1 : maxLng - minLng);
        final y = (maxLat - r.lat) / ((maxLat - minLat).abs() < 1e-9 ? 1 : maxLat - minLat);
        return Offset(
          inset + x * (constraints.maxWidth - inset * 2),
          inset * 0.7 + y * (constraints.maxHeight - inset * 1.4),
        );
      }

      final maxCount = data.regions
          .map((r) => data.academyCountIn(r.id))
          .fold(1, math.max);

      return Stack(children: [
        Positioned.fill(
          child: CustomPaint(
            painter: _RiverPainter(
              brightness: Theme.of(context).brightness,
            ),
          ),
        ),
        for (final region in data.regions)
          () {
            final center = project(region);
            final count = data.academyCountIn(region.id);
            final radius = 26 + (count / maxCount) * 34;
            final active = region.id == selected;
            return Positioned(
              left: center.dx - radius,
              top: center.dy - radius,
              width: radius * 2,
              height: radius * 2,
              child: _RegionBubble(
                region: region,
                count: count,
                active: active,
                onTap: () {
                  ref.read(selectionProvider.notifier).setRegion(region.id);
                  context.go('/tree');
                },
              ),
            );
          }(),
      ]);
    });
  }
}

class _RiverPainter extends CustomPainter {
  final Brightness brightness;
  const _RiverPainter({required this.brightness});

  @override
  void paint(Canvas canvas, Size size) {
    // 한강. 4개 학군이 모두 강남권이라는 지리적 맥락을 한 줄로 전달한다.
    final paint = Paint()
      ..color = AppColors.reputation
          .withValues(alpha: brightness == Brightness.dark ? 0.20 : 0.13)
      ..style = PaintingStyle.stroke
      ..strokeWidth = size.height * 0.13
      ..strokeCap = StrokeCap.round;

    final y = size.height * 0.17;
    final path = Path()
      ..moveTo(0, y)
      ..quadraticBezierTo(size.width * 0.35, y - size.height * 0.09,
          size.width * 0.62, y + size.height * 0.03)
      ..quadraticBezierTo(size.width * 0.82, y + size.height * 0.1,
          size.width, y + size.height * 0.02);
    canvas.drawPath(path, paint);

    final tp = TextPainter(
      text: TextSpan(
        text: '한강',
        style: TextStyle(
          fontFamily: 'Paperlogy',
          fontSize: 11,
          color: AppColors.reputation.withValues(alpha: 0.55),
        ),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(canvas, Offset(size.width * 0.04, y - 7));
  }

  @override
  bool shouldRepaint(_RiverPainter old) => old.brightness != brightness;
}

class _RegionBubble extends StatelessWidget {
  final Region region;
  final int count;
  final bool active;
  final VoidCallback onTap;
  const _RegionBubble({
    required this.region,
    required this.count,
    required this.active,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: '${region.nameKo} · ${region.dongList.join(", ")}\n학원 $count곳',
      child: GestureDetector(
        onTap: onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: active
                  ? [AppColors.evergreenBright, AppColors.evergreen]
                  : [
                      AppColors.evergreen.withValues(alpha: 0.30),
                      AppColors.evergreen.withValues(alpha: 0.50),
                    ],
            ),
            boxShadow: [
              BoxShadow(
                color: AppColors.evergreen.withValues(alpha: active ? 0.35 : 0.12),
                blurRadius: active ? 26 : 12,
              ),
            ],
          ),
          alignment: Alignment.center,
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Text(region.nameKo,
                style: const TextStyle(
                  fontFamily: 'Paperlogy',
                  fontSize: 15,
                  fontWeight: FontWeight.w800,
                  color: Colors.white,
                )),
            Text('$count',
                style: TextStyle(
                  fontFamily: 'Paperlogy',
                  fontSize: 11,
                  color: Colors.white.withValues(alpha: 0.85),
                )),
          ]),
        ),
      ),
    );
  }
}

class _RegionBreakdown extends StatelessWidget {
  final Region region;
  final EduTreeData data;
  const _RegionBreakdown({required this.region, required this.data});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final rows = data.academies.where((a) => a.regionId == region.id).toList();
    final bySubject = <String, int>{};
    for (final a in rows) {
      for (final s in a.subjects) {
        bySubject[s] = (bySubject[s] ?? 0) + 1;
      }
    }
    final total = bySubject.values.fold(0, (a, b) => a + b).clamp(1, 1 << 30);

    return Card(
      margin: const EdgeInsets.only(bottom: AppSpace.sm),
      child: Padding(
        padding: const EdgeInsets.all(AppSpace.md),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Text(region.nameKo, style: text.titleLarge),
            const SizedBox(width: AppSpace.sm),
            Text(region.dongList.join(' · '), style: text.bodySmall),
            const Spacer(),
            Text('${rows.length}곳', style: text.labelLarge),
          ]),
          const SizedBox(height: AppSpace.sm),
          ClipRRect(
            borderRadius: BorderRadius.circular(AppRadius.pill),
            child: SizedBox(
              height: 9,
              child: Row(children: [
                for (final e in bySubject.entries)
                  Expanded(
                    flex: (e.value / total * 1000).round().clamp(1, 1000),
                    child: Container(
                        color: AppColors.subjects[e.key] ?? AppColors.slate),
                  ),
              ]),
            ),
          ),
          const SizedBox(height: AppSpace.sm),
          Wrap(spacing: AppSpace.sm, runSpacing: 6, children: [
            for (final e in bySubject.entries)
              Chip2('${subjectNames[e.key] ?? e.key} ${e.value}',
                  color: AppColors.subjects[e.key] ?? AppColors.slate),
          ]),
        ]),
      ),
    );
  }
}
