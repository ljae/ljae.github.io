import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'browser_store.dart' as store;
import 'models.dart';

const ridingModes = {
  'unknown': '이동 방법 미정',
  'guardian': '보호자 직접 라이딩',
  'shuttle': '학원 셔틀 검토',
  'walk': '도보',
  'transit': '대중교통',
};
const ridingFits = {
  'unknown': '하원 동선 아직 미확인',
  'possible': '내 판단: 하원 동선 가능',
  'difficult': '내 판단: 하원 동선 조정 필요',
};

String ridingKey(String academyId, String subject, String band) =>
    '$academyId/$subject/$band';
bool _validKey(String key) {
  final p = key.split('/');
  return p.length == 3 &&
      RegExp(r'^\d{1,20}$').hasMatch(p[0]) &&
      subjectNames.containsKey(p[1]) &&
      gradeBandNames.containsKey(p[2]);
}

/// Personal observations, never an academy fact or automatically estimated route.
/// Scoped to the canonical academy, subject, and grade; never sent to a server.
class RidingPlan {
  final String mode, fit, updatedAt;
  final String? finish;
  final int? days, oneWayMinutes, guardianMinutes;
  const RidingPlan({
    this.mode = 'unknown',
    this.fit = 'unknown',
    this.days,
    this.oneWayMinutes,
    this.guardianMinutes,
    this.finish,
    required this.updatedAt,
  });
  int? get weeklyGuardianMinutes =>
      days == null || guardianMinutes == null ? null : days! * guardianMinutes!;
  bool get isValid =>
      ridingModes.containsKey(mode) &&
      ridingFits.containsKey(fit) &&
      (days == null || (days! >= 1 && days! <= 7)) &&
      (oneWayMinutes == null ||
          (oneWayMinutes! >= 0 && oneWayMinutes! <= 240)) &&
      (guardianMinutes == null ||
          (guardianMinutes! >= 0 && guardianMinutes! <= 1440)) &&
      (finish == null ||
          RegExp(r'^([01]\d|2[0-3]):[0-5]\d$').hasMatch(finish!)) &&
      DateTime.tryParse(updatedAt) != null;
  Map<String, dynamic> toJson() => {
    'mode': mode,
    'fit': fit,
    'days': days,
    'oneWayMinutes': oneWayMinutes,
    'guardianMinutes': guardianMinutes,
    'finish': finish,
    'updatedAt': updatedAt,
  };
  static RidingPlan? fromJson(Object? value) {
    try {
      final j = Map<String, dynamic>.from(value as Map);
      final plan = RidingPlan(
        mode: j['mode'] as String,
        fit: j['fit'] as String,
        days: j['days'] as int?,
        oneWayMinutes: j['oneWayMinutes'] as int?,
        guardianMinutes: j['guardianMinutes'] as int?,
        finish: j['finish'] as String?,
        updatedAt: j['updatedAt'] as String,
      );
      return plan.isValid ? plan : null;
    } catch (_) {
      return null;
    }
  }
}

class RidingPlans extends Notifier<Map<String, RidingPlan>> {
  static const storageKey = 'parent.riding.v1';
  @override
  Map<String, RidingPlan> build() {
    try {
      final data =
          jsonDecode(store.readPublic(storageKey) ?? '{}')
              as Map<String, dynamic>;
      return {
        for (final e in data.entries)
          if (_validKey(e.key) && RidingPlan.fromJson(e.value) != null)
            e.key: RidingPlan.fromJson(e.value)!,
      };
    } catch (_) {
      return {};
    }
  }

  bool save(String key, RidingPlan plan) {
    if (!_validKey(key) || !plan.isValid) {
      throw ArgumentError('Invalid riding plan');
    }
    state = {...state, key: plan};
    return _persist();
  }

  bool remove(String key) {
    state = {...state}..remove(key);
    return _persist();
  }

  bool _persist() => store.writePublic(
    storageKey,
    jsonEncode(state.map((key, value) => MapEntry(key, value.toJson()))),
  );
}

final ridingPlansProvider =
    NotifierProvider<RidingPlans, Map<String, RidingPlan>>(RidingPlans.new);

String ridingInquiry(RidingPlan? plan) => [
  '셔틀 정류장·운행 요일, 실제 반의 종료 시각과 직접 픽업할 때 대기 장소를 알려주세요.',
  if (plan?.mode == 'shuttle') '셔틀 이용을 검토 중입니다. 등원·하원 모두 이용 가능한가요?',
  if (plan?.finish != null)
    '하원 ${plan!.finish} 기준으로 동선을 검토 중인데, 실제 종료 시각과 보강일에도 맞출 수 있나요?',
  if (plan?.days != null) '주 ${plan!.days}회 일정으로 검토 중입니다. 가능한 수업 요일은 언제인가요?',
].join('\n');
