import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme.dart';
import '../../data/board.dart';
import '../../data/models.dart';
import '../../data/repository.dart';
import '../../widgets/common.dart';

/// 게시글 상세.
///
/// 목록 타일이 이 화면으로 보내고 있었는데 라우트가 없어 아무 일도
/// 일어나지 않았다. 글을 눌러도 안 열리는 게시판은 게시판이 아니다.
///
/// 목록에서 본문을 넘겨받지 않고 다시 읽는다. 링크로 바로 들어오는
/// 경우가 있고, 그때 목록을 거치지 않았다고 화면이 비면 안 된다.
class BoardPostPage extends ConsumerStatefulWidget {
  final String postId;
  const BoardPostPage({super.key, required this.postId});

  @override
  ConsumerState<BoardPostPage> createState() => _BoardPostPageState();
}

class _BoardPostPageState extends ConsumerState<BoardPostPage> {
  bool _bumped = false;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final async = ref.watch(boardPostProvider(widget.postId));

    return ListView(
      padding: const EdgeInsets.symmetric(vertical: AppSpace.lg),
      children: [
        ContentWidth(
          max: 820,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              TextButton.icon(
                onPressed: () => context.go('/board'),
                icon: const Icon(Icons.arrow_back, size: 16),
                label: const Text('게시판으로'),
                style: TextButton.styleFrom(padding: EdgeInsets.zero),
              ),
              const SizedBox(height: AppSpace.sm),
              async.when(
                loading: () => const Padding(
                  padding: EdgeInsets.symmetric(vertical: AppSpace.xxl),
                  child: Center(child: CircularProgressIndicator()),
                ),
                error: (e, _) =>
                    Text('글을 불러오지 못했습니다.\n$e', style: text.bodyMedium),
                data: (post) {
                  if (post == null) {
                    return Padding(
                      padding: const EdgeInsets.symmetric(vertical: AppSpace.xl),
                      child: Text(
                        '글을 찾을 수 없습니다. 삭제되었거나 주소가 잘못되었습니다.',
                        style: text.bodyLarge,
                      ),
                    );
                  }
                  // 조회수는 화면을 한 번 연 뒤에만 올린다. 실패해도 무시한다.
                  if (!_bumped) {
                    _bumped = true;
                    ref.read(boardServiceProvider).bumpView(post.id);
                  }
                  return _PostBody(post: post);
                },
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _PostBody extends ConsumerWidget {
  final BoardPost post;
  const _PostBody({required this.post});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final data = ref.watch(dataProvider).value;

    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Chip2(post.categoryLabel,
            color: post.isOfficial ? AppColors.navy : AppColors.slate),
        if (post.isOfficial) ...[
          const SizedBox(width: 5),
          const Chip2('학원실록 작성',
              color: AppColors.gold, icon: Icons.auto_awesome),
        ],
      ]),
      const SizedBox(height: AppSpace.sm),
      Text(post.title, style: text.headlineMedium),
      const SizedBox(height: 6),
      Row(children: [
        Text(post.nickname, style: text.labelMedium),
        const SizedBox(width: AppSpace.md),
        Text(
            '${post.createdAt.year}.${post.createdAt.month}.${post.createdAt.day}',
            style: text.bodySmall),
        const SizedBox(width: AppSpace.md),
        const Icon(Icons.visibility_outlined, size: 13, color: AppColors.mist),
        const SizedBox(width: 3),
        Text('${post.viewCount}', style: text.bodySmall),
      ]),
      const Divider(height: AppSpace.lg * 1.6),

      SelectionArea(child: Text(post.body, style: text.bodyLarge)),

      // 언급된 학원으로 건너갈 수 있게 한다. 글에서 이름만 보고 끝나면
      // 그 학원이 실제로 어떤 곳인지 확인할 길이 없다.
      if (post.academyKeys.isNotEmpty && data != null) ...[
        const SizedBox(height: AppSpace.xl),
        Text('이 글에서 언급된 학원', style: text.labelMedium),
        const SizedBox(height: 6),
        Wrap(spacing: AppSpace.sm, runSpacing: AppSpace.sm, children: [
          for (final key in post.academyKeys)
            if (data.academyById[key] case final Academy a)
              ActionChip(
                label: Text(a.displayName),
                onPressed: () => context.go('/academy/${a.id}'),
              ),
        ]),
      ],

      const SizedBox(height: AppSpace.xl),
      _Comments(postId: post.id),
      const SizedBox(height: AppSpace.xxl),
    ]);
  }
}

class _Comments extends ConsumerStatefulWidget {
  final String postId;
  const _Comments({required this.postId});

  @override
  ConsumerState<_Comments> createState() => _CommentsState();
}

class _CommentsState extends ConsumerState<_Comments> {
  final _body = TextEditingController();
  bool _busy = false;
  String? _notice;

  @override
  void dispose() {
    _body.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final body = _body.text.trim();
    if (body.length < 2) {
      setState(() => _notice = '내용을 입력해 주세요.');
      return;
    }
    setState(() { _busy = true; _notice = null; });
    try {
      await ref.read(boardServiceProvider).comment(widget.postId, body);
      _body.clear();
      ref.invalidate(boardCommentsProvider(widget.postId));
    } catch (e) {
      setState(() => _notice = '등록 실패: $e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final async = ref.watch(boardCommentsProvider(widget.postId));
    final signedIn = ref.watch(boardServiceProvider).signedIn;

    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const SectionHeader('댓글'),
      async.when(
        loading: () => const Padding(
          padding: EdgeInsets.all(AppSpace.md),
          child: Center(child: CircularProgressIndicator()),
        ),
        error: (e, _) => Text('불러오지 못했습니다: $e', style: text.bodyMedium),
        data: (rows) => rows.isEmpty
            ? Padding(
                padding: const EdgeInsets.symmetric(vertical: AppSpace.md),
                child: Text('아직 댓글이 없습니다. 첫 댓글을 남겨 주세요.',
                    style: text.bodyMedium),
              )
            : Column(children: [
                for (final c in rows)
                  Card(
                    margin: const EdgeInsets.only(bottom: AppSpace.sm),
                    child: Padding(
                      padding: const EdgeInsets.all(AppSpace.md),
                      child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(children: [
                              Text(c.nickname, style: text.labelLarge),
                              const Spacer(),
                              Text(
                                  '${c.createdAt.year}.${c.createdAt.month}.${c.createdAt.day}',
                                  style: text.bodySmall),
                            ]),
                            const SizedBox(height: 4),
                            Text(c.body, style: text.bodyMedium),
                          ]),
                    ),
                  ),
              ]),
      ),
      const SizedBox(height: AppSpace.sm),
      if (!signedIn)
        Text('댓글은 로그인 후 남길 수 있습니다. 학원 상세의 후기 영역에서 로그인하세요.',
            style: text.bodySmall)
      else ...[
        TextField(
          controller: _body,
          maxLines: 3,
          decoration: const InputDecoration(
            border: OutlineInputBorder(),
            hintText: '겪으신 경험을 나눠 주세요.',
          ),
        ),
        if (_notice != null) ...[
          const SizedBox(height: 6),
          Text(_notice!,
              style: text.bodySmall?.copyWith(color: AppColors.rising)),
        ],
        const SizedBox(height: AppSpace.sm),
        Align(
          alignment: Alignment.centerRight,
          child: FilledButton(
            onPressed: _busy ? null : _send,
            child: Text(_busy ? '등록 중…' : '댓글 등록'),
          ),
        ),
      ],
    ]);
  }
}
