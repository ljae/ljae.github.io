import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:edutree/data/source_notes.dart';
import 'package:edutree/features/sources/sources_page.dart';

void main() {
  final raw = jsonDecode(File('assets/research/source_notes.json').readAsStringSync()) as List;
  final rows = raw.map((j) => AcademySources.fromJson(
    Map<String, dynamic>.from(j as Map))).toList();

  test('published source notes have valid academy IDs, links and dates', () {
    final academies = jsonDecode(File('assets/data/academies.json').readAsStringSync()) as List;
    final ids = academies.map((a) => a['id']).toSet();
    expect(rows.map((r) => r.academyId).toSet().length, rows.length);
    for (final row in rows) {
      expect(ids, contains(row.academyId));
      expect(row.caveat, isNotEmpty);
      for (final n in row.notes) {
        expect(sourceTopics, contains(n.topic));
        expect(Uri.parse(n.url).scheme, 'https');
        expect(Uri.parse(n.url).host, isNotEmpty);
        expect(DateTime.tryParse(n.checkedAt), isNotNull);
        expect(n.summary, isNotEmpty);
      }
    }
  });

  for (final width in [375.0, 1200.0]) {
    testWidgets('topic comparison and missing evidence work at width $width', (tester) async {
      tester.view.physicalSize = Size(width, 1800);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(ProviderScope(overrides: [
        sourceNotesProvider.overrideWith((ref) async => rows),
      ], child: const MaterialApp(home: Scaffold(body: SourcesPage()))));
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

  testWidgets('a different branch does not inherit source notes', (tester) async {
    await tester.pumpWidget(ProviderScope(overrides: [
      sourceNotesProvider.overrideWith((ref) async => rows),
    ], child: const MaterialApp(home: Scaffold(
      body: AcademySourcePanel(academyId: '3000035683')))));
    await tester.pumpAndSettle();
    expect(find.text('공식 안내에서 확인한 것'), findsNothing);
  });
}
