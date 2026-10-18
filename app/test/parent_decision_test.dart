import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:edutree/core/env.dart';
import 'package:edutree/core/theme.dart';
import 'package:edutree/data/academy_detail.dart';
import 'package:edutree/data/contact_view_model.dart';
import 'package:edutree/data/models.dart';
import 'package:edutree/data/parent_decision.dart';
import 'package:edutree/data/parent_voice.dart';
import 'package:edutree/features/home/parent_opening.dart';
import 'package:edutree/features/feedback/parent_voice_page.dart';
import 'package:edutree/features/compare/compare_page.dart';
import 'package:edutree/features/academy/contact.dart';
import 'package:edutree/data/repository.dart';

void main() {
  test('unsafe contacts are rejected without altering a branch identity', () {
    for (final s in [
      'javascript:alert(1)',
      'data:text/plain,hi',
      'https://u:p@example.com',
      'https://',
      'https://exa mple.com',
      'https://good.com\\@evil.com',
    ]) {
      expect(safeContactUrl(s), isNull, reason: s);
    }
    expect(safeContactUrl('https://example.com/a')?.host, 'example.com');
    for (final s in [
      '전화 02-1234-5678',
      '00000000',
      '02-1234-5678;123',
      '12345',
    ]) {
      expect(safePhoneDigits(s), isNull, reason: s);
    }
    expect(safePhoneDigits('02-1234-0000'), '0212340000');
    expect(safePhoneDigits('1588-1234'), '15881234');
    expect(safePhoneDigits('+82 (2) 1234-5678'), '+82212345678');
    final r = RegistryEntry.fromJson({
      'id': '123',
      'name': '등록부 전용',
      'subjects': ['math'],
    });
    final c = ContactViewModel.fromDetail(AcademyDetail.listed(r));
    expect(c.academyId, '123');
    expect(c.hasContact, isFalse);
    const conflicting = ContactViewModel(
      academyId: '123',
      branchName: '같은 지점',
      phone: '02-1234-5678',
      phoneDisputed: true,
      officialUrl: 'https://example.com',
    );
    expect(conflicting.phone, isNull);
    expect(conflicting.officialUrl, 'https://example.com');
  });
  test(
    'compare IDs are bounded, distinct, and concern never becomes a score',
    () {
      expect(parseCompareIds('1,1,foo,2,3,4'), ['1', '2', '3']);
      final container = ProviderContainer();
      addTearDown(container.dispose);
      final notifier = container.read(compareProvider.notifier);
      notifier.clear();
      for (final id in ['1', '2', '3']) {
        expect(notifier.toggle(id), isTrue);
      }
      expect(notifier.toggle('4'), isFalse);
      container.read(parentConcernProvider.notifier).choose('homework');
      expect(
        inquiryQuestions(concern: container.read(parentConcernProvider))[1],
        contains('숙제'),
      );
      expect(inquiryQuestions().join(), isNot(matches(r'\d+만\s*원')));
      notifier.clear();
      container.read(parentConcernProvider.notifier).choose(null);
    },
  );
  test(
    'failed feedback retries preserve request identity; accepted receipt is required',
    () async {
      final requests = <Map<String, dynamic>>[];
      var fail = true;
      final service = ParentVoiceService((action, body) async {
        requests.add(Map.from(body));
        if (fail) {
          fail = false;
          throw const VoiceFailure('RETRY_LATER', '실패', retryable: true);
        }
        return {
          'receiptId': '00000000-0000-0000-0000-000000000001',
          'status': 'received',
        };
      });
      await expectLater(
        service.submit('feature_request', '비교하고 싶어요', pageType: 'compare'),
        throwsA(isA<VoiceFailure>()),
      );
      expect(service.lastCode, isNull);
      await service.submit('feature_request', '비교하고 싶어요', pageType: 'compare');
      expect(requests[0], requests[1]);
      expect(validReceipt(service.lastCode!), isTrue);
      final invalid = ParentVoiceService((_, _) async => {});
      await expectLater(
        invalid.submit('other', ''),
        throwsA(isA<VoiceFailure>()),
      );
      expect(invalid.lastCode, service.lastCode);
    },
  );
  for (final width in [320.0, 375.0, 768.0, 1440.0]) {
    for (final dark in [false, true]) {
      testWidgets('opening is usable at $width dark=$dark with 200% text', (
        tester,
      ) async {
        tester.view.physicalSize = Size(width, 1200);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.reset);
        final container = ProviderContainer();
        addTearDown(container.dispose);
        var explored = false;
        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp(
              theme: buildTheme(dark: dark),
              home: Scaffold(
                body: MediaQuery(
                  data: MediaQueryData(
                    size: Size(width, 1200),
                    textScaler: const TextScaler.linear(2),
                    disableAnimations: true,
                  ),
                  child: SingleChildScrollView(
                    child: ParentOpening(
                      onExplore: () => explored = true,
                      onSearch: () {},
                    ),
                  ),
                ),
              ),
            ),
          ),
        );
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
        await tester.ensureVisible(find.text('학원 살펴보기'));
        await tester.tap(find.text('학원 살펴보기'));
        expect(explored, isTrue);
        await tester.ensureVisible(find.text(parentConcerns['homework']!));
        await tester.tap(find.text(parentConcerns['homework']!));
        await tester.pump();
        expect(container.read(parentConcernProvider), 'homework');
        expect(find.text(concernQuestions['homework']!), findsOneWidget);
        expect(tester.takeException(), isNull);
        container.read(parentConcernProvider.notifier).choose(null);
      });
    }
  }

  testWidgets('unconfigured voice never claims acceptance', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          parentVoiceProvider.overrideWithValue(ParentVoiceService(null)),
          parentImprovementsProvider.overrideWith((_) async => []),
        ],
        child: const MaterialApp(
          home: Scaffold(body: ParentVoicePanel(pageType: 'compare')),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.textContaining('현재 의견 접수를 준비 중'), findsOneWidget);
    expect(find.text('의견을 접수했습니다.'), findsNothing);
    expect(
      tester
          .widget<FilledButton>(
            find.widgetWithText(FilledButton, '비공개로 의견 보내기'),
          )
          .onPressed,
      isNull,
    );
  });

  testWidgets(
    'voice form retains a failed draft and accepts only a server receipt',
    (tester) async {
      var fail = true;
      final service = ParentVoiceService((_, body) async {
        if (fail) {
          fail = false;
          throw const VoiceFailure(
            'RETRY_LATER',
            '연결 실패 · 다시 시도해주세요.',
            retryable: true,
          );
        }
        return {
          'receiptId': '00000000-0000-0000-0000-000000000009',
          'status': 'received',
        };
      });
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            parentVoiceProvider.overrideWithValue(service),
            parentImprovementsProvider.overrideWith((_) async => []),
          ],
          child: const MaterialApp(
            home: Scaffold(body: ParentVoicePanel(pageType: 'compare')),
          ),
        ),
      );
      await tester.pumpAndSettle();
      final category = find.byType(DropdownButtonFormField<String>).at(1);
      await tester.ensureVisible(category);
      await tester.tap(category);
      await tester.pumpAndSettle();
      await tester.tap(find.text('이런 기능이 필요해요').last);
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField).first, '두 후보를 비교하고 싶어요.');
      final button = find.widgetWithText(FilledButton, '비공개로 의견 보내기');
      await tester.ensureVisible(button);
      await tester.tap(button);
      await tester.pumpAndSettle();
      expect(find.text('의견을 접수했습니다.'), findsNothing);
      expect(find.text('연결 실패 · 다시 시도해주세요.'), findsOneWidget);
      expect(
        tester.widget<TextField>(find.byType(TextField).first).controller!.text,
        '두 후보를 비교하고 싶어요.',
      );
      await tester.ensureVisible(button);
      await tester.tap(button);
      await tester.pumpAndSettle();
      expect(find.text('의견을 접수했습니다.'), findsOneWidget);
      expect(validReceipt(service.lastCode!), isTrue);
    },
  );
  testWidgets('contact card exposes no dead telephone button', (tester) async {
    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(
          home: Scaffold(
            body: ContactCard(
              contact: ContactViewModel(academyId: '123', branchName: '등록부 학원'),
            ),
          ),
        ),
      ),
    );
    expect(find.text('전화하기'), findsNothing);
    expect(find.textContaining('공개된 연락처를 아직'), findsOneWidget);
  });
  testWidgets(
    'mobile comparison groups candidates under each criterion',
    (tester) async {
      dynamic read(String n) =>
          jsonDecode(File('assets/data/$n.json').readAsStringSync());
      final rows = (read('academies') as List)
          .take(2)
          .map((r) => Academy.fromJson(Map<String, dynamic>.from(r as Map)))
          .toList();
      final data = EduTreeData(
        meta: Meta.fromJson(Map<String, dynamic>.from(read('meta') as Map)),
        regions: [],
        tracks: [],
        academies: rows,
      );
      tester.view.physicalSize = const Size(320, 1000);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            dataProvider.overrideWith((_) async => data),
            registryProvider.overrideWith((_) async => []),
          ],
          child: MaterialApp(
            theme: buildTheme(dark: false),
            home: Scaffold(
              body: ComparePage(ids: rows.map((a) => a.id).join(',')),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(find.text('지점과 위치'), findsOneWidget);
      await tester.drag(find.byType(ListView).first, const Offset(0, -500));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    },
    skip: !Env.parentCompareEnabled,
  );
}
