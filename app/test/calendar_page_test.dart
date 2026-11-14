import 'dart:convert';

import 'package:edutree/core/theme.dart';
import 'package:edutree/data/academy_calendar.dart';
import 'package:edutree/data/repository.dart';
import 'package:edutree/features/calendar/calendar_page.dart';
import 'package:edutree/features/calendar/month_grid.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, Object?> _event(
  String title, {
  required List<String> dates,
  List<String> bands = const [],
  String kind = 'session',
  List<String>? regions,
  String? label,
}) => {
  'title': title,
  'url': 'https://example.com/${title.hashCode}',
  'postedAt': '2026-11-01',
  'kind': kind,
  'source': 'news',
  'dates': dates,
  'bands': bands,
  'regions': ?regions,
  'label': ?label,
};

String _file(List<Map<String, Object?>> events) => jsonEncode({
  'regions': ['daechi', 'mokdong', 'jamsil', 'banpo'],
  'generatedAt': '2026-11-14T13:00:00+00:00',
  'windowDays': 62,
  'events': events,
});

const _names = {'daechi': '대치', 'mokdong': '목동', 'jamsil': '잠실', 'banpo': '반포'};

final _today = DateTime.utc(2026, 11, 14);

Future<ProviderContainer> _pump(
  WidgetTester tester,
  Future<String> Function() source, {
  double width = 375,
  double height = 2400,
  bool dark = false,
  String region = 'daechi',
}) async {
  tester.view.physicalSize = Size(width, height);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final container = ProviderContainer(
    overrides: [
      calendarSourceProvider.overrideWithValue(source),
      calendarTodayProvider.overrideWithValue(_today),
      calendarRegionNamesProvider.overrideWithValue(_names),
    ],
  );
  addTearDown(container.dispose);
  container.read(selectionProvider.notifier).setRegion(region);
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: MaterialApp(
        theme: buildTheme(dark: dark),
        home: const Scaffold(body: CalendarPage()),
      ),
    ),
  );
  await tester.pumpAndSettle();
  return container;
}

/// 달력 칸의 날짜 숫자 중 [color] 로 칠한 것.
Finder _dayNumber(String day, Color color) => find.byWidgetPredicate(
  (w) => w is Text && w.data == day && w.style?.color == color,
);

void main() {
  final events = [
    _event('고등 입시설명회', dates: ['2026-11-20'], bands: ['high']),
    _event('초저 영어 설명회', dates: ['2026-11-21'], bands: ['elem_low']),
    _event('공통 개강 안내', dates: ['2026-11-22', '2026-12-05'], kind: 'open'),
    _event('지난 테스트', dates: ['2026-11-10'], bands: ['high'], kind: 'test'),
  ];

  testWidgets('학년 필터는 그 학년 글과 학년 공통 글을 함께 보인다', (tester) async {
    await _pump(tester, () async => _file(events));

    // 기본은 헤더와 같은 학년(예비초~초3).
    expect(find.text('초저 영어 설명회'), findsOneWidget);
    expect(find.text('공통 개강 안내'), findsNWidgets(2)); // 날짜 두 개에 각각
    expect(find.text('고등 입시설명회'), findsNothing);

    await tester.tap(find.text('고등').first);
    await tester.pumpAndSettle();
    expect(find.text('고등 입시설명회'), findsOneWidget);
    expect(find.text('공통 개강 안내'), findsNWidgets(2));
    expect(find.text('초저 영어 설명회'), findsNothing);

    await tester.tap(find.text('전체').first);
    await tester.pumpAndSettle();
    expect(find.text('고등 입시설명회'), findsOneWidget);
    expect(find.text('초저 영어 설명회'), findsOneWidget);

    // 확인되지 않은 안내라는 문구와 예비초 금지 안내가 늘 있다.
    expect(find.text(CalendarPage.unverifiedNote), findsOneWidget);
    expect(find.text(CalendarPage.preschoolNote), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('오늘 이전 날짜는 버린다', (tester) async {
    await _pump(tester, () async => _file(events));
    await tester.tap(find.text('전체').first);
    await tester.pumpAndSettle();
    expect(find.text('지난 테스트'), findsNothing);
    expect(find.textContaining('11월 10일'), findsNothing);
    expect(find.textContaining('11월 20일'), findsOneWidget);
  });

  test('여러 날짜 글은 남은 날짜에만 선다', () {
    final cal = AcademyCalendar.tryParse(
      _file([
        _event('두 날', dates: ['2026-11-13', '2026-11-14'], bands: ['middle']),
      ]),
    )!;
    final days = cal.agenda(today: _today, band: 'middle');
    expect(days.map((d) => d.day), [DateTime.utc(2026, 11, 14)]);
  });

  testWidgets('조건에 맞는 일정이 없으면 그렇게 적는다', (tester) async {
    await _pump(
      tester,
      () async => _file([
        _event('고등만', dates: ['2026-11-20'], bands: ['high']),
      ]),
    );
    expect(find.text(CalendarPage.emptyText), findsOneWidget);
    expect(find.text('고등만'), findsNothing);
    await tester.tap(find.text('전체 학년 보기'));
    await tester.pumpAndSettle();
    expect(find.text('고등만'), findsOneWidget);
    expect(find.text(CalendarPage.emptyText), findsNothing);
  });

  testWidgets('파일이 없거나 깨졌으면 지어내지 않고 알린다', (tester) async {
    await _pump(tester, () async => throw Exception('missing'));
    expect(find.text('일정 자료를 불러오지 못했습니다'), findsOneWidget);
    expect(find.text(CalendarPage.unverifiedNote), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('깨진 JSON 도 같은 상태다', (tester) async {
    await _pump(tester, () async => '{not json');
    expect(find.text('일정 자료를 불러오지 못했습니다'), findsOneWidget);
  });

  testWidgets('어두운 판 · 375px 에서 넘치지 않는다', (tester) async {
    await _pump(tester, () async => _file(events), dark: true);
    await tester.tap(find.text('전체').first);
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.text('오늘'), findsNothing); // 오늘 일정이 없으면 표시 안 함
  });

  testWidgets('오늘 날짜에만 오늘 표시를 붙인다', (tester) async {
    await _pump(
      tester,
      () async => _file([
        _event('오늘 설명회', dates: ['2026-11-14']),
      ]),
      width: 900,
    );
    expect(find.text('오늘'), findsOneWidget);
    expect(find.text('오늘 설명회'), findsOneWidget);
  });

  group('학군', () {
    final regional = [
      _event('대치 옛 행', dates: ['2026-11-20']), // regions 없음 → 대치
      _event('목동 설명회', dates: ['2026-11-21'], regions: ['mokdong']),
      _event(
        '대치잠실 개강',
        dates: ['2026-11-22'],
        regions: ['daechi', 'jamsil'],
        kind: 'open',
      ),
    ];

    test('regions 가 없는 행은 대치로 읽고, 옛 region 키도 읽는다', () {
      final cal = AcademyCalendar.tryParse(
        jsonEncode({
          'region': '대치',
          'generatedAt': '',
          'events': [
            _event('옛 행', dates: ['2026-11-20']),
          ],
        }),
      )!;
      expect(cal.regions, ['daechi']);
      expect(cal.events.single.regions, ['daechi']);
      expect(cal.events.single.cellLabel, '설명회'); // label 없음 → 종류 낱말
      expect(cal.agenda(today: _today, region: 'mokdong'), isEmpty);
      expect(cal.agenda(today: _today, region: 'daechi'), hasLength(1));
      expect(cal.agenda(today: _today, region: 'all'), hasLength(1));
    });

    testWidgets('헤더의 학군을 따른다 — 대치', (tester) async {
      await _pump(tester, () async => _file(regional), width: 900);
      await tester.tap(find.text('전체').first);
      await tester.pumpAndSettle();
      expect(find.text('대치 학원 일정'), findsOneWidget);
      expect(find.text('대치 옛 행'), findsOneWidget);
      expect(find.text('대치잠실 개강'), findsOneWidget);
      expect(find.text('목동 설명회'), findsNothing);
      // 한 학군만 볼 때는 줄마다 학군을 적지 않는다.
      expect(find.text('대치·잠실'), findsNothing);
    });

    testWidgets('목동을 고르면 목동 글만', (tester) async {
      await _pump(
        tester,
        () async => _file(regional),
        width: 900,
        region: 'mokdong',
      );
      await tester.tap(find.text('전체').first);
      await tester.pumpAndSettle();
      expect(find.text('목동 학원 일정'), findsOneWidget);
      expect(find.text('목동 설명회'), findsOneWidget);
      expect(find.text('대치 옛 행'), findsNothing);
    });

    testWidgets('전체 학군이면 모두 보이고 줄마다 학군을 적는다', (tester) async {
      final c = await _pump(tester, () async => _file(regional), width: 900);
      c.read(selectionProvider.notifier).setRegion('all');
      await tester.pumpAndSettle();
      await tester.tap(find.text('전체').first);
      await tester.pumpAndSettle();
      expect(find.text('전체 학군 학원 일정'), findsOneWidget);
      expect(find.text('대치 옛 행'), findsOneWidget);
      expect(find.text('목동 설명회'), findsOneWidget);
      expect(find.text('대치잠실 개강'), findsOneWidget);
      expect(find.text('목동'), findsOneWidget);
      expect(find.text('대치·잠실'), findsOneWidget);
      expect(find.text('대치'), findsOneWidget); // 옛 행
    });
  });

  group('달력 격자', () {
    final gridEvents = [
      _event('세정 설명회 원문', dates: ['2026-11-16'], label: '세정 설명회'),
      _event('긴 이름', dates: ['2026-11-18'], label: '아주아주아주긴학원이름 설명회'),
      _event('a', dates: ['2026-11-25'], label: '가 설명회'),
      _event('b', dates: ['2026-11-25'], label: '나 테스트', kind: 'test'),
      _event('c', dates: ['2026-11-25'], label: '다 개강', kind: 'open'),
      _event('다음달', dates: ['2026-12-05'], label: '에이프릴 개강', kind: 'open'),
      _event('지난', dates: ['2026-11-03'], label: '지난 설명회'),
    ];

    testWidgets('이번 달과 다음 달, 오늘은 주묵', (tester) async {
      await _pump(tester, () async => _file(gridEvents), width: 1200);
      await tester.tap(find.text('전체').first);
      await tester.pumpAndSettle();
      expect(find.byType(MonthGrid), findsNWidgets(2));
      expect(find.text('11월'), findsOneWidget);
      expect(find.text('12월'), findsOneWidget);
      final accent = AppColors.accentOn(false);
      expect(_dayNumber('14', accent), findsOneWidget);
      // 다른 날짜는 주묵이 아니다.
      expect(_dayNumber('15', accent), findsNothing);
      // 넓으면 나란히 선다.
      final a = tester.getTopLeft(find.byType(MonthGrid).first);
      final b = tester.getTopLeft(find.byType(MonthGrid).last);
      expect(a.dy, b.dy);
      expect(b.dx, greaterThan(a.dx));
    });

    testWidgets('칸에는 짧은 말, 둘까지 쓰고 나머지는 +N, 길면 줄임', (tester) async {
      await _pump(tester, () async => _file(gridEvents), width: 1200);
      await tester.tap(find.text('전체').first);
      await tester.pumpAndSettle();
      expect(find.text('세정 설명회'), findsOneWidget);
      expect(find.text('에이프릴 개강'), findsOneWidget);
      // 지난 날의 글도 칸에는 남는다(흐리게). 목록에는 없다.
      expect(find.text('지난 설명회'), findsOneWidget);
      expect(find.text('지난'), findsNothing);
      // 셋인 날: 둘 + '+1'.
      expect(find.text('가 설명회'), findsOneWidget);
      expect(find.text('나 테스트'), findsOneWidget);
      expect(find.text('다 개강'), findsNothing);
      expect(find.text('+1'), findsOneWidget);
      // 긴 말은 한 줄 줄임표로 칸 안에 머문다.
      final long = find.text('아주아주아주긴학원이름 설명회');
      final t = tester.widget<Text>(long);
      expect(t.maxLines, 1);
      expect(t.overflow, TextOverflow.ellipsis);
      final grid = tester.getRect(find.byType(MonthGrid).first);
      expect(tester.getSize(long).width, lessThan(grid.width / 7));
      expect(tester.takeException(), isNull);
    });

    testWidgets('학년·종류 거르개가 격자에도 걸린다', (tester) async {
      await _pump(tester, () async => _file(gridEvents), width: 1200);
      await tester.tap(find.text('전체').first);
      await tester.pumpAndSettle();
      await tester.tap(find.text('테스트').first);
      await tester.pumpAndSettle();
      expect(find.text('나 테스트'), findsOneWidget);
      expect(find.text('세정 설명회'), findsNothing);
      expect(find.text('+1'), findsNothing);
    });

    testWidgets('날짜를 누르면 목록의 그날로 내려간다', (tester) async {
      await _pump(
        tester,
        () async => _file(gridEvents),
        width: 1200,
        height: 900,
      );
      await tester.tap(find.text('전체').first);
      await tester.pumpAndSettle();
      final head = find.textContaining('12월 5일');
      expect(tester.getTopLeft(head).dy, greaterThan(900));
      await tester.tap(find.text('에이프릴 개강'));
      await tester.pumpAndSettle();
      final y = tester.getTopLeft(head).dy;
      // 목록의 끝이라 맨 위까지는 못 올라와도 화면 안에 들어온다.
      expect(y, greaterThanOrEqualTo(0));
      expect(y, lessThan(900 - 40));
    });

    testWidgets('375px 어두운 판에서 넘치지 않고 위아래로 쌓인다', (tester) async {
      await _pump(tester, () async => _file(gridEvents), dark: true);
      await tester.tap(find.text('전체').first);
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      final a = tester.getRect(find.byType(MonthGrid).first);
      final b = tester.getRect(find.byType(MonthGrid).last);
      expect(b.top, greaterThan(a.bottom));
      expect(a.right, lessThanOrEqualTo(375));
      expect(_dayNumber('14', AppColors.accentOn(true)), findsOneWidget);
    });

    testWidgets('글자를 못 넣는 폭에서는 종류 네모로 물러난다', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: buildTheme(dark: false),
          home: Scaffold(
            body: Center(
              child: SizedBox(
                width: 7 * 34,
                child: Builder(
                  builder: (context) => MonthGrid(
                    month: DateTime.utc(2026, 11, 1),
                    today: _today,
                    byDay: {
                      DateTime.utc(2026, 11, 16): [
                        CalendarEvent.tryParse(
                          _event('x', dates: ['2026-11-16'], label: '세정 설명회'),
                        )!,
                      ],
                    },
                    listedDays: const {},
                    onTapDay: (_) {},
                    metrics: MonthGridMetrics.of(context),
                  ),
                ),
              ),
            ),
          ),
        ),
      );
      expect(find.text('세정 설명회'), findsNothing);
      expect(tester.takeException(), isNull);
    });
  });
}
