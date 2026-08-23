import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/theme.dart';
import '../data/models.dart';
import '../data/repository.dart';
import 'common.dart';

/// 랭킹 · 검색 · 단계 상세에서 공통으로 쓰는 학원 카드.
class AcademyCard extends StatelessWidget {
  final Academy academy;
  final int? rank;
  final bool showPillars;
  final String? stageContext;

  const AcademyCard({
    super.key,
    required this.academy,
    this.rank,
    this.showPillars = true,
    this.stageContext,
  });

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final score = academy.score;
    final narrow = MediaQuery.sizeOf(context).width < 560;

    return Card(
      margin: const EdgeInsets.only(bottom: AppSpace.sm),
      child: InkWell(
        borderRadius: BorderRadius.circular(AppRadius.md),
        onTap: () => context.go('/academy/${academy.id}'),
        child: Padding(
          padding: const EdgeInsets.all(AppSpace.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (rank != null) _RankBadge(rank!),
                  if (rank != null) const SizedBox(width: AppSpace.md),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Flexible(
                              child: Text(academy.displayName,
                                  style: text.titleLarge,
                                  overflow: TextOverflow.ellipsis),
                            ),
                            const SizedBox(width: AppSpace.sm),
                            if (stageContext != null &&
                                academy.isFlagshipOf(stageContext!))
                              const Chip2('대표',
                                  color: AppColors.gold,
                                  icon: Icons.star_rounded),
                          ],
                        ),
                        const SizedBox(height: 6),
                        Wrap(
                          spacing: 5,
                          runSpacing: 5,
                          crossAxisAlignment: WrapCrossAlignment.center,
                          children: [
                            for (final s in academy.subjects.take(3))
                              Chip2(subjectNames[s] ?? s,
                                  color: AppColors.subjects[s] ??
                                      AppColors.slate),
                            VerifiedChip(verified: academy.isVerified),
                            ConfidenceChip(score: score),
                            if (academy.registrationCount > 1)
                              Chip2('${academy.registrationCount}개 등록 통합',
                                  color: AppColors.slate,
                                  icon: Icons.merge_type),
                          ],
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: AppSpace.sm),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      ScoreDial(score.total, size: narrow ? 52 : 60),
                      const SizedBox(height: 2),
                      MomentumArrow(score.momentumDirection),
                      // 지난 집계 대비 순위 변동. 화살표(momentum)는 언급량
                      // 추세라 다른 값이다 — 학부모가 궁금한 건 이쪽이다.
                      _RankDelta(academyId: academy.id),
                      // 점수 하나만으로는 무엇을 뜻하는지 읽히지 않는다.
                      // '의견 낸 후기 중 긍정 N%' 는 그 자체로 읽힌다.
                      if (score.positiveRate != null) ...[
                        const SizedBox(height: 3),
                        Text('긍정 ${score.positiveRate!.round()}%',
                            style: const TextStyle(
                              fontFamily: 'Paperlogy',
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                              color: AppColors.slate,
                            )),
                      ],
                    ],
                  ),
                ],
              ),
              if (showPillars) ...[
                const SizedBox(height: AppSpace.md),
                _PillarGrid(score: score, narrow: narrow),
              ],
              if (academy.capacity != null) ...[
                const SizedBox(height: AppSpace.sm),
                Row(children: [
                  if (academy.capacity != null)
                    _Fact(Icons.groups_outlined, '정원 ${academy.capacity}명'),
                ]),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _PillarGrid extends StatelessWidget {
  final Score score;
  final bool narrow;
  const _PillarGrid({required this.score, required this.narrow});

  @override
  Widget build(BuildContext context) {
    const weights = {
      'reputation': 0.35,
      'momentum': 0.20,
      'transparency': 0.25,
      'selectivity': 0.20,
    };
    final bars = [
      for (final e in weights.entries)
        PillarBar(
            pillar: e.key,
            value: score.pillar(e.key),
            weight: e.value,
            compact: true),
    ];
    if (narrow) {
      return Column(
        children: [
          for (final b in bars)
            Padding(padding: const EdgeInsets.only(bottom: 8), child: b),
        ],
      );
    }
    return Row(
      children: [
        for (var i = 0; i < bars.length; i++) ...[
          Expanded(child: bars[i]),
          if (i != bars.length - 1) const SizedBox(width: AppSpace.md),
        ],
      ],
    );
  }
}

class _RankBadge extends StatelessWidget {
  final int rank;
  const _RankBadge(this.rank);

  @override
  Widget build(BuildContext context) {
    final top = rank <= 3;
    return Container(
      width: 38,
      height: 38,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: top
            ? AppColors.gold.withValues(alpha: 0.18)
            : AppColors.line.withValues(alpha: 0.45),
        borderRadius: BorderRadius.circular(AppRadius.sm),
      ),
      child: Text('$rank',
          style: TextStyle(
            fontFamily: 'Paperlogy',
            fontSize: 16,
            fontWeight: FontWeight.w800,
            color: top ? const Color(0xFF9A7414) : AppColors.slate,
          )),
    );
  }
}

class _Fact extends StatelessWidget {
  final IconData icon;
  final String label;
  const _Fact(this.icon, this.label);

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(right: AppSpace.md),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Icon(icon, size: 13, color: AppColors.mist),
          const SizedBox(width: 4),
          Text(label, style: Theme.of(context).textTheme.bodySmall),
        ]),
      );
}

/// 지난 집계 대비 순위 변동. 이력이 하루뿐이면 아무것도 내지 않는다.
class _RankDelta extends ConsumerWidget {
  final String academyId;
  const _RankDelta({required this.academyId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final hist = ref.watch(historyProvider).value;
    final points = hist?.forAcademy(academyId) ?? const <RankPoint>[];
    if (points.length < 2) return const SizedBox.shrink();
    final prev = points[points.length - 2].rank;
    final now = points.last.rank;
    if (prev == null || now == null || prev == now) return const SizedBox.shrink();

    final up = now < prev;                 // 숫자가 작아지면 순위가 오른 것
    return Padding(
      padding: const EdgeInsets.only(top: 2),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(up ? Icons.arrow_drop_up : Icons.arrow_drop_down,
            size: 16, color: up ? AppColors.rising : AppColors.falling),
        Text('${(prev - now).abs()}',
            style: TextStyle(
              fontFamily: 'Paperlogy',
              fontSize: 11,
              fontWeight: FontWeight.w700,
              color: up ? AppColors.rising : AppColors.falling,
            )),
      ]),
    );
  }
}
