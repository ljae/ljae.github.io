import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme.dart';
import '../../data/models.dart';
import '../../data/repository.dart';
import '../../widgets/academy_card.dart';
import '../../widgets/annals.dart';
import '../../widgets/common.dart';
import 'roadmap_view.dart';

/// 테크트리 화면 — 나이 × 과목 로드맵 하나.
///
/// 한때 같은 그래프를 '과목 축'과 '목적성 축' 두 판으로 나눠 보여줬다.
/// 없앴다. 목적지를 고르는 일은 로드맵 자신이 이미 하고 있고
/// (`_destinationBar`), 고르면 그 길이 판 위에서 밝아진다. 같은 선택을
/// 두 곳에 두면 **어느 쪽이 진짜인지**가 흐려지고, 판을 하나 더 유지하는
/// 값은 계속 나간다. 목적지는 축이 아니라 이 판의 **조명**이다.
///
/// 과목·구간별 트리를 따로 두었던 것을 없앤 판단과 같은 줄기다 —
/// 같은 정보를 두 벌로 유지하면 한쪽만 고쳐진다.
class TechTreePage extends ConsumerWidget {
  const TechTreePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(dataProvider);
    final sel = ref.watch(selectionProvider);

    return async.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text('데이터를 불러오지 못했습니다\n$e')),
      data: (data) => ContentWidth(
        max: 1400,
        child: RoadmapView(data: data, regionId: sel.regionId),
      ),
    );
  }
}

/// 단계 상세 시트. 트리와 통합 로드맵이 같은 시트를 쓴다 —
/// 같은 단계가 화면마다 다른 얼굴을 하면 사용자가 길을 잃는다.
void showStageSheet(
    BuildContext context, Stage stage, EduTreeData data, String regionId) {
  showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    constraints: const BoxConstraints(maxWidth: 720),
    builder: (_) => _StageSheet(stage: stage, data: data, regionId: regionId),
  );
}

class _StageSheet extends ConsumerWidget {
  final Stage stage;
  final EduTreeData data;
  final String regionId;
  const _StageSheet(
      {required this.stage, required this.data, required this.regionId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final track = data.trackById[stage.trackId]!;
    final accent = AppColors.subjectOn(
        track.subject, Theme.of(context).brightness == Brightness.dark);
    // 목록이 한두 곳이면 '이 단계에 어떤 학원이 있나'에 답하지 못한다.
    // 근거가 있는 곳을 먼저 다 보여주고, 모자라면 같은 과목·구간까지
    // 넓혀 채운다. 이어 붙인 곳은 카드에 그렇게 적힌다.
    final matches =
        data.academiesForStage(stage.id, regionId: regionId, fillTo: 8);
    final direct = matches.where((m) => m.isDirect).toList();
    final nearby = matches.where((m) => !m.isDirect).toList();
    final dests = data.destinationsForStage(stage.id);
    final incoming =
        track.edges.where((e) => e.to == stage.id && e.condition.isNotEmpty);
    final outgoing =
        track.edges.where((e) => e.from == stage.id && e.condition.isNotEmpty);

    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.7,
      maxChildSize: 0.94,
      builder: (context, controller) => ListView(
        controller: controller,
        padding: const EdgeInsets.fromLTRB(
            AppSpace.lg, 0, AppSpace.lg, AppSpace.xl),
        children: [
          Row(children: [
            Chip2(stage.gradeLabel, color: accent, filled: true),
            const SizedBox(width: AppSpace.sm),
            Chip2(track.title, color: accent),
          ]),
          const SizedBox(height: AppSpace.sm),
          Text(stage.title, style: text.headlineLarge),
          if (stage.subtitle != null)
            Text(stage.subtitle!, style: text.bodyMedium),
          if (dests.isNotEmpty) ...[
            const SizedBox(height: AppSpace.md),
            // 목적지 → 단계만 있으면 로드맵에서 단계를 눌렀을 때 '이건
            // 어디로 이어지나'에 답하지 못한다. **엣지는 양쪽에서 읽을 수
            // 있어야 한다** — 글과 학원을 양쪽에서 잇는 것과 같은 이유다.
            Text('이 단계를 지나는 길', style: text.labelMedium),
            const SizedBox(height: 4),
            Wrap(
              spacing: AppSpace.sm,
              runSpacing: 4,
              children: [
                for (final d in dests)
                  InkWell(
                    onTap: () {
                      // 고르고 시트를 닫는다. 돌아간 판에 그 길이 밝혀져
                      // 있어야 '이 단계가 그 길의 어디쯤인지'가 보인다.
                      ref.read(destinationProvider.notifier).select(d.id);
                      Navigator.of(context).maybePop();
                    },
                    child: TagMark(
                      d.label,
                      color: AppColors.accentOn(
                          Theme.of(context).brightness == Brightness.dark),
                    ),
                  ),
              ],
            ),
          ],
          const SizedBox(height: AppSpace.lg),
          if (stage.goal != null)
            _Field(icon: Icons.flag_outlined, label: '이 단계의 목표', value: stage.goal!),
          if (stage.exitCriteria != null)
            _Field(
                icon: Icons.checklist_rtl,
                label: '다음 단계로 넘어가는 기준',
                value: stage.exitCriteria!),
          for (final e in incoming)
            _Field(
                icon: Icons.login,
                label: '${data.stageById[e.from]?.title ?? ""} 에서 진입',
                value: e.condition),
          for (final e in outgoing)
            _Field(
                icon: Icons.logout,
                label: '${data.stageById[e.to]?.title ?? ""} 로 진행',
                value: e.condition),
          const SizedBox(height: AppSpace.lg),
          SectionHeader('이 단계의 학원 ${direct.length}곳',
              subtitle: '${data.regionById[regionId]?.nameKo ?? ""} 기준 · 트리스코어 순'),
          if (direct.isEmpty)
            Text(
                '이 단계를 담당한다고 볼 근거가 있는 학원이 아직 없습니다.'
                '${nearby.isEmpty ? "" : " 같은 구간의 학원을 아래에 이어 둡니다."}',
                style: text.bodyMedium)
          else
            for (final m in direct)
              AcademyCard(
                  academy: m.academy,
                  showPillars: false,
                  stageContext: stage.id,
                  // 단계는 과목에 매인다. 대표 점수를 쓰면 수학 후기로
                  // 얻은 점수가 과학 단계 목록에 그대로 선다.
                  subject: track.subject,
                  stageBasis: m.basis),
          if (nearby.isNotEmpty) ...[
            const SizedBox(height: AppSpace.lg),
            // 이 단계 근거가 없는 곳이다. 위와 같은 제목으로 묶으면
            // 목록은 길어지고 뜻은 흐려진다.
            SectionHeader('같은 구간의 학원 ${nearby.length}곳',
                subtitle: '${track.title} · 이 단계를 특정할 근거는 없습니다'),
            for (final m in nearby)
              AcademyCard(
                  academy: m.academy,
                  showPillars: false,
                  stageContext: stage.id,
                  subject: track.subject,
                  stageBasis: m.basis),
          ],
        ],
      ),
    );
  }
}

class _Field extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  const _Field(
      {required this.icon, required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpace.md),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Icon(icon, size: 16, color: AppColors.mist),
        const SizedBox(width: AppSpace.sm),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(label, style: text.labelMedium),
            const SizedBox(height: 2),
            Text(value, style: text.bodyLarge),
          ]),
        ),
      ]),
    );
  }
}
