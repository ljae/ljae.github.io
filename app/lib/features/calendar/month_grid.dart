import 'package:flutter/material.dart';

import '../../core/theme.dart';
import '../../data/academy_calendar.dart';

/// 종류 색. 목록의 꼬리표와 달력 칸의 획이 **같은 색**을 써야 한 화면이
/// 같은 말을 한다. 주묵은 여기 없다 — 주묵은 '오늘' 하나에만 쓴다.
Color calendarKindColor(String kind, bool dark) => switch (kind) {
  'session' => AppColors.navyOn(dark),
  'test' => AppColors.estimatedOn(dark),
  _ => AppColors.mutedOn(dark),
};

/// 칸에 적는 작은 글자. 크기는 이 한 곳에서만 정한다 — 폭 판정이 이
/// 글자로 잰 값이라 둘이 어긋나면 판정이 거짓말을 한다.
const _labelSize = 10.0;
const _daySize = 12.0;
const _cellPad = 3.0;
const _stripe = 2.0;
const _stripeGap = 3.0;
const _labelGap = 2.0;
const _gridGap = AppSpace.lg;

/// 칸 폭으로 무엇을 그릴지 정하는 실측치. **눈으로 정하지 않는다** —
/// 글꼴·글자 배율이 바뀌면 같이 바뀌어야 하는 값이라 그릴 때 잰다.
class MonthGridMetrics {
  /// 한 칸에 짧은 말을 한 줄로 쓰는 데 드는 최소 폭('가나…'). 이보다
  /// 좁으면 글자 대신 종류 색 네모만 찍는다.
  final double labelCellMin;

  /// 두 달을 나란히 놓을 때 한 칸에 바라는 폭('가나다라…'). 이 폭이
  /// 안 나오면 위아래로 쌓는다 — 나란히 놓아 둘 다 점이 되느니 쌓아서
  /// 글자를 남긴다.
  final double comfortCellMin;

  final double labelLine;
  final double dayLine;

  const MonthGridMetrics({
    required this.labelCellMin,
    required this.comfortCellMin,
    required this.labelLine,
    required this.dayLine,
  });

  static TextStyle labelStyle(Color color) => TextStyle(
    fontFamily: 'Paperlogy',
    fontSize: _labelSize,
    fontWeight: FontWeight.w600,
    height: 1.2,
    letterSpacing: -0.3,
    color: color,
  );

  static TextStyle dayStyle(Color color, {bool strong = false}) => TextStyle(
    fontFamily: 'Paperlogy',
    fontSize: _daySize,
    fontWeight: strong ? FontWeight.w800 : FontWeight.w600,
    height: 1.25,
    color: color,
    fontFeatures: ledgerFigures,
  );

  static MonthGridMetrics of(BuildContext context) {
    final scaler = MediaQuery.textScalerOf(context);
    Size measure(String s, TextStyle style) {
      final tp = TextPainter(
        text: TextSpan(text: s, style: style),
        textDirection: TextDirection.ltr,
        textScaler: scaler,
        maxLines: 1,
      )..layout();
      final size = tp.size;
      tp.dispose();
      return size;
    }

    final label = labelStyle(const Color(0xFF000000));
    const chrome = _cellPad * 2 + _stripe + _stripeGap;
    final short = measure('가나…', label);
    final comfort = measure('가나다라…', label);
    return MonthGridMetrics(
      labelCellMin: short.width + chrome,
      comfortCellMin: comfort.width + chrome,
      labelLine: short.height,
      dayLine: measure('30', dayStyle(const Color(0xFF000000))).height,
    );
  }
}

/// 이번 달과 다음 달. 넓으면 나란히, 좁으면 위아래로.
class MonthGrids extends StatelessWidget {
  final DateTime today;
  final Map<DateTime, List<CalendarEvent>> byDay;

  /// 아래 목록에 머리가 있는 날. 이 날만 누를 수 있다.
  final Set<DateTime> listedDays;
  final ValueChanged<DateTime> onTapDay;

  const MonthGrids({
    super.key,
    required this.today,
    required this.byDay,
    required this.listedDays,
    required this.onTapDay,
  });

  @override
  Widget build(BuildContext context) {
    final metrics = MonthGridMetrics.of(context);
    final first = DateTime.utc(today.year, today.month, 1);
    final next = DateTime.utc(today.year, today.month + 1, 1);
    return LayoutBuilder(
      builder: (context, constraints) {
        final w = constraints.maxWidth;
        final sideBySide = w >= 2 * 7 * metrics.comfortCellMin + _gridGap;
        Widget grid(DateTime month) => MonthGrid(
          month: month,
          today: today,
          byDay: byDay,
          listedDays: listedDays,
          onTapDay: onTapDay,
          metrics: metrics,
        );
        if (sideBySide) {
          return Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(child: grid(first)),
              const SizedBox(width: _gridGap),
              Expanded(child: grid(next)),
            ],
          );
        }
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            grid(first),
            const SizedBox(height: AppSpace.lg),
            grid(next),
          ],
        );
      },
    );
  }
}

const _weekdayHead = ['일', '월', '화', '수', '목', '금', '토'];

/// 한 달. 일요일부터 일곱 칸. 칸은 계선으로 가르고 띄우지 않는다.
class MonthGrid extends StatelessWidget {
  final DateTime month;
  final DateTime today;
  final Map<DateTime, List<CalendarEvent>> byDay;
  final Set<DateTime> listedDays;
  final ValueChanged<DateTime> onTapDay;
  final MonthGridMetrics metrics;

  const MonthGrid({
    super.key,
    required this.month,
    required this.today,
    required this.byDay,
    required this.listedDays,
    required this.onTapDay,
    required this.metrics,
  });

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final text = Theme.of(context).textTheme;
    final y = month.year, m = month.month;
    final daysInMonth = DateTime.utc(y, m + 1, 0).day;
    // DateTime.weekday: 월 1 … 일 7 → 일요일 0 부터.
    final lead = DateTime.utc(y, m, 1).weekday % 7;
    final weeks = ((lead + daysInMonth) / 7).ceil();
    final count = [
      for (var d = 1; d <= daysInMonth; d++) ...?byDay[DateTime.utc(y, m, d)],
    ].length;

    return LayoutBuilder(
      builder: (context, constraints) {
        final cellW = constraints.maxWidth / 7;
        final withLabels = cellW >= metrics.labelCellMin;
        // Container 는 테두리 두께를 안쪽 여백으로 더한다. 오늘 칸의 윗변
        // 굵은 획(2)과 아랫변 계선(0.7)만큼 높이를 미리 더해 둬야 오늘
        // 칸만 1px 넘치는 일이 없다.
        const borders = AppRule.bold + AppRule.hair;
        final cellH =
            borders +
            (withLabels
                ? _cellPad * 2 +
                      metrics.dayLine +
                      2 * (metrics.labelLine + _labelGap)
                : _cellPad * 2 + metrics.dayLine + 4 + 6);

        return Semantics(
          container: true,
          label: '$y년 $m월 달력',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.baseline,
                textBaseline: TextBaseline.alphabetic,
                children: [
                  Text(
                    '$m월',
                    style: TextStyle(
                      fontFamily: 'Paperlogy',
                      fontSize: 18,
                      fontWeight: FontWeight.w800,
                      letterSpacing: -0.4,
                      color: AppColors.inkOn(dark),
                      fontFeatures: ledgerFigures,
                    ),
                  ),
                  const SizedBox(width: 6),
                  Text(
                    '$y',
                    style: text.labelSmall?.copyWith(
                      fontFeatures: ledgerFigures,
                    ),
                  ),
                  const Spacer(),
                  Text(
                    '일정 $count건',
                    style: text.labelSmall?.copyWith(
                      fontFeatures: ledgerFigures,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 6),
              // 머리 획 — 판면의 윗변. 높이만 정한 상자라 stretch 로 폭을 받는다.
              Container(height: AppRule.thin, color: AppColors.inkOn(dark)),
              Row(
                children: [
                  for (final w in _weekdayHead)
                    Expanded(
                      child: Padding(
                        padding: const EdgeInsets.symmetric(vertical: 4),
                        child: Text(
                          w,
                          textAlign: TextAlign.center,
                          maxLines: 1,
                          style: text.labelSmall?.copyWith(fontSize: 11),
                        ),
                      ),
                    ),
                ],
              ),
              Container(height: AppRule.hair, color: AppColors.ruleOn(dark)),
              for (var wk = 0; wk < weeks; wk++)
                Row(
                  children: [
                    for (var col = 0; col < 7; col++)
                      Expanded(
                        child: _cell(
                          context,
                          dark: dark,
                          day: wk * 7 + col - lead + 1,
                          daysInMonth: daysInMonth,
                          height: cellH,
                          withLabels: withLabels,
                          cellWidth: cellW,
                          lastCol: col == 6,
                        ),
                      ),
                  ],
                ),
            ],
          ),
        );
      },
    );
  }

  Widget _cell(
    BuildContext context, {
    required bool dark,
    required int day,
    required int daysInMonth,
    required double height,
    required bool withLabels,
    required double cellWidth,
    required bool lastCol,
  }) {
    final rule = BorderSide(
      color: AppColors.ruleSoftOn(dark),
      width: AppRule.hair,
    );
    final inMonth = day >= 1 && day <= daysInMonth;
    final date = inMonth ? DateTime.utc(month.year, month.month, day) : null;
    final isToday = date != null && date == today;
    final accent = AppColors.accentOn(dark);

    final box = BoxDecoration(
      color: isToday ? accent.withValues(alpha: dark ? 0.12 : 0.06) : null,
      border: Border(
        // 오늘은 윗변을 주묵 굵은 획으로 — 하단 바·헤더의 '지금 여기' 와 같은 말.
        top: isToday
            ? BorderSide(color: accent, width: AppRule.bold)
            : BorderSide.none,
        right: lastCol ? BorderSide.none : rule,
        bottom: rule,
      ),
    );
    if (date == null) {
      return Container(height: height, decoration: box);
    }

    final events = byDay[date] ?? const <CalendarEvent>[];
    final past = date.isBefore(today);
    // 네모(6 + 사이 2)는 칸에 들어가는 만큼만 — 최대 셋.
    final dotsFit = ((cellWidth - _cellPad * 2 + 2) / 8).floor().clamp(1, 3);
    final shown = withLabels ? 2 : dotsFit;
    final extra = events.length > shown ? events.length - shown : 0;
    final dayColor = isToday ? accent : AppColors.inkOn(dark);

    Widget content = Padding(
      padding: EdgeInsets.fromLTRB(
        _cellPad,
        isToday ? _cellPad - AppRule.bold : _cellPad,
        _cellPad,
        _cellPad,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              // 날짜가 남는 폭을 다 받고, '+N' 은 제 폭만. Flexible 과
              // Expanded 를 나란히 두면 반씩 나눠 날짜가 잘린다.
              Expanded(
                child: Text(
                  '$day',
                  maxLines: 1,
                  softWrap: false,
                  overflow: TextOverflow.clip,
                  style: MonthGridMetrics.dayStyle(dayColor, strong: isToday),
                ),
              ),
              if (extra > 0)
                Text(
                  '+$extra',
                  maxLines: 1,
                  softWrap: false,
                  style: MonthGridMetrics.labelStyle(
                    AppColors.mutedOn(dark),
                  ).copyWith(fontFeatures: ledgerFigures),
                ),
            ],
          ),
          if (withLabels)
            for (final e in events.take(shown))
              Padding(
                padding: const EdgeInsets.only(top: _labelGap),
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    border: Border(
                      left: BorderSide(
                        color: calendarKindColor(e.kind, dark),
                        width: _stripe,
                      ),
                    ),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.only(left: _stripeGap),
                    child: Text(
                      e.cellLabel,
                      maxLines: 1,
                      softWrap: false,
                      overflow: TextOverflow.ellipsis,
                      style: MonthGridMetrics.labelStyle(AppColors.inkOn(dark)),
                    ),
                  ),
                ),
              )
          else if (events.isNotEmpty) ...[
            const SizedBox(height: 4),
            // 칸이 좁아 글자가 안 들어갈 때는 종류 색 네모만. 수는 '+N' 이 말한다.
            Row(
              children: [
                for (final e in events.take(shown)) ...[
                  Container(
                    width: 6,
                    height: 6,
                    color: calendarKindColor(e.kind, dark),
                  ),
                  const SizedBox(width: 2),
                ],
              ],
            ),
          ],
        ],
      ),
    );

    if (past) content = Opacity(opacity: 0.38, child: content);

    final tappable = events.isNotEmpty && listedDays.contains(date);
    final semantic = [
      '${month.month}월 $day일',
      if (isToday) '오늘',
      if (events.isEmpty)
        '일정 없음'
      else
        '일정 ${events.length}건: ${events.map((e) => e.cellLabel).join(', ')}',
    ].join(', ');

    return Semantics(
      button: tappable,
      label: semantic,
      excludeSemantics: true,
      child: Container(
        height: height,
        decoration: box,
        child: tappable
            ? InkWell(onTap: () => onTapDay(date), child: content)
            : content,
      ),
    );
  }
}
