import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../core/env.dart';

/// 근거 한 줄에 대한 이의 접수.
///
/// 정정 요청(corrections)이 학원 단위라면 이쪽은 **주장 단위**다. 후기
/// 한 줄이 틀렸을 때 그 줄만 빼려고 만들었다 — 글 전체를 무효화하면
/// 같은 글의 멀쩡한 평판 근거까지 함께 사라진다.
///
/// 접수는 반영이 아니다. 운영자가 판정해야 다음 실행에서 빠진다.
/// 창구가 곧 편집권이 되면 그건 또 다른 왜곡이다 — corrections 와 같은
/// 판단이다. 예외 하나: 사유가 '지금은 다름'이고 그 주장이 2년 넘은
/// 것이면 파이프라인이 자동으로 넘긴다. 낡음은 가짜가 아니다.
enum DisputeReason {
  notTrue('not_true', '사실이 아닙니다'),
  outdated('outdated', '지금은 다릅니다'),
  otherAcademy('other_academy', '다른 학원 이야기입니다'),
  ad('ad', '광고입니다'),
  other('other', '기타');

  const DisputeReason(this.code, this.label);
  final String code;
  final String label;
}

class ClaimDisputeService {
  final SupabaseClient? _db;
  ClaimDisputeService(this._db);

  bool get enabled => _db != null;

  Future<void> submit({
    required String claimId,
    required String academyKey,
    required String claimKind,
    required String quote,
    required DisputeReason reason,
    String? note,
  }) async {
    await _db!.from('claim_disputes').insert({
      'claim_id': claimId,
      'academy_key': academyKey,
      'claim_kind': claimKind,
      // 접수 시점의 인용문을 함께 남긴다. 판정 화면에서 운영자가 무엇을
      // 두고 하는 말인지 알아야 하는데, 주장은 매 실행 다시 지어지므로
      // 판정할 때 원문이 남아 있다는 보장이 없다.
      'quote': quote,
      'reason': reason.code,
      'note': note,
    });
  }
}

final claimDisputeServiceProvider = Provider<ClaimDisputeService>(
  (ref) =>
      ClaimDisputeService(Env.hasSupabase ? Supabase.instance.client : null),
);
