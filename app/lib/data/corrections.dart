import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../core/env.dart';

/// 학원 관계자 정정 요청 접수.
///
/// 로그인을 요구하지 않는다 — 관계자에게 가입을 강요하면 창구가 아니라
/// 문턱이 된다. 접수분은 공개 화면에 노출되지 않고 운영자 검토 후에만
/// 데이터에 반영된다. 자동 반영하지 않는 이유: 창구가 곧 편집권이 되면
/// 그건 또 다른 왜곡이다.
class CorrectionService {
  final SupabaseClient? _db;
  CorrectionService(this._db);

  bool get enabled => _db != null;

  Future<void> submit({
    required String academyKey,
    required String academyName,
    required String requester,
    required String contact,
    required String kind, // fix | claim | remove
    required String message,
  }) async {
    await _db!.from('corrections').insert({
      'academy_key': academyKey,
      'academy_name': academyName,
      'requester': requester,
      'contact': contact,
      'claim_type': kind,
      'body': message,
    });
  }
}

final correctionServiceProvider = Provider<CorrectionService>(
    (ref) => CorrectionService(Env.hasSupabase ? Supabase.instance.client : null));
