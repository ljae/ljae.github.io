import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/env.dart';
import '../data/academy_detail.dart';
import '../data/models.dart';
import '../data/parent_comparison.dart';
import '../data/parent_decision.dart';
import '../data/repository.dart';
import '../data/riding_plan.dart';
import '../data/source_notes.dart';
import 'contact.dart';
import 'riding_card.dart';

/// The same preference is visible and editable throughout the decision journey.
class ParentConcernBar extends ConsumerWidget {
  const ParentConcernBar({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (!Env.parentOpeningEnabled && !Env.parentCompareEnabled) {
      return const SizedBox.shrink();
    }
    final concern = ref.watch(parentConcernProvider);
    final text = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            concern == null
                ? '학원을 볼 때, 무엇이 먼저 궁금한가요?'
                : '${concernLabels[concern]}부터 살펴보고 있어요',
            style: text.titleMedium,
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 6,
            children: [
              for (final e in concernLabels.entries)
                ChoiceChip(
                  label: Text(e.value),
                  selected: concern == e.key,
                  onSelected: (on) => ref
                      .read(parentConcernProvider.notifier)
                      .choose(on ? e.key : null),
                ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            concernEffects[concern] ??
                '고민을 고르면 학원 소개에서 관련 내용을 먼저 읽고, 같은 기준으로 비교와 문의를 이어갈 수 있어요.',
          ),
        ],
      ),
    );
  }
}

class ConcernPreview extends ConsumerWidget {
  final AcademyDetail detail;
  final bool compact;
  const ConcernPreview({super.key, required this.detail, this.compact = false});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (!Env.parentOpeningEnabled && !Env.parentCompareEnabled) {
      return const SizedBox.shrink();
    }
    final concern = ref.watch(parentConcernProvider);
    if (concern == null) return const SizedBox.shrink();
    final selection = ref.watch(selectionProvider);
    final criterion = comparisonCriteria.firstWhere(
      (c) => c.id == concernCriteria[concern],
    );
    final group = ref
        .watch(sourceNotesProvider)
        .value
        ?.where((g) => g.academyId == detail.id)
        .firstOrNull;
    final note = comparisonGuidance(
      detail,
      criterion,
      selection.subject,
      group,
    ).firstOrNull;
    final excerpt = comparisonExcerpts(
      detail,
      criterion,
      subject: selection.subject,
      gradeBand: selection.gradeBand,
    ).firstOrNull;
    final plan = concern == 'riding'
        ? ref.watch(ridingPlansProvider)[ridingKey(
            detail.id,
            selection.subject,
            selection.gradeBand,
          )]
        : null;
    final text = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 12),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.primary.withValues(alpha: .045),
          border: Border(
            left: BorderSide(
              color: Theme.of(context).colorScheme.primary,
              width: 3,
            ),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '${concernLabels[concern]} · 먼저 확인할 내용',
              style: text.titleSmall,
            ),
            const SizedBox(height: 6),
            Text(
              '${gradeBandNames[selection.gradeBand]} ${subjectNames[selection.subject]} 기준',
              style: text.labelSmall,
            ),
            if (!compact) ...[
              const SizedBox(height: 8),
              Text(criterion.meaning),
            ],
            const SizedBox(height: 10),
            if (note != null) ...[
              Text(
                note.summary,
                maxLines: compact ? 3 : null,
                overflow: compact ? TextOverflow.ellipsis : null,
              ),
              const SizedBox(height: 6),
              Text(
                '공식 안내 요약 · 자료 대조 ${note.checkedAt} · 선택 학년·현재 반 적용 확인 필요',
                style: text.bodySmall,
              ),
              if (group?.caveat.isNotEmpty == true)
                Text(group!.caveat, style: text.bodySmall),
              TextButton(
                onPressed: () => openExternal(note.url),
                child: const Text('안내 원문 확인'),
              ),
            ] else if (excerpt != null) ...[
              Text(
                '“${excerpt.text}”',
                maxLines: compact ? 3 : null,
                overflow: compact ? TextOverflow.ellipsis : null,
              ),
              const SizedBox(height: 6),
              Text(
                '${excerpt.selfDescription ? '학원 게시글' : '공개 글의 경험'} · ${excerpt.scope}\n${excerpt.dateLabel}',
                style: text.bodySmall,
              ),
              TextButton(
                onPressed: () => openExternal(excerpt.url),
                child: const Text('경험 원문 확인'),
              ),
            ] else
              Text(
                concern == 'riding'
                    ? '현재 반의 셔틀·하원 조건을 확인할 자료가 부족해요. 상세에서 위치를 확인하고 이동 조건을 적어보세요.'
                    : '이 과목·학년에 연결할 ${concernLabels[concern]} 자료가 아직 부족해요. 상세와 비교에서 아래 질문을 이어서 확인하세요.',
              ),
            if (plan?.weeklyGuardianMinutes case final minutes?) ...[
              const SizedBox(height: 8),
              Text('내 메모: 보호자 주간 이동·대기 $minutes분', style: text.titleSmall),
            ],
            if (!compact || note == null && excerpt == null) ...[
              const SizedBox(height: 8),
              Text('물어볼 질문  ${concernQuestions[concern]}'),
            ],
          ],
        ),
      ),
    );
  }
}

/// Also used by registry-only detail pages: lack of reviews must not hide travel.
class AcademyDecisionSection extends ConsumerWidget {
  final AcademyDetail detail;
  const AcademyDecisionSection({super.key, required this.detail});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (!Env.parentOpeningEnabled && !Env.parentCompareEnabled) {
      return const SizedBox.shrink();
    }
    final concern = ref.watch(parentConcernProvider);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const ParentConcernBar(),
        if (concern != null) ConcernPreview(detail: detail),
        Card(
          child: ExpansionTile(
            key: ValueKey('${detail.id}/$concern'),
            initiallyExpanded: concern == 'riding',
            title: const Text('라이딩·셔틀과 하원'),
            subtitle: const Text('지점 위치 · 내 이동 조건 · 상담 질문'),
            childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 20),
            children: [RidingCard(detail: detail)],
          ),
        ),
        const SizedBox(height: 16),
      ],
    );
  }
}
