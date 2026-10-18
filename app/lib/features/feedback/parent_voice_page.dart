import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../data/parent_voice.dart';
import '../../widgets/common.dart';
import '../../widgets/contact.dart';

void showParentVoice(
  BuildContext context, {
  String pageType = 'other',
  VoidCallback? onCorrection,
  VoidCallback? onReview,
}) {
  showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    builder: (_) => FractionallySizedBox(
      heightFactor: .92,
      child: ParentVoicePanel(
        pageType: pageType,
        onCorrection: onCorrection,
        onReview: onReview,
      ),
    ),
  );
}

class VoiceInvite extends StatelessWidget {
  final String pageType;
  final VoidCallback? onCorrection, onReview;
  const VoiceInvite({
    super.key,
    this.pageType = 'other',
    this.onCorrection,
    this.onReview,
  });
  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('학부모의 소리', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 8),
          const Text(
            '찾기 어려웠던 정보나 불편했던 순간을 알려주세요. 의견은 비공개로 검토하고, 반영한 내용은 개선 기록으로 전합니다.',
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 12,
            runSpacing: 8,
            children: [
              FilledButton(
                onPressed: () => showParentVoice(
                  context,
                  pageType: pageType,
                  onCorrection: onCorrection,
                  onReview: onReview,
                ),
                child: const Text('의견 남기기'),
              ),
              TextButton(
                onPressed: () => context.go('/feedback'),
                child: const Text('처리 상태 · 개선 기록'),
              ),
            ],
          ),
        ],
      ),
    ),
  );
}

class ParentVoicePage extends StatelessWidget {
  const ParentVoicePage({super.key});
  @override
  Widget build(BuildContext context) =>
      const ParentVoicePanel(pageType: 'other', fullPage: true);
}

class ParentVoicePanel extends ConsumerStatefulWidget {
  final String pageType;
  final bool fullPage;
  final VoidCallback? onCorrection, onReview;
  const ParentVoicePanel({
    super.key,
    required this.pageType,
    this.fullPage = false,
    this.onCorrection,
    this.onReview,
  });
  @override
  ConsumerState<ParentVoicePanel> createState() => _ParentVoicePanelState();
}

class _ParentVoicePanelState extends ConsumerState<ParentVoicePanel> {
  final _note = TextEditingController(), _code = TextEditingController();
  String? _category, _message;
  String _route = 'service';
  bool _busy = false, _received = false, _context = true;
  Map<String, dynamic>? _status;
  late ParentVoiceService _service;
  @override
  void initState() {
    super.initState();
    _service = ref.read(parentVoiceProvider);
    _code.text = _service.lastCode ?? '';
  }

  @override
  void dispose() {
    _service.forgetDraft();
    _note.dispose();
    _code.dispose();
    super.dispose();
  }

  Future<void> _run(Future<void> Function() action) async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      await action();
    } on VoiceFailure catch (e) {
      if (mounted) setState(() => _message = e.message);
    } catch (_) {
      if (mounted) setState(() => _message = '처리하지 못했습니다. 잠시 뒤 다시 시도해주세요.');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final service = ref.watch(parentVoiceProvider);
    final text = Theme.of(context).textTheme;
    return ListView(
      padding: EdgeInsets.fromLTRB(
        20,
        24,
        20,
        24 + MediaQuery.viewInsetsOf(context).bottom,
      ),
      children: [
        ContentWidth(
          max: 720,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(child: Text('학부모의 소리', style: text.headlineMedium)),
                  if (!widget.fullPage)
                    IconButton(
                      tooltip: '닫기 · 작성 내용 삭제',
                      onPressed: _busy ? null : () => Navigator.pop(context),
                      icon: const Icon(Icons.close),
                    ),
                ],
              ),
              const SizedBox(height: 12),
              const Text(
                '아이 이름·학교 반·전화번호·이메일은 적지 마세요. 내용은 운영팀만 확인합니다. 접수는 반영 약속과 다릅니다. 닫으면 작성 중인 메모는 지워집니다.',
              ),
              const SizedBox(height: 8),
              const Text(
                '의견 내용과 화면 정보는 접수 후 90일, 접수 기록은 180일 동안 보관합니다. 확인 코드로 먼저 삭제할 수 있습니다.',
              ),
              const SizedBox(height: 20),
              DropdownButtonFormField<String>(
                initialValue: _route,
                isExpanded: true,
                decoration: const InputDecoration(labelText: '남기려는 내용'),
                items: const [
                  DropdownMenuItem(value: 'service', child: Text('사이트 이용 의견')),
                  DropdownMenuItem(
                    value: 'correction',
                    child: Text('학원 정보 정정'),
                  ),
                  DropdownMenuItem(
                    value: 'evidence',
                    child: Text('잘못 연결된 근거 신고'),
                  ),
                  DropdownMenuItem(value: 'review', child: Text('실제 수강 경험')),
                ],
                onChanged: _busy ? null : (v) => setState(() => _route = v!),
              ),
              if (_route != 'service') ...[
                const SizedBox(height: 16),
                Text(switch (_route) {
                  'correction' => '정보 정정은 회신 연락처가 필요한 기존 폼에서 받습니다.',
                  'review' => '수강 후기는 해당 학원 상세에서 로그인 후 남길 수 있습니다.',
                  _ =>
                    '해당 학원 상세에서 잘못 연결된 근거의 신고 버튼을 이용해주세요. 신고만으로 글이 삭제되지는 않습니다.',
                }),
                const SizedBox(height: 12),
                OutlinedButton(
                  onPressed: () {
                    final callback = _route == 'correction'
                        ? widget.onCorrection
                        : _route == 'review'
                        ? widget.onReview
                        : null;
                    if (callback != null) {
                      if (!widget.fullPage) Navigator.pop(context);
                      callback();
                    } else {
                      if (!widget.fullPage) Navigator.pop(context);
                      context.go('/rank');
                    }
                  },
                  child: Text(
                    (_route == 'correction' && widget.onCorrection != null)
                        ? '정보 정정 요청 열기'
                        : '해당 학원 상세에서 확인하기',
                  ),
                ),
              ] else if (!_received) ...[
                const SizedBox(height: 20),
                if (!service.enabled)
                  const Text(
                    '현재 의견 접수를 준비 중입니다. 학원 정보 오류와 수강 후기는 위에서 기존 경로를 선택해주세요.',
                  ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  isExpanded: true,
                  decoration: const InputDecoration(labelText: '의견 유형 · 필수'),
                  items: [
                    for (final e in voiceCategories.entries)
                      DropdownMenuItem(value: e.key, child: Text(e.value)),
                  ],
                  onChanged: _busy
                      ? null
                      : (v) => setState(() => _category = v),
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: _note,
                  maxLength: 400,
                  maxLines: 4,
                  enabled: !_busy,
                  decoration: const InputDecoration(
                    labelText: '조금 더 들려주세요 · 선택',
                    alignLabelWithHint: true,
                  ),
                ),
                CheckboxListTile(
                  contentPadding: EdgeInsets.zero,
                  value: _context,
                  onChanged: _busy
                      ? null
                      : (v) => setState(() => _context = v!),
                  title: const Text('현재 화면 유형만 함께 보내기'),
                  subtitle: Text(
                    '현재 화면: ${const {'home': '홈', 'search': '학원 탐색', 'compare': '비교 노트', 'academy': '학원 상세', 'other': '의견 화면'}[widget.pageType] ?? '기타'} · 검색어·개인 조건·전체 주소는 보내지 않습니다.',
                  ),
                ),
                const SizedBox(height: 12),
                FilledButton(
                  onPressed: !service.enabled || _busy || _category == null
                      ? null
                      : () => _run(() async {
                          await service.submit(
                            _category!,
                            _note.text,
                            pageType: _context ? widget.pageType : null,
                          );
                          if (mounted) {
                            setState(() {
                              _received = true;
                              _note.clear();
                              _code.text = service.lastCode!;
                            });
                          }
                        }),
                  child: Text(_busy ? '보내는 중…' : '비공개로 의견 보내기'),
                ),
              ] else ...[
                const SizedBox(height: 20),
                Text('의견을 접수했습니다.', style: text.titleLarge),
                Text(
                  service.receiptStored
                      ? '확인 코드는 이번 탭에 보관됩니다. 탭을 닫기 전에 복사해두세요.'
                      : '이 환경에서는 확인 코드를 보관하지 못했습니다. 상태 확인이 필요하면 지금 복사해두세요.',
                ),
                const Text('확인 코드를 가진 사람은 처리 상태를 확인하거나 원문 삭제를 요청할 수 있습니다.'),
                TextButton(
                  onPressed: () => copyContactText(
                    context,
                    service.lastCode!,
                    success: '확인 코드를 복사했습니다. 안전하게 보관해주세요.',
                  ),
                  child: const Text('확인 코드 복사'),
                ),
              ],
              if (_received && _route == 'service')
                TextButton(
                  onPressed: _busy
                      ? null
                      : () => setState(() {
                          _received = false;
                          _category = null;
                          _message = null;
                        }),
                  child: const Text('새 의견 작성'),
                ),
              if (_message != null)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  child: Semantics(liveRegion: true, child: Text(_message!)),
                ),
              const Divider(height: 40),
              Text('내 의견 처리 상태', style: text.titleLarge),
              const SizedBox(height: 12),
              TextField(
                controller: _code,
                obscureText: true,
                autocorrect: false,
                enableSuggestions: false,
                decoration: const InputDecoration(
                  labelText: '확인 코드',
                  helperText: '이번 탭에 보관된 코드 또는 복사해 둔 코드를 입력해주세요.',
                ),
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  OutlinedButton(
                    onPressed: !service.enabled || _busy
                        ? null
                        : () => _run(() async {
                            service.remember(_code.text.trim());
                            final result = await service.status();
                            if (mounted) setState(() => _status = result);
                          }),
                    child: const Text('상태 확인'),
                  ),
                  TextButton(
                    onPressed: !service.enabled || _busy
                        ? null
                        : () => _run(() async {
                            final confirmed = await showDialog<bool>(
                              context: context,
                              builder: (ctx) => AlertDialog(
                                title: const Text('의견 원문을 삭제할까요?'),
                                content: const Text(
                                  '원문과 맥락·확인 코드가 삭제되어 상태 조회도 종료됩니다. 이미 공개한 비식별 개선 기록은 유지됩니다. 호스팅 백업은 보관 정책에 따라 정리됩니다.',
                                ),
                                actions: [
                                  TextButton(
                                    onPressed: () => Navigator.pop(ctx, false),
                                    child: const Text('취소'),
                                  ),
                                  FilledButton(
                                    onPressed: () => Navigator.pop(ctx, true),
                                    child: const Text('삭제'),
                                  ),
                                ],
                              ),
                            );
                            if (confirmed != true) return;
                            service.remember(_code.text.trim());
                            await service.delete();
                            if (mounted) {
                              setState(() {
                                _status = null;
                                _code.clear();
                                _received = false;
                                _category = null;
                                _message = '의견 원문과 확인 코드를 삭제했습니다.';
                              });
                            }
                          }),
                    child: const Text('원문 삭제'),
                  ),
                ],
              ),
              if (_status != null) ...[
                const SizedBox(height: 12),
                Text(
                  voiceStatuses[_status!['status']] ?? '처리 상태 확인 중',
                  style: text.titleMedium,
                ),
                if (_status!['safeResolution'] != null)
                  Text(_status!['safeResolution'] as String),
              ],
              const Divider(height: 40),
              Text('학부모 의견으로 바뀐 것', style: text.titleLarge),
              const SizedBox(height: 12),
              ref
                  .watch(parentImprovementsProvider)
                  .when(
                    loading: () => const LinearProgressIndicator(),
                    error: (_, _) => TextButton(
                      onPressed: () =>
                          ref.invalidate(parentImprovementsProvider),
                      child: const Text('개선 기록 다시 불러오기'),
                    ),
                    data: (rows) => Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: rows.isEmpty
                          ? [
                              const Text(
                                '아직 공개할 개선 기록이 없습니다. 실제 반영과 검증을 마친 뒤 소개합니다.',
                              ),
                            ]
                          : [
                              for (final r in rows)
                                Card(
                                  child: Padding(
                                    padding: const EdgeInsets.all(16),
                                    child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          r['title'] as String,
                                          style: text.titleMedium,
                                        ),
                                        Text(r['summary'] as String),
                                        Text(
                                          (r['published_at'] as String)
                                              .split('T')
                                              .first,
                                        ),
                                        TextButton(
                                          onPressed: () => openExternal(
                                            r['verification_url'] as String,
                                          ),
                                          child: const Text('반영된 화면 보기'),
                                        ),
                                      ],
                                    ),
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
  }
}
