import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme.dart';
import '../../data/models.dart';
import '../../data/repository.dart';
import '../../widgets/academy_card.dart';
import '../../widgets/common.dart';

class RankingPage extends ConsumerStatefulWidget {
  const RankingPage({super.key});

  @override
  ConsumerState<RankingPage> createState() => _RankingPageState();
}

class _RankingPageState extends ConsumerState<RankingPage> {
  String _subject = 'math';

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(dataProvider);
    final sel = ref.watch(selectionProvider);

    return async.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text('데이터를 불러오지 못했습니다\n$e')),
      data: (data) {
        final ranked = data.ranking(
          regionId: sel.regionId,
          subject: _subject,
          schoolLevel: sel.schoolLevel,   // 헤더 휠과 연동
        );
        final unranked = data.unranked(sel.regionId);
        final region = data.regionById[sel.regionId];
        final text = Theme.of(context).textTheme;

        // 랭킹은 100곳이 넘는다. 카드마다 막대가 넷이라 한 번에 다 만들면
        // 첫 스크롤이 걸린다. 보이는 것만 만든다.
        return CustomScrollView(
          slivers: [
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.only(top: AppSpace.lg),
                child: ContentWidth(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      SectionHeader('${region?.nameKo ?? ""} 학원 랭킹',
                          subtitle:
                              '트리스코어 기준 · 표본 ${data.meta.minSampleForRank}건 미만은 순위에서 제외됩니다'),
                      ChipRow<String>(
                        options: [
                          for (final e in subjectNames.entries)
                            if (e.key != 'etc') (e.key, e.value),
                        ],
                        selected: _subject,
                        onChanged: (v) => setState(() => _subject = v),
                      ),
                      const SizedBox(height: AppSpace.lg),
                      _MethodNote(meta: data.meta),
                      const SizedBox(height: AppSpace.md),
                    ],
                  ),
                ),
              ),
            ),
            if (ranked.isEmpty)
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: AppSpace.xl),
                  child: Center(
                      child: Text('조건에 맞는 학원이 없습니다',
                          style: text.bodyMedium)),
                ),
              )
            else
              SliverList.builder(
                itemCount: ranked.length,
                itemBuilder: (context, i) => ContentWidth(
                  child: AcademyCard(
                      key: ValueKey(ranked[i].id),
                      academy: ranked[i],
                      rank: i + 1),
                ),
              ),
            if (unranked.isNotEmpty)
              SliverToBoxAdapter(
                child: ContentWidth(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const SizedBox(height: AppSpace.xl),
                      SectionHeader('표본 부족으로 순위에서 제외된 학원',
                          subtitle:
                              '유효 후기 ${data.meta.minSampleForRank}건 미만입니다. 점수가 낮아서가 아니라, '
                              '적은 표본으로 순위를 매기는 것이 부당하기 때문입니다.'),
                      Wrap(
                        spacing: AppSpace.sm,
                        runSpacing: AppSpace.sm,
                        children: [
                          for (final a in unranked)
                            ActionChip(
                              label: Text(a.displayName),
                              onPressed: () => context.go('/academy/${a.id}'),
                            ),
                        ],
                      ),
                      const SizedBox(height: AppSpace.lg),
                    ],
                  ),
                ),
              ),
          ],
        );
      },
    );
  }
}

class _MethodNote extends StatelessWidget {
  final Meta meta;
  const _MethodNote({required this.meta});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final formula = '트리스코어 = '
        '${meta.weights.entries.map((e) => '${(e.value * 100).toStringAsFixed(0)}%·${pillarNames[e.key]}').join('  +  ')}';
    // 좁은 화면에서는 한 줄에 산식과 버튼을 같이 두면 산식이 '20%·진 / 입난이도'
    // 처럼 낱말 가운데서 끊긴다. 폭이 모자라면 아래로 내린다.
    final narrow = MediaQuery.sizeOf(context).width < 640;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpace.md),
        child: narrow
            ? Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(children: [
                    const Icon(Icons.calculate_outlined,
                        size: 18, color: AppColors.slate),
                    const SizedBox(width: AppSpace.sm),
                    Expanded(child: Text(formula, style: text.bodySmall)),
                  ]),
                  Align(
                    alignment: Alignment.centerRight,
                    child: TextButton(
                      onPressed: () => context.go('/method'),
                      child: const Text('산식 전체 보기'),
                    ),
                  ),
                ],
              )
            : Row(children: [
                const Icon(Icons.calculate_outlined,
                    size: 18, color: AppColors.slate),
                const SizedBox(width: AppSpace.sm),
                Expanded(child: Text(formula, style: text.bodySmall)),
                TextButton(
                  onPressed: () => context.go('/method'),
                  child: const Text('산식 전체 보기'),
                ),
              ]),
      ),
    );
  }
}
