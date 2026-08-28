import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/theme.dart';
import '../../data/models.dart';
import '../../data/repository.dart';
import '../../widgets/annals.dart';
import '../../widgets/common.dart';
import '../../data/corrections.dart';
import '../../data/leveltests.dart';
import '../../widgets/rank_history_chart.dart';
import 'review_section.dart';

/// 학원 상세.
///
/// 화면 구성의 핵심은 '검증된 사실'과 '커뮤니티 추정'을 절대 섞어 보여주지
/// 않는 것이다. 위쪽은 NEIS 공시 사실, 아래쪽은 추정 신호이며 각각 배지가 다르다.
class AcademyPage extends ConsumerWidget {
  final String academyId;
  const AcademyPage({super.key, required this.academyId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(dataProvider);

    return async.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text('$e')),
      data: (data) {
        final academy = data.academyById[academyId];
        if (academy == null) {
          return const Center(child: Text('학원을 찾을 수 없습니다'));
        }
        return _Body(academy: academy, data: data);
      },
    );
  }
}

class _Body extends StatelessWidget {
  final Academy academy;
  final EduTreeData data;
  const _Body({required this.academy, required this.data});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final score = academy.score;
    final region = data.regionById[academy.regionId];
    final stages = academy.stages
        .map((s) => data.stageById[s])
        .whereType<Stage>()
        .toList();
    final dark = Theme.of(context).brightness == Brightness.dark;

    return ListView(
      padding: const EdgeInsets.symmetric(vertical: AppSpace.lg),
      children: [
        ContentWidth(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              TextButton.icon(
                onPressed: () => context.go('/rank'),
                icon: const Icon(Icons.arrow_back, size: 16),
                label: const Text('랭킹으로'),
                style: TextButton.styleFrom(padding: EdgeInsets.zero),
              ),
              const SizedBox(height: AppSpace.sm),

              // ── 헤더 ────────────────────────────────────────
              Wrap(
                spacing: AppSpace.lg,
                runSpacing: AppSpace.md,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  // 표본이 0 이면 숫자를 내지 않는다. 아래 안내는 '점수를
                  // 매기지 않았습니다' 라고 적는데 머리에는 코호트 평균으로
                  // 채워진 값이 큼직하게 떠 있었다(실측: 근거 0건인데 40).
                  // 카드와 같은 규칙으로 맞춘다 — 다이얼은 '—', 라벨은
                  // '근거 없음'.
                  if (score.sampleSize == 0)
                    Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          '—',
                          style: TextStyle(
                            fontFamily: 'Paperlogy',
                            fontSize: 56,
                            height: 1.0,
                            color: AppColors.mist,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(spaced('근거없음'), style: text.labelMedium),
                      ],
                    )
                  else
                    ScoreDial(score.total, size: 92),
                  ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 560),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(academy.displayName, style: text.displayMedium),
                        const SizedBox(height: AppSpace.sm),
                        Wrap(
                          spacing: 6,
                          runSpacing: 6,
                          children: [
                            if (region != null)
                              Chip2(region.nameKo, color: AppColors.navy),
                            for (final s in orderedSubjects(academy.subjects))
                              Chip2(
                                subjectNames[s] ?? s,
                                color: AppColors.subjectOn(s, dark),
                              ),
                            VerifiedChip(verified: academy.isVerified),
                            ConfidenceChip(score: score),
                            if (score.rankInRegion != null)
                              Chip2(
                                '${region?.nameKo ?? ""} ${score.rankInRegion}위'
                                '${score.regionRankedCount != null ? " / ${score.regionRankedCount}곳" : ""}',
                                color: AppColors.gold,
                              ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AppSpace.xl),

              // ── 기둥별 점수 ─────────────────────────────────
              // 근거가 한 건도 없으면 점수를 내지 않는다. 코호트 평균으로
              // 채운 50점이 '평가 결과' 처럼 읽히면 그게 곧 거짓이다.
              if (score.sampleSize == 0)
                Card(
                  color: AppColors.estimated.withValues(alpha: 0.07),
                  child: Padding(
                    padding: const EdgeInsets.all(AppSpace.md),
                    child: Row(
                      children: [
                        const Icon(
                          Icons.info_outline,
                          size: 18,
                          color: AppColors.estimated,
                        ),
                        const SizedBox(width: AppSpace.sm),
                        Expanded(
                          child: Text(
                            '아직 이 학원을 다룬 글을 찾지 못했습니다. 점수를 매기지 '
                            '않았으며, 공식 등록 정보만 보여드립니다.',
                            style: text.bodyMedium,
                          ),
                        ),
                      ],
                    ),
                  ),
                )
              else ...[
                const SectionHeader(
                  '점수 구성',
                  subtitle:
                      '가중치가 큰 순서입니다. 각 기둥의 계산 근거를 '
                      '펼쳐 볼 수 있습니다.',
                ),
                // 무거운 기둥부터. 화면 순서가 곧 우선순위를 말한다.
                // 예체능·기타는 채점하지 않은 기둥을 아예 내지 않는다 —
                // 0 으로 그리면 '점수가 나쁘다'로 읽힌다.
                for (final key
                    in (pillarNames.keys.toList()..sort(
                      (a, b) => (data.meta.weights[b] ?? 0).compareTo(
                        data.meta.weights[a] ?? 0,
                      ),
                    )))
                  if (score.pillarOrNull(key) != null)
                    _PillarPanel(
                      pillar: key,
                      value: score.pillar(key),
                      weight: score.subjectGroup == 'academic'
                          ? (data.meta.weights[key] ?? 0)
                          : (key == 'reputation' ? 0.6 : 0.4),
                      breakdown:
                          (score.breakdown[key] as Map?)
                              ?.cast<String, dynamic>() ??
                          const {},
                    ),
              ],
              if (academy.subjectScores.length > 1) ...[
                const SizedBox(height: AppSpace.lg),
                _SubjectScores(academy: academy),
              ],
              const SizedBox(height: AppSpace.xl),

              // ── 공식 정보 ──────────────────────────────────
              SectionHeader(
                '공식 등록 정보',
                subtitle: academy.isVerified
                    ? 'NEIS 학원교습소정보 공시 기준 — 검증된 사실입니다'
                    : '샘플 데이터입니다. 실제 공시값이 아닙니다.',
              ),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(AppSpace.md),
                  child: Column(
                    children: [
                      if (academy.registrationCount > 1)
                        _Row(
                          '등록 건수',
                          '${academy.registrationCount}건 (관·과정별 등록을 한 학원으로 묶음)',
                        ),
                      if (academy.brandLabel != null)
                        _Row('브랜드', academy.brandLabel!),
                      _Row('등록상태', academy.registrationStatus ?? '—'),
                      _Row(
                        '정원',
                        academy.capacity != null ? '${academy.capacity}명' : '—',
                      ),
                      _Row('개설일', academy.establishedOn ?? '—'),
                      _Row('주소', academy.address ?? '—'),
                      if (academy.tel != null) _Row('전화', academy.tel!),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: AppSpace.xl),

              // ── 테크트리 위치 ───────────────────────────────
              if (stages.isNotEmpty) ...[
                const SectionHeader(
                  '단계별 진입 기준',
                  subtitle:
                      '이 학원이 담당하는 단계와, 각 단계를 넘어가려면 '
                      '무엇이 필요한지입니다. 커뮤니티 추정이 아니라 '
                      '큐레이션한 기준입니다.',
                ),
                Wrap(
                  spacing: AppSpace.sm,
                  runSpacing: AppSpace.sm,
                  children: [
                    for (final s in stages)
                      _StageLink(
                        stage: s,
                        track: data.trackById[s.trackId]!,
                        isFlagship: academy.isFlagshipOf(s.id),
                      ),
                  ],
                ),
                const SizedBox(height: AppSpace.md),
                for (final s in stages)
                  if (s.exitCriteria != null && s.exitCriteria!.isNotEmpty)
                    _StageCriteria(stage: s),
                const SizedBox(height: AppSpace.xl),
              ],

              // ── 근거 ───────────────────────────────────────
              const SectionHeader(
                '평판 점수에 반영된 근거',
                subtitle: '신뢰도 상위 게시물입니다. 원문 링크로만 제공하며 본문을 전재하지 않습니다.',
              ),
              if (academy.evidence.isEmpty)
                Text('표시할 근거가 없습니다.', style: text.bodyMedium)
              else
                for (final e in academy.evidence) _EvidenceTile(evidence: e),

              const SizedBox(height: AppSpace.xl),
              _RankTrend(academyId: academy.id, region: region?.nameKo ?? ''),

              const SizedBox(height: AppSpace.xl),
              _LevelTests(academyKey: academy.id),

              ReviewSection(
                academyId: academy.id,
                academyName: academy.displayName,
              ),

              const SizedBox(height: AppSpace.xl),
              _CorrectionNotice(
                academyKey: academy.id,
                academyName: academy.displayName,
              ),
              const SizedBox(height: AppSpace.xxl),
            ],
          ),
        ),
      ],
    );
  }
}

/// 과목별 점수 — 여러 과목을 가르치는 학원에만 보인다.
///
/// 한 학원이 여러 과목을 가르치는 것은 정상이지만, **근거는 과목마다
/// 다르다.** 수학 후기가 496건이고 과학 후기가 30건이라면 그 둘을 한
/// 점수로 합쳐 보여줄 수 없다 — 과학 순위가 수학의 명성으로 올라간다.
class _SubjectScores extends StatelessWidget {
  final Academy academy;
  const _SubjectScores({required this.academy});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final rows = academy.subjectScores.entries.toList()
      ..sort((a, b) => b.value.sampleSize.compareTo(a.value.sampleSize));

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SectionHeader(
          '과목별 점수',
          subtitle:
              '랭킹은 과목마다 따로 매깁니다. 그 과목을 말한 후기만 '
              '그 과목의 근거로 씁니다.',
        ),
        for (final e in rows)
          Padding(
            padding: const EdgeInsets.only(bottom: 6),
            child: Row(
              children: [
                SizedBox(
                  width: 74,
                  child: Chip2(
                    subjectNames[e.key] ?? e.key,
                    color: AppColors.subjectOn(e.key, dark),
                  ),
                ),
                const SizedBox(width: AppSpace.sm),
                SizedBox(
                  width: 52,
                  child: Text(
                    e.value.sampleSize == 0
                        ? '—'
                        : e.value.total.toStringAsFixed(1),
                    style: text.titleMedium,
                  ),
                ),
                Expanded(
                  child: Text(
                    e.value.sampleSize == 0
                        ? '근거 없음'
                        : '후기 ${e.value.sampleSize}건'
                              '${e.value.isRanked ? " · 학군 ${e.value.rankInRegion}위" : " · 표본 부족으로 순위 제외"}',
                    style: text.bodySmall,
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}

class _PillarPanel extends StatelessWidget {
  final String pillar;
  final double value;
  final double weight;
  final Map<String, dynamic> breakdown;
  const _PillarPanel({
    required this.pillar,
    required this.value,
    required this.weight,
    required this.breakdown,
  });

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final color = AppColors.pillars[pillar]!;
    final estimated = pillar == 'selectivity';

    return Card(
      margin: const EdgeInsets.only(bottom: AppSpace.sm),
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          tilePadding: const EdgeInsets.symmetric(horizontal: AppSpace.md),
          childrenPadding: const EdgeInsets.fromLTRB(
            AppSpace.md,
            0,
            AppSpace.md,
            AppSpace.md,
          ),
          // %는 여기서만 적는다. 목록 카드에서는 막대 폭이 그 정보를 담는다.
          title: PillarBar(
            pillar: pillar,
            value: value,
            weight: weight,
            showWeight: true,
          ),
          subtitle: Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Row(
              children: [
                Flexible(
                  child: Text(
                    pillarDescriptions[pillar] ?? '',
                    style: text.bodySmall,
                  ),
                ),
                if (estimated) ...[
                  const SizedBox(width: 6),
                  const Chip2('추정', color: AppColors.estimated),
                ],
              ],
            ),
          ),
          children: [
            for (final entry in breakdown.entries)
              Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    SizedBox(
                      width: 130,
                      child: Text(
                        entry.key,
                        style: text.labelMedium?.copyWith(color: color),
                      ),
                    ),
                    Expanded(
                      child: Text('${entry.value}', style: text.bodySmall),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _StageLink extends StatelessWidget {
  final Stage stage;
  final Track track;
  final bool isFlagship;
  const _StageLink({
    required this.stage,
    required this.track,
    required this.isFlagship,
  });

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final color = AppColors.subjectOn(track.subject, dark);
    return InkWell(
      borderRadius: BorderRadius.circular(AppRadius.sm),
      onTap: () => context.go('/tree'),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
        decoration: BoxDecoration(
          border: Border.all(color: color.withValues(alpha: 0.35)),
          borderRadius: BorderRadius.circular(AppRadius.sm),
          color: color.withValues(alpha: 0.06),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (isFlagship) ...[
              const Icon(Icons.star_rounded, size: 13, color: AppColors.gold),
              const SizedBox(width: 4),
            ],
            Text(
              '${track.title} · ${stage.title}',
              style: TextStyle(
                fontFamily: 'Paperlogy',
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: color,
              ),
            ),
            const SizedBox(width: 6),
            Text(
              stage.gradeLabel,
              style: const TextStyle(
                fontFamily: 'Paperlogy',
                fontSize: 11.5,
                color: AppColors.mist,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _EvidenceTile extends StatelessWidget {
  final Evidence evidence;
  const _EvidenceTile({required this.evidence});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final positive = evidence.sentiment >= 0;
    return Card(
      margin: const EdgeInsets.only(bottom: AppSpace.sm),
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(
          horizontal: AppSpace.md,
          vertical: AppSpace.sm,
        ),
        title: Text(
          evidence.title,
          style: text.titleMedium,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 4),
            Text(evidence.snippet, style: text.bodyMedium, maxLines: 2),
            const SizedBox(height: 6),
            Wrap(
              spacing: 6,
              children: [
                Chip2(evidence.sourceLabel, color: AppColors.slate),
                if (evidence.postedAt != null)
                  Chip2(evidence.postedAt!, color: AppColors.mist),
                Chip2(
                  positive ? '긍정' : '부정',
                  color: positive ? AppColors.verified : AppColors.momentum,
                ),
                Chip2(
                  '신뢰도 ${(evidence.credibility * 100).toStringAsFixed(0)}',
                  color: AppColors.reputation,
                ),
                // 지점을 밝히지 않은 글은 같은 브랜드 지점 여럿에 함께
                // 반영된다. 밝히지 않으면 '중복'으로 읽힌다.
                if (evidence.isBrandWide)
                  const Chip2('지점 불명 · 브랜드 공통', color: AppColors.mist),
              ],
            ),
          ],
        ),
        trailing: const Icon(Icons.open_in_new, size: 16),
        onTap: () {
          final uri = Uri.tryParse(evidence.url);
          if (uri != null && (uri.scheme == 'http' || uri.scheme == 'https')) {
            launchUrl(uri, mode: LaunchMode.externalApplication);
          }
        },
      ),
    );
  }
}

class _CorrectionNotice extends StatelessWidget {
  final String academyKey;
  final String academyName;
  const _CorrectionNotice({
    required this.academyKey,
    required this.academyName,
  });

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Card(
      color: AppColors.estimated.withValues(alpha: 0.07),
      child: Padding(
        padding: const EdgeInsets.all(AppSpace.md),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Icon(
              Icons.gavel_outlined,
              size: 18,
              color: AppColors.estimated,
            ),
            const SizedBox(width: AppSpace.sm),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('학원 운영자이신가요?', style: text.titleMedium),
                  const SizedBox(height: 4),
                  Text(
                    '표시된 정보에 사실과 다른 부분이 있다면 정정을 요청하실 수 있습니다. '
                    '접수되면 해당 항목에 "검토 중" 표시가 붙고, 7일 이내에 처리 결과를 회신합니다.',
                    style: text.bodyMedium,
                  ),
                  const SizedBox(height: AppSpace.sm),
                  OutlinedButton.icon(
                    onPressed: () => showModalBottomSheet<void>(
                      context: context,
                      isScrollControlled: true,
                      showDragHandle: true,
                      constraints: const BoxConstraints(maxWidth: 640),
                      builder: (_) => _CorrectionSheet(
                        academyKey: academyKey,
                        academyName: academyName,
                      ),
                    ),
                    icon: const Icon(Icons.edit_note, size: 16),
                    label: const Text('정정 요청하기'),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 정정 요청 접수 시트.
///
/// 로그인 없이 받는다. 항목은 최소한으로 — 무엇이 틀렸고(내용),
/// 누구시고(성함·직함), 어디로 회신하면 되는지(연락처)면 충분하다.
/// 단계 하나의 진입·통과 기준.
///
/// 등급반별 난이도를 커뮤니티 언급에서 만들어 보려 했지만 표본이
/// 186건뿐이었고 광고글이 섞여 기초반이 최상위반보다 어렵게 나왔다.
/// 대신 사람이 정리한 이 기준을 보여준다 — 무엇을 통과해야 하는지가
/// 분명하고, 출처를 설명할 수 있다.
class _StageCriteria extends StatelessWidget {
  final Stage stage;
  const _StageCriteria({required this.stage});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Card(
      margin: const EdgeInsets.only(bottom: AppSpace.sm),
      child: Padding(
        padding: const EdgeInsets.all(AppSpace.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(width: 3, height: 14, color: AppColors.navyBright),
                const SizedBox(width: 7),
                Text(stage.title, style: text.titleMedium),
                const SizedBox(width: 6),
                Chip2(stage.gradeLabel, color: AppColors.slate),
              ],
            ),
            if (stage.goal != null) ...[
              const SizedBox(height: 5),
              Text('목표 · ${stage.goal}', style: text.bodyMedium),
            ],
            const SizedBox(height: 3),
            Text(
              '다음 단계 기준 · ${stage.exitCriteria}',
              style: text.bodyMedium?.copyWith(color: AppColors.navy),
            ),
          ],
        ),
      ),
    );
  }
}

/// 순위 추이.
///
/// 화면의 상승·보합 화살표는 언급량 추세일 뿐 순위 변동이 아니다.
/// 학부모가 궁금해하는 '지난주보다 올랐나'는 이쪽이다.
///
/// 과거 이력이 없어 집계 시작일부터 쌓는다. 지어낸 과거를 채우지 않고,
/// 언제부터의 이야기인지 화면에 그대로 밝힌다.
class _RankTrend extends ConsumerWidget {
  final String academyId;
  final String region;
  const _RankTrend({required this.academyId, required this.region});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final hist = ref.watch(historyProvider).value;
    if (hist == null) return const SizedBox.shrink();
    final points = hist.forAcademy(academyId);
    if (points.isEmpty) return const SizedBox.shrink();

    final first = points.first, last = points.last;
    final moved = (first.rank != null && last.rank != null)
        ? first.rank! -
              last.rank! // 양수면 순위가 올라간 것
        : null;
    final since = points.first.day;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SectionHeader(
          '$region 순위 추이',
          subtitle:
              '${since.year}.${since.month}.${since.day} 집계 시작 이후. '
              '이전 기록은 없습니다 — 과거 순위를 만들어 넣지 않습니다.',
        ),
        if (moved != null && moved != 0)
          Padding(
            padding: const EdgeInsets.only(bottom: 6),
            child: Row(
              children: [
                Icon(
                  moved > 0 ? Icons.arrow_upward : Icons.arrow_downward,
                  size: 15,
                  color: moved > 0 ? AppColors.rising : AppColors.falling,
                ),
                const SizedBox(width: 4),
                Text(
                  '${moved.abs()}계단 ${moved > 0 ? "상승" : "하락"}',
                  style: text.titleMedium?.copyWith(
                    color: moved > 0 ? AppColors.rising : AppColors.falling,
                  ),
                ),
                const SizedBox(width: AppSpace.sm),
                Text(
                  '현재 ${last.rank}위 · 트리스코어 ${last.total}',
                  style: text.bodyMedium,
                ),
              ],
            ),
          ),
        RankHistoryChart(points: points),
      ],
    );
  }
}

/// 레벨테스트 일정.
///
/// 학원 공지와 학부모 제보를 구분해 표시한다 — 확실성이 다른 정보를
/// 섞어 '일정'이라 부르면 헛걸음의 책임이 우리에게 온다.
/// 일정이 없으면 섹션 자체를 내지 않는다. 빈 칸은 정보가 아니다.
class _LevelTests extends ConsumerWidget {
  final String academyKey;
  const _LevelTests({required this.academyKey});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(levelTestsProvider(academyKey));
    final rows = async.value ?? const [];
    if (rows.isEmpty) return const SizedBox.shrink();
    final text = Theme.of(context).textTheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SectionHeader(
          '레벨테스트 일정',
          subtitle:
              '학원 공지와 학부모 제보를 구분해 표시합니다. '
              '제보는 확인 전이므로 방문 전 학원에 확인하세요.',
        ),
        for (final t in rows)
          Card(
            margin: const EdgeInsets.only(bottom: AppSpace.sm),
            child: Padding(
              padding: const EdgeInsets.all(AppSpace.md),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(
                    Icons.event_outlined,
                    size: 18,
                    color: t.official
                        ? AppColors.verified
                        : AppColors.estimated,
                  ),
                  const SizedBox(width: AppSpace.sm),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Text(t.whenLabel, style: text.titleMedium),
                            const SizedBox(width: 6),
                            Chip2(
                              t.official ? '학원 공지' : '학부모 제보',
                              color: t.official
                                  ? AppColors.verified
                                  : AppColors.estimated,
                            ),
                          ],
                        ),
                        if (t.targetBand != null || t.subject != null)
                          Text(
                            [
                              if (t.targetBand != null)
                                gradeBandNames[t.targetBand] ?? '',
                              if (t.subject != null)
                                subjectNames[t.subject] ?? '',
                            ].where((x) => x.isNotEmpty).join(' · '),
                            style: text.bodySmall,
                          ),
                        if (t.detail != null && t.detail!.isNotEmpty)
                          Text(t.detail!, style: text.bodyMedium),
                        if (t.applyUntil != null)
                          Text(
                            '접수 마감 ${t.applyUntil!.month}월 ${t.applyUntil!.day}일',
                            style: text.bodySmall?.copyWith(
                              color: AppColors.rising,
                            ),
                          ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        const SizedBox(height: AppSpace.xl),
      ],
    );
  }
}

class _CorrectionSheet extends ConsumerStatefulWidget {
  final String academyKey;
  final String academyName;
  const _CorrectionSheet({required this.academyKey, required this.academyName});

  @override
  ConsumerState<_CorrectionSheet> createState() => _CorrectionSheetState();
}

class _CorrectionSheetState extends ConsumerState<_CorrectionSheet> {
  final _requester = TextEditingController();
  final _contact = TextEditingController();
  final _message = TextEditingController();
  String _kind = 'fix';
  bool _sending = false;
  String? _error;

  @override
  void dispose() {
    _requester.dispose();
    _contact.dispose();
    _message.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final service = ref.read(correctionServiceProvider);
    if (_message.text.trim().length < 10) {
      setState(() => _error = '정정하실 내용을 10자 이상 적어 주세요.');
      return;
    }
    if (_contact.text.trim().length < 5) {
      setState(() => _error = '회신받으실 연락처를 입력해 주세요.');
      return;
    }
    setState(() {
      _sending = true;
      _error = null;
    });
    try {
      await service.submit(
        academyKey: widget.academyKey,
        academyName: widget.academyName,
        requester: _requester.text.trim().isEmpty
            ? '미기재'
            : _requester.text.trim(),
        contact: _contact.text.trim(),
        kind: _kind,
        message: _message.text.trim(),
      );
      if (!mounted) return;
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('접수되었습니다. 검토 후 연락처로 회신드립니다.')),
      );
    } catch (_) {
      if (mounted) {
        setState(() {
          _sending = false;
          _error = '접수에 실패했습니다. 잠시 후 다시 시도해 주세요.';
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final enabled = ref.watch(correctionServiceProvider).enabled;

    return Padding(
      padding: EdgeInsets.only(
        left: AppSpace.md,
        right: AppSpace.md,
        bottom: MediaQuery.viewInsetsOf(context).bottom + AppSpace.lg,
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('${widget.academyName} — 정보 정정 요청', style: text.titleLarge),
            const SizedBox(height: 4),
            Text(
              '접수 내용은 공개되지 않으며, 운영자 검토 후 데이터에 반영됩니다.',
              style: text.bodySmall,
            ),
            const SizedBox(height: AppSpace.md),
            if (!enabled)
              Text('현재 접수 기능을 사용할 수 없습니다.', style: text.bodyMedium)
            else ...[
              Wrap(
                spacing: AppSpace.sm,
                children: [
                  for (final (v, label) in const [
                    ('fix', '정보가 틀렸어요'),
                    ('claim', '학원 관계자입니다'),
                    ('remove', '삭제를 요청합니다'),
                  ])
                    ChoiceChip(
                      label: Text(label),
                      selected: _kind == v,
                      onSelected: (_) => setState(() => _kind = v),
                    ),
                ],
              ),
              const SizedBox(height: AppSpace.md),
              TextField(
                controller: _message,
                maxLines: 4,
                maxLength: 4000,
                decoration: const InputDecoration(
                  border: OutlineInputBorder(),
                  labelText: '어떤 정보가 어떻게 잘못되었나요? *',
                  helperText: '예: 정원이 변경되었습니다. 현재 80명입니다.',
                ),
              ),
              const SizedBox(height: AppSpace.sm),
              TextField(
                controller: _requester,
                decoration: const InputDecoration(
                  border: OutlineInputBorder(),
                  labelText: '성함 · 직함 (선택)',
                ),
              ),
              const SizedBox(height: AppSpace.sm),
              TextField(
                controller: _contact,
                decoration: const InputDecoration(
                  border: OutlineInputBorder(),
                  labelText: '회신받으실 연락처 (이메일 또는 전화) *',
                ),
              ),
              if (_error != null) ...[
                const SizedBox(height: AppSpace.sm),
                Text(
                  _error!,
                  style: text.bodySmall?.copyWith(color: AppColors.rising),
                ),
              ],
              const SizedBox(height: AppSpace.md),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: _sending ? null : _submit,
                  child: Text(_sending ? '접수 중…' : '정정 요청 접수'),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _Row extends StatelessWidget {
  final String label;
  final String value;
  const _Row(this.label, this.value);

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 7),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 88,
          child: Text(label, style: Theme.of(context).textTheme.labelMedium),
        ),
        Expanded(
          child: Text(value, style: Theme.of(context).textTheme.bodyLarge),
        ),
      ],
    ),
  );
}
