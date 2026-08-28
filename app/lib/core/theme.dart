import 'package:flutter/material.dart';

/// 학원실록 디자인 시스템 — 「實錄 / The Annals」
///
/// 이 서비스는 실명 사업자를 다루는 **기록물**이지 추천 광고가 아니다.
/// 그래서 화면의 성격을 '앱'이 아니라 '문서'로 잡았다. 결정을 축마다
/// 적어 둔다 — 나중에 하나만 바꾸면 나머지가 다 어긋나기 때문이다.
///
///   바탕   순백이 아니라 **한지**(#F4F0E6). 흰 화면은 값이 0 인 배경이지만
///          종이는 그 자체로 '기록물'이라는 맥락을 깐다.
///   구분   그림자가 아니라 **계선(界線)**. 실록 판면의 세로 괘선에서 왔다.
///          카드를 띄우지 않고 줄로 가른다. 떠 있는 것은 광고지 기록이 아니다.
///   모서리 알약(pill)을 쓰지 않는다. 2~4px. 종이에 그은 칸은 둥글지 않다.
///   강조   **주묵(朱墨) 하나**(#C4392A). 인장의 색이다. 넓게 칠하지 않고
///          찍는다 — 1위, 현재 위치, 검증 도장에만.
///   회색   푸른 기 없는 **따뜻한 재색**. 종이 위에서 파란 회색은 뜬다.
///   숫자   **장부 숫자**(tabular). 등수·점수·표본은 자리를 맞춰 세로로
///          읽히게 한다. 비례폭 숫자는 줄이 바뀔 때마다 흔들린다.
///
/// 색 이름은 안료 이름을 따랐다. `blue600` 같은 이름은 다음 사람이
/// '왜 이 파랑인가'를 물을 수 없게 만든다.
class AppColors {
  // ── 브랜드 (로고에서 온 값 — 바꾸지 않는다)
  /// 실록의 표지. 이제 '깊은 바탕' 역할을 맡는다.
  static const navy = Color(0xFF182448);
  static const navyBright = Color(0xFF2E4A7D);

  /// 금박 테두리. **사람이 손댄 것**(큐레이션·대표 지정)에만 쓴다.
  static const gold = Color(0xFFB08D57);
  static const goldLight = Color(0xFFD9BE92);
  static const cream = Color(0xFFF5EFE3);

  // ── 주묵(朱墨). 이 디자인의 단 하나뿐인 강조색.
  //    넓은 면을 칠하는 데 쓰지 않는다. 도장은 작아야 도장이다.
  static const vermilion = Color(0xFFC4392A);
  static const vermilionDeep = Color(0xFF97281B);
  static const vermilionWash = Color(0xFFF3E0DB);

  // ── 먹 / 종이
  static const ink = Color(0xFF14161C);
  static const inkSoft = Color(0xFF2A2E38);

  /// 본문 보조. 푸른 회색이 아니라 **따뜻한 재색**이다.
  static const slate = Color(0xFF6B675E);
  static const mist = Color(0xFF9C978B);

  /// 계선. 종이 위의 괘선 두께로 쓴다 — 굵으면 표가 되고 얇으면 판면이 된다.
  static const line = Color(0xFFDDD5C4);
  static const lineSoft = Color(0xFFE9E2D3);

  /// 카드 면. 종이보다 아주 조금 밝은 정도. 순백으로 두면 카드가 뜬다.
  static const surface = Color(0xFFFCFAF4);
  static const canvas = Color(0xFFF4F0E6);

  /// 한 단계 더 눌린 바탕. 섹션을 번갈아 눕힐 때 쓴다.
  static const canvasDeep = Color(0xFFEBE4D3);

  // ── 다크 = 먹빛. 남색 화면이 아니라 **먹**이어야 종이의 반대편이 된다.
  static const darkCanvas = Color(0xFF101218);
  static const darkSurface = Color(0xFF181B23);
  static const darkLine = Color(0xFF2C303B);
  static const darkInk = Color(0xFFEDE7D9);

  // ── 기둥별 색. 안료 계열로 낮춰 종이 위에 앉게 했다.
  //    형광에 가까운 원색은 한지 바탕에서 혼자 떠오른다.
  /// 쪽빛 — 평판
  static const reputation = Color(0xFF2E4E8A);

  /// 주황 — 화제성
  static const momentum = Color(0xFFC4692A);

  /// 청자 — 투명성
  static const transparency = Color(0xFF3E7D66);

  /// 자주 — 진입난이도
  static const selectivity = Color(0xFF6E3B6E);

  // ── 상태
  static const rising = Color(0xFFC4392A); // 국내 관행: 상승=빨강
  static const falling = Color(0xFF2E4E8A);
  static const verified = Color(0xFF3E7D66);
  static const estimated = Color(0xFF9A6C1E);

  static const pillars = <String, Color>{
    'reputation': reputation,
    'momentum': momentum,
    'transparency': transparency,
    'selectivity': selectivity,
  };

  /// 과목별 색. 테크트리 그래프와 태그에서 공유한다.
  static const subjects = <String, Color>{
    'math': reputation,
    'english': Color(0xFFB4442C),
    'korean': selectivity,
    'science': transparency,
    // 키가 'art' 였다. 표시 이름 쪽은 'arts' 라 색을 못 찾고
    // 회색으로 떨어졌다 — 예체능만 색 코드에서 빠져 있었다.
    'arts': Color(0xFF9A6C1E),
    'etc': Color(0xFF6B675E),
  };

  /// 먹빛 바탕에서 쓰는 과목 색.
  ///
  /// 안료 색은 한지 위에서 앉으라고 낮춰 잡은 값이라, 먹빛 바탕에
  /// 그대로 쓰면 가라앉는다. 과목 줄의 색 사각은 7px 밖에 안 되는데
  /// 쪽빛 #2E4E8A 를 #101218 위에 두면 사각인지도 안 보였다(실측).
  /// **색 코드는 두 판에서 똑같이 읽혀야 코드다.**
  static const _subjectsDark = <String, Color>{
    'math': Color(0xFF5E86C8),
    'english': Color(0xFFDE7A62),
    'korean': Color(0xFFA472A4),
    'science': Color(0xFF63AF93),
    'arts': Color(0xFFC79A4B),
    'etc': Color(0xFF9C978B),
  };

  /// 과목 색을 밝기에 맞춰 고른다. **과목 색이 필요한 곳은 전부 이걸 쓴다** —
  /// `subjects[key]` 를 직접 읽으면 어두운 판에서만 조용히 가라앉는다.
  static Color subjectOn(String? key, bool dark) =>
      (dark ? _subjectsDark[key] : subjects[key]) ??
      (dark ? mist : slate);

  /// 밝기에 따라 갈리는 값을 한 곳에서 고른다. 화면마다
  /// `dark ? A : B` 를 반복하면 반드시 한 곳을 빠뜨린다.
  static Color inkOn(bool dark) => dark ? darkInk : ink;
  static Color mutedOn(bool dark) => dark ? mist : slate;
  static Color ruleOn(bool dark) => dark ? darkLine : line;
  static Color ruleSoftOn(bool dark) =>
      dark ? const Color(0xFF23262F) : lineSoft;
  static Color surfaceOn(bool dark) => dark ? darkSurface : surface;
  static Color canvasOn(bool dark) => dark ? darkCanvas : canvas;
  static Color canvasDeepOn(bool dark) =>
      dark ? const Color(0xFF0B0D12) : canvasDeep;
  static Color accentOn(bool dark) =>
      dark ? const Color(0xFFE05943) : vermilion;
}

class AppSpace {
  static const xs = 4.0;
  static const sm = 8.0;
  static const md = 16.0;
  static const lg = 24.0;
  static const xl = 40.0;
  static const xxl = 72.0;
  static const maxContent = 1180.0;

  /// 좌측 색인 여백(index rail)의 폭. 실록 판면의 판심(版心)처럼
  /// 본문 왼쪽에 고정으로 비워 두고 기록 번호·연도·표본 수를 넣는다.
  /// 이 값이 레이아웃 비대칭의 근거다 — 가운데 정렬을 쓰지 않는 이유.
  static const rail = 116.0;

  /// 레일을 넣을 수 있는 최소 화면 폭. 실측: 레일 116 + 본문 최소 460
  /// + 좌우 여백 48 = 624. 여유를 둬 700 으로 잡았다. 그보다 좁으면
  /// 레일 내용을 본문 **위**로 한 줄 올린다 — 지우지 않는다.
  static const railMinWidth = 700.0;
}

/// 모서리. **알약을 쓰지 않는다** — 이 디자인이 흔한 핀테크 계열과
/// 갈리는 가장 눈에 띄는 지점이다. 종이에 그은 칸은 둥글지 않다.
class AppRadius {
  static const none = 0.0;
  static const sm = 2.0;
  static const md = 3.0;
  static const lg = 4.0;

  /// 남겨 둔다 — 아바타·원형 다이얼처럼 **정말 원이어야 하는 곳**만.
  static const pill = 999.0;
}

/// 획(劃)의 두께. 계선은 굵기가 곧 위계다.
class AppRule {
  static const hair = 0.7;
  static const thin = 1.0;
  static const bold = 2.0;

  /// 섹션을 여는 굵은 획. 제목 위에 짧게 긋는다.
  static const stroke = 3.0;
}

/// 모션 토큰.
///
/// 흔한 '아래에서 위로 떠오르며 흐려짐'을 쓰지 않는다. 여기서는
/// **획을 긋고(wipe) 도장을 찍는다(press)**. 붓이 지나가듯 왼쪽에서
/// 오른쪽으로 열리고, 도장은 조금 크게 시작해 눌러 앉는다.
class AppMotion {
  static const stroke = Duration(milliseconds: 620);
  static const strokeCurve = Curves.easeOutQuart;
  static const press = Duration(milliseconds: 420);
  static const pressCurve = Curves.easeOutBack;
  static const quick = Duration(milliseconds: 180);

  /// 연달아 나오는 항목의 시차. 70ms 를 넘기면 '느리다'로 읽힌다.
  static const stagger = Duration(milliseconds: 70);
}

/// 장부 숫자 — 자릿수가 흔들리지 않게 고정폭으로 쓴다.
/// 등수·점수·표본 수는 세로로 견주는 값이라 폭이 흔들리면 못 읽는다.
const ledgerFigures = <FontFeature>[FontFeature.tabularFigures()];

ThemeData buildTheme({required bool dark}) {
  final onSurface = AppColors.inkOn(dark);
  final muted = AppColors.mutedOn(dark);
  final rule = AppColors.ruleOn(dark);
  final accent = AppColors.accentOn(dark);

  final scheme = (dark ? const ColorScheme.dark() : const ColorScheme.light())
      .copyWith(
        primary: dark ? AppColors.darkInk : AppColors.ink,
        onPrimary: dark ? AppColors.ink : AppColors.cream,
        secondary: accent,
        onSecondary: Colors.white,
        tertiary: AppColors.gold,
        surface: AppColors.surfaceOn(dark),
        onSurface: onSurface,
        outline: rule,
        outlineVariant: AppColors.ruleSoftOn(dark),
      );

  TextStyle t(
    double size,
    FontWeight weight, {
    double height = 1.45,
    Color? color,
    double spacing = -0.2,
  }) => TextStyle(
    fontFamily: 'Paperlogy',
    fontSize: size,
    fontWeight: weight,
    height: height,
    letterSpacing: spacing,
    color: color ?? onSurface,
  );

  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    scaffoldBackgroundColor: AppColors.canvasOn(dark),
    fontFamily: 'Paperlogy',
    dividerColor: rule,
    dividerTheme: DividerThemeData(
      color: rule,
      thickness: AppRule.hair,
      space: AppSpace.lg,
    ),
    // ── 한글 제목은 자간을 세게 조인다. Paperlogy 는 큰 크기에서 자간이
    //    벌어져 보여, 기본값으로 두면 '큰 글씨'일 뿐 '표제'가 되지 않는다.
    //    크기가 커질수록 더 조인다.
    textTheme: TextTheme(
      displayLarge: t(66, FontWeight.w800, height: 0.98, spacing: -3.8),
      displayMedium: t(46, FontWeight.w800, height: 1.04, spacing: -2.4),
      headlineLarge: t(33, FontWeight.w800, height: 1.16, spacing: -1.5),
      headlineMedium: t(24, FontWeight.w700, height: 1.26, spacing: -1.0),
      titleLarge: t(19, FontWeight.w700, height: 1.34, spacing: -0.65),
      titleMedium: t(16, FontWeight.w600, spacing: -0.4),
      bodyLarge: t(16, FontWeight.w400, height: 1.72, spacing: -0.15),
      bodyMedium: t(14, FontWeight.w400, height: 1.68, color: muted),
      bodySmall: t(12.5, FontWeight.w400, height: 1.55, color: muted),
      labelLarge: t(13.5, FontWeight.w600, spacing: -0.1),
      // 레일·머리말의 작은 라벨. **자간을 벌린다** — 좁은 자간이 기본인
      // 화면에서 넓은 자간은 그 자체로 '메타 정보'라는 신호가 된다.
      labelMedium: t(
        11,
        FontWeight.w600,
        spacing: 1.6,
        color: muted,
        height: 1.4,
      ),
      labelSmall: t(
        10,
        FontWeight.w600,
        spacing: 1.2,
        color: muted,
        height: 1.4,
      ),
    ),
    cardTheme: CardThemeData(
      elevation: 0,
      margin: EdgeInsets.zero,
      color: AppColors.surfaceOn(dark),
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppRadius.md),
        side: BorderSide(color: rule, width: AppRule.hair),
      ),
    ),
    // 버튼은 각지게. 알약 버튼을 하나라도 남기면 그것만 눈에 띈다.
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: dark ? AppColors.darkInk : AppColors.ink,
        foregroundColor: dark ? AppColors.ink : AppColors.cream,
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 17),
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(AppRadius.sm)),
        ),
        textStyle: t(14.5, FontWeight.w700, spacing: -0.3),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: onSurface,
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 17),
        side: BorderSide(color: rule, width: AppRule.thin),
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(AppRadius.sm)),
        ),
        textStyle: t(14.5, FontWeight.w700, spacing: -0.3),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: accent,
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(AppRadius.sm)),
        ),
        textStyle: t(13.5, FontWeight.w700, spacing: -0.2),
      ),
    ),
    iconButtonTheme: IconButtonThemeData(
      style: IconButton.styleFrom(
        foregroundColor: onSurface,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(AppRadius.sm)),
        ),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: AppColors.surfaceOn(dark),
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(AppRadius.sm),
        borderSide: BorderSide(color: rule, width: AppRule.thin),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(AppRadius.sm),
        borderSide: BorderSide(color: rule, width: AppRule.thin),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(AppRadius.sm),
        borderSide: BorderSide(color: accent, width: AppRule.thin),
      ),
      hintStyle: t(14, FontWeight.w400, color: AppColors.mist),
    ),
    chipTheme: ChipThemeData(
      backgroundColor: Colors.transparent,
      side: BorderSide(color: rule, width: AppRule.hair),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.all(Radius.circular(AppRadius.sm)),
      ),
      labelStyle: t(12, FontWeight.w600, spacing: -0.1),
    ),
    tooltipTheme: TooltipThemeData(
      decoration: BoxDecoration(
        color: dark ? AppColors.darkSurface : AppColors.ink,
        borderRadius: BorderRadius.circular(AppRadius.sm),
        border: Border.all(color: rule, width: AppRule.hair),
      ),
      textStyle: t(
        12,
        FontWeight.w500,
        color: dark ? AppColors.darkInk : AppColors.cream,
      ),
    ),
    progressIndicatorTheme: ProgressIndicatorThemeData(
      color: accent,
      linearTrackColor: AppColors.ruleSoftOn(dark),
      circularTrackColor: AppColors.ruleSoftOn(dark),
    ),
    snackBarTheme: SnackBarThemeData(
      backgroundColor: dark ? AppColors.darkSurface : AppColors.ink,
      contentTextStyle: t(
        13.5,
        FontWeight.w500,
        color: dark ? AppColors.darkInk : AppColors.cream,
      ),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.all(Radius.circular(AppRadius.sm)),
      ),
      behavior: SnackBarBehavior.floating,
    ),
  );
}
