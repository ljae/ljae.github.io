import 'package:flutter/material.dart';

import '../core/theme.dart';
import 'annals.dart';

/// 「實錄」 조작부 — 고르고 켜는 것들.
///
/// [annals.dart] 의 조형 위에 올라가는 부품이라 파일만 갈라 두었다.
/// Material 기본 컨트롤(`SegmentedButton`·`FilterChip`·`ActionChip`)은
/// 전부 양 끝이 알약이라, 각진 판면에서 **그것만 둥글어** 혼자 튄다.
/// 그래서 같은 일을 하는 것을 계선으로 다시 그렸다.

/// 계선으로 나눈 구간 선택. **한 칸짜리 표**로 그린다:
/// 바깥은 계선 하나, 칸 사이는 세로 계선, 고른 칸만 먹으로 채운다.
class RuledSegments<T> extends StatelessWidget {
  final List<(T value, String label)> options;
  final T selected;
  final ValueChanged<T> onChanged;

  const RuledSegments({
    super.key,
    required this.options,
    required this.selected,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final ink = AppColors.inkOn(dark);

    return DecoratedBox(
      decoration: BoxDecoration(
        border: Border.all(color: AppColors.ruleOn(dark), width: AppRule.thin),
        borderRadius: BorderRadius.circular(AppRadius.sm),
      ),
      child: IntrinsicHeight(
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            for (var i = 0; i < options.length; i++) ...[
              if (i != 0) const Rule.vertical(),
              _Segment(
                label: options[i].$2,
                selected: options[i].$1 == selected,
                ink: ink,
                dark: dark,
                onTap: () => onChanged(options[i].$1),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _Segment extends StatelessWidget {
  final String label;
  final bool selected;
  final Color ink;
  final bool dark;
  final VoidCallback onTap;

  const _Segment({
    required this.label,
    required this.selected,
    required this.ink,
    required this.dark,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      child: AnimatedContainer(
        duration: AppMotion.quick,
        padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 9),
        color: selected ? ink : Colors.transparent,
        child: Text(
          label,
          style: TextStyle(
            fontFamily: 'Paperlogy',
            fontSize: 12.5,
            fontWeight: selected ? FontWeight.w800 : FontWeight.w500,
            letterSpacing: -0.3,
            color: selected
                ? (dark ? AppColors.ink : AppColors.cream)
                : AppColors.mutedOn(dark),
          ),
        ),
      ),
    );
  }
}

/// 켜고 끄는 하나. 체크 표시는 **활자 기호**를 쓴다 — 아이콘 폰트를
/// 섞으면 글자와 기준선이 어긋나 줄이 흔들린다.
class RuledToggle extends StatelessWidget {
  final String label;
  final bool value;
  final ValueChanged<bool> onChanged;

  const RuledToggle({
    super.key,
    required this.label,
    required this.value,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final accent = AppColors.accentOn(dark);

    return InkWell(
      onTap: () => onChanged(!value),
      child: AnimatedContainer(
        duration: AppMotion.quick,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
        decoration: BoxDecoration(
          color: value
              ? accent.withValues(alpha: dark ? 0.14 : 0.07)
              : Colors.transparent,
          borderRadius: BorderRadius.circular(AppRadius.sm),
          border: Border.all(
            color: value ? accent : AppColors.ruleOn(dark),
            width: value ? AppRule.thin : AppRule.hair,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              value ? '✓' : '□',
              style: TextStyle(
                fontSize: 11.5,
                height: 1.3,
                color: value ? accent : AppColors.mutedOn(dark),
              ),
            ),
            const SizedBox(width: 6),
            Text(
              label,
              style: TextStyle(
                fontFamily: 'Paperlogy',
                fontSize: 12.5,
                fontWeight: value ? FontWeight.w800 : FontWeight.w500,
                letterSpacing: -0.3,
                color: value ? AppColors.inkOn(dark) : AppColors.mutedOn(dark),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 이름만 늘어놓는 자리에 쓰는 각진 이름표.
///
/// 등수도 점수도 없는 목록이라 **아무 값도 붙이지 않는다.** 여기에
/// 숫자를 하나라도 붙이면 순위가 있는 것처럼 읽힌다.
class NameChip extends StatelessWidget {
  final String label;
  final VoidCallback onTap;

  /// 등록부에서 채운 곳. 앞에 말줄임표를 세워 '수집한 적 없음'을 표시한다.
  final bool tentative;

  const NameChip({
    super.key,
    required this.label,
    required this.onTap,
    this.tentative = false,
  });

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    return InkWell(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 8),
        decoration: BoxDecoration(
          color: AppColors.surfaceOn(dark),
          borderRadius: BorderRadius.circular(AppRadius.sm),
          border: Border.all(
            color: AppColors.ruleOn(dark),
            width: AppRule.hair,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (tentative) ...[
              Text(
                '…',
                style: TextStyle(
                  fontSize: 12,
                  height: 1.2,
                  color: AppColors.mutedOn(dark),
                ),
              ),
              const SizedBox(width: 5),
            ],
            Text(
              label,
              style: TextStyle(
                fontFamily: 'Paperlogy',
                fontSize: 13,
                fontWeight: FontWeight.w500,
                letterSpacing: -0.3,
                color: AppColors.inkOn(dark),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
