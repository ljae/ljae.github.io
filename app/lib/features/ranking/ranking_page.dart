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

/// 우리 아이 맞춤 조건. **데이터가 실제로 있는 축만** 둔다.
///
/// 셔틀·시설처럼 수집원에 없는 축은 만들지 않는다 — 빈 화면만 남는다.
/// 여기 것은 전부 화면의 다른 자리(진입난이도·관점·사실 카드·정원·표본)에서
/// 이미 보여 주는 값이고, 조건은 그 값을 걸러 볼 뿐 등수를 다시 매기지
/// 않는다. 값을 모르는 학원은 조건에 **안 맞는 것으로** 본다 — '모른다'
/// 를 '맞다' 로 읽으면 조건이 아무것도 거르지 않는다.
enum _Fit {
  easyEntry('레테 부담 적은', '후기에서 탈락 사례가 확인되지 않은 곳'),
  goodTeacher('선생님 평 좋은', '후기 2건 이상이 선생님을 좋게 말한 곳'),
  goodCare('관리 평 좋은', '후기 2건 이상이 관리·피드백을 좋게 말한 곳'),
  lightHomework('숙제 부담 적은', '후기 기준 숙제 하루 1시간 이내이거나 숙제량을 좋게 말한 곳'),
  small('소수정예', '등록 정원 60명 이하'),
  manyReviews('후기 많은', '유효 후기 30건 이상');

  const _Fit(this.label, this.help);
  final String label;
  final String help;

  bool matches(Academy a, String subject) {
    final score = a.scoreFor(subject);
    switch (this) {
      case _Fit.easyEntry:
        return score.sampleSize > 0 && score.selectivityTier != 'high';
      case _Fit.goodTeacher:
        return (a.aspects['강사']?.mean ?? -1) >= 0.25;
      case _Fit.goodCare:
        return (a.aspects['관리']?.mean ?? -1) >= 0.25;
      case _Fit.lightHomework:
        final hw = a.facts['fact.homework'];
        if (hw != null && hw.hasValue && hw.value != null) {
          return hw.value! <= 60;
        }
        return (a.aspects['숙제량']?.mean ?? -1) >= 0.1;
      case _Fit.small:
        return a.capacity != null && a.capacity! <= 60;
      case _Fit.manyReviews:
        return score.sampleSize >= 30;
    }
  }
}

class _RankingPageState extends ConsumerState<RankingPage> {
  String _subject = 'math';

  /// 학술 과목인가. 정의는 `models.academicSubjects` 하나뿐이다 —
  /// 여기 따로 두면 과목이 늘 때 한쪽만 고치게 된다.
  static bool _isAcademic(String s) => isAcademicSubject(s);
  _Sort _sort = _Sort.score;
  bool _onlyVerified = false; // 공식 검증(NEIS 대조) 학원만
  final Set<_Fit> _fits = {};

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
          gradeBand: sel.gradeBand, // 헤더 선택기와 연동
        );
        // 상세 필터. 정렬을 바꿔도 순위 숫자는 트리스코어 순위 그대로다 —
        // 정렬은 보는 방법이지 등수를 다시 매기는 것이 아니다.
        if (_onlyVerified) {
          ranked = ranked.where((a) => a.isVerified).toList();
        }
        final rankOf = {
          for (var i = 0; i < ranked.length; i++) ranked[i].id: i + 1,
        };
        // 맞춤 조건. 등수는 위에서 이미 정해졌다 — 조건은 걸러 볼 뿐이다.
        final before = ranked.length;
        if (_fits.isNotEmpty) {
          ranked = ranked
              .where((a) => _fits.every((f) => f.matches(a, _subject)))
              .toList();
        }
        switch (_sort) {
          case _Sort.score:
            break;
          case _Sort.positive:
            ranked.sort(
              (a, b) => (b.scoreFor(_subject).positiveRate ?? -1).compareTo(
                a.scoreFor(_subject).positiveRate ?? -1,
              ),
            );
          case _Sort.sample:
            ranked.sort(
              (a, b) => b
                  .scoreFor(_subject)
                  .sampleSize
                  .compareTo(a.scoreFor(_subject).sampleSize),
            );
          case _Sort.selectivity:
            ranked.sort(
              (a, b) => (b.scoreFor(_subject).selectivity ?? -1).compareTo(
                a.scoreFor(_subject).selectivity ?? -1,
              ),
            );
        }
        // 아직 근거가 한 건도 없는 곳. 등수 없이 아래에 이어 붙인다.
        // 지금 보고 있는 랭킹과 같은 조건으로 뽑는다 — 영어 랭킹 아래에
        // 미술 학원이 늘어서면 그 목록이 무엇인지 읽히지 않는다.
        //
        // 목록이 10곳은 되게 채운다. 순위가 3곳뿐이면 학부모는 그 구간에
        // 학원이 셋뿐인 줄 안다. 다만 채우는 쪽에 등수를 붙이지는 않는다.
        final unranked = data.unscored(
          sel.regionId,
          subject: _subject,
          gradeBand: sel.gradeBand,
        );
        // 순위 + 미수집으로도 10곳이 안 되면 등록부에서 채운다.
        // 등록부는 늦게 오는 provider 라 아직 안 왔으면 그냥 없는 셈 친다 —
        // 이것 때문에 랭킹 첫 그림을 늦출 이유는 없다.
        final registry = ref.watch(registryProvider).value ?? const [];
        final fill = data.registryFill(
          registry,
          regionId: sel.regionId,
          subject: _subject,
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
                        '${region?.nameKo ?? "전체 학군"} 학원 랭킹',
                        kicker: spaced('랭킹'),
                        // 근거가 0건인 곳만 순위에서 빠진다. 표본이 얇은
                        // 곳은 등수를 감추는 대신 두께를 함께 적는다 —
                        // 아래 '미수집' 섹션 안내와 같은 말이어야 한다.
                        subtitle: _isAcademic(_subject)
                            ? '트리스코어 기준 · 근거가 0건인 곳은 순위를 매기지 않고, '
                                  '${data.meta.minSampleForRank}건 미만은 "표본 부족"으로 '
                                  '표기합니다'
                            : '만족도·화제성 기준 · 근거가 0건인 곳은 순위를 매기지 않고, '
                                  '${data.meta.minSampleForRank}건 미만은 "표본 부족"으로 '
                                  '표기합니다. 국·영·수·과학 학원은 각 과목 랭킹에서 보세요.',
                      ),
                      // 과목을 고르지 않은 '전체 랭킹'은 두지 않는다.
                      // 수학 학원과 미술 학원을 한 줄에 세우면 그 순위가
                      // 무엇을 뜻하는지 설명할 수 없다.
                      SubjectBar(
                        selected: _subject,
                        onChanged: (v) => setState(() {
                          if (v == null) return; // 랭킹은 '전체'를 두지 않는다
                          _subject = v;
                          // 비학술 과목에는 없는 정렬이라 기본으로 되돌린다.
                          if (!_isAcademic(v) && (_sort == _Sort.selectivity)) {
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
                      const SizedBox(height: AppSpace.sm),
                      _FitBar(
                        academic: _isAcademic(_subject),
                        fits: _fits,
                        matched: ranked.length,
                        total: before,
                        onToggle: (f, on) => setState(() {
                          if (on) {
                            _fits.add(f);
                          } else {
                            _fits.remove(f);
                          }
                        }),
                      ),
                      const SizedBox(height: AppSpace.md),
                      _MethodNote(
                        meta: data.meta,
                        academic: _isAcademic(_subject),
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
                      _fits.isNotEmpty
                          ? '맞춤 조건에 맞는 학원이 없습니다. 조건은 후기에서 '
                              '확인된 것만 세므로, 조건을 하나 풀어 보세요.'
                          : '조건에 맞는 학원이 없습니다',
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
                    subject: _subject,
                    index: i,
                    rank: rankOf[ranked[i].id] ?? i + 1,
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
                        '아직 근거가 없어 순위를 매기지 않은 학원',
                        kicker: spaced('미수집'),
                        subtitle:
                            '커뮤니티 후기를 아직 한 건도 찾지 못한 곳입니다. 점수가 낮아서가 '
                            '아니라 아직 보지 않았다는 뜻이라, 등수를 붙이지 않습니다. '
                            '후기가 한 건이라도 잡히면 위 순위에 들어오고, '
                            '${data.meta.minSampleForRank}건 미만이면 "표본 부족"이라 적습니다.',
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

class _MethodNote extends StatelessWidget {
  final Meta meta;
  final bool academic;
  const _MethodNote({required this.meta, required this.academic});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    // 예체능·기타는 만족도와 화제성만 본다. 진학 경로가 없고 공시로
    // 확인할 것도 적어, 네 기둥을 다 적용하면 없는 차이를 만들어 낸다.
    // 저울 자체는 meta 가 준다 — 화면에 상수로 두지 않는다.
    final weights = meta.weightsFor(academic ? 'academic' : 'non_academic');
    final formula =
        '트리스코어 = '
        '${weights.entries.map((e) => '${(e.value * 100).toStringAsFixed(0)}%·${pillarNames[e.key]}').join('  +  ')}'
        '${academic ? '' : '  (예체능·기타는 만족도·화제성만)'}';
    // 좁은 화면에서는 한 줄에 산식과 버튼을 같이 두면 산식이 '20%·진 / 입난이도'
    // 처럼 낱말 가운데서 끊긴다. 폭이 모자라면 아래로 내린다.
    final narrow = MediaQuery.sizeOf(context).width < 640;

    final dark = Theme.of(context).brightness == Brightness.dark;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: AppColors.surfaceOn(dark),
        border: Border(
          left: BorderSide(
            color: AppColors.accentOn(dark),
            width: AppRule.stroke,
          ),
          top: BorderSide(color: AppColors.ruleOn(dark), width: AppRule.hair),
          right: BorderSide(color: AppColors.ruleOn(dark), width: AppRule.hair),
          bottom: BorderSide(
            color: AppColors.ruleOn(dark),
            width: AppRule.hair,
          ),
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(AppSpace.md),
        child: narrow
            ? Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      RailLabel(spaced('산식')),
                      const SizedBox(width: AppSpace.sm),
                      Expanded(child: Text(formula, style: text.bodySmall)),
                    ],
                  ),
                  Align(
                    alignment: Alignment.centerRight,
                    child: TextButton(
                      onPressed: () => context.go('/method'),
                      child: const Text('산식 전체 보기'),
                    ),
                  ),
                ],
              )
            : Row(
                children: [
                  RailLabel(spaced('산식')),
                  const SizedBox(width: AppSpace.sm),
                  Expanded(child: Text(formula, style: text.bodySmall)),
                  TextButton(
                    onPressed: () => context.go('/method'),
                    child: const Text('산식 전체 보기'),
                  ),
                ],
              ),
      ),
    );
  }
}

/// 우리 아이 맞춤 조건 줄.
///
/// 조건마다 무엇을 근거로 거르는지 툴팁으로 밝힌다. '관리 평 좋은' 이
/// 무엇인지 모르면 조건이 아니라 광고다.
class _FitBar extends StatelessWidget {
  final bool academic;
  final Set<_Fit> fits;
  final int matched;
  final int total;
  final void Function(_Fit, bool) onToggle;
  const _FitBar({
    required this.academic,
    required this.fits,
    required this.matched,
    required this.total,
    required this.onToggle,
  });

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Wrap(
      spacing: AppSpace.sm,
      runSpacing: AppSpace.sm,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        RailLabel(spaced('맞춤')),
        for (final f in _Fit.values)
          // 예체능·기타는 진입난이도를 채점하지 않는다. 없는 값으로 거르면
          // 전부 빠진다.
          if (academic || f != _Fit.easyEntry)
            Tooltip(
              message: f.help,
              child: RuledToggle(
                label: f.label,
                value: fits.contains(f),
                onChanged: (v) => onToggle(f, v),
              ),
            ),
        if (fits.isNotEmpty)
          Text(
            '$total곳 중 $matched곳',
            style: text.bodySmall?.copyWith(color: AppColors.mutedOn(dark)),
          ),
      ],
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
        RailLabel(spaced('정렬')),
        RuledSegments<_Sort>(
          options: [
            (_Sort.score, '트리스코어'),
            if (academic) (_Sort.selectivity, '진입난이도'),
            (_Sort.positive, '긍정률'),
            (_Sort.sample, '표본 많은'),
          ],
          selected: sort,
          onChanged: onSort,
        ),
        RuledToggle(
          label: '공식 검증만',
          value: onlyVerified,
          onChanged: onVerified,
        ),
      ],
    );
  }
}
