import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../features/academy/academy_page.dart';
import '../features/board/board_page.dart';
import '../features/home/home_page.dart';
import '../features/map/map_page.dart';
import '../features/method/method_page.dart';
import '../features/ranking/ranking_page.dart';
import '../features/techtree/techtree_page.dart';
import '../widgets/app_shell.dart';

/// 메뉴 전환. 셸(헤더·하단바)은 그대로 두고 본문만 바꾸므로
/// 짧게 흐려 넘긴다. 그냥 툭 갈아 끼우면 어디가 바뀌었는지 눈이 못 따라간다.
/// 위로 살짝 올리는 정도만 곁들인다 — 길어지면 그게 더 답답하다.
CustomTransitionPage<void> _fade(Widget child) => CustomTransitionPage<void>(
      child: child,
      transitionDuration: const Duration(milliseconds: 180),
      reverseTransitionDuration: const Duration(milliseconds: 120),
      transitionsBuilder: (context, animation, secondary, child) {
        final curved =
            CurvedAnimation(parent: animation, curve: Curves.easeOutCubic);
        return FadeTransition(
          opacity: curved,
          child: SlideTransition(
            position: Tween(begin: const Offset(0, 0.012), end: Offset.zero)
                .animate(curved),
            child: child,
          ),
        );
      },
    );

final router = GoRouter(
  initialLocation: '/',
  routes: [
    ShellRoute(
      builder: (context, state, child) => AppShell(child: child),
      routes: [
        GoRoute(
            path: '/',
            pageBuilder: (context, state) => _fade(const HomePage())),

        GoRoute(
            path: '/tree',
            pageBuilder: (context, state) => _fade(const TechTreePage())),

        GoRoute(
            path: '/rank',
            pageBuilder: (context, state) => _fade(const RankingPage())),

        GoRoute(
            path: '/map',
            pageBuilder: (context, state) => _fade(const MapPage())),

        GoRoute(
            path: '/board',
            pageBuilder: (context, state) => _fade(const BoardPage())),

        GoRoute(
            path: '/method',
            pageBuilder: (context, state) => _fade(const MethodPage())),

        GoRoute(
          path: '/academy/:id',
          pageBuilder: (_, state) =>
              _fade(AcademyPage(academyId: state.pathParameters['id']!)),
        ),
      ],
    ),
  ],
  errorBuilder: (context, state) => Scaffold(
    body: Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Text('페이지를 찾을 수 없습니다'),
          const SizedBox(height: 12),
          FilledButton(
              onPressed: () => context.go('/'), child: const Text('홈으로')),
        ],
      ),
    ),
  ),
);
