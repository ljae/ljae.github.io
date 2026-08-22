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
  final List<RegistryEntry> registry;
  final List<School> schools;

  EduTreeData({
    required this.meta,
    required this.regions,
    required this.tracks,
    required this.academies,
    this.registry = const [],
    this.schools = const [],
  });

  late final Map<String, Region> regionById = {
    for (final r in regions) r.id: r
  };
  late final Map<String, Academy> academyById = {
    for (final a in academies) a.id: a
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

  List<Track> tracksFor({String? subject, String? schoolLevel}) {
    return tracks
        .where((t) =>
            (subject == null || t.subject == subject) &&
            (schoolLevel == null || t.schoolLevel == schoolLevel))
        .toList();
  }

  /// 지역 랭킹. 표본 부족 학원은 제외한다(제품 정책).
  List<Academy> ranking({
    required String regionId,
    String? subject,
    String? schoolLevel,
    bool includeUnranked = false,
  }) {
    final rows = academies.where((a) {
      if (!matchRegion(a.regionId, regionId)) return false;
      if (!includeUnranked && !a.score.isRanked) return false;
      if (subject != null && !a.subjects.contains(subject)) return false;
      if (schoolLevel != null && !a.schoolLevels.contains(schoolLevel)) {
        return false;
      }
      return true;
    }).toList();
    rows.sort((a, b) => b.score.total.compareTo(a.score.total));
    return rows;
  }

  /// 표본 부족으로 순위에서 빠진 학원들 — 별도 섹션에 보여준다.
  List<Academy> unranked(String regionId) {
    final rows = academies
        .where((a) => matchRegion(a.regionId, regionId) && !a.score.isRanked)
        .toList();
    rows.sort((a, b) => a.name.compareTo(b.name));
    return rows;
  }

  /// 검색 결과. 점수가 있는 학원을 먼저, 등록부 학원을 뒤에 둔다.
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
    for (final r in registry) {
      if (r.name.toLowerCase().contains(q) ||
          r.displayName.toLowerCase().contains(q)) {
        hits.add(SearchHit.listed(r));
      }
    }
    return hits.take(40).toList();
  }

  /// 학군별 등록 학원 수 — 채점 대상뿐 아니라 등록부 전체를 센다.
  /// 지도의 밀도는 '우리가 점수를 매긴 수'가 아니라 '실제로 있는 수'여야 한다.
  List<School> schoolsIn(String regionId, {String? level}) => schools
      .where((s) =>
          matchRegion(s.regionId, regionId) &&
          (level == null || s.level == level))
      .toList()
    ..sort((a, b) => a.name.compareTo(b.name));

  int academyCountIn(String regionId) =>
      academies.where((a) => a.regionId == regionId).length +
      registry.where((r) => r.regionId == regionId).length;

  /// 채점까지 마친 학원 수
  int evaluatedCountIn(String regionId) =>
      academies.where((a) => a.regionId == regionId).length;

  /// 학군 × 과목 분포 — 등록부까지 포함
  Map<String, int> subjectBreakdown(String regionId) {
    final counts = <String, int>{};
    void add(List<String> subjects) {
      for (final s in subjects.isEmpty ? const ['etc'] : subjects) {
        counts[s] = (counts[s] ?? 0) + 1;
      }
    }
    for (final a in academies.where((a) => a.regionId == regionId)) {
      add(a.subjects);
    }
    for (final r in registry.where((r) => r.regionId == regionId)) {
      add(r.subjects);
    }
    return counts;
  }
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

  Future<EduTreeData> load() async {
    final results = await Future.wait([
      _json('assets/data/meta.json'),
      _json('assets/data/regions.json'),
      _json('assets/data/techtree.json'),
      _json('assets/data/academies.json'),
      _json('assets/data/registry.json'),
      _json('assets/data/schools.json'),
    ]);

    return EduTreeData(
      meta: Meta.fromJson((results[0] as Map).cast<String, dynamic>()),
      regions: (results[1] as List)
          .map((e) => Region.fromJson((e as Map).cast<String, dynamic>()))
          .toList(),
      tracks: ((results[2] as Map)['tracks'] as List)
          .map((e) => Track.fromJson((e as Map).cast<String, dynamic>()))
          .toList(),
      academies: (results[3] as List)
          .map((e) => Academy.fromJson((e as Map).cast<String, dynamic>()))
          .toList(),
      registry: (results[4] as List)
          .map((e) => RegistryEntry.fromJson((e as Map).cast<String, dynamic>()))
          .toList(),
      schools: (results[5] as List)
          .map((e) => School.fromJson((e as Map).cast<String, dynamic>()))
          .toList(),
    );
  }

  Future<dynamic> _json(String path) async =>
      jsonDecode(await rootBundle.loadString(path));
}

final repositoryProvider =
    Provider<EduTreeRepository>((ref) => const EduTreeRepository());

final dataProvider = FutureProvider<EduTreeData>(
    (ref) => ref.watch(repositoryProvider).load());

/// 전역 선택 상태 — 지역 / 과목 / 학교급
class Selection {
  /// 'all' | 'daechi' | 'mokdong' | 'banpo' | 'jamsil'
  final String regionId;
  final String subject;
  final String schoolLevel;

  const Selection({
    this.regionId = 'daechi',
    this.subject = 'math',
    this.schoolLevel = 'elementary',
  });

  Selection copyWith({String? regionId, String? subject, String? schoolLevel}) =>
      Selection(
        regionId: regionId ?? this.regionId,
        subject: subject ?? this.subject,
        schoolLevel: schoolLevel ?? this.schoolLevel,
      );

  String get trackId => '${subject}_$schoolLevel';
  bool get isAllRegions => regionId == 'all';
}

class SelectionNotifier extends Notifier<Selection> {
  @override
  Selection build() => const Selection();

  void setRegion(String id) => state = state.copyWith(regionId: id);
  void setSubject(String id) => state = state.copyWith(subject: id);
  void setSchoolLevel(String id) => state = state.copyWith(schoolLevel: id);
}

final selectionProvider =
    NotifierProvider<SelectionNotifier, Selection>(SelectionNotifier.new);
