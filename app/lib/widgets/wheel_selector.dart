import 'dart:async';

import 'package:flutter/material.dart';

import '../core/theme.dart';

/// 헤더용 휠 선택기.
///
/// 칩 줄을 페이지마다 반복해 두면 화면마다 필터 상태가 따로 노는 것처럼
/// 보인다. 학군과 학교급은 서비스 전체를 관통하는 축이라 헤더에 한 번만
/// 두고 모든 화면이 같은 값을 본다.
///
/// 좁은 화면에서는 아예 쓰지 않는다. 헤더 높이가 한정된 곳에서 휠을
/// 굴리게 하면 잘못 건드리기 쉬워, 한 덩어리 버튼 + 시트로 바뀐다.
class WheelSelector<T> extends StatefulWidget {
  final String label;
  final List<(T value, String text)> options;
  final T selected;
  final ValueChanged<T> onChanged;
  final double width;

  const WheelSelector({
    super.key,
    required this.label,
    required this.options,
    required this.selected,
    required this.onChanged,
    this.width = 96,
  });

  @override
  State<WheelSelector<T>> createState() => _WheelSelectorState<T>();
}

class _WheelSelectorState<T> extends State<WheelSelector<T>> {
  FixedExtentScrollController? _controller;
  Timer? _settle;

  /// 선택값이 목록 어디에 있는가. 없으면 -1.
  ///
  /// 못 찾았을 때 0 으로 뭉개면 안 된다. 그러면 '목록이 아직 안 왔다'와
  /// '첫 칸이 선택됐다'가 같은 값이 되어, 아래 didUpdateWidget 이
  /// 바로잡아야 할 상황을 알아채지 못한다.
  int get _index => widget.options.indexWhere((o) => o.$1 == widget.selected);

  @override
  void initState() {
    super.initState();
    _controller = FixedExtentScrollController(initialItem: _index.clamp(0, 1 << 30));
  }

  @override
  void didUpdateWidget(covariant WheelSelector<T> old) {
    super.didUpdateWidget(old);
    final target = _index;
    if (target < 0 || !_controller!.hasClients) return;
    if (_controller!.selectedItem == target) return;

    // ★ 목록이 늦게 오는 경우를 반드시 함께 본다.
    //   학군 목록은 데이터가 도착해야 채워진다. 첫 빌드에서는 ['전체']
    //   하나뿐이라 'daechi' 를 못 찾고 휠이 0번 칸('전체')에 섰다.
    //   그 뒤 목록이 채워져도 selected 는 그대로라, 값이 바뀐 경우만
    //   보던 예전 코드는 아무것도 하지 않았다. 그래서 **화면은 '전체',
    //   실제 선택은 '대치'** 인 상태로 굳었다.
    if (old.options.length != widget.options.length) {
      // 사용자가 굴린 것이 아니라 목록이 도착한 것이다. 굴리지 않고 맞춘다.
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && _controller!.hasClients) _controller!.jumpToItem(target);
      });
      return;
    }
    if (old.selected != widget.selected) {
      // 밖에서 값이 바뀐 경우다. 툭 끊기지 않게 굴려서 옮긴다.
      _controller!.animateToItem(target,
          duration: const Duration(milliseconds: 220),
          curve: Curves.easeOutCubic);
    }
  }

  /// 휠이 멈춘 뒤에만 선택을 확정한다.
  ///
  /// 예전에는 지나가는 칸마다 onChanged 가 불렸다. 한 번 튕기면 상태가
  /// 대여섯 번 바뀌고 그때마다 화면 전체가 다시 그려져서, 손을 떼기도 전에
  /// 버벅였다. 스크롤이 잦아들면 그때 한 번만 알린다.
  void _commit(int index) {
    _settle?.cancel();
    _settle = Timer(const Duration(milliseconds: 140), () {
      if (!mounted) return;
      final value = widget.options[index].$1;
      if (value != widget.selected) widget.onChanged(value);
    });
  }

  @override
  void dispose() {
    _settle?.cancel();
    _controller?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final text = Theme.of(context).textTheme;

    return SizedBox(
      width: widget.width,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(widget.label,
              style: text.bodySmall?.copyWith(fontSize: 10.5, height: 1.1)),
          const SizedBox(height: 2),
          Container(
            height: 58,
            decoration: BoxDecoration(
              color: dark ? AppColors.darkCanvas : AppColors.canvas,
              borderRadius: BorderRadius.circular(AppRadius.sm),
              border: Border.all(color: dark ? AppColors.darkLine : AppColors.line),
            ),
            child: Stack(children: [
              // 선택 위치 표시. 휠에서 어느 칸이 '선택된 칸'인지 보이게 한다.
              Center(
                child: Container(
                  height: 22,
                  margin: const EdgeInsets.symmetric(horizontal: 4),
                  decoration: BoxDecoration(
                    color: AppColors.navy.withValues(alpha: dark ? 0.35 : 0.08),
                    borderRadius: BorderRadius.circular(6),
                  ),
                ),
              ),
              ListWheelScrollView.useDelegate(
                controller: _controller,
                itemExtent: 22,
                diameterRatio: 1.5,
                perspective: 0.003,
                physics: const FixedExtentScrollPhysics(),
                onSelectedItemChanged: _commit,
                childDelegate: ListWheelChildBuilderDelegate(
                  childCount: widget.options.length,
                  builder: (context, i) {
                    final active = widget.options[i].$1 == widget.selected;
                    return Center(
                      child: Text(
                        widget.options[i].$2,
                        style: TextStyle(
                          fontFamily: 'Paperlogy',
                          fontSize: active ? 13.5 : 12.5,
                          fontWeight: active ? FontWeight.w800 : FontWeight.w500,
                          letterSpacing: -0.3,
                          color: active
                              ? (dark ? Colors.white : AppColors.navy)
                              : AppColors.mist,
                        ),
                      ),
                    );
                  },
                ),
              ),
            ]),
          ),
        ],
      ),
    );
  }
}
