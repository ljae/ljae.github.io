import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/theme.dart';
import '../../data/parent_decision.dart';
import '../../widgets/common.dart';
import '../feedback/parent_voice_page.dart';

/// An immediately usable opening: no loading animation or scroll interception.
class ParentOpening extends ConsumerWidget {
  final VoidCallback onExplore, onSearch;
  const ParentOpening({
    super.key,
    required this.onExplore,
    required this.onSearch,
  });
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final text = Theme.of(context).textTheme;
    final concern = ref.watch(parentConcernProvider);
    return ColoredBox(
      color: AppColors.openingCanvasOn(dark),
      child: ContentWidth(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 40),
          child: LayoutBuilder(
            builder: (context, c) {
              final wide = c.maxWidth >= 850;
              final copy = Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '아이의 속도로, 우리만의 선택',
                    style: text.labelLarge?.copyWith(
                      color: AppColors.accentOn(dark),
                    ),
                  ),
                  const SizedBox(height: 20),
                  Text.rich(
                    TextSpan(
                      children: [
                        const TextSpan(text: '우리 아이의\n'),
                        TextSpan(
                          text: '다음 장을\n',
                          style: TextStyle(
                            fontWeight: FontWeight.w700,
                            decoration: TextDecoration.underline,
                            decorationColor: AppColors.openingNoteOn(dark),
                          ),
                        ),
                        const TextSpan(text: '함께 고릅니다.'),
                      ],
                    ),
                    style: text.displayMedium?.copyWith(
                      fontSize: wide ? 56 : 38,
                      height: 1.28,
                      letterSpacing: -1.8,
                    ),
                  ),
                  const SizedBox(height: 22),
                  const Text(
                    '후기의 맥락을 읽고, 몇 곳을 비교하고,\n궁금한 것은 학원에 직접 물어보세요.',
                    style: TextStyle(fontSize: 16, height: 1.9),
                  ),
                  const SizedBox(height: 24),
                  Wrap(
                    spacing: 10,
                    runSpacing: 10,
                    children: [
                      FilledButton.icon(
                        onPressed: onExplore,
                        icon: const Icon(Icons.north_east, size: 18),
                        label: const Text('학원 살펴보기'),
                      ),
                      OutlinedButton(
                        onPressed: () =>
                            showParentVoice(context, pageType: 'home'),
                        child: const Text('의견 남기기'),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  TextButton.icon(
                    onPressed: onSearch,
                    icon: const Icon(Icons.search, size: 18),
                    label: const Text('학원 이름으로 바로 찾기'),
                  ),
                ],
              );
              final notebook = Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 8,
                  vertical: 18,
                ),
                child: Stack(
                  clipBehavior: Clip.none,
                  children: [
                    Positioned.fill(
                      child: Transform.rotate(
                        angle: 3 * math.pi / 180,
                        child: DecoratedBox(
                          decoration: BoxDecoration(
                            color: AppColors.canvasDeepOn(dark),
                            border: Border.all(color: AppColors.ruleOn(dark)),
                            borderRadius: BorderRadius.circular(5),
                          ),
                        ),
                      ),
                    ),
                    Transform.rotate(
                      angle: wide ? -math.pi / 180 : 0,
                      child: Container(
                        width: double.infinity,
                        padding: const EdgeInsets.fromLTRB(22, 24, 22, 28),
                        decoration: BoxDecoration(
                          color: AppColors.openingPaperOn(dark),
                          border: Border.all(color: AppColors.ruleOn(dark)),
                          borderRadius: BorderRadius.circular(5),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Expanded(
                                  child: Text(
                                    '우리 아이를 위한 작은 메모',
                                    style: text.labelMedium,
                                  ),
                                ),
                                Text('01', style: text.headlineMedium),
                              ],
                            ),
                            const SizedBox(height: 24),
                            Text('지금, 어떤 고민이 있나요?', style: text.titleLarge),
                            const SizedBox(height: 16),
                            for (final e in parentConcerns.entries)
                              Semantics(
                                selected: concern == e.key,
                                child: Padding(
                                  padding: const EdgeInsets.only(bottom: 8),
                                  child: OutlinedButton(
                                    onPressed: () => ref
                                        .read(parentConcernProvider.notifier)
                                        .choose(
                                          concern == e.key ? null : e.key,
                                        ),
                                    style: OutlinedButton.styleFrom(
                                      alignment: Alignment.centerLeft,
                                      padding: const EdgeInsets.symmetric(
                                        vertical: 14,
                                        horizontal: 12,
                                      ),
                                      backgroundColor: concern == e.key
                                          ? AppColors.canvasDeepOn(dark)
                                          : null,
                                    ),
                                    child: Row(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.center,
                                      children: [
                                        Icon(
                                          concern == e.key
                                              ? Icons.radio_button_checked
                                              : Icons.radio_button_unchecked,
                                          size: 18,
                                        ),
                                        const SizedBox(width: 10),
                                        Expanded(child: Text(e.value)),
                                      ],
                                    ),
                                  ),
                                ),
                              ),
                            const Divider(height: 32),
                            Text('선택 전에, 한 가지 질문', style: text.labelMedium),
                            const SizedBox(height: 10),
                            Semantics(
                              liveRegion: true,
                              child: Text(
                                concernQuestions[concern] ??
                                    '우리 아이에게 어떤 수업이 필요한지, 하나씩 물어보며 알아가요.',
                                style: text.bodyLarge?.copyWith(height: 1.8),
                              ),
                            ),
                            const SizedBox(height: 18),
                            Text(
                              concernEffects[concern] ??
                                  '선택한 고민은 학원 소개에서 먼저 읽을 내용과 비교·문의로 이어집니다.',
                              style: text.bodySmall,
                            ),
                            if (concern != null) ...[
                              const SizedBox(height: 16),
                              FilledButton.icon(
                                onPressed: onExplore,
                                icon: const Icon(Icons.arrow_forward, size: 18),
                                label: const Text('이 고민으로 학원 살펴보기'),
                              ),
                            ],
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              );
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (wide)
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.center,
                      children: [
                        Expanded(flex: 6, child: copy),
                        const SizedBox(width: 48),
                        Expanded(flex: 5, child: notebook),
                      ],
                    )
                  else ...[
                    copy,
                    const SizedBox(height: 24),
                    notebook,
                  ],
                  const SizedBox(height: 36),
                  const Divider(),
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 32,
                    runSpacing: 16,
                    children: [
                      for (final label in [
                        '01  맥락을 읽고',
                        '02  나란히 비교하고',
                        '03  직접 물어봐요',
                      ])
                        Text(label, style: text.titleSmall),
                    ],
                  ),
                ],
              );
            },
          ),
        ),
      ),
    );
  }
}
