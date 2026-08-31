import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme.dart';
import '../../widgets/annals.dart';
import '../../widgets/subject_bar.dart';
import '../../data/models.dart';
import '../../data/repository.dart';
import 'techtree_page.dart' show showStageSheet;

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

  /// 세로 열(lane) 하나의 최소·최대 폭.
  ///
  /// 카드 한 줄은 '점 + 학원 이름 + 점수'다. 이보다 좁아지면 이름이 두어
  /// 글자에서 잘려 '여기 무엇이 있는가'를 말하지 못한다. 겹치는 단계가
  /// 많은 과목은 열을 더 쓰고 판은 그만큼 넓어진다 — 좁혀서 못 읽게
  /// 만드느니 가로로 미는 편이 낫다.
  static const _minLaneW = 132.0;
  static const _maxLaneW = 220.0;

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
        return _scrollable(
          context,
          roadmap,
          subjects,
          _Layout.compute(roadmap.stages, subjects, available: c.maxWidth),
          totalH: _y(_maxGrade + 1) + 20,
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
            itemBuilder: (context, i) {
              final one = [subjects[i]]; // 한 과목만 그린다
              return _scrollable(
                context,
                roadmap,
                one,
                _Layout.compute(roadmap.stages, one, available: width),
                totalH: totalH,
                showHeader: false, // 과목 이름은 위 칩이 이미 말한다
              );
            },
          ),
        ),
      ],
    );
  }

  /// 로드맵 판 하나. 과목 목록을 그대로 받으므로 전체(네 과목)와
  /// 한 과목짜리가 같은 코드를 쓴다 — 경로선 좌표도 이 목록으로 계산된다.
  /// 가로 스크롤 껍데기.
  ///
  /// 겹치는 단계가 많은 과목은 열을 더 쓰므로 판이 화면보다 넓어질 수
  /// 있다. 예전에는 열 폭을 340 으로 잘라 화면 안에 욱여넣었고, 그래서
  /// 겹친 카드가 서로를 덮었다. 넓으면 민다.
  Widget _scrollable(
    BuildContext context,
    Roadmap roadmap,
    List<String> subjects,
    _Layout layout, {
    required double totalH,
    bool showHeader = true,
  }) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: SizedBox(
        width: layout.contentW,
        child: _board(
          context,
          roadmap,
          subjects,
          layout,
          totalH: totalH,
          showHeader: showHeader,
        ),
      ),
    );
  }

  Widget _board(
    BuildContext context,
    Roadmap roadmap,
    List<String> subjects,
    _Layout layout, {
    required double totalH,
    bool showHeader = true,
  }) {
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (showHeader) ...[
            const SizedBox(height: AppSpace.md),
            _subjectHeader(context, subjects, layout),
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
                      layout: layout,
                      yOf: _y,
                      lineColor: Theme.of(context).dividerColor,
                    ),
                  ),
                ),
                for (final st in roadmap.stages)
                  if (subjects.contains(st.subject))
                    _positioned(
                      context,
                      st,
                      layout,
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
    _Layout layout,
  ) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Row(
      children: [
        const SizedBox(width: _axisW),
        for (final s in subjects)
          Container(
            width: layout.width[s],
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
    _Layout layout, {
    bool? onPath,
  }) {
    return Positioned(
      top: _y(st.gradeMin) + 2,
      left: layout.left(st),
      width: layout.laneW(st.subject),
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
  Widget _topLine(BuildContext context, StageMatch m) {
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

  /// 큐레이션한 대표 학원 한 줄.
  ///
  /// 근거 데이터가 없어 점수를 매기지 않는 구간(영유 등)은 목록이 통째로
  /// 비어 '어디를 말하는 것이냐'에 답하지 못했다. 사람이 적은 이름이므로
  /// 별표도 점수도 붙이지 않는다 — 점수와 같은 얼굴로 적으면 재지 않은
  /// 것을 잰 것처럼 읽힌다.
  Widget _repLine(BuildContext context, String name) {
    final text = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.only(top: 1),
      child: Row(
        children: [
          const Icon(Icons.bookmark_border, size: 10, color: AppColors.mist),
          const SizedBox(width: 3),
          Expanded(
            child: Text(
              name,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: text.bodySmall?.copyWith(
                fontSize: 10.5,
                color: AppColors.mist,
              ),
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

    // 카드 높이는 학년 폭에서 나온다(한 학년 = 72px). 한 학년짜리 단계는
    // 66px 뿐이라 제목 두 줄 + 학년 + 학원 세 줄이 애초에 들어가지 않는다.
    // 예전에는 넘치는 만큼 **잘려서** 학원 이름이 소리 없이 사라졌다.
    // 들어갈 만큼만 적고 나머지는 카드를 눌러 시트에서 본다.
    int slotsFor(double h) {
      final headH = 14 + (h < 100 ? 16.0 : 32.0) + 2 + 14;
      return ((h - headH) / 14.5).floor().clamp(0, 3);
    }

    final full = data.stageById[stage.id];

    // 길 밖은 **지우지 않고 흐리게** 둔다. 없애면 '그 과목이 아예 없다' 로
    // 읽히는데, 사실은 이 목적지가 그 단계를 요구하지 않을 뿐이다.
    final off = onPath == false;
    final card = LayoutBuilder(
      builder: (context, cons) {
        final slots = slotsFor(cons.maxHeight);
        final titleLines = cons.maxHeight < 100 ? 1 : 2;
        return InkWell(
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
                    maxLines: titleLines,
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
                      for (final r
                          in stage.representatives.take(
                            slots > 0 ? slots - 1 : 0,
                          ))
                        _repLine(context, r),
                      Text(
                        stage.representatives.isEmpty
                            ? '로드맵 안내 · 순위 없음'
                            : '대표 학원 · 순위 없음',
                        style: text.bodySmall?.copyWith(
                          fontSize: 9.5,
                          color: AppColors.mist,
                        ),
                      ),
                    ],
                  ),
                ),
              )
            else if (tops.isNotEmpty && slots > 0)
              Expanded(
                child: Align(
                  alignment: Alignment.bottomLeft,
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      for (final m in tops.take(slots)) _topLine(context, m),
                    ],
                  ),
                ),
              ),
          ],
        ),
      ),
        );
      },
    );
    return off
        ? Opacity(opacity: 0.26, child: IgnorePointer(child: card))
        : card;
  }
}

/// 판의 가로 배치 — 과목별 열 폭과, 겹치는 단계를 가르는 lane.
///
/// **lane 은 적는 것이 아니라 계산한다.** 예전에는 yaml 에 손으로 적어 둔
/// lane(0/1)을 그대로 믿고 '겹치면 열을 둘로 가른다'로 그렸다. 그런데 실제
/// 데이터는 한 학년에 최대 **네 단계**가 겹친다(수학 중2: 중등 내신 · 심화
/// KMO · 고등 선행 · 영재고 대비). 열이 둘뿐이라 나머지는 앞 카드와 **같은
/// 자리에 겹쳐 그려졌다** — 41단계 중 18쌍이 그랬고, 나중에 그린 카드가 앞
/// 카드를 덮어 학원 이름이 소리 없이 사라졌다. 로그도 안 남고 화면도
/// 멀쩡해 보이는 종류의 고장이다.
///
/// 이제 시작 학년 순으로 훑으며 **비어 있는 첫 열**에 넣는다(구간 그래프
/// 색칠). 겹치는 단계가 같은 열에 놓이는 일이 없고, 열은 그 과목이 실제로
/// 필요로 하는 만큼만 쓴다. yaml 의 lane 은 이제 '같은 학년에 시작하는
/// 단계들의 좌우 차례' 힌트로만 남는다.
class _Layout {
  /// 단계 id → 열 번호
  final Map<String, int> lane;

  /// 과목 → 열 수
  final Map<String, int> lanes;

  /// 과목 → 열 묶음의 왼쪽 x
  final Map<String, double> x;

  /// 과목 → 열 묶음 전체 폭
  final Map<String, double> width;

  /// 축을 포함한 판 전체 폭
  final double contentW;

  const _Layout(this.lane, this.lanes, this.x, this.width, this.contentW);

  double laneW(String subject) {
    final n = lanes[subject] ?? 1;
    final w = width[subject] ?? RoadmapView._minLaneW;
    return (w - RoadmapView._gap * (n - 1)) / n;
  }

  double left(RoadmapStage st) =>
      (x[st.subject] ?? RoadmapView._axisW) +
      (lane[st.id] ?? 0) * (laneW(st.subject) + RoadmapView._gap);

  double centerX(RoadmapStage st) => left(st) + laneW(st.subject) / 2;

  static _Layout compute(
    List<RoadmapStage> stages,
    List<String> subjects, {
    required double available,
  }) {
    final lane = <String, int>{};
    final lanes = <String, int>{};

    for (final s in subjects) {
      final list = stages.where((st) => st.subject == s).toList()
        ..sort((a, b) {
          final c = a.gradeMin.compareTo(b.gradeMin);
          if (c != 0) return c;
          // 시작이 같으면 사람이 적어 둔 자리를 존중한다. 충돌하지 않는
          // 한 원래 의도한 좌우가 그대로 남는다.
          final l = a.lane.compareTo(b.lane);
          return l != 0 ? l : a.gradeMax.compareTo(b.gradeMax);
        });
      // 열마다 '지금까지 찬 마지막 학년'
      final until = <int>[];
      for (final st in list) {
        var i = 0;
        while (i < until.length && until[i] >= st.gradeMin) {
          i++;
        }
        if (i == until.length) {
          until.add(st.gradeMax);
        } else {
          until[i] = st.gradeMax;
        }
        lane[st.id] = i;
      }
      lanes[s] = until.isEmpty ? 1 : until.length;
    }

    // 열 폭은 과목마다 다르다. 겹침이 없는 과목까지 가장 넓은 과목에
    // 맞춰 늘리면 판만 넓어지고 빈 자리가 는다.
    final width = <String, double>{};
    var need = 0.0;
    for (final s in subjects) {
      final n = lanes[s]!;
      width[s] = n * RoadmapView._minLaneW + RoadmapView._gap * (n - 1);
      need += width[s]! + RoadmapView._gap;
    }

    // 자리가 남으면 고르게 나눠 준다. 줄이지는 않는다 — 최소 폭은
    // '이름이 읽히는가'로 정한 값이라 양보하면 고치려던 문제로 돌아간다.
    final slack = available - RoadmapView._axisW - need;
    if (slack > 0) {
      final add = slack / subjects.length;
      for (final s in subjects) {
        final n = lanes[s]!;
        final cap = n * RoadmapView._maxLaneW + RoadmapView._gap * (n - 1);
        width[s] = (width[s]! + add).clamp(width[s]!, cap);
      }
    }

    final x = <String, double>{};
    var cursor = RoadmapView._axisW;
    for (final s in subjects) {
      x[s] = cursor;
      cursor += width[s]! + RoadmapView._gap;
    }
    return _Layout(lane, lanes, x, width, cursor);
  }
}

/// 단계 사이 경로선. 같은 과목 안의 연결만 그린다 —
/// 과목을 가로지르는 선까지 그리면 지도가 실타래가 된다.
class _EdgePainter extends CustomPainter {
  final Roadmap roadmap;
  final List<String> subjects;
  final _Layout layout;
  final double Function(num) yOf;
  final Color lineColor;

  _EdgePainter({
    required this.roadmap,
    required this.subjects,
    required this.layout,
    required this.yOf,
    required this.lineColor,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final byId = {for (final s in roadmap.stages) s.id: s};
    final paint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.4;

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

      final start = Offset(layout.centerX(a), yOf(a.gradeMax + 1) - 4);
      final end = Offset(layout.centerX(b), yOf(b.gradeMin) + 2);
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
      old.layout.contentW != layout.contentW || old.roadmap != roadmap;
}
