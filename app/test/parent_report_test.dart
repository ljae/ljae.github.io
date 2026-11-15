import 'dart:convert';

import 'package:edutree/core/router.dart' as app_router;
import 'package:edutree/data/models.dart';
import 'package:edutree/data/parent_reports.dart';
import 'package:edutree/data/repository.dart';
import 'package:edutree/features/feedback/parent_report_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

/// 학부모 제보 — 고르기만 하는 익명 폼.
///
/// 굳히는 것: 필수 항목 없이는 못 보낸다 · 보내는 값에 적은 글이 없다 ·
/// 서버가 받았다고 답해야 접수 기록이 뜬다 · 백엔드가 없으면 그렇게 말한다.

/// 서버 check 제약(supabase/18_parent_reports.sql)과 같은 값.
const _allowed = <String, Set<Object>>{
  'p_grade_band': {'elem_low', 'elem_high', 'middle', 'high'},
  'p_relation': {'current', 'past', 'test_only', 'consulted'},
  'p_subject': {'math', 'english', 'korean', 'science', 'arts', 'etc'},
  'p_level_test': {'passed', 'failed', 'waitlisted', 'no_test', 'not_taken'},
  'p_sessions_per_week': {1, 2, 3, 4, 5, 6, 7},
  'p_homework': {'light', 'medium', 'heavy'},
};

class _Store {
  final bool works;
  final values = <String, String>{};
  _Store({this.works = true});
  String? read(String key) => values[key];
  bool write(String key, String value) {
    if (works) values[key] = value;
    return works;
  }
}

ParentReportService _service(ReportRequest? request, {_Store? store}) {
  final s = store ?? _Store();
  return ParentReportService(request, read: s.read, write: s.write);
}

Widget _form(ParentReportService service) => ProviderScope(
  overrides: [parentReportsProvider.overrideWithValue(service)],
  child: const MaterialApp(
    home: Scaffold(
      body: SingleChildScrollView(
        child: ParentReportForm(academyId: '1000035161', academyName: '시험학원'),
      ),
    ),
  ),
);

bool _submitEnabled(WidgetTester tester) => tester
    .widget<FilledButton>(find.byKey(const ValueKey('tell-submit')))
    .enabled;

Future<void> _tapSubmit(WidgetTester tester) async {
  await tester.ensureVisible(find.byKey(const ValueKey('tell-submit')));
  await tester.tap(find.byKey(const ValueKey('tell-submit')));
  await tester.pumpAndSettle();
}

void main() {
  test('sha256 은 표준 시험값과 같다', () {
    expect(
      sha256Hex(const []),
      'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    );
    expect(
      sha256Hex(utf8.encode('abc')),
      'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad',
    );
    // 두 블록에 걸치는 입력(56바이트) — 덧붙임 경계.
    expect(
      sha256Hex(
        utf8.encode('abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq'),
      ),
      '248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1',
    );
    expect(
      sha256Hex(List<int>.filled(1000, 0x61)),
      '41edece42d63e8d9bf515a9ba6932e1c20cbc9f5a5d134645adb5db1b9737ea3',
    );
  });

  test('선택지는 서버 제약과 같은 값이다', () {
    Set<Object> keys(List<(String, String)> o) => {for (final (k, _) in o) k};
    expect(keys(reportGradeBands), _allowed['p_grade_band']);
    expect(keys(reportRelations), _allowed['p_relation']);
    expect(keys(reportSubjects), _allowed['p_subject']);
    expect(keys(reportLevelTests), _allowed['p_level_test']);
    expect(keys(reportHomework), _allowed['p_homework']);
    expect(reportSessions.toSet(), _allowed['p_sessions_per_week']);
    // 과목·학년대 순서와 이름은 앱의 다른 화면과 같다.
    expect([for (final (k, _) in reportSubjects) k], subjectOrder);
    for (final (k, label) in reportSubjects) {
      expect(label, subjectNames[k]);
    }
    for (final (k, label) in reportGradeBands) {
      expect(label, gradeBandNames[k]);
    }
  });

  test('필수 항목이 없으면 서버를 부르지 않는다', () async {
    var calls = 0;
    final service = _service((_) async {
      calls++;
      return 'ok';
    });
    for (final report in const [
      ParentReport(academyId: 'A1'),
      ParentReport(academyId: 'A1', gradeBand: 'middle'),
      ParentReport(academyId: 'A1', relation: 'current'),
      ParentReport(academyId: 'A1', gradeBand: '중2', relation: 'current'),
      ParentReport(
        academyId: 'A1',
        gradeBand: 'middle',
        relation: 'current',
        sessionsPerWeek: 9,
      ),
      ParentReport(academyId: '', gradeBand: 'middle', relation: 'current'),
    ]) {
      await expectLater(
        service.submit(report),
        throwsA(
          isA<ReportFailure>().having((e) => e.code, 'code', 'INVALID_INPUT'),
        ),
      );
    }
    expect(calls, 0);
  });

  test('백엔드가 없으면 성공이 아니라 실패다', () async {
    final service = _service(null);
    expect(service.enabled, isFalse);
    await expectLater(
      service.submit(
        const ParentReport(
          academyId: 'A1',
          gradeBand: 'middle',
          relation: 'current',
        ),
      ),
      throwsA(
        isA<ReportFailure>().having((e) => e.code, 'code', 'UNAVAILABLE'),
      ),
    );
  });

  test('실패한 요청을 다시 보내면 같은 요청 번호를 쓴다', () async {
    final ids = <Object?>[];
    var fail = true;
    final service = _service((p) async {
      ids.add(p['p_request_id']);
      if (fail) throw StateError('network');
      return 'ok';
    });
    const report = ParentReport(
      academyId: 'A1',
      gradeBand: 'middle',
      relation: 'past',
    );
    await expectLater(service.submit(report), throwsA(isA<ReportFailure>()));
    fail = false;
    expect(await service.submit(report), ReportOutcome.ok);
    expect(ids[0], ids[1]);
    // 접수된 뒤의 새 제출은 새 요청이다.
    expect(await service.submit(report), ReportOutcome.ok);
    expect(ids[2], isNot(ids[1]));
  });

  test('모르는 서버 응답을 접수로 읽지 않는다', () async {
    for (final answer in <Object?>[null, '', 'OK', 'received', 1, <String>[]]) {
      final service = _service((_) async => answer);
      await expectLater(
        service.submit(
          const ParentReport(
            academyId: 'A1',
            gradeBand: 'high',
            relation: 'consulted',
          ),
        ),
        throwsA(
          isA<ReportFailure>().having(
            (e) => e.code,
            'code',
            'INVALID_RESPONSE',
          ),
        ),
      );
    }
  });

  test('기기 토큰은 저장소에 남고 서버에는 해시만 간다', () async {
    final store = _Store();
    final hashes = <Object?>[];
    final service = _service((p) async {
      hashes.add(p['p_device_hash']);
      return 'ok';
    }, store: store);
    for (final id in ['A1', 'A2']) {
      await service.submit(
        ParentReport(academyId: id, gradeBand: 'high', relation: 'current'),
      );
    }
    final token = store.values.values.single;
    expect(hashes[0], hashes[1]);
    expect(hashes[0], sha256Hex(utf8.encode(token)));
    expect(hashes[0], isNot(token));
    expect(service.spent, isFalse);
  });

  test('저장소를 못 쓰면 메모리 토큰으로 한 번만 받는다', () async {
    var calls = 0;
    final service = _service((p) async {
      calls++;
      expect(p['p_device_hash'], matches(RegExp(r'^[a-f0-9]{64}$')));
      return 'ok';
    }, store: _Store(works: false));
    const report = ParentReport(
      academyId: 'A1',
      gradeBand: 'elem_low',
      relation: 'test_only',
    );
    expect(await service.submit(report), ReportOutcome.ok);
    expect(service.spent, isTrue);
    await expectLater(
      service.submit(report),
      throwsA(
        isA<ReportFailure>().having((e) => e.code, 'code', 'STORAGE_REQUIRED'),
      ),
    );
    expect(calls, 1);
  });

  test('저장소를 못 써도 실패한 전송은 그 한 번을 쓰지 않는다', () async {
    var fail = true;
    final service = _service((_) async {
      if (fail) throw StateError('network');
      return 'ok';
    }, store: _Store(works: false));
    const report = ParentReport(
      academyId: 'A1',
      gradeBand: 'elem_low',
      relation: 'test_only',
    );
    await expectLater(service.submit(report), throwsA(isA<ReportFailure>()));
    expect(service.spent, isFalse);
    fail = false;
    expect(await service.submit(report), ReportOutcome.ok);
  });

  testWidgets('필수 둘을 고르기 전에는 보낼 수 없다', (tester) async {
    var calls = 0;
    await tester.pumpWidget(
      _form(
        _service((_) async {
          calls++;
          return 'ok';
        }),
      ),
    );
    expect(_submitEnabled(tester), isFalse);
    expect(find.textContaining('고르면 보낼 수 있습니다'), findsOneWidget);

    await tester.tap(find.text('중등'));
    await tester.pump();
    expect(_submitEnabled(tester), isFalse);

    await tester.tap(find.text('다니는 중'));
    await tester.pump();
    expect(_submitEnabled(tester), isTrue);

    // 고른 칸을 다시 누르면 비워지고, 다시 못 보낸다.
    await tester.tap(find.text('중등'));
    await tester.pump();
    expect(_submitEnabled(tester), isFalse);
    expect(calls, 0);
    expect(find.byKey(const ValueKey('tell-receipt')), findsNothing);
  });

  testWidgets('폼에는 적는 칸이 없고 동의 문구가 단추 위에 있다', (tester) async {
    await tester.pumpWidget(_form(_service((_) async => 'ok')));
    expect(find.byType(EditableText), findsNothing);
    expect(find.byType(TextField), findsNothing);

    final consent = find.byKey(const ValueKey('tell-consent'));
    final words = tester.widget<Text>(consent).data!;
    for (final part in ['익명', '이름·연락처는 받지 않', '학년대만', '합친 수', '랭킹 점수는 바꾸지 않']) {
      expect(words, contains(part));
    }
    expect(
      tester.getTopLeft(consent).dy,
      lessThan(tester.getTopLeft(find.byKey(const ValueKey('tell-submit'))).dy),
    );
    // 가운데 정렬이 아니다 — 동의 문구와 단추가 같은 왼쪽 선에 선다.
    expect(
      tester.getTopLeft(consent).dx,
      tester.getTopLeft(find.byKey(const ValueKey('tell-submit'))).dx,
    );
  });

  testWidgets('보내는 값은 고른 값뿐이고, 받았다는 답 뒤에 접수 기록이 뜬다', (tester) async {
    final sent = <Map<String, dynamic>>[];
    await tester.pumpWidget(
      _form(
        _service((p) async {
          sent.add(p);
          return 'ok';
        }),
      ),
    );
    for (final label in ['초4~초6', '다녔음', '수학', '대기', '3회', '많음']) {
      await tester.ensureVisible(find.text(label));
      await tester.tap(find.text(label));
      await tester.pump();
    }
    await _tapSubmit(tester);

    final p = sent.single;
    expect(p.keys.toSet(), {
      'p_request_id',
      'p_academy_key',
      'p_device_hash',
      ..._allowed.keys,
    });
    expect(p['p_academy_key'], '1000035161');
    expect(p['p_grade_band'], 'elem_high');
    expect(p['p_relation'], 'past');
    expect(p['p_subject'], 'math');
    expect(p['p_level_test'], 'waitlisted');
    expect(p['p_sessions_per_week'], 3);
    expect(p['p_homework'], 'heavy');
    expect(
      p['p_request_id'],
      matches(
        RegExp(
          r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
        ),
      ),
    );
    expect(p['p_device_hash'], matches(RegExp(r'^[a-f0-9]{64}$')));
    // 자유 서술이 들어갈 자리가 없다: 식별자 셋을 뺀 값은 전부 닫힌 목록 안.
    for (final e in _allowed.entries) {
      expect(e.value, contains(p[e.key]), reason: e.key);
    }
    // 학원 이름조차 보내지 않는다.
    expect(jsonEncode(p), isNot(contains('시험학원')));

    expect(find.byKey(const ValueKey('tell-receipt')), findsOneWidget);
    expect(find.text('접수했습니다'), findsOneWidget);
    expect(find.text('시험학원'), findsOneWidget);
    expect(find.text('주 3회'), findsOneWidget);
    expect(find.byKey(const ValueKey('tell-submit')), findsNothing);
  });

  testWidgets('고르지 않은 선택 항목은 보내지 않는다', (tester) async {
    final sent = <Map<String, dynamic>>[];
    await tester.pumpWidget(
      _form(
        _service((p) async {
          sent.add(p);
          return 'duplicate';
        }),
      ),
    );
    await tester.tap(find.text('고등'));
    await tester.tap(find.text('상담만'));
    await tester.pump();
    await _tapSubmit(tester);
    expect(sent.single.keys.toSet(), {
      'p_request_id',
      'p_academy_key',
      'p_device_hash',
      'p_grade_band',
      'p_relation',
    });
    // 같은 기기의 재제보는 접수이되, 고쳐 썼다고 말한다.
    expect(find.byKey(const ValueKey('tell-receipt')), findsOneWidget);
    expect(find.textContaining('새 답으로 바꿨습니다'), findsOneWidget);
  });

  testWidgets('백엔드가 없으면 그렇게 말하고 보내기를 끈다', (tester) async {
    await tester.pumpWidget(_form(_service(null)));
    expect(find.text(ParentReportForm.unavailable), findsOneWidget);
    await tester.tap(find.text('중등'));
    await tester.tap(find.text('다니는 중'));
    await tester.pump();
    expect(_submitEnabled(tester), isFalse);
    expect(find.byKey(const ValueKey('tell-receipt')), findsNothing);
    expect(find.text('접수했습니다'), findsNothing);
  });

  testWidgets('전송 실패는 접수가 아니다 — 고른 답은 남는다', (tester) async {
    var fail = true;
    await tester.pumpWidget(
      _form(
        _service((_) async {
          if (fail) throw StateError('network');
          return 'ok';
        }),
      ),
    );
    await tester.tap(find.text('중등'));
    await tester.tap(find.text('다니는 중'));
    await tester.pump();
    await _tapSubmit(tester);
    expect(find.byKey(const ValueKey('tell-receipt')), findsNothing);
    expect(find.textContaining('저장되지 않았습니다'), findsOneWidget);
    expect(_submitEnabled(tester), isTrue);

    fail = false;
    await _tapSubmit(tester);
    expect(find.byKey(const ValueKey('tell-receipt')), findsOneWidget);
  });

  testWidgets('하루 제한은 접수가 아니다', (tester) async {
    await tester.pumpWidget(_form(_service((_) async => 'limited')));
    await tester.tap(find.text('중등'));
    await tester.tap(find.text('다니는 중'));
    await tester.pump();
    await _tapSubmit(tester);
    expect(find.byKey(const ValueKey('tell-receipt')), findsNothing);
    expect(find.textContaining('접수되지 않았습니다'), findsOneWidget);
  });

  testWidgets('좁은 화면에서도 넘치지 않는다', (tester) async {
    tester.view.physicalSize = const Size(320, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(_form(_service((_) async => 'ok')));
    expect(tester.takeException(), isNull);
    await tester.tap(find.text('중등'));
    await tester.tap(find.text('다니는 중'));
    await tester.pump();
    await _tapSubmit(tester);
    expect(find.byKey(const ValueKey('tell-receipt')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  group('/tell 화면', () {
    EduTreeData emptyData() => EduTreeData(
      meta: Meta.fromJson({
        'mode': 'live',
        'generatedAt': '2026-10-17T00:00:00Z',
      }),
      regions: const [],
      tracks: const [],
      academies: const [],
    );
    RegistryEntry listed() => RegistryEntry.fromJson({
      'id': '3000046567',
      'name': '한선영어학원',
      'regionId': 'banpo',
      'subjects': ['english'],
      'gradeBands': ['high'],
    });
    Widget page(String? id) => ProviderScope(
      overrides: [
        dataProvider.overrideWith((ref) async => emptyData()),
        registryProvider.overrideWith((ref) async => [listed()]),
        parentReportsProvider.overrideWithValue(_service((_) async => 'ok')),
      ],
      child: MaterialApp(
        home: Scaffold(body: ParentReportPage(academyId: id)),
      ),
    );

    test('라우트가 있다', () {
      final shell = app_router.router.configuration.routes
          .whereType<ShellRoute>()
          .single;
      expect(
        shell.routes.whereType<GoRoute>().map((r) => r.path),
        contains('/tell'),
      );
    });

    testWidgets('?academy 로 등록부 학원이 미리 골라진다', (tester) async {
      await tester.pumpWidget(page('3000046567'));
      await tester.pumpAndSettle();
      expect(find.text('한선영어학원'), findsOneWidget);
      expect(find.byKey(const ValueKey('tell-submit')), findsOneWidget);
      expect(find.byType(TextField), findsNothing);
    });

    testWidgets('목록에 없는 id 로는 폼을 열지 않는다', (tester) async {
      await tester.pumpWidget(page('does-not-exist'));
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('tell-submit')), findsNothing);
      expect(find.textContaining('주소의 학원을 찾지 못했습니다'), findsOneWidget);
      expect(find.byKey(const ValueKey('tell-academy-search')), findsOneWidget);
    });

    testWidgets('학원을 안 정했으면 기존 검색으로 고른다', (tester) async {
      await tester.pumpWidget(page(null));
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('tell-submit')), findsNothing);
      await tester.enterText(
        find.byKey(const ValueKey('tell-academy-search')),
        '한선',
      );
      await tester.pumpAndSettle();
      expect(
        find.byKey(const ValueKey('tell-pick-3000046567')),
        findsOneWidget,
      );
      expect(find.text('한선영어학원'), findsOneWidget);
    });
  });
}
