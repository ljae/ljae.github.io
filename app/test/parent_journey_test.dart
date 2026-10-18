import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:edutree/core/env.dart';
import 'package:edutree/core/theme.dart';
import 'package:edutree/data/browser_store.dart' as store;
import 'package:edutree/data/academy_detail.dart';
import 'package:edutree/data/models.dart';
import 'package:edutree/data/parent_comparison.dart';
import 'package:edutree/data/parent_decision.dart';
import 'package:edutree/data/repository.dart';
import 'package:edutree/data/riding_plan.dart';
import 'package:edutree/data/source_notes.dart';
import 'package:edutree/widgets/parent_journey.dart';
import 'package:edutree/widgets/riding_card.dart';
import 'parent_comparison_test.dart' as fixture;

void main() {
  setUp(() {
    store.writePublic(RidingPlans.storageKey, '{}');
    store.writePublic('parent.concern.v2', '');
  });
  tearDown(() {
    store.writePublic(RidingPlans.storageKey, '{}');
    store.writePublic('parent.concern.v2', '');
  });

  test(
    'travel observations restore by academy and class, never as shared link data',
    () {
      final c = ProviderContainer();
      const p = RidingPlan(
        mode: 'guardian',
        days: 3,
        guardianMinutes: 60,
        oneWayMinutes: 15,
        finish: '18:30',
        fit: 'possible',
        updatedAt: '2026-10-18',
      );
      expect(
        c.read(ridingPlansProvider.notifier).save('123/math/elem_low', p),
        isTrue,
      );
      expect(
        c.read(ridingPlansProvider)['123/math/elem_low']!.weeklyGuardianMinutes,
        180,
      );
      c.read(parentConcernProvider.notifier).choose('riding');
      c.dispose();
      final restored = ProviderContainer();
      addTearDown(restored.dispose);
      expect(restored.read(parentConcernProvider), 'riding');
      expect(
        restored.read(ridingPlansProvider)['123/math/elem_low']!.finish,
        '18:30',
      );
      for (final key in [
        '124/math/elem_low',
        '123/english/elem_low',
        '123/math/high',
      ]) {
        expect(restored.read(ridingPlansProvider)[key], isNull);
      }
      expect(parseCompareIds('123,124'), ['123', '124']);
      expect(ridingInquiry(p), contains('하원 18:30'));
      expect(
        restored.read(ridingPlansProvider.notifier).remove('123/math/elem_low'),
        isTrue,
      );
      expect(jsonDecode(store.readPublic(RidingPlans.storageKey)!), isEmpty);
    },
  );

  test(
    'unknown travel time stays unknown; explicit zero and guardian time are distinct',
    () {
      expect(
        const RidingPlan(
          days: 3,
          oneWayMinutes: 15,
          updatedAt: '2026-10-18',
        ).weeklyGuardianMinutes,
        isNull,
      );
      expect(
        const RidingPlan(
          guardianMinutes: 60,
          updatedAt: '2026-10-18',
        ).weeklyGuardianMinutes,
        isNull,
      );
      expect(
        const RidingPlan(
          days: 3,
          guardianMinutes: 0,
          updatedAt: '2026-10-18',
        ).weeklyGuardianMinutes,
        0,
      );
      expect(
        const RidingPlan(
          days: 3,
          guardianMinutes: 40,
          oneWayMinutes: 90,
          updatedAt: '2026-10-18',
        ).weeklyGuardianMinutes,
        120,
      );
      final c = ProviderContainer();
      addTearDown(c.dispose);
      expect(
        () => c
            .read(ridingPlansProvider.notifier)
            .save(
              '123/math/elem_low',
              const RidingPlan(days: 8, updatedAt: '2026-10-18'),
            ),
        throwsArgumentError,
      );
      expect(
        () => c
            .read(ridingPlansProvider.notifier)
            .save(
              '123/math/elem_low',
              const RidingPlan(finish: '25:00', updatedAt: '2026-10-18'),
            ),
        throwsArgumentError,
      );
    },
  );

  test('corrupt local records cannot become travel facts', () {
    final valid = const RidingPlan(days: 2, updatedAt: '2026-10-18').toJson();
    store.writePublic(
      RidingPlans.storageKey,
      jsonEncode({
        '123/math/elem_low': valid,
        '123/math/high': {...valid, 'guardianMinutes': '60'},
        '124/math/elem_low': {...valid, 'mode': 'officially_verified_shuttle'},
        'not-a-public-id/math/elem_low': valid,
      }),
    );
    final c = ProviderContainer();
    addTearDown(c.dispose);
    expect(c.read(ridingPlansProvider).keys, ['123/math/elem_low']);
  });

  test(
    'riding prioritizes transport sources without claiming current shuttle availability',
    () {
      expect(orderedComparisonCriteria('riding').first.id, 'riding');
      final criterion = orderedComparisonCriteria('riding').first;
      final d = fixture.academy('1', [
        fixture.evidence('shuttle', '셔틀 정류장에서 내려서 걸어갔어요.'),
        fixture.evidence('generic', '숙제를 마치고 귀가했다.'),
        fixture.evidence('other-grade', '셔틀로 이동했어요.', band: 'high'),
        fixture.evidence('brand', '셔틀 운행', branch: 'brand'),
        fixture.evidence('money', '셔틀 비용은 5만원'),
      ]);
      final rows = comparisonExcerpts(
        d,
        criterion,
        subject: 'math',
        gradeBand: 'elem_low',
      );
      expect(rows.map((r) => r.url), ['https://example.com/shuttle']);
      expect(rows.single.dateLabel, contains('수강 시점 미확인'));
      expect(d.academy!.score.total, 80);
    },
  );

  testWidgets(
    'selected concern changes the actual introduction evidence and inquiry',
    (tester) async {
      final c = ProviderContainer(
        overrides: [sourceNotesProvider.overrideWith((_) async => [])],
      );
      addTearDown(c.dispose);
      final d = fixture.academy('1', [
        fixture.evidence('homework', '숙제는 집에서 삼십 분 동안 했어요.'),
        fixture.evidence('feedback', '질문 시간은 수업 끝에 따로 있었어요.'),
      ]);
      c.read(parentConcernProvider.notifier).choose('homework');
      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: c,
          child: MaterialApp(
            home: Scaffold(
              body: SingleChildScrollView(
                child: Column(
                  children: [
                    const ParentConcernBar(),
                    ConcernPreview(detail: d),
                  ],
                ),
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('“숙제는 집에서 삼십 분 동안 했어요.”'), findsOneWidget);
      expect(find.text('“질문 시간은 수업 끝에 따로 있었어요.”'), findsNothing);
      await tester.tap(find.widgetWithText(ChoiceChip, '질문·피드백'));
      await tester.pumpAndSettle();
      expect(find.text('“숙제는 집에서 삼십 분 동안 했어요.”'), findsNothing);
      expect(find.text('“질문 시간은 수업 끝에 따로 있었어요.”'), findsOneWidget);
      expect(
        find.text('물어볼 질문  ${concernQuestions['questions']}'),
        findsOneWidget,
      );
      c.read(selectionProvider.notifier).setGradeBand('high');
      await tester.pumpAndSettle();
      expect(find.text('“질문 시간은 수업 끝에 따로 있었어요.”'), findsNothing);
      expect(find.textContaining('자료가 아직 부족해요'), findsOneWidget);
    },
    skip: !Env.parentOpeningEnabled,
  );

  for (final width in [320.0, 768.0]) {
    testWidgets(
      'registry travel notes and editor remain usable at $width with large text',
      (tester) async {
        tester.view.physicalSize = Size(width, 1400);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.reset);
        final c = ProviderContainer();
        addTearDown(c.dispose);
        final d = AcademyDetail.listed(
          RegistryEntry.fromJson({
            'id': '123',
            'name': '등록부 학원',
            'subjects': ['math'],
          }),
        );
        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: c,
            child: MaterialApp(
              theme: buildTheme(dark: width == 768),
              builder: (context, child) => MediaQuery(
                data: MediaQuery.of(
                  context,
                ).copyWith(textScaler: const TextScaler.linear(2)),
                child: child!,
              ),
              home: Scaffold(
                body: SingleChildScrollView(child: RidingCard(detail: d)),
              ),
            ),
          ),
        );
        await tester.pumpAndSettle();
        expect(find.text('주소 미확인'), findsOneWidget);
        expect(find.text('지도에서 동선 확인'), findsNothing);
        await tester.ensureVisible(find.text('라이딩 메모 작성'));
        await tester.tap(find.text('라이딩 메모 작성'));
        await tester.pumpAndSettle();
        await tester.ensureVisible(
          find.widgetWithText(TextFormField, '하루 보호자 이동·대기 시간 · 선택'),
        );
        await tester.enterText(
          find.widgetWithText(TextFormField, '하루 보호자 이동·대기 시간 · 선택'),
          '45',
        );
        await tester.ensureVisible(find.text('내 기기에 저장'));
        await tester.tap(find.text('내 기기에 저장'));
        await tester.pumpAndSettle();
        expect(
          c.read(ridingPlansProvider)['123/math/elem_low']!.guardianMinutes,
          45,
        );
        expect(
          c
              .read(ridingPlansProvider)['123/math/elem_low']!
              .weeklyGuardianMinutes,
          isNull,
        );
        c.read(selectionProvider.notifier).setGradeBand('high');
        await tester.pumpAndSettle();
        expect(find.text('라이딩 메모 수정'), findsNothing);
        expect(find.text('라이딩 메모 작성'), findsOneWidget);
        expect(tester.takeException(), isNull);
      },
    );
  }
}
