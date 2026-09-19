import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/theme.dart';
import '../data/models.dart';
import '../data/repository.dart';
import 'common.dart';
import 'academy_positioning.dart';
import 'parent_essentials.dart';

/// 학원의 분야·대상·과정을 먼저 읽고 점수는 보조 정보로 확인한다.
class AcademyCard extends StatelessWidget {
  final Academy academy;
  final int? rank;
  final bool showPillars;
  final String? stageContext;
  final String? subject;
  final String? stageBasis;
  final int index;
  const AcademyCard({
    super.key,
    required this.academy,
    this.rank,
    this.showPillars = false,
    this.stageContext,
    this.subject,
    this.stageBasis,
    this.index = 0,
  });

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final score = academy.scoreFor(subject);
    final subjects = orderedSubjects(
      academy.subjects,
    ).map((s) => subjectNames[s]).whereType<String>().take(3).join(' · ');
    final grades = academy.gradeBands
        .map((g) => gradeBandNames[g])
        .whereType<String>()
        .join(' · ');
    final radius = BorderRadius.circular(16);
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Material(
        color: AppColors.surfaceOn(dark),
        shape: RoundedRectangleBorder(
          borderRadius: radius,
          side: BorderSide(color: AppColors.ruleOn(dark)),
        ),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: () => context.go('/academy/${academy.id}'),
          child: Padding(
            padding: const EdgeInsets.all(22),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            subjects.isEmpty ? '과목 확인 중' : subjects,
                            style: text.labelMedium?.copyWith(
                              color: AppColors.accentOn(dark),
                            ),
                          ),
                          const SizedBox(height: 8),
                          Text(academy.displayName, style: text.titleLarge),
                        ],
                      ),
                    ),
                    const SizedBox(width: 12),
                    if (rank != null && score.isRanked)
                      Text(
                        '$rank위',
                        style: text.titleMedium?.copyWith(
                          color: AppColors.mutedOn(dark),
                        ),
                      ),
                    const SizedBox(width: 8),
                    Icon(
                      Icons.arrow_outward_rounded,
                      size: 18,
                      color: AppColors.mutedOn(dark),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  grades.isEmpty ? '대상 학년 확인 중' : grades,
                  style: text.bodySmall,
                ),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [VerifiedChip(verified: academy.isVerified)],
                ),
                const SizedBox(height: 12),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(
                      Icons.place_outlined,
                      size: 17,
                      color: AppColors.mutedOn(dark),
                    ),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        academy.address ?? '주소 확인 중',
                        style: text.bodySmall,
                      ),
                    ),
                  ],
                ),
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 16),
                  child: Divider(height: 1),
                ),
                AcademyPositioning(academy: academy, subject: subject),
                if (academy.profile?.oneLiner case final line?) ...[
                  const SizedBox(height: 12),
                  Text(
                    line,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: text.bodySmall?.copyWith(
                      color: AppColors.mutedOn(dark),
                    ),
                  ),
                ],
                const SizedBox(height: 16),
                Text('교습비 · 교재비는 상담 시 확인', style: text.bodySmall),
                if (parentClassSummary(academy).isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Text(parentClassSummary(academy), style: text.bodySmall),
                ],
                const SizedBox(height: 20),
                Wrap(
                  spacing: 16,
                  runSpacing: 6,
                  children: [
                    Text(
                      score.hasTotal
                          ? '트리스코어 ${score.total.toStringAsFixed(1)}'
                          : '평가 자료 수집 중',
                      style: text.labelSmall,
                    ),
                    Text('분석 근거 ${score.sampleSize}건', style: text.labelSmall),
                    if (!score.isRanked && score.sampleSize > 0)
                      Text('순위 산정 제외', style: text.labelSmall),
                    if (StageMatch.labelFor(stageBasis) case final label?)
                      Text(label, style: text.labelSmall),
                  ],
                ),
                if (showPillars && score.sampleSize > 0) ...[
                  const SizedBox(height: 16),
                  AcademyPillarGrid(
                    score: score,
                    narrow: MediaQuery.sizeOf(context).width < 560,
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// 카드의 기둥 막대. 가중치는 meta.json 에서 읽는다.
///
/// 예전에는 여기에 0.20/0.25 가 상수로 박혀 있었다. 산식을 0.35 로 바꾼
/// 뒤에도 카드는 옛 값을 그대로 보여줬다 — 상세의 35%와 목록의 20%가
/// 어긋나 있었던 이유다.
class AcademyPillarGrid extends ConsumerWidget {
  final Score score;
  final bool narrow;
  const AcademyPillarGrid({
    super.key,
    required this.score,
    this.narrow = false,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final meta = ref.watch(dataProvider).value?.meta;
    // 예체능·기타는 투명성·진입난이도를 채점하지 않는다. 값이 없는
    // 기둥을 0으로 그리면 '점수가 나쁘다'로 읽힌다. 저울은 meta 가 준다 —
    // 화면이 상수로 들고 있으면 산식을 바꿔도 여기만 옛 값으로 남는다.
    final weights = meta?.weightsFor(score.subjectGroup) ?? const {};
    if (weights.isEmpty) return const SizedBox.shrink();
    return PillarWeightBars(score: score, weights: weights, stacked: narrow);
  }
}
