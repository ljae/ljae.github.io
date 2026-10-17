import 'dart:async';

import 'package:edutree/core/theme.dart';
import 'package:edutree/data/admin.dart';
import 'package:edutree/data/growth.dart';
import 'package:edutree/features/admin/growth/growth_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class RecordingGrowthService extends GrowthService {
  int requests = 0;
  RecordingGrowthService() : super(null);
  @override
  Future<List<Map<String, dynamic>>> reports() async {
    requests++;
    return [];
  }
}

class AuthorizingAdminService extends AdminService {
  bool allowed = true;
  AuthorizingAdminService() : super(null);
  @override
  Future<bool> isAdmin() async => allowed;
}

void main() {
  test('account changes invalidate authorized report caches', () async {
    final changes = StreamController<String?>();
    final admin = AuthorizingAdminService();
    final service = RecordingGrowthService();
    final container = ProviderContainer(
      overrides: [
        growthAuthIdentityProvider.overrideWith((ref) async* {
          yield 'admin-id';
          yield* changes.stream;
        }),
        adminServiceProvider.overrideWithValue(admin),
        growthServiceProvider.overrideWithValue(service),
      ],
    );
    addTearDown(() async {
      container.dispose();
      await changes.close();
    });
    final subscription = container.listen(growthReportsProvider, (_, next) {});
    addTearDown(subscription.close);
    expect(await container.read(growthReportsProvider.future), isEmpty);
    expect(service.requests, 1);
    admin.allowed = false;
    changes.add('other-account');
    await Future<void>.delayed(Duration.zero);
    await expectLater(
      container.read(growthReportsProvider.future),
      throwsStateError,
    );
    expect(service.requests, 1);
  });
  test(
    'growth providers do not fetch before affirmative admin authorization',
    () async {
      final service = RecordingGrowthService();
      final container = ProviderContainer(
        overrides: [
          growthAccessProvider.overrideWith((ref) async => false),
          growthServiceProvider.overrideWithValue(service),
        ],
      );
      addTearDown(container.dispose);
      await expectLater(
        container.read(growthReportsProvider.future),
        throwsStateError,
      );
      expect(service.requests, 0);
    },
  );

  for (final width in [320.0, 390.0, 1440.0]) {
    testWidgets(
      'growth overview shows nulls and incomplete coverage at $width',
      (tester) async {
        tester.view.physicalSize = Size(width, 1000);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.reset);
        final report = <String, dynamic>{
          'property': 'sc-domain:example.org',
          'asOf': '2026-10-17',
          'totals': {'clicks': 5, 'impressions': 188, 'ctr': 5 / 188},
          'quality': {
            'queryClickCoverage': 0,
            'pageRowsTruncated': true,
            'warnings': ['PAGE_ROW_LIMIT_REACHED'],
          },
          'daily': [
            {'date': '2026-09-17', 'clicks': 0, 'impressions': 0},
            {'date': '2026-09-19', 'clicks': 5, 'impressions': 188},
          ],
          'pages': [
            {
              'key': 'https://example.org/a/1.html',
              'clicks': 0,
              'impressions': 0,
              'position': null,
            },
          ],
          'queries': <Map<String, dynamic>>[],
          'findings': <Map<String, dynamic>>[],
          'pageCount': 1000,
          'evaluation': 'insufficient_evidence',
        };
        await tester.pumpWidget(
          MaterialApp(
            theme: buildTheme(dark: false),
            home: Scaffold(
              body: SingleChildScrollView(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: GrowthOverview(report: report),
                ),
              ),
            ),
          ),
        );
        await tester.pumpAndSettle();
        expect(find.text('2.66%'), findsOneWidget);
        expect(find.text('≥1000'), findsOneWidget);
        expect(find.textContaining('검색어 클릭 가시성: 0.0%'), findsOneWidget);
        expect(tester.takeException(), isNull);
      },
    );
  }
}
