import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'repository.dart';

/// 학군별 학원 일정(설명회·테스트·개강) — `assets/data/calendar.json`.
///
/// 만드는 쪽은 `pipeline/edutree/digest.py` 다. 학원 측이 올린 안내 글을
/// 공식 검색 API 로 찾아 제목에 적힌 날짜만 옮긴 것이라 **우리가 확인한
/// 일정이 아니고 점수에도 쓰지 않는다.** 화면은 그 사실을 함께 적는다.
///
/// 예비초(만 3세~취학 전) 대상 테스트·면접은 2026-10-01 부터 학원법
/// 시행령으로 금지라 파이프라인이 애초에 싣지 않는다.

const calendarKindNames = <String, String>{
  'session': '설명회',
  'test': '테스트',
  'open': '개강',
};

const calendarSourceNames = <String, String>{
  'news': '뉴스',
  'blog': '블로그',
  'homepage': '학원 홈페이지',
};

class CalendarEvent {
  final String title;
  final String url;
  final String postedAt;
  final String kind;
  final String source;
  final List<DateTime> dates;

  /// 비면 학년 공통 — 어느 학년 필터에서도 보인다.
  final List<String> bands;

  /// 이 글이 속한 학군 id. 옛 파일(대치만 싣던 때)의 행에는 없다 —
  /// 그때는 대치뿐이었으므로 없으면 `['daechi']` 로 읽는다.
  final List<String> regions;

  /// 달력 칸에 적을 짧은 말('세정 설명회'). 없으면 종류 낱말.
  final String label;

  const CalendarEvent({
    required this.title,
    required this.url,
    required this.postedAt,
    required this.kind,
    required this.source,
    required this.dates,
    required this.bands,
    this.regions = const ['daechi'],
    String? label,
  }) : label = label ?? '';

  /// 칸에 적을 말. 파일에 없으면 종류 낱말('설명회').
  String get cellLabel => label.trim().isNotEmpty
      ? label.trim()
      : (calendarKindNames[kind] ?? kind);

  /// [regionId] 가 null 이거나 'all' 이면 어느 학군이든 맞는다
  /// (`EduTreeData.matchRegion` 과 같은 뜻).
  bool inRegion(String? regionId) =>
      regionId == null || regionId == 'all' || regions.contains(regionId);

  bool get isCommon => bands.isEmpty;

  /// 모르는 꼴의 행은 버린다(null). 행 하나가 틀렸다고 판 전체를 잃지 않는다.
  static CalendarEvent? tryParse(Object? raw) {
    if (raw is! Map) return null;
    final title = raw['title'];
    final url = raw['url'];
    final kind = raw['kind'];
    if (title is! String || title.trim().isEmpty) return null;
    if (url is! String || url.isEmpty) return null;
    if (kind is! String || !calendarKindNames.containsKey(kind)) return null;
    final dates = <DateTime>[];
    for (final d in (raw['dates'] as List?) ?? const []) {
      final day = d is String ? parseCalendarDay(d) : null;
      if (day != null) dates.add(day);
    }
    if (dates.isEmpty) return null;
    final rawRegions = raw['regions'];
    final regions = [
      if (rawRegions is List)
        for (final r in rawRegions)
          if (r is String && r.isNotEmpty) r,
    ];
    final label = raw['label'];
    return CalendarEvent(
      title: title.trim(),
      url: url,
      postedAt: (raw['postedAt'] as String?) ?? '',
      kind: kind,
      source: (raw['source'] as String?) ?? '',
      dates: dates,
      bands: [
        for (final b in (raw['bands'] as List?) ?? const [])
          if (b is String) b,
      ],
      regions: regions.isEmpty ? const ['daechi'] : regions,
      label: label is String ? label : null,
    );
  }
}

/// 'YYYY-MM-DD' → 그날 0시(지역 시각 없는 날짜). 틀린 꼴이면 null.
DateTime? parseCalendarDay(String s) {
  final m = RegExp(r'^(\d{4})-(\d{2})-(\d{2})$').firstMatch(s.trim());
  if (m == null) return null;
  final y = int.parse(m[1]!), mo = int.parse(m[2]!), d = int.parse(m[3]!);
  final day = DateTime.utc(y, mo, d);
  // 2026-02-31 같은 값은 DateTime 이 다음 달로 넘겨 버린다. 넘긴 값은 거짓이다.
  if (day.year != y || day.month != mo || day.day != d) return null;
  return day;
}

class AcademyCalendar {
  /// 파일이 다루는 학군 id. 옛 파일은 `region: '대치'` 한 값뿐이었다.
  final List<String> regions;
  final String generatedAt;
  final int windowDays;
  final List<CalendarEvent> events;

  const AcademyCalendar({
    required this.regions,
    required this.generatedAt,
    required this.windowDays,
    required this.events,
  });

  /// 파일 꼴이 틀리면 null — 화면은 '불러올 수 없음' 으로 적는다.
  static AcademyCalendar? tryParse(String body) {
    try {
      final j = jsonDecode(body);
      if (j is! Map) return null;
      final raw = j['events'];
      if (raw is! List) return null;
      final rawRegions = j['regions'];
      return AcademyCalendar(
        regions: rawRegions is List
            ? [
                for (final r in rawRegions)
                  if (r is String) r,
              ]
            : const ['daechi'],
        generatedAt: (j['generatedAt'] as String?) ?? '',
        windowDays: (j['windowDays'] as num?)?.toInt() ?? 31,
        events: [for (final e in raw) ?CalendarEvent.tryParse(e)],
      );
    } catch (_) {
      return null;
    }
  }

  /// 수집일을 한국 시각 날짜로. 모르면 null.
  DateTime? get generatedDayKst {
    final t = DateTime.tryParse(generatedAt);
    if (t == null) return null;
    final k = t.toUtc().add(const Duration(hours: 9));
    return DateTime.utc(k.year, k.month, k.day);
  }

  /// 거르개를 지난 글을 날짜별로 묶는다(지난 날짜 포함). 한 글이 여러
  /// 날이면 날마다 선다. 달력 격자와 목록이 **같은 묶음**을 본다 — 따로
  /// 거르면 격자에 있는 날이 목록에 없는 일이 생긴다.
  ///
  /// [band] 가 null 이면 전체. 아니면 그 학년 글 + 학년 공통 글.
  /// [kind] 가 null 이면 종류 전체. [region] 이 null·'all' 이면 학군 전체.
  Map<DateTime, List<CalendarEvent>> byDay({
    String? band,
    String? kind,
    String? region,
  }) {
    final out = <DateTime, List<CalendarEvent>>{};
    for (final e in events) {
      if (band != null && !e.isCommon && !e.bands.contains(band)) continue;
      if (kind != null && e.kind != kind) continue;
      if (!e.inRegion(region)) continue;
      for (final d in e.dates.toSet()) {
        out.putIfAbsent(d, () => []).add(e);
      }
    }
    const kindOrder = ['session', 'test', 'open'];
    for (final list in out.values) {
      list.sort((a, b) {
        final k = kindOrder
            .indexOf(a.kind)
            .compareTo(kindOrder.indexOf(b.kind));
        return k != 0 ? k : a.title.compareTo(b.title);
      });
    }
    return out;
  }

  /// 오늘 이후의 날짜만 날짜순으로.
  List<CalendarDay> agenda({
    required DateTime today,
    String? band,
    String? kind,
    String? region,
  }) {
    final start = DateTime.utc(today.year, today.month, today.day);
    final grouped = byDay(band: band, kind: kind, region: region);
    final days = grouped.keys.where((d) => !d.isBefore(start)).toList()..sort();
    return [for (final d in days) CalendarDay(day: d, events: grouped[d]!)];
  }
}

class CalendarDay {
  final DateTime day;
  final List<CalendarEvent> events;
  const CalendarDay({required this.day, required this.events});
}

/// 원문 읽기. 시험에서는 바꿔 끼운다.
final calendarSourceProvider = Provider<Future<String> Function()>(
  (ref) =>
      () => rootBundle.loadString('assets/data/calendar.json'),
);

/// 일정 — 이 화면에 들어올 때 처음 읽힌다(첫 그림에는 안 싣는다).
/// 없거나 꼴이 틀리면 null.
final academyCalendarProvider = FutureProvider<AcademyCalendar?>((ref) async {
  try {
    final body = await ref.watch(calendarSourceProvider)();
    return AcademyCalendar.tryParse(body);
  } catch (_) {
    return null;
  }
});

/// 오늘(한국 날짜). 파일이 하루 묵어도 지난 날짜는 화면에서 뺀다.
final calendarTodayProvider = Provider<DateTime>((ref) {
  final k = DateTime.now().toUtc().add(const Duration(hours: 9));
  return DateTime.utc(k.year, k.month, k.day);
});

/// 일정 화면의 거르개. 학년은 헤더와 같은 [selectionProvider] 를 쓰고,
/// 여기에는 '전체 학년' 여부와 종류만 둔다 — 학년을 두 곳에 들고 있으면
/// 헤더와 화면이 서로 다른 학년을 가리키게 된다.
class CalendarFilter {
  final bool allBands;

  /// null = 종류 전체.
  final String? kind;

  const CalendarFilter({this.allBands = false, this.kind});

  CalendarFilter copyWith({bool? allBands, String? Function()? kind}) =>
      CalendarFilter(
        allBands: allBands ?? this.allBands,
        kind: kind == null ? this.kind : kind(),
      );

  @override
  bool operator ==(Object other) =>
      other is CalendarFilter &&
      other.allBands == allBands &&
      other.kind == kind;

  @override
  int get hashCode => Object.hash(allBands, kind);
}

class CalendarFilterNotifier extends Notifier<CalendarFilter> {
  @override
  CalendarFilter build() => const CalendarFilter();

  void showAllBands() => state = state.copyWith(allBands: true);

  void selectBand(String band) {
    ref.read(selectionProvider.notifier).setGradeBand(band);
    state = state.copyWith(allBands: false);
  }

  void setKind(String? kind) => state = state.copyWith(kind: () => kind);
}

final calendarFilterProvider =
    NotifierProvider<CalendarFilterNotifier, CalendarFilter>(
      CalendarFilterNotifier.new,
    );

/// 학군 이름(id → '대치'). 앱 자료(`regions.json`)가 왔으면 그 이름을,
/// 아직이면 네 학군의 고정 이름을 쓴다 — 일정 화면이 학원 자료 전체를
/// 기다리지 않게. 시험에서는 바꿔 끼운다.
const _fallbackRegionNames = <String, String>{
  'daechi': '대치',
  'mokdong': '목동',
  'jamsil': '잠실',
  'banpo': '반포',
};

final calendarRegionNamesProvider = Provider<Map<String, String>>((ref) {
  final loaded = ref.watch(dataProvider.select((d) => d.value?.regionById));
  if (loaded == null || loaded.isEmpty) return _fallbackRegionNames;
  return {
    ..._fallbackRegionNames,
    for (final e in loaded.entries) e.key: e.value.nameKo,
  };
});
