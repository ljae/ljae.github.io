import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../../data/admin.dart';
import '../../data/parent_voice.dart';
import '../../widgets/common.dart';

final _queueProvider = FutureProvider.family<List<Map<String, dynamic>>, int>((
  ref,
  page,
) async {
  if (!await ref.watch(isAdminProvider.future)) {
    return [];
  }
  final rows = await Supabase.instance.client.rpc<List<dynamic>>(
    'parent_voice_admin_queue',
    params: {'p_page': page},
  );
  return rows.map((r) => Map<String, dynamic>.from(r as Map)).toList();
});

class ParentVoiceAdminPage extends ConsumerStatefulWidget {
  const ParentVoiceAdminPage({super.key});
  @override
  ConsumerState<ParentVoiceAdminPage> createState() =>
      _ParentVoiceAdminPageState();
}

class _ParentVoiceAdminPageState extends ConsumerState<ParentVoiceAdminPage> {
  int page = 0;
  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.symmetric(vertical: 24),
    children: [
      ContentWidth(
        max: 900,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '학부모 의견 관리',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 12),
            const Text(
              '원문은 비공개입니다. 처리 사유와 공개 요약에 개인 정보·원문을 옮기지 마세요. 접수 수는 고유 학부모 수나 학원 평가가 아닙니다.',
            ),
            TextButton(
              onPressed: () => context.go('/admin'),
              child: const Text('관리자 화면으로'),
            ),
            ref
                .watch(isAdminProvider)
                .when(
                  loading: () => const LinearProgressIndicator(),
                  error: (_, _) => const Text('운영자 권한을 확인하지 못했습니다.'),
                  data: (allowed) {
                    if (!allowed) {
                      return const Text('관리자 화면에서 운영자로 로그인해주세요.');
                    }
                    return ref
                        .watch(_queueProvider(page))
                        .when(
                          loading: () => const LinearProgressIndicator(),
                          error: (_, _) => TextButton(
                            onPressed: () =>
                                ref.invalidate(_queueProvider(page)),
                            child: const Text('접수 목록 다시 불러오기 · 연결과 스키마 확인 필요'),
                          ),
                          data: (rows) => Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Wrap(
                                spacing: 12,
                                runSpacing: 8,
                                children: [
                                  TextButton(
                                    onPressed: page > 0
                                        ? () => setState(() => page--)
                                        : null,
                                    child: const Text('이전'),
                                  ),
                                  Text('${page + 1}페이지'),
                                  TextButton(
                                    onPressed: rows.length == 25
                                        ? () => setState(() => page++)
                                        : null,
                                    child: const Text('다음'),
                                  ),
                                  TextButton(
                                    onPressed: () =>
                                        ref.invalidate(_queueProvider(page)),
                                    child: const Text('새로고침'),
                                  ),
                                ],
                              ),
                              if (rows.isEmpty)
                                const Text('이 페이지에 접수된 의견이 없습니다.'),
                              for (final row in rows)
                                _FeedbackCard(
                                  key: ValueKey(
                                    '${row['id']}:${row['version']}',
                                  ),
                                  row: row,
                                  onChanged: () {
                                    ref.invalidate(_queueProvider(page));
                                    ref.invalidate(parentImprovementsProvider);
                                  },
                                ),
                            ],
                          ),
                        );
                  },
                ),
          ],
        ),
      ),
    ],
  );
}

class _FeedbackCard extends StatefulWidget {
  final Map<String, dynamic> row;
  final VoidCallback onChanged;
  const _FeedbackCard({super.key, required this.row, required this.onChanged});
  @override
  State<_FeedbackCard> createState() => _FeedbackCardState();
}

class _FeedbackCardState extends State<_FeedbackCard> {
  final fields = {
    for (final k in [
      'safe',
      'internal',
      'duplicate',
      'title',
      'summary',
      'commit',
      'deploy',
      'url',
    ])
      k: TextEditingController(),
  };
  String? target, message;
  bool busy = false, verified = false;
  @override
  void initState() {
    super.initState();
    fields['safe']!.text = widget.row['safe_resolution'] as String? ?? '';
    fields['internal']!.text =
        widget.row['internal_resolution'] as String? ?? '';
  }

  @override
  void dispose() {
    for (final c in fields.values) {
      c.dispose();
    }
    super.dispose();
  }

  String value(String key) => fields[key]!.text.trim();
  Future<void> run(Future<void> Function() fn) async {
    setState(() {
      busy = true;
      message = null;
    });
    try {
      await fn();
      if (mounted) {
        ScaffoldMessenger.maybeOf(
          context,
        )?.showSnackBar(const SnackBar(content: Text('처리를 저장했습니다.')));
        widget.onChanged();
      }
    } catch (_) {
      if (mounted) {
        setState(() => message = '처리하지 못했습니다. 권한·입력·상태를 확인하고 새로고침해주세요.');
      }
    } finally {
      if (mounted) {
        setState(() => busy = false);
      }
    }
  }

  Widget field(String key, String label, {int max = 400, int lines = 1}) =>
      Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: TextField(
          controller: fields[key],
          maxLength: max,
          maxLines: lines,
          enabled: !busy,
          decoration: InputDecoration(labelText: label),
        ),
      );
  @override
  Widget build(BuildContext context) {
    final r = widget.row;
    final state = r['status'] as String;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '${voiceCategories[r['category']] ?? '기타'} · ${voiceStatuses[state]}',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            Text('접수 ${r['created_at']} · 화면 ${r['page_type'] ?? '미제공'}'),
            const SizedBox(height: 12),
            SelectableText('접수 ID ${r['id']}'),
            SelectableText(r['note'] as String? ?? '메모 없음'),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              isExpanded: true,
              decoration: const InputDecoration(labelText: '다음 상태'),
              items: [
                for (final s in voiceTransitions[state] ?? <String>[])
                  DropdownMenuItem(value: s, child: Text(voiceStatuses[s]!)),
              ],
              onChanged: busy ? null : (v) => setState(() => target = v),
            ),
            field('safe', '접수증에 표시할 사유 · 원문·신상 제외', lines: 2),
            field('internal', '내부 검토 메모', max: 1000, lines: 2),
            if (target == 'duplicate')
              field('duplicate', '함께 검토할 접수 ID', max: 36),
            FilledButton(
              onPressed: busy || target == null
                  ? null
                  : () => run(() async {
                      await Supabase.instance.client.rpc<dynamic>(
                        'parent_voice_transition',
                        params: {
                          'p_id': r['id'],
                          'p_version': r['version'],
                          'p_status': target,
                          'p_safe_resolution': value('safe'),
                          'p_internal_resolution': value('internal'),
                          'p_duplicate_of': target == 'duplicate'
                              ? value('duplicate')
                              : null,
                        },
                      );
                    }),
              child: const Text('상태와 사유 저장'),
            ),
            if (state == 'resolved')
              ExpansionTile(
                tilePadding: EdgeInsets.zero,
                title: const Text('검증된 개선 기록 공개'),
                children: [
                  const Text(
                    '운영 반영을 직접 확인한 변경만 공개합니다. 요약은 모든 방문자에게 보입니다. 의견 원문을 인용하지 마세요.',
                  ),
                  field('title', '공개 제목', max: 100),
                  field('summary', '공개 개선 요약', max: 600, lines: 3),
                  field('commit', '반영 커밋 SHA', max: 40),
                  field('deploy', '배포 식별자', max: 200),
                  field('url', '확인한 운영 화면 https://openedu4u.com/…', max: 1000),
                  CheckboxListTile(
                    value: verified,
                    onChanged: busy
                        ? null
                        : (v) => setState(() => verified = v!),
                    title: const Text('운영 화면에서 변경을 확인했고 공개 내용을 검수했습니다.'),
                  ),
                  FilledButton(
                    onPressed: busy || !verified
                        ? null
                        : () => run(() async {
                            await Supabase.instance.client.rpc<dynamic>(
                              'parent_voice_publish',
                              params: {
                                'p_feedback_id': r['id'],
                                'p_title': value('title'),
                                'p_summary': value('summary'),
                                'p_commit': value('commit'),
                                'p_deploy_ref': value('deploy'),
                                'p_url': value('url'),
                              },
                            );
                          }),
                    child: const Text('검수한 개선 기록 공개'),
                  ),
                ],
              ),
            if (message != null) Text(message!),
          ],
        ),
      ),
    );
  }
}
