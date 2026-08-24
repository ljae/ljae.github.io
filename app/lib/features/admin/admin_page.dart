import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/theme.dart';
import '../../data/admin.dart';
import '../../widgets/common.dart';

/// 참조 글 검수 관리자 화면.
///
/// 랭킹이 커뮤니티 글에서 나오는 이상, 무엇을 근거로 삼았는지 사람이
/// 확인할 수 있어야 한다. 다만 사람이 영원히 누르게 두면 그건 자동화가
/// 아니라 노동이다 — 반려할 때 남긴 사유가 크롤 규칙이 되어 다음
/// 수집부터 같은 글이 안 올라오게 하는 것이 이 화면의 핵심이다.
class AdminPage extends ConsumerStatefulWidget {
  const AdminPage({super.key});

  @override
  ConsumerState<AdminPage> createState() => _AdminPageState();
}

class _AdminPageState extends ConsumerState<AdminPage> {
  int _tab = 0;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final service = ref.watch(adminServiceProvider);
    final enabled = service.enabled;
    final isAdmin = ref.watch(isAdminProvider);

    return ListView(
      padding: const EdgeInsets.symmetric(vertical: AppSpace.lg),
      children: [
        ContentWidth(
          max: 1000,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SectionHeader('참조 글 검수',
                  subtitle: '랭킹 근거로 쓰인 글을 확인하고, 잘못 잡힌 글을 '
                      '반려합니다. 반려 사유는 다음 수집의 필터가 됩니다.'),
              if (!enabled)
                Text('Supabase 연결이 없어 검수 기능을 쓸 수 없습니다.',
                    style: text.bodyLarge)
              else if (!service.signedIn)
                const _SignIn()
              else if (isAdmin.value == false)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(AppSpace.md),
                    child: Text(
                      '이 계정은 운영자로 등록되어 있지 않습니다. '
                      '등록은 데이터베이스에서만 가능합니다.',
                      style: text.bodyLarge,
                    ),
                  ),
                )
              else ...[
                const _SourceList(),
                const SizedBox(height: AppSpace.lg),
                SegmentedButton<int>(
                  showSelectedIcon: false,
                  segments: const [
                    ButtonSegment(value: 0, label: Text('검수 대기')),
                    ButtonSegment(value: 1, label: Text('크롤 규칙')),
                  ],
                  selected: {_tab},
                  onSelectionChanged: (v) => setState(() => _tab = v.first),
                ),
                const SizedBox(height: AppSpace.md),
                if (_tab == 0) const _PendingList() else const _RulesPanel(),
              ],
              const SizedBox(height: AppSpace.xxl),
            ],
          ),
        ),
      ],
    );
  }
}

/// 어떤 사이트를 참조하는지 밝힌다. 랭킹의 출처를 묻는 질문에
/// 화면이 스스로 답할 수 있어야 한다.
class _SourceList extends StatelessWidget {
  const _SourceList();

  static const sources = [
    ('네이버 블로그', 'https://section.blog.naver.com',
        '검색 API. 최신순으로 받아 학원명이 본문에 나온 글만 근거로 씁니다.'),
    ('네이버 카페', 'https://section.cafe.naver.com',
        '검색 API. 공개 글만 받습니다. 로그인이 필요한 카페는 수집하지 않습니다.'),
    ('네이버 지식iN', 'https://kin.naver.com',
        '검색 API. 질문·답변에서 학원 언급을 봅니다.'),
    ('학원실록 자체 후기', '',
        '로그인 후 남긴 후기. 재원 인증분은 신뢰도를 더 높게 줍니다.'),
  ];

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpace.md),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('참조하는 곳', style: text.titleMedium),
          const SizedBox(height: 6),
          for (final (name, url, note) in sources)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Icon(Icons.link, size: 14, color: AppColors.mist),
                const SizedBox(width: 6),
                Expanded(
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        InkWell(
                          onTap: url.isEmpty
                              ? null
                              : () => launchUrl(Uri.parse(url),
                                  webOnlyWindowName: '_blank'),
                          child: Text(name,
                              style: text.labelLarge?.copyWith(
                                  color: url.isEmpty
                                      ? null
                                      : AppColors.navyBright)),
                        ),
                        Text(note, style: text.bodySmall),
                      ]),
                ),
              ]),
            ),
          const SizedBox(height: 6),
          Text(
            'robots.txt 나 콘텐츠 신호로 수집을 거부한 사이트는 참조하지 않습니다. '
            '본문은 저장하지 않고 원문 링크로만 안내합니다.',
            style: text.bodySmall,
          ),
        ]),
      ),
    );
  }
}

class _PendingList extends ConsumerWidget {
  const _PendingList();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final async = ref.watch(pendingReviewsProvider(null));

    return async.when(
      loading: () => const Padding(
        padding: EdgeInsets.all(AppSpace.xl),
        child: Center(child: CircularProgressIndicator()),
      ),
      error: (e, _) => Text('불러오지 못했습니다: $e', style: text.bodyMedium),
      data: (rows) => rows.isEmpty
          ? Padding(
              padding: const EdgeInsets.symmetric(vertical: AppSpace.xl),
              child: Text(
                  '검수 대기 글이 없습니다. 다음 수집에서 새 글이 올라옵니다.',
                  style: text.bodyMedium),
            )
          : Column(children: [
              Padding(
                padding: const EdgeInsets.only(bottom: AppSpace.sm),
                child: Row(children: [
                  Text('${rows.length}건 대기', style: text.labelLarge),
                  const Spacer(),
                  Flexible(
                    child: Text('신뢰도가 높은 글부터 — 점수에 영향이 큰 순서입니다',
                        textAlign: TextAlign.right, style: text.bodySmall),
                  ),
                ]),
              ),
              for (final r in rows) _ReviewTile(key: ValueKey(r.urlHash), row: r),
            ]),
    );
  }
}

class _ReviewTile extends ConsumerStatefulWidget {
  final MentionReview row;
  const _ReviewTile({super.key, required this.row});

  @override
  ConsumerState<_ReviewTile> createState() => _ReviewTileState();
}

class _ReviewTileState extends ConsumerState<_ReviewTile> {
  bool _done = false;
  bool _busy = false;

  Future<bool> _judge(String verdict, {String? reason}) async {
    setState(() => _busy = true);
    try {
      await ref
          .read(adminServiceProvider)
          .judge(widget.row.urlHash, verdict, reason: reason);
      if (mounted) setState(() => _done = true);
      return true;
    } catch (_) {
      if (!mounted) return false;
      setState(() => _busy = false);
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('처리에 실패했습니다.')));
      return false;
    }
  }

  /// 반려하면 사유를 묻고, 이어서 규칙으로 굳힐지 묻는다.
  /// 여기서 규칙이 안 생기면 사람이 같은 글을 영원히 누르게 된다.
  Future<void> _reject() async {
    final reason = await showModalBottomSheet<String>(
      context: context,
      builder: (_) => const _ReasonSheet(),
    );
    if (reason == null || !mounted) return;
    final ok = await _judge('rejected', reason: reason);
    if (!ok || !mounted) return;
    if (reason == 'person' || reason == 'irrelevant' || reason == 'sale') {
      final made = await showModalBottomSheet<bool>(
        context: context,
        isScrollControlled: true,
        showDragHandle: true,
        constraints: const BoxConstraints(maxWidth: 640),
        builder: (_) => _RuleSheet(row: widget.row),
      );
      if (made == true) ref.invalidate(crawlRulesProvider);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_done) return const SizedBox.shrink();
    final text = Theme.of(context).textTheme;
    final r = widget.row;

    return Card(
      margin: const EdgeInsets.only(bottom: AppSpace.sm),
      child: Padding(
        padding: const EdgeInsets.all(AppSpace.md),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Wrap(spacing: 6, runSpacing: 4, children: [
            Chip2(r.academyName.isEmpty ? r.academyKey : r.academyName,
                color: AppColors.navy),
            Chip2(r.sourceLabel, color: AppColors.slate),
            if (r.postedAt != null)
              Text('${r.postedAt!.year}.${r.postedAt!.month}.${r.postedAt!.day}',
                  style: text.bodySmall),
          ]),
          const SizedBox(height: 6),
          Text(r.title, style: text.titleMedium),
          if (r.snippet.isNotEmpty) ...[
            const SizedBox(height: 3),
            Text(r.snippet,
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
                style: text.bodyMedium),
          ],
          const SizedBox(height: AppSpace.sm),
          Row(children: [
            if (r.sourceUrl != null)
              TextButton.icon(
                onPressed: () => launchUrl(Uri.parse(r.sourceUrl!),
                    webOnlyWindowName: '_blank'),
                icon: const Icon(Icons.open_in_new, size: 14),
                label: const Text('원문'),
              ),
            const Spacer(),
            OutlinedButton(
              onPressed: _busy ? null : _reject,
              style:
                  OutlinedButton.styleFrom(foregroundColor: AppColors.rising),
              child: const Text('반려'),
            ),
            const SizedBox(width: AppSpace.sm),
            FilledButton(
              onPressed: _busy ? null : () => _judge('confirmed'),
              child: const Text('확인'),
            ),
          ]),
        ]),
      ),
    );
  }
}

class _ReasonSheet extends StatelessWidget {
  const _ReasonSheet();

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(AppSpace.md),
        child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('왜 근거로 쓸 수 없나요', style: text.titleMedium),
              const SizedBox(height: 4),
              Text('사유는 크롤러 개선에 그대로 쓰입니다.', style: text.bodySmall),
              const SizedBox(height: AppSpace.sm),
              for (final e in rejectReasons.entries)
                ListTile(
                  dense: true,
                  title: Text(e.value),
                  onTap: () => Navigator.of(context).pop(e.key),
                ),
            ]),
      ),
    );
  }
}

/// 반려를 규칙으로 굳히는 시트.
class _RuleSheet extends ConsumerStatefulWidget {
  final MentionReview row;
  const _RuleSheet({required this.row});

  @override
  ConsumerState<_RuleSheet> createState() => _RuleSheetState();
}

class _RuleSheetState extends ConsumerState<_RuleSheet> {
  final _pattern = TextEditingController();
  final _reason = TextEditingController();
  String _scope = 'academy';
  bool _busy = false;

  @override
  void dispose() {
    _pattern.dispose();
    _reason.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Padding(
      padding: EdgeInsets.only(
          left: AppSpace.md,
          right: AppSpace.md,
          bottom: MediaQuery.viewInsetsOf(context).bottom + AppSpace.lg),
      child: SingleChildScrollView(
        child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('같은 글이 다시 안 올라오게 할까요', style: text.titleLarge),
              const SizedBox(height: 4),
              Text(
                '이 글에서 걸러야 할 낱말을 적으면 다음 수집부터 제외합니다. '
                '예: 뮤지컬 배우와 이름이 겹칠 때 "뮤지컬|공연|배우".',
                style: text.bodySmall,
              ),
              const SizedBox(height: AppSpace.md),
              SegmentedButton<String>(
                showSelectedIcon: false,
                segments: [
                  ButtonSegment(
                      value: 'academy',
                      label: Text(widget.row.academyName.isEmpty
                          ? '이 학원에만'
                          : '${widget.row.academyName}에만')),
                  const ButtonSegment(value: 'global', label: Text('전체에')),
                ],
                selected: {_scope},
                onSelectionChanged: (v) => setState(() => _scope = v.first),
              ),
              const SizedBox(height: AppSpace.md),
              TextField(
                controller: _pattern,
                decoration: const InputDecoration(
                  border: OutlineInputBorder(),
                  labelText: '제외할 낱말 (여러 개는 | 로 구분) *',
                  hintText: '뮤지컬|공연|배우|커튼콜',
                ),
              ),
              const SizedBox(height: AppSpace.sm),
              TextField(
                controller: _reason,
                decoration: const InputDecoration(
                  border: OutlineInputBorder(),
                  labelText: '이유 * — 나중에 이 규칙을 지울지 판단하는 근거',
                  hintText: '뮤지컬 배우 윤도영과 학원명이 같아 오검출',
                ),
              ),
              const SizedBox(height: AppSpace.md),
              Row(children: [
                TextButton(
                  onPressed: () => Navigator.of(context).pop(false),
                  child: const Text('규칙 없이 넘어가기'),
                ),
                const Spacer(),
                FilledButton(
                  onPressed: _busy
                      ? null
                      : () async {
                          if (_pattern.text.trim().isEmpty ||
                              _reason.text.trim().isEmpty) {
                            return;
                          }
                          setState(() => _busy = true);
                          try {
                            await ref.read(adminServiceProvider).addRule(
                                  kind: 'exclude_keyword',
                                  pattern: _pattern.text.trim(),
                                  reason: _reason.text.trim(),
                                  scope: _scope,
                                  academyKey: widget.row.academyKey,
                                );
                            if (context.mounted) {
                              Navigator.of(context).pop(true);
                            }
                          } catch (_) {
                            if (context.mounted) setState(() => _busy = false);
                          }
                        },
                  child: Text(_busy ? '저장 중…' : '규칙 추가'),
                ),
              ]),
            ]),
      ),
    );
  }
}

class _RulesPanel extends ConsumerWidget {
  const _RulesPanel();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final async = ref.watch(crawlRulesProvider);

    return async.when(
      loading: () => const Padding(
        padding: EdgeInsets.all(AppSpace.xl),
        child: Center(child: CircularProgressIndicator()),
      ),
      error: (e, _) => Text('불러오지 못했습니다: $e', style: text.bodyMedium),
      data: (rules) => Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '검수에서 나온 규칙입니다. 매 수집마다 적용되어 같은 오검출이 '
              '반복되지 않게 합니다. 효과가 없으면 끄면 됩니다.',
              style: text.bodySmall,
            ),
            const SizedBox(height: AppSpace.sm),
            if (rules.isEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: AppSpace.lg),
                child: Text('아직 규칙이 없습니다. 글을 반려하면서 만들어집니다.',
                    style: text.bodyMedium),
              )
            else
              for (final r in rules)
                Card(
                  margin: const EdgeInsets.only(bottom: AppSpace.sm),
                  child: Padding(
                    padding: const EdgeInsets.all(AppSpace.md),
                    child: Row(children: [
                      Expanded(
                        child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Wrap(spacing: 6, children: [
                                Chip2(
                                    r.scope == 'global'
                                        ? '전체'
                                        : (r.academyKey ?? '학원'),
                                    color: AppColors.navy),
                                Text(r.kindLabel, style: text.bodySmall),
                              ]),
                              const SizedBox(height: 4),
                              Text(r.pattern, style: text.titleMedium),
                              Text(r.reason, style: text.bodySmall),
                              if (r.hits > 0)
                                Text('${r.hits}건 걸러냄',
                                    style: text.bodySmall
                                        ?.copyWith(color: AppColors.verified)),
                            ]),
                      ),
                      Switch(
                        value: r.active,
                        onChanged: (v) async {
                          await ref
                              .read(adminServiceProvider)
                              .toggleRule(r.id, v);
                          ref.invalidate(crawlRulesProvider);
                        },
                      ),
                    ]),
                  ),
                ),
          ]),
    );
  }
}

/// 운영자 로그인. 후기와 같은 방식 — 비밀번호를 만들지 않는다.
class _SignIn extends ConsumerStatefulWidget {
  const _SignIn();

  @override
  ConsumerState<_SignIn> createState() => _SignInState();
}

class _SignInState extends ConsumerState<_SignIn> {
  final _email = TextEditingController();
  String? _notice;
  bool _busy = false;

  @override
  void dispose() {
    _email.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpace.md),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('운영자 로그인', style: text.titleMedium),
          const SizedBox(height: 4),
          Text('등록된 운영자 계정만 검수 화면을 볼 수 있습니다.',
              style: text.bodySmall),
          const SizedBox(height: AppSpace.md),
          TextField(
            controller: _email,
            keyboardType: TextInputType.emailAddress,
            decoration: const InputDecoration(
                labelText: '이메일', border: OutlineInputBorder()),
          ),
          if (_notice != null) ...[
            const SizedBox(height: 6),
            Text(_notice!, style: text.bodySmall),
          ],
          const SizedBox(height: AppSpace.sm),
          FilledButton(
            onPressed: _busy
                ? null
                : () async {
                    setState(() { _busy = true; _notice = null; });
                    try {
                      await ref
                          .read(adminServiceProvider)
                          .signIn(_email.text.trim());
                      if (mounted) {
                        setState(() => _notice = '로그인 링크를 보냈습니다.');
                      }
                    } catch (e) {
                      if (mounted) setState(() => _notice = '전송 실패: $e');
                    } finally {
                      if (mounted) setState(() => _busy = false);
                    }
                  },
            child: Text(_busy ? '보내는 중…' : '로그인 링크 받기'),
          ),
        ]),
      ),
    );
  }
}
