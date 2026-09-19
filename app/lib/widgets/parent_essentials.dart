import 'package:flutter/material.dart';
import '../core/theme.dart';
import '../data/models.dart';

/// 확인된 후기 사실만 요약한다. 없는 수업 시간이나 비용은 추정하지 않는다.
String parentClassSummary(Academy academy) {
  final labels = <String, String>{
    'fact.class_freq': '주',
    'fact.class_minutes': '1회',
  };
  return [
    for (final entry in labels.entries)
      if (academy.facts[entry.key] case final fact?)
        if (fact.hasValue) '${entry.value} ${fact.text}',
  ].join(' · ');
}

class ParentEssentials extends StatelessWidget {
  final Academy academy;
  const ParentEssentials({super.key, required this.academy});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final grades = academy.gradeBands
        .map((g) => gradeBandNames[g] ?? g)
        .join(' · ');
    final schedule = parentClassSummary(academy);
    final items = <(IconData, String, String)>[
      (Icons.school_outlined, '대상 학년', grades.isEmpty ? '학원에 확인해주세요' : grades),
      (Icons.place_outlined, '통학 위치', academy.address ?? '주소 확인 중'),
      (Icons.payments_outlined, '교습비', '현재 제공 자료에 금액 없음 · 교재비 포함 여부도 확인'),
      (
        Icons.schedule_outlined,
        '수업 횟수·시간',
        schedule.isEmpty ? '상담 시 요일·시간표 확인' : '$schedule (후기 기준)',
      ),
    ];
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.surfaceOn(dark),
        borderRadius: BorderRadius.circular(AppRadius.lg),
        border: Border.all(color: AppColors.ruleOn(dark)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('상담 전, 먼저 확인하세요', style: text.titleLarge),
          const SizedBox(height: 18),
          LayoutBuilder(
            builder: (context, constraints) {
              final width = constraints.maxWidth >= 620
                  ? (constraints.maxWidth - 24) / 2
                  : constraints.maxWidth;
              return Wrap(
                spacing: 24,
                runSpacing: 20,
                children: [
                  for (final item in items)
                    SizedBox(
                      width: width,
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Icon(
                            item.$1,
                            size: 21,
                            color: AppColors.accentOn(dark),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(item.$2, style: text.labelLarge),
                                const SizedBox(height: 4),
                                Text(item.$3, style: text.bodyMedium),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                ],
              );
            },
          ),
        ],
      ),
    );
  }
}
