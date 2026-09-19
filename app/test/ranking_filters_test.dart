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
}
