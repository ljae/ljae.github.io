import 'package:flutter_test/flutter_test.dart';
import 'package:edutree/data/models.dart';
import 'package:edutree/data/repository.dart';

Academy row(
  String id,
  List<String> bands, {
  int sample = 20,
  Map<String, List<String>>? perSubject,
}) => Academy.fromJson({
  'id': id,
  'name': id,
  'regionId': 'daechi',
  'subjects': ['math', 'english'],
  'gradeBands': bands,
  'gradeBandsBySubject': perSubject ?? <String, List<String>>{},
  'score': {'total': 80, 'reputation': 80, 'momentum': 50, 'confidence': 'high', 'sampleSize': sample, 'isRanked': sample >= 10},
});
EduTreeData data(List<Academy> rows) => EduTreeData(
  meta: Meta.fromJson({'mode': 'live'}),
  regions: [],
  tracks: [],
  academies: rows,
);
void main() {
  test('registry search finds the public MSC name without borrowing CMS', () {
    final msc = RegistryEntry.fromJson({'id':'msc', 'name':'엠에스씨학원', 'aliases':['MSC브레인컨설팅그룹 목동센터', 'MSC']});
    final cms = RegistryEntry.fromJson({'id':'cms', 'name':'씨엠에스학원'});
    expect(msc.matchesQuery(' msc '), isTrue);
    expect(msc.matchesQuery('브레인컨설팅'), isTrue);
    expect(cms.matchesQuery('msc'), isFalse);
    expect(msc.matchesQuery(''), isFalse);
  });
  test('unknown and high-only academies do not enter elementary ranking', () {
    final d = data([
      row('unknown', []),
      row('high', ['high']),
      row('elementary', ['elem_low']),
    ]);
    expect(
      d.ranking(regionId: 'daechi', gradeBand: 'elem_low').map((a) => a.id),
      ['elementary'],
    );
    expect(d.search('unknown'), isNotEmpty);
    expect(d.ranking(regionId: 'daechi').length, 3);
    expect(
      data([
        row('unknown', [], sample: 0),
      ]).unscored('daechi', gradeBand: 'elem_low'),
      isEmpty,
    );
  });
  test('elementary English cannot qualify academy for elementary math', () {
    final d = data([
      row(
        'mixed',
        ['elem_low', 'high'],
        perSubject: {
          'math': ['high'],
          'english': ['elem_low'],
        },
      ),
    ]);
    expect(
      d.ranking(regionId: 'daechi', subject: 'math', gradeBand: 'elem_low'),
      isEmpty,
    );
    expect(
      d
          .ranking(
            regionId: 'daechi',
            subject: 'english',
            gradeBand: 'elem_low',
          )
          .length,
      1,
    );
    expect(
      d.ranking(regionId: 'daechi', subject: 'math', gradeBand: 'high').length,
      1,
    );
  });
  test('registry filler requires matching grade and subject evidence', () {
    RegistryEntry entry(String id, List<String> bands) =>
        RegistryEntry.fromJson({
          'id': id,
          'name': id,
          'regionId': 'daechi',
          'subjects': ['math'],
          'gradeBands': bands,
        });
    final d = data([]);
    final got = d.registryFill(
      [
        entry('unknown', []),
        entry('high', ['high']),
        entry('elementary', ['elem_low']),
      ],
      regionId: 'daechi',
      gradeBand: 'elem_low',
      subject: 'math',
      have: 0,
    );
    expect(got.map((a) => a.id), ['elementary']);
  });
}
