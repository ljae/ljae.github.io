import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/env.dart';
import '../../core/theme.dart';
import '../../data/models.dart';
import '../../data/repository.dart';
import '../../widgets/common.dart';
import 'naver_map.dart';

/// 학군지도.
///
/// 학원이 아니라 **학교**가 주인공이다. 어느 학교에 배정되는지가 곧 학군이고,
/// 학부모가 집을 고를 때 실제로 보는 것도 그것이다. 학원은 참고 레이어로만 얹는다.
class MapPage extends ConsumerStatefulWidget {
  const MapPage({super.key});

  @override
  ConsumerState<MapPage> createState() => _MapPageState();
}

class _MapPageState extends ConsumerState<MapPage> {
  String? _level;          // null = 초·중·고 전체
  bool _showAcademies = false;

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(dataProvider);
    final sel = ref.watch(selectionProvider);

    return async.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text('$e')),
      data: (data) {
        final region = data.regionById[sel.regionId];
        final schools = data.schoolsIn(sel.regionId, level: _level);
        final academies = _showAcademies
            ? data.academies
                .where((a) => a.regionId == sel.regionId && a.lat != null)
                .toList()
            : <Academy>[];

        return ListView(
          padding: const EdgeInsets.symmetric(vertical: AppSpace.lg),
          children: [
            ContentWidth(
              max: 1320,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SectionHeader('${region?.nameKo ?? ''} 학군지도',
                      subtitle: '학군은 학원이 아니라 학교로 정해집니다. '
                          '초·중·고 위치를 보고, 필요하면 학원을 겹쳐 보세요.'),
                  ChipRow<String>(
                    options: [for (final r in data.regions) (r.id, r.nameKo)],
                    selected: sel.regionId,
                    onChanged: ref.read(selectionProvider.notifier).setRegion,
                  ),
                  const SizedBox(height: AppSpace.sm),
                  Row(children: [
                    Expanded(
                      child: ChipRow<String?>(
                        options: const [
                          (null, '초·중·고 전체'),
                          ('elementary', '초등학교'),
                          ('middle', '중학교'),
                          ('high', '고등학교'),
                        ],
                        selected: _level,
                        onChanged: (v) => setState(() => _level = v),
                      ),
                    ),
                    const SizedBox(width: AppSpace.md),
                    FilterChip(
                      label: const Text('학원 겹쳐 보기'),
                      selected: _showAcademies,
                      onSelected: (v) => setState(() => _showAcademies = v),
                    ),
                  ]),
                  const SizedBox(height: AppSpace.md),
                  _MapSurface(
                    region: region,
                    schools: schools,
                    academies: academies,
                    data: data,
                  ),
                  const SizedBox(height: AppSpace.lg),
                  _SchoolList(schools: schools, region: region),
                  const SizedBox(height: AppSpace.xl),
                  const _PendingNotice(),
                  const SizedBox(height: AppSpace.xxl),
                ],
              ),
            ),
          ],
        );
      },
    );
  }
}

class _MapSurface extends StatelessWidget {
  final Region? region;
  final List<School> schools;
  final List<Academy> academies;
  final EduTreeData data;
  const _MapSurface({
    required this.region,
    required this.schools,
    required this.academies,
    required this.data,
  });

  String _markers() {
    final items = <Map<String, dynamic>>[];
    for (final s in schools.where((s) => s.hasLocation)) {
      items.add({
        'lat': s.lat, 'lng': s.lng, 'label': s.name,
        'title': s.name,
        'subtitle': [s.levelLabel, s.foundation, s.coed]
            .whereType<String>().where((x) => x.isNotEmpty).join(' · '),
        'color': '#${schoolLevelColors[s.level]!.toRadixString(16).substring(2)}',
        'z': 3,
      });
    }
    for (final a in academies) {
      items.add({
        'lat': a.lat, 'lng': a.lng, 'label': a.displayName,
        'title': a.displayName,
        'subtitle': '트리스코어 ${a.score.total.toStringAsFixed(0)} · '
            '${a.subjects.map((s) => subjectNames[s] ?? s).join(", ")}',
        'color': '#6B7785',
        'z': 1,
      });
    }
    return jsonEncode(items);
  }

  @override
  Widget build(BuildContext context) {
    final usable = Env.hasNaverMap &&
        naverMapAvailable &&
        schools.any((s) => s.hasLocation);

    return Card(
      clipBehavior: Clip.antiAlias,
      child: AspectRatio(
        aspectRatio: 16 / 10,
        child: usable
            ? NaverMapView(
                lat: region?.lat ?? 37.5,
                lng: region?.lng ?? 127.0,
                zoom: 15,
                markersJson: _markers(),
              )
            : _Schematic(data: data, schools: schools),
      ),
    );
  }
}

/// 지도 키가 없거나 SDK 인증이 실패했을 때. 화면이 비지 않도록 모식도로 대체한다.
class _Schematic extends StatelessWidget {
  final EduTreeData data;
  final List<School> schools;
  const _Schematic({required this.data, required this.schools});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final located = schools.where((s) => s.hasLocation).toList();

    return LayoutBuilder(builder: (context, c) {
      if (located.isEmpty) {
        return Center(
          child: Padding(
            padding: const EdgeInsets.all(AppSpace.lg),
            child: Text('표시할 학교 좌표가 없습니다.', style: text.bodyMedium),
          ),
        );
      }
      final lats = located.map((s) => s.lat!);
      final lngs = located.map((s) => s.lng!);
      final minLat = lats.reduce(math.min), maxLat = lats.reduce(math.max);
      final minLng = lngs.reduce(math.min), maxLng = lngs.reduce(math.max);
      const pad = 46.0;

      return Stack(children: [
        Positioned.fill(child: Container(color: const Color(0xFFEFF1EC))),
        for (final s in located)
          Positioned(
            left: pad +
                ((s.lng! - minLng) / ((maxLng - minLng).abs() < 1e-9 ? 1 : maxLng - minLng)) *
                    (c.maxWidth - pad * 2),
            top: pad +
                ((maxLat - s.lat!) / ((maxLat - minLat).abs() < 1e-9 ? 1 : maxLat - minLat)) *
                    (c.maxHeight - pad * 2),
            child: FractionalTranslation(
              translation: const Offset(-0.5, -0.5),
              child: Tooltip(
                message: '${s.name}\n${s.levelLabel} · ${s.foundation ?? ''}',
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
                  decoration: BoxDecoration(
                    color: Color(schoolLevelColors[s.level]!),
                    borderRadius: BorderRadius.circular(AppRadius.pill),
                  ),
                  child: Text(s.name,
                      style: const TextStyle(
                          fontFamily: 'Paperlogy',
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                          color: Colors.white)),
                ),
              ),
            ),
          ),
        Positioned(
          left: AppSpace.md,
          bottom: AppSpace.md,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.92),
              borderRadius: BorderRadius.circular(AppRadius.sm),
            ),
            child: Text('네이버 지도 키가 없어 모식도로 표시 중입니다',
                style: text.bodySmall),
          ),
        ),
      ]);
    });
  }
}

class _SchoolList extends StatelessWidget {
  final List<School> schools;
  final Region? region;
  const _SchoolList({required this.schools, required this.region});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final byLevel = <String, List<School>>{};
    for (final s in schools) {
      byLevel.putIfAbsent(s.level, () => []).add(s);
    }
    const order = ['elementary', 'middle', 'high'];

    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      SectionHeader('${region?.nameKo ?? ''} 학교 ${schools.length}곳',
          subtitle: 'NEIS 학교기본정보 공시 기준'),
      for (final level in order)
        if ((byLevel[level] ?? []).isNotEmpty) ...[
          Padding(
            padding: const EdgeInsets.only(top: AppSpace.sm, bottom: 6),
            child: Row(children: [
              Container(width: 8, height: 8,
                  decoration: BoxDecoration(
                      color: Color(schoolLevelColors[level]!),
                      shape: BoxShape.circle)),
              const SizedBox(width: 6),
              Text('${byLevel[level]!.first.levelLabel} ${byLevel[level]!.length}곳',
                  style: text.titleMedium),
            ]),
          ),
          Wrap(spacing: AppSpace.sm, runSpacing: AppSpace.sm, children: [
            for (final s in byLevel[level]!)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 7),
                decoration: BoxDecoration(
                  border: Border.all(color: AppColors.line),
                  borderRadius: BorderRadius.circular(AppRadius.sm),
                ),
                child: Row(mainAxisSize: MainAxisSize.min, children: [
                  Text(s.name, style: text.labelLarge),
                  const SizedBox(width: 6),
                  Text([s.foundation, s.coed].whereType<String>().join(' · '),
                      style: text.bodySmall?.copyWith(fontSize: 11)),
                ]),
              ),
          ]),
        ],
    ]);
  }
}

class _PendingNotice extends StatelessWidget {
  const _PendingNotice();

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Card(
      color: AppColors.estimated.withValues(alpha: 0.07),
      child: Padding(
        padding: const EdgeInsets.all(AppSpace.md),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            const Icon(Icons.construction, size: 17, color: AppColors.estimated),
            const SizedBox(width: AppSpace.sm),
            Text('준비 중', style: text.titleMedium),
          ]),
          const SizedBox(height: 6),
          Text(
            '통학구역 경계와 배정 아파트는 학구도 공공데이터(폴리곤)를 받아 얹을 예정입니다.\n'
            '학교 순위는 학교알리미 공시의 졸업생 진로현황(특목고·자사고 진학 실적)을 '
            '근거로 삼습니다. 별도 API 키가 필요합니다.',
            style: text.bodyMedium,
          ),
        ]),
      ),
    );
  }
}
