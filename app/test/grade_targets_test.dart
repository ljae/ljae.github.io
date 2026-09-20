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
  'score': {
    'total': 80,
    'reputation': 80,
    'momentum': 50,
    'confidence': 'high',
    'sampleSize': sample,
    'isRanked': sample >= 10,
  },
});
EduTreeData data(List<Academy> rows) => EduTreeData(
  meta: Meta.fromJson({'mode': 'live'}),
  regions: [],
  tracks: [],
  academies: rows,
);
void main() {
  test('registry search finds the public MSC name without borrowing CMS', () {
    final msc = RegistryEntry.fromJson({
      'id': 'msc',
      'name': '엠에스씨학원',
      'aliases': ['MSC브레인컨설팅그룹 목동센터', 'MSC'],
    });
    final cms = RegistryEntry.fromJson({'id': 'cms', 'name': '씨엠에스학원'});
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
      ['elementary', 'unknown'],
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

  test('missing subject grade mapping does not borrow another subject', () {
    final academy = row(
      'only-english-grade',
      ['elem_low'],
      perSubject: {'english': ['elem_low']},
    );
    expect(academy.bandsForSubject('math'), isEmpty);
    expect(academy.bandsForSubject('english'), ['elem_low']);
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
    final got = d.registryMatches(
      [
        entry('unknown', []),
        entry('high', ['high']),
        entry('elementary', ['elem_low']),
      ],
      regionId: 'daechi',
      gradeBand: 'elem_low',
      subject: 'math',
    );
    expect(got.map((a) => a.id), ['elementary', 'unknown']);
  });
  test(
    'unknown grades stay discoverable without borrowing another subject',
    () {
      final d = data([
        row('unknown', []),
        row(
          'mathUnknown',
          ['elem_low'],
          perSubject: {
            'english': ['elem_low'],
            'math': [],
          },
        ),
        row('high', ['high']),
      ]);
      expect(
        d
            .unconfirmedGrades(regionId: 'daechi', subject: 'math')
            .map((a) => a.id),
        ['mathUnknown', 'unknown'],
      );
      expect(
        d.unconfirmedGrades(regionId: 'mokdong', subject: 'math'),
        isEmpty,
      );
      expect(d.unconfirmedGrades(regionId: 'all', subject: 'science'), isEmpty);
    },
  );

  test('registry lists every matching academy and excludes absorbed IDs', () {
    final d = data([
      Academy.fromJson({
        'id': 'scored',
        'name': 'scored',
        'registrationIds': ['absorbed'],
        'score': {
          'total': 50,
          'reputation': 50,
          'momentum': 50,
          'sampleSize': 0,
          'confidence': 'low',
          'isRanked': false,
        },
      }),
    ]);
    RegistryEntry entry(String id, List<String> bands) =>
        RegistryEntry.fromJson({
          'id': id,
          'name': id,
          'regionId': 'daechi',
          'subjects': ['math'],
          'gradeBands': bands,
        });
    final registry = [
      for (var i = 0; i < 15; i++) entry('listed$i', ['elem_low']),
      entry('scored', ['elem_low']),
      entry('absorbed', ['elem_low']),
      entry('unknown', []),
      entry('high', ['high']),
    ];
    expect(
      d
          .registryMatches(
            registry,
            regionId: 'daechi',
            subject: 'math',
            gradeBand: 'elem_low',
          )
          .length,
      15,
    );
    expect(
      d
          .registryMatches(
            registry,
            regionId: 'daechi',
            subject: 'math',
            unknownGradeOnly: true,
          )
          .map((r) => r.id),
      ['unknown'],
    );
  });

  test(
    'bundled academies remain discoverable in every region and subject',
    () async {
      TestWidgetsFlutterBinding.ensureInitialized();
      const repository = EduTreeRepository();
      final d = await repository.load();
      final registry = await repository.loadRegistry();
      for (final region in d.regions) {
        for (final subject in subjectNames.keys) {
          for (final band in gradeBandNames.keys) {
            final ids = [
              ...d
                  .ranking(
                    regionId: region.id,
                    subject: subject,
                    gradeBand: band,
                  )
                  .map((a) => a.id),
              ...d
                  .unscored(region.id, subject: subject, gradeBand: band)
                  .map((a) => a.id),
              ...d
                  .unconfirmedGrades(regionId: region.id, subject: subject)
                  .map((a) => a.id),
              ...d
                  .registryMatches(
                    registry,
                    regionId: region.id,
                    subject: subject,
                    gradeBand: band,
                  )
                  .map((a) => a.id),
              ...d
                  .registryMatches(
                    registry,
                    regionId: region.id,
                    subject: subject,
                    unknownGradeOnly: true,
                  )
                  .map((a) => a.id),
            ];
            final expected = {
              for (final a in d.academies)
                if (a.regionId == region.id &&
                    a.subjects.contains(subject) &&
                    (a.bandsForSubject(subject).isEmpty ||
                        a.bandsForSubject(subject).contains(band)))
                  a.id,
              for (final a in registry)
                if (a.regionId == region.id &&
                    a.subjects.contains(subject) &&
                    !d.academyById.containsKey(a.id) &&
                    (a.bandsForSubject(subject).isEmpty ||
                        a.bandsForSubject(subject).contains(band)))
                  a.id,
            };
            expect(ids.toSet(), expected, reason: '$region/$subject/$band');
            expect(ids.length, ids.toSet().length, reason: 'duplicate listing');
          }
        }
      }
    },
  );
}
