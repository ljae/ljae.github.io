import 'package:flutter/widgets.dart';

/// 헤더 배치 규칙 — 폭 하나에서 전부 파생시킨다.
///
/// 예전에는 임계값이 셋(로고 720, 내비 860, 필터 1180)이었고 서로를 몰랐다.
/// 그래서 900px 에서는 내비가 켜지는데 자리가 모자라 '산식'과 검색이
/// 잘려 나갔고, 375px 에서는 학교급 선택기가 화면 밖으로 밀려났다.
///
/// 지금은 요소가 차지하는 폭을 실제로 더해 보고 들어갈 것만 켠다.
/// 임계값을 눈으로 정하지 않았다는 뜻이다 — 아래 상수는 각 요소의
/// 최소 점유 폭이고, 합이 넘치면 우선순위가 낮은 것부터 끈다.
@immutable
class HeaderLayout {
  /// 요소별 최소 점유 폭. 실측해서 넣었다.
  static const _search = 44.0;
  static const _filters = 158.0;   // 드롭다운 두 개 + 사이 간격
  static const _wheels = 186.0;    // 휠 두 개 + 사이 간격
  static const _byOperator = 96.0;
  static const _nav = 430.0;       // 메뉴 6개
  static const _gap = 16.0;

  final double logo;
  final double titleSize;
  final bool showNav;
  final bool showByOperator;
  final bool showFilters;
  final bool useWheels;

  const HeaderLayout({
    required this.logo,
    required this.titleSize,
    required this.showNav,
    required this.showByOperator,
    required this.showFilters,
    required this.useWheels,
  });

  /// [available] 은 좌우 여백을 뺀 헤더 안쪽 폭이다.
  factory HeaderLayout.forWidth(double available) {
    // 로고와 제목은 항상 나온다. 브랜드가 먼저 사라지면 안 된다.
    final logo = available >= 1000
        ? 84.0
        : available >= 700
            ? 64.0
            : 46.0;
    final titleSize = available >= 1000
        ? 30.0
        : available >= 700
            ? 25.0
            : 20.0;

    // 제목 글자 폭은 '학원실록' 네 글자 기준으로 잡는다.
    var used = logo + _gap + titleSize * 4.1 + _search;

    // 우선순위: 필터 > 내비 > 운영사 표기.
    // 필터는 모든 화면의 내용을 바꾸는 축이라 가장 먼저 자리를 준다.
    // 내비는 좁은 화면에서 하단 바가 대신한다.
    // 운영사 표기는 없어도 기능이 아쉽지 않다 — 푸터에도 있다.
    final showFilters = used + _gap + _filters <= available;
    if (showFilters) used += _gap + _filters;

    final showNav = used + _gap + _nav <= available;
    if (showNav) used += _gap + _nav;

    final showByOperator = used + _gap + _byOperator <= available;
    if (showByOperator) used += _gap + _byOperator;

    // 휠은 자리가 넉넉할 때만. 좁은 곳에서 휠을 굴리면 잘못 건드리기 쉽다.
    final useWheels =
        showFilters && used + (_wheels - _filters) <= available;

    return HeaderLayout(
      logo: logo,
      titleSize: titleSize,
      showNav: showNav,
      showByOperator: showByOperator,
      showFilters: showFilters,
      useWheels: useWheels,
    );
  }

  /// 상단 바 높이. 휠이 있으면 그만큼만 키운다.
  double get barHeight => useWheels ? 96 : logo + 20;

  @override
  bool operator ==(Object other) =>
      other is HeaderLayout &&
      other.logo == logo &&
      other.titleSize == titleSize &&
      other.showNav == showNav &&
      other.showByOperator == showByOperator &&
      other.showFilters == showFilters &&
      other.useWheels == useWheels;

  @override
  int get hashCode =>
      Object.hash(logo, titleSize, showNav, showByOperator, showFilters, useWheels);
}
