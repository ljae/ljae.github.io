import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../core/brand.dart';
import '../core/theme.dart';

/// 「實錄」 조형 요소 — 이 파일이 새 디자인의 서명이다.
///
/// 화면을 '카드가 떠 있는 앱'이 아니라 '괘선이 그어진 판면'으로 만드는
/// 부품들을 모아 둔다. 여기 있는 것만으로 화면 성격이 정해지므로,
/// 새 화면을 만들 때는 Card·Chip 을 새로 그리기 전에 여기를 먼저 볼 것.
///
///   [PaperGround]   한지 바탕 + 계선(界線) + 결
///   [LogoMark]      로고 표장. 계선 둘 사이로 계단이 오른다
///   [Seal]          낙관(落款). 검증·1위 같은 **단정**에만 찍는다
///   [LedgerNumber]  장부 숫자. 등수·점수·수량
///   [Rule]          계선 한 줄
///   [StrokeIn]      획을 긋듯 왼→오른쪽으로 열리는 등장
///   [IndexRail]     좌측 색인 여백을 둔 비대칭 배치
///   [SectionOpener] 굵은 획 + 벌린 자간 라벨 + 큰 표제
///   [TagMark]       각진 꼬리표. 알약 칩을 대신한다
///   [GaugeSpine]    세로 눈금 게이지

// ─────────────────────────────────────────────────────────────────────
// 바탕
// ─────────────────────────────────────────────────────────────────────

/// 한지 바탕. 세로 계선과 아주 옅은 결을 깐다.
///
/// 그림자를 쓰지 않기로 한 대신 **바탕에 정보를 준다.** 아무 무늬 없는
/// 단색 위에서는 계층이 테두리 하나로만 갈리는데, 옅은 세로 괘선이
/// 있으면 그 위에 놓인 것이 '판면 위의 항목'으로 읽힌다.
class PaperGround extends StatelessWidget {
  final Widget child;

  /// 계선 간격. 좁히면 원고지가 되고 넓히면 무늬가 사라진다.
  final double column;

  /// 한 단계 눌린 바탕(섹션을 번갈아 눕힐 때).
  final bool deep;

  /// 결(grain)을 뿌릴지. 히어로처럼 넓은 면에서만 켠다 —
  /// 좁은 카드 안에서는 보이지도 않으면서 그리기만 한다.
  final bool grain;

  const PaperGround({
    super.key,
    required this.child,
    this.column = 84,
    this.deep = false,
    this.grain = false,
  });

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: deep ? AppColors.canvasDeepOn(dark) : AppColors.canvasOn(dark),
      ),
      child: CustomPaint(
        painter: _GyeseonPainter(
          rule: AppColors.ruleOn(dark).withValues(alpha: dark ? 0.30 : 0.42),
          fiber: AppColors.inkOn(dark).withValues(alpha: dark ? 0.05 : 0.035),
          column: column,
          grain: grain,
        ),
        child: child,
      ),
    );
  }
}

class _GyeseonPainter extends CustomPainter {
  final Color rule;
  final Color fiber;
  final double column;
  final bool grain;

  const _GyeseonPainter({
    required this.rule,
    required this.fiber,
    required this.column,
    required this.grain,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final p = Paint()
      ..color = rule
      ..strokeWidth = AppRule.hair;

    // 세로 계선. 화면 가운데를 기준으로 좌우 대칭이 되도록 시작점을
    // 잡는다 — 왼쪽 끝에서 시작하면 폭이 바뀔 때마다 무늬가 흔들린다.
    final mid = size.width / 2;
    final first = mid - (mid ~/ column) * column;
    for (var x = first; x < size.width; x += column) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), p);
    }

    if (!grain) return;

    // 결. 난수를 고정 시드로 돌려 폭이 바뀌어도 같은 자리에 찍히게 한다.
    // 매번 다른 자리에 찍히면 스크롤할 때 종이가 살아 움직인다.
    final g = Paint()..color = fiber;
    var seed = 20260827;
    int next() => seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF;
    final count = math.min(520, (size.width * size.height / 2600).round());
    for (var i = 0; i < count; i++) {
      final x = (next() % 10000) / 10000 * size.width;
      final y = (next() % 10000) / 10000 * size.height;
      final len = 1.0 + (next() % 5);
      canvas.drawRect(Rect.fromLTWH(x, y, len, 0.8), g);
    }
  }

  @override
  bool shouldRepaint(_GyeseonPainter old) =>
      old.rule != rule || old.column != column || old.grain != grain;
}

// ─────────────────────────────────────────────────────────────────────
// 표장(標章)
// ─────────────────────────────────────────────────────────────────────

/// 로고 마크. 계선 둘 사이로 계단이 오르고 그 끝에 주묵이 찍힌다.
///
/// **래스터를 쓰지 않는다.** PNG 한 장으로는 두 판을 못 맞춘다 — 한지
/// 바탕에 맞춘 먹빛 마크는 먹빛 판면에서 사라지고, 바탕을 깔면 어두운
/// 헤더에 흰 딱지가 붙는다. 도형이 사각형 일곱 개뿐이라 그릴 값이다.
///
/// 좌표는 `brand/build_marks.py` 의 작은 판과 **같은 48단위 격자**다.
/// 로고를 고치면 그쪽을 고치고 이 표를 맞춰 옮긴다 — 두 곳에 있는 것은
/// 알지만, 파비콘·앱아이콘을 파이썬이 내고 화면은 다트가 그리므로
/// 한쪽만 두면 다른 쪽이 못 읽는다.
class LogoMark extends StatelessWidget {
  final double size;
  const LogoMark({super.key, this.size = 28});

  /// 48단위 격자 위의 사각형 (x, y, w, h). 마지막 하나가 주묵이다.
  static const _grid = 48.0;
  static const _ink = <List<double>>[
    [3, 6, 3, 36], // 왼쪽 계선
    [42, 6, 3, 36], // 오른쪽 계선
    [12, 27, 6, 15], // 리서 1
    [12, 27, 15, 6], // 트레드 1
    [21, 15, 6, 18], // 리서 2
    [21, 15, 15, 6], // 트레드 2
  ];
  static const _tip = <double>[30, 6, 6, 9];

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    // 접근성 라벨은 **바깥에서** 감싼다. `CustomPaint` 는 자식이 있으면
    // 제 `size` 를 버리고 자식 크기를 따르므로, 라벨을 자식으로 넣으면
    // 마크가 0×0 으로 접힌다 — 여기서 한 번 틀렸고 시험이 잡았다.
    return Semantics(
      label: Brand.name,
      image: true,
      child: CustomPaint(
        size: Size.square(size),
        painter: _LogoPainter(
          ink: AppColors.inkOn(dark),
          accent: AppColors.accentOn(dark),
        ),
      ),
    );
  }
}

class _LogoPainter extends CustomPainter {
  final Color ink;
  final Color accent;
  const _LogoPainter({required this.ink, required this.accent});

  @override
  void paint(Canvas canvas, Size size) {
    final k = size.shortestSide / LogoMark._grid;
    void box(List<double> r, Color c) => canvas.drawRect(
      Rect.fromLTWH(r[0] * k, r[1] * k, r[2] * k, r[3] * k),
      Paint()..color = c,
    );
    for (final r in LogoMark._ink) {
      box(r, ink);
    }
    box(LogoMark._tip, accent);
  }

  @override
  bool shouldRepaint(_LogoPainter old) =>
      old.ink != ink || old.accent != accent;
}

// ─────────────────────────────────────────────────────────────────────
// 낙관(落款)
// ─────────────────────────────────────────────────────────────────────

/// 도장. **단정할 수 있는 것에만 찍는다.**
///
/// 이 서비스에는 '확인된 사실'과 '추정'이 섞여 있다. 도장은 앞의 것에만
/// 쓴다 — 추정에 도장을 찍으면 그 순간부터 도장이 아무 뜻도 갖지 않는다.
/// 쓰는 곳: 공시로 검증된 등록 정보, 1위, 사람이 큐레이션한 단계.
class Seal extends StatelessWidget {
  /// 한 글자. 두 글자까지는 들어가지만 한 글자가 가장 도장답다.
  final String glyph;
  final double size;
  final Color color;

  /// 음각(글자를 파낸 흰 글씨) / 양각(붉은 글씨). 기본은 음각.
  final bool solid;

  /// 손으로 찍은 티. 0 이면 반듯하다.
  final double tilt;

  const Seal(
    this.glyph, {
    super.key,
    this.size = 34,
    this.color = AppColors.vermilion,
    this.solid = true,
    this.tilt = -0.045,
  });

  @override
  Widget build(BuildContext context) {
    return Transform.rotate(
      angle: tilt,
      child: Container(
        width: size,
        height: size,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: solid ? color : Colors.transparent,
          borderRadius: BorderRadius.circular(AppRadius.sm),
          border: Border.all(color: color, width: size * 0.055),
        ),
        // 안쪽 테두리는 **큰 도장에만** 두른다. 24px 아래에서는 그 선이
        // 글자 자리를 먹어 한자가 '붉은 네모 안의 점'으로 뭉갰다(실측).
        // 작을 때는 테두리를 빼고 글자를 키운다 — 도장은 읽혀야 도장이다.
        child: Container(
          width: size - size * (size >= 24 ? 0.24 : 0.14),
          height: size - size * (size >= 24 ? 0.24 : 0.14),
          alignment: Alignment.center,
          decoration: size >= 24
              ? BoxDecoration(
                  border: Border.all(
                    color: (solid ? AppColors.cream : color).withValues(
                      alpha: solid ? 0.55 : 0.35,
                    ),
                    width: math.max(0.6, size * 0.028),
                  ),
                )
              : null,
          child: Text(
            glyph,
            maxLines: 1,
            style: TextStyle(
              fontFamily: 'Paperlogy',
              fontSize:
                  size *
                  (glyph.characters.length > 1
                      ? 0.34
                      : (size >= 24 ? 0.50 : 0.62)),
              fontWeight: FontWeight.w800,
              height: 1.0,
              letterSpacing: -0.5,
              color: solid ? AppColors.cream : color,
            ),
          ),
        ),
      ),
    );
  }
}

/// 도장을 **누르는** 등장. 조금 크게 시작해 눌러 앉고, 각도도 같이 잡힌다.
/// 흔한 '떠오르며 흐려짐'과 이 동작이 이 디자인의 모션 정체성이다.
class SealPress extends StatefulWidget {
  final Widget child;
  final Duration delay;
  const SealPress({super.key, required this.child, this.delay = Duration.zero});

  @override
  State<SealPress> createState() => _SealPressState();
}

class _SealPressState extends State<SealPress>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: AppMotion.press,
  );

  @override
  void initState() {
    super.initState();
    if (widget.delay == Duration.zero) {
      _c.forward();
    } else {
      Future.delayed(widget.delay, () {
        if (mounted) _c.forward();
      });
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (MediaQuery.maybeDisableAnimationsOf(context) ?? false) {
      return widget.child;
    }
    final a = CurvedAnimation(parent: _c, curve: AppMotion.pressCurve);
    return AnimatedBuilder(
      animation: a,
      builder: (_, child) => Opacity(
        opacity: _c.value.clamp(0.0, 1.0),
        child: Transform.scale(
          scale: 1.30 - 0.30 * a.value,
          child: Transform.rotate(angle: (1 - a.value) * -0.10, child: child),
        ),
      ),
      child: widget.child,
    );
  }
}

// ─────────────────────────────────────────────────────────────────────
// 장부 숫자
// ─────────────────────────────────────────────────────────────────────

/// 등수·점수·수량. **고정폭 숫자**로 찍어 세로로 견줄 수 있게 한다.
///
/// 비례폭 숫자는 1 이 좁아서 목록에서 줄마다 자리가 어긋난다.
/// 장부에서 그건 오류로 읽힌다.
class LedgerNumber extends StatelessWidget {
  final String value;
  final double size;
  final Color? color;
  final FontWeight weight;

  /// 숫자 위에 붙는 벌린 자간 라벨(예: `표 본`).
  final String? label;

  /// 숫자 아래 계선을 긋는다.
  final bool underline;
  final CrossAxisAlignment align;

  const LedgerNumber(
    this.value, {
    super.key,
    this.size = 30,
    this.color,
    this.weight = FontWeight.w800,
    this.label,
    this.underline = false,
    this.align = CrossAxisAlignment.start,
  });

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final text = Theme.of(context).textTheme;
    final n = Text(
      value,
      style: TextStyle(
        fontFamily: 'Paperlogy',
        fontSize: size,
        fontWeight: weight,
        height: 1.0,
        letterSpacing: size * -0.045,
        color: color ?? AppColors.inkOn(dark),
        fontFeatures: ledgerFigures,
      ),
    );

    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: align,
      children: [
        if (label != null) ...[
          Text(label!, style: text.labelSmall),
          SizedBox(height: size * 0.14),
        ],
        n,
        if (underline) ...[
          SizedBox(height: size * 0.18),
          SizedBox(
            width: size * 1.5,
            child: Rule(color: color ?? AppColors.ruleOn(dark)),
          ),
        ],
      ],
    );
  }
}

// ─────────────────────────────────────────────────────────────────────
// 계선
// ─────────────────────────────────────────────────────────────────────

/// 줄 하나. `Divider` 는 세로 여백을 스스로 갖는데, 판면을 짤 때는
/// 여백을 바깥에서 정해야 해서 여백 없는 줄이 따로 필요하다.
class Rule extends StatelessWidget {
  final double thickness;
  final Color? color;
  final Axis axis;
  final double? extent;

  const Rule({
    super.key,
    this.thickness = AppRule.hair,
    this.color,
    this.axis = Axis.horizontal,
    this.extent,
  });

  const Rule.vertical({
    super.key,
    this.thickness = AppRule.hair,
    this.color,
    this.extent,
  }) : axis = Axis.vertical;

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final c = color ?? AppColors.ruleOn(dark);
    return axis == Axis.horizontal
        ? Container(height: thickness, width: extent, color: c)
        : Container(width: thickness, height: extent, color: c);
  }
}

// ─────────────────────────────────────────────────────────────────────
// 획을 긋는 등장
// ─────────────────────────────────────────────────────────────────────

/// 왼쪽에서 오른쪽으로 **열리는** 등장. 붓이 지나가는 모양이다.
///
/// 위로 떠오르는 흔한 등장 대신 이걸 쓴다. 글을 '쓰는' 동작이라
/// 기록물이라는 성격과 맞고, 세로 스크롤과 방향이 겹치지 않아
/// 스크롤 중에도 어지럽지 않다.
class StrokeIn extends StatefulWidget {
  final Widget child;
  final Duration delay;

  /// 여러 개를 연달아 낼 때의 순번. [delay] 대신 이것만 주면 된다.
  final int index;
  final Alignment from;

  const StrokeIn({
    super.key,
    required this.child,
    this.delay = Duration.zero,
    this.index = 0,
    this.from = Alignment.centerLeft,
  });

  @override
  State<StrokeIn> createState() => _StrokeInState();
}

class _StrokeInState extends State<StrokeIn>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: AppMotion.stroke,
  );

  @override
  void initState() {
    super.initState();
    final d = widget.delay == Duration.zero
        ? AppMotion.stagger * widget.index
        : widget.delay;
    if (d == Duration.zero) {
      _c.forward();
    } else {
      Future.delayed(d, () {
        if (mounted) _c.forward();
      });
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // 모션을 끈 사용자에게는 획을 긋지 않는다. 읽는 데 필요한 것은
    // 내용이지 동작이 아니다.
    if (MediaQuery.maybeDisableAnimationsOf(context) ?? false) {
      return widget.child;
    }

    final a = CurvedAnimation(parent: _c, curve: AppMotion.strokeCurve);
    return AnimatedBuilder(
      animation: a,
      builder: (_, child) => ClipRect(
        // **폭을 줄이지 않고 그리기만 자른다.** 예전에는
        // `Align(widthFactor:)` 로 열었는데, 그러면 애니메이션 도중의
        // 폭이 곧 레이아웃 폭이 되어 카드가 실제로 좁아졌다 — 캡처에서
        // 목록의 카드마다 오른쪽 끝이 다른 자리에서 잘려 있었다.
        // 클리퍼는 배치를 건드리지 않으므로 동작이 멈춰도 폭은 그대로다.
        clipper: StrokeClipper(a.value, widget.from),
        child: Opacity(opacity: (a.value * 1.8).clamp(0.0, 1.0), child: child),
      ),
      child: widget.child,
    );
  }
}

/// 획이 지나간 만큼만 보여 주는 클리퍼.
///
/// [StrokeIn](첫 화면 등장)과 [Reveal](스크롤 등장)이 나눠 쓴다 — 시점만
/// 다르고 조형은 같아야 한다. 두 벌로 두면 한쪽만 고쳐 놓고 못 알아챈다.
class StrokeClipper extends CustomClipper<Rect> {
  final double t;
  final Alignment from;
  const StrokeClipper(this.t, this.from);

  @override
  Rect getClip(Size size) {
    final w = size.width * t.clamp(0.0, 1.0);
    // 가운데에서 여는 경우(세로 제자)는 양쪽으로 벌어진다.
    if (from == Alignment.center) {
      final half = w / 2;
      return Rect.fromLTRB(
        size.width / 2 - half,
        0,
        size.width / 2 + half,
        size.height,
      );
    }
    if (from == Alignment.centerRight) {
      return Rect.fromLTRB(size.width - w, 0, size.width, size.height);
    }
    return Rect.fromLTRB(0, 0, w, size.height);
  }

  @override
  bool shouldReclip(StrokeClipper old) => old.t != t || old.from != from;
}

// ─────────────────────────────────────────────────────────────────────
// 비대칭 배치
// ─────────────────────────────────────────────────────────────────────

/// 좌측 색인 여백을 둔 배치. **가운데 정렬을 쓰지 않는 이유가 이것이다.**
///
/// 실록 판면에는 본문 옆에 늘 비워 두는 자리가 있고 거기에 권차·연도가
/// 들어간다. 화면에서도 그 자리를 고정으로 비워 두고 기록 번호·집계일·
/// 표본 수처럼 '본문은 아니지만 늘 있어야 하는 것'을 넣는다.
///
/// 좁은 화면에서는 레일을 **지우지 않고** 본문 위로 한 줄 올린다.
/// 지우면 좁은 화면에서만 정보가 사라지고, 그건 화면 크기로 정보량을
/// 정하는 셈이 된다.
class IndexRail extends StatelessWidget {
  final Widget rail;
  final Widget child;
  final double gap;

  const IndexRail({
    super.key,
    required this.rail,
    required this.child,
    this.gap = AppSpace.lg,
  });

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= AppSpace.railMinWidth;
    if (!wide) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          DefaultTextStyle.merge(
            style: Theme.of(context).textTheme.labelMedium!,
            child: rail,
          ),
          const SizedBox(height: AppSpace.sm),
          child,
        ],
      );
    }
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: AppSpace.rail,
          child: DefaultTextStyle.merge(
            style: Theme.of(context).textTheme.labelMedium!,
            child: rail,
          ),
        ),
        SizedBox(width: gap),
        Expanded(child: child),
      ],
    );
  }
}

// ─────────────────────────────────────────────────────────────────────
// 표제
// ─────────────────────────────────────────────────────────────────────

/// 섹션 머리. 굵은 획 → 벌린 자간 라벨 → 큰 표제 순으로 내려온다.
/// 세 층이 각각 다른 일을 한다: 획은 시작을 알리고, 라벨은 갈래를
/// 말하고, 표제는 내용을 말한다.
class SectionOpener extends StatelessWidget {
  final String title;
  final String? kicker;
  final String? subtitle;
  final Widget? trailing;

  const SectionOpener(
    this.title, {
    super.key,
    this.kicker,
    this.subtitle,
    this.trailing,
  });

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final dark = Theme.of(context).brightness == Brightness.dark;

    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpace.lg),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Rule(
                  thickness: AppRule.stroke,
                  extent: 46,
                  color: AppColors.accentOn(dark),
                ),
                const SizedBox(height: AppSpace.md),
                if (kicker != null) ...[
                  Text(kicker!, style: text.labelMedium),
                  const SizedBox(height: 6),
                ],
                Text(title, style: text.headlineLarge),
                if (subtitle != null) ...[
                  const SizedBox(height: AppSpace.sm),
                  ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 620),
                    child: Text(subtitle!, style: text.bodyMedium),
                  ),
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

// ─────────────────────────────────────────────────────────────────────
// 꼬리표
// ─────────────────────────────────────────────────────────────────────

/// 각진 꼬리표. 알약 칩을 대신한다.
///
/// 왼쪽에 색 획을 세우고 본문은 색을 거의 쓰지 않는다. 칩마다 배경을
/// 칠하면 목록이 색종이가 되고, 정작 하나뿐인 강조색(주묵)이 묻힌다.
class TagMark extends StatelessWidget {
  final String label;
  final Color color;
  final IconData? icon;

  /// 채운 꼬리표. 정말 강조할 하나에만.
  final bool filled;

  const TagMark(
    this.label, {
    super.key,
    required this.color,
    this.icon,
    this.filled = false,
  });

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final fg = filled ? AppColors.cream : AppColors.inkOn(dark);

    return Container(
      padding: EdgeInsets.fromLTRB(icon == null ? 8 : 7, 4, 8, 4.5),
      decoration: BoxDecoration(
        color: filled ? color : color.withValues(alpha: dark ? 0.10 : 0.07),
        // 모서리를 굴리지 않는다. **왼쪽만 굵은 획인 테두리에는 반경을
        // 줄 수 없다** — Flutter 가 페인트 단계에서 막는다(색·굵기가
        // 균일한 테두리에만 borderRadius 를 허용한다). 릴리스에서는
        // assert 가 꺼져 조용히 지나가지만, 그건 고쳐진 게 아니라
        // 안 보이는 것이다. 2px 짜리 반경은 이 크기에서 눈에도 안 띄고,
        // 각진 칸이 이 판면의 말투이기도 하다.
        border: Border(
          left: BorderSide(color: color, width: AppRule.bold),
          top: BorderSide(
            color: color.withValues(alpha: filled ? 1 : 0.22),
            width: AppRule.hair,
          ),
          right: BorderSide(
            color: color.withValues(alpha: filled ? 1 : 0.22),
            width: AppRule.hair,
          ),
          bottom: BorderSide(
            color: color.withValues(alpha: filled ? 1 : 0.22),
            width: AppRule.hair,
          ),
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 11.5, color: filled ? AppColors.cream : color),
            const SizedBox(width: 4),
          ],
          Text(
            label,
            style: TextStyle(
              fontFamily: 'Paperlogy',
              fontSize: 11.5,
              fontWeight: FontWeight.w600,
              letterSpacing: -0.1,
              height: 1.25,
              color: fg,
              fontFeatures: ledgerFigures,
            ),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────
// 눈금
// ─────────────────────────────────────────────────────────────────────

/// 세로 눈금 게이지. 점수 옆에 세워 '0~100 중 어디인가'를 말한다.
///
/// 원형 도넛 대신 이걸 쓴다. 도넛은 값이 클수록 예뻐 보이지만 두 값을
/// 견주기 어렵고, 세로 막대는 목록에서 **위아래로 바로 견줄 수 있다.**
class GaugeSpine extends StatelessWidget {
  final double value; // 0~100
  final double height;
  final double width;
  final Color? color;

  const GaugeSpine(
    this.value, {
    super.key,
    this.height = 46,
    this.width = 5,
    this.color,
  });

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final c = color ?? AppColors.inkOn(dark);
    final f = (value / 100).clamp(0.0, 1.0);

    return SizedBox(
      width: width + 7,
      height: height,
      child: Stack(
        children: [
          Positioned(
            left: 0,
            top: 0,
            bottom: 0,
            width: width,
            child: ColoredBox(color: AppColors.ruleOn(dark)),
          ),
          Positioned(
            left: 0,
            bottom: 0,
            width: width,
            child: TweenAnimationBuilder<double>(
              tween: Tween(begin: 0, end: f),
              duration: AppMotion.stroke,
              curve: AppMotion.strokeCurve,
              builder: (_, v, _) => Container(height: height * v, color: c),
            ),
          ),
          // 50 눈금. 코호트 평균이 50 이라 '가운데보다 위/아래'가
          // 이 서비스에서 실제 의미를 갖는 유일한 기준선이다.
          Positioned(
            left: 0,
            top: height / 2,
            width: width + 5,
            child: Rule(color: AppColors.ruleOn(dark), thickness: AppRule.hair),
          ),
        ],
      ),
    );
  }
}

/// 벌린 자간의 작은 라벨. 레일·머리말에서 반복해 쓴다.
class RailLabel extends StatelessWidget {
  final String text;
  final Color? color;
  const RailLabel(this.text, {super.key, this.color});

  @override
  Widget build(BuildContext context) => Text(
    text,
    style: Theme.of(context).textTheme.labelMedium?.copyWith(color: color),
  );
}

/// 레일에 넣는 한 항목 — 벌린 자간 라벨 + 장부 숫자.
class RailFact extends StatelessWidget {
  final String label;
  final String value;
  final Color? valueColor;
  const RailFact(this.label, this.value, {super.key, this.valueColor});

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpace.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          RailLabel(label),
          const SizedBox(height: 3),
          Text(
            value,
            style: TextStyle(
              fontFamily: 'Paperlogy',
              fontSize: 15,
              fontWeight: FontWeight.w700,
              height: 1.25,
              letterSpacing: -0.4,
              color: valueColor ?? AppColors.inkOn(dark),
              fontFeatures: ledgerFigures,
            ),
          ),
        ],
      ),
    );
  }
}

/// 천 단위 구분. 4170 은 규모가 안 읽힌다.
String ledgerCount(int v) => v.toString().replaceAllMapped(
  RegExp(r'(\d)(?=(\d{3})+$)'),
  (m) => '${m[1]},',
);

/// 벌린 자간 라벨용 — 한글 사이에 얇은 공백을 넣어 '메타 정보'로 읽히게 한다.
/// `기록` → `기 록`. 자간(letterSpacing)만으로는 한글에서 티가 잘 안 난다.
String spaced(String s) => s.characters.join(' ');
