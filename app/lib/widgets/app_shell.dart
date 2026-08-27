import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:url_launcher/url_launcher.dart';

import '../core/brand.dart';
import '../core/theme.dart';
import '../data/models.dart';
import '../data/repository.dart';
import 'annals.dart';
import 'common.dart';
import 'scroll_stage.dart';
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

/// 머리띠 두께. 헤더 높이 계산에 들어가는 값이라 상수로 둔다.
const double _headBand = 3.0;

class AppShell extends ConsumerStatefulWidget {
  final Widget child;
  const AppShell({super.key, required this.child});

  @override
  ConsumerState<AppShell> createState() => _AppShellState();
}

class _AppShellState extends ConsumerState<AppShell> {
  /// 읽은 만큼. 본문의 스크롤 알림이 채우고 머리띠가 읽는다.
  /// ValueNotifier 로 흘리므로 스크롤 한 번에 셸 전체가 다시 그려지지 않는다.
  final _read = ValueNotifier<double>(0);

  @override
  void dispose() {
    _read.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final layout = HeaderLayout.forWidth(headerContentWidth(context));
    // 데모 배너는 있을 때만 자리를 차지한다.
    final demo = ref.watch(
      dataProvider.select((d) => d.value?.meta.isDemo == true),
    );

    return Scaffold(
      appBar: PreferredSize(
        // 머리띠 3px 이 늘 맨 위에 있다. 높이 계산에 반드시 더할 것 —
        // 빼먹으면 헤더가 3px 만큼 잘린다.
        preferredSize: Size.fromHeight(
          _headBand + layout.barHeight + (demo ? 38 : 0),
        ),
        child: Column(
          children: [
            // 책배(冊背)의 머리띠. 모든 화면 맨 위에 주묵 한 줄.
            // 로고가 없어도 '이 서비스'라는 것을 말하는 장치이고,
            // **읽은 만큼 찬다** — 진행 막대를 새로 만드는 대신 이미
            // 있는 것에 뜻을 하나 더 얹었다. 새 부품보다 조용하다.
            ReadingBand(height: _headBand, progress: _read),
            _TopBar(layout: layout),
            if (demo) const _DemoBanner(),
          ],
        ),
      ),
      // 판면은 앱 전체에 깔린다. 스크롤해도 계선은 제자리에 있고
      // 내용만 지나간다 — 종이 위를 읽는 느낌이 그래서 난다.
      body: ReadingProgress(
        notifier: _read,
        child: PaperGround(child: widget.child),
      ),
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
        color: AppColors.surfaceOn(dark),
        // 계선 한 줄이 아니라 **굵은 획**으로 닫는다. 판면의 윗변이다.
        border: Border(
          bottom: BorderSide(color: AppColors.inkOn(dark), width: AppRule.thin),
        ),
      ),
      child: ContentWidth(
        child: Row(
          children: [
            _Brand(layout: layout),
            if (layout.showByOperator) ...[
              const SizedBox(width: 9),
              const _ByOperator(),
            ],
            const SizedBox(width: AppSpace.md),
            _HeaderFilters(mode: layout.filterMode),
            // 남는 자리는 전부 메뉴 몫이다.
            //
            // 여기서 한 번 틀렸다. Spacer 와 Flexible 을 나란히 뒀더니 둘 다
            // flex 자식이라 남은 폭을 반씩 나눠 가졌다. 메뉴는 필요한 만큼의
            // 절반만 받고, reverse 로 오른쪽에 붙어 있던 탓에 '홈'과 '테크트리'가
            // 왼쪽으로 밀려 사라졌다. 자리가 없어서가 아니라 안 준 것이었다.
            //
            // 지금은 Expanded 하나가 남는 폭을 다 받고, 그 안에서 오른쪽 정렬한다.
            // 그래도 넘치면 잘리는 대신 왼쪽부터 보이며 가로로 밀린다.
            Expanded(
              child: layout.showNav
                  ? Align(
                      alignment: Alignment.centerRight,
                      child: SingleChildScrollView(
                        scrollDirection: Axis.horizontal,
                        child: Row(
                          children: [
                            for (final (path, label, _) in _navItems)
                              _NavLink(
                                path: path,
                                label: label,
                                active: path == '/'
                                    ? location == '/'
                                    : location.startsWith(path),
                              ),
                            const SizedBox(width: AppSpace.xs),
                          ],
                        ),
                      ),
                    )
                  : const SizedBox.shrink(),
            ),
            IconButton(
              tooltip: '학원 검색',
              onPressed: () =>
                  showSearch(context: context, delegate: _AcademySearch()),
              icon: const Icon(Icons.search, size: 21),
            ),
          ],
        ),
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
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _Logo(size: layout.logo),
          const SizedBox(width: AppSpace.sm),
          Text(
            Brand.name,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
              fontWeight: FontWeight.w800,
              fontSize: layout.titleSize,
              letterSpacing: -1.1,
            ),
          ),
        ],
      ),
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
        onTap: () => launchUrl(
          Uri.base.resolve('openedu/'),
          webOnlyWindowName: '_blank',
        ),
        child: const Padding(
          padding: EdgeInsets.symmetric(horizontal: 5, vertical: 3),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                'by ',
                style: TextStyle(
                  fontFamily: 'Paperlogy',
                  fontSize: 12,
                  color: AppColors.mist,
                ),
              ),
              Text(
                Brand.operator,
                style: TextStyle(
                  fontFamily: 'Paperlogy',
                  fontSize: 12.5,
                  fontWeight: FontWeight.w700,
                  color: AppColors.gold,
                ),
              ),
              SizedBox(width: 2),
              Icon(Icons.north_east, size: 9.5, color: AppColors.gold),
            ],
          ),
        ),
      ),
    );
  }
}

/// 학원이 받는 학년대. 초등을 저·고학년으로 가른다 — 학원가에서
/// 그 둘은 사실상 다른 시장이고, 한 덩어리로 두면 학부모가 자기
/// 구간이 아닌 것을 계속 보게 된다.
const _bandOptions = <(String, String)>[
  ('elem_low', '예비초~초3'),
  ('elem_high', '초4~초6'),
  ('middle', '중등'),
  ('high', '고등'),
];

/// 학군·학교급 필터. 페이지마다 흩어 두지 않고 헤더에 한 번만 둔다.
class _HeaderFilters extends ConsumerWidget {
  final FilterMode mode;
  const _HeaderFilters({required this.mode});

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

    if (mode == FilterMode.sheet) {
      return _FilterButton(regions: regions, selection: sel);
    }

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        WheelSelector<String>(
          label: '학군',
          options: regions,
          selected: sel.regionId,
          onChanged: notifier.setRegion,
          width: 92,
        ),
        const SizedBox(width: AppSpace.sm),
        WheelSelector<String>(
          label: '학년',
          options: _bandOptions,
          selected: sel.gradeBand,
          onChanged: notifier.setGradeBand,
          width: 112,
        ),
      ],
    );
  }
}

/// 좁은 화면용. 두 선택을 한 덩어리로 접고, 누르면 시트로 펼친다.
///
/// 드롭다운 두 개를 억지로 밀어 넣는 것보다 낫다. 헤더에서는 지금 값이
/// 뭔지만 보이면 되고, 고르는 일은 손가락이 닿는 넓은 곳에서 하는 편이 낫다.
class _FilterButton extends StatelessWidget {
  final List<(String, String)> regions;
  final Selection selection;
  const _FilterButton({required this.regions, required this.selection});

  String _label() {
    final region = regions
        .firstWhere(
          (r) => r.$1 == selection.regionId,
          orElse: () => ('all', '전체'),
        )
        .$2;
    final level = _bandOptions
        .firstWhere(
          (l) => l.$1 == selection.gradeBand,
          orElse: () => _bandOptions.first,
        )
        .$2;
    return '$region · $level';
  }

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Semantics(
      button: true,
      label: '학군과 학년 고르기. 지금 ${_label()}',
      child: InkWell(
        borderRadius: BorderRadius.circular(AppRadius.sm),
        onTap: () => _open(context),
        child: Container(
          height: 38,
          padding: const EdgeInsets.symmetric(horizontal: 10),
          decoration: BoxDecoration(
            color: AppColors.canvasOn(dark),
            borderRadius: BorderRadius.circular(AppRadius.sm),
            border: Border(
              left: BorderSide(
                color: AppColors.accentOn(dark),
                width: AppRule.bold,
              ),
              top: BorderSide(color: AppColors.ruleOn(dark)),
              right: BorderSide(color: AppColors.ruleOn(dark)),
              bottom: BorderSide(color: AppColors.ruleOn(dark)),
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                _label(),
                style: TextStyle(
                  fontFamily: 'Paperlogy',
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                  letterSpacing: -0.3,
                  color: AppColors.inkOn(dark),
                ),
              ),
              const SizedBox(width: 3),
              Icon(Icons.expand_more, size: 17, color: AppColors.mutedOn(dark)),
            ],
          ),
        ),
      ),
    );
  }

  void _open(BuildContext context) {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (_) => const _FilterSheet(),
    );
  }
}

class _FilterSheet extends ConsumerWidget {
  const _FilterSheet();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final regionList =
        ref.watch(dataProvider.select((d) => d.value?.regions)) ??
        const <Region>[];
    final sel = ref.watch(selectionProvider);
    final notifier = ref.read(selectionProvider.notifier);
    final text = Theme.of(context).textTheme;

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
          AppSpace.md,
          0,
          AppSpace.md,
          AppSpace.lg,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 시트 안에서도 화면과 같은 밑줄 탭을 쓴다. 여기만
            // Material 기본 ChoiceChip(알약)을 두면 같은 선택이
            // 두 가지 모양을 갖게 된다.
            Text(spaced('학군'), style: text.labelMedium),
            const SizedBox(height: AppSpace.sm),
            ChipRow<String>(
              options: <(String, String)>[
                ('all', '전체'),
                for (final r in regionList) (r.id, r.nameKo),
              ],
              selected: sel.regionId,
              onChanged: notifier.setRegion,
            ),
            const SizedBox(height: AppSpace.lg),
            Text(spaced('학년'), style: text.labelMedium),
            const SizedBox(height: AppSpace.sm),
            ChipRow<String>(
              options: _bandOptions,
              selected: sel.gradeBand,
              onChanged: notifier.setGradeBand,
            ),
          ],
        ),
      ),
    );
  }
}

class _Logo extends StatelessWidget {
  final double size;
  const _Logo({required this.size});

  @override
  Widget build(BuildContext context) {
    // 각지게 자른다. 둥근 아이콘은 어느 앱에나 있고, 이 화면에서는
    // 유일하게 둥근 것이 되어 혼자 튄다.
    return ClipRRect(
      borderRadius: BorderRadius.circular(AppRadius.sm),
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
  const _NavLink({
    required this.path,
    required this.label,
    required this.active,
  });

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final accent = AppColors.accentOn(dark);

    // 알약 배경 대신 **밑줄**. 계선과 같은 언어라 헤더가 판면의 일부로
    // 읽히고, 지금 어디를 보고 있는지는 주묵 한 줄이 말한다.
    return InkWell(
      onTap: () => context.go(path),
      child: Container(
        padding: const EdgeInsets.fromLTRB(13, 10, 13, 8),
        decoration: BoxDecoration(
          border: Border(
            bottom: BorderSide(
              color: active ? accent : Colors.transparent,
              width: AppRule.bold,
            ),
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontFamily: 'Paperlogy',
            fontSize: 14.5,
            fontWeight: active ? FontWeight.w800 : FontWeight.w500,
            letterSpacing: -0.4,
            color: active ? AppColors.inkOn(dark) : AppColors.mutedOn(dark),
          ),
        ),
      ),
    );
  }
}

class _BottomBar extends StatelessWidget {
  const _BottomBar();

  @override
  Widget build(BuildContext context) {
    final location = GoRouterState.of(context).uri.path;
    var index = _navItems.indexWhere(
      (i) => i.$1 == '/' ? location == '/' : location.startsWith(i.$1),
    );
    if (index < 0) index = 0;

    final dark = Theme.of(context).brightness == Brightness.dark;
    final accent = AppColors.accentOn(dark);

    // Material 기본 NavigationBar 는 선택 항목에 알약 배경을 깐다.
    // 이 화면에서 유일하게 둥근 것이 되어 혼자 튀므로 직접 그린다.
    // 선택 표시는 **위쪽 주묵 획** — 헤더의 밑줄과 짝이 맞는다.
    return SafeArea(
      top: false,
      child: Container(
        height: 62,
        decoration: BoxDecoration(
          color: AppColors.surfaceOn(dark),
          border: Border(
            top: BorderSide(color: AppColors.inkOn(dark), width: AppRule.thin),
          ),
        ),
        child: Row(
          children: [
            for (var i = 0; i < _navItems.length; i++)
              Expanded(
                child: InkWell(
                  onTap: () => context.go(_navItems[i].$1),
                  child: DecoratedBox(
                    decoration: BoxDecoration(
                      color: i == index
                          ? accent.withValues(alpha: dark ? 0.12 : 0.06)
                          : Colors.transparent,
                      border: Border(
                        top: BorderSide(
                          color: i == index ? accent : Colors.transparent,
                          width: AppRule.bold,
                        ),
                      ),
                    ),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          _navItems[i].$3,
                          size: 20,
                          color: i == index
                              ? AppColors.inkOn(dark)
                              : AppColors.mutedOn(dark),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          _navItems[i].$2,
                          style: TextStyle(
                            fontFamily: 'Paperlogy',
                            fontSize: 11,
                            fontWeight: i == index
                                ? FontWeight.w800
                                : FontWeight.w500,
                            letterSpacing: -0.3,
                            color: i == index
                                ? AppColors.inkOn(dark)
                                : AppColors.mutedOn(dark),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _AcademySearch extends SearchDelegate<String> {
  @override
  String get searchFieldLabel => '학원명 · 별칭으로 검색';

  @override
  List<Widget> buildActions(BuildContext context) => [
    IconButton(onPressed: () => query = '', icon: const Icon(Icons.clear)),
  ];

  @override
  Widget buildLeading(BuildContext context) => IconButton(
    onPressed: () => close(context, ''),
    icon: const Icon(Icons.arrow_back),
  );

  @override
  Widget buildResults(BuildContext context) => _results(context);

  @override
  Widget buildSuggestions(BuildContext context) => _results(context);

  Widget _results(BuildContext context) {
    return Consumer(
      builder: (context, ref, _) {
        final data = ref.watch(dataProvider).value;
        if (data == null) {
          return const Center(child: CircularProgressIndicator());
        }
        if (query.isEmpty) {
          return const Center(
            child: Text(
              '학원명 또는 별칭을 입력하세요',
              style: TextStyle(color: AppColors.mist),
            ),
          );
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
            final subjects = hit.subjects
                .map((s) => subjectNames[s] ?? s)
                .join(', ');
            return ListTile(
              key: ValueKey(hit.id),
              title: Text(hit.name),
              subtitle: Text(
                '${region?.nameKo ?? ''}'
                '${subjects.isEmpty ? '' : ' · $subjects'}',
              ),
              trailing: hit.evaluated
                  ? Text(
                      hit.total!.toStringAsFixed(0),
                      style: const TextStyle(
                        fontFamily: 'Paperlogy',
                        fontSize: 17,
                        fontWeight: FontWeight.w800,
                        letterSpacing: -0.6,
                        fontFeatures: ledgerFigures,
                      ),
                    )
                  : const TagMark('미평가', color: AppColors.mist),
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
      },
    );
  }
}
