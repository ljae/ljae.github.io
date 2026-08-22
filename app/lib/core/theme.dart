import 'package:flutter/material.dart';

/// 에듀트리 디자인 시스템.
///
/// 상록수(evergreen) 계열을 브랜드 축으로 삼는다. 자라나는 나무 = 테크트리라는
/// 은유를 색으로 유지하면서, 교육 앱이 흔히 쓰는 채도 높은 파랑을 피해
/// '신뢰할 만한 데이터 제품'으로 읽히게 하는 것이 목표.
class AppColors {
  // 브랜드
  static const evergreen = Color(0xFF12513F);
  static const evergreenBright = Color(0xFF1E9E76);
  static const gold = Color(0xFFE8B33C);

  // 잉크 / 표면
  static const ink = Color(0xFF0C1116);
  static const inkSoft = Color(0xFF1B242E);
  static const slate = Color(0xFF5A6874);
  static const mist = Color(0xFF8D9AA6);
  static const line = Color(0xFFE2E7EA);
  static const surface = Color(0xFFFFFFFF);
  static const canvas = Color(0xFFF5F7F6);

  // 다크
  static const darkCanvas = Color(0xFF0C1116);
  static const darkSurface = Color(0xFF151D25);
  static const darkLine = Color(0xFF26323C);

  // 기둥별 색 (랭킹·상세 전반에서 일관되게 쓴다)
  static const reputation = Color(0xFF2F7DD1);
  static const momentum = Color(0xFFE07A3E);
  static const transparency = Color(0xFF1E9E76);
  static const selectivity = Color(0xFF8B5CF6);

  // 상태
  static const rising = Color(0xFFDC2626);   // 국내 관행: 상승=빨강
  static const falling = Color(0xFF2563EB);
  static const verified = Color(0xFF1E9E76);
  static const estimated = Color(0xFFB45309);

  static const pillars = <String, Color>{
    'reputation': reputation,
    'momentum': momentum,
    'transparency': transparency,
    'selectivity': selectivity,
  };

  /// 과목별 색. 테크트리 그래프와 칩에서 공유한다.
  static const subjects = <String, Color>{
    'math': Color(0xFF2F7DD1),
    'english': Color(0xFFD1552F),
    'korean': Color(0xFF7A4FC0),
    'science': Color(0xFF1E9E76),
    'etc': Color(0xFF6B7785),
  };
}

class AppSpace {
  static const xs = 4.0;
  static const sm = 8.0;
  static const md = 16.0;
  static const lg = 24.0;
  static const xl = 40.0;
  static const xxl = 64.0;
  static const maxContent = 1180.0;
}

class AppRadius {
  static const sm = 8.0;
  static const md = 14.0;
  static const lg = 22.0;
  static const pill = 999.0;
}

ThemeData buildTheme({required bool dark}) {
  final scheme = dark
      ? const ColorScheme.dark(
          primary: AppColors.evergreenBright,
          secondary: AppColors.gold,
          surface: AppColors.darkSurface,
        )
      : const ColorScheme.light(
          primary: AppColors.evergreen,
          secondary: AppColors.gold,
          surface: AppColors.surface,
        );

  final onSurface = dark ? const Color(0xFFE8EDF0) : AppColors.ink;
  final muted = dark ? AppColors.mist : AppColors.slate;

  TextStyle t(double size, FontWeight weight,
          {double height = 1.45, Color? color, double spacing = -0.2}) =>
      TextStyle(
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
    scaffoldBackgroundColor: dark ? AppColors.darkCanvas : AppColors.canvas,
    fontFamily: 'Paperlogy',
    dividerColor: dark ? AppColors.darkLine : AppColors.line,
    textTheme: TextTheme(
      displayLarge: t(52, FontWeight.w800, height: 1.15, spacing: -1.4),
      displayMedium: t(40, FontWeight.w800, height: 1.18, spacing: -1.1),
      headlineLarge: t(30, FontWeight.w700, height: 1.25, spacing: -0.8),
      headlineMedium: t(23, FontWeight.w700, height: 1.3, spacing: -0.6),
      titleLarge: t(19, FontWeight.w600, height: 1.35),
      titleMedium: t(16, FontWeight.w600),
      bodyLarge: t(15.5, FontWeight.w400, height: 1.65),
      bodyMedium: t(14, FontWeight.w400, height: 1.6, color: muted),
      bodySmall: t(12.5, FontWeight.w400, height: 1.5, color: muted),
      labelLarge: t(13.5, FontWeight.w600, spacing: 0),
      labelMedium: t(12, FontWeight.w500, spacing: 0, color: muted),
    ),
    cardTheme: CardThemeData(
      elevation: 0,
      color: dark ? AppColors.darkSurface : AppColors.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppRadius.md),
        side: BorderSide(color: dark ? AppColors.darkLine : AppColors.line),
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 16),
        shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppRadius.sm)),
        textStyle: t(14.5, FontWeight.w600, color: Colors.white),
      ),
    ),
  );
}
