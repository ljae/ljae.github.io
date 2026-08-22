import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

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
          colors: [Color(0xFF1B2C55), Color(0xFF182448), Color(0xFF0B1020)],
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
                'NEIS 공시로 사실을 확인하고, 커뮤니티 신호로 평판을 읽어 '
                '${data.regions.length}개 학군의 진학 경로를 한 장의 지도로 만듭니다.',
                style: text.bodyLarge
                    ?.copyWith(color: Colors.white.withValues(alpha: 0.82)),
              ),
            ),
            const SizedBox(height: AppSpace.lg),
            Row(children: [
              Container(
                width: 3,
                height: 34,
                color: AppColors.gold.withValues(alpha: 0.7),
                margin: const EdgeInsets.only(right: AppSpace.sm),
              ),
              Expanded(
                child: Text(Brand.nameOrigin,
                    style: text.bodySmall?.copyWith(
                        color: AppColors.goldLight, height: 1.5)),
              ),
            ]),
            const SizedBox(height: AppSpace.lg),
            Wrap(spacing: AppSpace.sm, runSpacing: AppSpace.sm, children: [
              FilledButton.icon(
                onPressed: () => context.go('/tree'),
                icon: const Icon(Icons.account_tree_outlined, size: 18),
                label: const Text('테크트리 보기'),
                style: FilledButton.styleFrom(
                    backgroundColor: AppColors.gold,
                    foregroundColor: const Color(0xFF1B2540)),
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
              _Stat(_n(data.meta.registryCount), '등록 학원'),
              _Stat(_n(data.meta.evaluatedCount), '트리스코어 채점'),
              _Stat('${data.stageById.length}', '테크트리 단계'),
              _Stat(_n(data.meta.mentionCount), '분석한 커뮤니티 글'),
            ]),
          ],
        ),
      ),
    );
  }
}

/// 천 단위 구분. 4,170 을 4170 으로 두면 규모가 안 읽힌다.
String _n(int v) => v.toString()
    .replaceAllMapped(RegExp(r'(\d)(?=(\d{3})+$)'), (m) => '${m[1]},');

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
            subtitle: '서울 전체는 초등학생이 줄고 있습니다(2025년 순유출 −188명). '
                '그런데 이 네 학군은 모두 순유입입니다. 그 격차가 학군이라는 말의 실체입니다.'),
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
              // 순유입은 이 서비스만 보여주는 숫자다. 서울 전체가 학생을
              // 잃는 동안 이 학군들이 얼마나 끌어당기는지를 한 줄로 말해 준다.
              if (region.latestTrend('elementary') case final t?) ...[
                Row(children: [
                  Icon(t.netTransfer >= 0 ? Icons.trending_up : Icons.trending_down,
                      size: 14,
                      color: t.netTransfer >= 0 ? AppColors.rising : AppColors.falling),
                  const SizedBox(width: 5),
                  Expanded(
                    child: Text(
                      '초등 순유입 ${t.netTransfer >= 0 ? "+" : ""}${t.netTransfer}명',
                      style: text.labelMedium?.copyWith(
                        color: t.netTransfer >= 0 ? AppColors.rising : AppColors.falling,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                  Text('${t.year}', style: text.bodySmall?.copyWith(fontSize: 10.5)),
                ]),
                const SizedBox(height: 6),
              ],
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

  /// 기존 Open Edu 정적 사이트는 Flutter 라우터 바깥(/openedu/)에 있다.
  /// Uri.base 로 풀면 로컬·운영 어디서든 같은 코드로 열린다.
  void _openOperatorSite() {
    launchUrl(Uri.base.resolve('openedu/'), webOnlyWindowName: '_blank');
  }

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

          // 운영사 표기. 눈에는 들어오되 화면을 가져가지 않을 만큼만.
          InkWell(
            onTap: _openOperatorSite,
            borderRadius: BorderRadius.circular(AppRadius.sm),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 2),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                Text('${Brand.name} 서비스 운영 · ',
                    style: text.bodySmall?.copyWith(color: AppColors.mist)),
                Text(Brand.operator,
                    style: text.bodySmall?.copyWith(
                      color: AppColors.goldLight,
                      fontWeight: FontWeight.w700,
                    )),
                const SizedBox(width: 5),
                const Icon(Icons.north_east, size: 11, color: AppColors.goldLight),
              ]),
            ),
          ),
          const SizedBox(height: 6),
          Text(
            '${Brand.operator}는 1:1 원어민 영어 교육 사업을 함께 운영합니다. '
            '영어 과목 항목에는 이해상충 가능성이 있어 이를 고지합니다.',
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
            TextButton(
                onPressed: _openOperatorSite,
                child: const Text('Open Edu 회사 소개')),
          ]),
          const SizedBox(height: AppSpace.md),
          Text('© ${Brand.operator} · ${Brand.domain}',
              style: text.bodySmall?.copyWith(color: AppColors.slate)),
        ]),
      ),
    );
  }
}
