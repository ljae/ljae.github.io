import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

import 'package:edutree/core/router.dart';
import 'package:edutree/features/home/home_page.dart';
import 'package:edutree/widgets/app_shell.dart';

/// 산식은 메뉴에서 빠지되 **주소는 남고, 첫 화면에서 들어갈 수 있어야** 한다.
/// 셋 중 하나라도 어긋나면 산식 공개가 말뿐이 된다.
void main() {
  test('메뉴에 산식이 없다', () {
    expect(navItems.map((i) => i.$1), isNot(contains('/method')));
    expect(navItems.map((i) => i.$2), isNot(contains('산식')));
    // 메뉴가 줄어도 홈은 첫 칸이어야 하단 바의 폴백(index 0)이 홈이다.
    expect(navItems.first.$1, '/');
  });

  test('/method 라우트는 그대로 살아 있다', () {
    final shell = router.configuration.routes.whereType<ShellRoute>().single;
    final paths = shell.routes.whereType<GoRoute>().map((r) => r.path);
    expect(paths, contains('/method'));
    // 메뉴 항목은 전부 라우트가 있어야 한다 — 없는 곳으로 보내지 않는다.
    for (final (path, _, _) in navItems) {
      expect(paths, contains(path));
    }
  });

  testWidgets('첫 화면의 산식 링크가 전문으로 안내한다', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(home: Scaffold(body: MethodLink())),
    );
    expect(find.text(MethodLink.label), findsOneWidget);
    expect(MethodLink.label, contains('산식'));
  });
}
