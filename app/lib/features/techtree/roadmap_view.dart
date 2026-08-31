import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme.dart';
import '../../widgets/annals.dart';
import '../../widgets/subject_bar.dart';
import '../../data/models.dart';
import '../../data/repository.dart';
import 'techtree_page.dart' show showStageSheet;

/// 과목마다 겹치는 단계가 **서로 다른 칸에 서도록** 자리를 계산한다.
///
/// 예전에는 yaml 의 `lane`(사람이 손으로 적은 0/1)을 그대로 믿고
/// '겹치는 단계가 있으면 폭을 반으로 나눠 왼쪽·오른쪽에 세운다' 였다.
/// 두 가지가 깨진다.
///
///  1. **셋 이상이 한 학년에 겹치면 자리가 모자란다.** 고3 수학은
///     내신·수능·최상위·N수 넷이 동시에 열려 있다.
///  2. **같은 lane 끼리 겹치면 정확히 포개진다.** 위 카드가 아래 카드를
///     통째로 덮어, 그 안의 학원 이름이 화면에서 사라진다.
///
/// 실측(41단계)에서 2번이 **16쌍**이었다. `math_hi_naesin` 과
/// `math_hi_suneung` 은 학년 범위도 lane 도 같아 한쪽이 아예 안 보였다.
///
/// → 자리를 **겹침에서 계산한다.** 시작 학년 순으로 훑으며 비어 있는 첫
/// 칸에 넣는 구간 그래프 색칠이라, 필요한 칸 수가 최소가 된다. yaml 의
/// `lane` 은 버리지 않고 **같은 학년에서 시작한 것들의 좌우 차례**로만
/// 쓴다 — '주(主)가 왼쪽' 같은 사람의 뜻이 그만큼 남는다.
class RoadmapLanes {
  final Map<String, int> _laneOf;
  final Map<String, int> _countOf;

  const RoadmapLanes._(this._laneOf, this._countOf);

  factory RoadmapLanes.of(Roadmap roadmap) {
    final laneOf = <String, int>{};
    final countOf = <String, int>{};
    final bySubject = <String, List<RoadmapStage>>{};
    for (final s in roadmap.stages) {
      (bySubject[s.subject] ??= <RoadmapStage>[]).add(s);
    }
    for (final entry in bySubject.entries) {
      final rows = [...entry.value]..sort((a, b) {
        final g = a.gradeMin.compareTo(b.gradeMin);
        if (g != 0) return g;
        final l = a.lane.compareTo(b.lane);
        if (l != 0) return l;
        return a.id.compareTo(b.id); // 같은 값이면 순서를 못 박는다
      });
      // 칸마다 '지금까지 그 칸을 쓴 마지막 단계의 끝 학년'을 들고 간다.
      final ends = <int>[];
      for (final s in rows) {
        var col = ends.indexWhere((end) => end < s.gradeMin);
        if (col < 0) {
          ends.add(s.gradeMax);
          col = ends.length - 1;
        } else {
          ends[col] = s.gradeMax;
        }
        laneOf[s.id] = col;
      }
      countOf[entry.key] = ends.length;
    }
    return RoadmapLanes._(laneOf, countOf);
  }

  int laneOfStage(String stageId) => _laneOf[stageId] ?? 0;

  /// 그 과목이 쓰는 칸 수. 최소 1 — 0 으로 나누지 않는다.
  int countFor(String subject) => _countOf[subject] ?? 1;
}

/// 통합 로드맵 — 연령 축 하나 위에 네 과목을 나란히 놓는다.
///
/// 과목·구간별 트리는 '지금 내 아이 구간'을 보는 데 좋지만, 5세 영어 →
/// 6세 수학 → 7세 국어 → 초4 재편이라는 전체 흐름은 과목을 나란히
/// 놓아야 보인다. 세로가 나이, 가로가 과목이다. 카드의 세로 위치와
/// 길이가 곧 시작 나이와 지속 기간이다 — 표를 읽는 게 아니라 지도를
/// 보게 하는 것이 목적이다.
///
/// 유아 단계(영유)는 방향 안내일 뿐이라 점선 테두리로 구분하고,
/// 눌러도 랭킹으로 이어지지 않는다.
class RoadmapView extends ConsumerStatefulWidget {
  final EduTreeData data;
  final String regionId;
  const RoadmapView({super.key, required this.data, required this.regionId});

  static const _minGrade = -2; // 5세
  static const _maxGrade = 12; // 고3
  static const _unitH = 72.0; // 학년 1칸 높이 (학원 3줄이 들어가야 한다)
  static const _axisW = 52.0;
  static const _gap = 10.0;

  /// 이 아래로는 과목을 한 번에 하나만 보여준다.
  ///
  /// 네 과목이 다 들어가려면 축 52 + (최소 카드폭 150 + 사이 10) × 4 =
  /// 692 가 필요하다. 그보다 좁으면 가로 스크롤로 도망가는데, 세로로도
  /// 긴 화면을 가로로도 밀어야 해서 손이 두 방향을 오간다. 휴대폰에서는
  /// 한 과목을 온전히 보여주고 옆으로 넘기는 편이 낫다.
  static const mobileMaxWidth = 700.0;

  static double _y(num grade) => (grade - _minGrade) * _unitH;

  @override
  ConsumerState<RoadmapView> createState() => _RoadmapViewState();
}

class _RoadmapViewState extends ConsumerState<RoadmapView> {
  PageController? _pages;
  int _page = 0;

  /// 고른 진로 목적지. null 이면 전체를 같은 밝기로 본다.
  ///
  /// 판이 모든 길을 같은 밝기로 그리면 '우리 아이 길은 어디냐' 에 답하지
  /// 못한다. 목적지를 고르면 그 길만 살아나고 관문이 나이 축에 뜬다.
  ///
  /// **선택은 이 화면이 갖지 않는다.** 목적성 판(DestinationBoard)과 같은
  /// 것을 보고 있어야 축을 바꿔도 고른 길이 유지된다 — 화면마다 따로 들면
  /// 두 판이 같은 그래프의 두 얼굴이라는 사실이 드러나지 않는다.
  String? get _destId => ref.watch(destinationProvider);

  Destination? get _dest => data.destinationById(_destId);

  /// 칸 사이. 카드 테두리가 맞닿아 한 덩어리로 보이지 않을 만큼만.
  static const _laneGap = 4.0;

  /// 겹침에서 계산한 자리. 데이터가 바뀔 때만 다시 잡는다 —
  /// 매 프레임 41단계를 훑을 이유가 없다.
  late RoadmapLanes _lanes = RoadmapLanes.of(widget.data.roadmap);

  @override
  void didUpdateWidget(covariant RoadmapView old) {
    super.didUpdateWidget(old);
    if (!identical(old.data.roadmap, widget.data.roadmap)) {
      _lanes = RoadmapLanes.of(widget.data.roadmap);
    }
  }

  // 위젯 쪽 상수를 그대로 쓴다. 두 벌로 두면 한쪽만 고쳐진다.
  static const _minGrade = RoadmapView._minGrade;
  static const _maxGrade = RoadmapView._maxGrade;
  static const _unitH = RoadmapView._unitH;
  static const _axisW = RoadmapView._axisW;
  static const _gap = RoadmapView._gap;

  EduTreeData get data => widget.data;
  String get regionId => widget.regionId;

  double _y(num grade) => RoadmapView._y(grade);

  @override
  void dispose() {
    _pages?.dispose();
    super.dispose();
  }

  void _goTo(int i) {
    setState(() => _page = i);
    _pages?.animateToPage(
      i,
      duration: const Duration(milliseconds: 260),
      curve: Curves.easeOutCubic,
    );
  }

  @override
  Widget build(BuildContext context) {
    final roadmap = data.roadmap;
    if (roadmap.isEmpty) {
      return const Center(child: Text('로드맵 데이터가 없습니다'));
    }
    // 순서는 표준 하나뿐이다. 예전에는 여기 `['english', 'math', …]` 가
    // 박혀 있어 로드맵만 영어부터였다 — 시작 나이 순이라는 나름의 뜻이
    // 있었지만, 이 판은 **세로축이 이미 나이**다. 가로까지 나이를 말하면
    // 같은 것을 두 번 말하면서 다른 화면과 어긋난다.
    final subjects = orderedSubjects(
      subjectOrder,
    ).where((s) => roadmap.stages.any((st) => st.subject == s)).toList();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (data.destinations.isNotEmpty) _destinationBar(context),
        Expanded(child: _canvas(context, roadmap, subjects)),
      ],
    );
  }

  Widget _canvas(
    BuildContext context,
    Roadmap roadmap,
    List<String> subjects,
  ) {
    return LayoutBuilder(
      builder: (context, c) {
        if (c.maxWidth < RoadmapView.mobileMaxWidth && subjects.length > 1) {
          return _mobile(context, roadmap, subjects, c.maxWidth);
        }
        // 좁은 화면에서는 가로 스크롤로 도망가게 한다. 네 과목을 억지로
        // 구겨 넣으면 카드가 글자 하나 폭이 된다.
        final colW =
            ((c.maxWidth - _axisW - _gap * subjects.length) / subjects.length)
                .clamp(150.0, 340.0);
        final contentW = _axisW + (colW + _gap) * subjects.length;
        final totalH = _y(_maxGrade + 1) + 20;

        return SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: SizedBox(
            width: contentW,
            child: _board(
              context,
              roadmap,
              subjects,
              colW: colW,
              totalH: totalH,
            ),
          ),
        );
      },
    );
  }

  /// 진로 목적지 선택 — 「實錄」의 목차에 해당한다.
  ///
  /// 고르면 그 길의 단계만 밝아지고, 되돌리기 어려운 지점이 나이 축에 뜬다.
  Widget _destinationBar(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final d = _dest;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SizedBox(height: AppSpace.sm),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: [
              _destChip(context, null, '전체'),
              for (final x in data.destinations)
                _destChip(context, x.id, x.label),
            ],
          ),
        ),
        if (d != null) ...[
          const SizedBox(height: 7),
          Wrap(
            spacing: AppSpace.sm,
            runSpacing: 4,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              if (d.summary != null)
                Text(d.summary!, style: text.bodySmall),
              // 큐레이션한 길에 데이터가 얼마나 찼는지를 숨기지 않는다.
              // 학군 기준으로 다시 센다. 파이프라인의 academyCount 는
              // 전국 합계라, 학군을 바꿔도 숫자가 안 움직여서 그 숫자가
              // 무엇을 세었는지 알 수 없었다. 판은 학군 하나를 본다.
              if (d.linkable)
                TagMark(
                  '이 길의 학원 '
                  '${data.destinationAcademyCount(d, regionId: regionId)}곳',
                  color: AppColors.accentOn(dark),
                )
              else
                const TagMark(
                  '근거가 얇아 학원을 잇지 않습니다',
                  color: AppColors.mist,
                ),
            ],
          ),
        ],
        const SizedBox(height: 7),
      ],
    );
  }

  Widget _destChip(BuildContext context, String? id, String label) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final on = _destId == id;
    final accent = AppColors.accentOn(dark);
    return Padding(
      padding: const EdgeInsets.only(right: 6),
      child: InkWell(
        onTap: () => ref.read(destinationProvider.notifier).select(id),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
          decoration: BoxDecoration(
            color: on ? accent : Colors.transparent,
            // 계선(界線)을 따른다 — 이 판에서 둥근 알약은 다른 말투다.
            border: Border.all(
              color: on ? accent : AppColors.ruleOn(dark),
              width: AppRule.hair,
            ),
          ),
          child: Text(
            label,
            style: _chipStyle(on, dark),
          ),
        ),
      ),
    );
  }

  TextStyle _chipStyle(bool on, bool dark) => TextStyle(
        fontFamily: 'Paperlogy',
        fontSize: 12.5,
        fontWeight: on ? FontWeight.w600 : FontWeight.w400,
        color: on ? Colors.white : AppColors.inkOn(dark),
      );

  /// 휴대폰용 — 한 과목씩, 옆으로 넘겨서 본다.
  ///
  /// 예전에는 좁은 화면에서도 네 과목을 가로 스크롤로 밀게 했다. 로드맵은
  /// 세로로 긴 그림이라 세로로 훑다가 과목을 바꾸려면 가로로도 밀어야 했고,
  /// 두 방향이 섞이면 한 손으로 못 쓴다. 한 과목을 화면 폭 전부에 펴고
  /// 과목 전환을 스와이프에 맡기면 방향이 하나로 정리된다.
  ///
  /// 세로 스크롤은 페이지마다 따로 둔다 — 국어를 보다 영어로 넘겼을 때
  /// 영어가 중간부터 시작하면 어디를 보고 있는지 알 수 없다.
  Widget _mobile(
    BuildContext context,
    Roadmap roadmap,
    List<String> subjects,
    double width,
  ) {
    _pages ??= PageController(initialPage: _page);
    final text = Theme.of(context).textTheme;
    final colW = (width - _axisW - _gap).clamp(150.0, 420.0);
    final totalH = _y(_maxGrade + 1) + 20;

    return Column(
      children: [
        const SizedBox(height: AppSpace.sm),
        // 과목 칩이 곧 현재 위치 표시다. 점(dot) 표시를 따로 두면 같은 것을
        // 두 번 말하게 된다.
        //
        // 여기만 꽉 채운 알약(999px)이었다 — 각진 판면에서 그것만 둥글어
        // 혼자 튀었고, 같은 조작인 랭킹의 과목 줄과도 모양이 달랐다.
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: AppSpace.sm),
          child: SubjectBar(
            selected: _page < subjects.length ? subjects[_page] : null,
            only: subjects.toSet(),
            onChanged: (v) {
              final i = v == null ? -1 : subjects.indexOf(v);
              if (i >= 0) _goTo(i);
            },
          ),
        ),
        const SizedBox(height: 4),
        Text(
          '옆으로 넘겨 과목을 바꿉니다',
          style: text.bodySmall?.copyWith(fontSize: 10.5),
        ),
        const SizedBox(height: 4),
        Expanded(
          child: PageView.builder(
            controller: _pages,
            itemCount: subjects.length,
            onPageChanged: (i) => setState(() => _page = i),
            itemBuilder: (context, i) => _board(
              context,
              roadmap,
              [subjects[i]], // 한 과목만 그린다
              colW: colW,
              totalH: totalH,
              showHeader: false, // 과목 이름은 위 칩이 이미 말한다
            ),
          ),
        ),
      ],
    );
  }

  /// 로드맵 판 하나. 과목 목록을 그대로 받으므로 전체(네 과목)와
  /// 한 과목짜리가 같은 코드를 쓴다 — 경로선 좌표도 이 목록으로 계산된다.
  Widget _board(
    BuildContext context,
    Roadmap roadmap,
    List<String> subjects, {
    required double colW,
    required double totalH,
    bool showHeader = true,
  }) {
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (showHeader) ...[
            const SizedBox(height: AppSpace.md),
            _subjectHeader(context, subjects, colW),
            const SizedBox(height: 6),
          ],
          SizedBox(
            height: totalH,
            child: Stack(
              children: [
                for (var g = _minGrade; g <= _maxGrade; g++)
                  Positioned(
                    top: _y(g),
                    left: 0,
                    right: 0,
                    child: _GradeRow(
                      grade: g,
                      milestone: roadmap.milestones
                          .where((m) => m.grade == g)
                          .firstOrNull,
                      // 되돌리기 어려운 분기점. 목적지를 골랐을 때만 뜬다 —
                      // 늘 띄우면 어느 길의 관문인지 알 수 없다.
                      gate: _dest?.gates
                          .where((x) => x.grade == g)
                          .firstOrNull,
                    ),
                  ),
                Positioned.fill(
                  child: CustomPaint(
                    painter: _EdgePainter(
                      roadmap: roadmap,
                      subjects: subjects,
                      colW: colW,
                      gap: _gap,
                      axisW: _axisW,
                      yOf: _y,
                      lineColor: Theme.of(context).dividerColor,
                      lanes: _lanes,
                      laneGap: _laneGap,
                    ),
                  ),
                ),
                for (final st in roadmap.stages)
                  if (subjects.contains(st.subject))
                    _positioned(
                      context,
                      st,
                      subjects,
                      colW,
                      // 목적지를 안 골랐으면 전부 같은 밝기(null).
                      onPath: _dest?.stageIds.contains(st.id),
                    ),
              ],
            ),
          ),
          const SizedBox(height: AppSpace.xl),
        ],
      ),
    );
  }

  Widget _subjectHeader(
    BuildContext context,
    List<String> subjects,
    double colW,
  ) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Row(
      children: [
        const SizedBox(width: _axisW),
        for (final s in subjects)
          Container(
            width: colW,
            margin: const EdgeInsets.only(right: _gap),
            padding: const EdgeInsets.symmetric(vertical: 7),
            decoration: BoxDecoration(
              color: AppColors.subjectOn(s, dark).withValues(
                alpha: 0.1,
              ),
              borderRadius: BorderRadius.circular(AppRadius.sm),
            ),
            child: Center(
              child: Text(
                subjectNames[s] ?? s,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  color: AppColors.subjectOn(s, dark),
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
          ),
      ],
    );
  }

  Widget _positioned(
    BuildContext context,
    RoadmapStage st,
    List<String> subjects,
    double colW, {
    bool? onPath,
  }) {
    final col = subjects.indexOf(st.subject);
    // 자리는 겹침에서 계산한다 — [RoadmapLanes] 참고.
    final lanes = _lanes.countFor(st.subject);
    final laneW = (colW - _laneGap * (lanes - 1)) / lanes;
    final left =
        _axisW +
        col * (colW + _gap) +
        _lanes.laneOfStage(st.id) * (laneW + _laneGap);

    return Positioned(
      top: _y(st.gradeMin) + 2,
      left: left,
      width: laneW,
      height: (st.gradeMax - st.gradeMin + 1) * _unitH - 6,
      child: _StageCard(
        stage: st,
        data: data,
        regionId: regionId,
        onPath: onPath,
      ),
    );
  }
}

class _GradeRow extends StatelessWidget {
  final int grade;
  final RoadmapMilestone? milestone;

  /// 고른 목적지의 분기점. '언제 갈리는가' 가 학부모의 실제 질문이라
  /// 이정표(milestone)보다 강하게 적는다.
  final DestinationGate? gate;

  const _GradeRow({required this.grade, this.milestone, this.gate});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return SizedBox(
      height: RoadmapView._unitH,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: RoadmapView._axisW,
            child: Padding(
              padding: const EdgeInsets.only(top: 2, right: 8),
              child: Text(
                Stage.gradeName(grade),
                textAlign: TextAlign.right,
                style: text.bodySmall?.copyWith(
                  fontSize: 11,
                  fontWeight: (gate != null || milestone != null)
                      ? FontWeight.w800
                      : FontWeight.w400,
                  color: gate != null
                      ? AppColors.estimated
                      : (milestone != null ? AppColors.gold : null),
                ),
              ),
            ),
          ),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Divider(
                  height: 1,
                  thickness: gate != null ? 1.6 : 1,
                  color: gate != null
                      ? AppColors.estimated.withValues(alpha: 0.8)
                      : milestone != null
                          ? AppColors.gold.withValues(alpha: 0.55)
                          : Theme.of(context)
                              .dividerColor
                              .withValues(alpha: 0.5),
                ),
                // 관문을 이정표보다 위에 둔다. 되돌리기 어려운 지점이
                // 그 나이의 가장 중요한 사실이다.
                if (gate != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Row(
                      children: [
                        const Icon(
                          Icons.flag_outlined,
                          size: 11,
                          color: AppColors.estimated,
                        ),
                        const SizedBox(width: 3),
                        Flexible(
                          child: Text(
                            gate!.note,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: text.bodySmall?.copyWith(
                              fontSize: 10,
                              height: 1.3,
                              fontWeight: FontWeight.w600,
                              color: AppColors.estimated,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                if (milestone != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Tooltip(
                      message: milestone!.note,
                      child: Text(
                        '◆ ${milestone!.label}',
                        style: text.bodySmall?.copyWith(
                          fontSize: 10,
                          color: AppColors.gold,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _StageCard extends StatelessWidget {
  /// 학원 한 줄의 높이(실측). 아이콘 10 + 글자 11 + 위 여백 1.
  /// 몇 줄이 들어가는지 세는 데만 쓴다 — 줄 자체는 제 크기로 그린다.
  static const _topLineH = 16.0;

  /// 이 폭 아래로는 점수를 빼고 이름에 자리를 준다. 학원 이름은 대개
  /// 네다섯 글자(11px ≈ 55px)라 아이콘·여백을 빼면 이만큼은 있어야 한다.
  static const _compactWidth = 118.0;

  final RoadmapStage stage;
  final EduTreeData data;
  final String regionId;
  /// 고른 목적지의 길에 속하는가. null 이면 목적지를 안 골랐다는 뜻이라
  /// 전부 같은 밝기로 둔다 — 아무것도 안 골랐는데 흐려지면 고장으로 보인다.
  final bool? onPath;

  const _StageCard({
    required this.stage,
    required this.data,
    required this.regionId,
    this.onPath,
  });

  /// 카드 아래의 학원 한 줄. 세 상태를 서로 다르게 적는다.
  ///
  ///   ★ 점수   랭킹에 든 곳
  ///   ○ 표본   이 단계 학원이지만 아직 표본이 모자란 곳
  ///   … 구간   이 단계 근거는 없고 같은 과목·구간이라 이어 붙인 곳
  ///
  /// 셋을 같은 얼굴로 적으면 목록은 채워지지만 무엇을 믿을지는 알 수 없다.
  ///
  /// [compact] 는 칸이 좁을 때다(한 과목이 여러 칸으로 갈리면 카드가
  /// 75px 까지 좁아진다). 그때는 **점수를 뺀다** — 이름과 점수를 한 줄에
  /// 우겨 넣으면 정작 찾으러 온 이름이 서너 글자로 잘린다. 점수는 눌러서
  /// 여는 시트에 온전히 있다. 없앨 것은 기능이 아니라 곁가지다.
  Widget _topLine(BuildContext context, StageMatch m, {bool compact = false}) {
    final text = Theme.of(context).textTheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final score = m.academy.scoreFor(stage.subject);
    final starred = score.isRanked && m.isDirect;
    final dim = !starred;

    return Padding(
      padding: const EdgeInsets.only(top: 1),
      child: Row(
        children: [
          Icon(
            !m.isDirect
                ? Icons.more_horiz
                : score.isRanked
                ? Icons.star_rounded
                : Icons.circle_outlined,
            size: 10,
            color: starred ? AppColors.gold : AppColors.mist,
          ),
          const SizedBox(width: 3),
          Expanded(
            child: Text(
              m.academy.displayName,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: text.bodySmall?.copyWith(
                fontSize: 10.5,
                color: dim
                    ? AppColors.mist
                    : (dark ? Colors.white70 : AppColors.inkSoft),
              ),
            ),
          ),
          if (!compact)
            Text(
              !m.isDirect
                  ? '구간'
                  : score.isRanked
                  ? score.total.toStringAsFixed(0)
                  : '표본',
              style: text.bodySmall?.copyWith(
                fontSize: 10.5,
                fontWeight: starred ? FontWeight.w700 : FontWeight.w400,
                color: dim ? AppColors.mist : null,
              ),
            ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final accent = AppColors.subjectOn(
        stage.subject, Theme.of(context).brightness == Brightness.dark);

    // 로드맵에서 랭킹으로 이어지는 고리 — 이 단계 담당 학원 중 상위.
    // 유아 단계는 랭킹과 연결하지 않는다.
    //
    // 랭킹 진입(표본 10건 이상) 학원만 보이면 160개 조합 중 18개만
    // 채워진다. 그래서 부족하면 아직 표본이 모자란 곳까지 이어 붙이되,
    // 점수 대신 '표본 부족'이라 적는다 — 없는 점수를 있는 척하지 않으면서
    // '이 단계에 어떤 학원이 있는가'는 답할 수 있다.
    //
    // 그마저 없으면(세부 단계는 근거 있는 학원이 아예 없기도 하다) 같은
    // 과목·구간까지 넓힌다. 이어 붙인 곳은 별표 대신 흐린 점으로 나오고,
    // 시트를 열면 '이 단계 근거 없음'이라 적혀 있다.
    final tops = stage.roadmapOnly
        ? const <StageMatch>[]
        : data
              .academiesForStage(stage.id, regionId: regionId, fillTo: 3)
              .take(3)
              .toList();

    final full = data.stageById[stage.id];

    // 길 밖은 **지우지 않고 흐리게** 둔다. 없애면 '그 과목이 아예 없다' 로
    // 읽히는데, 사실은 이 목적지가 그 단계를 요구하지 않을 뿐이다.
    final off = onPath == false;
    final card = InkWell(
      borderRadius: BorderRadius.circular(AppRadius.sm),
      onTap: full == null
          ? null
          : () => showStageSheet(context, full, data, regionId),
      child: Container(
        padding: const EdgeInsets.fromLTRB(9, 7, 9, 7),
        decoration: BoxDecoration(
          color: dark ? AppColors.darkSurface : AppColors.surface,
          borderRadius: BorderRadius.circular(AppRadius.sm),
          border: Border.all(
            color: onPath == true
                ? AppColors.accentOn(dark)
                : stage.roadmapOnly
                    ? AppColors.mist
                    : accent.withValues(alpha: 0.55),
            width: onPath == true ? 2 : (stage.roadmapOnly ? 1 : 1.4),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(width: 3, height: 12, color: accent),
                const SizedBox(width: 5),
                Expanded(
                  child: Text(
                    stage.title,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: text.labelLarge?.copyWith(
                      fontSize: 12.5,
                      height: 1.25,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 2),
            Text(
              stage.gradeLabel,
              style: text.bodySmall?.copyWith(fontSize: 10),
            ),
            if (stage.roadmapOnly)
              Expanded(
                child: Align(
                  alignment: Alignment.bottomLeft,
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // 이름은 적되 **점수도 등수도 붙이지 않는다.** 5~6세를
                      // 순위에 세울 근거가 없다는 판단은 그대로다. 그래도
                      // '그 구간에 무엇이 있나' 는 답할 수 있고, 빈 칸으로
                      // 두면 화면이 학부모보다 덜 아는 셈이 된다.
                      for (final name in stage.examples)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 1),
                          child: Text(
                            name,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: text.bodySmall?.copyWith(fontSize: 11),
                          ),
                        ),
                      Text(
                        '로드맵 안내 · 순위 없음',
                        style: text.bodySmall?.copyWith(
                          fontSize: 9.5,
                          color: AppColors.mist,
                        ),
                      ),
                    ],
                  ),
                ),
              )
            else if (tops.isNotEmpty)
              // **들어가는 만큼만 싣는다.** 학년 한 칸짜리 카드(72px)는
              // 표제 두 줄과 학년 표기를 빼고 나면 20px 남짓만 남는데,
              // 거기에 세 줄을 밀어 넣고 있었다 — 실측 43px 넘침. 넘친
              // 부분은 그려지지 않으므로 **학원 이름이 통째로 사라진다.**
              // 잘려 나가느니 적게 보여주는 편이 낫다.
              Expanded(
                child: LayoutBuilder(
                  builder: (context, c) {
                    final n = (c.maxHeight / _topLineH)
                        .floor()
                        .clamp(0, tops.length);
                    if (n == 0) return const SizedBox.shrink();
                    return Align(
                      alignment: Alignment.bottomLeft,
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          for (final m in tops.take(n))
                            _topLine(context, m,
                                compact: c.maxWidth < _compactWidth),
                        ],
                      ),
                    );
                  },
                ),
              ),
          ],
        ),
      ),
    );
    return off
        ? Opacity(opacity: 0.26, child: IgnorePointer(child: card))
        : card;
  }
}

/// 단계 사이 경로선. 같은 과목 안의 연결만 그린다 —
/// 과목을 가로지르는 선까지 그리면 지도가 실타래가 된다.
class _EdgePainter extends CustomPainter {
  final Roadmap roadmap;
  final List<String> subjects;
  final double colW;
  final double gap;
  final double axisW;
  final double Function(num) yOf;
  final Color lineColor;
  final RoadmapLanes lanes;
  final double laneGap;

  _EdgePainter({
    required this.roadmap,
    required this.subjects,
    required this.colW,
    required this.gap,
    required this.axisW,
    required this.yOf,
    required this.lineColor,
    required this.lanes,
    required this.laneGap,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final byId = {for (final s in roadmap.stages) s.id: s};
    final paint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.4;

    // 카드 배치와 **같은 자리 계산**을 쓴다. 예전에는 겹침 판정을 여기에
    // 한 벌 더 적어 두었는데, 그러면 배치를 고칠 때 경로선이 옛 규칙에
    // 남아 카드와 어긋난 곳을 가리킨다.
    double centerX(RoadmapStage st) {
      final col = subjects.indexOf(st.subject);
      final n = lanes.countFor(st.subject);
      final laneW = (colW - laneGap * (n - 1)) / n;
      return axisW +
          col * (colW + gap) +
          lanes.laneOfStage(st.id) * (laneW + laneGap) +
          laneW / 2;
    }

    for (final e in roadmap.edges) {
      final a = byId[e.from];
      final b = byId[e.to];
      if (a == null || b == null) continue;
      if (a.subject != b.subject) continue;
      if (!subjects.contains(a.subject)) continue;

      paint.color = switch (e.type) {
        EdgeType.accelerated => AppColors.gold,
        EdgeType.alternative => lineColor,
        _ => AppColors.navyBright.withValues(alpha: 0.5),
      };

      final start = Offset(centerX(a), yOf(a.gradeMax + 1) - 4);
      final end = Offset(centerX(b), yOf(b.gradeMin) + 2);
      final mid = (start.dy + end.dy) / 2;
      canvas.drawPath(
        Path()
          ..moveTo(start.dx, start.dy)
          ..cubicTo(start.dx, mid, end.dx, mid, end.dx, end.dy),
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _EdgePainter old) =>
      old.colW != colW ||
      old.roadmap != roadmap ||
      // 과목 목록이 바뀌면(모바일에서 페이지를 넘기면) 칸 번호가 그대로여도
      // 선이 다른 자리로 가야 한다.
      !identical(old.subjects, subjects) ||
      !identical(old.lanes, lanes);
}
