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
  bool _showApartments = true;

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(dataProvider);
    // 지도 데이터는 이 화면에서 처음 읽는다.
    final mapAsync = ref.watch(mapDataProvider);
    final sel = ref.watch(selectionProvider);

    if (async.hasError || mapAsync.hasError) {
      return Center(
          child: Text('${async.error ?? mapAsync.error}'));
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
                .where((a) =>
                    EduTreeData.matchRegion(a.regionId, sel.regionId) &&
                    a.lat != null)
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
                  SectionHeader('${region?.nameKo ?? ''} 학군지도',
                      subtitle: '학군은 학원이 아니라 학교로 정해집니다. '
                          '초·중·고 위치를 보고, 필요하면 학원을 겹쳐 보세요.'),
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
                  ]),
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

  String _markers() {
    final items = <Map<String, dynamic>>[];
    for (final s in schools.where((s) => s.hasLocation)) {
      items.add({
        'lat': s.lat, 'lng': s.lng, 'label': s.name,
        'title': s.name,
        'subtitle': [
          s.levelLabel, s.foundation, s.coed,
          if (s.zoneName != null) s.zoneName,
          if (s.zonePeers.isNotEmpty) '학교군 ${s.zonePeers.length + 1}개교 추첨',
        ].whereType<String>().where((x) => x.isNotEmpty).join(' · '),
        'color': '#${schoolLevelColors[s.level]!.toRadixString(16).substring(2)}',
        'z': 3,
      });
    }
    for (final a in apartments) {
      items.add({
        'lat': a.lat, 'lng': a.lng, 'label': a.name,
        'title': a.name,
        'subtitle': [
          [
            a.dong,
            if (a.households != null) '${a.households}세대',
          ].whereType<String>().join(' · '),
          ...a.zones.map((z) => '${z.levelLabel} ${z.assignmentText}'),
        ].where((x) => x.isNotEmpty).join('<br>'),
        'color': '#8B5CF6',
        'z': 2,
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
        'subtitle': '${props['level'] == 'high' ? '고등학교' : '중학교'} 학교군 · '
            '${props['eduOffice'] ?? ''}',
        'color': props['level'] == 'high' ? '#B4531E' : '#1E7A5A',
        'rings': geom['coordinates'],
      });
    }
    return jsonEncode({'markers': items, 'zones': zonePolys});
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

/// 아파트별 배정 학교. 학부모가 실제로 찾는 정보라 목록으로도 둔다.
class _ApartmentList extends StatelessWidget {
  final List<Apartment> apartments;
  const _ApartmentList({required this.apartments});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final rows = apartments.take(40).toList();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      SectionHeader('아파트별 배정 학교 (${apartments.length}단지)',
          subtitle: '초등학교는 통학구역이라 배정이 확정됩니다. '
              '중·고등학교는 학교군 추첨이라 학교를 특정할 수 없지만, '
              '통학 편의가 반영되므로 가까운 학교일수록 갈 확률이 높습니다.'),
      for (final a in rows)
        Card(
          margin: const EdgeInsets.only(bottom: AppSpace.sm),
          child: Padding(
            padding: const EdgeInsets.all(AppSpace.md),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Expanded(child: Text(a.name, style: text.titleMedium)),
                if (a.households != null)
                  Text('${a.households}세대', style: text.bodySmall),
              ]),
              const SizedBox(height: 6),
              Wrap(spacing: 6, runSpacing: 6, children: [
                for (final z in a.zones)
                  Chip2('${z.levelLabel} · ${z.assignmentText}',
                      color: z.certain
                          ? AppColors.verified
                          : (z.level == 'elementary'
                              ? AppColors.reputation
                              : AppColors.estimated),
                      icon: z.certain ? Icons.verified_rounded : null),
              ]),
              for (final z in a.zones)
                if (z.nearby.isNotEmpty) _NearbyRow(zone: z),
            ]),
          ),
        ),
      if (apartments.length > rows.length)
        Padding(
          padding: const EdgeInsets.only(top: AppSpace.sm),
          child: Text('외 ${apartments.length - rows.length}단지', style: text.bodySmall),
        ),
    ]);
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
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          const Icon(Icons.near_me_outlined,
              size: 13, color: AppColors.mist),
          const SizedBox(width: 4),
          Text('${zone.levelLabel} 가까운 순 (추첨이지만 통학 편의 반영)',
              style: text.bodySmall?.copyWith(fontSize: 11)),
        ]),
        const SizedBox(height: 3),
        Wrap(spacing: 6, runSpacing: 4, children: [
          for (var i = 0; i < zone.nearby.length; i++)
            Text(
              '${i + 1}. ${zone.nearby[i].name} ${zone.nearby[i].distanceLabel}',
              style: text.bodySmall?.copyWith(
                  fontSize: 11.5,
                  fontWeight: i == 0 ? FontWeight.w700 : FontWeight.w400,
                  color: i == 0 ? AppColors.navy : null),
            ),
        ]),
      ]),
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
                  if (s.zoneName != null) ...[
                    const SizedBox(width: 6),
                    Chip2(s.zoneName!, color: AppColors.navy),
                  ],
                  if (s.apartments.isNotEmpty) ...[
                    const SizedBox(width: 6),
                    Chip2('배정 ${s.apartments.length}단지',
                        color: AppColors.navy),
                  ],
                ]),
              ),
              ),
          ]),
        ],
    ]);
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
class _CareersPanel extends StatelessWidget {
  final School school;
  const _CareersPanel({required this.school});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final c = school.careers;
    final ex = school.outcomesExtra;
    // 중학교는 특목+자사 진학이 핵심 관심사, 고등학교는 대학 진학률.
    final rows = <(String, String)>[];
    if (c != null) {
      for (final k in const [
        '특수목적고', '자율고', '일반고', '특성화고', '대학', '전문대학', '진학률'
      ]) {
        final v = c[k];
        if (v is num) {
          rows.add((k, k == '진학률' ? '${v.toStringAsFixed(1)}%' : '${v.toInt()}명'));
        }
      }
    }
    if (rows.isEmpty && ex == null) return const SizedBox.shrink();

    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('졸업생 진로', style: text.labelMedium),
      const SizedBox(height: 4),
      if (rows.isNotEmpty) ...[
        Wrap(spacing: AppSpace.md, runSpacing: 4, children: [
          for (final (k, v) in rows)
            Text.rich(TextSpan(children: [
              TextSpan(text: '$k ', style: text.bodyMedium),
              TextSpan(
                  text: v,
                  style: text.titleMedium?.copyWith(fontSize: 14.5)),
            ])),
        ]),
        Text('출처: 학교알리미 공시 ${c!['year'] ?? ''}',
            style: text.bodySmall?.copyWith(fontSize: 10.5)),
      ],
      if (ex != null && ex['snu_admits'] != null) ...[
        const SizedBox(height: 4),
        Text('서울대 ${ex['snu_admits']}명 (${ex['snu_year'] ?? ''})',
            style: text.titleMedium?.copyWith(fontSize: 14.5)),
        Text('출처: ${ex['source'] ?? '외부 집계'}',
            style: text.bodySmall?.copyWith(fontSize: 10.5)),
      ],
    ]);
  }
}

class _SchoolSheet extends StatelessWidget {
  final School school;
  const _SchoolSheet({required this.school});

  static String _won(int v) => v >= 10000
      ? '${(v / 10000).toStringAsFixed(1)}만'
      : '$v';

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final certain = school.level == 'elementary' &&
        school.apartments.any((a) => a.certain);

    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.7,
      maxChildSize: 0.94,
      builder: (context, controller) => ListView(
        controller: controller,
        padding: const EdgeInsets.fromLTRB(
            AppSpace.lg, 0, AppSpace.lg, AppSpace.xl),
        children: [
          Row(children: [
            Chip2(school.levelLabel,
                color: Color(schoolLevelColors[school.level]!), filled: true),
            const SizedBox(width: 6),
            if (school.foundation != null)
              Chip2(school.foundation!, color: AppColors.slate),
            if (school.coed != null) ...[
              const SizedBox(width: 6),
              Chip2(school.coed!, color: AppColors.slate),
            ],
          ]),
          const SizedBox(height: AppSpace.sm),
          Text(school.name, style: text.headlineLarge),
          if (school.address != null)
            Text(school.address!, style: text.bodyMedium),
          const SizedBox(height: AppSpace.lg),

          if (school.careers != null || school.outcomesExtra != null) ...[
            _CareersPanel(school: school),
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
                child: Row(children: [
                  Icon(
                      a.certain
                          ? Icons.verified_rounded
                          : Icons.casino_outlined,
                      size: 14,
                      color: a.certain
                          ? AppColors.verified
                          : AppColors.estimated),
                  const SizedBox(width: 7),
                  Expanded(child: Text(a.name, style: text.bodyLarge)),
                  if (a.dong != null)
                    Text(a.dong!, style: text.bodySmall),
                  const SizedBox(width: AppSpace.sm),
                  if (a.households != null)
                    Text('${a.households}세대', style: text.labelMedium),
                ]),
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
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            const Icon(Icons.info_outline, size: 17, color: AppColors.estimated),
            const SizedBox(width: AppSpace.sm),
            Text('배정 정보를 읽는 법', style: text.titleMedium),
          ]),
          const SizedBox(height: 6),
          Text(
            '초등학교는 통학구역이 1:1 이라 배정 학교를 확정할 수 있습니다. '
            '중·고등학교는 여러 학교가 한 학교군에 묶여 추첨으로 정해지므로 '
            '학교를 특정하지 않고 "N개교 중 추첨" 으로 표시합니다.\n\n'
            '배정은 해마다 바뀔 수 있습니다. 실제 배정은 관할 교육지원청 공고를 '
            '확인해 주세요.\n\n'
            '학교 순위는 학교알리미 OpenAPI 에 졸업생 진로현황이 없어 보류 중입니다.',
            style: text.bodyMedium,
          ),
        ]),
      ),
    );
  }
}
