import 'package:flutter/material.dart';

import '../core/theme.dart';
import '../data/models.dart';

/// 과목 선택 줄 — **화면마다 하나의 모양, 하나의 순서.**
///
/// 고치기 전에는 같은 일을 네 가지 모양으로 하고 있었다:
///
///     랭킹        밑줄 탭          수학부터
///     로드맵(모바일) 꽉 채운 알약(999px) 영어부터
///     후기 쓰기    ChoiceChip       수학부터, 기타 뺌
///     후기 거르기  FilterChip       수학부터, 있는 것만
///
/// 모양이 넷이면 같은 조작인 줄 모르고, 순서가 둘이면 손이 기억을 못 한다.
/// 순서는 [subjectOrder] 하나로 모았고(근거는 거기 적어 뒀다), 모양은
/// 이 파일 하나가 갖는다.
///
/// ## 조형
///
///   색 사각    과목 색은 꼬리표·로드맵·트리에서 이미 쓰는 코드다. 선택
///             여부와 무관하게 늘 보여 줘 **색과 과목의 짝**을 이 줄이
///             가르치게 했다. `PillarBar` 가 쓰는 것과 같은 장치다.
///   밑줄      선택 표시는 **주묵**이다. 과목 색으로 그으면 예뻐 보이지만,
///             주묵은 이 앱에서 '지금 여기'를 뜻하는 하나뿐인 신호라
///             내비·필터와 뜻이 어긋난다. 정체성은 사각이, 위치는 밑줄이.
///   계선      학술 넷과 예체능·기타 사이에 세로 계선을 세운다. 장식이
///             아니라 **산식이 갈리는 자리**다 — 뒤 둘은 평판·화제성만 본다.
class SubjectBar extends StatelessWidget {
  /// 지금 고른 과목. `null` 이면 '전체'.
  final String? selected;

  /// `null` 이 올 수 있다 — [allowAll] 이 켜져 있고 '전체'를 고른 경우.
  final ValueChanged<String?> onChanged;

  /// 이것만 낸다. 비우면 [subjectOrder] 전부.
  /// 데이터에 없는 과목을 눌러 빈 화면을 보게 두지 않으려는 용도다.
  final Set<String>? only;

  /// '전체' 칸을 둘지. 거르개(filter)에서는 켜고, 랭킹처럼 반드시 하나를
  /// 골라야 하는 곳에서는 끈다 — 과목 없는 랭킹은 뜻을 설명할 수 없다.
  final bool allowAll;

  /// 예체능·기타를 낼지. 후기 작성처럼 학술만 받는 곳에서 끈다.
  final bool showNonAcademic;

  const SubjectBar({
    super.key,
    required this.selected,
    required this.onChanged,
    this.only,
    this.allowAll = false,
    this.showNonAcademic = true,
  });

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final keys = [
      for (final s in subjectOrder)
        if (only == null || only!.contains(s))
          if (showNonAcademic || isAcademicSubject(s)) s,
    ];
    if (keys.isEmpty) return const SizedBox.shrink();

    final items = <Widget>[
      if (allowAll)
        _SubjectTab(
          label: '전체',
          color: null,
          on: selected == null,
          onTap: () => onChanged(null),
        ),
      for (var i = 0; i < keys.length; i++) ...[
        // 학술과 비학술 사이에 계선. 앞이 학술이고 지금이 비학술일 때 한 번.
        if (i > 0 &&
            isAcademicSubject(keys[i - 1]) &&
            !isAcademicSubject(keys[i]))
          const _GroupRule(),
        _SubjectTab(
          label: subjectNames[keys[i]]!,
          color: AppColors.subjectOn(keys[i], dark),
          on: selected == keys[i],
          onTap: () => onChanged(keys[i]),
        ),
      ],
    ];

    // 과목이 여섯이면 좁은 화면에서 한 줄에 안 들어간다. 가로 스크롤만
    // 두면 잘린 칸이 있다는 것 자체가 안 보여 '예체능'을 못 찾는다.
    return LayoutBuilder(
      builder: (context, c) {
        final tight = c.maxWidth < 620 || items.length > 5;
        if (tight) {
          return Wrap(
            spacing: AppSpace.sm,
            runSpacing: 2,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: items,
          );
        }
        return SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: [
              for (final w in items)
                Padding(
                  padding: const EdgeInsets.only(right: AppSpace.sm),
                  child: w,
                ),
            ],
          ),
        );
      },
    );
  }
}

/// 학술 / 예체능·기타를 가르는 계선.
///
/// **폭을 반드시 못 박는다.** 처음엔 `SizedBox(height: 34, child: Center(…))`
/// 로 뒀는데, `Center` 는 폭 제약이 느슨하면 **최대까지 펼친다** — 계선
/// 하나가 1132px 짜리 덩어리가 되어 Wrap 의 한 줄을 통째로 차지했고,
/// 예체능·기타가 다음 줄로 밀려났다. 선은 안 보이고 줄만 갈라진 채였다.
/// (같은 함정을 축만 바꿔 세 번째 만났다 — 접히거나 펼쳐지거나.)
class _GroupRule extends StatelessWidget {
  const _GroupRule();

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 3),
      child: SizedBox(
        width: AppRule.thin,
        height: 20,
        child: ColoredBox(color: AppColors.ruleOn(dark)),
      ),
    );
  }
}

class _SubjectTab extends StatelessWidget {
  final String label;

  /// `null` 이면 '전체' — 색이 정해지지 않은 칸이라 빈 사각을 세운다.
  final Color? color;
  final bool on;
  final VoidCallback onTap;

  const _SubjectTab({
    required this.label,
    required this.color,
    required this.on,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final accent = AppColors.accentOn(dark);
    final c = color;

    return Semantics(
      button: true,
      selected: on,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppRadius.sm),
        child: AnimatedContainer(
          duration: AppMotion.quick,
          padding: const EdgeInsets.fromLTRB(11, 9, 11, 7),
          decoration: BoxDecoration(
            color: on
                ? accent.withValues(alpha: dark ? 0.13 : 0.07)
                : Colors.transparent,
            border: Border(
              bottom: BorderSide(
                color: on ? accent : AppColors.ruleOn(dark),
                width: on ? AppRule.bold : AppRule.hair,
              ),
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              // '전체'도 자리를 지킨다 — 사각이 없으면 글자 시작점이 어긋나
              // 줄이 들쭉날쭉해진다.
              _Marker(color: c, on: on, dark: dark),
              const SizedBox(width: 7),
              Text(
                label,
                style: TextStyle(
                  fontFamily: 'Paperlogy',
                  fontSize: 13.5,
                  fontWeight: on ? FontWeight.w800 : FontWeight.w500,
                  letterSpacing: -0.3,
                  color: on ? AppColors.inkOn(dark) : AppColors.mutedOn(dark),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// 과목 색 사각. '전체'는 속이 빈 사각 — 아직 색이 정해지지 않았다는 뜻.
class _Marker extends StatelessWidget {
  final Color? color;
  final bool on;
  final bool dark;
  const _Marker({required this.color, required this.on, required this.dark});

  @override
  Widget build(BuildContext context) {
    final c = color;
    if (c == null) {
      return SizedBox(
        width: 7,
        height: 7,
        child: DecoratedBox(
          decoration: BoxDecoration(
            border: Border.all(
              color: on ? AppColors.inkOn(dark) : AppColors.mutedOn(dark),
              width: AppRule.thin,
            ),
          ),
        ),
      );
    }
    // 안 고른 칸도 색을 보여 준다. 색과 과목의 짝을 이 줄이 가르친다 —
    // 다만 고른 칸보다 옅게 둬 '지금 여기'를 가리지 않는다.
    return SizedBox(
      width: 7,
      height: 7,
      child: ColoredBox(color: on ? c : c.withValues(alpha: 0.45)),
    );
  }
}
