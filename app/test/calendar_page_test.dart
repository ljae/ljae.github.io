import 'dart:convert';

import 'package:edutree/core/theme.dart';
import 'package:edutree/data/academy_calendar.dart';
import 'package:edutree/features/calendar/calendar_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, Object?> _event(
  String title, {
  required List<String> dates,
  List<String> bands = const [],
  String kind = 'session',
}) => {
  'title': title,
  'url': 'https://example.com/${title.hashCode}',
  'postedAt': '2026-11-01',
  'kind': kind,
  'source': 'news',
  'dates': dates,
  'bands': bands,
};

String _file(List<Map<String, Object?>> events) => jsonEncode({
  'region': '대치',
  'generatedAt': '2026-11-14T13:00:00+00:00',
  'windowDays': 31,
  'events': events,
});

final _today = DateTime.utc(2026, 11, 14);

Future<void> _pump(
  WidgetTester tester,
  Future<String> Function() source, {
  double width = 375,
  bool dark = false,
}) async {
  tester.view.physicalSize = Size(width, 2400);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        calendarSourceProvider.overrideWithValue(source),
        calendarTodayProvider.overrideWithValue(_today),
      ],
      child: MaterialApp(
        theme: buildTheme(dark: dark),
        home: const Scaffold(body: CalendarPage()),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

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
}
