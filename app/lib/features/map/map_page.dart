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
  String? _level; // null = 초·중·고 전체
  bool _showAcademies = false;
  bool _showApartments = true;

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(dataProvider);
    // 지도 데이터는 이 화면에서 처음 읽는다.
    final mapAsync = ref.watch(mapDataProvider);
    final sel = ref.watch(selectionProvider);

    if (async.hasError || mapAsync.hasError) {
      return Center(child: Text('${async.error ?? mapAsync.error}'));
    }
    if (!async.hasValue || !mapAsync.hasValue) {
      return const Center(child: CircularProgressIndicator());
    }
    final mapData = mapAsync.requireValue;

    return async.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text('$e')),
      data: (data) {
        final region = data.regionById[sel.regionId];
        final schools = mapData.schoolsIn(sel.regionId, level: _level);
        final academies = _showAcademies
            ? data.academies
                  .where(
                    (a) =>
                        EduTreeData.matchRegion(a.regionId, sel.regionId) &&
                        a.lat != null,
                  )
                  .toList()
            : <Academy>[];
        final apartments = _showApartments
            ? mapData
                  .apartmentsIn(sel.regionId)
                  .where((a) => a.hasLocation)
                  .toList()
            : <Apartment>[];

        return ListView(
          padding: const EdgeInsets.symmetric(vertical: AppSpace.lg),
          children: [
            ContentWidth(
              max: 1320,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SectionHeader(
                    '${region?.nameKo ?? ''} 학군지도',
                    subtitle:
                        '학군은 학원이 아니라 학교로 정해집니다. '
                        '초·중·고 위치를 보고, 필요하면 학원을 겹쳐 보세요.',
                  ),
                  Row(
                    children: [
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
                        label: const Text('아파트'),
                        selected: _showApartments,
                        onSelected: (v) => setState(() => _showApartments = v),
                      ),
                      const SizedBox(width: AppSpace.sm),
                      FilterChip(
                        label: const Text('학원'),
                        selected: _showAcademies,
                        onSelected: (v) => setState(() => _showAcademies = v),
                      ),
                    ],
                  ),
                  const SizedBox(height: AppSpace.md),
                  _MapSurface(
                    region: region,
                    allRegions: sel.isAllRegions,
                    regions: data.regions,
                    schools: schools,
                    academies: academies,
                    apartments: apartments,
                    mapData: mapData,
                    level: _level,
                  ),
                  const SizedBox(height: AppSpace.lg),
                  if (apartments.isNotEmpty)
                    _ApartmentList(apartments: apartments),
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
  final bool allRegions;
  final List<Region> regions;
  final List<School> schools;
  final List<Academy> academies;
  final List<Apartment> apartments;
  final MapData mapData;
  final String? level;
  const _MapSurface({
    required this.region,
    this.allRegions = false,
    this.regions = const [],
    required this.schools,
    required this.academies,
    this.apartments = const [],
    required this.mapData,
    this.level,
  });

  /// 마커 정보창의 학교급 한 줄.
  ///
  /// 중·고는 학교군 안 추첨이라 '여기로 간다'고 말할 수 없다. 그렇다고
  /// 11개교를 늘어놓기만 하면 화면이 학부모보다 덜 아는 셈이다 — 배정에
  /// 통학 편의가 반영되므로 가까운 학교로 갈 확률이 실제로 높고, 학부모도
  /// 그렇게 안다. 가까운 순 세 곳을 거리와 함께 보여주는 선에서 멈춘다.
  /// 확률(%)로 바꾸지 않는다 — 실제 배정 결과 자료가 없다.
  static String _zoneLine(ApartmentZone z) {
    // 초등은 배정이 확정이라 학교를 그대로 적는다.
    if (z.level == 'elementary') return '${z.levelLabel} ${z.assignmentText}';

    // 중·고는 **가까운 세 곳을 앞세운다.**
    //
    // 예전에는 'OO학교군 · 11개교 중 추첨' 이 머리에 오고 학교 이름이
    // 뒤에 붙었다. 학부모가 알고 싶은 것은 '어디로 갈 가능성이 큰가'
    // 인데, 머리에 온 말이 '알 수 없다' 라 화면이 학부모보다 덜 아는
    // 셈이었다. 배정에 통학 편의가 반영되므로 가까운 학교로 갈 확률이
    // 실제로 높고, 학부모도 '추첨이지만 보통 저기 간다' 로 안다.
    //
    // 그래도 **확률(%)로는 바꾸지 않는다** — 실제 배정 결과 자료가 없다.
    // 거리와 순서까지만 말하고, 추첨이라는 사실은 작게 뒤에 남긴다.
    if (z.nearby.isEmpty) return '${z.levelLabel} ${z.assignmentText}';
    final top = z.nearby.take(3).toList();
    final names = [
      for (var i = 0; i < top.length; i++)
        '${i + 1}. ${top[i].name} ${top[i].distanceLabel}${top[i].coedTag}',
    ].join(' · ');
    return '<span style="color:#0B1020">${z.levelLabel} 가까운 순 $names</span>'
        '<br><span style="font-size:10.5px">'
        '${z.zoneName ?? ""} · 추첨이지만 통학 편의가 반영됩니다</span>';
  }

  /// 지도 위 단지 이름. **짧을수록 많이 산다.**
  ///
  /// 원본은 '대치풍림아이원아파트 1.2단지' 처럼 길고, 앞의 학군 이름과
  /// 끝의 '아파트' 는 이 지도에서 이미 아는 말이라 자리만 차지한다.
  /// 이름표가 길면 겹쳐서 접히고, 접히면 화면에서 사라진 것처럼 보인다.
  /// 누르면 뜨는 제목에는 **원래 이름을 그대로** 쓴다.
  static String _shortAptName(String name) {
    var s = name.replaceAll(RegExp(r'^(대치|목동|반포|잠실)\s*'), '');
    s = s.replaceAll(RegExp(r'아파트'), '');
    s = s.replaceAll(RegExp(r'\s+'), ' ').trim();
    if (s.isEmpty) s = name;
    return s.characters.length > 9
        ? '${s.characters.take(9)}…'
        : s;
  }

  String _markers() {
    final items = <Map<String, dynamic>>[];
    for (final s in schools.where((s) => s.hasLocation)) {
      items.add({
        'lat': s.lat,
        'lng': s.lng,
        'label': s.name,
        'title': s.name,
        'subtitle': [
          s.levelLabel,
          s.foundation,
          s.coed,
          if (s.zoneName != null) s.zoneName,
          if (s.zonePeers.isNotEmpty) '학교군 ${s.zonePeers.length + 1}개교 추첨',
        ].whereType<String>().where((x) => x.isNotEmpty).join(' · '),
        'color':
            '#${schoolLevelColors[s.level]!.toRadixString(16).substring(2)}',
        'z': 3,
      });
    }
    for (final a in apartments) {
      items.add({
        'lat': a.lat,
        'lng': a.lng,
        'label': _shortAptName(a.name),
        // 작은 이름표로 그린다. 한 화면에 학교 36곳 + 단지 79곳이 서는데
        // 같은 크기로 두면 단지가 전부 접혀 '아파트가 없다' 로 보인다.
        'small': true,
        'title': a.name,
        'subtitle': [
          [
            a.dong,
            if (a.households != null) '${a.households}세대',
          ].whereType<String>().join(' · '),
          ...a.zones.map(_zoneLine),
        ].where((x) => x.isNotEmpty).join('<br>'),
        'color': '#8B5CF6',
        'z': 2,
      });
    }
    for (final a in academies) {
      items.add({
        'lat': a.lat,
        'lng': a.lng,
        'label': a.displayName,
        'title': a.displayName,
        'subtitle':
            '트리스코어 ${a.score.total.toStringAsFixed(0)} · '
            '${orderedSubjects(a.subjects).map((s) => subjectNames[s]!).join(", ")}',
        'color': '#6B7785',
        'z': 1,
      });
    }
    // 선택한 학군에 걸친 구역만 그린다.
    //
    // 처음에는 전체 227개를 다 그렸는데, fillOpacity 0.1 짜리 폴리곤이
    // 겹겹이 쌓여 지도를 하얗게 덮어 버렸다. 타일이 안 나오는 것처럼 보여
    // 한참 엉뚱한 곳을 팠다. 실제로 타일은 정상이었고 위가 가려져 있었다.
    final activeZones = <String>{
      for (final s in schools)
        if (s.zoneId != null) s.zoneId!,
      for (final a in apartments)
        for (final z in a.zones)
          if (z.zoneId != null) z.zoneId!,
    };

    final zonePolys = <Map<String, dynamic>>[];
    for (final f in mapData.zoneFeatures) {
      final props = (f['properties'] as Map).cast<String, dynamic>();
      if (level != null && props['level'] != level) continue;
      if (activeZones.isNotEmpty && !activeZones.contains(props['zoneId'])) {
        continue;
      }
      final geom = (f['geometry'] as Map).cast<String, dynamic>();
      zonePolys.add({
        'name': props['zoneName'],
        'subtitle':
            '${props['level'] == 'high' ? '고등학교' : '중학교'} 학교군 · '
            '${props['eduOffice'] ?? ''}',
        'color': props['level'] == 'high' ? '#B4531E' : '#1E7A5A',
        'rings': geom['coordinates'],
      });
    }
    return jsonEncode({'markers': items, 'zones': zonePolys});
  }

  @override
  Widget build(BuildContext context) {
    final usable =
        Env.hasNaverMap &&
        naverMapAvailable &&
        schools.any((s) => s.hasLocation);

    return Card(
      clipBehavior: Clip.antiAlias,
      child: AspectRatio(
        aspectRatio: 16 / 10,
        child: usable
            ? NaverMapView(
                // '전체'일 때는 4개 학군 중심의 평균으로 잡고 한 단계 넓게 본다.
                lat: allRegions && regions.isNotEmpty
                    ? regions.map((r) => r.lat).reduce((a, b) => a + b) /
                          regions.length
                    : region?.lat ?? 37.5,
                lng: allRegions && regions.isNotEmpty
                    ? regions.map((r) => r.lng).reduce((a, b) => a + b) /
                          regions.length
                    : region?.lng ?? 127.0,
                zoom: allRegions ? 12 : 15,
                markersJson: _markers(),
              )
            : _Schematic(schools: schools),
      ),
    );
  }
}

/// 지도 키가 없거나 SDK 인증이 실패했을 때. 화면이 비지 않도록 모식도로 대체한다.
class _Schematic extends StatelessWidget {
  final List<School> schools;
  const _Schematic({required this.schools});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final located = schools.where((s) => s.hasLocation).toList();

    return LayoutBuilder(
      builder: (context, c) {
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

        return Stack(
          children: [
            Positioned.fill(child: Container(color: const Color(0xFFEFF1EC))),
            for (final s in located)
              Positioned(
                left:
                    pad +
                    ((s.lng! - minLng) /
                            ((maxLng - minLng).abs() < 1e-9
                                ? 1
                                : maxLng - minLng)) *
                        (c.maxWidth - pad * 2),
                top:
                    pad +
                    ((maxLat - s.lat!) /
                            ((maxLat - minLat).abs() < 1e-9
                                ? 1
                                : maxLat - minLat)) *
                        (c.maxHeight - pad * 2),
                child: FractionalTranslation(
                  translation: const Offset(-0.5, -0.5),
                  child: Tooltip(
                    message:
                        '${s.name}\n${s.levelLabel} · ${s.foundation ?? ''}',
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 7,
                        vertical: 3,
                      ),
                      decoration: BoxDecoration(
                        color: Color(schoolLevelColors[s.level]!),
                        borderRadius: BorderRadius.circular(AppRadius.pill),
                      ),
                      child: Text(
                        s.name,
                        style: const TextStyle(
                          fontFamily: 'Paperlogy',
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                          color: Colors.white,
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            Positioned(
              left: AppSpace.md,
              bottom: AppSpace.md,
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 6,
                ),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.92),
                  borderRadius: BorderRadius.circular(AppRadius.sm),
                ),
                child: Text('네이버 지도 키가 없어 모식도로 표시 중입니다', style: text.bodySmall),
              ),
            ),
          ],
        );
      },
    );
  }
}

/// 아파트별 배정 학교. 학부모가 실제로 찾는 정보라 목록으로도 둔다.
class _ApartmentList extends StatelessWidget {
  final List<Apartment> apartments;
  const _ApartmentList({required this.apartments});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final rows = apartments.take(40).toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SectionHeader(
          '아파트별 배정 학교 (${apartments.length}단지)',
          subtitle:
              '초등학교는 통학구역이라 배정이 확정됩니다. '
              '중·고등학교는 학교군 추첨이라 학교를 특정할 수 없지만, '
              '통학 편의가 반영되므로 가까운 학교일수록 갈 확률이 높습니다.',
        ),
        for (final a in rows)
          Card(
            margin: const EdgeInsets.only(bottom: AppSpace.sm),
            child: Padding(
              padding: const EdgeInsets.all(AppSpace.md),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(child: Text(a.name, style: text.titleMedium)),
                      if (a.households != null)
                        Text('${a.households}세대', style: text.bodySmall),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    children: [
                      for (final z in a.zones)
                        Chip2(
                          '${z.levelLabel} · ${z.assignmentText}',
                          color: z.certain
                              ? AppColors.verified
                              : (z.level == 'elementary'
                                    ? AppColors.reputation
                                    : AppColors.estimated),
                          icon: z.certain ? Icons.verified_rounded : null,
                        ),
                    ],
                  ),
                  for (final z in a.zones)
                    if (z.nearby.isNotEmpty) _NearbyRow(zone: z),
                ],
              ),
            ),
          ),
        if (apartments.length > rows.length)
          Padding(
            padding: const EdgeInsets.only(top: AppSpace.sm),
            child: Text(
              '외 ${apartments.length - rows.length}단지',
              style: text.bodySmall,
            ),
          ),
      ],
    );
  }
}

/// 학교군 안에서 가까운 학교를 가까운 순으로 보여준다.
///
/// 추첨이라 '어디로 간다'고 말할 수는 없다. 그렇다고 아홉 개 학교를
/// 나란히 늘어놓기만 하면 화면이 학부모보다 덜 아는 셈이 된다 —
/// 실제로는 '추첨이지만 보통 저기 간다'는 감각이 있고, 그 근거는
/// 배정에 반영되는 통학 편의다. 거리를 그대로 보여주는 선에서 멈춘다.
/// 확률(%)로 바꾸지 않는 이유는 실제 배정 결과 자료가 없기 때문이다.
class _NearbyRow extends StatelessWidget {
  final ApartmentZone zone;
  const _NearbyRow({required this.zone});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.only(top: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.near_me_outlined,
                size: 13,
                color: AppColors.mist,
              ),
              const SizedBox(width: 4),
              Text(
                '${zone.levelLabel} 배정 가능성 높은 순 (추첨이지만 통학 편의 반영)',
                style: text.bodySmall?.copyWith(fontSize: 11),
              ),
            ],
          ),
          const SizedBox(height: 3),
          // 지도 마커와 같은 세 곳을 보여준다. 화면마다 개수가 다르면
          // 같은 값을 두 번 읽어야 한다.
          Wrap(
            spacing: 6,
            runSpacing: 4,
            children: [
              for (var i = 0; i < zone.nearby.take(3).length; i++)
                Text(
                  '${i + 1}. ${zone.nearby[i].name} '
                  '${zone.nearby[i].distanceLabel}${zone.nearby[i].coedTag}',
                  style: text.bodySmall?.copyWith(
                    fontSize: 11.5,
                    fontWeight: i == 0 ? FontWeight.w700 : FontWeight.w400,
                    color: i == 0 ? AppColors.navy : null,
                  ),
                ),
            ],
          ),
        ],
      ),
    );
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

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SectionHeader(
          '${region?.nameKo ?? ''} 학교 ${schools.length}곳',
          subtitle: 'NEIS 학교기본정보 공시 기준',
        ),
        _CareerRanking(schools: schools),
        for (final level in order)
          if ((byLevel[level] ?? []).isNotEmpty) ...[
            Padding(
              padding: const EdgeInsets.only(top: AppSpace.sm, bottom: 6),
              child: Row(
                children: [
                  Container(
                    width: 8,
                    height: 8,
                    decoration: BoxDecoration(
                      color: Color(schoolLevelColors[level]!),
                      shape: BoxShape.circle,
                    ),
                  ),
                  const SizedBox(width: 6),
                  Text(
                    '${byLevel[level]!.first.levelLabel} ${byLevel[level]!.length}곳',
                    style: text.titleMedium,
                  ),
                ],
              ),
            ),
            Wrap(
              spacing: AppSpace.sm,
              runSpacing: AppSpace.sm,
              children: [
                for (final s in byLevel[level]!)
                  InkWell(
                    borderRadius: BorderRadius.circular(AppRadius.sm),
                    onTap: () => showModalBottomSheet<void>(
                      context: context,
                      isScrollControlled: true,
                      showDragHandle: true,
                      constraints: const BoxConstraints(maxWidth: 640),
                      builder: (_) => _SchoolSheet(school: s),
                    ),
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 11,
                        vertical: 7,
                      ),
                      decoration: BoxDecoration(
                        border: Border.all(color: AppColors.line),
                        borderRadius: BorderRadius.circular(AppRadius.sm),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(s.name, style: text.labelLarge),
                          const SizedBox(width: 6),
                          Text(
                            [
                              s.foundation,
                              s.coed,
                            ].whereType<String>().join(' · '),
                            style: text.bodySmall?.copyWith(fontSize: 11),
                          ),
                          if (s.zoneName != null) ...[
                            const SizedBox(width: 6),
                            Chip2(s.zoneName!, color: AppColors.navy),
                          ],
                          if (s.apartments.isNotEmpty) ...[
                            const SizedBox(width: 6),
                            Chip2(
                              '배정 ${s.apartments.length}단지',
                              color: AppColors.navy,
                            ),
                          ],
                        ],
                      ),
                    ),
                  ),
              ],
            ),
          ],
      ],
    );
  }
}

/// 진로 공시가 붙은 학교를 순위로 보여준다.
///
/// 중학교는 특목·자사고 진학률, 고등학교는 대학 진학률 기준이다.
/// 공시가 붙은 학교가 3곳 미만이면 내놓지 않는다 — 두 곳을 세워 놓고
/// '1위'라 부르는 것은 순위가 아니다.
///
/// 진학률로 학교를 줄 세우는 일이 거친 것은 안다. 그래서 값과 출처를
/// 그대로 보여주고 가공 점수를 만들지 않는다.
class _CareerRanking extends StatelessWidget {
  final List<School> schools;
  const _CareerRanking({required this.schools});

  static const _minShown = 3;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;

    double? metric(School s) {
      final c = s.careers;
      if (c == null) return null;
      if (s.level == 'middle') {
        final a = (c['특수목적고'] as num?)?.toDouble();
        final b = (c['자율고'] as num?)?.toDouble();
        if (a == null && b == null) return null;
        return (a ?? 0) + (b ?? 0);
      }
      return (c['대학'] as num?)?.toDouble();
    }

    Widget section(String level, String title, String unit) {
      final rows = <(School, double)>[
        for (final s in schools)
          if (s.level == level && metric(s) != null) (s, metric(s)!),
      ]..sort((a, b) => b.$2.compareTo(a.$2));
      if (rows.length < _minShown) return const SizedBox.shrink();

      return Padding(
        padding: const EdgeInsets.only(bottom: AppSpace.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: text.titleMedium),
            Text(unit, style: text.bodySmall),
            const SizedBox(height: 6),
            for (var i = 0; i < rows.length; i++)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 3),
                child: Row(
                  children: [
                    SizedBox(
                      width: 22,
                      child: Text(
                        '${i + 1}',
                        style: text.labelMedium?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                    Expanded(
                      child: Text(rows[i].$1.name, style: text.bodyLarge),
                    ),
                    SizedBox(
                      width: 120,
                      child: LinearProgressIndicator(
                        value: (rows[i].$2 / 100).clamp(0, 1),
                        minHeight: 6,
                        backgroundColor: AppColors.line,
                        color: Color(schoolLevelColors[level]!),
                      ),
                    ),
                    const SizedBox(width: AppSpace.sm),
                    SizedBox(
                      width: 52,
                      child: Text(
                        '${rows[i].$2.toStringAsFixed(1)}%',
                        textAlign: TextAlign.right,
                        style: text.titleMedium?.copyWith(fontSize: 14),
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
      );
    }

    final middle = section(
      'middle',
      '중학교 · 특목·자사고 진학률',
      '학교알리미 졸업생 진로 현황 공시. 진학률만 놓고 세운 순서입니다.',
    );
    final high = section(
      'high',
      '고등학교 · 대학 진학률',
      '학교알리미 졸업생 진로 현황 공시. 전문대·국외는 제외한 4년제 기준입니다.',
    );
    if (middle is SizedBox && high is SizedBox) return const SizedBox.shrink();

    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpace.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [middle, high],
      ),
    );
  }
}

/// 학교 진로 추이.
///
/// 진로 공시는 연 1회라 점이 드물게 찍힌다. 두 점이 모이기 전에는
/// 아무것도 내지 않는다 — 한 점으로 추세를 말할 수는 없다.
class _SchoolTrend extends ConsumerWidget {
  final String schoolId;
  final String level;
  const _SchoolTrend({required this.schoolId, required this.level});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final rows =
        ref.watch(historyProvider).value?.forSchool(schoolId) ?? const [];
    if (rows.length < 2) return const SizedBox.shrink();

    final first = rows.first.$2, last = rows.last.$2;
    final diff = last - first;
    final labelText = level == 'middle' ? '특목·자사고 진학률' : '대학 진학률';

    return Padding(
      padding: const EdgeInsets.only(top: AppSpace.sm),
      child: Row(
        children: [
          Icon(
            diff >= 0 ? Icons.trending_up : Icons.trending_down,
            size: 15,
            color: diff >= 0 ? AppColors.rising : AppColors.falling,
          ),
          const SizedBox(width: 4),
          Text(
            '$labelText ${diff >= 0 ? "+" : ""}${diff.toStringAsFixed(1)}%p '
            '(${rows.first.$1.year} → ${rows.last.$1.year})',
            style: text.bodySmall,
          ),
        ],
      ),
    );
  }
}

/// 학교 상세 — 배정 아파트를 보여준다.
///
/// '이 집은 어느 학교냐' 만큼이나 '이 학교 보내려면 어디 살아야 하냐' 를
/// 많이 찾는다. 같은 데이터를 양방향으로 볼 수 있어야 한다.
/// 졸업생 진로 공시 표시.
///
/// 공시(학교알리미)와 수기 보완(서울대 등 외부 집계)을 한 패널에 두되
/// 출처를 각각 명시한다. 두 숫자는 같은 자리에서 나온 값이 아니다.
///
/// 값은 전부 비율(%)이다. 학교알리미가 인원이 아니라 비율로 공시한다.
class _CareersPanel extends StatelessWidget {
  final School school;
  const _CareersPanel({required this.school});

  /// 학부모가 실제로 보는 순서. 중학교는 특목·자사가 먼저다.
  static const _middle = ['특수목적고', '자율고', '일반고', '특성화고'];
  static const _high = ['대학', '전문대학', '국외', '취업'];

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final c = school.careers;
    final ex = school.outcomesExtra;

    final order = school.level == 'middle' ? _middle : _high;
    final rows = <(String, double)>[
      if (c != null)
        for (final k in order)
          if (c[k] is num) (k, (c[k] as num).toDouble()),
    ];
    if (rows.isEmpty && ex == null) return const SizedBox.shrink();

    // 중학교는 특목+자사를 합쳐서 한 번 더 보여준다 — 학부모가 묶어서 본다.
    final headline = school.level == 'middle' && c != null
        ? ((c['특수목적고'] as num?)?.toDouble() ?? 0) +
              ((c['자율고'] as num?)?.toDouble() ?? 0)
        : (c?['대학'] as num?)?.toDouble();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('졸업생 진로', style: text.labelMedium),
        const SizedBox(height: 4),
        if (headline != null) ...[
          Text(
            school.level == 'middle'
                ? '특목·자사고 ${headline.toStringAsFixed(1)}%'
                : '대학 진학 ${headline.toStringAsFixed(1)}%',
            style: text.headlineMedium?.copyWith(fontSize: 21),
          ),
          const SizedBox(height: 6),
        ],
        if (rows.isNotEmpty) ...[
          Wrap(
            spacing: AppSpace.md,
            runSpacing: 4,
            children: [
              for (final (k, v) in rows)
                Text.rich(
                  TextSpan(
                    children: [
                      TextSpan(text: '$k ', style: text.bodyMedium),
                      TextSpan(
                        text: '${v.toStringAsFixed(1)}%',
                        style: text.titleMedium?.copyWith(fontSize: 14.5),
                      ),
                    ],
                  ),
                ),
            ],
          ),
          const SizedBox(height: 2),
          Text(
            '출처: 학교알리미 ${c!['year'] ?? ''} 공시 · 졸업생 진로 현황',
            style: text.bodySmall?.copyWith(fontSize: 10.5),
          ),
        ],
        if (ex != null && ex['snu_admits'] != null) ...[
          const SizedBox(height: 6),
          Text(
            '서울대 ${ex['snu_admits']}명 (${ex['snu_year'] ?? ''})',
            style: text.titleMedium?.copyWith(fontSize: 14.5),
          ),
          Text(
            '출처: ${ex['source'] ?? '외부 집계'}',
            style: text.bodySmall?.copyWith(fontSize: 10.5),
          ),
        ],
      ],
    );
  }
}

class _SchoolSheet extends StatelessWidget {
  final School school;
  const _SchoolSheet({required this.school});

  static String _won(int v) =>
      v >= 10000 ? '${(v / 10000).toStringAsFixed(1)}만' : '$v';

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final certain =
        school.level == 'elementary' && school.apartments.any((a) => a.certain);

    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.7,
      maxChildSize: 0.94,
      builder: (context, controller) => ListView(
        controller: controller,
        padding: const EdgeInsets.fromLTRB(
          AppSpace.lg,
          0,
          AppSpace.lg,
          AppSpace.xl,
        ),
        children: [
          Row(
            children: [
              Chip2(
                school.levelLabel,
                color: Color(schoolLevelColors[school.level]!),
                filled: true,
              ),
              const SizedBox(width: 6),
              if (school.foundation != null)
                Chip2(school.foundation!, color: AppColors.slate),
              if (school.coed != null) ...[
                const SizedBox(width: 6),
                Chip2(school.coed!, color: AppColors.slate),
              ],
            ],
          ),
          const SizedBox(height: AppSpace.sm),
          Text(school.name, style: text.headlineLarge),
          if (school.address != null)
            Text(school.address!, style: text.bodyMedium),
          const SizedBox(height: AppSpace.lg),

          if (school.careers != null || school.outcomesExtra != null) ...[
            _CareersPanel(school: school),
            _SchoolTrend(schoolId: school.id, level: school.level),
            const SizedBox(height: AppSpace.lg),
          ],

          if (school.zoneName != null) ...[
            Text('학구', style: text.labelMedium),
            const SizedBox(height: 4),
            Text(school.zoneName!, style: text.titleMedium),
            if (school.zonePeers.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(
                '이 학교군에는 ${school.zonePeers.length + 1}개 학교가 묶여 있어 '
                '추첨으로 배정됩니다: ${school.zonePeers.take(6).join(", ")}'
                '${school.zonePeers.length > 6 ? " 외" : ""}',
                style: text.bodyMedium,
              ),
            ],
            const SizedBox(height: AppSpace.lg),
          ],

          if (school.apartments.isEmpty)
            Text('연결된 배정 아파트 정보가 없습니다.', style: text.bodyMedium)
          else ...[
            SectionHeader(
              certain ? '이 학교로 배정되는 아파트' : '이 학교군에 속한 아파트',
              subtitle: school.apartmentHouseholds != null
                  ? '${school.apartments.length}단지 · '
                        '${_won(school.apartmentHouseholds!)}세대'
                        '${certain ? "" : " (추첨 대상)"}'
                  : '${school.apartments.length}단지',
            ),
            for (final a in school.apartments)
              Padding(
                padding: const EdgeInsets.only(bottom: 7),
                child: Row(
                  children: [
                    Icon(
                      a.certain
                          ? Icons.verified_rounded
                          : Icons.casino_outlined,
                      size: 14,
                      color: a.certain
                          ? AppColors.verified
                          : AppColors.estimated,
                    ),
                    const SizedBox(width: 7),
                    Expanded(child: Text(a.name, style: text.bodyLarge)),
                    if (a.dong != null) Text(a.dong!, style: text.bodySmall),
                    const SizedBox(width: AppSpace.sm),
                    if (a.households != null)
                      Text('${a.households}세대', style: text.labelMedium),
                  ],
                ),
              ),
            const SizedBox(height: AppSpace.md),
            Text(
              certain
                  ? '초등학교는 통학구역이 1:1 이라 배정이 확정됩니다. '
                        '다만 구역은 해마다 조정될 수 있으니 관할 교육지원청 공고를 확인해 주세요.'
                  : '중·고등학교는 학교군 추첨이라 이 아파트들이 반드시 이 학교로 '
                        '배정되는 것은 아닙니다.',
              style: text.bodySmall,
            ),
          ],
        ],
      ),
    );
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
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(
                  Icons.info_outline,
                  size: 17,
                  color: AppColors.estimated,
                ),
                const SizedBox(width: AppSpace.sm),
                Text('배정 정보를 읽는 법', style: text.titleMedium),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              '초등학교는 통학구역이 1:1 이라 배정 학교를 확정할 수 있습니다. '
              '중·고등학교는 여러 학교가 한 학교군에 묶여 추첨으로 정해지므로 '
              '학교를 특정하지 않고 "N개교 중 추첨" 으로 표시합니다.\n\n'
              '다만 추첨에 통학 편의가 반영되어 가까운 학교로 갈 확률이 높습니다. '
              '그래서 단지를 선택하면 가까운 순으로 세 곳을 거리와 함께 보여줍니다. '
              '남고·여고는 이름 뒤에 (남)·(여)로 표시했습니다 — 자녀 성별에 따라 '
              '실제 후보가 달라지기 때문입니다. '
              '확률(%)로 바꾸지 않는 이유는 실제 배정 결과 자료가 공개되어 있지 '
              '않기 때문입니다 — 근거 없는 숫자를 붙이지 않으려는 것입니다.\n\n'
              '배정은 해마다 바뀔 수 있습니다. 실제 배정은 관할 교육지원청 공고를 '
              '확인해 주세요.\n\n'
              '학교 순위는 학교알리미 OpenAPI 에 졸업생 진로현황이 없어 보류 중입니다.',
              style: text.bodyMedium,
            ),
          ],
        ),
      ),
    );
  }
}
