import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:url_launcher/url_launcher.dart';

import '../core/brand.dart';
import '../core/theme.dart';
import '../data/models.dart';
import '../data/repository.dart';
import 'common.dart';
import 'wheel_selector.dart';

const _navItems = <(String path, String label, IconData icon)>[
  ('/', '홈', Icons.home_outlined),
  ('/tree', '테크트리', Icons.account_tree_outlined),
  ('/rank', '랭킹', Icons.leaderboard_outlined),
  ('/map', '학군지도', Icons.map_outlined),
  ('/method', '산식', Icons.calculate_outlined),
];

class AppShell extends ConsumerWidget {
  final Widget child;
  const AppShell({super.key, required this.child});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final wide = MediaQuery.sizeOf(context).width >= 860;
    final meta = ref.watch(dataProvider).value?.meta;

    return Scaffold(
      appBar: PreferredSize(
        preferredSize: Size.fromHeight(
            topBarHeightFor(context) + (meta?.isDemo == true ? 38 : 0)),
        child: Column(children: [
          _TopBar(wide: wide),
          if (meta != null) DemoBanner(meta: meta),
        ]),
      ),
      body: child,
      bottomNavigationBar: wide ? null : _BottomBar(),
    );
  }
}

class _TopBar extends StatelessWidget {
  final bool wide;
  const _TopBar({required this.wide});

  @override
  Widget build(BuildContext context) {
    final location = GoRouterState.of(context).uri.path;
    final dark = Theme.of(context).brightness == Brightness.dark;

    return Container(
      height: topBarHeightFor(context),
      decoration: BoxDecoration(
        color: dark ? AppColors.darkSurface : AppColors.surface,
        border: Border(
            bottom:
                BorderSide(color: dark ? AppColors.darkLine : AppColors.line)),
      ),
      child: ContentWidth(
        child: Row(children: [
          InkWell(
            onTap: () => context.go('/'),
            child: Row(children: [
              const _Logo(),
              const SizedBox(width: AppSpace.sm),
              Text(Brand.name,
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.w800,
                      fontSize: wide ? 32 : 24,
                      letterSpacing: -0.6)),
            ]),
          ),
          const SizedBox(width: 9),
          const _ByOperator(),
          const SizedBox(width: AppSpace.lg),
          const _HeaderFilters(),
          const Spacer(),
          if (wide)
            for (final (path, label, _) in _navItems)
              _NavLink(
                  path: path,
                  label: label,
                  active: path == '/'
                      ? location == '/'
                      : location.startsWith(path)),
          if (wide) const SizedBox(width: AppSpace.sm),
          IconButton(
            tooltip: '학원 검색',
            onPressed: () => showSearch(
                context: context, delegate: _AcademySearch()),
            icon: const Icon(Icons.search, size: 21),
          ),
        ]),
      ),
    );
  }
}

/// 헤더 로고 크기. 상단 바 높이가 여기에 딸려 간다.
///
/// 데스크톱은 크게 간다 — 브랜드가 눈에 들어와야 한다.
/// 모바일은 조금 줄인다. 100px 로고 + 124px 바는 812px 화면의 15%를 먹는다.
double logoSizeFor(BuildContext context) =>
    MediaQuery.sizeOf(context).width >= 720 ? 100.0 : 72.0;

double topBarHeightFor(BuildContext context) => logoSizeFor(context) + 24;

/// 운영사 표기. 제목 옆에 작게 붙이고 회사 소개로 연결한다.
/// 브랜드를 가리지 않을 만큼만 — 크기와 색을 확실히 낮췄다.
class _ByOperator extends StatelessWidget {
  const _ByOperator();

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: '${Brand.operator} 회사 소개',
      child: InkWell(
        borderRadius: BorderRadius.circular(AppRadius.sm),
        onTap: () => launchUrl(Uri.base.resolve('openedu/'),
            webOnlyWindowName: '_blank'),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 3),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Text('by ',
                style: TextStyle(
                    fontFamily: 'Paperlogy',
                    fontSize: 12,
                    color: AppColors.mist)),
            Text(Brand.operator,
                style: const TextStyle(
                    fontFamily: 'Paperlogy',
                    fontSize: 12.5,
                    fontWeight: FontWeight.w700,
                    color: AppColors.gold)),
            const SizedBox(width: 2),
            const Icon(Icons.north_east, size: 9.5, color: AppColors.gold),
          ]),
        ),
      ),
    );
  }
}

/// 학군·학교급 필터. 페이지마다 흩어 두지 않고 헤더에 한 번만 둔다.
class _HeaderFilters extends ConsumerWidget {
  const _HeaderFilters();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final data = ref.watch(dataProvider).value;
    final sel = ref.watch(selectionProvider);
    final notifier = ref.read(selectionProvider.notifier);
    final narrow = MediaQuery.sizeOf(context).width < 1180;

    final regions = <(String, String)>[
      ('all', '전체'),
      for (final r in data?.regions ?? const <Region>[]) (r.id, r.nameKo),
    ];

    return Row(mainAxisSize: MainAxisSize.min, children: [
      WheelSelector<String>(
        label: '학군',
        options: regions,
        selected: sel.regionId,
        onChanged: notifier.setRegion,
        width: 92,
        compact: narrow,
      ),
      const SizedBox(width: AppSpace.sm),
      WheelSelector<String>(
        label: '학교급',
        options: const [
          ('elementary', '초등'),
          ('middle', '중등'),
          ('high', '고등'),
        ],
        selected: sel.schoolLevel,
        onChanged: notifier.setSchoolLevel,
        width: 78,
        compact: narrow,
      ),
    ]);
  }
}

class _Logo extends StatelessWidget {
  const _Logo();

  @override
  Widget build(BuildContext context) {
    final size = logoSizeFor(context);
    return ClipRRect(
      borderRadius: BorderRadius.circular(size * 0.2),
      child: Image.asset(
        'assets/brand/mark.png',
        width: size,
        height: size,
        fit: BoxFit.cover,
        filterQuality: FilterQuality.high,
      ),
    );
  }
}


class _NavLink extends StatelessWidget {
  final String path;
  final String label;
  final bool active;
  const _NavLink(
      {required this.path, required this.label, required this.active});

  @override
  Widget build(BuildContext context) {
    return TextButton(
      onPressed: () => context.go(path),
      style: TextButton.styleFrom(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        foregroundColor: active ? AppColors.navy : AppColors.slate,
      ),
      child: Text(label,
          style: TextStyle(
            fontFamily: 'Paperlogy',
            fontSize: 14.5,
            fontWeight: active ? FontWeight.w700 : FontWeight.w500,
            letterSpacing: -0.2,
          )),
    );
  }
}

class _BottomBar extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final location = GoRouterState.of(context).uri.path;
    var index = _navItems.indexWhere((i) =>
        i.$1 == '/' ? location == '/' : location.startsWith(i.$1));
    if (index < 0) index = 0;

    return NavigationBar(
      selectedIndex: index,
      height: 64,
      labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
      onDestinationSelected: (i) => context.go(_navItems[i].$1),
      destinations: [
        for (final (_, label, icon) in _navItems)
          NavigationDestination(icon: Icon(icon, size: 21), label: label),
      ],
    );
  }
}

class _AcademySearch extends SearchDelegate<String> {
  @override
  String get searchFieldLabel => '학원명 · 별칭으로 검색';

  @override
  List<Widget> buildActions(BuildContext context) => [
        IconButton(
            onPressed: () => query = '', icon: const Icon(Icons.clear)),
      ];

  @override
  Widget buildLeading(BuildContext context) => IconButton(
      onPressed: () => close(context, ''), icon: const Icon(Icons.arrow_back));

  @override
  Widget buildResults(BuildContext context) => _results(context);

  @override
  Widget buildSuggestions(BuildContext context) => _results(context);

  Widget _results(BuildContext context) {
    return Consumer(builder: (context, ref, _) {
      final data = ref.watch(dataProvider).value;
      if (data == null) {
        return const Center(child: CircularProgressIndicator());
      }
      final rows = data.search(query);
      if (query.isEmpty) {
        return const Center(
            child: Text('학원명 또는 별칭을 입력하세요',
                style: TextStyle(color: AppColors.mist)));
      }
      if (rows.isEmpty) {
        return Center(child: Text("'$query' 검색 결과가 없습니다"));
      }
      return ListView.builder(
        itemCount: rows.length,
        itemBuilder: (context, i) {
          final hit = rows[i];
          final region = data.regionById[hit.regionId];
          final subjects =
              hit.subjects.map((s) => subjectNames[s] ?? s).join(', ');
          return ListTile(
            title: Text(hit.name),
            subtitle: Text('${region?.nameKo ?? ''}'
                '${subjects.isEmpty ? '' : ' · $subjects'}'),
            trailing: hit.evaluated
                ? Text(hit.total!.toStringAsFixed(0),
                    style: const TextStyle(
                        fontFamily: 'Paperlogy', fontWeight: FontWeight.w700))
                : const Chip2('미평가', color: AppColors.mist),
            // 등록부 학원은 상세 화면이 없다. 점수를 만들지 않았으므로
            // 보여줄 것도 없고, 있는 척하면 그게 곧 거짓이다.
            onTap: hit.evaluated
                ? () {
                    close(context, hit.id);
                    context.go('/academy/${hit.id}');
                  }
                : null,
          );
        },
      );
    });
  }
}
