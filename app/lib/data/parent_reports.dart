import 'dart:convert';
import 'dart:math';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../core/env.dart';
import 'browser_store.dart' as store;
import 'models.dart';

/// 학부모 제보 — 학원 한 곳에 대한 30초짜리 구조화 답. 로그인 불요.
///
/// ★ **자유 서술도 연락처도 없다.** 그것이 이 창구의 개인정보 설계다.
///   적을 자리가 없으면 아이 이름도 전화번호도 들어올 수 없다. 학년도
///   정확한 학년이 아니라 학년대만 보낸다. 항목을 더할 때 물을 것:
///   그 칸에 사람이 문장을 적을 수 있는가. 있으면 넣지 않는다.
///
/// ★ **점수에 쓰이지 않는다.** 서버 표(supabase/18_parent_reports.sql)는
///   파이프라인이 수집 우선순위로만 읽는다. 화면 문구가 그렇게 약속하므로
///   이 값을 순위·정렬에 잇는 코드를 여기에 두지 않는다.
///
/// ★ **서버가 받았다고 답해야 접수다.** 백엔드가 없거나 실패하면 그렇게
///   말한다 — 화면에 성공이라 뜨고 아무 데도 안 간 폼이 이미 한 번 있었다.

/// 선택지. 키는 서버의 check 제약과 같아야 한다 — 시험이 순서까지 본다.
/// 학년대·과목의 이름과 차례는 앱의 다른 화면과 **같은 표**에서 온다
/// (`gradeBandNames`·`subjectOrder`). 여기 따로 적으면 언젠가 어긋난다.
final reportGradeBands = <(String, String)>[
  for (final e in gradeBandNames.entries) (e.key, e.value),
];
const reportRelations = <(String, String)>[
  ('current', '다니는 중'),
  ('past', '다녔음'),
  ('test_only', '레벨테스트만'),
  ('consulted', '상담만'),
];
final reportSubjects = <(String, String)>[
  for (final k in subjectOrder) (k, subjectNames[k]!),
];
const reportLevelTests = <(String, String)>[
  ('passed', '합격'),
  ('failed', '불합격'),
  ('waitlisted', '대기'),
  ('no_test', '시험 없음'),
  ('not_taken', '안 봄'),
];
const reportHomework = <(String, String)>[
  ('light', '적음'),
  ('medium', '보통'),
  ('heavy', '많음'),
];
const reportSessions = <int>[1, 2, 3, 4, 5, 6, 7];

String? _label(List<(String, String)> options, String? key) {
  for (final (k, label) in options) {
    if (k == key) return label;
  }
  return null;
}

bool _has(List<(String, String)> options, String? key) =>
    _label(options, key) != null;

/// 폼의 답 한 벌. 전부 고른 값이고, 적은 값은 하나도 없다.
class ParentReport {
  final String academyId;
  final String? gradeBand, relation, subject, levelTest, homework;
  final int? sessionsPerWeek;

  const ParentReport({
    required this.academyId,
    this.gradeBand,
    this.relation,
    this.subject,
    this.levelTest,
    this.sessionsPerWeek,
    this.homework,
  });

  /// 아직 안 고른 필수 항목. 비어 있어야 보낼 수 있다.
  List<String> get missing => [
    if (!_has(reportGradeBands, gradeBand)) '아이 학년대',
    if (!_has(reportRelations, relation)) '이 학원과의 관계',
  ];

  bool get valid =>
      RegExp(r'^[0-9A-Za-z_-]{1,64}$').hasMatch(academyId) &&
      missing.isEmpty &&
      (subject == null || _has(reportSubjects, subject)) &&
      (levelTest == null || _has(reportLevelTests, levelTest)) &&
      (homework == null || _has(reportHomework, homework)) &&
      (sessionsPerWeek == null || reportSessions.contains(sessionsPerWeek));

  /// 접수 화면에 되적는 줄. 보낸 것을 그대로 보여 준다 — 그 밖에 간 것이 없다.
  List<(String, String)> get lines => [
    ('아이 학년대', _label(reportGradeBands, gradeBand) ?? '—'),
    ('관계', _label(reportRelations, relation) ?? '—'),
    if (subject != null) ('과목', _label(reportSubjects, subject)!),
    if (levelTest != null) ('레벨테스트', _label(reportLevelTests, levelTest)!),
    if (sessionsPerWeek != null) ('수업 횟수', '주 $sessionsPerWeek회'),
    if (homework != null) ('숙제량', _label(reportHomework, homework)!),
  ];

  /// 같은 답인지. 재시도는 같은 요청 번호를 다시 써야 서버가 한 번만 센다.
  String get _signature =>
      '$academyId|$gradeBand|$relation|$subject|$levelTest|$sessionsPerWeek|$homework';

  /// RPC 인자. 고르지 않은 선택 항목은 **보내지 않는다**(null 로도).
  Map<String, dynamic> toParams({
    required String requestId,
    required String deviceHash,
  }) => {
    'p_request_id': requestId,
    'p_academy_key': academyId,
    'p_grade_band': gradeBand,
    'p_relation': relation,
    'p_device_hash': deviceHash,
    'p_subject': ?subject,
    'p_level_test': ?levelTest,
    'p_sessions_per_week': ?sessionsPerWeek,
    'p_homework': ?homework,
  };
}

/// 서버가 돌려주는 세 낱말.
enum ReportOutcome {
  /// 새로 받았다.
  ok,

  /// 이 기기가 이 학원에 이미 낸 답이 있어 새 답으로 고쳐 썼다(한 건으로 센다).
  duplicate,

  /// 하루 제한에 닿았다. **접수되지 않았다.**
  limited,
}

class ReportFailure implements Exception {
  final String code;
  final String message;
  const ReportFailure(this.code, this.message);
  @override
  String toString() => message;
}

/// 서버 호출. 인자를 받아 서버의 답(ok/duplicate/limited)을 돌려준다.
typedef ReportRequest = Future<Object?> Function(Map<String, dynamic> params);

typedef TokenRead = String? Function(String key);
typedef TokenWrite = bool Function(String key, String value);

const _deviceKey = 'parent.report.device.v1';
final _tokenShape = RegExp(r'^[A-Za-z0-9_-]{43}$');

String _randomToken() => base64Url
    .encode(List<int>.generate(32, (_) => Random.secure().nextInt(256)))
    .replaceAll('=', '');

String _uuid() {
  final b = List<int>.generate(16, (_) => Random.secure().nextInt(256));
  b[6] = (b[6] & 15) | 64;
  b[8] = (b[8] & 63) | 128;
  final h = b.map((v) => v.toRadixString(16).padLeft(2, '0')).join();
  return '${h.substring(0, 8)}-${h.substring(8, 12)}-${h.substring(12, 16)}-'
      '${h.substring(16, 20)}-${h.substring(20)}';
}

class ParentReportService {
  final ReportRequest? request;
  final TokenRead _read;
  final TokenWrite _write;

  /// 저장소를 못 쓸 때만 쓰는 토큰. 탭을 닫으면 사라진다.
  String? _memoryToken;
  bool _memorySpent = false;
  String? _pendingSignature, _pendingRequestId;

  ParentReportService(this.request, {TokenRead? read, TokenWrite? write})
    : _read = read ?? store.readPublic,
      _write = write ?? store.writePublic;

  /// 접수 서버가 연결돼 있는가. 아니면 화면이 그렇게 말해야 한다.
  bool get enabled => request != null;

  /// 기기 토큰과, 그것을 저장소에 붙들었는지.
  ///
  /// 서버에는 토큰이 아니라 그 sha256 만 간다. 저장소를 비우면 새 기기가
  /// 된다 — 사람을 가리키는 값이 아니다.
  (String token, bool persisted) _device() {
    final saved = _read(_deviceKey);
    if (saved != null && _tokenShape.hasMatch(saved)) return (saved, true);
    final fresh = _memoryToken ?? _randomToken();
    // 썼다는 답만 믿지 않고 되읽는다. 사파리 사생활 보호 모드는 쓰기가
    // 조용히 버려진다.
    if (_write(_deviceKey, fresh) && _read(_deviceKey) == fresh) {
      return (fresh, true);
    }
    _memoryToken = fresh;
    return (fresh, false);
  }

  /// 저장소를 못 쓰는 환경에서 한 번을 이미 보냈는가. 그 뒤로는 받지
  /// 않는다 — 새로 고칠 때마다 새 기기로 세어지는 답을 쌓지 않기 위해서다.
  bool get spent => _memorySpent;

  Future<ReportOutcome> submit(ParentReport report) async {
    final send = request;
    if (send == null) {
      throw const ReportFailure(
        'UNAVAILABLE',
        '지금은 제보를 받을 수 없습니다. 접수 서버가 연결되지 않아 저장되지 않았습니다.',
      );
    }
    if (!report.valid) {
      throw ReportFailure(
        'INVALID_INPUT',
        report.missing.isEmpty
            ? '선택한 값을 확인해주세요.'
            : '${report.missing.join(' · ')} 항목을 골라주세요.',
      );
    }
    final (token, persisted) = _device();
    if (!persisted && _memorySpent) {
      throw const ReportFailure(
        'STORAGE_REQUIRED',
        '이 브라우저는 저장소를 쓸 수 없어 한 번만 제보할 수 있습니다. 이미 한 번 접수했습니다.',
      );
    }
    if (_pendingSignature != report._signature || _pendingRequestId == null) {
      _pendingSignature = report._signature;
      _pendingRequestId = _uuid();
    }
    final Object? answer;
    try {
      answer = await send(
        report.toParams(
          requestId: _pendingRequestId!,
          deviceHash: sha256Hex(utf8.encode(token)),
        ),
      );
    } catch (_) {
      // 요청 번호를 남겨 둔다 — 같은 답을 다시 보내면 서버가 한 번만 센다.
      throw const ReportFailure(
        'RETRY_LATER',
        '보내지 못했습니다. 저장되지 않았습니다. 고른 답은 그대로 두었으니 다시 시도해주세요.',
      );
    }
    final outcome = switch (answer) {
      'ok' => ReportOutcome.ok,
      'duplicate' => ReportOutcome.duplicate,
      'limited' => ReportOutcome.limited,
      // 모르는 답을 성공으로 읽지 않는다.
      _ => throw const ReportFailure(
        'INVALID_RESPONSE',
        '접수 확인을 받지 못했습니다. 저장됐는지 알 수 없으니 다시 시도해주세요.',
      ),
    };
    _pendingSignature = null;
    _pendingRequestId = null;
    if (outcome != ReportOutcome.limited && !persisted) _memorySpent = true;
    return outcome;
  }
}

ReportRequest parentReportRequest(SupabaseClient db) =>
    (params) => db.rpc<Object?>('submit_parent_report', params: params);

final parentReportsProvider = Provider<ParentReportService>((ref) {
  if (!Env.hasSupabase) return ParentReportService(null);
  return ParentReportService(parentReportRequest(Supabase.instance.client));
});

// ── sha256 ──────────────────────────────────────────────────────────
//
// `crypto` 패키지는 다른 패키지를 따라 들어와 있을 뿐 이 앱의 직접
// 의존성이 아니다. 해시 한 번 때문에 의존성을 늘리지 않고 여기 둔다.
// FIPS 180-4 그대로이고 표준 시험값을 시험이 확인한다. 웹(JS 정수)에서도
// 같아야 하므로 덧셈마다 32비트로 자른다.

const _k = <int>[
  0x428a2f98,
  0x71374491,
  0xb5c0fbcf,
  0xe9b5dba5,
  0x3956c25b,
  0x59f111f1,
  0x923f82a4,
  0xab1c5ed5,
  0xd807aa98,
  0x12835b01,
  0x243185be,
  0x550c7dc3,
  0x72be5d74,
  0x80deb1fe,
  0x9bdc06a7,
  0xc19bf174,
  0xe49b69c1,
  0xefbe4786,
  0x0fc19dc6,
  0x240ca1cc,
  0x2de92c6f,
  0x4a7484aa,
  0x5cb0a9dc,
  0x76f988da,
  0x983e5152,
  0xa831c66d,
  0xb00327c8,
  0xbf597fc7,
  0xc6e00bf3,
  0xd5a79147,
  0x06ca6351,
  0x14292967,
  0x27b70a85,
  0x2e1b2138,
  0x4d2c6dfc,
  0x53380d13,
  0x650a7354,
  0x766a0abb,
  0x81c2c92e,
  0x92722c85,
  0xa2bfe8a1,
  0xa81a664b,
  0xc24b8b70,
  0xc76c51a3,
  0xd192e819,
  0xd6990624,
  0xf40e3585,
  0x106aa070,
  0x19a4c116,
  0x1e376c08,
  0x2748774c,
  0x34b0bcb5,
  0x391c0cb3,
  0x4ed8aa4a,
  0x5b9cca4f,
  0x682e6ff3,
  0x748f82ee,
  0x78a5636f,
  0x84c87814,
  0x8cc70208,
  0x90befffa,
  0xa4506ceb,
  0xbef9a3f7,
  0xc67178f2,
];

const _m = 0xffffffff;
int _rotr(int x, int n) => ((x >> n) | (x << (32 - n))) & _m;

/// 바이트열의 sha256 을 소문자 16진수 64자로.
String sha256Hex(List<int> bytes) {
  final bits = bytes.length * 8;
  final data = <int>[...bytes, 0x80];
  while (data.length % 64 != 56) {
    data.add(0);
  }
  // 길이는 64비트 빅엔디언. 시프트는 JS 에서 32비트라 나눗셈으로 뗀다.
  final high = bits ~/ 0x100000000, low = bits % 0x100000000;
  for (final word in [high, low]) {
    for (var s = 24; s >= 0; s -= 8) {
      data.add((word >> s) & 0xff);
    }
  }
  final h = <int>[
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, //
    0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
  ];
  final w = List<int>.filled(64, 0);
  for (var off = 0; off < data.length; off += 64) {
    for (var i = 0; i < 16; i++) {
      final j = off + i * 4;
      w[i] =
          ((data[j] << 24) |
              (data[j + 1] << 16) |
              (data[j + 2] << 8) |
              data[j + 3]) &
          _m;
    }
    for (var i = 16; i < 64; i++) {
      final s0 = _rotr(w[i - 15], 7) ^ _rotr(w[i - 15], 18) ^ (w[i - 15] >> 3);
      final s1 = _rotr(w[i - 2], 17) ^ _rotr(w[i - 2], 19) ^ (w[i - 2] >> 10);
      w[i] = (w[i - 16] + s0 + w[i - 7] + s1) & _m;
    }
    var a = h[0], b = h[1], c = h[2], d = h[3];
    var e = h[4], f = h[5], g = h[6], hh = h[7];
    for (var i = 0; i < 64; i++) {
      final s1 = _rotr(e, 6) ^ _rotr(e, 11) ^ _rotr(e, 25);
      final ch = (e & f) ^ ((~e & _m) & g);
      final t1 = (hh + s1 + ch + _k[i] + w[i]) & _m;
      final s0 = _rotr(a, 2) ^ _rotr(a, 13) ^ _rotr(a, 22);
      final maj = (a & b) ^ (a & c) ^ (b & c);
      final t2 = (s0 + maj) & _m;
      hh = g;
      g = f;
      f = e;
      e = (d + t1) & _m;
      d = c;
      c = b;
      b = a;
      a = (t1 + t2) & _m;
    }
    final next = [a, b, c, d, e, f, g, hh];
    for (var i = 0; i < 8; i++) {
      h[i] = (h[i] + next[i]) & _m;
    }
  }
  return h.map((v) => v.toRadixString(16).padLeft(8, '0')).join();
}
