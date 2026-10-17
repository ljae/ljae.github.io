import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme.dart';
import '../../../data/admin.dart';
import '../../../data/growth.dart';
import '../../../widgets/common.dart';
import '../../../widgets/content_loading.dart';

const growthStateLabels = {
  'proposed': '제안',
  'ready': '준비됨',
  'in_progress': '진행 중',
  'deployed': '배포됨',
  'observing': '관찰 중',
  'verified': '검증됨',
  'deferred': '보류',
  'rejected': '반려',
  'inconclusive': '판정 보류',
  'rolled_back': '복귀됨',
};
const growthTransitions = {
  'proposed': ['ready', 'deferred', 'rejected'],
  'ready': ['in_progress', 'deferred', 'rejected'],
  'in_progress': ['deployed', 'deferred'],
  'deployed': ['observing', 'rolled_back'],
  'observing': ['verified', 'inconclusive', 'rolled_back'],
  'deferred': ['ready', 'rejected'],
  'rolled_back': ['ready'],
  'inconclusive': ['observing', 'ready'],
  'verified': ['ready'],
};

class GrowthPage extends ConsumerStatefulWidget {
  const GrowthPage({super.key});
  @override
  ConsumerState<GrowthPage> createState() => _GrowthPageState();
}

class _GrowthPageState extends ConsumerState<GrowthPage> {
  int _tab = 0;
  String? _snapshot;
  int _taskPage = 0;

  @override
  Widget build(BuildContext context) {
    final service = ref.watch(adminServiceProvider);
    final admin = ref.watch(growthAccessProvider);
    if (!service.enabled || !service.signedIn) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('검색 분석은 운영자 로그인 후 사용할 수 있습니다.'),
            TextButton(
              onPressed: () => context.go('/admin'),
              child: const Text('운영자 로그인'),
            ),
          ],
        ),
      );
    }
    if (admin.isLoading) return const ContentLoading();
    if (admin.value != true) return const Center(child: Text('운영자 권한이 필요합니다.'));
    return ListView(
      padding: const EdgeInsets.symmetric(vertical: AppSpace.lg),
      children: [
        ContentWidth(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SectionHeader(
                '검색 성장',
                subtitle: '노출 변화와 유입 동선을 확인하고, 근거가 있는 개선 과제를 추적합니다.',
              ),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final (i, label) in [
                    (0, '현황·페이지'),
                    (1, '개선 과제'),
                    (2, '실험'),
                  ])
                    ChoiceChip(
                      label: Text(label),
                      selected: _tab == i,
                      onSelected: (_) => setState(() => _tab = i),
                    ),
                  IconButton(
                    tooltip: '최신 자료 다시 읽기',
                    onPressed: () {
                      ref.invalidate(growthReportsProvider);
                      ref.invalidate(growthOverviewProvider);
                      ref.invalidate(growthTasksProvider(_taskPage));
                      ref.invalidate(growthExperimentsProvider);
                    },
                    icon: const Icon(Icons.refresh),
                  ),
                ],
              ),
              const SizedBox(height: AppSpace.lg),
              if (_tab == 0)
                _overview()
              else if (_tab == 1)
                _tasks()
              else
                _experiments(),
            ],
          ),
        ),
      ],
    );
  }

  Widget _error(Object error) => Card(
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('검색 분석 자료를 불러오지 못했습니다.'),
          const Text('수집 연결과 분석 데이터베이스 적용 상태를 확인한 뒤 다시 읽어 주세요.'),
          TextButton(
            onPressed: () => showDialog<void>(
              context: context,
              builder: (_) => AlertDialog(
                title: const Text('연결 상태'),
                content: SelectableText('$error'),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('닫기'),
                  ),
                ],
              ),
            ),
            child: const Text('오류 상세 확인'),
          ),
        ],
      ),
    ),
  );

  Widget _overview() => ref
      .watch(growthReportsProvider)
      .when(
        loading: () => const ContentLoading(),
        error: (e, _) => _error(e),
        data: (reports) {
          if (reports.isEmpty) {
            return const Card(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text(
                  '아직 수입한 검색 자료가 없습니다. CSV 수입 또는 GSC 읽기 전용 수집을 연결해 주세요.',
                ),
              ),
            );
          }
          final id = reports.any((r) => r['id'] == _snapshot)
              ? _snapshot!
              : reports.first['id'] as String;
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              DropdownButtonFormField<String>(
                key: ValueKey(id),
                initialValue: id,
                isExpanded: true,
                decoration: const InputDecoration(labelText: '관측 기간 · 자료 출처'),
                items: [
                  for (final r in reports)
                    DropdownMenuItem(
                      value: r['id'] as String,
                      child: Text(
                        '${r['range_start']} ~ ${r['range_end']} · ${r['source'] == 'gsc_csv' ? 'CSV' : 'API'}',
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                ],
                onChanged: (v) => setState(() => _snapshot = v),
              ),
              const SizedBox(height: 20),
              ref
                  .watch(growthOverviewProvider(id))
                  .when(
                    loading: () => const ContentLoading(),
                    error: (e, _) => _error(e),
                    data: (report) => GrowthOverview(report: report),
                  ),
            ],
          );
        },
      );

  Widget _tasks() => ref
      .watch(growthTasksProvider(_taskPage))
      .when(
        loading: () => const ContentLoading(),
        error: (e, _) => _error(e),
        data: (tasks) => Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (tasks.isEmpty) const Text('이 페이지에 표시할 개선 과제가 없습니다.'),
            for (final t in tasks)
              Card(
                child: ListTile(
                  isThreeLine: true,
                  leading: Text(t['severity'] as String),
                  title: Text(t['title'] as String),
                  subtitle: Text(
                    '${t['subject_key']}\n${growthStateLabels[t['state']] ?? t['state']}',
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => _taskDialog(t),
                ),
              ),
            Row(
              children: [
                TextButton(
                  onPressed: _taskPage == 0
                      ? null
                      : () => setState(() => _taskPage--),
                  child: const Text('이전'),
                ),
                Text(' ${_taskPage + 1} 페이지 '),
                TextButton(
                  onPressed: tasks.length < 25
                      ? null
                      : () => setState(() => _taskPage++),
                  child: const Text('다음'),
                ),
              ],
            ),
          ],
        ),
      );

  Future<void> _taskDialog(Map<String, dynamic> task) async {
    final note = TextEditingController(text: task['note'] as String? ?? '');
    bool busy = false;
    String? error;
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (_, update) => AlertDialog(
          title: Text(task['title'] as String),
          content: SizedBox(
            width: 620,
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    '${task['severity']} · ${growthStateLabels[task['state']]}',
                  ),
                  const SizedBox(height: 12),
                  SelectableText(
                    const JsonEncoder.withIndent(
                      '  ',
                    ).convert(task['evidence']),
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: note,
                    decoration: const InputDecoration(labelText: '진행 메모'),
                    maxLines: 2,
                  ),
                  if (error != null)
                    Text(
                      error!,
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                      ),
                    ),
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      for (final next
                          in growthTransitions[task['state']] ?? <String>[])
                        OutlinedButton(
                          onPressed: busy
                              ? null
                              : () async {
                                  update(() {
                                    busy = true;
                                    error = null;
                                  });
                                  try {
                                    if (next == 'deployed' &&
                                        !await _deployment(
                                          task['id'] as String,
                                        )) {
                                      update(() => busy = false);
                                      return;
                                    }
                                    await ref
                                        .read(growthServiceProvider)
                                        .transition(task, next, note.text);
                                    ref.invalidate(
                                      growthTasksProvider(_taskPage),
                                    );
                                    if (dialogContext.mounted) {
                                      Navigator.pop(dialogContext);
                                    }
                                  } catch (e) {
                                    update(() {
                                      error = '$e';
                                      busy = false;
                                    });
                                  }
                                },
                          child: Text(growthStateLabels[next] ?? next),
                        ),
                    ],
                  ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Clipboard.setData(
                ClipboardData(
                  text: const JsonEncoder.withIndent('  ').convert(task),
                ),
              ),
              child: const Text('구현 명세 복사'),
            ),
            TextButton(
              onPressed: busy ? null : () => Navigator.pop(dialogContext),
              child: const Text('닫기'),
            ),
          ],
        ),
      ),
    );
    note.dispose();
  }

  Future<bool> _deployment(String taskId) async {
    final commit = TextEditingController(),
        deploy = TextEditingController(),
        url = TextEditingController();
    String? error;
    bool busy = false;
    final saved = await showDialog<bool>(
      context: context,
      builder: (c) => StatefulBuilder(
        builder: (_, update) => AlertDialog(
          title: const Text('배포 확인 기록'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: commit,
                decoration: const InputDecoration(labelText: '커밋 SHA'),
              ),
              TextField(
                controller: deploy,
                decoration: const InputDecoration(labelText: '배포 실행 ID'),
              ),
              TextField(
                controller: url,
                decoration: const InputDecoration(labelText: '직접 확인한 운영 URL'),
              ),
              if (error != null) Text(error!),
            ],
          ),
          actions: [
            TextButton(
              onPressed: busy ? null : () => Navigator.pop(c, false),
              child: const Text('취소'),
            ),
            FilledButton(
              onPressed: busy
                  ? null
                  : () async {
                      if (!RegExp(
                            r'^[0-9a-f]{7,40}$',
                          ).hasMatch(commit.text.trim()) ||
                          deploy.text.trim().isEmpty ||
                          !url.text.startsWith('https://openedu4u.com/')) {
                        update(() => error = '커밋·배포 ID·운영 URL을 확인해 주세요.');
                        return;
                      }
                      update(() => busy = true);
                      try {
                        await ref
                            .read(growthServiceProvider)
                            .recordChange(
                              taskId,
                              commit.text.trim(),
                              deploy.text.trim(),
                              url.text.trim(),
                            );
                        if (c.mounted) Navigator.pop(c, true);
                      } catch (e) {
                        update(() {
                          error = '$e';
                          busy = false;
                        });
                      }
                    },
              child: const Text('확인 기록 저장'),
            ),
          ],
        ),
      ),
    );
    commit.dispose();
    deploy.dispose();
    url.dispose();
    return saved == true;
  }

  Widget _experiments() => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      const Text('배포 전 URL 묶음과 가설을 고정합니다. 표본이 부족하면 효과 판정을 보류합니다.'),
      const SizedBox(height: 12),
      OutlinedButton.icon(
        onPressed: _newExperiment,
        icon: const Icon(Icons.add),
        label: const Text('실험 기록'),
      ),
      ref
          .watch(growthExperimentsProvider)
          .when(
            loading: () => const ContentLoading(),
            error: (e, _) => _error(e),
            data: (rows) => Column(
              children: [
                for (final e in rows)
                  Card(
                    child: ExpansionTile(
                      title: Text(e['hypothesis'] as String),
                      subtitle: Text(
                        '${e['verdict']} · 28일 이상 관찰 / 최소 500노출·20클릭',
                      ),
                      children: [
                        Padding(
                          padding: const EdgeInsets.all(16),
                          child: SelectableText(
                            const JsonEncoder.withIndent('  ').convert(e),
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
    ],
  );

  Future<void> _newExperiment() async {
    final hypothesis = TextEditingController(),
        treatment = TextEditingController(),
        control = TextEditingController();
    String? error;
    bool busy = false;
    await showDialog<void>(
      context: context,
      builder: (c) => StatefulBuilder(
        builder: (_, update) => AlertDialog(
          title: const Text('실험 시작 기록'),
          content: SizedBox(
            width: 600,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(
                    controller: hypothesis,
                    decoration: const InputDecoration(labelText: '검증할 가설'),
                    maxLines: 2,
                  ),
                  TextField(
                    controller: treatment,
                    decoration: const InputDecoration(
                      labelText: '변경 URL · 한 줄에 하나',
                    ),
                    maxLines: 3,
                  ),
                  TextField(
                    controller: control,
                    decoration: const InputDecoration(labelText: '대조 URL · 선택'),
                    maxLines: 3,
                  ),
                  if (error != null) Text(error!),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: busy ? null : () => Navigator.pop(c),
              child: const Text('취소'),
            ),
            FilledButton(
              onPressed: busy
                  ? null
                  : () async {
                      List<String> urls(String text) => text
                          .split('\n')
                          .map((s) => s.trim())
                          .where((s) => s.isNotEmpty)
                          .toSet()
                          .toList();
                      final t = urls(treatment.text), b = urls(control.text);
                      if (hypothesis.text.trim().length < 10 ||
                          t.isEmpty ||
                          [...t, ...b].any(
                            (u) => !u.startsWith('https://openedu4u.com/'),
                          ) ||
                          t.any(b.contains)) {
                        update(() => error = '가설과 중복되지 않는 운영 URL 목록을 확인해 주세요.');
                        return;
                      }
                      update(() => busy = true);
                      try {
                        await ref
                            .read(growthServiceProvider)
                            .createExperiment(hypothesis.text.trim(), t, b);
                        ref.invalidate(growthExperimentsProvider);
                        if (c.mounted) Navigator.pop(c);
                      } catch (e) {
                        update(() {
                          error = '$e';
                          busy = false;
                        });
                      }
                    },
              child: const Text('기록'),
            ),
          ],
        ),
      ),
    );
    hypothesis.dispose();
    treatment.dispose();
    control.dispose();
  }
}

class GrowthOverview extends StatelessWidget {
  final Map<String, dynamic> report;
  const GrowthOverview({super.key, required this.report});
  @override
  Widget build(BuildContext context) {
    final totals = Map<String, dynamic>.from(report['totals'] as Map);
    final quality = Map<String, dynamic>.from(report['quality'] as Map);
    final daily = (report['daily'] as List).cast<Map<String, dynamic>>();
    final findings = (report['findings'] as List).cast<Map<String, dynamic>>();
    final ctr = totals['ctr'] as num?;
    final coverage = quality['queryClickCoverage'] as num?;
    final truncated = quality['pageRowsTruncated'] == true;
    final pageCount = report['pageCount'] ?? (report['pages'] as List).length;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('${report['property']} · PT 기준 · 자료 추출 ${report['asOf']}'),
        const SizedBox(height: 12),
        LayoutBuilder(
          builder: (_, c) {
            final width =
                (c.maxWidth - (c.maxWidth > 850 ? 36 : 12)) /
                (c.maxWidth > 850 ? 4 : 2);
            return Wrap(
              spacing: 12,
              runSpacing: 12,
              children: [
                for (final (label, value) in [
                  ('검색 클릭', '${totals['clicks']}'),
                  ('검색 노출', '${totals['impressions']}'),
                  (
                    '클릭률',
                    ctr == null ? '—' : '${(ctr * 100).toStringAsFixed(2)}%',
                  ),
                  ('관측 페이지', '${truncated ? '≥' : ''}$pageCount'),
                ])
                  SizedBox(
                    width: width,
                    child: Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(label),
                            Text(
                              value,
                              style: Theme.of(context).textTheme.headlineMedium,
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
              ],
            );
          },
        ),
        const SizedBox(height: 20),
        Text(
          '검색어 클릭 가시성: ${coverage == null ? '분모 없음' : '${(coverage * 100).toStringAsFixed(1)}%'} · ${truncated ? '페이지 표는 내보내기 상한에 도달했습니다.' : '검색어 표와 총계는 다른 집계입니다.'}',
        ),
        for (final warning in (quality['warnings'] as List? ?? []))
          Text('자료 범위: $warning', style: Theme.of(context).textTheme.bodySmall),
        const SizedBox(height: 20),
        const SectionHeader('노출 추이', subtitle: '누락된 날짜는 0으로 채우지 않습니다.'),
        if (daily.length > 1)
          Semantics(
            label: '일별 검색 노출 그래프. 아래 일별 수치 표를 확인할 수 있습니다.',
            child: SizedBox(
              height: 180,
              width: double.infinity,
              child: CustomPaint(
                painter: _GrowthChart(
                  daily,
                  Theme.of(context).colorScheme.primary,
                ),
              ),
            ),
          ),
        ExpansionTile(
          title: const Text('일별 수치 표'),
          children: [
            for (final row in daily)
              ListTile(
                dense: true,
                title: Text('${row['date']}'),
                trailing: Text('${row['clicks']}클릭 / ${row['impressions']}노출'),
              ),
          ],
        ),
        const SizedBox(height: 20),
        const SectionHeader('진단 결과', subtitle: '급감 관측과 원인 확정을 구분합니다.'),
        if (findings.isEmpty)
          const Text('이 기간에 규칙으로 확인된 이상이 없습니다. 전체 품질 통과를 뜻하지는 않습니다.'),
        for (final f in findings)
          Card(
            child: ExpansionTile(
              title: Text('${f['severity']} · ${f['title']}'),
              subtitle: Text('${f['subjectKey']} · ${f['confidence']}'),
              children: [
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: SelectableText(
                    const JsonEncoder.withIndent('  ').convert(f),
                  ),
                ),
              ],
            ),
          ),
        const SizedBox(height: 20),
        _metricTable(context, '관측 검색어', report['queries'] as List),
        _metricTable(context, '관측 페이지 · 상위 20개', report['pages'] as List),
        if (report['evaluation'] == 'insufficient_evidence')
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 16),
            child: Text('현재 클릭 표본으로 검색 성과의 개선 여부를 판정하기 어렵습니다.'),
          ),
      ],
    );
  }

  Widget _metricTable(
    BuildContext context,
    String title,
    List<dynamic> rows,
  ) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(title, style: Theme.of(context).textTheme.titleLarge),
      const Text('검색어와 페이지의 관계는 별도 관측이 필요합니다.'),
      for (final r in rows)
        ListTile(
          contentPadding: EdgeInsets.zero,
          title: SelectableText('${r['key']}'),
          subtitle: Text(
            '노출 ${r['impressions']} · 클릭 ${r['clicks']} · 순위 ${r['position'] == null ? '—' : (r['position'] as num).toStringAsFixed(1)}',
          ),
        ),
      const SizedBox(height: 20),
    ],
  );
}

class _GrowthChart extends CustomPainter {
  final List<Map<String, dynamic>> daily;
  final Color color;
  _GrowthChart(this.daily, this.color);
  @override
  void paint(Canvas canvas, Size size) {
    if (daily.length < 2) return;
    final first = DateTime.parse(daily.first['date'] as String),
        last = DateTime.parse(daily.last['date'] as String);
    final days = math.max(1, last.difference(first).inDays),
        maxValue = daily
            .map((r) => (r['impressions'] as num).toDouble())
            .reduce(math.max);
    final path = Path();
    DateTime? previous;
    for (final r in daily) {
      final d = DateTime.parse(r['date'] as String),
          x = d.difference(first).inDays / days * size.width;
      final y =
          size.height -
          10 -
          (r['impressions'] as num) /
              math.max(1, maxValue) *
              (size.height - 20);
      if (previous == null || d.difference(previous).inDays > 1) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
      previous = d;
    }
    canvas.drawPath(
      path,
      Paint()
        ..color = color
        ..strokeWidth = 2.5
        ..style = PaintingStyle.stroke,
    );
  }

  @override
  bool shouldRepaint(covariant _GrowthChart old) =>
      old.daily != daily || old.color != color;
}
