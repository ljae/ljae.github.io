import 'package:flutter/foundation.dart' show ValueListenable;
import 'package:flutter/material.dart';

import '../core/theme.dart';
import 'annals.dart';

/// 스크롤이 곧 붓질 — 「實錄」의 상호작용 층.
///
/// 참고한 것은 토스의 **스크롤 서사**다. 화면을 내리는 동안 값이 채워지고
/// 숫자가 세어지며 다음 이야기가 열린다. 다만 **가져오지 않은 것이 하나
/// 있다: 스크롤을 붙잡지 않는다.**
///
/// 토스는 판을 화면에 고정(pin)해 두고 스크롤을 애니메이션 재생기로 쓴다.
/// 마케팅 페이지에서는 그 값을 치를 만하지만, 여기는 학부모가 **찾으러**
/// 오는 자료 화면이다. 스크롤이 내 뜻대로 안 움직이면 그건 연출이 아니라
/// 고장으로 읽힌다. 그래서 고정하지 않고, **보이는 동안의 진행도**만
/// 값으로 쓴다 — 느낌은 같고 스크롤은 그대로다.
///
///   [Reveal]      화면에 들어올 때 한 번 획을 긋는다
///   [Scrub]       화면을 지나가는 동안의 진행도(0~1)를 준다
///   [Tally]       장부 숫자를 세어 올린다
///   [ReadingBand] 머리띠가 읽은 만큼 찬다
///
/// **셋 다 모션을 끈 사용자에게는 완성된 상태를 즉시 준다.** 진행도는 1,
/// 숫자는 최종값. 동작이 정보를 쥐고 있으면 안 된다 — 못 보는 사람에게
/// 내용까지 안 보이는 것이 이 종류 연출의 가장 흔한 실패다.

// ─────────────────────────────────────────────────────────────────────
// 바탕 계산
// ─────────────────────────────────────────────────────────────────────

/// 스크롤 위치를 듣고, 자기가 뷰포트의 어디쯤 있는지를 0~1 로 돌려준다.
///
/// `VisibilityDetector` 같은 패키지를 쓰지 않는다. 필요한 것은 '보이는가'가
/// 아니라 '얼마나 지나갔는가'이고, 그건 스크롤 위치와 자기 상자만 있으면
/// 구할 수 있다. 의존성을 하나 더 들이는 값이 그것보다 크다.
abstract class _StageWatcher<T extends StatefulWidget> extends State<T> {
  ScrollPosition? _position;

  /// 스크롤 판 자체. **여기 붙잡아 둔다.**
  ///
  /// 스크롤 콜백 안에서 `Scrollable.of(context)` 를 부르면 안 된다 —
  /// 그건 조상 탐색(dependOnInheritedWidgetOfExactType)이라, 위젯이
  /// 떨어져 나간 뒤 콜백이 한 번 더 돌면
  /// 'Looking up a deactivated widget's ancestor is unsafe' 로 죽는다.
  /// 의존성은 didChangeDependencies 에서 한 번만 집어 두고,
  /// 그 뒤로는 저장해 둔 것만 쓴다.
  ScrollableState? _scrollable;

  /// 뷰포트 위쪽을 0, 아래쪽을 1 로 놓았을 때 이 위젯 **위쪽 모서리**의 자리.
  /// 아래에서 올라오면 1 → 0 으로 줄어든다.
  double _headFraction = 1;

  /// 이 위젯이 뷰포트를 **지나간 정도**. 아래끝이 화면 바닥에 닿을 때 0,
  /// 위끝이 화면 꼭대기를 지날 때 1.
  double _passFraction = 0;

  bool get reduceMotion =>
      MediaQuery.maybeDisableAnimationsOf(context) ?? false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _scrollable = Scrollable.maybeOf(context);
    final p = _scrollable?.position;
    if (!identical(p, _position)) {
      _position?.removeListener(_onScroll);
      _position = p;
      _position?.addListener(_onScroll);
    }
    // 첫 프레임에는 아직 배치가 없다. 그려진 뒤에 한 번 재 본다 —
    // 이걸 빠뜨리면 **첫 화면에 이미 보이는 것**이 영원히 안 열린다.
    WidgetsBinding.instance.addPostFrameCallback((_) => _onScroll());
  }

  @override
  void dispose() {
    _position?.removeListener(_onScroll);
    super.dispose();
  }

  void _onScroll() {
    if (!mounted) return;
    final scrollable = _scrollable;
    if (scrollable == null || !scrollable.mounted) return;

    final box = context.findRenderObject() as RenderBox?;
    if (box == null || !box.attached || !box.hasSize) return;

    final viewport = scrollable.context.findRenderObject() as RenderBox?;
    if (viewport == null || !viewport.attached || !viewport.hasSize) return;

    final vh = viewport.size.height;
    if (vh <= 0) return;

    final top = box.localToGlobal(Offset.zero, ancestor: viewport).dy;
    final height = box.size.height;

    final head = (top / vh).clamp(0.0, 1.0);
    // 아래끝이 바닥에 닿는 순간(top + height == vh)을 0,
    // 위끝이 꼭대기를 지나는 순간(top == 0)을 1 로 잡는다.
    final span = vh + height;
    final pass = span <= 0 ? 0.0 : ((vh - top) / span).clamp(0.0, 1.0);

    if ((head - _headFraction).abs() < 0.001 &&
        (pass - _passFraction).abs() < 0.001) {
      return;
    }
    _headFraction = head;
    _passFraction = pass;
    onStageChanged(head, pass);
  }

  /// 자리가 바뀔 때마다 불린다. 구현체가 [setState] 여부를 정한다 —
  /// 스크롤 한 번에 프레임마다 불리므로 여기서 무조건 재구성하면 안 된다.
  void onStageChanged(double head, double pass);
}

// ─────────────────────────────────────────────────────────────────────
// 한 번 긋는 획
// ─────────────────────────────────────────────────────────────────────

/// 화면에 들어올 때 왼쪽에서 오른쪽으로 열린다. **한 번만** 열고,
/// 다시 올려도 닫지 않는다 — 읽은 것을 되감는 화면은 없다.
///
/// [StrokeIn] 과 조형은 같지만 **시점이 다르다.** 그쪽은 위젯이 만들어질 때
/// 열려서, 목록 아래쪽의 카드는 아무도 안 볼 때 이미 다 열려 있었다.
/// 스크롤로 내려가면 정지 화면이 나타나는 셈이라 연출이 통째로 낭비됐다.
class Reveal extends StatefulWidget {
  final Widget child;

  /// 연달아 나오는 항목의 순번. 같은 화면에 함께 들어오면 시차를 준다.
  final int index;

  /// 위끝이 뷰포트의 어디까지 올라오면 열지. 0.9 면 화면 아래 10% 에
  /// 걸쳤을 때. 너무 낮게 잡으면 이미 다 읽은 뒤에 열린다.
  final double trigger;

  final Alignment from;

  const Reveal({
    super.key,
    required this.child,
    this.index = 0,
    this.trigger = 0.92,
    this.from = Alignment.centerLeft,
  });

  @override
  State<Reveal> createState() => _RevealState();
}

class _RevealState extends _StageWatcher<Reveal>
    with SingleTickerProviderStateMixin {
  // `late final` 초기화식으로 두면 한 번도 안 읽힌 채 dispose 에서
  // 처음 만들어진다 — 이미 죽은 State 위에 티커를 다는 셈이다.
  late final AnimationController _c;
  bool _fired = false;

  @override
  void initState() {
    super.initState();
    _c = AnimationController(vsync: this, duration: AppMotion.stroke);
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  void onStageChanged(double head, double pass) {
    if (_fired || head > widget.trigger) return;
    _fired = true;
    final d = AppMotion.stagger * widget.index;
    if (d == Duration.zero) {
      _c.forward();
    } else {
      Future.delayed(d, () {
        if (mounted) _c.forward();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (reduceMotion) return widget.child;

    return AnimatedBuilder(
      animation: _c,
      builder: (_, child) {
        final t = AppMotion.strokeCurve.transform(_c.value);
        return ClipRect(
          // 폭을 줄이지 않고 **그리기만** 자른다. `Align(widthFactor:)` 로
          // 열면 애니메이션 도중의 폭이 곧 배치 폭이 되어 자식이 실제로
          // 좁아진다 — 목록에서 카드마다 오른쪽 끝이 어긋났던 원인이다.
          clipper: StrokeClipper(t, widget.from),
          child: Opacity(opacity: (t * 1.8).clamp(0.0, 1.0), child: child),
        );
      },
      child: widget.child,
    );
  }
}

// ─────────────────────────────────────────────────────────────────────
// 지나가는 동안의 진행도
// ─────────────────────────────────────────────────────────────────────

/// 이 위젯이 화면을 지나가는 동안의 진행도를 자식에게 준다.
///
/// [from]~[to] 구간을 0~1 로 다시 편다. 기본값(0.15~0.62)은 실측이다 —
/// 섹션이 화면 가운데쯤 올라왔을 때 다 차야 읽는 속도와 맞는다.
/// 1.0 까지 끌면 다 읽고 지나간 뒤에야 완성되어 아무도 못 본다.
class Scrub extends StatefulWidget {
  final Widget Function(BuildContext context, double t) builder;
  final double from;
  final double to;

  const Scrub({
    super.key,
    required this.builder,
    this.from = 0.15,
    this.to = 0.62,
  });

  @override
  State<Scrub> createState() => _ScrubState();
}

class _ScrubState extends _StageWatcher<Scrub> {
  double _t = 0;

  @override
  void onStageChanged(double head, double pass) {
    final span = widget.to - widget.from;
    final next = span <= 0
        ? 1.0
        : ((pass - widget.from) / span).clamp(0.0, 1.0);
    // 되감지 않는다. 위로 다시 올렸을 때 값이 줄어들면 '지워지는' 것처럼
    // 보이는데, 기록이 지워지는 화면은 이 서비스에서 뜻이 나쁘다.
    if (next <= _t) return;
    setState(() => _t = next);
  }

  @override
  Widget build(BuildContext context) =>
      widget.builder(context, reduceMotion ? 1.0 : _t);
}

// ─────────────────────────────────────────────────────────────────────
// 세어 올리는 장부 숫자
// ─────────────────────────────────────────────────────────────────────

/// 화면에 들어오면 0 부터 [value] 까지 세어 올린다.
///
/// **고정폭 숫자라 자리가 흔들리지 않는다**(`ledgerFigures`). 비례폭으로
/// 세면 1 이 좁아서 숫자가 세어지는 내내 옆 칸이 들썩인다 — 그게 이
/// 연출이 싸구려로 보이는 가장 흔한 이유다.
class Tally extends StatefulWidget {
  final int value;
  final double size;
  final Color? color;
  final FontWeight weight;

  /// 천 단위 구분을 붙일지. 등수처럼 작은 수에는 끈다.
  final bool grouped;

  const Tally(
    this.value, {
    super.key,
    this.size = 27,
    this.color,
    this.weight = FontWeight.w800,
    this.grouped = true,
  });

  @override
  State<Tally> createState() => _TallyState();
}

class _TallyState extends _StageWatcher<Tally>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c;
  bool _fired = false;

  @override
  void initState() {
    super.initState();
    // 세는 시간은 획보다 길다. 같으면 숫자가 '휙' 지나가 안 읽힌다.
    _c = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1150),
    );
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  void onStageChanged(double head, double pass) {
    if (_fired || head > 0.92) return;
    _fired = true;
    _c.forward();
  }

  static String _fmt(int v, bool grouped) => grouped
      ? v.toString().replaceAllMapped(
          RegExp(r'(\d)(?=(\d{3})+$)'),
          (m) => '${m[1]},',
        )
      : v.toString();

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final style = TextStyle(
      fontFamily: 'Paperlogy',
      fontSize: widget.size,
      fontWeight: widget.weight,
      height: 1.0,
      letterSpacing: widget.size * -0.045,
      color: widget.color ?? AppColors.inkOn(dark),
      fontFeatures: ledgerFigures,
    );

    if (reduceMotion) {
      return Text(_fmt(widget.value, widget.grouped), style: style);
    }

    return AnimatedBuilder(
      animation: _c,
      builder: (_, _) {
        final t = Curves.easeOutQuart.transform(_c.value);
        return Text(
          _fmt((widget.value * t).round(), widget.grouped),
          style: style,
        );
      },
    );
  }
}

// ─────────────────────────────────────────────────────────────────────
// 읽은 만큼 차는 머리띠
// ─────────────────────────────────────────────────────────────────────

/// 화면 맨 위 주묵 한 줄이 **읽은 만큼** 찬다.
///
/// 진행 막대를 따로 만들지 않았다. 머리띠는 이미 모든 화면 맨 위에 있고,
/// 거기에 뜻을 하나 더 얹는 편이 새 부품을 얹는 것보다 조용하다.
///
/// **스크롤 컨트롤러를 찾아다니지 않는다.** 처음엔 머리띠가 스스로
/// `PrimaryScrollController` 를 뒤지게 했는데, 스크롤할 것이 없는 화면에서는
/// 영영 못 찾고 매 프레임 다시 찾으러 가는 **바쁜 대기**가 됐다.
/// 지금은 본문 쪽에서 스크롤 알림을 받아 값만 흘려보낸다 — 찾을 일이 없다.
class ReadingBand extends StatelessWidget {
  final double height;

  /// 0~1. [AppShell] 이 본문의 스크롤 알림을 받아 채운다.
  final ValueListenable<double> progress;

  const ReadingBand({super.key, required this.progress, this.height = 3});

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final accent = AppColors.accentOn(dark);

    // **`width: double.infinity` 를 빼면 안 된다.** Column 의 교차축 제약은
    // 느슨해서, 높이만 준 SizedBox 는 폭 0 으로 눕는다 — 머리띠가 통째로
    // 사라졌다(실측). 앞서 자(尺) 막대가 높이 0 이 됐던 것과 같은 함정을
    // 축만 바꿔 반복한 것이다: **한 축만 정한 상자는 나머지 축에서 접힌다.**
    return SizedBox(
      height: height,
      width: double.infinity,
      child: Stack(
        children: [
          // 안 읽은 쪽도 **주묵으로 남긴다.** 0.22 로 뒀더니 첫 화면에서
          // 머리띠가 거의 안 보였다 — 진행도를 얻자고 브랜드 표시를 잃은
          // 셈이다. 0.45 면 '조금 옅은 주묵 줄'로 읽히고, 읽은 쪽은 그
          // 위에 온전한 주묵으로 덮인다. 표시는 늘 있고 진행도 보인다.
          Positioned.fill(
            child: ColoredBox(color: accent.withValues(alpha: 0.45)),
          ),
          ValueListenableBuilder<double>(
            valueListenable: progress,
            builder: (_, t, _) => FractionallySizedBox(
              alignment: Alignment.centerLeft,
              widthFactor: t.clamp(0.0, 1.0),
              heightFactor: 1,
              child: ColoredBox(color: accent),
            ),
          ),
        ],
      ),
    );
  }
}

/// 본문의 스크롤 알림에서 진행도를 뽑아 [notifier] 에 흘린다.
///
/// **바깥 세로 스크롤만 본다.** 가로 휠·목록 안 목록까지 세면 엉뚱한
/// 스크롤이 머리띠를 움직인다 — 테크트리의 가로 스크롤이 그렇다.
class ReadingProgress extends StatelessWidget {
  final ValueNotifier<double> notifier;
  final Widget child;

  const ReadingProgress({
    super.key,
    required this.notifier,
    required this.child,
  });

  void _update(ScrollMetrics m, int depth) {
    if (depth != 0 || m.axis != Axis.vertical) return;
    if (!m.hasContentDimensions) return;
    final range = m.maxScrollExtent - m.minScrollExtent;
    // 스크롤할 것이 없는 화면은 **가득 찬 것으로 본다.** 0 으로 두면
    // '아직 안 읽었다'가 아니라 고장으로 보인다.
    final t = range <= 8
        ? 1.0
        : ((m.pixels - m.minScrollExtent) / range).clamp(0.0, 1.0);
    if ((t - notifier.value).abs() < 0.002) return;
    notifier.value = t;
  }

  @override
  Widget build(BuildContext context) {
    // 두 겹이 필요하다. ScrollMetricsNotification 은 ScrollNotification 의
    // 자식이 아니라서, 이것만으로는 **첫 배치**(아직 굴리기 전)의 값을
    // 못 받는다 — 새 화면으로 옮겼을 때 머리띠가 옛 값을 들고 있게 된다.
    return NotificationListener<ScrollMetricsNotification>(
      onNotification: (n) {
        _update(n.metrics, n.depth);
        return false;
      },
      child: NotificationListener<ScrollNotification>(
        onNotification: (n) {
          _update(n.metrics, n.depth);
          return false;
        },
        child: child,
      ),
    );
  }
}
