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

/// 정렬 기준. 트리스코어가 기본이고, 나머지는 보조 축이다.
enum _Sort { score, selectivity, positive, sample }

class _RankingPageState extends ConsumerState<RankingPage> {
  String _subject = 'math';

  /// 학술 과목인가. 예체능·기타는 만족도·화제성만 본다.
  static bool _isAcademic(String s) =>
      const {'math', 'english', 'korean', 'science'}.contains(s);
  _Sort _sort = _Sort.score;
  bool _onlyVerified = false;  // 공식 검증(NEIS 대조) 학원만

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(dataProvider);
    final sel = ref.watch(selectionProvider);

    return async.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text('데이터를 불러오지 못했습니다\n$e')),
      data: (data) {
        var ranked = data.ranking(
          regionId: sel.regionId,
          subject: _subject,
          gradeBand: sel.gradeBand,   // 헤더 선택기와 연동
        );
        // 상세 필터. 정렬을 바꿔도 순위 숫자는 트리스코어 순위 그대로다 —
        // 정렬은 보는 방법이지 등수를 다시 매기는 것이 아니다.
        if (_onlyVerified) {
          ranked = ranked.where((a) => a.isVerified).toList();
        }
        final rankOf = {
          for (var i = 0; i < ranked.length; i++) ranked[i].id: i + 1,
        };
        switch (_sort) {
          case _Sort.score:
            break;
          case _Sort.positive:
            ranked.sort((a, b) => (b.score.positiveRate ?? -1)
                .compareTo(a.score.positiveRate ?? -1));
          case _Sort.sample:
            ranked.sort(
                (a, b) => b.score.sampleSize.compareTo(a.score.sampleSize));
          case _Sort.selectivity:
            ranked.sort((a, b) => (b.score.selectivity ?? -1)
                .compareTo(a.score.selectivity ?? -1));
        }
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
                      // 과목을 고르지 않은 '전체 랭킹'은 두지 않는다.
                      // 수학 학원과 미술 학원을 한 줄에 세우면 그 순위가
                      // 무엇을 뜻하는지 설명할 수 없다.
                      ChipRow<String>(
                        options: [
                          for (final e in subjectNames.entries) (e.key, e.value),
                        ],
                        selected: _subject,
                        onChanged: (v) => setState(() {
                          _subject = v;
                          // 비학술 과목에는 없는 정렬이라 기본으로 되돌린다.
                          if (!_isAcademic(v) &&
                              (_sort == _Sort.selectivity)) {
                            _sort = _Sort.score;
                          }
                        }),
                      ),
                      const SizedBox(height: AppSpace.sm),
                      _FilterBar(
                        academic: _isAcademic(_subject),
                        sort: _sort,
                        onlyVerified: _onlyVerified,
                        onSort: (v) => setState(() => _sort = v),
                        onVerified: (v) => setState(() => _onlyVerified = v),
                      ),
                      const SizedBox(height: AppSpace.md),
                      _MethodNote(
                          meta: data.meta, academic: _isAcademic(_subject)),
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
                      rank: rankOf[ranked[i].id] ?? i + 1),
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
  final bool academic;
  const _MethodNote({required this.meta, required this.academic});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    // 예체능·기타는 만족도와 화제성만 본다. 진학 경로가 없고 공시로
    // 확인할 것도 적어, 네 기둥을 다 적용하면 없는 차이를 만들어 낸다.
    final weights = academic
        ? meta.weights
        : const {'reputation': 0.6, 'momentum': 0.4};
    final formula = '트리스코어 = '
        '${weights.entries.map((e) => '${(e.value * 100).toStringAsFixed(0)}%·${pillarNames[e.key]}').join('  +  ')}'
        '${academic ? '' : '  (예체능·기타는 만족도·화제성만)'}';
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

/// 상세 필터 줄. 데이터가 실제로 있는 축만 내놓는다 —
/// 시설·셔틀 같은 항목은 수집원(NEIS)에 없으므로 필터로 만들지 않는다.
/// 없는 데이터로 필터를 만들면 빈 화면만 남는다.
class _FilterBar extends StatelessWidget {
  final bool academic;
  final _Sort sort;
  final bool onlyVerified;
  final ValueChanged<_Sort> onSort;
  final ValueChanged<bool> onVerified;
  const _FilterBar({
    required this.academic,
    required this.sort,
    required this.onlyVerified,
    required this.onSort,
    required this.onVerified,
  });

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: AppSpace.sm,
      runSpacing: AppSpace.sm,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        SegmentedButton<_Sort>(
          showSelectedIcon: false,
          style: const ButtonStyle(
            visualDensity: VisualDensity.compact,
            tapTargetSize: MaterialTapTargetSize.shrinkWrap,
          ),
          segments: [
            const ButtonSegment(value: _Sort.score, label: Text('트리스코어')),
            if (academic)
              const ButtonSegment(
                  value: _Sort.selectivity, label: Text('진입난이도')),
            const ButtonSegment(value: _Sort.positive, label: Text('긍정률')),
            const ButtonSegment(value: _Sort.sample, label: Text('표본 많은')),
          ],
          selected: {sort},
          onSelectionChanged: (v) => onSort(v.first),
        ),
        FilterChip(
          label: const Text('공식 검증만'),
          selected: onlyVerified,
          onSelected: onVerified,
        ),
      ],
    );
  }
}
