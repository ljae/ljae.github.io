import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../core/env.dart';

/// 학원실록 자체 후기.
///
/// 커뮤니티에서 긁어온 글과 성격이 다르다. 작성자가 로그인해 있고, 별점과
/// 관점이 구조화돼 있고, 수강 기간이 함께 들어온다. 그래서 평판 점수에서
/// 스크랩 스니펫보다 높은 신뢰도를 받는다.
///
/// Supabase 키가 없으면 이 계층 전체가 비활성이고, 앱은 후기 UI 를 감춘다.
class UserReview {
  final String id;
  final String academyId;
  final String nickname;
  final int rating;
  final String body;
  final Map<String, dynamic> aspects;

  /// 구조화 태그 — 학년·과목·키워드. '초2 학부모의 수학 후기'만 걸러
  /// 보는 일이 가능해지는 축이다.
  final String? gradeBand;
  final String? subject;
  final List<String> tags;

  final DateTime createdAt;
  final bool isMine;

  const UserReview({
    required this.id,
    required this.academyId,
    required this.nickname,
    required this.rating,
    required this.body,
    required this.aspects,
    this.gradeBand,
    this.subject,
    this.tags = const [],
    required this.createdAt,
    this.isMine = false,
  });

  factory UserReview.fromRow(Map<String, dynamic> r, String? myId) => UserReview(
        id: r['id'] as String,
        academyId: (r['academy_key'] ?? r['academy_id'] ?? '') as String,
        nickname: (r['nickname'] ?? '익명') as String,
        rating: (r['rating'] as num).toInt(),
        body: (r['body'] ?? '') as String,
        aspects: (r['aspects'] as Map?)?.cast<String, dynamic>() ?? const {},
        gradeBand: r['grade_band'] as String?,
        subject: r['subject'] as String?,
        tags: ((r['tags'] as List?) ?? const []).cast<String>(),
        createdAt:
            DateTime.tryParse('${r['created_at']}') ?? DateTime.now(),
        isMine: myId != null && r['author_id'] == myId,
      );
}

class ReviewService {
  const ReviewService();

  SupabaseClient get _db => Supabase.instance.client;
  String? get currentUserId => _db.auth.currentUser?.id;
  bool get signedIn => currentUserId != null;

  Future<List<UserReview>> forAcademy(String academyId) async {
    final rows = await _db
        .from('user_reviews')
        .select('id, academy_key, rating, body, aspects, grade_band, subject, tags, '
        'created_at, author_id, '
            'profiles(nickname)')
        .eq('academy_key', academyId)
        .eq('status', 'published')
        .order('created_at', ascending: false)
        .limit(50);

    return (rows as List).map((r) {
      final row = (r as Map).cast<String, dynamic>();
      final profile = (row['profiles'] as Map?)?.cast<String, dynamic>();
      row['nickname'] = profile?['nickname'];
      return UserReview.fromRow(row, currentUserId);
    }).toList();
  }

  /// 이메일 링크 로그인. 카카오·구글은 콘솔에서 공급자를 붙인 뒤 확장한다.
  Future<void> signInWithEmail(String email) =>
      _db.auth.signInWithOtp(email: email, emailRedirectTo: Uri.base.origin);

  Future<void> signOut() => _db.auth.signOut();

  Future<void> submit({
    required String academyId,
    required int rating,
    required String body,
    Map<String, int> aspects = const {},
    String? gradeBand,
    String? subject,
    List<String> tags = const [],
    DateTime? attendedFrom,
    DateTime? attendedTo,
  }) async {
    final uid = currentUserId;
    if (uid == null) {
      throw StateError('로그인이 필요합니다');
    }
    await _db.from('user_reviews').upsert({
      'academy_key': academyId,
      'author_id': uid,
      'rating': rating,
      'body': body,
      'aspects': aspects,
      'grade_band': gradeBand,
      'subject': subject,
      'tags': tags,
      'attended_from': attendedFrom?.toIso8601String().split('T').first,
      'attended_to': attendedTo?.toIso8601String().split('T').first,
    }, onConflict: 'academy_key,author_id');
  }
}

final reviewServiceProvider = Provider((ref) => const ReviewService());

/// 로그인 상태 스트림. Supabase 가 없으면 항상 로그아웃 상태.
final authStateProvider = StreamProvider<AuthState?>((ref) {
  if (!Env.hasSupabase) return Stream.value(null);
  return Supabase.instance.client.auth.onAuthStateChange;
});

final reviewsProvider =
    FutureProvider.family<List<UserReview>, String>((ref, academyId) async {
  if (!Env.hasSupabase) return const [];
  ref.watch(authStateProvider);
  return ref.watch(reviewServiceProvider).forAcademy(academyId);
});
