import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme.dart';
import '../../data/models.dart';
import '../../data/repository.dart';
import '../../widgets/academy_card.dart';
import '../../widgets/common.dart';
import 'graph_view.dart';
import 'roadmap_view.dart';

/// 테크트리 화면.
///
/// 기본 얼굴은 통합 로드맵이다 — 5세 영어 → 6세 수학 → 7세 국어 →
/// 초4 재편으로 이어지는 전체 흐름을 먼저 보여주고, 과목을 고르면
/// 그 과목·구간의 상세 트리로 들어간다. 전체를 먼저, 상세는 선택.
class TechTreePage extends ConsumerStatefulWidget {
  const TechTreePage({super.key});

  @override
  ConsumerState<TechTreePage> createState() => _TechTreePageState();
}

class _TechTreePageState extends ConsumerState<TechTreePage> {
  bool _showRoadmap = true;

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(dataProvider);
    final sel = ref.watch(selectionProvider);

    return async.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text('데이터를 불러오지 못했습니다\n$e')),
      data: (data) {
        final track = data.trackById[sel.trackId];
        return Column(children: [
          _Filters(
            showRoadmap: _showRoadmap,
            onChanged: (v) => setState(() => _showRoadmap = v),
          ),
          const Divider(height: 1),
          Expanded(
            child: _showRoadmap
                ? ContentWidth(
                    max: 1400,
                    child:
                        RoadmapView(data: data, regionId: sel.regionId))
                : track == null
                    ? const Center(child: Text('해당 과목·학년 구간 트랙이 없습니다'))
                    : _TrackBody(
                        track: track, data: data, regionId: sel.regionId),
          ),
        ]);
      },
    );
  }
}

class _Filters extends ConsumerWidget {
  final bool showRoadmap;
  final ValueChanged<bool> onChanged;
  const _Filters({required this.showRoadmap, required this.onChanged});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final sel = ref.watch(selectionProvider);
    final notifier = ref.read(selectionProvider.notifier);

    return Container(
      padding: const EdgeInsets.symmetric(vertical: AppSpace.md),
      color: Theme.of(context).brightness == Brightness.dark
          ? AppColors.darkSurface
          : AppColors.surface,
      child: ContentWidth(
        max: 1400,
        child: Row(children: [
          Expanded(
            child: ChipRow<String>(
              options: [
                ('roadmap', '전체 로드맵'),
                for (final e in subjectNames.entries)
                  if (e.key != 'etc') (e.key, e.value),
              ],
              selected: showRoadmap ? 'roadmap' : sel.subject,
              onChanged: (v) {
                if (v == 'roadmap') {
                  onChanged(true);
                } else {
                  notifier.setSubject(v);
                  onChanged(false);
                }
              },
            ),
          ),
        ]),
      ),
    );
  }
}

class _TrackBody extends StatelessWidget {
  final Track track;
  final EduTreeData data;
  final String regionId;
  const _TrackBody(
      {required this.track, required this.data, required this.regionId});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    // 좁은 화면에서는 제목·설명 옆에 범례를 둘 자리가 없다. 예전에는
    // 범례(Wrap)가 폭 제한 없이 옆에 붙어 설명 위로 겹쳐 그려졌다.
    final narrow = MediaQuery.sizeOf(context).width < 720;
    final heading = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('${data.regionById[regionId]?.nameKo ?? ""} · ${track.title}',
            style: narrow
                ? text.titleLarge?.copyWith(fontWeight: FontWeight.w800)
                : text.headlineMedium),
        const SizedBox(height: 3),
        Text(track.summary, style: text.bodyMedium),
      ],
    );

    return Column(children: [
      Padding(
        padding: const EdgeInsets.symmetric(
            horizontal: AppSpace.lg, vertical: AppSpace.md),
        child: narrow
            ? Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                heading,
                const SizedBox(height: AppSpace.sm),
                const _Legend(),
              ])
            : Row(children: [
          Expanded(child: heading),
          const _Legend(),
        ]),
      ),
      Expanded(
        child: Container(
          width: double.infinity,
          decoration: BoxDecoration(
            color: Theme.of(context).brightness == Brightness.dark
                ? const Color(0xFF0A0F14)
                : const Color(0xFFEFF3F1),
          ),
          child: TechTreeGraph(
            track: track,
            data: data,
            regionId: regionId,
            onStageTap: (stage) => showStageSheet(context, stage, data, regionId),
          ),
        ),
      ),
    ]);
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

class _Legend extends StatelessWidget {
  const _Legend();
  @override
  Widget build(BuildContext context) {
    Widget item(Color color, String label, bool dashed) => Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 16,
              height: 2,
              decoration: BoxDecoration(
                color: dashed ? null : color,
                border: dashed
                    ? Border(top: BorderSide(color: color, width: 2, style: BorderStyle.solid))
                    : null,
              ),
            ),
            const SizedBox(width: 5),
            Text(label, style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(width: AppSpace.md),
          ],
        );

    return Wrap(children: [
      item(AppColors.navyBright, '일반 경로', false),
      item(AppColors.mist, '우회 경로', true),
      item(AppColors.gold, '속진', false),
    ]);
  }
}

class _StageSheet extends StatelessWidget {
  final Stage stage;
  final EduTreeData data;
  final String regionId;
  const _StageSheet(
      {required this.stage, required this.data, required this.regionId});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final track = data.trackById[stage.trackId]!;
    final accent = AppColors.subjects[track.subject] ?? AppColors.navy;
    final academies = data.academiesForStage(stage.id, regionId: regionId);
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
          SectionHeader('이 단계의 학원 ${academies.length}곳',
              subtitle: '${data.regionById[regionId]?.nameKo ?? ""} 기준 · 트리스코어 순'),
          if (academies.isEmpty)
            Text('이 학군에는 등록된 학원이 없습니다.', style: text.bodyMedium)
          else
            for (final a in academies)
              AcademyCard(
                  academy: a, showPillars: false, stageContext: stage.id),
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
