import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../core/env.dart';

/// 참조 글 검수.
///
/// 랭킹이 커뮤니티 글에서 나오는 이상, 어떤 글을 근거로 삼았는지
/// 사람이 확인할 수 있어야 한다. 자동 필터는 '윤도영 학원'과
/// '뮤지컬 배우 윤도영'을 구분하지 못한다 — 학원명이 본문에 있는지만
/// 보기 때문이다.
class MentionReview {
  final String urlHash;
  final String academyKey;
  final String academyName;
  final String title;
  final String snippet;
  final String source;
  final String? sourceUrl;
  final DateTime? postedAt;
  final String verdict;
  final String? rejectReason;

  const MentionReview({
    required this.urlHash,
    required this.academyKey,
    required this.academyName,
    required this.title,
    required this.snippet,
    required this.source,
    this.sourceUrl,
    this.postedAt,
    this.verdict = 'pending',
    this.rejectReason,
  });

  factory MentionReview.fromRow(Map<String, dynamic> r) => MentionReview(
        urlHash: r['url_hash'] as String,
        academyKey: (r['academy_key'] ?? '') as String,
        academyName: (r['academy_name'] ?? '') as String,
        title: (r['title'] ?? '') as String,
        snippet: (r['snippet'] ?? '') as String,
        source: (r['source'] ?? '') as String,
        sourceUrl: r['source_url'] as String?,
        postedAt: r['posted_at'] == null
            ? null
            : DateTime.tryParse(r['posted_at'] as String),
        verdict: (r['verdict'] ?? 'pending') as String,
        rejectReason: r['reject_reason'] as String?,
      );

  String get sourceLabel => switch (source) {
        'naver_blog' => '네이버 블로그',
        'naver_cafe' => '네이버 카페',
        'naver_kin' => '네이버 지식iN',
        'edutree_review' => '학원실록 후기',
        _ => source,
      };
}

/// 반려 사유. 이 목록이 곧 크롤러 개선의 재료다.
const rejectReasons = <String, String>{
  'person': '동명이인 (사람 이름)',
  'different_academy': '다른 학원',
  'ad': '광고·홍보글',
  'sale': '판매·중고거래',
  'irrelevant': '학원과 무관',
  'other': '기타',
};

/// 판정에서 뽑아낸 크롤 규칙. 사람이 만든 것이라 근거를 설명할 수 있고
/// 되돌릴 수도 있다.
class CrawlRule {
  final String id;
  final String scope;
  final String? academyKey;
  final String kind;
  final String pattern;
  final String reason;
  final int hits;
  final bool active;

  const CrawlRule({
    required this.id,
    required this.scope,
    this.academyKey,
    required this.kind,
    required this.pattern,
    required this.reason,
    this.hits = 0,
    this.active = true,
  });

  factory CrawlRule.fromRow(Map<String, dynamic> r) => CrawlRule(
        id: r['id'] as String,
        scope: (r['scope'] ?? 'global') as String,
        academyKey: r['academy_key'] as String?,
        kind: (r['kind'] ?? 'exclude_keyword') as String,
        pattern: (r['pattern'] ?? '') as String,
        reason: (r['reason'] ?? '') as String,
        hits: (r['hits'] as num?)?.toInt() ?? 0,
        active: (r['active'] ?? true) as bool,
      );

  String get kindLabel => switch (kind) {
        'exclude_keyword' => '이 말이 있으면 제외',
        'require_keyword' => '이 말이 없으면 제외',
        'exclude_domain' => '이 도메인 제외',
        _ => kind,
      };
}

class AdminService {
  final SupabaseClient? _db;
  const AdminService(this._db);

  bool get enabled => _db != null;
  bool get signedIn => _db?.auth.currentUser != null;

  /// 이 계정이 운영자인가. admins 표는 본인 행만 읽히므로,
  /// 한 건이라도 보이면 운영자다.
  Future<bool> isAdmin() async {
    if (_db == null || !signedIn) return false;
    try {
      final rows = await _db.from('admins').select('user_id').limit(1);
      return (rows as List).isNotEmpty;
    } catch (_) {
      return false;
    }
  }

  /// 로그인 링크. 후기와 같은 방식(비밀번호 없음)을 쓴다.
  Future<void> signIn(String email) =>
      _db!.auth.signInWithOtp(email: email, emailRedirectTo: Uri.base.origin);

  Future<List<MentionReview>> pending({String? academyKey}) async {
    if (_db == null) return const [];
    var q = _db.from('mention_reviews').select().eq('verdict', 'pending');
    if (academyKey != null) q = q.eq('academy_key', academyKey);
    final rows = await q.order('created_at', ascending: false).limit(200);
    return (rows as List)
        .map((r) => MentionReview.fromRow((r as Map).cast<String, dynamic>()))
        .toList();
  }

  Future<void> judge(String urlHash, String verdict,
      {String? reason, String? note}) async {
    await _db!.from('mention_reviews').update({
      'verdict': verdict,
      'reject_reason': reason,
      'note': note,
      'reviewed_at': DateTime.now().toIso8601String(),
    }).eq('url_hash', urlHash);
  }

  Future<List<CrawlRule>> rules() async {
    if (_db == null) return const [];
    final rows = await _db
        .from('crawl_rules')
        .select()
        .order('created_at', ascending: false)
        .limit(100);
    return (rows as List)
        .map((r) => CrawlRule.fromRow((r as Map).cast<String, dynamic>()))
        .toList();
  }

  /// 규칙에는 반드시 이유를 적는다. 왜 넣었는지 모르는 규칙은
  /// 나중에 지우지도 못하고 계속 남는다.
  Future<void> addRule({
    required String kind,
    required String pattern,
    required String reason,
    String scope = 'global',
    String? academyKey,
  }) async {
    await _db!.from('crawl_rules').upsert({
      'scope': scope,
      'academy_key': scope == 'academy' ? academyKey : null,
      'kind': kind,
      'pattern': pattern,
      'reason': reason,
      'active': true,
    }, onConflict: 'scope,academy_key,kind,pattern');
  }

  Future<void> toggleRule(String id, bool active) async {
    await _db!.from('crawl_rules').update({'active': active}).eq('id', id);
  }
}

final adminServiceProvider = Provider<AdminService>(
    (ref) => AdminService(Env.hasSupabase ? Supabase.instance.client : null));

final isAdminProvider =
    FutureProvider<bool>((ref) => ref.watch(adminServiceProvider).isAdmin());

final pendingReviewsProvider =
    FutureProvider.family<List<MentionReview>, String?>((ref, academyKey) =>
        ref.watch(adminServiceProvider).pending(academyKey: academyKey));

final crawlRulesProvider = FutureProvider<List<CrawlRule>>(
    (ref) => ref.watch(adminServiceProvider).rules());
