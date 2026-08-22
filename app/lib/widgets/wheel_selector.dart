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

  int get _index =>
      widget.options.indexWhere((o) => o.$1 == widget.selected).clamp(0, 1 << 30);

  @override
  void initState() {
    super.initState();
    _controller = FixedExtentScrollController(initialItem: _index);
  }

  @override
  void didUpdateWidget(covariant WheelSelector<T> old) {
    super.didUpdateWidget(old);
    if (old.selected != widget.selected && _controller!.hasClients) {
      final target = _index;
      if (_controller!.selectedItem != target) {
        // 밖에서 값이 바뀐 경우다. 툭 끊기지 않게 굴려서 옮긴다.
        _controller!.animateToItem(target,
            duration: const Duration(milliseconds: 220),
            curve: Curves.easeOutCubic);
      }
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
