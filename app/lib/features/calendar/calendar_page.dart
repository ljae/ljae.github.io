import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme.dart';
import '../../data/academy_calendar.dart';
import '../../data/models.dart';
import '../../data/repository.dart';
import '../../widgets/annals.dart';
import '../../widgets/annals_controls.dart';
import '../../widgets/common.dart';
import '../../widgets/contact.dart';
import '../../widgets/content_loading.dart';

/// 대치 학원 일정 — 앞으로 한 달의 설명회·테스트·개강.
///
/// 읽기 전용이다. 달력 격자 대신 **날짜별 목록**으로 둔다 — 휴대폰에서
/// 칸 하나에 글 제목이 안 들어간다. 주묵은 '오늘' 하나에만 쓴다.
class CalendarPage extends ConsumerWidget {
  const CalendarPage({super.key});

  static const unverifiedNote =
      '여기 일정은 학원 측이 올린 안내 글(학원 홈페이지·뉴스·블로그)에서 제목에 적힌 '
      '날짜만 옮긴 것입니다. 저희가 확인한 일정이 아니며 점수·순위에 쓰지 않습니다. '
      '날짜·대상·신청 방법은 학원에 직접 확인해 주세요.';

  static const preschoolNote =
      '2026년 10월 1일부터 예비초(만 3세~취학 전) 대상 레벨테스트·면접은 '
      '학원법 시행령으로 금지되어, 그런 안내는 싣지 않습니다.';

  static const emptyText = '이 기간에 모은 일정이 없습니다';

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return ref
        .watch(academyCalendarProvider)
        .when(
          loading: () => const ContentLoading(),
          // 공급자가 실패를 null 로 바꾸므로 여기 올 일은 거의 없다.
          error: (_, _) => const _Body(calendar: null),
          data: (calendar) => _Body(calendar: calendar),
        );
  }
}

class _Body extends ConsumerWidget {
  final AcademyCalendar? calendar;
  const _Body({required this.calendar});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final today = ref.watch(calendarTodayProvider);
    final filter = ref.watch(calendarFilterProvider);
    final headerBand = ref.watch(selectionProvider.select((s) => s.gradeBand));
    final band = filter.allBands ? null : headerBand;
    final cal = calendar;
    final days = cal?.agenda(today: today, band: band, kind: filter.kind);
    final eventCount = days?.fold<int>(0, (n, d) => n + d.events.length) ?? 0;
    final collected = cal?.generatedDayKst;

    return ListView(
      padding: const EdgeInsets.symmetric(vertical: AppSpace.lg),
      children: [
        ContentWidth(
          child: IndexRail(
            rail: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                RailFact('수집일', collected == null ? '—' : _ymd(collected)),
                RailFact('일정', cal == null ? '—' : '$eventCount건'),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('설명회 · 테스트 · 개강', style: text.labelMedium),
                const SizedBox(height: 6),
                Text('${cal?.region ?? '대치'} 학원 일정', style: text.headlineLarge),
                const SizedBox(height: AppSpace.sm),
                Text(
                  '앞으로 ${cal?.windowDays ?? 31}일 안의 일정을 날짜별로 모았습니다. '
                  '누르면 원문이 새 창에서 열립니다.',
                  style: text.bodyMedium,
                ),
                const SizedBox(height: AppSpace.md),
                _Notice(dark: dark),
                const SizedBox(height: AppSpace.lg),
                _Filters(band: band, kind: filter.kind),
                const SizedBox(height: AppSpace.lg),
                if (cal == null)
                  _Empty(
                    message: '일정 자료를 불러오지 못했습니다',
                    detail:
                        '자료가 아직 만들어지지 않았거나 읽을 수 없는 상태입니다. '
                        '없는 일정을 채워 넣지 않습니다.',
                    action: TextButton(
                      onPressed: () => ref.invalidate(academyCalendarProvider),
                      child: const Text('다시 시도'),
                    ),
                  )
                else if (days!.isEmpty)
                  _Empty(
                    message: CalendarPage.emptyText,
                    detail: band == null && filter.kind == null
                        ? '검색으로 찾은 학원 안내 글 가운데 앞으로의 날짜가 적힌 것이 없습니다.'
                        : '고른 조건에 맞는 안내 글을 찾지 못했습니다. 일정이 없다는 뜻은 아닙니다.',
                    action: band != null
                        ? TextButton(
                            onPressed: () => ref
                                .read(calendarFilterProvider.notifier)
                                .showAllBands(),
                            child: const Text('전체 학년 보기'),
                          )
                        : null,
                  )
                else
                  for (final d in days)
                    _DaySection(day: d, isToday: d.day == today),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _Notice extends StatelessWidget {
  final bool dark;
  const _Notice({required this.dark});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpace.md),
      decoration: BoxDecoration(
        color: AppColors.canvasDeepOn(dark),
        border: Border.all(color: AppColors.ruleOn(dark), width: AppRule.hair),
        borderRadius: BorderRadius.circular(AppRadius.sm),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('학원 측 안내 · 확인되지 않음', style: text.titleSmall),
          const SizedBox(height: 6),
          Text(CalendarPage.unverifiedNote, style: text.bodySmall),
          const SizedBox(height: 6),
          Text(CalendarPage.preschoolNote, style: text.bodySmall),
        ],
      ),
    );
  }
}

class _Filters extends ConsumerWidget {
  final String? band;
  final String? kind;
  const _Filters({required this.band, required this.kind});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final notifier = ref.read(calendarFilterProvider.notifier);
    // 375px 에서 다섯 칸이 넘치면 잘리는 대신 줄어든다. 가로 스크롤은 안 만든다.
    Widget fit(Widget child) => FittedBox(
      fit: BoxFit.scaleDown,
      alignment: Alignment.centerLeft,
      child: child,
    );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const RailLabel('학년'),
        const SizedBox(height: 6),
        fit(
          RuledSegments<String>(
            options: [
              ('all', '전체'),
              for (final e in gradeBandNames.entries) (e.key, e.value),
            ],
            selected: band ?? 'all',
            onChanged: (v) =>
                v == 'all' ? notifier.showAllBands() : notifier.selectBand(v),
          ),
        ),
        const SizedBox(height: AppSpace.md),
        const RailLabel('종류'),
        const SizedBox(height: 6),
        fit(
          RuledSegments<String>(
            options: [
              ('all', '전체'),
              for (final e in calendarKindNames.entries) (e.key, e.value),
            ],
            selected: kind ?? 'all',
            onChanged: (v) => notifier.setKind(v == 'all' ? null : v),
          ),
        ),
      ],
    );
  }
}

class _Empty extends StatelessWidget {
  final String message;
  final String detail;
  final Widget? action;
  const _Empty({required this.message, required this.detail, this.action});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(message, style: text.titleMedium),
        const SizedBox(height: 6),
        Text(detail, style: text.bodySmall),
        ?action,
      ],
    );
  }
}

const _weekdays = ['월', '화', '수', '목', '금', '토', '일'];

String _ymd(DateTime d) =>
    '${d.year}.${d.month.toString().padLeft(2, '0')}.${d.day.toString().padLeft(2, '0')}';

class _DaySection extends StatelessWidget {
  final CalendarDay day;
  final bool isToday;
  const _DaySection({required this.day, required this.isToday});

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final d = day.day;
    final headColor = isToday
        ? AppColors.accentOn(dark)
        : AppColors.inkOn(dark);
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpace.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Text(
                '${d.month}월 ${d.day}일 (${_weekdays[d.weekday - 1]})',
                style: TextStyle(
                  fontFamily: 'Paperlogy',
                  fontSize: 16,
                  fontWeight: FontWeight.w800,
                  letterSpacing: -0.4,
                  color: headColor,
                  fontFeatures: ledgerFigures,
                ),
              ),
              if (isToday) ...[
                const SizedBox(width: AppSpace.sm),
                Text(
                  '오늘',
                  style: TextStyle(
                    fontFamily: 'Paperlogy',
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                    color: headColor,
                  ),
                ),
              ],
            ],
          ),
          const SizedBox(height: 6),
          Rule(
            thickness: isToday ? AppRule.bold : AppRule.thin,
            color: isToday ? headColor : AppColors.ruleOn(dark),
          ),
          for (var i = 0; i < day.events.length; i++) ...[
            if (i != 0) Rule(color: AppColors.ruleSoftOn(dark)),
            _EventRow(event: day.events[i]),
          ],
        ],
      ),
    );
  }
}

class _EventRow extends StatelessWidget {
  final CalendarEvent event;
  const _EventRow({required this.event});

  static Color kindColor(String kind, bool dark) => switch (kind) {
    'session' => AppColors.navyOn(dark),
    'test' => AppColors.estimatedOn(dark),
    _ => AppColors.mutedOn(dark),
  };

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final bands = event.isCommon
        ? '학년 공통'
        : event.bands.map((b) => gradeBandNames[b] ?? b).join('·');
    final meta = [
      calendarSourceNames[event.source] ?? '출처 미상',
      bands,
      if (parseCalendarDay(event.postedAt) case final p?) '${_ymd(p)} 게시',
    ].join(' · ');
    return Semantics(
      link: true,
      label: '${calendarKindNames[event.kind]} ${event.title}, 원문 새 창에서 열기',
      excludeSemantics: true,
      child: InkWell(
        onTap: () => openExternal(event.url),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 10),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SizedBox(
                width: 64,
                child: Align(
                  alignment: Alignment.topLeft,
                  child: TagMark(
                    calendarKindNames[event.kind] ?? event.kind,
                    color: kindColor(event.kind, dark),
                  ),
                ),
              ),
              const SizedBox(width: AppSpace.sm),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(event.title, style: text.bodyLarge),
                    const SizedBox(height: 3),
                    Text(meta, style: text.bodySmall),
                  ],
                ),
              ),
              const SizedBox(width: AppSpace.xs),
              Icon(Icons.open_in_new, size: 15, color: AppColors.mutedOn(dark)),
            ],
          ),
        ),
      ),
    );
  }
}
