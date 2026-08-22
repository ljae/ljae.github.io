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

final router = GoRouter(
  initialLocation: '/',
  routes: [
    ShellRoute(
      builder: (context, state, child) => AppShell(child: child),
      routes: [
        GoRoute(path: '/', builder: (context, state) => const HomePage()),
        GoRoute(path: '/tree', builder: (context, state) => const TechTreePage()),
        GoRoute(path: '/rank', builder: (context, state) => const RankingPage()),
        GoRoute(path: '/map', builder: (context, state) => const MapPage()),
        GoRoute(path: '/board', builder: (context, state) => const BoardPage()),
        GoRoute(path: '/method', builder: (context, state) => const MethodPage()),
        GoRoute(
          path: '/academy/:id',
          builder: (_, state) =>
              AcademyPage(academyId: state.pathParameters['id']!),
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
