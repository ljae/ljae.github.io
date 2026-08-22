import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../core/env.dart';

/// 게시판.
///
/// 학원실록이 만든 글(is_official)과 학부모 글을 같은 목록에 두되 반드시
/// 구분해 표시한다. 자동 생성 글을 사람 글인 척 섞으면 그 순간 이 서비스가
/// 걸러내겠다고 공언한 바로 그것이 된다.
class BoardPost {
  final String id;
  final String category;
  final String? regionId;
  final String title;
  final String body;
  final bool isOfficial;
  final String? officialKind;
  final List<String> academyKeys;
  final String nickname;
  final int viewCount;
  final int commentCount;
  final DateTime createdAt;

  const BoardPost({
    required this.id,
    required this.category,
    this.regionId,
    required this.title,
    required this.body,
    required this.isOfficial,
    this.officialKind,
    required this.academyKeys,
    required this.nickname,
    required this.viewCount,
    required this.commentCount,
    required this.createdAt,
  });

  factory BoardPost.fromRow(Map<String, dynamic> r) {
    final profile = (r['profiles'] as Map?)?.cast<String, dynamic>();
    return BoardPost(
      id: r['id'] as String,
      category: (r['category'] ?? 'talk') as String,
      regionId: r['region_id'] as String?,
      title: (r['title'] ?? '') as String,
      body: (r['body'] ?? '') as String,
      isOfficial: (r['is_official'] ?? false) as bool,
      officialKind: r['official_kind'] as String?,
      academyKeys: ((r['academy_keys'] as List?) ?? const []).cast<String>(),
      nickname: (r['is_official'] == true)
          ? '학원실록'
          : (profile?['nickname'] ?? '학부모') as String,
      viewCount: (r['view_count'] as num?)?.toInt() ?? 0,
      commentCount: (r['comment_count'] as num?)?.toInt() ?? 0,
      createdAt: DateTime.tryParse('${r['created_at']}') ?? DateTime.now(),
    );
  }

  String get categoryLabel => switch (category) {
        'report' => '주간 리포트',
        'guide' => '단계 해설',
        'question' => '질문',
        'review' => '후기',
        _ => '수다',
      };
}

class BoardComment {
  final String id;
  final String nickname;
  final String body;
  final DateTime createdAt;
  const BoardComment({
    required this.id,
    required this.nickname,
    required this.body,
    required this.createdAt,
  });

  factory BoardComment.fromRow(Map<String, dynamic> r) {
    final profile = (r['profiles'] as Map?)?.cast<String, dynamic>();
    return BoardComment(
      id: r['id'] as String,
      nickname: (profile?['nickname'] ?? '학부모') as String,
      body: (r['body'] ?? '') as String,
      createdAt: DateTime.tryParse('${r['created_at']}') ?? DateTime.now(),
    );
  }
}

const _postSelect =
    'id, category, region_id, title, body, is_official, official_kind, '
    'academy_keys, view_count, comment_count, created_at, profiles(nickname)';

class BoardService {
  const BoardService();
  SupabaseClient get _db => Supabase.instance.client;
  String? get uid => _db.auth.currentUser?.id;
  bool get signedIn => uid != null;

  Future<List<BoardPost>> list({String? regionId, String? category}) async {
    var q = _db.from('board_posts').select(_postSelect).eq('status', 'published');
    if (regionId != null && regionId != 'all') q = q.eq('region_id', regionId);
    if (category != null) q = q.eq('category', category);
    final rows = await q.order('created_at', ascending: false).limit(60);
    return (rows as List)
        .map((r) => BoardPost.fromRow((r as Map).cast<String, dynamic>()))
        .toList();
  }

  /// 특정 학원을 언급한 글. 학원 상세에서 '이 학원 이야기'로 보여준다.
  Future<List<BoardPost>> forAcademy(String academyId) async {
    final rows = await _db
        .from('board_posts')
        .select(_postSelect)
        .contains('academy_keys', [academyId])
        .eq('status', 'published')
        .order('created_at', ascending: false)
        .limit(20);
    return (rows as List)
        .map((r) => BoardPost.fromRow((r as Map).cast<String, dynamic>()))
        .toList();
  }

  Future<List<BoardComment>> comments(String postId) async {
    final rows = await _db
        .from('board_comments')
        .select('id, body, created_at, profiles(nickname)')
        .eq('post_id', postId)
        .eq('status', 'published')
        .order('created_at');
    return (rows as List)
        .map((r) => BoardComment.fromRow((r as Map).cast<String, dynamic>()))
        .toList();
  }

  Future<void> write({
    required String title,
    required String body,
    String category = 'talk',
    String? regionId,
    List<String> academyKeys = const [],
  }) async {
    final id = uid;
    if (id == null) throw StateError('로그인이 필요합니다');
    await _db.from('board_posts').insert({
      'title': title,
      'body': body,
      'category': category,
      'region_id': regionId == 'all' ? null : regionId,
      'author_id': id,
      'academy_keys': academyKeys,
      'is_official': false,
    });
  }

  Future<void> comment(String postId, String body) async {
    final id = uid;
    if (id == null) throw StateError('로그인이 필요합니다');
    await _db.from('board_comments')
        .insert({'post_id': postId, 'author_id': id, 'body': body});
  }

  Future<void> bumpView(String postId) async {
    try {
      await _db.rpc<void>('bump_view', params: {'p_id': postId});
    } catch (_) {/* 조회수는 실패해도 무시 */}
  }
}

final boardServiceProvider = Provider((ref) => const BoardService());

final boardListProvider = FutureProvider.family<List<BoardPost>, (String?, String?)>(
    (ref, key) async {
  if (!Env.hasSupabase) return const [];
  return ref.watch(boardServiceProvider).list(regionId: key.$1, category: key.$2);
});

final boardCommentsProvider =
    FutureProvider.family<List<BoardComment>, String>((ref, postId) async {
  if (!Env.hasSupabase) return const [];
  return ref.watch(boardServiceProvider).comments(postId);
});

final academyBoardProvider =
    FutureProvider.family<List<BoardPost>, String>((ref, academyId) async {
  if (!Env.hasSupabase) return const [];
  return ref.watch(boardServiceProvider).forAcademy(academyId);
});
