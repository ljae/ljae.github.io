import '../../widgets/content_loading.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme.dart';
import '../../data/models.dart';
import '../../data/repository.dart';
import '../../widgets/academy_card.dart';
import '../../widgets/annals.dart';
import '../../widgets/annals_controls.dart';
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
        // 아직 근거가 한 건도 없는 곳. 등수 없이 아래에 이어 붙인다.
        // 지금 보고 있는 랭킹과 같은 조건으로 뽑는다 — 영어 랭킹 아래에
        // 미술 학원이 늘어서면 그 목록이 무엇인지 읽히지 않는다.
        //
        // 목록이 10곳은 되게 채운다. 순위가 3곳뿐이면 학부모는 그 구간에
        // 학원이 셋뿐인 줄 안다. 다만 채우는 쪽에 등수를 붙이지는 않는다.
        final unranked = data
            .unscored(sel.regionId, subject: subject, gradeBand: sel.gradeBand)
            .where(matches)
            .toList();
        // 순위 + 미수집으로도 10곳이 안 되면 등록부에서 채운다.
        // 등록부는 늦게 오는 provider 라 아직 안 왔으면 그냥 없는 셈 친다 —
        // 이것 때문에 랭킹 첫 그림을 늦출 이유는 없다.
        final registry = ref.watch(registryProvider).value ?? const [];
        final fill = (_query.isNotEmpty || _onlyVerified)
            ? <RegistryEntry>[]
            : data.registryFill(
                registry,
                regionId: sel.regionId,
                subject: subject,
                gradeBand: sel.gradeBand,
                have: ranked.length + unranked.length,
              );
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
                            '선택한 과목·학년의 공시 근거가 있는 학원만 표시합니다. 대상 학년 미확인 학원은 전체 학원 검색에서 찾을 수 있습니다.',
                      ),
                      TextField(
                        onChanged: (value) =>
                            setState(() => _query = value.trim().toLowerCase()),
                        decoration: const InputDecoration(
                          labelText: '선택한 조건 안에서 검색',
                          hintText: '학원 이름 또는 도로명',
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
                              '${ranked.length}곳 · 순위 대상 ${ranked.where((a) => a.scoreFor(subject).isRanked).length}곳 · 나머지는 순위 보류',
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
            if (ranked.isEmpty)
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
              )
            else
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
            if (unranked.isNotEmpty || fill.isNotEmpty)
              SliverToBoxAdapter(
                child: ContentWidth(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const SizedBox(height: AppSpace.xl),
                      SectionHeader(
                        '함께 살펴볼 학원',
                        kicker: spaced('미수집'),
                        subtitle:
                            '분석 근거를 모으고 있는 학원입니다. 이름을 누르면 등록 정보를 볼 수 있습니다.',
                      ),
                      Wrap(
                        spacing: AppSpace.sm,
                        runSpacing: AppSpace.sm,
                        children: [
                          for (final a in unranked)
                            NameChip(
                              label: a.displayName,
                              onTap: () => context.go('/academy/${a.id}'),
                            ),
                          // 등록부에서 채운 곳. 수집한 적이 없어 상세에
                          // 보여줄 것이 등록 정보뿐이라 눌러도 그쪽으로 간다.
                          //
                          // ★ '아직 안 봤다' 와 '이 랭킹의 대상이 아니다' 는
                          //   다른 상태다. 학습지·방문수업 프랜차이즈는
                          //   낮은 평가를 받은 것이 아니라 줄에 세우지
                          //   않는 것이므로 그 이유를 함께 적는다.
                          for (final r in fill)
                            NameChip(
                              label: r.notRanked == null
                                  ? r.displayName
                                  : '${r.displayName} · ${r.notRanked}',
                              tentative: true,
                              onTap: () => context.go('/academy/${r.id}'),
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
