import 'dart:convert';
import 'dart:math';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../core/env.dart';
import 'browser_store.dart' as store;

const voiceCategories = <String, String>{
  'missing_info': '정보가 부족해요',
  'discovery_compare': '찾거나 비교하기 어려워요',
  'contact': '연락 경로가 불편해요',
  'feature_request': '이런 기능이 필요해요',
  'other': '기타',
};
const voiceStatuses = <String, String>{
  'received': '접수됨',
  'triaged': '검토 중',
  'planned': '개선 계획',
  'in_progress': '개선 중',
  'resolved': '수정·검증 완료',
  'declined': '반영 보류',
  'duplicate': '같은 문제와 함께 검토',
};
const voiceTransitions = <String, List<String>>{
  'received': ['triaged'],
  'triaged': ['planned', 'declined', 'duplicate'],
  'planned': ['in_progress', 'triaged'],
  'in_progress': ['resolved', 'triaged'],
  'resolved': ['triaged'],
  'declined': ['triaged'],
  'duplicate': ['triaged'],
};

class VoiceFailure implements Exception {
  final String code;
  final String message;
  final bool retryable;
  const VoiceFailure(this.code, this.message, {this.retryable = false});
  @override
  String toString() => message;
}

String _secret() => base64Url
    .encode(List<int>.generate(32, (_) => Random.secure().nextInt(256)))
    .replaceAll('=', '');
String _uuid() {
  final b = List<int>.generate(16, (_) => Random.secure().nextInt(256));
  b[6] = (b[6] & 15) | 64;
  b[8] = (b[8] & 63) | 128;
  final h = b.map((v) => v.toRadixString(16).padLeft(2, '0')).join();
  return '${h.substring(0, 8)}-${h.substring(8, 12)}-${h.substring(12, 16)}-${h.substring(16, 20)}-${h.substring(20)}';
}

bool validReceipt(String code) =>
    RegExp(r'^[0-9a-fA-F-]{36}\.[A-Za-z0-9_-]{43}$').hasMatch(code) &&
    RegExp(
      r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
    ).hasMatch(code.split('.').first);

typedef VoiceRequest =
    Future<Map<String, dynamic>> Function(
      String action,
      Map<String, dynamic> body,
    );

class ParentVoiceService {
  final VoiceRequest? request;
  Map<String, dynamic>? _pending;
  String? lastCode;
  bool receiptStored = false;
  ParentVoiceService(this.request) {
    final code = store.readSession('parent.receipt.v2');
    if (code != null && validReceipt(code)) lastCode = code;
  }
  bool get enabled => request != null;
  void forgetDraft() => _pending = null;
  void remember(String code) {
    if (!validReceipt(code)) {
      throw const VoiceFailure('INVALID_RECEIPT', '확인 코드 형식을 확인해주세요.');
    }
    lastCode = code;
    receiptStored = store.writeSession('parent.receipt.v2', code);
  }

  Future<Map<String, dynamic>> _send(
    String action,
    Map<String, dynamic> body,
  ) async {
    if (request == null) {
      throw const VoiceFailure('UNAVAILABLE', '현재 의견 접수를 준비 중입니다.');
    }
    try {
      return await request!(action, body);
    } on VoiceFailure {
      rethrow;
    } catch (_) {
      throw const VoiceFailure(
        'RETRY_LATER',
        '보내지 못했습니다. 입력을 유지했습니다. 다시 시도해주세요.',
        retryable: true,
      );
    }
  }

  Future<void> submit(String category, String note, {String? pageType}) async {
    final normalized = note.trim();
    if (!voiceCategories.containsKey(category) ||
        normalized.runes.length > 400) {
      throw const VoiceFailure('INVALID_INPUT', '유형과 400자 이내의 메모를 확인해주세요.');
    }
    if (_pending == null ||
        _pending!['category'] != category ||
        _pending!['note'] != normalized ||
        ((_pending!['context'] as Map?)?['pageType']) != pageType) {
      _pending = {
        'requestId': _uuid(),
        'receiptSecret': _secret(),
        'category': category,
        'note': normalized,
        if (pageType != null) 'context': {'pageType': pageType},
      };
    }
    final pending = Map<String, dynamic>.from(_pending!);
    try {
      final row = await _send('submit', pending);
      final code = '${row['receiptId']}.${pending['receiptSecret']}';
      if (row['status'] != 'received' || !validReceipt(code)) {
        throw const VoiceFailure(
          'INVALID_RESPONSE',
          '접수 확인 응답을 받지 못했습니다. 다시 시도해주세요.',
          retryable: true,
        );
      }
      remember(code);
      if (_pending?['requestId'] == pending['requestId']) _pending = null;
    } on VoiceFailure catch (e) {
      if (!e.retryable && _pending?['requestId'] == pending['requestId']) {
        _pending = null;
      }
      rethrow;
    }
  }

  Map<String, dynamic> _receipt() {
    if (lastCode == null || !validReceipt(lastCode!)) {
      throw const VoiceFailure('INVALID_RECEIPT', '확인 코드를 입력해주세요.');
    }
    final p = lastCode!.split('.');
    return {'receiptId': p[0], 'receiptSecret': p[1]};
  }

  Future<Map<String, dynamic>> status() => _send('status', _receipt());
  Future<void> delete() async {
    await _send('delete', _receipt());
    lastCode = null;
    store.writeSession('parent.receipt.v2', null);
  }
}

VoiceRequest parentVoiceRequest(SupabaseClient db) => (action, body) async {
  try {
    final r = await db.functions.invoke('parent-voice/$action', body: body);
    // functions_client decodes an empty 204 body as "", not a JSON map.
    if (action == 'delete' && r.status == 204) return {};
    return Map<String, dynamic>.from(r.data as Map? ?? {});
  } on FunctionException catch (e) {
    final d = e.details;
    if (d is Map) {
      throw VoiceFailure(
        d['code'] as String? ?? 'RETRY_LATER',
        d['message'] as String? ?? '처리하지 못했습니다.',
        retryable: d['retryable'] == true,
      );
    }
    throw const VoiceFailure(
      'RETRY_LATER',
      '처리하지 못했습니다. 다시 시도해주세요.',
      retryable: true,
    );
  }
};

final parentVoiceProvider = Provider<ParentVoiceService>((ref) {
  if (!Env.parentVoiceEnabled || !Env.hasSupabase) {
    return ParentVoiceService(null);
  }
  return ParentVoiceService(parentVoiceRequest(Supabase.instance.client));
});
final parentImprovementsProvider = FutureProvider<List<Map<String, dynamic>>>((
  ref,
) async {
  if (!Env.parentVoiceEnabled || !Env.hasSupabase) return [];
  final rows = await Supabase.instance.client
      .from('parent_improvements')
      .select('id,title,summary,published_at,verification_url')
      .order('published_at', ascending: false)
      .limit(10);
  return rows.map((r) => Map<String, dynamic>.from(r)).toList();
});
