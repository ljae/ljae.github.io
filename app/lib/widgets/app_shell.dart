import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:url_launcher/url_launcher.dart';

import '../core/brand.dart';
import '../core/theme.dart';
import '../data/models.dart';
import '../data/repository.dart';
import 'common.dart';
import 'header_layout.dart';
import 'wheel_selector.dart';

const _navItems = <(String path, String label, IconData icon)>[
  ('/', '홈', Icons.home_outlined),
  ('/tree', '테크트리', Icons.account_tree_outlined),
  ('/rank', '랭킹', Icons.leaderboard_outlined),
  ('/board', '게시판', Icons.forum_outlined),
  ('/map', '학군지도', Icons.map_outlined),
  ('/method', '산식', Icons.calculate_outlined),
];

/// 헤더 안쪽에서 실제로 쓸 수 있는 폭. [ContentWidth] 와 같은 계산이다.
double headerContentWidth(BuildContext context) {
  final w = MediaQuery.sizeOf(context).width;
  final pad = w < 640 ? AppSpace.md : AppSpace.lg;
  return (w < AppSpace.maxContent ? w : AppSpace.maxContent) - pad * 2;
}

class AppShell extends ConsumerWidget {
  final Widget child;
  const AppShell({super.key, required this.child});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final layout = HeaderLayout.forWidth(headerContentWidth(context));
    // 데모 배너는 있을 때만 자리를 차지한다.
    final demo = ref.watch(dataProvider.select((d) => d.value?.meta.isDemo == true));

    return Scaffold(
      appBar: PreferredSize(
        preferredSize: Size.fromHeight(layout.barHeight + (demo ? 38 : 0)),
        child: Column(children: [
          _TopBar(layout: layout),
          if (demo) const _DemoBanner(),
        ]),
      ),
      body: child,
      // 상단에 메뉴를 못 넣는 폭에서는 하단 바가 대신한다.
      bottomNavigationBar: layout.showNav ? null : const _BottomBar(),
    );
  }
}

class _DemoBanner extends ConsumerWidget {
  const _DemoBanner();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final meta = ref.watch(dataProvider).value?.meta;
    return meta == null ? const SizedBox.shrink() : DemoBanner(meta: meta);
  }
}

class _TopBar extends StatelessWidget {
  final HeaderLayout layout;
  const _TopBar({required this.layout});

  @override
  Widget build(BuildContext context) {
    final location = GoRouterState.of(context).uri.path;
    final dark = Theme.of(context).brightness == Brightness.dark;

    return Container(
      height: layout.barHeight,
      decoration: BoxDecoration(
        color: dark ? AppColors.darkSurface : AppColors.surface,
        border: Border(
            bottom:
                BorderSide(color: dark ? AppColors.darkLine : AppColors.line)),
      ),
      child: ContentWidth(
        child: Row(children: [
          _Brand(layout: layout),
          if (layout.showByOperator) ...[
            const SizedBox(width: 9),
            const _ByOperator(),
          ],
          if (layout.showFilters) ...[
            const SizedBox(width: AppSpace.md),
            _HeaderFilters(wheels: layout.useWheels),
          ],
          const Spacer(),
          // 자리가 모자라면 잘리는 대신 가로로 밀린다.
          // 예전에는 Row 가 그대로 넘쳐서 '산식'과 검색이 사라졌다.
          if (layout.showNav)
            Flexible(
              child: SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                reverse: true,
                child: Row(children: [
                  for (final (path, label, _) in _navItems)
                    _NavLink(
                        path: path,
                        label: label,
                        active: path == '/'
                            ? location == '/'
                            : location.startsWith(path)),
                  const SizedBox(width: AppSpace.xs),
                ]),
              ),
            ),
          IconButton(
            tooltip: '학원 검색',
            onPressed: () =>
                showSearch(context: context, delegate: _AcademySearch()),
            icon: const Icon(Icons.search, size: 21),
          ),
        ]),
      ),
    );
  }
}

/// 로고 + 워드마크. 폭이 모자라면 워드마크가 줄어들되 잘리지는 않는다.
class _Brand extends StatelessWidget {
  final HeaderLayout layout;
  const _Brand({required this.layout});

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: () => context.go('/'),
      borderRadius: BorderRadius.circular(AppRadius.sm),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        _Logo(size: layout.logo),
        const SizedBox(width: AppSpace.sm),
        Text(Brand.name,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.w800,
                fontSize: layout.titleSize,
                letterSpacing: -0.6)),
      ]),
    );
  }
}

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
        child: const Padding(
          padding: EdgeInsets.symmetric(horizontal: 5, vertical: 3),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Text('by ',
                style: TextStyle(
                    fontFamily: 'Paperlogy',
                    fontSize: 12,
                    color: AppColors.mist)),
            Text(Brand.operator,
                style: TextStyle(
                    fontFamily: 'Paperlogy',
                    fontSize: 12.5,
                    fontWeight: FontWeight.w700,
                    color: AppColors.gold)),
            SizedBox(width: 2),
            Icon(Icons.north_east, size: 9.5, color: AppColors.gold),
          ]),
        ),
      ),
    );
  }
}

/// 학군·학교급 필터. 페이지마다 흩어 두지 않고 헤더에 한 번만 둔다.
class _HeaderFilters extends ConsumerWidget {
  final bool wheels;
  const _HeaderFilters({required this.wheels});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // 학군 목록만 본다. 학원 목록이 바뀌었다고 헤더가 다시 그려질 이유는 없다.
    final regionList =
        ref.watch(dataProvider.select((d) => d.value?.regions)) ??
            const <Region>[];
    final sel = ref.watch(selectionProvider);
    final notifier = ref.read(selectionProvider.notifier);

    final regions = <(String, String)>[
      ('all', '전체'),
      for (final r in regionList) (r.id, r.nameKo),
    ];

    return Row(mainAxisSize: MainAxisSize.min, children: [
      WheelSelector<String>(
        label: '학군',
        options: regions,
        selected: sel.regionId,
        onChanged: notifier.setRegion,
        width: 92,
        compact: !wheels,
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
        compact: !wheels,
      ),
    ]);
  }
}

class _Logo extends StatelessWidget {
  final double size;
  const _Logo({required this.size});

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(size * 0.2),
      child: Image.asset(
        'assets/brand/mark.png',
        width: size,
        height: size,
        fit: BoxFit.cover,
        filterQuality: FilterQuality.medium,
        // 표시 크기에 맞춰 디코딩한다. 원본을 그대로 풀면
        // 헤더 하나 그리자고 큰 비트맵을 메모리에 올리게 된다.
        cacheWidth: (size * MediaQuery.devicePixelRatioOf(context)).round(),
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
  const _BottomBar();

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
      if (query.isEmpty) {
        return const Center(
            child: Text('학원명 또는 별칭을 입력하세요',
                style: TextStyle(color: AppColors.mist)));
      }

      // 등록부는 검색을 열 때 처음 읽는다. 아직 안 왔으면 채점 대상만
      // 먼저 보여주고, 도착하면 뒤에 이어 붙는다 — 기다리게 하지 않는다.
      final registry = ref.watch(registryProvider).value;
      final q = query.trim().toLowerCase();
      final rows = <SearchHit>[
        ...data.search(query),
        if (registry != null)
          for (final r in registry)
            if (r.name.toLowerCase().contains(q) ||
                r.displayName.toLowerCase().contains(q))
              SearchHit.listed(r),
      ];

      if (rows.isEmpty) {
        return Center(child: Text("'$query' 검색 결과가 없습니다"));
      }
      return ListView.builder(
        itemCount: rows.length > 40 ? 40 : rows.length,
        itemBuilder: (context, i) {
          final hit = rows[i];
          final region = data.regionById[hit.regionId];
          final subjects =
              hit.subjects.map((s) => subjectNames[s] ?? s).join(', ');
          return ListTile(
            key: ValueKey(hit.id),
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
