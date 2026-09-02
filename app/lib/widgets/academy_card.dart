import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/theme.dart';
import '../data/models.dart';
import '../data/repository.dart';
import 'annals.dart';
import 'common.dart';
import 'contact.dart';

/// 랭킹 · 검색 · 단계 상세에서 공통으로 쓰는 학원 카드.
///
/// 「實錄」에서 이 카드는 **한 건의 기록(記錄)** 이다. 조형을 그렇게 짰다:
///
///   왼쪽 칸  등수를 장부 숫자로 **매달아** 둔다. 본문 밖에 있으므로
///            줄이 몇 줄이 되든 등수의 세로 위치가 흔들리지 않는다.
///   도장     공시로 검증된 등록에만 찍는다. 꼬리표 하나를 도장으로
///            바꾼 것인데, 꼬리표는 읽어야 하고 도장은 보면 안다.
///   계선     카드를 띄우지 않는다. 그림자로 떠 있는 것은 광고고,
///            줄로 갈린 것은 기록이다.
class AcademyCard extends StatelessWidget {
  final Academy academy;
  final int? rank;
  final bool showPillars;
  final String? stageContext;

  /// 과목 랭킹에서 보여줄 때의 과목. 같은 학원이라도 과목마다 표본과
  /// 점수가 다르므로, 어느 과목의 순위를 보고 있는지가 곧 어떤 점수를
  /// 보여줄지를 정한다.
  final String? subject;

  /// 테크트리 단계 목록에서 보여줄 때, **이 학원이 왜 이 단계에 있는지.**
  /// [StageMatch.basis] 를 그대로 받는다. 큐레이션(curated)은 적지 않는다 —
  /// 기본값이라 매번 적으면 읽히지 않는다. 나머지는 반드시 적는다:
  /// 추정과 확정이 같은 얼굴로 나오면 목록 전체를 믿을 수 없게 된다.
  final String? stageBasis;

  /// 목록에서의 순번. 획이 차례로 그어지도록 시차를 준다.
  final int index;

  const AcademyCard({
    super.key,
    required this.academy,
    this.rank,
    this.showPillars = true,
    this.stageContext,
    this.subject,
    this.stageBasis,
    this.index = 0,
  });

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final score = academy.scoreFor(subject);
    final narrow = MediaQuery.sizeOf(context).width < 560;
    final gutter = narrow ? 44.0 : 58.0;

    // **카드 스스로는 등장하지 않는다.**
    //
    // 한때 여기서 획을 그었는데 두 가지가 걸렸다. 하나, 랭킹은 100곳이
    // 넘고 목록은 스크롤할 때마다 항목을 새로 만들었다 지운다 — 되올릴
    // 때마다 같은 카드가 다시 그어져 목록이 부산스러웠다. 둘, 줄마다
    // 움직이는 목록은 훑어 읽기가 어렵다. 발췌처럼 **세 장쯤 세워 두는
    // 자리**에서만 값이 있으므로, 열지 말지는 화면이 정하도록 [Reveal] 로
    // 감싸는 몫을 호출부에 넘겼다.
    return Container(
      margin: const EdgeInsets.only(bottom: AppSpace.sm),
      decoration: BoxDecoration(
        color: AppColors.surfaceOn(dark),
        border: Border(
          top: BorderSide(color: AppColors.ruleOn(dark), width: AppRule.hair),
          bottom: BorderSide(
            color: AppColors.ruleOn(dark),
            width: AppRule.hair,
          ),
          // 왼쪽 굵은 획이 '기록 한 건'의 시작을 표시한다.
          // 순위권(1~3)만 주묵. 나머지는 먹.
          left: BorderSide(
            color: (rank != null && rank! <= 3)
                ? AppColors.accentOn(dark)
                : AppColors.ruleOn(dark),
            width: (rank != null && rank! <= 3) ? AppRule.bold : AppRule.hair,
          ),
          right: BorderSide(color: AppColors.ruleOn(dark), width: AppRule.hair),
        ),
      ),
      child: InkWell(
        onTap: () => context.go('/academy/${academy.id}'),
        child: Padding(
          padding: EdgeInsets.fromLTRB(
            narrow ? 12 : AppSpace.md,
            14,
            narrow ? 12 : AppSpace.md,
            14,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // ── 왼쪽 칸: 매달린 등수
                  if (rank != null) ...[
                    SizedBox(
                      width: gutter,
                      child: _RankGutter(rank: rank!, academyId: academy.id),
                    ),
                    const SizedBox(width: AppSpace.sm),
                  ],

                  // ── 본문
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.center,
                          children: [
                            Flexible(
                              child: Text(
                                academy.displayName,
                                style: text.titleLarge,
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                            // 도장은 이름 바로 뒤에. 이름과 떨어지면
                            // 무엇을 검증했다는 것인지 안 읽힌다.
                            if (academy.isVerified) ...[
                              const SizedBox(width: 7),
                              // 글자는 **획이 적은 것**으로 고른다.
                              // '實' 은 21px 에서 붉은 네모 안의 얼룩이
                              // 됐다(실측). '正' 은 다섯 획이라 이 크기에서
                              // 살아남고, 뜻도 '바르다'라 검증에 맞는다.
                              Tooltip(
                                message: '공시 검증 — NEIS 등록 정보와 대조했습니다',
                                child: SealPress(
                                  delay: AppMotion.stagger * (index + 2),
                                  child: Seal(
                                    '正',
                                    size: 21,
                                    color: AppColors.accentOn(dark),
                                  ),
                                ),
                              ),
                            ],
                            if (stageContext != null &&
                                academy.isFlagshipOf(stageContext!)) ...[
                              const SizedBox(width: 6),
                              const TagMark(
                                '대표',
                                color: AppColors.gold,
                                icon: Icons.star_rounded,
                              ),
                            ],
                          ],
                        ),
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 5,
                          runSpacing: 5,
                          crossAxisAlignment: WrapCrossAlignment.center,
                          children: [
                            // 표시 이름이 없는 과목 키는 **찍지 않는다.**
                            // `general` 은 '어느 과목인지 모른다'는 뜻인데,
                            // 키를 그대로 내면 화면에 'general' 이라는
                            // 영문이 꼬리표로 붙는다(실측: 깊은생각 카드).
                            // 모른다는 것은 붙일 꼬리표가 없다는 뜻이다.
                            // 표준 순서로 세운 뒤 앞에서 셋. 데이터가 주는
                            // 순서대로 찍으면 같은 학원인데 화면마다 꼬리표
                            // 차례가 달라진다.
                            for (final s in orderedSubjects(
                              academy.subjects,
                            ).take(3))
                              if (subjectNames[s] case final name?)
                                TagMark(
                                  name,
                                  color: AppColors.subjectOn(s, dark),
                                ),
                            // 검증된 곳은 도장이 이미 말했다. 꼬리표까지
                            // 붙이면 같은 말을 두 번 한다.
                            if (!academy.isVerified)
                              const VerifiedChip(verified: false),
                            ConfidenceChip(score: score),
                            if (StageMatch.labelFor(stageBasis)
                                case final basisLabel?)
                              TagMark(
                                basisLabel,
                                color: AppColors.mist,
                                icon: Icons.help_outline,
                              ),
                            if (academy.registrationCount > 1)
                              TagMark(
                                '${academy.registrationCount}개 등록 통합',
                                color: AppColors.slate,
                                icon: Icons.merge_type,
                              ),
                            if (academy.capacity != null)
                              TagMark(
                                '정원 ${academy.capacity}명',
                                color: AppColors.slate,
                                icon: Icons.groups_outlined,
                              ),
                            // 목록에서 바로 건다. 상세로 들어가 번호를
                            // 옮겨 적는 것이 학부모의 실제 다음 동작이었다.
                            CallTag(academy: academy),
                          ],
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(width: AppSpace.md),

                  // ── 오른쪽: 점수 눈금
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      // 근거가 없거나 네 기둥을 못 채웠으면 숫자를 내지
                      // 않는다 — 견줄 수 없는 값이다.
                      if (!score.hasTotal)
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                            Text(
                              '—',
                              style: TextStyle(
                                fontFamily: 'Paperlogy',
                                fontSize: narrow ? 26 : 32,
                                height: 1.0,
                                color: AppColors.mist,
                              ),
                            ),
                            const SizedBox(height: 5),
                            // 두 상태를 같은 말로 적지 않는다. '근거 없음'
                            // 은 아무것도 못 본 것이고, '기둥 미완' 은
                            // 후기는 있는데 진입난이도를 잴 사건이 없어
                            // 네 기둥을 못 채운 것이다.
                            RailLabel(spaced(
                                score.sampleSize == 0 ? '근거없음' : '기둥미완')),
                          ],
                        )
                      else ...[
                        ScoreDial(
                          score.total,
                          size: narrow ? 44 : 52,
                          showLabel: false,
                        ),
                        const SizedBox(height: 7),
                        MomentumArrow(score.momentumDirection),
                        // 점수 하나만으로는 무엇을 뜻하는지 읽히지 않는다.
                        // '의견 낸 후기 중 긍정 N%' 는 그 자체로 읽힌다.
                        if (score.positiveRate != null) ...[
                          const SizedBox(height: 2),
                          Text(
                            '긍정 ${score.positiveRate!.round()}%',
                            style: TextStyle(
                              fontFamily: 'Paperlogy',
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                              color: AppColors.mutedOn(dark),
                              fontFeatures: ledgerFigures,
                            ),
                          ),
                        ],
                      ],
                    ],
                  ),
                ],
              ),

              // ── 점수 구성. 근거가 없으면 그리지 않는다 — 코호트
              //    평균(50)으로 채워진 막대가 '평가 결과'로 읽힌다.
              if (showPillars && score.sampleSize > 0) ...[
                const SizedBox(height: 10),
                Padding(
                  padding: EdgeInsets.only(
                    left: rank != null ? gutter + AppSpace.sm : 0,
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Rule(color: AppColors.ruleSoftOn(dark)),
                      const SizedBox(height: 12),
                      AcademyPillarGrid(score: score, narrow: narrow),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// 매달린 등수 + 지난 집계 대비 변동.
///
/// 등수 아래 계선을 짧게 긋는다. 장부의 항목 번호가 그렇게 생겼고,
/// 줄이 있으면 숫자가 본문이 아니라 **색인**으로 읽힌다.
class _RankGutter extends StatelessWidget {
  final int rank;
  final String academyId;
  const _RankGutter({required this.rank, required this.academyId});

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final top = rank <= 3;
    final color = top ? AppColors.accentOn(dark) : AppColors.inkOn(dark);
    final narrow = MediaQuery.sizeOf(context).width < 560;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        // 한 자리 등수도 두 자리로 적는다. 목록에서 자릿수가 흔들리면
        // 왼쪽 줄이 들쭉날쭉해져 색인처럼 보이지 않는다.
        Text(
          rank < 10 ? '0$rank' : '$rank',
          style: TextStyle(
            fontFamily: 'Paperlogy',
            fontSize: narrow ? 24 : 30,
            fontWeight: FontWeight.w800,
            height: 0.95,
            letterSpacing: -1.6,
            color: color,
            fontFeatures: ledgerFigures,
          ),
        ),
        const SizedBox(height: 6),
        Rule(
          extent: narrow ? 22 : 28,
          thickness: top ? AppRule.bold : AppRule.hair,
          color: top ? color : AppColors.ruleOn(dark),
        ),
        const SizedBox(height: 6),
        _RankDelta(academyId: academyId),
      ],
    );
  }
}

/// 지난 집계 대비 순위 변동. 이력이 하루뿐이면 아무것도 내지 않는다.
class _RankDelta extends ConsumerWidget {
  final String academyId;
  const _RankDelta({required this.academyId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final hist = ref.watch(historyProvider).value;
    final points = hist?.forAcademy(academyId) ?? const <RankPoint>[];
    if (points.length < 2) return const SizedBox.shrink();
    final prev = points[points.length - 2].rank;
    final now = points.last.rank;
    if (prev == null || now == null || prev == now) {
      return const SizedBox.shrink();
    }

    final up = now < prev; // 숫자가 작아지면 순위가 오른 것
    final color = up ? AppColors.rising : AppColors.falling;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          up ? '▲' : '▼',
          style: TextStyle(fontSize: 9.5, height: 1.4, color: color),
        ),
        const SizedBox(width: 2),
        Text(
          '${(prev - now).abs()}',
          style: TextStyle(
            fontFamily: 'Paperlogy',
            fontSize: 11,
            fontWeight: FontWeight.w700,
            color: color,
            fontFeatures: ledgerFigures,
          ),
        ),
      ],
    );
  }
}

/// 카드의 기둥 막대. 가중치는 meta.json 에서 읽는다.
///
/// 예전에는 여기에 0.20/0.25 가 상수로 박혀 있었다. 산식을 0.35 로 바꾼
/// 뒤에도 카드는 옛 값을 그대로 보여줬다 — 상세의 35%와 목록의 20%가
/// 어긋나 있었던 이유다.
class AcademyPillarGrid extends ConsumerWidget {
  final Score score;
  final bool narrow;
  const AcademyPillarGrid({
    super.key,
    required this.score,
    this.narrow = false,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final meta = ref.watch(dataProvider).value?.meta;
    // 예체능·기타는 투명성·진입난이도를 채점하지 않는다. 값이 없는
    // 기둥을 0으로 그리면 '점수가 나쁘다'로 읽힌다. 저울은 meta 가 준다 —
    // 화면이 상수로 들고 있으면 산식을 바꿔도 여기만 옛 값으로 남는다.
    final weights = meta?.weightsFor(score.subjectGroup) ?? const {};
    if (weights.isEmpty) return const SizedBox.shrink();
    return PillarWeightBars(score: score, weights: weights, stacked: narrow);
  }
}
