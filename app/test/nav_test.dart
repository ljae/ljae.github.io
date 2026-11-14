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
  });

  test('메뉴는 학원 탐색 · 일정 차례이고 홈 칸은 없다', () {
    // 홈은 로고가 맡는다. 메뉴 첫 두 칸이 학부모가 가장 자주 찾는 둘이다.
    expect(navItems.map((i) => i.$2), isNot(contains('홈')));
    expect(navItems.map((i) => i.$1), isNot(contains('/')));
    expect(navItems[0].$1, '/rank');
    expect(navItems[0].$2, '학원 탐색');
    expect(navItems[1].$1, '/calendar');
    expect(navItems[1].$2, '일정');
    // HeaderLayout._nav 는 네 칸 기준의 실측치다.
    expect(navItems.length, 4);
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
