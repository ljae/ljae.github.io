import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:edutree/widgets/ranking_data_notice.dart';

void main() {
  testWidgets('old data is visibly delayed and is not a child-fit verdict', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: RankingDataNotice(
            generatedAt: '2026-10-19T23:47:08Z',
            now: DateTime.utc(2026, 11, 9),
          ),
        ),
      ),
    );
    expect(find.textContaining('갱신 지연'), findsOneWidget);
    expect(find.textContaining('해당 지점에 확인'), findsOneWidget);
    expect(find.textContaining('2~3곳'), findsOneWidget);
  });

  testWidgets('unknown generation time asks for confirmation', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(body: RankingDataNotice(generatedAt: '')),
      ),
    );
    expect(find.textContaining('자료 생성일 확인 필요'), findsOneWidget);
  });
}
