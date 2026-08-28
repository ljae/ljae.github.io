import 'package:flutter/material.dart';

import '../core/theme.dart';
import '../data/models.dart';
import 'annals.dart';

/// 최대폭 제한 + 좌우 여백. 모든 페이지 본문이 이걸 통과한다.
class ContentWidth extends StatelessWidget {
  final Widget child;
  final double max;
  const ContentWidth({
    super.key,
    required this.child,
    this.max = AppSpace.maxContent,
  });

  @override
  Widget build(BuildContext context) {
    final pad = MediaQuery.sizeOf(context).width < 640
        ? AppSpace.md
        : AppSpace.lg;
    return Center(
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: max),
        child: Padding(
          padding: EdgeInsets.symmetric(horizontal: pad),
          child: child,
        ),
      ),
    );
  }
}

/// 데모 모드 배너. 실명 학원에 합성 점수가 붙어 있음을 반드시 알린다.
///
/// 여기에는 **도장을 찍지 않는다.** 도장은 단정에만 쓰기로 했고,
/// 이 배너가 말하는 것은 정확히 그 반대다.
class DemoBanner extends StatelessWidget {
  final Meta meta;
  const DemoBanner({super.key, required this.meta});

  @override
  Widget build(BuildContext context) {
    if (!meta.isDemo) return const SizedBox.shrink();
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        color: dark
            ? AppColors.vermilion.withValues(alpha: 0.14)
            : AppColors.vermilionWash,
        border: Border(
          top: BorderSide(color: AppColors.accentOn(dark), width: AppRule.bold),
          bottom: BorderSide(
            color: AppColors.accentOn(dark).withValues(alpha: 0.3),
            width: AppRule.hair,
          ),
        ),
      ),
      padding: const EdgeInsets.symmetric(vertical: 9, horizontal: AppSpace.md),
      child: Center(
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            RailLabel(spaced('표본'), color: AppColors.accentOn(dark)),
            const SizedBox(width: AppSpace.sm),
            Flexible(
              child: Text(
                '샘플 데이터로 동작 중입니다 — 표시된 점수는 합성값이며 실제 평가가 아닙니다.',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: dark ? AppColors.darkInk : AppColors.vermilionDeep,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 꼬리표. 이름은 그대로 두고 조형만 「實錄」 것으로 바꿨다 —
/// 서른 곳 넘는 호출부를 한꺼번에 고치는 것보다 이쪽이 안전하다.
class Chip2 extends StatelessWidget {
  final String label;
  final Color color;
  final IconData? icon;
  final bool filled;
  const Chip2(
    this.label, {
    super.key,
    required this.color,
    this.icon,
    this.filled = false,
  });

  @override
  Widget build(BuildContext context) =>
      TagMark(label, color: color, icon: icon, filled: filled);
}

/// 검증됨 / 추정 배지 — 사실과 의견을 시각적으로 분리하는 장치.
class VerifiedChip extends StatelessWidget {
  final bool verified;
  const VerifiedChip({super.key, required this.verified});

  @override
  Widget build(BuildContext context) => verified
      ? const TagMark(
          '공시 검증',
          color: AppColors.verified,
          icon: Icons.check_rounded,
        )
      : const TagMark(
          '샘플',
          color: AppColors.estimated,
          icon: Icons.science_outlined,
        );
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
    return TagMark(
      '${score.confidenceLabel} · ${score.sampleSize}건',
      color: color,
    );
  }
}

/// 트리스코어 표시. 이름은 'Dial' 로 남았지만 **더 이상 도넛이 아니다.**
///
/// 도넛은 값이 클수록 예뻐 보일 뿐, 목록에서 두 값을 견주기 어렵다.
/// 세로 눈금 + 장부 숫자로 바꾸면 카드가 세로로 쌓일 때 눈금 높이가
/// 그대로 비교가 된다. 70 이상만 주묵으로 채운다 — 강조색을 아무 데나
/// 쓰면 그 색이 아무 뜻도 갖지 않는다.
class ScoreDial extends StatelessWidget {
  final double value;
  final double size;
  final bool showLabel;
  const ScoreDial(
    this.value, {
    super.key,
    this.size = 64,
    this.showLabel = true,
  });

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final strong = value >= 70;
    final gauge = strong ? AppColors.accentOn(dark) : AppColors.inkOn(dark);

    return Row(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        GaugeSpine(value, height: size * 0.82, width: 3.5, color: gauge),
        const SizedBox(width: 7),
        Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (showLabel) ...[
              Text(
                spaced('트리스코어'),
                style: Theme.of(context).textTheme.labelSmall,
              ),
              SizedBox(height: size * 0.05),
            ],
            Text(
              value.toStringAsFixed(0),
              style: TextStyle(
                fontFamily: 'Paperlogy',
                fontSize: size * 0.60,
                fontWeight: FontWeight.w800,
                height: 0.94,
                letterSpacing: size * -0.035,
                color: AppColors.inkOn(dark),
                fontFeatures: ledgerFigures,
              ),
            ),
          ],
        ),
      ],
    );
  }
}

/// 기둥별 막대. 랭킹·상세에서 동일한 시각 언어를 유지한다.
///
/// 둥근 막대를 각진 계선으로 바꿨다. 아이콘 대신 **색 사각**을 세운다 —
/// 목록에서 아이콘 넷은 서로 구분되지 않고 모양만 어지럽다.
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
    final dark = Theme.of(context).brightness == Brightness.dark;
    final text = Theme.of(context).textTheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Container(
              width: compact ? 6 : 7,
              height: compact ? 6 : 7,
              color: color,
            ),
            const SizedBox(width: 6),
            Flexible(
              child: Text(
                pillarNames[pillar] ?? pillar,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: text.labelLarge?.copyWith(
                  fontSize: compact ? 11.5 : 12.5,
                  color: AppColors.mutedOn(dark),
                ),
              ),
            ),
            if (showWeight) ...[
              const SizedBox(width: 5),
              Text(
                '${(weight * 100).toStringAsFixed(0)}%',
                style: text.bodySmall?.copyWith(
                  fontSize: 10.5,
                  fontFeatures: ledgerFigures,
                ),
              ),
            ],
            const SizedBox(width: 6),
            Text(
              value.toStringAsFixed(0),
              style: TextStyle(
                fontFamily: 'Paperlogy',
                fontSize: compact ? 12 : 13.5,
                fontWeight: FontWeight.w700,
                height: 1.2,
                letterSpacing: -0.3,
                color: AppColors.inkOn(dark),
                fontFeatures: ledgerFigures,
              ),
            ),
          ],
        ),
        const SizedBox(height: 5),
        // 각진 계선 막대. 트랙은 계선 색, 채움은 기둥 색.
        LayoutBuilder(
          builder: (context, c) {
            final w = c.maxWidth.isFinite ? c.maxWidth : 120.0;
            final h = compact ? 3.0 : 5.0;
            return SizedBox(
              width: w,
              height: h,
              child: Stack(
                children: [
                  Positioned.fill(
                    child: ColoredBox(color: AppColors.ruleSoftOn(dark)),
                  ),
                  TweenAnimationBuilder<double>(
                    tween: Tween(begin: 0, end: (value / 100).clamp(0.0, 1.0)),
                    duration: AppMotion.stroke,
                    curve: AppMotion.strokeCurve,
                    builder: (_, v, _) =>
                        Container(width: w * v, height: h, color: color),
                  ),
                ],
              ),
            );
          },
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
      return Column(
        children: [
          for (final e in rows)
            Padding(
              padding: const EdgeInsets.only(bottom: 9),
              child: PillarBar(
                pillar: e.key,
                value: score.pillar(e.key),
                weight: e.value,
                compact: true,
                showWeight: showWeight,
              ),
            ),
        ],
      );
    }
    // flex 를 가중치에 비례시킨다. 정수여야 해서 1000배해 반올림한다.
    return Row(
      children: [
        for (var i = 0; i < rows.length; i++) ...[
          Expanded(
            flex: (rows[i].value * 1000).round(),
            child: PillarBar(
              pillar: rows[i].key,
              value: score.pillar(rows[i].key),
              weight: rows[i].value,
              compact: true,
              showWeight: showWeight,
            ),
          ),
          if (i != rows.length - 1) const SizedBox(width: AppSpace.md),
        ],
      ],
    );
  }
}

/// 언급량 추세. 아이콘 대신 활자 삼각형을 쓴다 — 장부에 찍힌 기호처럼
/// 보이고, 아이콘 폰트와 달리 글자 크기·자간이 본문과 같이 움직인다.
class MomentumArrow extends StatelessWidget {
  final String direction;
  const MomentumArrow(this.direction, {super.key});

  @override
  Widget build(BuildContext context) {
    final (glyph, color, label) = switch (direction) {
      'rising' => ('▲', AppColors.rising, '상승'),
      'falling' => ('▼', AppColors.falling, '하락'),
      _ => ('—', AppColors.mist, '보합'),
    };
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        // 8.5px 로는 화면에서 점 하나로 보였다(실측). 삼각형이
        // 삼각형으로 읽히는 최소 크기가 10.5 다.
        Text(
          glyph,
          style: TextStyle(fontSize: 10.5, height: 1.35, color: color),
        ),
        const SizedBox(width: 3),
        Text(
          label,
          style: TextStyle(
            fontFamily: 'Paperlogy',
            fontSize: 11.5,
            fontWeight: FontWeight.w600,
            letterSpacing: -0.2,
            color: color,
          ),
        ),
      ],
    );
  }
}

/// 섹션 머리. 조형은 [SectionOpener] 가 갖고 있다 —
/// 호출부를 그대로 두기 위해 이름만 남겨 이어 붙인다.
class SectionHeader extends StatelessWidget {
  final String title;
  final String? subtitle;
  final Widget? trailing;
  final String? kicker;
  const SectionHeader(
    this.title, {
    super.key,
    this.subtitle,
    this.trailing,
    this.kicker,
  });

  @override
  Widget build(BuildContext context) => SectionOpener(
    title,
    kicker: kicker,
    subtitle: subtitle,
    trailing: trailing,
  );
}

/// 선택 줄. 알약이 아니라 **밑줄 탭**이다.
///
/// 알약 필터는 어느 앱에나 있어 화면의 성격을 말하지 않는다. 밑줄은
/// 계선과 같은 언어라 판면 안에 자연스럽게 앉고, 선택된 하나만 주묵으로
/// 그어 두면 '지금 어디를 보고 있는가'가 색 하나로 읽힌다.
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
    final tabs = [
      for (final (value, label) in options)
        _Tab(
          label: label,
          selected: value == selected,
          onTap: () => onChanged(value),
        ),
    ];

    // 과목이 여섯 개가 되면서 한 줄에 안 들어간다. 가로 스크롤만 두면
    // 잘린 칩이 있다는 것 자체가 안 보여 '예체능' 탭을 못 찾는다.
    // 좁은 화면에서는 줄을 바꿔 전부 내놓는다.
    return LayoutBuilder(
      builder: (context, c) {
        final tight = c.maxWidth < 560 || options.length > 5;
        if (tight) {
          return Wrap(spacing: AppSpace.sm, runSpacing: 2, children: tabs);
        }
        return SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: [
              for (final t in tabs)
                Padding(
                  padding: const EdgeInsets.only(right: AppSpace.sm),
                  child: t,
                ),
            ],
          ),
        );
      },
    );
  }
}

class _Tab extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;
  const _Tab({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final accent = AppColors.accentOn(dark);
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(AppRadius.sm),
      child: AnimatedContainer(
        duration: AppMotion.quick,
        padding: const EdgeInsets.fromLTRB(11, 9, 11, 7),
        decoration: BoxDecoration(
          color: selected
              ? accent.withValues(alpha: dark ? 0.13 : 0.07)
              : Colors.transparent,
          border: Border(
            bottom: BorderSide(
              color: selected ? accent : AppColors.ruleOn(dark),
              width: selected ? AppRule.bold : AppRule.hair,
            ),
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontFamily: 'Paperlogy',
            fontSize: 13.5,
            fontWeight: selected ? FontWeight.w800 : FontWeight.w500,
            letterSpacing: -0.3,
            color: selected ? AppColors.inkOn(dark) : AppColors.mutedOn(dark),
          ),
        ),
      ),
    );
  }
}
