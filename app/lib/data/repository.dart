import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'models.dart';

/// 데이터 접근 계층.
///
/// v1은 파이프라인이 만든 정적 번들을 읽는다. Supabase 전환 시
/// [EduTreeRepository] 의 구현만 갈아끼우면 되도록 인터페이스를 좁게 유지한다.
class EduTreeData {
  final Meta meta;
  final List<Region> regions;
  final List<Track> tracks;
  final List<Academy> academies;
  final Roadmap roadmap;

  EduTreeData({
    required this.meta,
    required this.regions,
    required this.tracks,
    required this.academies,
    this.roadmap = const Roadmap(),
  });

  late final Map<String, Region> regionById = {
    for (final r in regions) r.id: r
  };
  late final Map<String, Academy> academyById = {
    // 흡수된 옛 등록번호를 먼저 깐다 — 진짜 id 가 나중에 덮어 이긴다.
    // 통합으로 id 가 바뀌어도 옛 링크(/academy/<옛id>)가 살아남는다.
    for (final a in academies)
      for (final rid in a.registrationIds) rid: a,
    for (final a in academies) a.id: a,
  };
  late final Map<String, Stage> stageById = {
    for (final t in tracks)
      for (final s in t.stages) s.id: s
  };
  late final Map<String, Track> trackById = {for (final t in tracks) t.id: t};

  /// 'all' 은 학군 전체를 뜻한다. 헤더 휠에서 '전체'를 고른 상태.
  static bool matchRegion(String? rowRegion, String? selected) =>
      selected == null || selected == 'all' || rowRegion == selected;

  /// 단계 → 그 단계를 담당하는 학원들 (지역 필터 적용 가능)
  List<Academy> academiesForStage(String stageId, {String? regionId}) {
    final rows = academies.where((a) =>
        a.stages.contains(stageId) && matchRegion(a.regionId, regionId));
    final list = rows.toList()
      ..sort((a, b) {
        final fa = a.isFlagshipOf(stageId) ? 1 : 0;
        final fb = b.isFlagshipOf(stageId) ? 1 : 0;
        if (fa != fb) return fb - fa;
        return b.score.total.compareTo(a.score.total);
      });
    return list;
  }

  List<Track> tracksFor({String? subject, String? gradeBand}) {
    return tracks
        .where((t) =>
            (subject == null || t.subject == subject) &&
            (gradeBand == null || t.gradeBand == gradeBand))
        .toList();
  }

  /// 지역·과목·학년 구간 필터. 랭킹과 '표본 부족' 목록이 함께 쓴다.
  bool _matchesFilters(
    Academy a, {
    required String regionId,
    String? subject,
    String? gradeBand,
  }) {
    if (!matchRegion(a.regionId, regionId)) return false;
    if (subject != null && !a.subjects.contains(subject)) return false;
    // 구간이 비어 있는 학원은 특정 학년대에 한정되지 않는 곳으로 보고
    // 어떤 필터에도 걸리게 둔다. 걸러내면 종합·보습 학원이 통째로 사라진다.
    if (gradeBand != null &&
        a.gradeBands.isNotEmpty &&
        !a.gradeBands.contains(gradeBand)) {
      return false;
    }
    return true;
  }

  /// 지역 랭킹. 표본 부족 학원은 제외한다(제품 정책).
  List<Academy> ranking({
    required String regionId,
    String? subject,
    String? gradeBand,
    bool includeUnranked = false,
  }) {
    final rows = academies
        .where((a) =>
            (includeUnranked || a.score.isRanked) &&
            _matchesFilters(a,
                regionId: regionId, subject: subject, gradeBand: gradeBand))
        .toList();
    rows.sort((a, b) => b.score.total.compareTo(a.score.total));
    return rows;
  }

  /// 표본 부족으로 순위에서 빠진 학원들 — 별도 섹션에 보여준다.
  ///
  /// **랭킹과 같은 조건으로 걸러야 한다.** 지역만 보고 뽑으면 영어 랭킹
  /// 아래에 미술·수학 학원까지 늘어서서, 그 목록이 무엇의 목록인지
  /// 읽히지 않는다. 순위에서 빠진 이유가 표본이지 과목이 아니므로,
  /// 지금 보고 있는 과목·학년 구간 안의 학원만 열거한다.
  List<Academy> unranked(
    String regionId, {
    String? subject,
    String? gradeBand,
  }) {
    final rows = academies
        .where((a) =>
            !a.score.isRanked &&
            _matchesFilters(a,
                regionId: regionId, subject: subject, gradeBand: gradeBand))
        .toList();
    rows.sort((a, b) => a.name.compareTo(b.name));
    return rows;
  }

  /// 채점 대상 안에서의 검색. 등록부는 [registryProvider] 가 따로 늦게 온다.
  List<SearchHit> search(String query) {
    final q = query.trim().toLowerCase();
    if (q.isEmpty) return const [];

    final hits = <SearchHit>[];
    for (final a in academies) {
      final match = a.name.toLowerCase().contains(q) ||
          (a.brand ?? '').toLowerCase().contains(q) ||
          a.aliases.any((x) => x.toLowerCase().contains(q));
      if (match) hits.add(SearchHit.scored(a));
    }
    return hits;
  }
}

/// 지도 전용 데이터. 학교·아파트·학구 폴리곤 합쳐 1.6MB 라
/// 첫 화면에서 같이 읽으면 그만큼 첫 그림이 늦어진다. 지도에 들어갈 때 읽는다.
class MapData {
  final List<School> schools;
  final List<Apartment> apartments;
  final List<dynamic> zoneFeatures;

  const MapData({
    this.schools = const [],
    this.apartments = const [],
    this.zoneFeatures = const [],
  });

  List<School> schoolsIn(String regionId, {String? level}) => schools
      .where((s) =>
          EduTreeData.matchRegion(s.regionId, regionId) &&
          (level == null || s.level == level))
      .toList()
    ..sort((a, b) => a.name.compareTo(b.name));

  List<Apartment> apartmentsIn(String regionId) => apartments
      .where((a) => EduTreeData.matchRegion(a.regionId, regionId))
      .toList()
    ..sort((a, b) => (b.households ?? 0).compareTo(a.households ?? 0));
}

/// 검색 결과 한 줄. 점수가 있는 학원과 등록부 학원을 함께 담는다.
class SearchHit {
  final String id;
  final String name;
  final String regionId;
  final List<String> subjects;
  final double? total;
  final bool evaluated;

  const SearchHit({
    required this.id,
    required this.name,
    required this.regionId,
    required this.subjects,
    this.total,
    required this.evaluated,
  });

  factory SearchHit.scored(Academy a) => SearchHit(
        id: a.id,
        name: a.displayName,
        regionId: a.regionId,
        subjects: a.subjects,
        total: a.score.total,
        evaluated: true,
      );

  factory SearchHit.listed(RegistryEntry r) => SearchHit(
        id: r.id,
        name: r.displayName,
        regionId: r.regionId,
        subjects: r.subjects,
        evaluated: false,
      );
}

class EduTreeRepository {
  const EduTreeRepository();

  /// 첫 화면에 필요한 것만. 1.4MB.
  Future<EduTreeData> load() async {
    final results = await Future.wait([
      _json('assets/data/meta.json'),
      _json('assets/data/regions.json'),
      _json('assets/data/techtree.json'),
      _json('assets/data/academies.json'),
    ]);

    return EduTreeData(
      meta: Meta.fromJson((results[0] as Map).cast<String, dynamic>()),
      regions: (results[1] as List)
          .map((e) => Region.fromJson((e as Map).cast<String, dynamic>()))
          .toList(),
      tracks: ((results[2] as Map)['tracks'] as List)
          .map((e) => Track.fromJson((e as Map).cast<String, dynamic>()))
          .toList(),
      roadmap: (results[2] as Map)['roadmap'] is Map
          ? Roadmap.fromJson(
              ((results[2] as Map)['roadmap'] as Map).cast<String, dynamic>())
          : const Roadmap(),
      academies: (results[3] as List)
          .map((e) => Academy.fromJson((e as Map).cast<String, dynamic>()))
          .toList(),
    );
  }

  /// 등록부 1.4MB. 검색을 열 때만 필요하다.
  Future<List<RegistryEntry>> loadRegistry() async =>
      ((await _json('assets/data/registry.json')) as List)
          .map((e) => RegistryEntry.fromJson((e as Map).cast<String, dynamic>()))
          .toList();

  /// 랭킹 이력. 상세 화면에서만 쓰이므로 첫 화면에서 읽지 않는다.
  Future<RankHistory> loadHistory() async {
    try {
      final j = await _json('assets/data/history.json');
      return RankHistory.fromJson((j as Map).cast<String, dynamic>());
    } on Exception {
      // 아직 이력 파일이 없을 수 있다. 없으면 화면이 추이를 감춘다.
      return const RankHistory();
    }
  }

  /// 지도 데이터 1.6MB. 학군지도에 들어갈 때만 필요하다.
  Future<MapData> loadMapData() async {
    final results = await Future.wait([
      _json('assets/data/schools.json'),
      _json('assets/data/apartments.json'),
      _json('assets/data/zones.geojson'),
    ]);
    return MapData(
      schools: (results[0] as List)
          .map((e) => School.fromJson((e as Map).cast<String, dynamic>()))
          .toList(),
      apartments: (results[1] as List)
          .map((e) => Apartment.fromJson((e as Map).cast<String, dynamic>()))
          .toList(),
      zoneFeatures: ((results[2] as Map)['features'] as List?) ?? const [],
    );
  }

  Future<dynamic> _json(String path) async =>
      jsonDecode(await rootBundle.loadString(path));
}

final repositoryProvider =
    Provider<EduTreeRepository>((ref) => const EduTreeRepository());

final dataProvider = FutureProvider<EduTreeData>(
    (ref) => ref.watch(repositoryProvider).load());

/// 랭킹 이력 한 점.
class RankPoint {
  final DateTime day;
  final int? rank;
  final double total;
  final int sampleSize;
  const RankPoint({
    required this.day,
    this.rank,
    required this.total,
    required this.sampleSize,
  });
}

/// 랭킹 이력. 과거 자료가 없어 집계 시작일부터 쌓는다.
///
/// 지어낸 과거를 채워 넣지 않는다 — 비어 있는 편이 낫고, 화면도
/// '집계 시작 이후'라고 그대로 말한다.
class RankHistory {
  final Map<String, List<RankPoint>> academies;
  final Map<String, List<(DateTime, double)>> schools;
  const RankHistory({this.academies = const {}, this.schools = const {}});

  List<RankPoint> forAcademy(String id) => academies[id] ?? const [];
  List<(DateTime, double)> forSchool(String id) => schools[id] ?? const [];

  /// 집계 시작일. 화면이 '언제부터의 이야기인지' 밝히는 데 쓴다.
  DateTime? get since {
    DateTime? first;
    for (final rows in academies.values) {
      if (rows.isEmpty) continue;
      if (first == null || rows.first.day.isBefore(first)) first = rows.first.day;
    }
    return first;
  }

  factory RankHistory.fromJson(Map<String, dynamic> j) {
    final acad = <String, List<RankPoint>>{};
    for (final e in ((j['academies'] as Map?) ?? const {}).entries) {
      final rows = <RankPoint>[];
      for (final d in ((e.value as Map).cast<String, dynamic>()).entries) {
        final day = DateTime.tryParse(d.key);
        final v = (d.value as Map).cast<String, dynamic>();
        if (day == null) continue;
        rows.add(RankPoint(
          day: day,
          rank: (v['r'] as num?)?.toInt(),
          total: (v['t'] as num?)?.toDouble() ?? 0,
          sampleSize: (v['n'] as num?)?.toInt() ?? 0,
        ));
      }
      rows.sort((a, b) => a.day.compareTo(b.day));
      acad[e.key as String] = rows;
    }
    final sch = <String, List<(DateTime, double)>>{};
    for (final e in ((j['schools'] as Map?) ?? const {}).entries) {
      final rows = <(DateTime, double)>[];
      for (final d in ((e.value as Map).cast<String, dynamic>()).entries) {
        final day = DateTime.tryParse(d.key);
        final v = (d.value as Map).cast<String, dynamic>();
        if (day == null) continue;
        rows.add((day, (v['v'] as num?)?.toDouble() ?? 0));
      }
      rows.sort((a, b) => a.$1.compareTo(b.$1));
      sch[e.key as String] = rows;
    }
    return RankHistory(academies: acad, schools: sch);
  }
}

/// 등록부 — 검색이 열릴 때 처음 읽힌다. 한 번 읽으면 남는다.
final registryProvider = FutureProvider<List<RegistryEntry>>(
    (ref) => ref.watch(repositoryProvider).loadRegistry());

/// 랭킹 이력 — 상세 화면에서 처음 읽힌다.
final historyProvider =
    FutureProvider<RankHistory>((ref) => ref.watch(repositoryProvider).loadHistory());

/// 지도 데이터 — 학군지도에 들어갈 때 처음 읽힌다.
final mapDataProvider = FutureProvider<MapData>(
    (ref) => ref.watch(repositoryProvider).loadMapData());

/// 전역 선택 상태 — 지역 / 과목 / 학교급
class Selection {
  /// 'all' | 'daechi' | 'mokdong' | 'banpo' | 'jamsil'
  final String regionId;
  final String subject;
  final String gradeBand;

  const Selection({
    this.regionId = 'daechi',
    this.subject = 'math',
    this.gradeBand = 'elem_low',
  });

  Selection copyWith({String? regionId, String? subject, String? gradeBand}) =>
      Selection(
        regionId: regionId ?? this.regionId,
        subject: subject ?? this.subject,
        gradeBand: gradeBand ?? this.gradeBand,
      );

  String get trackId => '${subject}_$gradeBand';
  bool get isAllRegions => regionId == 'all';

  // 값이 같으면 같은 상태다. 이게 없으면 리버팟이 매 갱신을 '바뀐 것'으로
  // 보고 구독자를 전부 다시 그린다. 휠을 한 번 굴릴 때마다 화면 전체가
  // 재구성되던 원인이었다.
  @override
  bool operator ==(Object other) =>
      other is Selection &&
      other.regionId == regionId &&
      other.subject == subject &&
      other.gradeBand == gradeBand;

  @override
  int get hashCode => Object.hash(regionId, subject, gradeBand);
}

class SelectionNotifier extends Notifier<Selection> {
  @override
  Selection build() => const Selection();

  void setRegion(String id) => state = state.copyWith(regionId: id);
  void setSubject(String id) => state = state.copyWith(subject: id);
  void setGradeBand(String id) => state = state.copyWith(gradeBand: id);
}

final selectionProvider =
    NotifierProvider<SelectionNotifier, Selection>(SelectionNotifier.new);
