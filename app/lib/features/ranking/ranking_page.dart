import '../../widgets/content_loading.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme.dart';
import '../../data/models.dart';
import '../../data/repository.dart';
import '../../widgets/academy_card.dart';
import '../../widgets/annals.dart';
import '../../widgets/subject_bar.dart';
import '../../widgets/common.dart';

class RankingPage extends ConsumerStatefulWidget {
  const RankingPage({super.key});

  @override
  ConsumerState<RankingPage> createState() => _RankingPageState();
}

/// 정렬 기준. 트리스코어가 기본이고, 나머지는 보조 축이다.
enum _Sort { score, selectivity, positive, sample }

class _RankingPageState extends ConsumerState<RankingPage> {
  /// 학술 과목인가. 정의는 `models.academicSubjects` 하나뿐이다 —
  /// 여기 따로 두면 과목이 늘 때 한쪽만 고치게 된다.
  static bool _isAcademic(String s) => isAcademicSubject(s);
  _Sort _sort = _Sort.score;
  String _query = '';
  bool _onlyVerified = false; // 공식 검증(NEIS 대조) 학원만

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(dataProvider);
    final sel = ref.watch(selectionProvider);
    final subject = sel.subject;

    return async.when(
      loading: () => const ContentLoading(),
      error: (e, _) => Center(child: Text('데이터를 불러오지 못했습니다\n$e')),
      data: (data) {
        var ranked = data.ranking(
          regionId: sel.regionId,
          subject: subject,
          gradeBand: sel.gradeBand, // 헤더 선택기와 연동
        );
        // 미확인 학원도 선택한 학년의 후보로 보여주되, 확인된 학원과
        // 같은 순위를 부여하지 않는다. 근거가 들어오면 자동으로 위 목록으로 이동한다.
        ranked = ranked
            .where((a) => a.bandsForSubject(subject).isNotEmpty)
            .toList();
        // 상세 필터. 정렬을 바꿔도 순위 숫자는 트리스코어 순위 그대로다 —
        // 정렬은 보는 방법이지 등수를 다시 매기는 것이 아니다.
        final rankOf = <String, int>{};
        for (final a in ranked.where((a) => a.scoreFor(subject).isRanked)) {
          rankOf[a.id] = rankOf.length + 1;
        }
        bool matches(Academy a) =>
            (!_onlyVerified || a.isVerified) &&
            (_query.isEmpty ||
                [
                  a.name,
                  a.displayName,
                  ...a.aliases,
                  a.address ?? '',
                ].any((v) => v.toLowerCase().contains(_query)));
        ranked = ranked.where(matches).toList();
        switch (_sort) {
          case _Sort.score:
            break;
          case _Sort.positive:
            ranked.sort(
              (a, b) => (b.scoreFor(subject).positiveRate ?? -1).compareTo(
                a.scoreFor(subject).positiveRate ?? -1,
              ),
            );
          case _Sort.sample:
            ranked.sort(
              (a, b) => b
                  .scoreFor(subject)
                  .sampleSize
                  .compareTo(a.scoreFor(subject).sampleSize),
            );
          case _Sort.selectivity:
            ranked.sort(
              (a, b) => (b.scoreFor(subject).selectivity ?? -1).compareTo(
                a.scoreFor(subject).selectivity ?? -1,
              ),
            );
        }
        final unranked = data
            .unscored(sel.regionId, subject: subject, gradeBand: sel.gradeBand)
            .where((a) => a.bandsForSubject(subject).isNotEmpty)
            .where(matches)
            .toList();
        final unknown = data
            .unconfirmedGrades(regionId: sel.regionId, subject: subject)
            .where(matches)
            .toList();
        final registryAsync = ref.watch(registryProvider);
        final registry = registryAsync.value ?? const <RegistryEntry>[];
        bool matchesRegistry(RegistryEntry r) =>
            (!_onlyVerified || r.isVerified) &&
            (_query.isEmpty ||
                r.matchesQuery(_query) ||
                (r.address ?? '').toLowerCase().contains(_query));
        final listed = data
            .registryMatches(
              registry,
              regionId: sel.regionId,
              subject: subject,
              gradeBand: sel.gradeBand,
            )
            .where(matchesRegistry)
            .toList();
        final unknownListed = data
            .registryMatches(
              registry,
              regionId: sel.regionId,
              subject: subject,
              unknownGradeOnly: true,
            )
            .where(matchesRegistry)
            .toList();
        final unscoredHits = [
          ...unranked.map(SearchHit.scored),
          ...listed.map(SearchHit.listed),
        ];
        final unknownHits = [
          ...unknown.map(SearchHit.scored),
          ...unknownListed.map(SearchHit.listed),
        ];
        final total = ranked.length + unscoredHits.length + unknownHits.length;
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
                      SectionHeader(
                        '${region?.nameKo ?? "전체 학군"} 학원 탐색',
                        kicker: spaced('학원 탐색'),
                        subtitle:
                            '선택한 학군·과목·학년의 학원을 보여줍니다. 대상 학년 미확인 학원은 별도 목록에서 확인할 수 있습니다.',
                      ),
                      TextField(
                        onChanged: (value) =>
                            setState(() => _query = value.trim().toLowerCase()),
                        decoration: const InputDecoration(
                          labelText: '학원 목록 검색',
                          hintText: '학원 이름·별칭 또는 도로명',
                          prefixIcon: Icon(Icons.search),
                        ),
                      ),
                      const SizedBox(height: 20),
                      // 과목을 고르지 않은 '전체 랭킹'은 두지 않는다.
                      // 수학 학원과 미술 학원을 한 줄에 세우면 그 순위가
                      // 무엇을 뜻하는지 설명할 수 없다.
                      SubjectBar(
                        selected: subject,
                        onChanged: (v) => setState(() {
                          if (v == null) return; // 랭킹은 '전체'를 두지 않는다
                          ref.read(selectionProvider.notifier).setSubject(v);
                          // 비학술 과목에는 없는 정렬이라 기본으로 되돌린다.
                          if (!_isAcademic(v) && (_sort == _Sort.selectivity)) {
                            _sort = _Sort.score;
                          }
                        }),
                      ),
                      const SizedBox(height: AppSpace.sm),
                      _FilterBar(
                        academic: _isAcademic(subject),
                        sort: _sort,
                        onlyVerified: _onlyVerified,
                        onSort: (v) => setState(() => _sort = v),
                        onVerified: (v) => setState(() => _onlyVerified = v),
                      ),
                      const SizedBox(height: AppSpace.md),
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              '총 $total곳 · 순위 대상 ${ranked.where((a) => a.scoreFor(subject).isRanked).length}곳 · 대상 학년 미확인 ${unknownHits.length}곳',
                              style: text.bodySmall,
                            ),
                          ),
                          TextButton(
                            onPressed: () => context.go('/method'),
                            child: const Text('평가 기준'),
                          ),
                        ],
                      ),
                      const SizedBox(height: AppSpace.md),
                    ],
                  ),
                ),
              ),
            ),
            if (total == 0 &&
                !registryAsync.isLoading &&
                !registryAsync.hasError)
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: AppSpace.xl),
                  child: Center(
                    child: Text(
                      '조건에 맞는 분석 결과가 없습니다.\n검색어나 필터를 바꿔보세요.',
                      style: text.bodyMedium,
                      textAlign: TextAlign.center,
                    ),
                  ),
                ),
              ),
            if (ranked.isNotEmpty)
              SliverList.builder(
                itemCount: ranked.length,
                itemBuilder: (context, i) => ContentWidth(
                  child: AcademyCard(
                    key: ValueKey(ranked[i].id),
                    academy: ranked[i],
                    subject: subject,
                    index: i,
                    rank: rankOf[ranked[i].id],
                  ),
                ),
              ),
            if (unscoredHits.isNotEmpty) ...[
              _listHeader(
                '함께 살펴볼 학원 · ${unscoredHits.length}곳',
                '선택한 학년의 등록 정보가 있는 학원입니다. 분석 근거 수집 중이거나 순위 대상이 아닌 곳도 포함합니다.',
              ),
              _academyLinks(unscoredHits, listed),
            ],
            if (unknownHits.isNotEmpty) ...[
              _listHeader(
                '대상 학년 미확인 · ${unknownHits.length}곳',
                '선택한 학년의 후보입니다. 학원에 대상 학년을 확인하면 학년별 순위에 반영됩니다.',
              ),
              _academyLinks(unknownHits, unknownListed),
            ],
            if (registryAsync.isLoading)
              const SliverToBoxAdapter(
                child: ContentWidth(
                  child: Padding(
                    padding: EdgeInsets.all(AppSpace.md),
                    child: Text('등록부 학원을 불러오는 중입니다.'),
                  ),
                ),
              ),
            if (registryAsync.hasError)
              SliverToBoxAdapter(
                child: ContentWidth(
                  child: TextButton.icon(
                    onPressed: () => ref.invalidate(registryProvider),
                    icon: const Icon(Icons.refresh),
                    label: const Text('등록부를 불러오지 못했습니다. 다시 시도'),
                  ),
                ),
              ),
          ],
        );
      },
    );
  }

  Widget _listHeader(String title, String subtitle) => SliverToBoxAdapter(
    child: ContentWidth(
      child: Padding(
        padding: const EdgeInsets.only(top: AppSpace.xl, bottom: AppSpace.sm),
        child: SectionHeader(title, subtitle: subtitle),
      ),
    ),
  );

  Widget _academyLinks(List<SearchHit> hits, List<RegistryEntry> registry) {
    final reasons = {for (final r in registry) r.id: r.notRanked};
    return SliverList.builder(
      itemCount: hits.length,
      itemBuilder: (context, index) {
        final hit = hits[index];
        return ContentWidth(
          child: ListTile(
            key: ValueKey(hit.id),
            title: Text(hit.name),
            subtitle: Text(
              reasons[hit.id] ?? (hit.evaluated ? '학원 정보 보기' : '등록 정보 보기'),
            ),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => context.go('/academy/${hit.id}'),
          ),
        );
      },
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
    return Row(
      children: [
        PopupMenuButton<_Sort>(
          tooltip: '정렬 기준 선택',
          initialValue: sort,
          onSelected: onSort,
          itemBuilder: (_) => [
            const PopupMenuItem(value: _Sort.score, child: Text('트리스코어순')),
            if (academic)
              const PopupMenuItem(
                value: _Sort.selectivity,
                child: Text('진입난이도순'),
              ),
            const PopupMenuItem(value: _Sort.positive, child: Text('긍정률순')),
            const PopupMenuItem(value: _Sort.sample, child: Text('근거 많은 순')),
          ],
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 12),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.sort, size: 18),
                const SizedBox(width: 8),
                Text(switch (sort) {
                  _Sort.score => '트리스코어순',
                  _Sort.selectivity => '진입난이도순',
                  _Sort.positive => '긍정률순',
                  _Sort.sample => '근거 많은 순',
                }),
                const Icon(Icons.expand_more, size: 18),
              ],
            ),
          ),
        ),
        const Spacer(),
        FilterChip(
          label: const Text('공시 확인'),
          selected: onlyVerified,
          onSelected: onVerified,
        ),
      ],
    );
  }
}
