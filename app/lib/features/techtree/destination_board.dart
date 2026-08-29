import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme.dart';
import '../../data/models.dart';
import '../../data/repository.dart';
import '../../widgets/annals.dart';
import 'techtree_page.dart' show showStageSheet;

/// 눌러 들어간 과목 — 해설판이 그 과목을 맨 앞에 세운다.
///
/// 표와 해설판이 세로로 떨어져 있어서, 어느 칸을 눌러 왔는지 판이
/// 기억하지 못하면 사용자가 같은 것을 두 번 찾는다.
class _FocusNotifier extends Notifier<String?> {
  @override
  String? build() => null;
  void set(String? s) => state = s;
}

final _focusProvider = NotifierProvider<_FocusNotifier, String?>(
  _FocusNotifier.new,
);

/// 목적성 판 — 행이 진로 목적지, 열이 과목.
///
/// 로드맵(과목 축)은 '우리 아이는 지금 초4 수학인데 이게 어디로
/// 이어지나'에 답한다. 그런데 학부모의 질문은 반대 방향으로도 온다:
/// **'의대를 보내려면 지금 무엇부터인가.'** 목적지를 로드맵의 조명으로만
/// 두면 이 방향에는 답하지 못한다 — 길을 고르기 전에는 어떤 길이
/// 있는지조차 한눈에 안 보이기 때문이다.
///
/// 그래서 같은 그래프를 축만 바꿔 한 번 더 그린다. 칸 하나가
/// (목적지 × 과목)이고, 그 칸이 곧 '의대의 수학'이다.
///
/// **판이 말하는 것은 셋이다.**
/// - 이 길이 어느 과목을 지나는가 (지나지 않는 과목은 빈칸)
/// - 언제 갈리는가 (가장 이른 관문)
/// - 그 대목이 얼마나 찼는가 (학원 수 · 비었으면 '비었음')
///
/// 경로는 사람이 적고 **얼마나 찼는지는 데이터가 말한다.** 빈 대목을
/// 숨기지 않는 이유가 그것이다 — 숨기면 큐레이션한 길이 전부 채워진
/// 것처럼 읽힌다.
class DestinationBoard extends ConsumerWidget {
  final EduTreeData data;
  final String regionId;

  /// '과목 축에서 보기' — 고른 길을 로드맵으로 넘긴다.
  /// 두 축을 잇는 고리다. 없으면 이 판이 막다른 골목이 된다.
  final VoidCallback? onShowRoadmap;

  const DestinationBoard({
    super.key,
    required this.data,
    required this.regionId,
    this.onShowRoadmap,
  });

  /// 이 아래로는 표 대신 목적지별 카드로 편다.
  /// 라벨 190 + 갈림 52 + (과목 칸 58 × 6) = 590 이 최소인데, 그 폭에서는
  /// 칸이 숫자 하나 폭이라 표가 표 구실을 못 한다. 여유를 둔 값이다.
  static const tableMinWidth = 660.0;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final selected = data.destinationById(ref.watch(destinationProvider));
    // 판의 열은 목적지들이 실제로 지나는 과목만 세운다. 아무 길도 지나지
    // 않는 과목의 열을 두면 빈 칸만 늘어난다.
    final subjects = orderedSubjects({
      for (final d in data.destinations) ...d.subjects,
    });

    return LayoutBuilder(
      builder: (context, c) => SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: AppSpace.sm),
            _legend(context),
            const SizedBox(height: AppSpace.sm),
            if (c.maxWidth >= tableMinWidth)
              _table(context, ref, subjects, c.maxWidth)
            else
              _cards(context, ref),
            if (selected != null) ...[
              const SizedBox(height: AppSpace.lg),
              _DestinationBrief(
                dest: selected,
                data: data,
                regionId: regionId,
                onShowRoadmap: onShowRoadmap,
              ),
            ],
            const SizedBox(height: AppSpace.xl),
          ],
        ),
      ),
    );
  }

  Widget _legend(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Text(
      '칸의 숫자는 그 길의 그 과목을 담당한다고 볼 근거가 있는 학원 수입니다'
      ' · 지나지 않는 과목은 빈칸입니다',
      style: text.bodySmall?.copyWith(
        fontSize: 11,
        color: AppColors.mutedOn(dark),
      ),
    );
  }

  void _pick(WidgetRef ref, String destId, String? subject) {
    ref.read(destinationProvider.notifier).select(destId);
    ref.read(_focusProvider.notifier).set(subject);
  }

  // ── 넓은 화면: 표 ──────────────────────────────────────────────────

  Widget _table(
    BuildContext context,
    WidgetRef ref,
    List<String> subjects,
    double maxWidth,
  ) {
    const labelW = 190.0;
    const gateW = 52.0;
    final colW = ((maxWidth - labelW - gateW) / subjects.length).clamp(
      58.0,
      120.0,
    );

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _head(context, subjects, labelW, gateW, colW),
        for (final axis in data.destinationAxes) ...[
          _axisHead(context, axis),
          for (final d in data.destinations.where((x) => x.axis == axis))
            _row(context, ref, d, subjects, labelW, gateW, colW),
        ],
      ],
    );
  }

  Widget _head(
    BuildContext context,
    List<String> subjects,
    double labelW,
    double gateW,
    double colW,
  ) {
    final text = Theme.of(context).textTheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          SizedBox(
            width: labelW,
            child: Text('진로 목적지', style: text.labelMedium),
          ),
          SizedBox(
            width: gateW,
            child: Text(
              '갈림',
              textAlign: TextAlign.center,
              style: text.labelMedium,
            ),
          ),
          for (final s in subjects)
            SizedBox(
              width: colW,
              child: Column(
                children: [
                  // 과목 색은 꼬리표·로드맵·트리가 이미 쓰는 코드다. 여기서도
                  // 같은 코드를 쓴다 — 색이 화면마다 다른 뜻을 가지면
                  // 그건 코드가 아니다.
                  Container(
                    width: 7,
                    height: 7,
                    color: AppColors.subjectOn(s, dark),
                  ),
                  const SizedBox(height: 3),
                  Text(subjectNames[s] ?? s, style: text.labelMedium),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _axisHead(BuildContext context, String axis) {
    final text = Theme.of(context).textTheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Padding(
      padding: const EdgeInsets.only(top: AppSpace.md, bottom: 3),
      child: Row(
        children: [
          Text(
            axis,
            style: text.labelMedium?.copyWith(
              color: AppColors.mutedOn(dark),
              letterSpacing: 1.2,
            ),
          ),
          const SizedBox(width: AppSpace.sm),
          const Expanded(child: Rule()),
        ],
      ),
    );
  }

  Widget _row(
    BuildContext context,
    WidgetRef ref,
    Destination d,
    List<String> subjects,
    double labelW,
    double gateW,
    double colW,
  ) {
    final text = Theme.of(context).textTheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final on = ref.watch(destinationProvider) == d.id;
    final accent = AppColors.accentOn(dark);

    return DecoratedBox(
      decoration: BoxDecoration(
        border: Border(
          // 고른 줄은 주묵 한 획으로 표시한다. 줄 전체를 칠하면 판면이
          // 색종이가 되고 하나뿐인 강조색이 뜻을 잃는다.
          left: BorderSide(
            color: on ? accent : Colors.transparent,
            width: AppRule.bold,
          ),
          bottom: BorderSide(
            color: AppColors.ruleSoftOn(dark),
            width: AppRule.hair,
          ),
        ),
      ),
      // 칸의 높이를 서로 맞춘다. `stretch` 만 주면 Row 의 세로가 열려
      // 있어(스크롤 안의 Column) '무한 높이' 로 눕는다 — 한 축만 정한
      // 상자를 Row·Column·Wrap 에 넣을 때마다 나오는 그 함정이다.
      // 누가 나머지 축을 정하는지 여기서 못 박는다.
      child: IntrinsicHeight(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            SizedBox(
              width: labelW,
              child: InkWell(
                onTap: () {
                  ref.read(destinationProvider.notifier).toggle(d.id);
                  ref.read(_focusProvider.notifier).set(null);
                },
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(7, 8, 6, 8),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        d.label,
                        style: text.bodyMedium?.copyWith(
                          fontWeight: on ? FontWeight.w700 : FontWeight.w500,
                        ),
                      ),
                      Text(
                        d.linkable
                            ? '학원 ${data.destinationAcademyCount(d, regionId: regionId)}곳'
                            : '학원을 잇지 않음',
                        style: text.bodySmall?.copyWith(
                          fontSize: 10,
                          fontFeatures: ledgerFigures,
                          color: d.linkable
                              ? AppColors.mutedOn(dark)
                              : AppColors.mist,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            SizedBox(
              width: gateW,
              child: Center(child: _gateMark(context, d)),
            ),
            // 지나는 교과 단계가 하나도 없는 길(예체능 입시)은 칸을 점으로
            // 채우지 않는다. 점 여섯 개는 '데이터가 빠졌다' 로 읽히는데
            // 사실은 **축이 다르다는 진술**이다. 빈 상태가 정상일 때는
            // 비워 두지 말고 그렇게 적는다.
            if (d.subjects.isEmpty)
              Expanded(child: _offAxisNote(context, d))
            else
              for (final s in subjects)
                SizedBox(
                  width: colW,
                  child: _Cell(
                    leg: data.legFor(d, s, regionId: regionId),
                    onTap: () => _pick(ref, d.id, s),
                  ),
                ),
          ],
        ),
      ),
    );
  }

  /// 교과 단계를 하나도 지나지 않는 길에 붙이는 말.
  ///
  /// 왜 비었는지는 그 길의 요약이 이미 말한다(예체능: '실기 중심이라
  /// 교과 테크트리와 축이 다르다'). 그것을 여기로 끌어와 적는다 —
  /// 이유 없는 빈칸은 다음 사람이 버그로 읽는다.
  Widget _offAxisNote(BuildContext context, Destination d) {
    final text = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 8),
      child: Text(
        d.summary ?? '교과 단계를 잇지 않는 길입니다',
        maxLines: 2,
        overflow: TextOverflow.ellipsis,
        style: text.bodySmall?.copyWith(fontSize: 11, color: AppColors.mist),
      ),
    );
  }

  /// 가장 이른 관문의 학년. **'언제 갈리는가'가 학부모의 실제 질문이다** —
  /// 되돌리기 어려운 지점이 초4 인 길과 고1 인 길은 준비가 통째로 다르다.
  Widget _gateMark(BuildContext context, Destination d) {
    final text = Theme.of(context).textTheme;
    final g = d.firstGateGrade;
    if (g == null) {
      return Text('·', style: text.bodySmall?.copyWith(color: AppColors.mist));
    }
    return Text(
      Stage.gradeName(g),
      style: text.bodySmall?.copyWith(
        fontSize: 11,
        fontWeight: FontWeight.w700,
        color: AppColors.estimated,
        fontFeatures: ledgerFigures,
      ),
    );
  }

  // ── 좁은 화면: 목적지별 카드 ────────────────────────────────────────

  Widget _cards(BuildContext context, WidgetRef ref) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final axis in data.destinationAxes) ...[
          _axisHead(context, axis),
          for (final d in data.destinations.where((x) => x.axis == axis))
            _card(context, ref, d),
        ],
      ],
    );
  }

  Widget _card(BuildContext context, WidgetRef ref, Destination d) {
    final text = Theme.of(context).textTheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final on = ref.watch(destinationProvider) == d.id;
    final accent = AppColors.accentOn(dark);
    final hair = BorderSide(
      color: AppColors.ruleSoftOn(dark),
      width: AppRule.hair,
    );

    return InkWell(
      onTap: () {
        ref.read(destinationProvider.notifier).toggle(d.id);
        ref.read(_focusProvider.notifier).set(null);
      },
      child: Container(
        margin: const EdgeInsets.only(bottom: 6),
        padding: const EdgeInsets.fromLTRB(9, 8, 9, 9),
        decoration: BoxDecoration(
          border: Border(
            left: BorderSide(
              color: on ? accent : AppColors.ruleOn(dark),
              width: on ? AppRule.bold : AppRule.hair,
            ),
            top: hair,
            right: hair,
            bottom: hair,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    d.label,
                    style: text.bodyLarge?.copyWith(
                      fontWeight: on ? FontWeight.w700 : FontWeight.w600,
                    ),
                  ),
                ),
                if (d.firstGateGrade != null)
                  Text(
                    '갈림 ${Stage.gradeName(d.firstGateGrade!)}',
                    style: text.bodySmall?.copyWith(
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                      color: AppColors.estimated,
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 5),
            if (d.subjects.isEmpty)
              _offAxisNote(context, d)
            else
              Wrap(
                spacing: 5,
                runSpacing: 5,
                children: [
                  for (final leg in data.legsFor(d, regionId: regionId))
                    SizedBox(
                      width: 92,
                      child: _Cell(
                        leg: leg,
                        dense: true,
                        onTap: () => _pick(ref, d.id, leg.subject),
                      ),
                    ),
                ],
              ),
          ],
        ),
      ),
    );
  }
}

/// 판의 칸 하나 — (목적지 × 과목).
///
/// **세 상태를 다른 얼굴로 적는다.** 섞으면 판이 아무 말도 안 하게 된다.
///
///     지나지 않음   빈칸(·)     이 길은 이 과목을 요구하지 않는다
///     잇지 않음     —           근거가 얇아 학원을 안 잇기로 한 길
///     비었음        '비었음'     요구하는데 근거 있는 학원이 0곳
class _Cell extends StatelessWidget {
  final DestinationLeg leg;
  final VoidCallback? onTap;
  final bool dense;

  const _Cell({required this.leg, this.onTap, this.dense = false});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final color = AppColors.subjectOn(leg.subject, dark);

    if (leg.isOffPath) {
      // 이 길이 지나지 않는 과목. **비어 있는 것과 다르다** — 여기에
      // 0 을 적으면 '학원이 없는 대목'으로 읽힌다.
      return Center(
        child: Text(
          '·',
          style: text.bodySmall?.copyWith(color: AppColors.mist),
        ),
      );
    }

    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: EdgeInsets.symmetric(vertical: dense ? 5 : 7, horizontal: 5),
        child: Column(
          crossAxisAlignment: dense
              ? CrossAxisAlignment.start
              : CrossAxisAlignment.center,
          mainAxisSize: MainAxisSize.min,
          children: [
            if (dense)
              Text(
                subjectNames[leg.subject] ?? leg.subject,
                style: text.bodySmall?.copyWith(
                  fontSize: 10.5,
                  fontWeight: FontWeight.w600,
                  color: color,
                ),
              ),
            if (!leg.linkable)
              Text('—', style: text.bodySmall?.copyWith(color: AppColors.mist))
            else if (leg.academyCount == 0)
              Text(
                '비었음',
                style: text.bodySmall?.copyWith(
                  fontSize: 10.5,
                  fontWeight: FontWeight.w600,
                  color: AppColors.estimated,
                ),
              )
            else
              Text(
                '${leg.academyCount}곳',
                style: text.bodyMedium?.copyWith(
                  fontWeight: FontWeight.w700,
                  fontFeatures: ledgerFigures,
                  color: color,
                ),
              ),
            Text(
              '단계 ${leg.stages.length}',
              style: text.bodySmall?.copyWith(
                fontSize: 9.5,
                color: AppColors.mist,
                fontFeatures: ledgerFigures,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 고른 길의 해설 — 관문과 과목별 단계.
///
/// 표는 '어느 대목이 얼마나 찼나'까지만 말한다. 그 아래에서 길을 시간
/// 순으로 편다. 단계를 누르면 **기존 단계 시트**로 간다 — 같은 단계가
/// 화면마다 다른 얼굴을 하면 사용자가 길을 잃는다.
class _DestinationBrief extends ConsumerWidget {
  final Destination dest;
  final EduTreeData data;
  final String regionId;
  final VoidCallback? onShowRoadmap;

  const _DestinationBrief({
    required this.dest,
    required this.data,
    required this.regionId,
    this.onShowRoadmap,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final accent = AppColors.accentOn(dark);
    final region = data.regionById[regionId]?.nameKo;
    final focus = ref.watch(_focusProvider);
    final hair = BorderSide(color: AppColors.ruleOn(dark), width: AppRule.hair);

    // 눌러 들어온 과목을 맨 앞에. 나머지는 표준 순서를 지킨다.
    final legs = data.legsFor(dest, regionId: regionId)
      ..sort(
        (a, b) => (a.subject == focus ? 0 : 1) - (b.subject == focus ? 0 : 1),
      );
    final gates = dest.gates.toList()..sort((a, b) => a.grade - b.grade);

    return Container(
      decoration: BoxDecoration(
        color: AppColors.surfaceOn(dark),
        border: Border(
          left: BorderSide(color: accent, width: AppRule.bold),
          top: hair,
          right: hair,
          bottom: hair,
        ),
      ),
      padding: const EdgeInsets.fromLTRB(
        AppSpace.md,
        AppSpace.md,
        AppSpace.md,
        AppSpace.lg,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(child: Text(dest.label, style: text.titleLarge)),
              if (onShowRoadmap != null)
                TextButton(
                  onPressed: onShowRoadmap,
                  child: const Text('과목 축에서 보기'),
                ),
            ],
          ),
          if (dest.summary != null) Text(dest.summary!, style: text.bodyMedium),
          const SizedBox(height: AppSpace.sm),
          if (dest.linkable)
            TagMark(
              '이 길의 학원 '
              '${data.destinationAcademyCount(dest, regionId: regionId)}곳'
              '${region == null ? "" : " · $region"}',
              color: accent,
            )
          else
            const TagMark('근거가 얇아 학원을 잇지 않습니다', color: AppColors.mist),
          if (gates.isNotEmpty) ...[
            const SizedBox(height: AppSpace.md),
            Text('관문', style: text.labelMedium),
            const SizedBox(height: 3),
            for (final g in gates)
              Padding(
                padding: const EdgeInsets.only(bottom: 3),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    SizedBox(
                      width: 44,
                      child: Text(
                        Stage.gradeName(g.grade),
                        style: text.bodySmall?.copyWith(
                          fontWeight: FontWeight.w700,
                          color: AppColors.estimated,
                          fontFeatures: ledgerFigures,
                        ),
                      ),
                    ),
                    Expanded(child: Text(g.note, style: text.bodySmall)),
                  ],
                ),
              ),
          ],
          const SizedBox(height: AppSpace.md),
          Text('지나는 단계', style: text.labelMedium),
          for (final leg in legs)
            _LegBlock(leg: leg, data: data, regionId: regionId),
        ],
      ),
    );
  }
}

/// 한 과목의 길 — 나이 순 단계 줄.
class _LegBlock extends StatelessWidget {
  final DestinationLeg leg;
  final EduTreeData data;
  final String regionId;

  const _LegBlock({
    required this.leg,
    required this.data,
    required this.regionId,
  });

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final color = AppColors.subjectOn(leg.subject, dark);

    return Padding(
      padding: const EdgeInsets.only(top: 7),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(width: 3, height: 12, color: color),
              const SizedBox(width: 5),
              Text(
                subjectNames[leg.subject] ?? leg.subject,
                style: text.labelLarge?.copyWith(color: color),
              ),
              const SizedBox(width: 6),
              if (leg.linkable)
                Text(
                  '학원 ${leg.academyCount}곳',
                  style: text.bodySmall?.copyWith(
                    fontSize: 10.5,
                    color: AppColors.mutedOn(dark),
                    fontFeatures: ledgerFigures,
                  ),
                ),
            ],
          ),
          for (final s in leg.stages)
            _StageLine(
              stage: s,
              count: leg.countOf(s.id),
              linkable: leg.linkable,
              onTap: () => showStageSheet(context, s, data, regionId),
            ),
        ],
      ),
    );
  }
}

class _StageLine extends StatelessWidget {
  final Stage stage;
  final int count;
  final bool linkable;
  final VoidCallback onTap;

  const _StageLine({
    required this.stage,
    required this.count,
    required this.linkable,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final dark = Theme.of(context).brightness == Brightness.dark;

    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(8, 4, 0, 4),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(
              width: 64,
              child: Text(
                stage.gradeLabel,
                style: text.bodySmall?.copyWith(
                  fontSize: 10.5,
                  color: AppColors.mutedOn(dark),
                  fontFeatures: ledgerFigures,
                ),
              ),
            ),
            Expanded(child: Text(stage.title, style: text.bodyMedium)),
            const SizedBox(width: 6),
            if (!linkable)
              const SizedBox.shrink()
            else if (count == 0)
              // 큐레이션한 길의 빈 대목. **'길이 없다'가 아니라 '아직
              // 아무것도 모른다'다** — 감추면 다음 사람이 채워진 줄 안다.
              Text(
                '비었음',
                style: text.bodySmall?.copyWith(
                  fontSize: 10.5,
                  fontWeight: FontWeight.w600,
                  color: AppColors.estimated,
                ),
              )
            else
              Text(
                '$count곳',
                style: text.bodySmall?.copyWith(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  fontFeatures: ledgerFigures,
                ),
              ),
          ],
        ),
      ),
    );
  }
}
