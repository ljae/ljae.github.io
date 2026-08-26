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

  /// 단계 → 그 단계를 담당하는 학원들 (지역 필터 적용 가능).
  ///
  /// **근거가 강한 순으로 세운다.** 파이프라인이 단계마다 왜 붙었는지를
  /// 함께 내려준다(curated · hinted · inferred). 예전에는 셋이 한 덩어리로
  /// 와서 '사람이 확인한 매핑'과 '과목·학년만 보고 넣은 것'이 화면에서
  /// 구분되지 않았다.
  ///
  /// [fillTo] 를 주면 근거가 있는 곳이 그만큼 안 될 때 **같은 과목·학년
  /// 구간**의 학원을 이어 붙인다(basis `band`). 파이프라인은 근거 없는
  /// 배정을 만들지 않으므로 세부 단계(선행·영재고 대비 …)는 비기 쉬운데,
  /// 없는 근거를 데이터에 지어 넣는 대신 화면에서 '이 단계 특정 근거
  /// 없음'이라 적고 이어 붙인다. 랭킹의 '표본 부족' 폴백과 같은 방식이다.
  List<StageMatch> academiesForStage(String stageId,
      {String? regionId, int fillTo = 0}) {
    final stage = stageById[stageId];
    final subject = stage == null ? null : trackById[stage.trackId]?.subject;

    int byScore(Academy a, Academy b) {
      final sa = a.scoreFor(subject), sb = b.scoreFor(subject);
      // 랭킹에 든 곳을 먼저. 점수가 있는 것과 없는 것을 한 줄에 세우면
      // 코호트 평균으로 채워진 값이 실제 평가처럼 읽힌다.
      if (sa.isRanked != sb.isRanked) return sa.isRanked ? -1 : 1;
      return sb.total.compareTo(sa.total);
    }

    final direct = academies
        .where((a) =>
            a.stages.contains(stageId) && matchRegion(a.regionId, regionId))
        .toList()
      ..sort((a, b) {
        final fa = a.isFlagshipOf(stageId) ? 1 : 0;
        final fb = b.isFlagshipOf(stageId) ? 1 : 0;
        if (fa != fb) return fb - fa;
        // 근거의 강도는 **정렬이 아니라 카드의 딱지**로 말한다. 여기 있는
        // 곳은 전부 근거가 있고, 그다음 학부모가 궁금한 것은 '어느 쪽이
        // 더 알려졌나'다. 근거 등급은 점수가 같을 때만 본다.
        final byS = byScore(a, b);
        if (byS != 0) return byS;
        return StageMatch.rank(a.stageBasisOf(stageId)) -
            StageMatch.rank(b.stageBasisOf(stageId));
      });

    final out = [
      for (final a in direct) StageMatch(a, a.stageBasisOf(stageId)),
    ];
    if (out.length >= fillTo || stage == null || subject == null) return out;

    final seen = {for (final m in out) m.academy.id};
    final bands = stage.gradeBands;
    final extra = academies
        .where((a) =>
            !seen.contains(a.id) &&
            matchRegion(a.regionId, regionId) &&
            a.subjects.contains(subject) &&
            // 구간이 비어 있는 학원은 '어느 학년대인지 공시에 없음'이다.
            // 어느 구간에도 안 넣으면 통째로 사라진다 — 필터와 같게 읽는다.
            (a.gradeBands.isEmpty ||
                a.gradeBands.any((b) => bands.contains(b))))
        .toList()
      ..sort(byScore);

    out.addAll(
        extra.take(fillTo - out.length).map((a) => StageMatch(a, 'band')));
    return out;
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

  /// 지역 랭킹. **근거가 한 건이라도 있으면 줄을 세운다.**
  ///
  /// 예전에는 표본 10건 미만을 순위에서 통째로 뺐다. 그랬더니 96개
  /// 조합(4학군 × 6과목 × 4구간) 중 순위가 10곳을 넘는 곳이 **하나뿐**
  /// 이었다 — 학부모가 '반포 과학 초등' 을 눌러도 빈 화면을 봤다.
  ///
  /// 그래서 기준을 바꿨다. 표본이 **1건 이상**이면 순위에 넣되,
  /// 10건 미만은 카드에 '표본 부족' 이라 적는다(Score.isRanked 가 그
  /// 표시를 판단한다). 등수를 감추는 대신 **근거의 두께를 함께** 보여
  /// 주는 쪽이다.
  ///
  /// ★ 표본 0 은 여기 넣지 않는다. 점수가 코호트 평균(50)으로 채워져
  ///   있어 등수를 매기면 그건 평가가 아니라 기본값이다. [unscored] 로
  ///   따로 나가고 화면에서는 등수 없이 '근거 없음' 으로 적는다.
  List<Academy> ranking({
    required String regionId,
    String? subject,
    String? gradeBand,
    bool includeUnranked = false,
  }) {
    // ★ 과목 랭킹은 그 과목의 점수로 거르고 세운다. 대표 점수를 쓰면
    //   수학 후기가 많은 종합학원이 과학 랭킹 상위를 차지한다.
    final rows = academies
        .where((a) =>
            (includeUnranked || a.scoreFor(subject).sampleSize > 0) &&
            _matchesFilters(a,
                regionId: regionId, subject: subject, gradeBand: gradeBand))
        .toList();
    rows.sort((a, b) =>
        b.scoreFor(subject).total.compareTo(a.scoreFor(subject).total));
    return rows;
  }

  /// 아직 근거가 한 건도 없는 학원. **등수를 매기지 않는다.**
  ///
  /// **랭킹과 같은 조건으로 걸러야 한다.** 지역만 보고 뽑으면 영어 랭킹
  /// 아래에 미술·수학 학원까지 늘어서서, 그 목록이 무엇의 목록인지
  /// 읽히지 않는다.
  ///
  /// 표본 0 이면 점수가 코호트 평균으로 채워진다. 그 값으로 3위·4위를
  /// 붙이면 화면의 등수가 평가 결과가 아니라 기본값이 된다 — 실명
  /// 사업자를 다루는 서비스에서 그건 없는 사실을 지어내는 것이다.
  /// '아직 안 봤다' 와 '보고서 낮았다' 는 다른 상태다.
  List<Academy> unscored(
    String regionId, {
    String? subject,
    String? gradeBand,
  }) {
    final rows = academies
        .where((a) =>
            a.scoreFor(subject).sampleSize == 0 &&
            _matchesFilters(a,
                regionId: regionId, subject: subject, gradeBand: gradeBand))
        .toList();
    // 정원이 큰 곳부터. 이름순은 'ㄱ' 으로 시작하는 곳이 늘 위에 올 뿐
    // 아무것도 뜻하지 않는다.
    rows.sort((a, b) => (b.capacity ?? 0).compareTo(a.capacity ?? 0));
    return rows;
  }

  /// 순위 + 미수집을 합쳐도 [want] 곳이 안 되면 **등록부에서 채운다.**
  ///
  /// 채점 대상은 400곳뿐이고 회차마다 순환한다. 그래서 조합에 따라
  /// 채점 대상 안에 학원이 서넛밖에 없다(실측: 대치 과학 예비초~초3 은
  /// 3곳). 그 화면을 그대로 두면 학부모는 그 구간에 학원이 셋뿐인 줄
  /// 안다 — 실제로는 등록부에 스무 곳이 넘는다.
  ///
  /// ★ 등록부 학원에는 **점수도 등수도 붙이지 않는다.** 수집한 적이
  ///   없으니 붙일 근거가 없다. 화면에도 '등록부 · 미수집' 이라 적는다.
  ///   등록부 행에는 학년 구간이 없어 어느 구간에서나 나온다 — 필터가
  ///   빈 구간을 '한정되지 않음' 으로 읽는 것과 같은 규칙이다.
  List<RegistryEntry> registryFill(
    List<RegistryEntry> registry, {
    required String regionId,
    String? subject,
    required int have,
    int want = 10,
  }) {
    if (have >= want || registry.isEmpty) return const [];
    final rows = registry
        .where((r) =>
            matchRegion(r.regionId, regionId) &&
            (subject == null || r.subjects.contains(subject)))
        .toList()
      // 정원이 큰 곳부터. 학부모가 이름을 들어 봤을 확률이 그나마 높다.
      ..sort((a, b) => (b.capacity ?? 0).compareTo(a.capacity ?? 0));
    return rows.take(want - have).toList();
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
