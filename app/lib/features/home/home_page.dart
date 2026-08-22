import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/brand.dart';
import '../../core/theme.dart';
import '../../data/models.dart';
import '../../data/repository.dart';
import '../../widgets/academy_card.dart';
import '../../widgets/common.dart';

class HomePage extends ConsumerWidget {
  const HomePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(dataProvider);
    return async.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text('데이터를 불러오지 못했습니다\n$e')),
      data: (data) => ListView(children: [
        _Hero(data: data),
        const SizedBox(height: AppSpace.xxl),
        _RegionGrid(data: data),
        const SizedBox(height: AppSpace.xxl),
        _HowItWorks(meta: data.meta),
        const SizedBox(height: AppSpace.xxl),
        _Spotlight(data: data),
        const SizedBox(height: AppSpace.xxl),
        const _Footer(),
      ]),
    );
  }
}

class _Hero extends StatelessWidget {
  final EduTreeData data;
  const _Hero({required this.data});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final narrow = MediaQuery.sizeOf(context).width < 760;

    return Container(
      width: double.infinity,
      padding: EdgeInsets.symmetric(vertical: narrow ? AppSpace.xl : 76),
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF0E3B2E), Color(0xFF12513F), Color(0xFF0C1116)],
        ),
      ),
      child: ContentWidth(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(AppRadius.pill),
              ),
              child: Text(Brand.tagline,
                  style: text.labelLarge?.copyWith(color: Colors.white)),
            ),
            const SizedBox(height: AppSpace.lg),
            Text(
              '우리 아이는 지금 어디에 있고,\n다음엔 어디로 가야 하나요?',
              style: (narrow ? text.headlineLarge : text.displayLarge)
                  ?.copyWith(color: Colors.white),
            ),
            const SizedBox(height: AppSpace.md),
            ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 620),
              child: Text(
                '${Brand.name}는 학원 목록이 아니라 학원 사이의 길을 보여줍니다. '
                '공공데이터로 사실을 확인하고, 커뮤니티 신호로 평판을 읽어 '
                '${data.regions.length}개 학군의 진학 경로를 한 장의 지도로 만듭니다.',
                style: text.bodyLarge
                    ?.copyWith(color: Colors.white.withValues(alpha: 0.82)),
              ),
            ),
            const SizedBox(height: AppSpace.lg),
            Wrap(spacing: AppSpace.sm, runSpacing: AppSpace.sm, children: [
              FilledButton.icon(
                onPressed: () => context.go('/tree'),
                icon: const Icon(Icons.account_tree_outlined, size: 18),
                label: const Text('테크트리 보기'),
                style: FilledButton.styleFrom(
                    backgroundColor: AppColors.evergreenBright),
              ),
              OutlinedButton.icon(
                onPressed: () => context.go('/rank'),
                icon: const Icon(Icons.leaderboard_outlined, size: 18),
                label: const Text('학군별 랭킹'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.white,
                  side: BorderSide(color: Colors.white.withValues(alpha: 0.4)),
                  padding: const EdgeInsets.symmetric(
                      horizontal: 22, vertical: 16),
                ),
              ),
            ]),
            const SizedBox(height: AppSpace.xl),
            Wrap(spacing: AppSpace.xl, runSpacing: AppSpace.md, children: [
              _Stat('${data.academies.length}', '수록 학원'),
              _Stat('${data.tracks.length}', '과목·학교급 트랙'),
              _Stat('${data.stageById.length}', '테크트리 단계'),
              _Stat('${data.meta.mentionCount}', '분석한 커뮤니티 글'),
            ]),
          ],
        ),
      ),
    );
  }
}

class _Stat extends StatelessWidget {
  final String value;
  final String label;
  const _Stat(this.value, this.label);

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(value,
          style: text.headlineLarge?.copyWith(color: AppColors.gold)),
      Text(label,
          style: text.bodySmall
              ?.copyWith(color: Colors.white.withValues(alpha: 0.65))),
    ]);
  }
}

class _RegionGrid extends ConsumerWidget {
  final EduTreeData data;
  const _RegionGrid({required this.data});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final width = MediaQuery.sizeOf(context).width;
    final columns = width < 620 ? 1 : (width < 980 ? 2 : 4);

    return ContentWidth(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const SectionHeader('4개 학군',
            subtitle: '각 학군은 서로 다른 논리로 움직입니다. 같은 과목이라도 경로가 다릅니다.'),
        GridView.count(
          crossAxisCount: columns,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          crossAxisSpacing: AppSpace.md,
          mainAxisSpacing: AppSpace.md,
          childAspectRatio: columns == 1 ? 3.4 : 1.02,
          children: [
            for (final region in data.regions)
              _RegionCard(
                region: region,
                count: data.academyCountIn(region.id),
                onTap: () {
                  ref.read(selectionProvider.notifier).setRegion(region.id);
                  context.go('/tree');
                },
              ),
          ],
        ),
      ]),
    );
  }
}

class _RegionCard extends StatelessWidget {
  final Region region;
  final int count;
  final VoidCallback onTap;
  const _RegionCard(
      {required this.region, required this.count, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(AppRadius.md),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(AppSpace.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(children: [
                Text(region.nameKo, style: text.headlineMedium),
                const SizedBox(width: 6),
                Text(region.nameEn,
                    style: text.bodySmall?.copyWith(color: AppColors.mist)),
              ]),
              const SizedBox(height: 2),
              Text(region.sigungu, style: text.bodySmall),
              const SizedBox(height: AppSpace.sm),
              Expanded(
                child: Text(region.tagline,
                    style: text.bodyMedium, maxLines: 3),
              ),
              const Divider(height: AppSpace.lg),
              Row(children: [
                Text('학원 $count곳', style: text.labelLarge),
                const Spacer(),
                const Icon(Icons.arrow_forward, size: 15),
              ]),
            ],
          ),
        ),
      ),
    );
  }
}

class _HowItWorks extends StatelessWidget {
  final Meta meta;
  const _HowItWorks({required this.meta});

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    final columns = width < 720 ? 1 : (width < 1040 ? 2 : 4);

    return ContentWidth(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        SectionHeader('트리스코어는 이렇게 계산됩니다',
            subtitle: '산식을 숨기지 않습니다. 점수를 만든 근거를 학원마다 전부 공개합니다.',
            trailing: TextButton(
              onPressed: () => context.go('/method'),
              child: const Text('자세히'),
            )),
        GridView.count(
          crossAxisCount: columns,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          crossAxisSpacing: AppSpace.md,
          mainAxisSpacing: AppSpace.md,
          childAspectRatio: columns == 1 ? 3.0 : 0.98,
          children: [
            for (final key in pillarNames.keys)
              _PillarCard(
                  pillar: key, weight: meta.weights[key] ?? 0),
          ],
        ),
      ]),
    );
  }
}

class _PillarCard extends StatelessWidget {
  final String pillar;
  final double weight;
  const _PillarCard({required this.pillar, required this.weight});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final color = AppColors.pillars[pillar]!;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpace.md),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Icon(pillarIcons[pillar], size: 18, color: color),
            const Spacer(),
            Text('${(weight * 100).toStringAsFixed(0)}%',
                style: text.headlineMedium?.copyWith(color: color)),
          ]),
          const SizedBox(height: AppSpace.sm),
          Text(pillarNames[pillar]!, style: text.titleLarge),
          const SizedBox(height: 4),
          Expanded(
            child: Text(pillarDescriptions[pillar]!,
                style: text.bodyMedium, maxLines: 5),
          ),
        ]),
      ),
    );
  }
}

class _Spotlight extends ConsumerWidget {
  final EduTreeData data;
  const _Spotlight({required this.data});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final sel = ref.watch(selectionProvider);
    final top = data.ranking(regionId: sel.regionId).take(3).toList();
    final region = data.regionById[sel.regionId];

    return ContentWidth(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        SectionHeader('${region?.nameKo ?? ""} 상위 학원',
            subtitle: '트리스코어 기준 · 표본 ${data.meta.minSampleForRank}건 이상만 순위에 넣습니다',
            trailing: TextButton(
              onPressed: () => context.go('/rank'),
              child: const Text('전체 랭킹'),
            )),
        for (var i = 0; i < top.length; i++)
          AcademyCard(academy: top[i], rank: i + 1),
      ]),
    );
  }
}

class _Footer extends StatelessWidget {
  const _Footer();

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Container(
      width: double.infinity,
      color: AppColors.ink,
      padding: const EdgeInsets.symmetric(vertical: AppSpace.xl),
      child: ContentWidth(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(Brand.name,
              style: text.titleLarge?.copyWith(color: Colors.white)),
          const SizedBox(height: 6),
          Text(Brand.description,
              style: text.bodyMedium?.copyWith(color: AppColors.mist)),
          const SizedBox(height: AppSpace.lg),
          Text(
            '운영: ${Brand.operator} · ${Brand.domain}\n'
            '${Brand.operator}는 영어 교육 사업을 함께 운영합니다. 영어 과목 항목에는 이해상충 가능성이 있어 이를 고지합니다.',
            style: text.bodySmall?.copyWith(color: AppColors.mist),
          ),
          const SizedBox(height: AppSpace.md),
          Wrap(spacing: AppSpace.md, children: [
            TextButton(
                onPressed: () => context.go('/method'),
                child: const Text('산식 · 데이터 출처')),
            TextButton(
                onPressed: () => context.go('/method'),
                child: const Text('정정 요청')),
          ]),
        ]),
      ),
    );
  }
}
