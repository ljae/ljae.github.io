import 'dart:async';

import 'package:edutree/core/selection_route.dart';
import 'package:edutree/core/router.dart' as app_router;
import 'package:edutree/core/theme.dart';
import 'package:edutree/data/academy_detail.dart';
import 'package:edutree/data/models.dart';
import 'package:edutree/data/repository.dart';
import 'package:edutree/features/academy/academy_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

EduTreeData emptyData() => EduTreeData(
  meta: Meta.fromJson({'mode': 'live', 'generatedAt': '2026-10-17T00:00:00Z'}),
  regions: const [],
  tracks: const [],
  academies: const [],
);

RegistryEntry listed() => RegistryEntry.fromJson({
  'id': '3000046567',
  'name': '한선영어학원',
  'regionId': 'banpo',
  'subjects': ['english'],
  'address': '서울특별시 서초구 고무래로10길 27',
  'capacity': 644,
  'registrationStatus': '개원',
  'isVerified': true,
  'registrationIds': ['99'],
  'gradeBands': ['high'],
});

void main() {
  testWidgets('detail retry recovers failed shared data loading', (
    tester,
  ) async {
    var attempts = 0;
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          dataProvider.overrideWith((ref) async {
            if (++attempts == 1) throw StateError('temporary failure');
            return emptyData();
          }),
          registryProvider.overrideWith((ref) async => [listed()]),
        ],
        child: MaterialApp(
          home: Scaffold(body: AcademyPage(academyId: '3000046567')),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('다시 시도'), findsOneWidget);
    await tester.tap(find.text('다시 시도'));
    await tester.pumpAndSettle();
    expect(find.text('한선영어학원'), findsOneWidget);
    expect(attempts, 2);
  });
  testWidgets('production academy route restores explicit regional context', (
    tester,
  ) async {
    final container = ProviderContainer(
      overrides: [
        dataProvider.overrideWith((ref) async => emptyData()),
        registryProvider.overrideWith((ref) async => [listed()]),
      ],
    );
    addTearDown(container.dispose);
    app_router.router.go('/rank?region=daechi');
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(
          theme: buildTheme(dark: false),
          routerConfig: app_router.router,
        ),
      ),
    );
    await tester.pumpAndSettle();
    app_router.router.go(
      '/academy/3000046567?region=banpo&subject=english&band=middle',
    );
    await tester.pumpAndSettle();
    expect(
      app_router.router.routeInformationProvider.value.uri.path,
      '/academy/3000046567',
    );
    expect(find.text('한선영어학원'), findsOneWidget);
    expect(
      container.read(selectionProvider),
      const Selection(
        regionId: 'banpo',
        subject: 'english',
        gradeBand: 'middle',
      ),
    );
    expect(tester.takeException(), isNull);
  });
  test('URL filters and track identifiers preserve valid context', () {
    const initial = Selection();
    final explicit = selectionFromUri(
      Uri.parse('/rank?region=mokdong&subject=english&band=middle'),
      initial,
    );
    expect(
      explicit,
      const Selection(
        regionId: 'mokdong',
        subject: 'english',
        gradeBand: 'middle',
      ),
    );
    final track = selectionFromUri(
      Uri.parse('/tree?track=english_elem_high'),
      initial,
    );
    expect(track.subject, 'english');
    expect(track.gradeBand, 'elem_high');
    expect(
      selectionFromUri(Uri.parse('/rank?region=invalid&band=all'), explicit),
      explicit,
    );
  });

  test(
    'registry resolver waits, resolves aliases, and distinguishes a missing ID',
    () async {
      final waiting = Completer<List<RegistryEntry>>();
      final container = ProviderContainer(
        overrides: [
          dataProvider.overrideWith((ref) async => emptyData()),
          registryProvider.overrideWith((ref) => waiting.future),
        ],
      );
      addTearDown(container.dispose);
      final future = container.read(academyDetailProvider('3000046567').future);
      await Future<void>.delayed(Duration.zero);
      expect(
        container.read(academyDetailProvider('3000046567')).isLoading,
        true,
      );
      waiting.complete([listed()]);
      final detail = await future;
      expect(detail!.registry!.id, '3000046567');
      expect(detail.academy, isNull);
      expect(
        (await container.read(academyDetailProvider('99').future))!.id,
        detail.id,
      );
      expect(
        await container.read(academyDetailProvider('missing').future),
        isNull,
      );
    },
  );

  for (final width in [320.0, 390.0, 768.0, 1440.0]) {
    for (final dark in [false, true]) {
      testWidgets('registry facts remain usable at $width dark=$dark', (
        tester,
      ) async {
        tester.view.physicalSize = Size(width, 1100);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.reset);
        final container = ProviderContainer(
          overrides: [
            dataProvider.overrideWith((ref) async => emptyData()),
            registryProvider.overrideWith((ref) async => [listed()]),
          ],
        );
        addTearDown(container.dispose);
        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp(
              theme: buildTheme(dark: dark),
              home: const Scaffold(body: AcademyPage(academyId: '3000046567')),
            ),
          ),
        );
        await tester.pumpAndSettle();
        expect(find.text('한선영어학원'), findsOneWidget);
        expect(find.text('대상 학년: 미확인'), findsOneWidget);
        expect(find.text('학원을 찾을 수 없습니다'), findsNothing);
        expect(find.textContaining('트리스코어'), findsNothing);
        expect(tester.takeException(), isNull);
      });
    }
  }

  testWidgets(
    'explicit conditions and browser back restore selection before results',
    (tester) async {
      final router = GoRouter(
        initialLocation: '/rank?region=mokdong&subject=english&band=middle',
        routes: [
          GoRoute(
            path: '/rank',
            builder: (_, state) => SelectionRoute(
              uri: state.uri,
              child: Consumer(
                builder: (_, ref, _) =>
                    Text(ref.watch(selectionProvider).regionId),
              ),
            ),
          ),
        ],
      );
      addTearDown(router.dispose);
      final container = ProviderContainer();
      addTearDown(container.dispose);
      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp.router(routerConfig: router),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('mokdong'), findsOneWidget);
      router.go('/rank?region=banpo&subject=math&band=high');
      await tester.pumpAndSettle();
      expect(container.read(selectionProvider).regionId, 'banpo');
      router.go('/rank?region=mokdong&subject=english&band=middle');
      await tester.pumpAndSettle();
      expect(container.read(selectionProvider).gradeBand, 'middle');
      container.read(selectionProvider.notifier).setRegion('jamsil');
      await tester.pumpAndSettle();
      expect(
        router.routeInformationProvider.value.uri.queryParameters['region'],
        'jamsil',
      );
    },
  );
}
