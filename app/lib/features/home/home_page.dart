import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/brand.dart';
import '../../core/theme.dart';
import '../../data/repository.dart';
import '../../widgets/academy_card.dart';
import '../../widgets/common.dart';
import '../../widgets/subject_bar.dart';

/// 소개보다 탐색을 먼저. 학군과 과목을 고르면 학원의 성격을 바로 읽는다.
class HomePage extends ConsumerWidget {
  const HomePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final selection = ref.watch(selectionProvider);
    final notifier = ref.read(selectionProvider.notifier);
    final text = Theme.of(context).textTheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    return ref
        .watch(dataProvider)
        .when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) =>
              const Center(child: Text('데이터를 불러오지 못했습니다. 다시 시도해주세요.')),
          data: (data) {
            final academies = data.ranking(
              regionId: selection.regionId,
              subject: selection.subject,
              gradeBand: selection.gradeBand,
            );
            final region =
                data.regionById[selection.regionId]?.nameKo ?? '전체 학군';
            return ListView(
              children: [
                ContentWidth(
                  child: Padding(
                    padding: const EdgeInsets.only(top: 48, bottom: 32),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '학원을 고르는 기준이 선명해지도록',
                          style: text.labelLarge?.copyWith(
                            color: AppColors.accentOn(dark),
                          ),
                        ),
                        const SizedBox(height: 16),
                        Text(
                          '우리 아이의 다음 학원,\n특징부터 살펴보세요.',
                          style: text.displayMedium?.copyWith(
                            fontSize: MediaQuery.sizeOf(context).width < 600
                                ? 32
                                : 48,
                            height: 1.25,
                            letterSpacing: -1.8,
                          ),
                        ),
                        const SizedBox(height: 18),
                        Text(
                          '어떤 과정을 배우고, 어떤 학년이 다니는지.\n학원마다 다른 방향을 한눈에 비교하세요.',
                          style: text.bodyLarge?.copyWith(
                            color: AppColors.mutedOn(dark),
                          ),
                        ),
                        const SizedBox(height: 28),
                        Wrap(
                          spacing: 12,
                          runSpacing: 8,
                          children: [
                            FilledButton.icon(
                              onPressed: () => context.go('/rank'),
                              icon: const Icon(Icons.arrow_forward, size: 18),
                              label: const Text('학원 둘러보기'),
                            ),
                            TextButton(
                              onPressed: () => context.go('/tree'),
                              child: const Text('학습 경로 보기 →'),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
                ContentWidth(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Divider(height: 1),
                      const SizedBox(height: 28),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          for (final r in data.regions)
                            ChoiceChip(
                              label: Text(r.nameKo),
                              selected: selection.regionId == r.id,
                              showCheckmark: false,
                              onSelected: (_) => notifier.setRegion(r.id),
                            ),
                          ChoiceChip(
                            label: const Text('전체 학군'),
                            selected: selection.regionId == 'all',
                            showCheckmark: false,
                            onSelected: (_) => notifier.setRegion('all'),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      SubjectBar(
                        selected: selection.subject,
                        onChanged: (s) {
                          if (s != null) notifier.setSubject(s);
                        },
                      ),
                      const SizedBox(height: 32),
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              '$region 학원 살펴보기',
                              style: text.headlineMedium,
                            ),
                          ),
                          TextButton(
                            onPressed: () => context.go('/rank'),
                            child: const Text('전체 보기 →'),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Text('선택한 학년 기준 · 트리스코어순', style: text.bodySmall),
                      const SizedBox(height: 20),
                      if (academies.isEmpty)
                        const Padding(
                          padding: EdgeInsets.symmetric(vertical: 32),
                          child: Text('이 조건의 학원 정보를 모으고 있습니다. 학군이나 과목을 바꿔보세요.'),
                        ),
                      LayoutBuilder(
                        builder: (context, constraints) {
                          final columns = constraints.maxWidth >= 900
                              ? 3
                              : constraints.maxWidth >= 600
                              ? 2
                              : 1;
                          final width =
                              (constraints.maxWidth - (columns - 1) * 16) /
                              columns;
                          return Wrap(
                            spacing: 16,
                            runSpacing: 4,
                            children: [
                              for (final academy in academies.take(6))
                                SizedBox(
                                  width: width,
                                  child: AcademyCard(
                                    academy: academy,
                                    subject: selection.subject,
                                  ),
                                ),
                            ],
                          );
                        },
                      ),
                      const SizedBox(height: 28),
                      Container(
                        padding: const EdgeInsets.all(24),
                        decoration: BoxDecoration(
                          color: AppColors.canvasDeepOn(dark),
                          borderRadius: BorderRadius.circular(16),
                        ),
                        child: Row(
                          children: [
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    '지금 단계에서, 다음 단계로',
                                    style: text.titleMedium,
                                  ),
                                  const SizedBox(height: 8),
                                  Text(
                                    '학년별 학습 과정과 연결되는 학원을 살펴보세요.',
                                    style: text.bodySmall,
                                  ),
                                ],
                              ),
                            ),
                            const SizedBox(width: 12),
                            IconButton(
                              onPressed: () => context.go('/tree'),
                              tooltip: '학습 경로 보기',
                              icon: const Icon(Icons.arrow_forward),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 48),
                      const Divider(height: 1),
                      const SizedBox(height: 20),
                      Wrap(
                        spacing: 20,
                        runSpacing: 8,
                        crossAxisAlignment: WrapCrossAlignment.center,
                        children: [
                          Text(Brand.name, style: text.titleMedium),
                          const MethodLink(),
                          TextButton(
                            onPressed: () => context.go('/board'),
                            child: const Text('의견 나누기'),
                          ),
                          TextButton(
                            onPressed: () =>
                                launchUrl(Uri.base.resolve('openedu/')),
                            child: const Text('운영사 Open Edu'),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Text(
                        '공시와 공개된 후기를 바탕으로 정리합니다. 과정·입학 조건은 학원에 확인해주세요.',
                        style: text.bodySmall,
                      ),
                      const SizedBox(height: 8),
                      Text(
                        '운영사 Open Edu는 영어 교육 사업을 함께 운영합니다. 영어 과목에는 이해상충 가능성이 있습니다.',
                        style: text.bodySmall,
                      ),
                      const SizedBox(height: 28),
                    ],
                  ),
                ),
              ],
            );
          },
        );
  }
}

class MethodLink extends StatelessWidget {
  static const label = '산식 · 데이터 출처';
  const MethodLink({super.key});
  @override
  Widget build(BuildContext context) => TextButton(
    onPressed: () => context.go('/method'),
    child: const Text(label),
  );
}
