import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/theme.dart';
import '../../data/models.dart';
import '../../data/repository.dart';
import '../../widgets/common.dart';

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
    final stages =
        academy.stages.map((s) => data.stageById[s]).whereType<Stage>().toList();

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
                  ScoreDial(score.total, size: 92),
                  ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 560),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(academy.displayName, style: text.displayMedium),
                        const SizedBox(height: AppSpace.sm),
                        Wrap(spacing: 6, runSpacing: 6, children: [
                          if (region != null)
                            Chip2(region.nameKo, color: AppColors.navy),
                          for (final s in academy.subjects)
                            Chip2(subjectNames[s] ?? s,
                                color: AppColors.subjects[s] ?? AppColors.slate),
                          VerifiedChip(verified: academy.isVerified),
                          ConfidenceChip(score: score),
                          if (score.rankInRegion != null)
                            Chip2(
                                '${region?.nameKo ?? ""} ${score.rankInRegion}위'
                                '${score.regionRankedCount != null ? " / ${score.regionRankedCount}곳" : ""}',
                                color: AppColors.gold),
                        ]),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AppSpace.xl),

              // ── 기둥별 점수 ─────────────────────────────────
              SectionHeader('점수 구성',
                  subtitle: '각 기둥의 계산 근거를 펼쳐 볼 수 있습니다'),
              for (final key in pillarNames.keys)
                _PillarPanel(
                  pillar: key,
                  value: score.pillar(key),
                  weight: data.meta.weights[key] ?? 0,
                  breakdown: (score.breakdown[key] as Map?)
                          ?.cast<String, dynamic>() ??
                      const {},
                ),
              const SizedBox(height: AppSpace.xl),

              // ── 공식 정보 ──────────────────────────────────
              SectionHeader('공식 등록 정보',
                  subtitle: academy.isVerified
                      ? 'NEIS 학원교습소정보 공시 기준 — 검증된 사실입니다'
                      : '샘플 데이터입니다. 실제 공시값이 아닙니다.'),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(AppSpace.md),
                  child: Column(children: [
                    if (academy.registrationCount > 1)
                      _Row('등록 건수',
                          '${academy.registrationCount}건 (관·과정별 등록을 한 학원으로 묶음)'),
                    _Row('등록상태', academy.registrationStatus ?? '—'),
                    _Row('교습비', academy.tuitionRaw ?? '미공개'),
                    _Row('정원', academy.capacity != null ? '${academy.capacity}명' : '—'),
                    _Row('개설일', academy.establishedOn ?? '—'),
                    _Row('주소', academy.address ?? '—'),
                    if (academy.tel != null) _Row('전화', academy.tel!),
                  ]),
                ),
              ),
              const SizedBox(height: AppSpace.xl),

              // ── 테크트리 위치 ───────────────────────────────
              if (stages.isNotEmpty) ...[
                SectionHeader('테크트리에서의 위치',
                    subtitle: '이 학원이 담당하는 단계입니다'),
                Wrap(
                  spacing: AppSpace.sm,
                  runSpacing: AppSpace.sm,
                  children: [
                    for (final s in stages)
                      _StageLink(
                          stage: s,
                          track: data.trackById[s.trackId]!,
                          isFlagship: academy.isFlagshipOf(s.id)),
                  ],
                ),
                const SizedBox(height: AppSpace.xl),
              ],

              // ── 근거 ───────────────────────────────────────
              SectionHeader('평판 점수에 반영된 근거',
                  subtitle: '신뢰도 상위 게시물입니다. 원문 링크로만 제공하며 본문을 전재하지 않습니다.'),
              if (academy.evidence.isEmpty)
                Text('표시할 근거가 없습니다.', style: text.bodyMedium)
              else
                for (final e in academy.evidence) _EvidenceTile(evidence: e),

              const SizedBox(height: AppSpace.xl),
              const _CorrectionNotice(),
              const SizedBox(height: AppSpace.xxl),
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
              AppSpace.md, 0, AppSpace.md, AppSpace.md),
          title: PillarBar(pillar: pillar, value: value, weight: weight),
          subtitle: Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Row(children: [
              Flexible(
                  child: Text(pillarDescriptions[pillar] ?? '',
                      style: text.bodySmall)),
              if (estimated) ...[
                const SizedBox(width: 6),
                const Chip2('추정', color: AppColors.estimated),
              ],
            ]),
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
                      child: Text(entry.key,
                          style: text.labelMedium?.copyWith(color: color)),
                    ),
                    Expanded(
                        child: Text('${entry.value}', style: text.bodySmall)),
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
  const _StageLink(
      {required this.stage, required this.track, required this.isFlagship});

  @override
  Widget build(BuildContext context) {
    final color = AppColors.subjects[track.subject] ?? AppColors.navy;
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
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          if (isFlagship) ...[
            const Icon(Icons.star_rounded, size: 13, color: AppColors.gold),
            const SizedBox(width: 4),
          ],
          Text('${track.title} · ${stage.title}',
              style: TextStyle(
                fontFamily: 'Paperlogy',
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: color,
              )),
          const SizedBox(width: 6),
          Text(stage.gradeLabel,
              style: const TextStyle(
                  fontFamily: 'Paperlogy',
                  fontSize: 11.5,
                  color: AppColors.mist)),
        ]),
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
            horizontal: AppSpace.md, vertical: AppSpace.sm),
        title: Text(evidence.title,
            style: text.titleMedium, maxLines: 1, overflow: TextOverflow.ellipsis),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 4),
            Text(evidence.snippet, style: text.bodyMedium, maxLines: 2),
            const SizedBox(height: 6),
            Wrap(spacing: 6, children: [
              Chip2(evidence.sourceLabel, color: AppColors.slate),
              if (evidence.postedAt != null)
                Chip2(evidence.postedAt!, color: AppColors.mist),
              Chip2(positive ? '긍정' : '부정',
                  color: positive ? AppColors.verified : AppColors.momentum),
              Chip2('신뢰도 ${(evidence.credibility * 100).toStringAsFixed(0)}',
                  color: AppColors.reputation),
            ]),
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
  const _CorrectionNotice();

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Card(
      color: AppColors.estimated.withValues(alpha: 0.07),
      child: Padding(
        padding: const EdgeInsets.all(AppSpace.md),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Icon(Icons.gavel_outlined, size: 18, color: AppColors.estimated),
          const SizedBox(width: AppSpace.sm),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('학원 운영자이신가요?', style: text.titleMedium),
              const SizedBox(height: 4),
              Text(
                '표시된 정보에 사실과 다른 부분이 있다면 정정을 요청하실 수 있습니다. '
                '접수되면 해당 항목에 "검토 중" 표시가 붙고, 7일 이내에 처리 결과를 회신합니다.',
                style: text.bodyMedium,
              ),
              const SizedBox(height: AppSpace.sm),
              OutlinedButton.icon(
                onPressed: () => context.go('/method#correction'),
                icon: const Icon(Icons.edit_note, size: 16),
                label: const Text('정정 요청하기'),
              ),
            ]),
          ),
        ]),
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
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          SizedBox(
              width: 88,
              child: Text(label,
                  style: Theme.of(context).textTheme.labelMedium)),
          Expanded(
              child: Text(value,
                  style: Theme.of(context).textTheme.bodyLarge)),
        ]),
      );
}
