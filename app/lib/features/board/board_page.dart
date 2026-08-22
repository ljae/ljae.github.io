import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/env.dart';
import '../../core/theme.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../../data/board.dart';
import '../../data/repository.dart';
import '../../widgets/common.dart';

const _categories = <(String?, String)>[
  (null, '전체'),
  ('report', '주간 리포트'),
  ('guide', '단계 해설'),
  ('question', '질문'),
  ('talk', '수다'),
];

class BoardPage extends ConsumerStatefulWidget {
  const BoardPage({super.key});

  @override
  ConsumerState<BoardPage> createState() => _BoardPageState();
}

class _BoardPageState extends ConsumerState<BoardPage> {
  String? _category;

  @override
  Widget build(BuildContext context) {
    final sel = ref.watch(selectionProvider);
    final text = Theme.of(context).textTheme;

    if (!Env.hasSupabase) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(AppSpace.xl),
          child: Text('게시판은 준비 중입니다.', style: text.bodyLarge),
        ),
      );
    }

    final async = ref.watch(boardListProvider((sel.regionId, _category)));
    final service = ref.watch(boardServiceProvider);

    return ListView(
      padding: const EdgeInsets.symmetric(vertical: AppSpace.lg),
      children: [
        ContentWidth(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SectionHeader('게시판',
                  subtitle: '여기 남긴 이야기는 트리스코어에 반영됩니다. '
                      '누가 무엇을 말하는지가 곧 지표가 됩니다.',
                  trailing: FilledButton.icon(
                    onPressed: () => _write(context, ref),
                    icon: const Icon(Icons.edit_outlined, size: 16),
                    label: Text(service.signedIn ? '글쓰기' : '로그인하고 쓰기'),
                  )),
              const _LoopNotice(),
              const SizedBox(height: AppSpace.md),
              ChipRow<String?>(
                options: _categories,
                selected: _category,
                onChanged: (v) => setState(() => _category = v),
              ),
              const SizedBox(height: AppSpace.md),
              async.when(
                loading: () => const Padding(
                  padding: EdgeInsets.all(AppSpace.xl),
                  child: Center(child: CircularProgressIndicator()),
                ),
                error: (e, _) => Text('불러오지 못했습니다: $e', style: text.bodyMedium),
                data: (posts) => posts.isEmpty
                    ? Padding(
                        padding: const EdgeInsets.symmetric(vertical: AppSpace.xl),
                        child: Center(
                            child: Text('아직 글이 없습니다.', style: text.bodyMedium)),
                      )
                    : Column(
                        children: [for (final p in posts) _PostTile(post: p)]),
              ),
              const SizedBox(height: AppSpace.xxl),
            ],
          ),
        ),
      ],
    );
  }

  void _write(BuildContext context, WidgetRef ref) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      constraints: const BoxConstraints(maxWidth: 680),
      builder: (_) => const _WriteSheet(),
    );
  }
}

/// 게시판의 존재 이유를 한 줄로 설명한다.
/// '써봤자 아무 일도 안 일어난다'는 인상이 들면 아무도 쓰지 않는다.
class _LoopNotice extends StatelessWidget {
  const _LoopNotice();

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Card(
      color: AppColors.navy.withValues(alpha: 0.05),
      child: Padding(
        padding: const EdgeInsets.all(AppSpace.md),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Icon(Icons.sync_alt, size: 18, color: AppColors.navy),
          const SizedBox(width: AppSpace.sm),
          Expanded(
            child: Text(
              '학부모가 남긴 글 → 학원별로 집계 → 트리스코어의 평판·화제성에 반영 '
              '→ 주간 리포트로 되돌아옵니다. '
              '학원실록이 자동 생성한 글에는 작성자가 "학원실록"으로 표시되며, '
              '이 글들은 점수 계산에서 제외됩니다.',
              style: text.bodyMedium,
            ),
          ),
        ]),
      ),
    );
  }
}

class _PostTile extends StatelessWidget {
  final BoardPost post;
  const _PostTile({required this.post});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Card(
      margin: const EdgeInsets.only(bottom: AppSpace.sm),
      child: InkWell(
        borderRadius: BorderRadius.circular(AppRadius.md),
        onTap: () => context.go('/board/${post.id}'),
        child: Padding(
          padding: const EdgeInsets.all(AppSpace.md),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Chip2(post.categoryLabel,
                  color: post.isOfficial ? AppColors.navy : AppColors.slate),
              if (post.isOfficial) ...[
                const SizedBox(width: 5),
                const Chip2('학원실록 작성',
                    color: AppColors.gold, icon: Icons.auto_awesome),
              ],
              const Spacer(),
              Text('${post.createdAt.year}.${post.createdAt.month}.${post.createdAt.day}',
                  style: text.bodySmall),
            ]),
            const SizedBox(height: AppSpace.sm),
            Text(post.title, style: text.titleLarge, maxLines: 2),
            const SizedBox(height: 5),
            Text(post.body.replaceAll('\n', ' '),
                style: text.bodyMedium, maxLines: 2, overflow: TextOverflow.ellipsis),
            const SizedBox(height: AppSpace.sm),
            Row(children: [
              Text(post.nickname, style: text.labelMedium),
              const SizedBox(width: AppSpace.md),
              Icon(Icons.mode_comment_outlined, size: 13, color: AppColors.mist),
              const SizedBox(width: 3),
              Text('${post.commentCount}', style: text.bodySmall),
              const SizedBox(width: AppSpace.md),
              Icon(Icons.visibility_outlined, size: 13, color: AppColors.mist),
              const SizedBox(width: 3),
              Text('${post.viewCount}', style: text.bodySmall),
              if (post.academyKeys.isNotEmpty) ...[
                const Spacer(),
                Chip2('학원 ${post.academyKeys.length}곳 언급',
                    color: AppColors.reputation),
              ],
            ]),
          ]),
        ),
      ),
    );
  }
}

class _WriteSheet extends ConsumerStatefulWidget {
  const _WriteSheet();
  @override
  ConsumerState<_WriteSheet> createState() => _WriteSheetState();
}

class _WriteSheetState extends ConsumerState<_WriteSheet> {
  final _title = TextEditingController();
  final _body = TextEditingController();
  final _email = TextEditingController();
  String _category = 'talk';
  bool _busy = false;
  String? _notice;

  @override
  void dispose() {
    _title.dispose();
    _body.dispose();
    _email.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final service = ref.watch(boardServiceProvider);
    final sel = ref.watch(selectionProvider);

    return Padding(
      padding: EdgeInsets.fromLTRB(AppSpace.lg, 0, AppSpace.lg,
          MediaQuery.viewInsetsOf(context).bottom + AppSpace.lg),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(service.signedIn ? '글쓰기' : '로그인', style: text.headlineMedium),
            const SizedBox(height: AppSpace.md),
            if (!service.signedIn) ...[
              Text('이메일로 로그인 링크를 보내드립니다. 비밀번호는 만들지 않습니다.',
                  style: text.bodyMedium),
              const SizedBox(height: AppSpace.sm),
              TextField(
                controller: _email,
                keyboardType: TextInputType.emailAddress,
                decoration: const InputDecoration(
                    labelText: '이메일', border: OutlineInputBorder()),
              ),
              const SizedBox(height: AppSpace.md),
              FilledButton(
                onPressed: _busy
                    ? null
                    : () async {
                        setState(() => _busy = true);
                        try {
                          await Supabase.instance.client.auth.signInWithOtp(
                              email: _email.text.trim(),
                              emailRedirectTo: Uri.base.origin);
                          setState(() => _notice = '로그인 링크를 보냈습니다. 메일함을 확인해 주세요.');
                        } catch (e) {
                          setState(() => _notice = '전송 실패: $e');
                        } finally {
                          setState(() => _busy = false);
                        }
                      },
                child: Text(_busy ? '보내는 중…' : '로그인 링크 받기'),
              ),
            ] else ...[
              ChipRow<String>(
                options: const [
                  ('talk', '수다'),
                  ('question', '질문'),
                  ('review', '후기'),
                ],
                selected: _category,
                onChanged: (v) => setState(() => _category = v),
              ),
              const SizedBox(height: AppSpace.md),
              TextField(
                controller: _title,
                decoration: const InputDecoration(
                    labelText: '제목', border: OutlineInputBorder()),
              ),
              const SizedBox(height: AppSpace.sm),
              TextField(
                controller: _body,
                maxLines: 8,
                decoration: const InputDecoration(
                  labelText: '내용',
                  helperText: '학원 이름을 적으시면 그 학원 지표에 반영됩니다',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: AppSpace.md),
              FilledButton(
                onPressed: _busy
                    ? null
                    : () async {
                        if (_title.text.trim().length < 2 ||
                            _body.text.trim().length < 5) {
                          setState(() => _notice = '제목과 내용을 입력해 주세요');
                          return;
                        }
                        setState(() => _busy = true);
                        try {
                          await service.write(
                            title: _title.text.trim(),
                            body: _body.text.trim(),
                            category: _category,
                            regionId: sel.regionId,
                          );
                          if (!context.mounted) return;
                          ref.invalidate(boardListProvider);
                          Navigator.of(context).pop();
                        } catch (e) {
                          setState(() => _notice = '등록 실패: $e');
                        } finally {
                          if (mounted) setState(() => _busy = false);
                        }
                      },
                child: Text(_busy ? '등록 중…' : '등록'),
              ),
            ],
            if (_notice != null) ...[
              const SizedBox(height: AppSpace.md),
              Text(_notice!,
                  style: text.bodyMedium?.copyWith(color: AppColors.estimated)),
            ],
            const SizedBox(height: AppSpace.md),
            Text(
              '실명 사업자에 대한 글입니다. 사실과 다른 내용이나 비방은 삭제될 수 있습니다. '
              '학원 관계자는 학부모로 활동할 수 없습니다.',
              style: text.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}
