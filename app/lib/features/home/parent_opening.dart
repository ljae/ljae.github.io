import 'package:flutter/material.dart';
import '../../core/theme.dart';
import '../../widgets/common.dart';

/// Start with actions the available academy data can actually support.
class ParentOpening extends StatelessWidget {
  final VoidCallback onExplore, onSearch;
  const ParentOpening({
    super.key,
    required this.onExplore,
    required this.onSearch,
  });

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final text = Theme.of(context).textTheme;
    return ColoredBox(
      color: AppColors.openingCanvasOn(dark),
      child: ContentWidth(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 28),
          child: LayoutBuilder(
            builder: (context, constraints) {
              final wide = constraints.maxWidth >= 850;
              final introduction = Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '대치 · 목동 · 반포 · 잠실',
                    style: text.labelLarge?.copyWith(
                      color: AppColors.accentOn(dark),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    '광고는 거르고,\n진짜 기록만 남겼습니다.',
                    style: text.displayMedium?.copyWith(
                      fontSize: wide ? 44 : 30,
                      height: 1.3,
                      letterSpacing: -1.2,
                    ),
                  ),
                  const SizedBox(height: 8),
                  // 머리 위 학군 줄과 같은 글자 크기(labelLarge). 주묵은
                  // 그 줄이 이미 쓰므로 여기는 먹빛 회색으로 낮춘다.
                  Text(
                    '대한민국 학원 데이터 플랫폼, 학원실록',
                    style: text.labelLarge?.copyWith(
                      color: AppColors.mutedOn(dark),
                    ),
                  ),
                  const SizedBox(height: 14),
                  Text(
                    '학년과 과목으로 찾고, 위치와 후기 근거를 살펴보세요.\n관심 있는 학원은 최대 3곳까지 나란히 비교할 수 있어요.',
                    style: text.bodyLarge?.copyWith(height: 1.7),
                  ),
                  const SizedBox(height: 20),
                  FilledButton.icon(
                    onPressed: onExplore,
                    icon: const Icon(Icons.tune, size: 18),
                    label: const Text('학원 살펴보기'),
                  ),
                ],
              );
              final search = Container(
                width: double.infinity,
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: AppColors.surfaceOn(dark),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: AppColors.ruleOn(dark)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('알아보고 있는 학원이 있나요?', style: text.titleMedium),
                    const SizedBox(height: 8),
                    Text('학원 이름으로 바로 찾아보세요.', style: text.bodyMedium),
                    const SizedBox(height: 16),
                    OutlinedButton.icon(
                      onPressed: onSearch,
                      icon: const Icon(Icons.search, size: 20),
                      label: const Text('학원 이름으로 바로 찾기'),
                    ),
                  ],
                ),
              );
              if (wide) {
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    Expanded(flex: 7, child: introduction),
                    const SizedBox(width: 40),
                    Expanded(flex: 5, child: search),
                  ],
                );
              }
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  introduction,
                  const SizedBox(height: 20),
                  TextButton.icon(
                    onPressed: onSearch,
                    icon: const Icon(Icons.search, size: 20),
                    label: const Text('학원 이름으로 바로 찾기'),
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
