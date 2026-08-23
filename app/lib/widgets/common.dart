import 'package:flutter/material.dart';

import '../core/theme.dart';
import '../data/models.dart';

/// 최대폭 제한 + 좌우 여백. 모든 페이지 본문이 이걸 통과한다.
class ContentWidth extends StatelessWidget {
  final Widget child;
  final double max;
  const ContentWidth({super.key, required this.child, this.max = AppSpace.maxContent});

  @override
  Widget build(BuildContext context) {
    final pad = MediaQuery.sizeOf(context).width < 640 ? AppSpace.md : AppSpace.lg;
    return Center(
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: max),
        child: Padding(
            padding: EdgeInsets.symmetric(horizontal: pad), child: child),
      ),
    );
  }
}

/// 데모 모드 배너. 실명 학원에 합성 점수가 붙어 있음을 반드시 알린다.
class DemoBanner extends StatelessWidget {
  final Meta meta;
  const DemoBanner({super.key, required this.meta});

  @override
  Widget build(BuildContext context) {
    if (!meta.isDemo) return const SizedBox.shrink();
    return Container(
      width: double.infinity,
      color: AppColors.gold.withValues(alpha: 0.16),
      padding: const EdgeInsets.symmetric(vertical: 10, horizontal: AppSpace.md),
      child: Center(
        child: Text(
          '샘플 데이터로 동작 중입니다 — 표시된 점수는 합성값이며 실제 평가가 아닙니다.',
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: const Color(0xFF7A5B10), fontWeight: FontWeight.w600),
        ),
      ),
    );
  }
}

class Chip2 extends StatelessWidget {
  final String label;
  final Color color;
  final IconData? icon;
  final bool filled;
  const Chip2(this.label,
      {super.key, required this.color, this.icon, this.filled = false});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: EdgeInsets.symmetric(
          horizontal: icon == null ? 9 : 8, vertical: 4.5),
      decoration: BoxDecoration(
        color: filled ? color : color.withValues(alpha: 0.11),
        borderRadius: BorderRadius.circular(AppRadius.pill),
        border: filled ? null : Border.all(color: color.withValues(alpha: 0.28)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) Icon(icon, size: 12, color: filled ? Colors.white : color),
          if (icon != null) const SizedBox(width: 4),
          Text(label,
              style: TextStyle(
                fontFamily: 'Paperlogy',
                fontSize: 11.5,
                fontWeight: FontWeight.w600,
                letterSpacing: -0.1,
                color: filled ? Colors.white : color,
              )),
        ],
      ),
    );
  }
}

/// 검증됨 / 추정 배지 — 사실과 의견을 시각적으로 분리하는 장치.
class VerifiedChip extends StatelessWidget {
  final bool verified;
  const VerifiedChip({super.key, required this.verified});

  @override
  Widget build(BuildContext context) => verified
      ? const Chip2('공식 검증',
          color: AppColors.verified, icon: Icons.verified_rounded)
      : const Chip2('샘플',
          color: AppColors.estimated, icon: Icons.science_outlined);
}

class ConfidenceChip extends StatelessWidget {
  final Score score;
  const ConfidenceChip({super.key, required this.score});

  @override
  Widget build(BuildContext context) {
    final color = switch (score.confidence) {
      'high' => AppColors.verified,
      'medium' => AppColors.slate,
      _ => AppColors.estimated,
    };
    return Chip2('${score.confidenceLabel} · ${score.sampleSize}건', color: color);
  }
}

/// 큰 점수 원형 표시
class ScoreDial extends StatelessWidget {
  final double value;
  final double size;
  final bool showLabel;
  const ScoreDial(this.value,
      {super.key, this.size = 64, this.showLabel = true});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: Stack(
        alignment: Alignment.center,
        children: [
          SizedBox.expand(
            child: CircularProgressIndicator(
              value: value / 100,
              strokeWidth: size * 0.085,
              backgroundColor: AppColors.line.withValues(alpha: 0.55),
              valueColor: AlwaysStoppedAnimation(_colorFor(value)),
              strokeCap: StrokeCap.round,
            ),
          ),
          Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(value.toStringAsFixed(0),
                  style: TextStyle(
                    fontFamily: 'Paperlogy',
                    fontSize: size * 0.34,
                    fontWeight: FontWeight.w800,
                    height: 1.0,
                    letterSpacing: -0.8,
                  )),
              if (showLabel)
                Text('트리스코어',
                    style: TextStyle(
                      fontFamily: 'Paperlogy',
                      fontSize: size * 0.125,
                      color: AppColors.mist,
                      height: 1.4,
                    )),
            ],
          ),
        ],
      ),
    );
  }

  static Color _colorFor(double v) {
    if (v >= 70) return AppColors.navyBright;
    if (v >= 55) return AppColors.reputation;
    if (v >= 45) return AppColors.momentum;
    return AppColors.slate;
  }
}

/// 기둥별 막대. 랭킹·상세에서 동일한 시각 언어를 유지한다.
class PillarBar extends StatelessWidget {
  final String pillar;
  final double value;
  final double weight;
  final bool compact;

  /// true 면 가중치를 숫자로 함께 적는다. 상세 화면처럼 한 번만
  /// 나오는 곳에서만 켠다 — 목록에서는 카드마다 같은 %가 반복돼
  /// 읽히지 않고, 폭이 이미 그 정보를 담고 있다.
  final bool showWeight;

  const PillarBar({
    super.key,
    required this.pillar,
    required this.value,
    required this.weight,
    this.compact = false,
    this.showWeight = false,
  });

  @override
  Widget build(BuildContext context) {
    final color = AppColors.pillars[pillar] ?? AppColors.slate;
    final text = Theme.of(context).textTheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(pillarIcons[pillar], size: compact ? 12 : 14, color: color),
            const SizedBox(width: 5),
            Flexible(
              child: Text(pillarNames[pillar] ?? pillar,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: text.labelMedium?.copyWith(
                      color: color, fontWeight: FontWeight.w600)),
            ),
            if (showWeight) ...[
              const SizedBox(width: 5),
              Text('${(weight * 100).toStringAsFixed(0)}%',
                  style: text.bodySmall?.copyWith(fontSize: 10.5)),
            ],
            const Spacer(),
            Text(value.toStringAsFixed(0),
                style: text.labelLarge?.copyWith(fontSize: compact ? 12 : 13.5)),
          ],
        ),
        const SizedBox(height: 4),
        ClipRRect(
          borderRadius: BorderRadius.circular(AppRadius.pill),
          child: LinearProgressIndicator(
            value: value / 100,
            minHeight: compact ? 4 : 6,
            backgroundColor: color.withValues(alpha: 0.13),
            valueColor: AlwaysStoppedAnimation(color),
          ),
        ),
      ],
    );
  }
}

/// 네 기둥을 한 줄에 놓되, **각 칸의 폭이 곧 가중치**다.
///
/// 예전에는 네 칸을 같은 폭으로 두고 카드마다 '35%' 같은 숫자를 반복해
/// 적었다. 같은 숫자가 카드 수만큼 반복되니 읽히지 않았고, 정작 어느
/// 기둥이 무거운지는 눈에 들어오지 않았다. 폭으로 보여주면 한 번에 읽히고
/// 반복 표기가 필요 없다.
///
/// 가중치는 meta.json 에서 온다. 화면에 상수로 박아 두면 산식을 바꿀 때마다
/// 어긋난다 — 실제로 0.20/0.25 가 박혀 있어 0.35 로 바꾼 뒤에도 옛 값을
/// 보여주고 있었다.
class PillarWeightBars extends StatelessWidget {
  final Score score;
  final Map<String, double> weights;
  final bool stacked;
  final bool showWeight;

  const PillarWeightBars({
    super.key,
    required this.score,
    required this.weights,
    this.stacked = false,
    this.showWeight = false,
  });

  /// 표시 순서는 무거운 것부터. 화면이 곧 우선순위를 말한다.
  List<MapEntry<String, double>> get _ordered {
    final rows = weights.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    return rows;
  }

  @override
  Widget build(BuildContext context) {
    final rows = _ordered;
    if (stacked) {
      return Column(children: [
        for (final e in rows)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: PillarBar(
                pillar: e.key,
                value: score.pillar(e.key),
                weight: e.value,
                compact: true,
                showWeight: showWeight),
          ),
      ]);
    }
    // flex 를 가중치에 비례시킨다. 정수여야 해서 1000배해 반올림한다.
    return Row(children: [
      for (var i = 0; i < rows.length; i++) ...[
        Expanded(
          flex: (rows[i].value * 1000).round(),
          child: PillarBar(
              pillar: rows[i].key,
              value: score.pillar(rows[i].key),
              weight: rows[i].value,
              compact: true,
              showWeight: showWeight),
        ),
        if (i != rows.length - 1) const SizedBox(width: AppSpace.md),
      ],
    ]);
  }
}

class MomentumArrow extends StatelessWidget {
  final String direction;
  const MomentumArrow(this.direction, {super.key});

  @override
  Widget build(BuildContext context) {
    final (icon, color, label) = switch (direction) {
      'rising' => (Icons.arrow_drop_up, AppColors.rising, '상승'),
      'falling' => (Icons.arrow_drop_down, AppColors.falling, '하락'),
      _ => (Icons.remove, AppColors.mist, '보합'),
    };
    return Row(mainAxisSize: MainAxisSize.min, children: [
      Icon(icon, size: 18, color: color),
      Text(label,
          style: TextStyle(
              fontFamily: 'Paperlogy',
              fontSize: 11.5,
              fontWeight: FontWeight.w600,
              color: color)),
    ]);
  }
}

class SectionHeader extends StatelessWidget {
  final String title;
  final String? subtitle;
  final Widget? trailing;
  const SectionHeader(this.title, {super.key, this.subtitle, this.trailing});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpace.md),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: text.headlineMedium),
                if (subtitle != null) ...[
                  const SizedBox(height: 4),
                  Text(subtitle!, style: text.bodyMedium),
                ],
              ],
            ),
          ),
          ?trailing,
        ],
      ),
    );
  }
}

/// 가로 스크롤 선택 칩 줄
class ChipRow<T> extends StatelessWidget {
  final List<(T value, String label)> options;
  final T selected;
  final ValueChanged<T> onChanged;
  const ChipRow({
    super.key,
    required this.options,
    required this.selected,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          for (final (value, label) in options)
            Padding(
              padding: const EdgeInsets.only(right: AppSpace.sm),
              child: _Pill(
                label: label,
                selected: value == selected,
                onTap: () => onChanged(value),
              ),
            ),
        ],
      ),
    );
  }
}

class _Pill extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;
  const _Pill(
      {required this.label, required this.selected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Material(
      color: selected
          ? AppColors.navy
          : (dark ? AppColors.darkSurface : AppColors.surface),
      borderRadius: BorderRadius.circular(AppRadius.pill),
      child: InkWell(
        borderRadius: BorderRadius.circular(AppRadius.pill),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 9),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(AppRadius.pill),
            border: Border.all(
                color: selected
                    ? AppColors.navy
                    : (dark ? AppColors.darkLine : AppColors.line)),
          ),
          child: Text(label,
              style: TextStyle(
                fontFamily: 'Paperlogy',
                fontSize: 13.5,
                fontWeight: FontWeight.w600,
                letterSpacing: -0.2,
                color: selected
                    ? Colors.white
                    : (dark ? AppColors.mist : AppColors.slate),
              )),
        ),
      ),
    );
  }
}
