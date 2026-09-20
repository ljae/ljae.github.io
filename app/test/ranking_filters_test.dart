import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:edutree/core/theme.dart';
import 'package:edutree/data/models.dart';
import 'package:edutree/data/repository.dart';
import 'package:edutree/features/ranking/ranking_page.dart';
import 'package:edutree/widgets/academy_card.dart';

void main() {
  Academy academy(String id, double total, bool verified) => Academy.fromJson({
    'id': id,
    'name': '학원$id',
    'regionId': 'daechi',
    'subjects': ['math'],
    'gradeBands': ['elem_low'],
    'isVerified': verified,
    'subjectScores': {
      'math': {
        'total': total,
        'reputation': total,
        'momentum': total,
        'sampleSize': 20,
        'isRanked': true,
        'confidence': 'high',
      },
    },
    'score': {
      'total': total,
      'reputation': total,
      'momentum': total,
      'sampleSize': 20,
      'isRanked': true,
      'confidence': 'high',
    },
  });

  testWidgets(
    'verification and search keep original rank and filter all result groups',
    (tester) async {
      tester.view.physicalSize = const Size(1100, 1800);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final data = EduTreeData(
        meta: Meta.fromJson({'mode': 'live'}),
        regions: [],
        tracks: [],
        academies: [academy('A', 80, false), academy('B', 70, true)],
      );
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            dataProvider.overrideWith((ref) async => data),
            registryProvider.overrideWith((ref) async => []),
          ],
          child: MaterialApp(
            theme: buildTheme(dark: false),
            home: const Scaffold(body: RankingPage()),
          ),
        ),
      );
      await tester.pumpAndSettle();
      AcademyCard cardB() =>
          tester.widget<AcademyCard>(find.byKey(const ValueKey('B')));
      expect(cardB().rank, 2);
      await tester.tap(find.text('공시 확인'));
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('A')), findsNothing);
      expect(cardB().rank, 2);
      await tester.enterText(find.byType(TextField), '학원B');
      await tester.pumpAndSettle();
      expect(cardB().rank, 2);
      await tester.enterText(find.byType(TextField), '없는학원');
      await tester.pumpAndSettle();
      expect(find.byType(AcademyCard), findsNothing);
      expect(find.textContaining('조건에 맞는 분석 결과가 없습니다'), findsOneWidget);
    },
  );

  testWidgets(
    'search includes unknown grades and registry with consistent filters',
    (tester) async {
      tester.view.physicalSize = const Size(1100, 1800);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final data = EduTreeData(
        meta: Meta.fromJson({'mode': 'live'}),
        regions: [],
        tracks: [],
        academies: [
          academy('ranked', 80, true),
          Academy.fromJson({
            'id': 'unknown',
            'name': '미확인학원',
            'score': {
              'total': 50,
              'reputation': 50,
              'momentum': 50,
              'sampleSize': 0,
              'confidence': 'low',
              'isRanked': false,
            },
            'regionId': 'daechi',
            'subjects': ['math'],
            'gradeBands': <String>[],
            'isVerified': true,
            'aliases': ['공통별칭'],
          }),
        ],
      );
      RegistryEntry entry(String id, List<String> bands, bool verified) =>
          RegistryEntry.fromJson({
            'id': id,
            'name': id,
            'regionId': 'daechi',
            'subjects': ['math'],
            'gradeBands': bands,
            'isVerified': verified,
            'aliases': ['공통별칭'],
            'address': '테스트로 123',
          });
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            dataProvider.overrideWith((ref) async => data),
            registryProvider.overrideWith(
              (ref) async => [
                entry('registered', ['elem_low'], true),
                entry('unknownListed', [], true),
                entry('unverified', [], false),
                entry('highOnly', ['high'], true),
              ],
            ),
          ],
          child: MaterialApp(
            theme: buildTheme(dark: false),
            home: const Scaffold(body: RankingPage()),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.textContaining('총 5곳'), findsOneWidget);
      await tester.enterText(find.byType(TextField), '공통별칭');
      await tester.pumpAndSettle();
      expect(find.textContaining('총 4곳'), findsOneWidget);
      expect(find.byKey(const ValueKey('unknown')), findsOneWidget);
      expect(find.byKey(const ValueKey('unknownListed')), findsOneWidget);
      expect(find.byKey(const ValueKey('registered')), findsOneWidget);
      expect(find.byKey(const ValueKey('highOnly')), findsNothing);
      expect(find.byType(AcademyCard), findsNothing);
      expect(find.textContaining('조건에 맞는 분석 결과가 없습니다'), findsNothing);
      await tester.tap(find.text('공시 확인'));
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('unverified')), findsNothing);
      expect(find.textContaining('총 3곳'), findsOneWidget);
      await tester.enterText(find.byType(TextField), '테스트로');
      await tester.pumpAndSettle();
      expect(find.textContaining('총 2곳'), findsOneWidget);
      expect(find.byKey(const ValueKey('registered')), findsOneWidget);
      expect(find.byKey(const ValueKey('unknownListed')), findsOneWidget);
    },
  );

  testWidgets('registry loading and failure are not reported as no academies', (
    tester,
  ) async {
    final pending = Completer<List<RegistryEntry>>();
    var attempts = 0;
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          dataProvider.overrideWith(
            (ref) async => EduTreeData(
              meta: Meta.fromJson({'mode': 'live'}),
              regions: [],
              tracks: [],
              academies: [],
            ),
          ),
          registryProvider.overrideWith((ref) {
            attempts++;
            return attempts == 1 ? pending.future : Future.value([]);
          }),
        ],
        child: MaterialApp(
          theme: buildTheme(dark: false),
          home: const Scaffold(body: RankingPage()),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('등록부 학원을 불러오는 중입니다.'), findsOneWidget);
    expect(find.textContaining('조건에 맞는 분석 결과가 없습니다'), findsNothing);
    pending.completeError(StateError('offline'));
    await tester.pumpAndSettle();
    expect(find.textContaining('조건에 맞는 분석 결과가 없습니다'), findsNothing);
    await tester.tap(find.text('등록부를 불러오지 못했습니다. 다시 시도'));
    await tester.pumpAndSettle();
    expect(attempts, 2);
    expect(find.textContaining('조건에 맞는 분석 결과가 없습니다'), findsOneWidget);
  });
}
