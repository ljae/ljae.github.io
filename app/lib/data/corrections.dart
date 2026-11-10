import 'dart:convert';
import 'dart:math';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../core/env.dart';
import 'browser_store.dart' as store;

/// Private correction receipt: local session stores only an unguessable capability.
class CorrectionService {
  final SupabaseClient? _db;
  Map<String, dynamic>? _pending;
  Map<String, dynamic>? _receipt;
  CorrectionService(this._db) {
    try {
      final raw = store.readSession('correction.receipt.v1');
      if (raw != null) {
        _receipt = Map<String, dynamic>.from(jsonDecode(raw) as Map);
      }
    } catch (_) {
      _receipt = null;
    }
  }
  bool get enabled => _db != null;
  bool hasReceiptFor(String key) => _receipt?['academyKey'] == key;
  String _secret() => base64Url
      .encode(List.generate(32, (_) => Random.secure().nextInt(256)))
      .replaceAll('=', '');
  String _id() {
    final bytes = List.generate(16, (_) => Random.secure().nextInt(256));
    bytes[6] = (bytes[6] & 15) | 64;
    bytes[8] = (bytes[8] & 63) | 128;
    final h = bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
    return '${h.substring(0, 8)}-${h.substring(8, 12)}-${h.substring(12, 16)}-${h.substring(16, 20)}-${h.substring(20)}';
  }

  Future<void> submit({
    required String academyKey,
    required String academyName,
    required String requester,
    required String contact,
    required String kind,
    required String message,
  }) async {
    final values = {
      'p_academy_key': academyKey,
      'p_academy_name': academyName,
      'p_requester': requester,
      'p_contact': contact,
      'p_kind': kind,
      'p_body': message,
    };
    if (_pending == null ||
        values.entries.any((e) => _pending![e.key] != e.value)) {
      _pending = {...values, 'p_id': _id(), 'p_secret': _secret()};
    }
    final request = Map<String, dynamic>.from(_pending!);
    final result = Map<String, dynamic>.from(
      await _db!.rpc<dynamic>('correction_submit_ai', params: request) as Map,
    );
    if (result['id'] != request['p_id']) {
      throw StateError('접수 확인을 받지 못했습니다. 같은 내용으로 다시 시도해주세요.');
    }
    _receipt = {
      'id': request['p_id'],
      'secret': request['p_secret'],
      'academyKey': academyKey,
    };
    store.writeSession('correction.receipt.v1', jsonEncode(_receipt));
    _pending = null;
  }

  Future<Map<String, dynamic>> status(String academyKey) async {
    if (!hasReceiptFor(academyKey)) {
      throw StateError('이 기기에 보관된 정정 확인 코드가 없습니다.');
    }
    return Map<String, dynamic>.from(
      await _db!.rpc<dynamic>(
            'correction_receipt_ai',
            params: {'p_id': _receipt!['id'], 'p_secret': _receipt!['secret']},
          )
          as Map,
    );
  }
}

final correctionServiceProvider = Provider<CorrectionService>(
  (ref) => CorrectionService(Env.hasSupabase ? Supabase.instance.client : null),
);
