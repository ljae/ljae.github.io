import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:edutree/core/theme.dart';
import 'package:edutree/data/models.dart';
import 'package:edutree/data/repository.dart';
import 'package:edutree/features/home/home_page.dart';
import 'package:edutree/features/ranking/ranking_page.dart';
import 'package:edutree/widgets/app_shell.dart';
import 'package:edutree/widgets/subject_bar.dart';

void main() {
  dynamic read(String name) =>
      jsonDecode(File('assets/data/$name.json').readAsStringSync());
  final data = EduTreeData(
    meta: Meta.fromJson(read('meta') as Map<String, dynamic>),
    regions: (read('regions') as List)
        .map((j) => Region.fromJson(j as Map<String, dynamic>))
        .toList(),
    tracks: (read('techtree')['tracks'] as List)
        .map((j) => Track.fromJson(j as Map<String, dynamic>))
        .toList(),
    academies: (read('academies') as List)
        .map((j) => Academy.fromJson(j as Map<String, dynamic>))
        .toList(),
  );
  for (final dark in [false, true]) {
    for (final width in [320.0, 375.0, 768.0, 1440.0]) {
      testWidgets(
        'home and explore preserve selection without overflow at $width dark=$dark',
        (tester) async {
          tester.view.physicalSize = Size(width, 1000);
          tester.view.devicePixelRatio = 1;
          addTearDown(tester.view.reset);
          final router = GoRouter(
            routes: [
              ShellRoute(
                builder: (_, _, child) => AppShell(child: child),
                routes: [
                  GoRoute(path: '/', builder: (_, _) => const HomePage()),
                  GoRoute(
                    path: '/rank',
                    builder: (_, _) => const RankingPage(),
                  ),
                ],
              ),
            ],
          );
          addTearDown(router.dispose);
          final container = ProviderContainer(
            overrides: [
              dataProvider.overrideWith((ref) async => data),
              registryProvider.overrideWith((ref) async => []),
            ],
          );
          addTearDown(container.dispose);
          await tester.pumpWidget(
            UncontrolledProviderScope(
              container: container,
              child: MaterialApp.router(
                theme: buildTheme(dark: dark),
                routerConfig: router,
              ),
            ),
          );
          await tester.pumpAndSettle();
          expect(tester.takeException(), isNull);
          expect(find.textContaining('원출처로 비교'), findsNothing);
          container.read(selectionProvider.notifier).setSubject('english');
          await tester.pumpAndSettle();
          router.go('/rank');
          await tester.pumpAndSettle();
          expect(
            tester.widget<SubjectBar>(find.byType(SubjectBar)).selected,
            'english',
          );
          expect(find.textContaining('원출처로 비교'), findsNothing);
          expect(tester.takeException(), isNull);
          await tester.drag(
            find.byType(CustomScrollView),
            const Offset(0, -400),
          );
          await tester.pumpAndSettle();
          expect(tester.takeException(), isNull);
        },
      );
    }
  }
}
