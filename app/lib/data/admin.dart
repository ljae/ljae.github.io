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
  // 브랜드는 맞지만 다른 지역 지점 이야기. 파이프라인의 지점 게이트가
  // 이미 대부분을 거르지만, 지역명을 안 쓰고 쓴 글은 사람만 알아본다.
  'other_region': '다른 지역 지점',
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
        'exclude_region' => '제목에 이 지역이 나오면 제외',
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
  ///
  /// 돌아올 곳에 해시(#/admin)를 넣을 수 없다. Supabase 가 redirect_to 에서
  /// fragment 를 떼어 버리기 때문이다 — 허용 목록에 넣어도 잘린다.
  /// 대신 쿼리로 표시하고, 앱이 뜰 때 그 표시를 보고 관리자 화면으로 옮긴다.
  Future<void> signIn(String email) => _db!.auth.signInWithOtp(
        email: email,
        emailRedirectTo: '${Uri.base.origin}/?next=admin',
      );

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
      {String? reason, String? note}) =>
      judgeMany([urlHash], verdict, reason: reason, note: note);

  /// 같은 글에 걸린 여러 학원을 한 번에 판정한다.
  Future<void> judgeMany(List<String> urlHashes, String verdict,
      {String? reason, String? note}) async {
    if (urlHashes.isEmpty) return;
    await _db!.from('mention_reviews').update({
      'verdict': verdict,
      'reject_reason': reason,
      'note': note,
      'reviewed_at': DateTime.now().toIso8601String(),
    }).inFilter('url_hash', urlHashes);
  }

  /// 재분류 — '이 글은 저 학원 글이다'.
  ///
  /// 반려와 다르다. 반려는 글을 버리지만 재분류는 **옮긴다.** 네 학원을
  /// 비교하는 글이 한 곳에만 붙었을 때, 버리면 멀쩡한 근거가 사라지고
  /// 어느 학원 글인지 사람이 아는 정보도 함께 사라진다.
  ///
  /// [keep] 은 그대로 둘 학원의 검수 키, [targets] 는 새로 붙일 학원 id.
  /// 넷 중 하나는 맞고 셋이 틀린 경우가 있어 둘을 따로 받는다.
  Future<void> reassign(
    List<String> urlHashes, {
    required List<String> keep,
    required List<String> targets,
  }) async {
    if (_db == null || urlHashes.isEmpty) return;
    final now = DateTime.now().toIso8601String();
    final drop = urlHashes.where((h) => !keep.contains(h)).toList();

    if (drop.isNotEmpty) {
      await _db.from('mention_reviews').update({
        'verdict': 'reclassified',
        'reject_reason': 'different_academy',
        'reviewed_at': now,
      }).inFilter('url_hash', drop);
    }
    if (keep.isNotEmpty) {
      await _db.from('mention_reviews').update({
        'verdict': 'confirmed',
        'reviewed_at': now,
      }).inFilter('url_hash', keep);
    }
    if (targets.isNotEmpty) {
      // 목적지는 글 단위다. 어느 행에 적혀 있든 파이프라인은 앞자리
      // (url_hash)만 보므로, 이 글의 모든 행에 같이 적어 둔다.
      await _db.from('mention_reviews').update({
        'reassign_to': targets,
      }).inFilter('url_hash', urlHashes);
    }
  }


  /// 대기 중인 질문. 우선순위(영향 추정치) 큰 것부터.
  Future<List<ReviewQuestion>> pendingQuestions() async {
    if (_db == null) return const [];
    final rows = await _db
        .from('review_questions')
        .select()
        .eq('status', 'pending')
        .order('priority', ascending: false)
        .limit(30);
    return (rows as List)
        .map((r) => ReviewQuestion.fromRow((r as Map).cast<String, dynamic>()))
        .toList();
  }

  /// 답을 남긴다. 실제 조치(판정·규칙·위키)는 다음 수집의
  /// apply_answers 가 한다 — 조치 경로는 기존 검수 체계 그대로다.
  Future<void> answerQuestion(String id,
      {String? value, String? text}) async {
    await _db!.from('review_questions').update({
      'status': 'answered',
      'answer': {'value': value, 'text': text},
      'answered_at': DateTime.now().toIso8601String(),
    }).eq('id', id);
  }

  /// 건너뛰기도 답이다 — 같은 질문이 다시 올라오지 않는다.
  Future<void> dismissQuestion(String id) async {
    await _db!.from('review_questions').update({
      'status': 'dismissed',
      'answered_at': DateTime.now().toIso8601String(),
    }).eq('id', id);
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

  // ── 접수함: 예약 요청 · 근거 신고 ──────────────────────────────
  //
  // 둘 다 앱이 로그인 없이 넣고 운영자만 읽는다. 예약은 운영자가 학원에
  // 연락해 잇고 회신하는 것이 처리이고, 신고는 파이프라인이 질문으로
  // 올리므로 여기서는 보고 닫기만 한다.

  Future<List<Reservation>> reservations({bool all = false}) async {
    if (_db == null) return const [];
    var q = _db.from('test_reservations').select();
    if (!all) q = q.eq('status', 'open');
    final rows = await q.order('created_at', ascending: false).limit(200);
    return (rows as List)
        .map((r) => Reservation.fromRow((r as Map).cast<String, dynamic>()))
        .toList();
  }

  Future<void> closeReservation(String id, String status,
      {String? note}) async {
    await _db!.from('test_reservations').update({
      'status': status,
      'handler_note': note,
      'handled_at': DateTime.now().toUtc().toIso8601String(),
    }).eq('id', id);
  }

  Future<List<EvidenceReport>> reports() async {
    if (_db == null) return const [];
    final rows = await _db
        .from('evidence_reports')
        .select()
        .inFilter('status', ['open', 'queued'])
        .order('created_at', ascending: false)
        .limit(200);
    return (rows as List)
        .map((r) => EvidenceReport.fromRow((r as Map).cast<String, dynamic>()))
        .toList();
  }

  Future<void> closeReport(String id, String status) async {
    await _db!.from('evidence_reports').update({'status': status}).eq('id', id);
  }
}

/// 레벨테스트 예약 요청 한 건.
class Reservation {
  final String id;
  final String academyKey;
  final String academyName;
  final String? parentName;
  final String contact;
  final String? childBand;
  final String? subject;
  final String? preferred;
  final String? note;
  final String status;
  final DateTime? createdAt;

  const Reservation({
    required this.id,
    required this.academyKey,
    required this.academyName,
    this.parentName,
    required this.contact,
    this.childBand,
    this.subject,
    this.preferred,
    this.note,
    required this.status,
    this.createdAt,
  });

  factory Reservation.fromRow(Map<String, dynamic> r) => Reservation(
        id: r['id'] as String,
        academyKey: (r['academy_key'] ?? '') as String,
        academyName: (r['academy_name'] ?? '') as String,
        parentName: r['parent_name'] as String?,
        contact: (r['contact'] ?? '') as String,
        childBand: r['child_band'] as String?,
        subject: r['subject'] as String?,
        preferred: r['preferred'] as String?,
        note: r['note'] as String?,
        status: (r['status'] ?? 'open') as String,
        createdAt: r['created_at'] == null
            ? null
            : DateTime.tryParse(r['created_at'] as String),
      );
}

/// '이 학원 글이 아니에요' 신고 한 건.
class EvidenceReport {
  final String id;
  final String urlHash;
  final String academyKey;
  final String? sourceUrl;
  final String? title;
  final String reason;
  final String? note;
  final String status;

  const EvidenceReport({
    required this.id,
    required this.urlHash,
    required this.academyKey,
    this.sourceUrl,
    this.title,
    required this.reason,
    this.note,
    required this.status,
  });

  factory EvidenceReport.fromRow(Map<String, dynamic> r) => EvidenceReport(
        id: r['id'] as String,
        urlHash: (r['url_hash'] ?? '') as String,
        academyKey: (r['academy_key'] ?? '') as String,
        sourceUrl: r['source_url'] as String?,
        title: r['title'] as String?,
        reason: (r['reason'] ?? 'other') as String,
        note: r['note'] as String?,
        status: (r['status'] ?? 'open') as String,
      );

  String get reasonLabel => switch (reason) {
        'other_academy' => '다른 학원 이야기',
        'not_review' => '학원 후기 아님',
        'ad' => '광고·홍보',
        'outdated' => '오래된 이야기',
        _ => '기타',
      };
}

final reservationsProvider = FutureProvider<List<Reservation>>(
    (ref) => ref.watch(adminServiceProvider).reservations());
final evidenceReportsProvider = FutureProvider<List<EvidenceReport>>(
    (ref) => ref.watch(adminServiceProvider).reports());

final adminServiceProvider = Provider<AdminService>(
    (ref) => AdminService(Env.hasSupabase ? Supabase.instance.client : null));

final isAdminProvider =
    FutureProvider<bool>((ref) => ref.watch(adminServiceProvider).isAdmin());


/// 파이프라인이 만든 질문 하나.
///
/// 글마다 읽는 검수 대신, 판단이 필요한 지점만 골라 묻는다. 답 하나가
/// 판정·규칙·위키 힌트가 되어 다음 수집부터 자동으로 적용된다 —
/// 같은 상황을 사람이 다시 볼 일이 없게 하는 것이 목적이다.
class ReviewQuestion {
  final String id;
  final String kind;
  final String? academyKey;
  final String? academyName;
  final String question;
  final Map<String, dynamic> payload;
  /// [{value, label}]. null 이면 자유 입력(동네 말 등).
  final List<Map<String, dynamic>>? options;
  final double priority;

  const ReviewQuestion({
    required this.id,
    required this.kind,
    this.academyKey,
    this.academyName,
    required this.question,
    this.payload = const {},
    this.options,
    this.priority = 0,
  });

  factory ReviewQuestion.fromRow(Map<String, dynamic> r) => ReviewQuestion(
        id: r['id'] as String,
        kind: (r['kind'] ?? '') as String,
        academyKey: r['academy_key'] as String?,
        academyName: r['academy_name'] as String?,
        question: (r['question'] ?? '') as String,
        payload: ((r['payload'] as Map?) ?? const {}).cast<String, dynamic>(),
        options: (r['options'] as List?)
            ?.map((e) => (e as Map).cast<String, dynamic>())
            .toList(),
        priority: (r['priority'] as num?)?.toDouble() ?? 0,
      );

  String get kindLabel => switch (kind) {
        'confirm_post' => '글 분류 확인',
        'exclude_word' => '규칙 후보',
        'locality' => '지점 변별어',
        'author' => '반복 작성자',
        'compare' => '중요도 비교',
        _ => kind,
      };
}

/// 같은 글을 하나로 묶은 검수 단위.
///
/// 한 글이 여러 학원을 언급하면 판정은 학원별로 나뉘어야 하지만
/// (한쪽에서 오검출이어도 다른 쪽에서는 정상 근거일 수 있다), 화면에서
/// 같은 글을 네 번 읽게 하는 것은 낭비다. 읽기는 한 번, 판정은 학원별로.
class ReviewGroup {
  final String title;
  final String snippet;
  final String source;
  final String? sourceUrl;
  final DateTime? postedAt;
  final List<MentionReview> items;

  const ReviewGroup({
    required this.title,
    required this.snippet,
    required this.source,
    this.sourceUrl,
    this.postedAt,
    required this.items,
  });

  List<String> get academyNames => [
        for (final i in items)
          i.academyName.isEmpty ? i.academyKey : i.academyName,
      ];

  String get sourceLabel => items.first.sourceLabel;

  /// 같은 원문끼리 묶는다. URL 이 없으면 제목으로 대신한다.
  static List<ReviewGroup> from(List<MentionReview> rows) {
    final byKey = <String, List<MentionReview>>{};
    for (final r in rows) {
      final key = (r.sourceUrl == null || r.sourceUrl!.isEmpty)
          ? 'title:${r.title}'
          : 'url:${r.sourceUrl}';
      byKey.putIfAbsent(key, () => []).add(r);
    }
    return [
      for (final items in byKey.values)
        ReviewGroup(
          title: items.first.title,
          snippet: items.first.snippet,
          source: items.first.source,
          sourceUrl: items.first.sourceUrl,
          postedAt: items.first.postedAt,
          items: items,
        ),
    ];
  }
}

final pendingReviewsProvider =
    FutureProvider.family<List<MentionReview>, String?>((ref, academyKey) =>
        ref.watch(adminServiceProvider).pending(academyKey: academyKey));


final pendingQuestionsProvider = FutureProvider<List<ReviewQuestion>>(
    (ref) => ref.watch(adminServiceProvider).pendingQuestions());

final crawlRulesProvider = FutureProvider<List<CrawlRule>>(
    (ref) => ref.watch(adminServiceProvider).rules());
