import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:edutree/data/source_notes.dart';
import 'package:edutree/features/sources/sources_page.dart';
import 'package:edutree/widgets/academy_sources_button.dart';

void main() {
  testWidgets('grade evidence is loaded and joined to its exact academy', (
    tester,
  ) async {
    rootBundle.clear();
    final messenger =
        TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
    messenger.setMockMessageHandler('flutter/assets', (message) async {
      final path = utf8.decode(
        message!.buffer.asUint8List(
          message.offsetInBytes,
          message.lengthInBytes,
        ),
      );
      return ByteData.sublistView(File(path).readAsBytesSync());
    });
    addTearDown(() {
      messenger.setMockMessageHandler('flutter/assets', null);
      rootBundle.clear();
    });
    final container = ProviderContainer();
    addTearDown(container.dispose);
    final sources = await container.read(sourceNotesProvider.future);
    final grades = sources
        .firstWhere((r) => r.academyId == '3000027539')
        .notes
        .where((n) => n.topic == '대상 학년')
        .toList();
    expect(grades, isNotEmpty);
    expect(grades.first.url, 'https://www.highonemath.com/program.html');
    expect(grades.first.supports('math'), isTrue);
    expect(grades.first.supports('english'), isFalse);
    expect(sourceTopics, contains('대상 학년'));
  });

  test(
    'directory operating information remains visible with a subject filter',
    () {
      const note = SourceNote(
        topic: '운영·일정',
        title: '학원 소개',
        summary: '셔틀 제공 안내',
        url: 'https://www.gangmom.kr/institute/example',
        checkedAt: '2026-09-19',
        kind: 'directory',
      );
      expect(note.supports('math'), isTrue);
      expect(note.isPrimary, isFalse);
      expect(note.sourceLabel, '학원 소개 · 주소 대조');
    },
  );

  final raw =
      jsonDecode(File('assets/research/source_notes.json').readAsStringSync())
          as List;
  final rows = raw
      .map((j) => AcademySources.fromJson(Map<String, dynamic>.from(j as Map)))
      .toList();

  test('published source notes have valid academy IDs, links and dates', () {
    final academies =
        jsonDecode(File('assets/data/academies.json').readAsStringSync())
            as List;
    final ids = academies.map((a) => a['id']).toSet();
    expect(rows.map((r) => r.academyId).toSet().length, rows.length);
    for (final row in rows) {
      expect(ids, contains(row.academyId));
      expect(row.caveat, isNotEmpty);
      for (final n in row.notes) {
        expect(sourceTopics, contains(n.topic));
        expect(['https', 'http'], contains(Uri.parse(n.url).scheme));
        expect(Uri.parse(n.url).host, isNotEmpty);
        expect(DateTime.tryParse(n.checkedAt), isNotNull);
        expect(n.summary, isNotEmpty);
        expect(n.subjects, isNotEmpty);
        expect(['branch', 'brand'], contains(n.sourceScope));
        expect(n.isPrimary, isTrue);
        if (n.shortSummary != null) {
          expect(n.shortSummary!.length, lessThanOrEqualTo(55));
        }
      }
    }
  });

  test('compact notes respect subject and primary source boundaries', () {
    final sources = AcademySources.fromJson({
      'academyId': 'example',
      'name': 'Example',
      'scope': 'brand',
      'caveat': 'Branch conditions differ',
      'notes': [
        {
          'topic': '수업·교재',
          'title': 'Directory',
          'summary': 'Unverified',
          'shortSummary': 'Directory claim',
          'kind': 'directory',
          'subjects': ['math'],
          'url': 'https://example.com/directory',
          'checkedAt': '2026-09-17',
        },
        {
          'topic': '수업·교재',
          'title': 'Science',
          'summary': 'Science curriculum',
          'shortSummary': 'Science only',
          'subjects': ['science'],
          'url': 'https://example.com/science',
          'checkedAt': '2026-09-17',
        },
        {
          'topic': '수업·교재',
          'title': 'Math',
          'summary': 'Math curriculum',
          'shortSummary': 'Math only',
          'subjects': ['math'],
          'sourceScope': 'brand',
          'url': 'https://example.com/math',
          'checkedAt': '2026-09-17',
        },
      ],
    });
    expect(
      sources.compactNote('수업·교재', subject: 'math')?.shortSummary,
      'Math only',
    );
    expect(
      sources.compactNote('수업·교재', subject: 'math')?.sourceLabel,
      '브랜드 공통 안내',
    );
    expect(sources.compactNote('수업·교재', subject: 'english'), isNull);
    expect(sources.compactNote('입학·레벨테스트', subject: 'math'), isNull);
  });

  testWidgets('compact source sheet displays evidence on a narrow screen', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(320, 720);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: AcademySourcesButton(sources: rows.first, subject: 'english'),
        ),
      ),
    );
    await tester.tap(find.byType(TextButton));
    await tester.pumpAndSettle();
    expect(find.text(rows.first.caveat), findsOneWidget);
    expect(find.text(rows.first.notes.first.summary), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  for (final width in [375.0, 1200.0]) {
    testWidgets('topic comparison and missing evidence work at width $width', (
      tester,
    ) async {
      tester.view.physicalSize = Size(width, 1800);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(
        ProviderScope(
          overrides: [sourceNotesProvider.overrideWith((ref) async => rows)],
          child: const MaterialApp(home: Scaffold(body: SourcesPage())),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('원출처로 비교하기'), findsOneWidget);
      expect(find.text(rows.first.notes.first.summary), findsOneWidget);
      expect(tester.takeException(), isNull);
      await tester.tap(find.widgetWithText(ChoiceChip, '숙제'));
      await tester.pumpAndSettle();
      expect(find.text(rows.first.notes.first.summary), findsNothing);
      expect(find.textContaining('확인한 자료 없음'), findsWidgets);
      expect(find.text('잘 맞는 아이'), findsNothing);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('a different branch does not inherit source notes', (
    tester,
  ) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [sourceNotesProvider.overrideWith((ref) async => rows)],
        child: const MaterialApp(
          home: Scaffold(body: AcademySourcePanel(academyId: '3000035683')),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('공식 안내에서 확인한 것'), findsNothing);
  });
}
