import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/theme.dart';
import '../data/models.dart';
import '../data/repository.dart';
import '../data/source_notes.dart';
import 'academy_sources_button.dart';

/// 확인된 과정과 출처가 있는 프로필만 학원의 특징으로 요약한다.
class AcademyPositioning extends ConsumerWidget {
  final Academy academy;
  final String? subject;
  const AcademyPositioning({super.key, required this.academy, this.subject});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final data = ref.watch(dataProvider).value;
    final sources = ref
        .watch(sourceNotesProvider)
        .value
        ?.where((s) => s.academyId == academy.id)
        .firstOrNull;
    final courseNote = sources?.compactNote('수업·교재', subject: subject);
    final admissionNote = sources?.compactNote('입학·레벨테스트', subject: subject);
    final stages = <String>{
      for (final id in academy.stages)
        if (['curated', 'hinted'].contains(academy.stageBasisOf(id)))
          if (data?.stageById[id] case final stage?)
            if (subject == null ||
                data?.trackById[stage.trackId]?.subject == subject)
              stage.title,
    };
    final profile = academy.profile;
    final curriculum = profile?.curriculum;
    final operatingFacts = <String>[];
    for (final key in [
      'fact.class_freq',
      'fact.class_minutes',
      'fact.homework',
    ]) {
      final fact = academy.facts[key];
      if (fact == null ||
          !fact.hasValue ||
          fact.stale ||
          fact.disputed ||
          fact.quotes.length < 2) {
        continue;
      }
      final prefix = key == 'fact.class_freq'
          ? '주 '
          : key == 'fact.homework'
          ? '하루 과제 '
          : '수업 ';
      operatingFacts.add('$prefix${fact.text}');
    }
    final hasDirection =
        courseNote != null ||
        stages.isNotEmpty ||
        (curriculum != null &&
            curriculum.quotes.isNotEmpty &&
            curriculum.note != null);
    final direction =
        courseNote?.shortSummary ??
        (stages.isNotEmpty
            ? stages.take(2).join(' · ')
            : curriculum != null &&
                  curriculum.quotes.isNotEmpty &&
                  curriculum.note != null
            ? curriculum.note!
            : operatingFacts.isNotEmpty
            ? '${operatingFacts.take(2).join(' · ')} · 후기 기준'
            : '세부 과정 확인 중');
    final entry = academy.entryTags
        .map((t) => entryTagLabels[t])
        .whereType<String>()
        .take(2)
        .join(' · ');
    final levelTest = profile?.levelTest;
    final entrySignal = switch (academy.scoreFor(subject).selectivityTier) {
      'high' => '진입 난이도 높음 · 후기 기준',
      'medium' => '진입 난이도 중간 · 후기 기준',
      'mentioned' => '입학 테스트·대기 언급 있음',
      _ => '학원에 직접 문의',
    };
    final admissions =
        admissionNote?.shortSummary ??
        (entry.isNotEmpty
            ? '$entry · 후기 기준'
            : levelTest != null && levelTest.quotes.isNotEmpty
            ? levelTest.note ?? entrySignal
            : entrySignal);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        LayoutBuilder(
          builder: (context, constraints) {
            final cells = [
              _Fact(
                label: courseNote == null
                    ? (hasDirection ? '학습 방향' : '수업 특징')
                    : '학습 방향 · ${courseNote.sourceLabel}',
                value: direction,
              ),
              _Fact(
                label: admissionNote == null
                    ? '입학 정보'
                    : '입학 정보 · ${admissionNote.sourceLabel}',
                value: admissions,
              ),
            ];
            if (constraints.maxWidth < 420) {
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [cells[0], const SizedBox(height: 14), cells[1]],
              );
            }
            return Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(child: cells[0]),
                const SizedBox(width: 24),
                Expanded(child: cells[1]),
              ],
            );
          },
        ),
        if (sources != null)
          AcademySourcesButton(sources: sources, subject: subject),
      ],
    );
  }
}

class _Fact extends StatelessWidget {
  final String label;
  final String value;
  const _Fact({required this.label, required this.value});
  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: text.labelSmall?.copyWith(color: AppColors.mutedOn(dark)),
        ),
        const SizedBox(height: 5),
        Text(
          value,
          style: text.bodyMedium?.copyWith(fontWeight: FontWeight.w500),
        ),
      ],
    );
  }
}
