import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/brand.dart';
import '../../core/theme.dart';
import '../../data/models.dart';
import '../../data/repository.dart';
import '../../widgets/academy_card.dart';
import '../../widgets/app_shell.dart';
import '../../widgets/common.dart';
import '../../widgets/subject_bar.dart';

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
                ColoredBox(
                  color: dark
                      ? const Color(0xFF142D27)
                      : const Color(0xFFE8F1EC),
                  child: ContentWidth(
                    child: SizedBox(
                      width: double.infinity,
                      child: Padding(
                        padding: const EdgeInsets.symmetric(vertical: 36),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              '대치 · 목동 · 반포 · 잠실',
                              style: text.labelLarge?.copyWith(
                                color: AppColors.accentOn(dark),
                              ),
                            ),
                            const SizedBox(height: 14),
                            Text(
                              '좋은 학원보다,\n우리 아이에게 맞는 학원.',
                              style: text.displayMedium?.copyWith(
                                fontSize: MediaQuery.sizeOf(context).width < 600
                                    ? 30
                                    : 46,
                                height: 1.3,
                                letterSpacing: -1.4,
                              ),
                            ),
                            const SizedBox(height: 16),
                            Text(
                              '대상 학년부터 수업 특징, 통학 위치, 후기 근거까지.\n상담 전에 필요한 정보를 한곳에서 살펴보세요.',
                              style: text.bodyLarge,
                            ),
                            const SizedBox(height: 24),
                            ConstrainedBox(
                              constraints: const BoxConstraints(maxWidth: 640),
                              child: Material(
                                color: AppColors.surfaceOn(dark),
                                borderRadius: BorderRadius.circular(14),
                                child: InkWell(
                                  borderRadius: BorderRadius.circular(14),
                                  onTap: () => showSearch(
                                    context: context,
                                    delegate: AcademySearch(),
                                  ),
                                  child: Padding(
                                    padding: const EdgeInsets.all(18),
                                    child: Row(
                                      children: [
                                        Icon(
                                          Icons.search,
                                          color: AppColors.accentOn(dark),
                                        ),
                                        const SizedBox(width: 12),
                                        Expanded(
                                          child: Text(
                                            '궁금한 학원 이름을 검색해보세요',
                                            style: text.bodyMedium,
                                          ),
                                        ),
                                        const Icon(
                                          Icons.arrow_forward,
                                          size: 20,
                                        ),
                                      ],
                                    ),
                                  ),
                                ),
                              ),
                            ),
                            const SizedBox(height: 18),
                            const Wrap(
                              spacing: 18,
                              runSpacing: 10,
                              children: [
                                _TrustLabel(
                                  Icons.fact_check_outlined,
                                  '공공 등록 정보 대조',
                                ),
                                _TrustLabel(
                                  Icons.filter_alt_outlined,
                                  '광고·중복 글 필터링',
                                ),
                                _TrustLabel(Icons.link, '후기 원문 근거 공개'),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
                ContentWidth(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 32),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('어디에서, 무엇을 배우나요?', style: text.headlineMedium),
                        const SizedBox(height: 8),
                        Text(
                          '학군과 아이의 학년을 고르면 조건에 맞는 학원을 보여드려요.',
                          style: text.bodyMedium,
                        ),
                        const SizedBox(height: 20),
                        Container(
                          padding: const EdgeInsets.all(20),
                          decoration: BoxDecoration(
                            color: AppColors.surfaceOn(dark),
                            borderRadius: BorderRadius.circular(16),
                            border: Border.all(color: AppColors.ruleOn(dark)),
                          ),
                          child: LayoutBuilder(
                            builder: (context, constraints) {
                              final columns = constraints.maxWidth >= 900
                                  ? 3
                                  : constraints.maxWidth >= 600
                                  ? 2
                                  : 1;
                              final width =
                                  (constraints.maxWidth - (columns - 1) * 24) /
                                  columns;
                              Widget group(String label, Widget child) =>
                                  SizedBox(
                                    width: width,
                                    child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Text(label, style: text.labelLarge),
                                        const SizedBox(height: 10),
                                        child,
                                      ],
                                    ),
                                  );
                              return Wrap(
                                spacing: 24,
                                runSpacing: 20,
                                children: [
                                  group(
                                    '01  학군',
                                    Wrap(
                                      spacing: 8,
                                      runSpacing: 8,
                                      children: [
                                        for (final r in data.regions)
                                          ChoiceChip(
                                            label: Text(r.nameKo),
                                            selected:
                                                selection.regionId == r.id,
                                            showCheckmark: false,
                                            onSelected: (_) =>
                                                notifier.setRegion(r.id),
                                          ),
                                        ChoiceChip(
                                          label: const Text('전체 학군'),
                                          selected: selection.regionId == 'all',
                                          showCheckmark: false,
                                          onSelected: (_) =>
                                              notifier.setRegion('all'),
                                        ),
                                      ],
                                    ),
                                  ),
                                  group(
                                    '02  아이 학년',
                                    Wrap(
                                      spacing: 8,
                                      runSpacing: 8,
                                      children: [
                                        for (final band in [
                                          'elem_low',
                                          'elem_high',
                                          'middle',
                                          'high',
                                        ])
                                          ChoiceChip(
                                            label: Text(
                                              gradeBandNames[band] ?? band,
                                            ),
                                            selected:
                                                selection.gradeBand == band,
                                            showCheckmark: false,
                                            onSelected: (_) =>
                                                notifier.setGradeBand(band),
                                          ),
                                      ],
                                    ),
                                  ),
                                  group(
                                    '03  배울 과목',
                                    SubjectBar(
                                      selected: selection.subject,
                                      onChanged: (s) {
                                        if (s != null) notifier.setSubject(s);
                                      },
                                    ),
                                  ),
                                ],
                              );
                            },
                          ),
                        ),
                        const SizedBox(height: 28),
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
                        Text(
                          '${gradeBandNames[selection.gradeBand] ?? ""} · ${subjectNames[selection.subject] ?? ""} · 트리스코어순',
                          style: text.bodySmall,
                        ),
                        const SizedBox(height: 8),
                        Text(
                          '점수는 공개된 글의 분석 결과입니다. 수업의 질이나 아이와의 적합성을 보장하지 않습니다.',
                          style: text.bodySmall,
                        ),
                        const SizedBox(height: 20),
                        if (academies.isEmpty)
                          const Padding(
                            padding: EdgeInsets.symmetric(vertical: 24),
                            child: Text(
                              '이 조건의 분석 근거를 모으고 있습니다. 전체 보기에서 등록된 학원도 확인해보세요.',
                            ),
                          ),
                        LayoutBuilder(
                          builder: (context, constraints) {
                            final columns = constraints.maxWidth >= 1000
                                ? 3
                                : constraints.maxWidth >= 660
                                ? 2
                                : 1;
                            final width =
                                (constraints.maxWidth - (columns - 1) * 16) /
                                columns;
                            return Wrap(
                              spacing: 16,
                              runSpacing: 8,
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
                        const SizedBox(height: 24),
                        Wrap(
                          spacing: 12,
                          runSpacing: 12,
                          children: [
                            FilledButton.icon(
                              onPressed: () => context.go('/rank'),
                              icon: const Icon(Icons.search, size: 18),
                              label: const Text('조건에 맞는 학원 더 보기'),
                            ),
                            OutlinedButton.icon(
                              onPressed: () => context.go('/map'),
                              icon: const Icon(Icons.map_outlined, size: 18),
                              label: const Text('학군 지도 살펴보기'),
                            ),
                            TextButton(
                              onPressed: () => context.go('/tree'),
                              child: const Text('학년별 학습 경로 →'),
                            ),
                          ],
                        ),
                        const SizedBox(height: 36),
                        Container(
                          padding: const EdgeInsets.all(24),
                          decoration: BoxDecoration(
                            color: AppColors.canvasDeepOn(dark),
                            borderRadius: BorderRadius.circular(16),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                '정보가 확실한 만큼만 보여드립니다.',
                                style: text.titleLarge,
                              ),
                              const SizedBox(height: 10),
                              Text(
                                '공식 등록 정보와 후기 분석을 구분합니다. 광고·중복 글과 지점이 불명확한 글을 걸러내고, 표본이 부족하면 순위를 매기지 않습니다.',
                                style: text.bodyMedium,
                              ),
                              const SizedBox(height: 8),
                              const MethodLink(),
                            ],
                          ),
                        ),
                        const SizedBox(height: 32),
                        const Divider(height: 1),
                        const SizedBox(height: 20),
                        Wrap(
                          spacing: 20,
                          runSpacing: 8,
                          crossAxisAlignment: WrapCrossAlignment.center,
                          children: [
                            Text(Brand.name, style: text.titleMedium),
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
                          '데이터 업데이트 ${data.meta.generatedAt.split("T").first} · 교습비·시간표·셔틀은 상담 시 확인해주세요.',
                          style: text.bodySmall,
                        ),
                        const SizedBox(height: 8),
                        Text(
                          '운영사 Open Edu는 영어 교육 사업을 함께 운영합니다. 영어 과목에는 이해상충 가능성이 있습니다.',
                          style: text.bodySmall,
                        ),
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

class _TrustLabel extends StatelessWidget {
  final IconData icon;
  final String label;
  const _TrustLabel(this.icon, this.label);
  @override
  Widget build(BuildContext context) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Icon(
        icon,
        size: 17,
        color: AppColors.accentOn(
          Theme.of(context).brightness == Brightness.dark,
        ),
      ),
      const SizedBox(width: 6),
      Flexible(
        child: Text(label, style: Theme.of(context).textTheme.bodySmall),
      ),
    ],
  );
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
