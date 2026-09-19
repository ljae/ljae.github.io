import 'package:flutter/material.dart';

import '../core/brand.dart';
import '../core/theme.dart';

/// 첫 접속의 HTML 로딩 화면과 같은 색·문구·간격을 사용한다.
class ContentLoading extends StatelessWidget {
  const ContentLoading({super.key});

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final text = Theme.of(context).textTheme;
    final reduceMotion = MediaQuery.disableAnimationsOf(context);
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 40),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
          child: Container(
            width: double.infinity,
            padding: EdgeInsets.all(
              MediaQuery.sizeOf(context).width < 380 ? 24 : 32,
            ),
            decoration: BoxDecoration(
              color: AppColors.surfaceOn(dark),
              border: Border.all(color: AppColors.ruleOn(dark)),
              borderRadius: BorderRadius.circular(AppRadius.lg),
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  Brand.tagline,
                  style: text.labelMedium?.copyWith(
                    color: AppColors.accentOn(dark),
                  ),
                ),
                const SizedBox(height: 14),
                Semantics(
                  liveRegion: true,
                  child: Text(
                    '학원 정보를\n불러오고 있어요',
                    style: text.headlineSmall?.copyWith(
                      fontSize: 25,
                      height: 1.45,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  '대상 학년부터 수업 특징, 통학 위치까지.\n상담에 필요한 정보를 준비하고 있어요.',
                  style: text.bodyMedium?.copyWith(
                    color: AppColors.mutedOn(dark),
                    height: 1.8,
                  ),
                ),
                const SizedBox(height: 28),
                ExcludeSemantics(
                  child: reduceMotion
                      ? Align(
                          alignment: Alignment.center,
                          child: FractionallySizedBox(
                            widthFactor: .35,
                            child: Container(
                              height: 3,
                              color: AppColors.accentOn(dark),
                            ),
                          ),
                        )
                      : const LinearProgressIndicator(minHeight: 3),
                ),
                const SizedBox(height: 14),
                Text(
                  '잠시만 기다려 주세요.',
                  style: text.bodySmall?.copyWith(
                    color: AppColors.mutedOn(dark),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
