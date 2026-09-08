import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

import 'package:edutree/data/models.dart';
import 'package:edutree/data/repository.dart';

/// 학교 → 배정 아파트를 **번들 그대로** 이어 본다.
///
/// 2026-09-07 실측: schools.json 140곳 전부 `apartments: []` 였다.
/// 파이프라인의 학구 필드 이월(`_carry_zone_fields`)이 zoneId 가 있으면
/// 통째로 건너뛰어 `apartments`·`apartmentHouseholds` 가 빠졌고, 화면은
/// 모든 학교에서 '연결된 배정 아파트 정보가 없습니다' 를 냈다. 같은 번들의
/// apartments.json 은 단지마다 학교군을 온전히 갖고 있으므로 앱이 반대편에서
/// 잇는다(`MapData.apartmentsForSchool`). 여기서 그 이음을 실제 자료로 고정한다
/// — 자료가 바뀌어 다시 0 이 되면 이 시험이 먼저 안다.
void main() {
  late MapData data;

  setUpAll(() {
    // 테스트는 패키지 루트(app/)에서 돈다. rootBundle 대신 파일로 읽는다.
    final schools = (jsonDecode(
      File('assets/data/schools.json').readAsStringSync(),
    ) as List)
        .map((e) => School.fromJson((e as Map).cast<String, dynamic>()))
        .toList();
    final apartments = (jsonDecode(
      File('assets/data/apartments.json').readAsStringSync(),
    ) as List)
        .map((e) => Apartment.fromJson((e as Map).cast<String, dynamic>()))
        .toList();
    data = MapData(schools: schools, apartments: apartments);
  });

  test('학교 대부분이 색인으로 배정 아파트를 얻는다 (실측 114/140)', () {
    final linked = data.schools
        .where((s) => data.apartmentsForSchool(s).isNotEmpty)
        .toList();
    expect(data.schools.length, greaterThanOrEqualTo(100));
    expect(linked.length, greaterThanOrEqualTo(100),
        reason: '학교 ${data.schools.length}곳 중 ${linked.length}곳만 이어졌다');

    // 초등도 이어져야 한다 — 통학구역은 학교 하나짜리 구역이라 이름으로만
    // 이어지는 곳이 있다. zoneId 만 보면 초등이 통째로 빠진다.
    final elementary =
        linked.where((s) => s.level == 'elementary').length;
    expect(elementary, greaterThanOrEqualTo(40));
  });

  test('학교급이 다른 학교군은 잇지 않는다', () {
    for (final s in data.schools) {
      for (final (_, z) in data.apartmentsForSchool(s)) {
        expect(z.level == null || z.level == s.level, isTrue,
            reason: '${s.name}(${s.level}) 에 ${z.zoneName}(${z.level}) 이 붙었다');
      }
    }
  });

  test('한 단지는 한 학교에 한 번만 선다', () {
    for (final s in data.schools) {
      final ids = data.apartmentsForSchool(s).map((e) => e.$1.id).toList();
      expect(ids.toSet().length, ids.length, reason: s.name);
    }
  });

  test('파이프라인 값이 있으면 그것을 쓰고, 없으면 색인으로 잇는다', () {
    const given = School(
      id: 'x',
      name: '없는초등학교',
      level: 'elementary',
      levelLabel: '초등학교',
      regionId: 'daechi',
      apartments: [ZonedApartment(name: '어딘가', households: 10, certain: true)],
    );
    expect(data.zonedApartmentsFor(given).single.name, '어딘가');

    final joined = data.schools.firstWhere(
      (s) => s.apartments.isEmpty && data.apartmentsForSchool(s).isNotEmpty,
    );
    final rows = data.zonedApartmentsFor(joined);
    expect(rows, isNotEmpty);
    expect(rows.length, data.apartmentsForSchool(joined).length);
  });
}
