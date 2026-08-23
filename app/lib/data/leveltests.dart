import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../core/env.dart';

/// 레벨테스트 일정.
///
/// 학부모가 가장 시간에 쫓기며 찾는 정보다. 폐쇄 커뮤니티가 이걸 쥐고
/// 있어서 검색으로는 안 나온다. 구조화해서 열어 두는 것이 우리가 할 수
/// 있는 일이다.
///
/// 학원 공지(official)와 학부모 제보(tip)를 구분해 표시한다. 확실성이
/// 다른 정보를 섞어 '일정'이라 부르면 헛걸음의 책임이 우리에게 온다.
class LevelTest {
  final String id;
  final String academyKey;
  final String academyName;
  final DateTime? testDate;
  final String? dateNote;
  final String? targetBand;
  final String? subject;
  final DateTime? applyUntil;
  final String? detail;
  final String? link;
  final bool official;

  const LevelTest({
    required this.id,
    required this.academyKey,
    required this.academyName,
    this.testDate,
    this.dateNote,
    this.targetBand,
    this.subject,
    this.applyUntil,
    this.detail,
    this.link,
    this.official = false,
  });

  factory LevelTest.fromRow(Map<String, dynamic> r) => LevelTest(
        id: r['id'] as String,
        academyKey: (r['academy_key'] ?? '') as String,
        academyName: (r['academy_name'] ?? '') as String,
        testDate: r['test_date'] == null
            ? null
            : DateTime.tryParse(r['test_date'] as String),
        dateNote: r['date_note'] as String?,
        targetBand: r['target_band'] as String?,
        subject: r['subject'] as String?,
        applyUntil: r['apply_until'] == null
            ? null
            : DateTime.tryParse(r['apply_until'] as String),
        detail: r['detail'] as String?,
        link: r['link'] as String?,
        official: (r['source_kind'] ?? 'tip') == 'official',
      );

  /// 날짜가 없으면 '매월 첫 주 토요일' 같은 고정 일정 설명을 쓴다.
  String get whenLabel {
    if (testDate != null) {
      return '${testDate!.month}월 ${testDate!.day}일';
    }
    return dateNote ?? '일정 미정';
  }
}

class LevelTestService {
  final SupabaseClient? _db;
  const LevelTestService(this._db);

  bool get enabled => _db != null;

  /// 지난 일정은 빼고 가져온다. 고정 일정(date_note)은 날짜가 없어 함께 온다.
  Future<List<LevelTest>> upcoming({String? academyKey}) async {
    if (_db == null) return const [];
    final today = DateTime.now().toIso8601String().split('T').first;
    var q = _db.from('level_tests').select().eq('status', 'published');
    if (academyKey != null) q = q.eq('academy_key', academyKey);
    final rows = await q
        .or('test_date.gte.$today,test_date.is.null')
        .order('test_date', ascending: true)
        .limit(60);
    return (rows as List)
        .map((r) => LevelTest.fromRow((r as Map).cast<String, dynamic>()))
        .toList();
  }
}

final levelTestServiceProvider = Provider<LevelTestService>((ref) =>
    LevelTestService(Env.hasSupabase ? Supabase.instance.client : null));

/// 학원별 일정. 상세 화면에서 쓴다.
final levelTestsProvider =
    FutureProvider.family<List<LevelTest>, String>((ref, academyKey) =>
        ref.watch(levelTestServiceProvider).upcoming(academyKey: academyKey));
