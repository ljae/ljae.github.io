import 'package:edutree/data/repository.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  Map<String, dynamic> point(String? version, {String subject = 'math'}) => {
    'r': 1,
    't': 60,
    'n': 12,
    'version': version,
    'subject': version == null ? null : subject,
    'region': version == null ? null : 'daechi',
  };

  test('history only connects the latest continuous scoring context', () {
    final history = RankHistory.fromJson({
      'academies': {
        'A': {
          '2026-09-17': point('v2'),
          '2026-09-14': point(null),
          '2026-09-16': point('v2'),
          '2026-09-15': point('v1'),
        },
      },
    });
    expect(history.forAcademy('A').map((p) => p.day.day), [16, 17]);
  });

  test('a subject change breaks the series even if it later changes back', () {
    final history = RankHistory.fromJson({
      'academies': {
        'A': {
          '2026-09-15': point('v2'),
          '2026-09-16': point('v2', subject: 'science'),
          '2026-09-17': point('v2'),
        },
      },
    });
    expect(history.forAcademy('A').map((p) => p.day.day), [17]);
  });

  test('legacy history and empty history remain readable', () {
    final history = RankHistory.fromJson({
      'academies': {
        'A': {'2026-09-15': point(null), '2026-09-16': point(null)},
        'B': <String, dynamic>{},
      },
    });
    expect(history.forAcademy('A').length, 2);
    expect(history.forAcademy('B'), isEmpty);
  });
}
