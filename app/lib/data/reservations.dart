import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../core/env.dart';

/// 레벨테스트 예약 요청 · 잘못 붙은 근거 신고 · 행동 기록.
///
/// 셋 다 **접수**다. 예약을 대신 확정하지 않는다 — 학원과 제휴가 없고,
/// 확정처럼 보이는 접수는 헛걸음의 책임을 우리에게 가져온다. 운영자가
/// 학원에 연락해 잇고, 그 결과를 연락처로 회신한다.
///
/// 로그인을 요구하지 않는다(corrections 와 같은 이유). 접수분은 공개되지
/// 않는다 — 접수 목록이 보이면 그 자체가 학원 평가처럼 읽힌다.
class ReservationService {
  final SupabaseClient? _db;
  const ReservationService(this._db);

  bool get enabled => _db != null;

  Future<void> submit({
    required String academyKey,
    required String academyName,
    required String contact,
    String? parentName,
    String? childBand,
    String? subject,
    String? preferred,
    String? note,
  }) async {
    await _db!.from('test_reservations').insert({
      'academy_key': academyKey,
      'academy_name': academyName,
      'contact': contact,
      'parent_name': parentName,
      'child_band': childBand,
      'subject': subject,
      'preferred': preferred,
      'note': note,
    });
  }
}

/// 신고 사유. 자유 서술만 받으면 나중에 집계도 규칙도 못 만든다.
enum ReportReason {
  otherAcademy('other_academy', '다른 학원 이야기예요'),
  notReview('not_review', '학원 후기가 아니에요'),
  ad('ad', '광고·홍보글이에요'),
  outdated('outdated', '너무 오래된 이야기예요'),
  other('other', '기타');

  const ReportReason(this.code, this.label);
  final String code;
  final String label;
}

/// 근거 한 줄에 대한 '이 학원 글이 아니에요'.
///
/// 접수는 반영이 아니다. 파이프라인이 신고된 글을 질문 큐 맨 앞에 올리고,
/// 운영자의 답이 판정·규칙이 되어 다음 갱신에 반영된다. 익명 신고가 곧
/// 삭제가 되면 학원이 불리한 글만 지우는 통로가 된다.
class EvidenceReportService {
  final SupabaseClient? _db;
  const EvidenceReportService(this._db);

  bool get enabled => _db != null;

  Future<void> submit({
    required String urlHash,
    required String academyKey,
    String? sourceUrl,
    String? title,
    required ReportReason reason,
    String? note,
  }) async {
    await _db!.from('evidence_reports').insert({
      'url_hash': urlHash,
      'academy_key': academyKey,
      'source_url': sourceUrl,
      'title': title,
      'reason': reason.code,
      'note': note,
    });
  }
}

/// 전화·예약 버튼을 누른 사실만 남긴다. 누가 눌렀는지는 남기지 않는다.
///
/// 파이프라인이 30일 창으로 세어 **수집 우선순위**에만 쓴다 — 학부모가
/// 전화를 거는 학원은 우리가 근거를 더 찾아야 할 학원이지, 점수가 높은
/// 학원이 아니다. 실패해도 화면은 아무 일 없이 간다.
class ActionLogService {
  final SupabaseClient? _db;
  const ActionLogService(this._db);

  Future<void> log(String academyKey, String action) async {
    if (_db == null) return;
    try {
      await _db.from('academy_actions').insert({
        'academy_key': academyKey,
        'action': action,
      });
    } catch (_) {
      // 기록은 부산물이다. 못 남겨도 전화는 걸려야 한다.
    }
  }
}

final reservationServiceProvider = Provider<ReservationService>(
  (ref) => ReservationService(Env.hasSupabase ? Supabase.instance.client : null),
);

final evidenceReportServiceProvider = Provider<EvidenceReportService>(
  (ref) => EvidenceReportService(
      Env.hasSupabase ? Supabase.instance.client : null),
);

final actionLogProvider = Provider<ActionLogService>(
  (ref) => ActionLogService(Env.hasSupabase ? Supabase.instance.client : null),
);
