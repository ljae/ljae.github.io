import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme.dart';
import '../../data/models.dart';
import '../../data/repository.dart';
import '../../widgets/academy_card.dart';
import '../../widgets/common.dart';
import 'graph_view.dart';

class TechTreePage extends ConsumerWidget {
  const TechTreePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(dataProvider);
    final sel = ref.watch(selectionProvider);

    return async.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text('데이터를 불러오지 못했습니다\n$e')),
      data: (data) {
        final track = data.trackById[sel.trackId];
        return Column(children: [
          _Filters(data: data),
          const Divider(height: 1),
          Expanded(
            child: track == null
                ? const Center(child: Text('해당 과목·학교급 트랙이 없습니다'))
                : _TrackBody(track: track, data: data, regionId: sel.regionId),
          ),
        ]);
      },
    );
  }
}

class _Filters extends ConsumerWidget {
  final EduTreeData data;
  const _Filters({required this.data});

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
                for (final e in subjectNames.entries)
                  if (e.key != 'etc') (e.key, e.value),
              ],
              selected: sel.subject,
              onChanged: notifier.setSubject,
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
    return Column(children: [
      Padding(
        padding: const EdgeInsets.symmetric(
            horizontal: AppSpace.lg, vertical: AppSpace.md),
        child: Row(children: [
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('${data.regionById[regionId]?.nameKo ?? ""} · ${track.title}',
                  style: text.headlineMedium),
              const SizedBox(height: 3),
              Text(track.summary, style: text.bodyMedium),
            ]),
          ),
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
            onStageTap: (stage) => _openStage(context, stage, data, regionId),
          ),
        ),
      ),
    ]);
  }

  void _openStage(
      BuildContext context, Stage stage, EduTreeData data, String regionId) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      constraints: const BoxConstraints(maxWidth: 720),
      builder: (_) => _StageSheet(stage: stage, data: data, regionId: regionId),
    );
  }
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
