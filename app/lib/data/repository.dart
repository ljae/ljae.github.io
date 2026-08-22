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

  EduTreeData({
    required this.meta,
    required this.regions,
    required this.tracks,
    required this.academies,
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

  /// 단계 → 그 단계를 담당하는 학원들 (지역 필터 적용 가능)
  List<Academy> academiesForStage(String stageId, {String? regionId}) {
    final rows = academies.where((a) =>
        a.stages.contains(stageId) &&
        (regionId == null || a.regionId == regionId));
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
      if (a.regionId != regionId) return false;
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
    final rows =
        academies.where((a) => a.regionId == regionId && !a.score.isRanked).toList();
    rows.sort((a, b) => a.name.compareTo(b.name));
    return rows;
  }

  List<Academy> search(String query) {
    final q = query.trim().toLowerCase();
    if (q.isEmpty) return const [];
    return academies.where((a) {
      if (a.name.toLowerCase().contains(q)) return true;
      if ((a.brand ?? '').toLowerCase().contains(q)) return true;
      return a.aliases.any((x) => x.toLowerCase().contains(q));
    }).take(30).toList();
  }

  int academyCountIn(String regionId) =>
      academies.where((a) => a.regionId == regionId).length;
}

class EduTreeRepository {
  const EduTreeRepository();

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
      academies: (results[3] as List)
          .map((e) => Academy.fromJson((e as Map).cast<String, dynamic>()))
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
