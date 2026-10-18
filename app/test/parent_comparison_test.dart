import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:edutree/core/env.dart';
import 'package:edutree/core/theme.dart';
import 'package:edutree/data/academy_detail.dart';
import 'package:edutree/data/comparison_articles.dart';
import 'package:edutree/data/models.dart';
import 'package:edutree/data/parent_comparison.dart';
import 'package:edutree/data/parent_decision.dart';
import 'package:edutree/data/repository.dart';
import 'package:edutree/data/source_notes.dart';
import 'package:edutree/features/compare/compare_page.dart';

Map<String, dynamic> evidence(
  String id,
  String text, {
  String? subject = 'math',
  String? band = 'elem_low',
  String? branch = 'direct',
  String? date = '2025-08-01',
}) => {
  'url': 'https://example.com/$id',
  'source': 'naver_blog',
  'snippet': text,
  'subject': subject,
  'band': band,
  'branch_basis': branch,
  'posted_at': date,
};

AcademyDetail academy(
  String id,
  List<Map<String, dynamic>> evidence, {
  Map<String, dynamic>? profile,
}) => AcademyDetail.evaluated(
  Academy.fromJson({
    'id': id,
    'name': '테스트 학원 $id',
    'subjects': ['math', 'english'],
    'gradeBandsBySubject': {
      'math': ['elem_low'],
      'english': ['high'],
    },
    'gradeTarget': {
      'basis': '공식 안내',
      'bandBasis': {
        'math': {'elem_low': 'reviews'},
        'english': {'high': 'official'},
      },
    },
    'score': {
      'total': 80,
      'reputation': 80,
      'momentum': 60,
      'sampleSize': 10,
      'confidence': 'medium',
      'isRanked': true,
    },
    'evidence': evidence,
    'profile': profile,
  }),
);

final homework = comparisonCriteria.firstWhere((c) => c.id == 'homework');

void main() {
  test(
    'comparison displays distinct source content, not counts or AI conclusions',
    () {
      final a = academy('1', [evidence('a', '숙제를 학원에서 마친 뒤 귀가했어요.')]);
      final b = academy('2', [evidence('b', '숙제는 집에서 풀고 다음 수업에서 확인했어요.')]);
      final x = comparisonExcerpts(
        a,
        homework,
        subject: 'math',
        gradeBand: 'elem_low',
      ).single;
      final y = comparisonExcerpts(
        b,
        homework,
        subject: 'math',
        gradeBand: 'elem_low',
      ).single;
      expect(x.text, '숙제를 학원에서 마친 뒤 귀가했어요.');
      expect(y.text, '숙제는 집에서 풀고 다음 수업에서 확인했어요.');
      expect(x.url, 'https://example.com/a');
      expect(x.dateLabel, contains('수강 시점 미확인'));
      expect(homework.meaning, contains('집에서 쓸 시간'));
      expect(a.academy!.score.total, 80);
    },
  );

  test(
    'other subjects, grades, brands, unlinked quotes and fees cannot explain a choice',
    () {
      final d = academy(
        '1',
        [
          evidence('good', '숙제는 집에서 풀어요.'),
          evidence('subject', '영어 숙제', subject: 'english'),
          evidence('grade', '고등 숙제', band: 'high'),
          evidence('brand', '다른 지점 숙제', branch: 'brand'),
          evidence('branch', '지점 미상 숙제', branch: null),
          evidence('fee', '숙제가 있고 수강료 20만원입니다.'),
          {...evidence('unsafe', '숙제'), 'url': 'javascript:alert(1)'},
        ],
        profile: {
          'homework': {
            'note': '모든 학생에게 완벽한 학원',
            'load': '하',
            'quotes': [
              {'url': 'https://example.com/unlinked', 'quote': '숙제가 없어요.'},
            ],
          },
        },
      );
      final rows = comparisonExcerpts(
        d,
        homework,
        subject: 'math',
        gradeBand: 'elem_low',
      );
      expect(rows.map((r) => r.url), ['https://example.com/good']);
      expect(rows.single.text, isNot(contains('완벽')));
    },
  );

  test(
    'unknown scope stays explicit and cannot outrank known scope by recency',
    () {
      final d = academy('1', [
        evidence(
          'unknown',
          '숙제를 점검해요.',
          subject: null,
          band: null,
          date: '2026-10-01',
        ),
        evidence('known', '숙제는 집에서 풀어요.', date: '2024-02-01'),
      ]);
      final rows = comparisonExcerpts(
        d,
        homework,
        subject: 'math',
        gradeBand: 'elem_low',
      );
      expect(rows.first.url, endsWith('/known'));
      expect(rows.last.scope, '과목 미확인 · 학년 미확인');
      expect(
        comparisonQuestion(homework, [rows.last], 'math', 'elem_low'),
        contains('이 글이'),
      );
      expect(rows.first.dateLabel, contains('2024-02-01'));
    },
  );

  test(
    'profile quotes retain self-description, source date and distinct URL count',
    () {
      final d = academy(
        '1',
        [evidence('a', '숙제 지도')],
        profile: {
          'homework': {
            'quotes': [
              {
                'url': 'https://example.com/a',
                'quote': '매일 숙제를 지도합니다.',
                'kind': 'self',
                'postedAt': '2025-02-30',
              },
              {'url': 'https://example.com/a', 'quote': '숙제 중복 인용'},
            ],
          },
        },
      );
      final row = comparisonExcerpts(
        d,
        homework,
        subject: 'math',
        gradeBand: 'elem_low',
      ).single;
      expect(row.selfDescription, isTrue);
      expect(row.text, '매일 숙제를 지도합니다.');
      expect(row.postedAt, isNull);
    },
  );

  test(
    'grade provenance is scoped, absent scope is not rejection or a zero score',
    () {
      final d = academy('1', []);
      expect(comparisonTarget(d, 'math', 'elem_low').label, '공개 글에 대상 학년 언급');
      expect(comparisonTarget(d, 'math', 'high').label, contains('대상 자료 없음'));
      expect(comparisonTarget(d, 'science', 'elem_low').label, '과학 운영 자료 없음');
      final registry = AcademyDetail.listed(
        RegistryEntry.fromJson({
          'id': '99',
          'name': '등록부 학원',
          'subjects': ['math'],
        }),
      );
      expect(
        comparisonExcerpts(
          registry,
          homework,
          subject: 'math',
          gradeBand: 'elem_low',
        ),
        isEmpty,
      );
      expect(
        comparisonTarget(registry, 'math', 'elem_low').explanation,
        contains('확인하지 못했어요'),
      );
      expect(registry.academy, isNull);
    },
  );

  test('a topic quotation appears before a newer generic introduction', () {
    final d = academy(
      '1',
      [
        evidence('intro', '수업과 숙제 이야기를 소개할게요.', date: '2026-09-01'),
        evidence('specific', '우리 반 숙제 이야기', date: '2025-03-01'),
      ],
      profile: {
        'homework': {
          'quotes': [
            {
              'url': 'https://example.com/specific',
              'quote': '숙제는 집에서 풀고 선생님이 오답을 확인했어요.',
            },
          ],
        },
      },
    );
    final rows = comparisonExcerpts(
      d,
      homework,
      subject: 'math',
      gradeBand: 'elem_low',
    );
    expect(rows.first.text, '숙제는 집에서 풀고 선생님이 오답을 확인했어요.');
    expect(rows.length, 2);
  });

  test(
    'official guidance keeps academy, primary source and subject boundaries',
    () {
      final d = academy('1', []);
      SourceNote note(
        String url, {
        String subject = 'math',
        String scope = 'branch',
        String kind = 'official',
      }) => SourceNote(
        topic: '수업·교재',
        title: '진도 안내',
        summary: '개별 진도와 오답 수업을 소개합니다.',
        url: url,
        checkedAt: '2025-10-01',
        subjects: [subject],
        sourceScope: scope,
        kind: kind,
      );
      final g = AcademySources(
        academyId: '1',
        name: '학원',
        scope: 'branch',
        caveat: '반별 확인 필요',
        notes: [
          note('https://example.com/math'),
          note('https://example.com/english', subject: 'english'),
          note('https://example.com/brand', scope: 'brand'),
          note('https://example.com/directory', kind: 'directory'),
        ],
      );
      final c = comparisonCriteria.firstWhere((c) => c.id == 'curriculum');
      expect(comparisonGuidance(d, c, 'math', g).map((n) => n.url), [
        'https://example.com/math',
      ]);
      expect(comparisonGuidance(academy('2', []), c, 'math', g), isEmpty);
      expect(
        comparisonQuestion(c, [], 'math', 'high', hasGuidance: true),
        contains('고등 수학 반에도 적용되나요'),
      );
    },
  );

  for (final size in [320.0, 768.0, 1440.0]) {
    testWidgets(
      'comparison remains meaningful at $size and double text size',
      (tester) async {
        tester.view.physicalSize = Size(size, 1200);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.reset);
        final a = academy('1', [evidence('a', '숙제를 학원에서 마친 뒤 귀가했어요.')]);
        final b = academy('2', [evidence('b', '숙제는 집에서 풀고 다음 수업에서 확인했어요.')]);
        final container = ProviderContainer(
          overrides: [
            sourceNotesProvider.overrideWith((_) async => []),
            comparisonArticlesProvider.overrideWith((_) async => []),
            academyDetailProvider('1').overrideWith((_) async => a),
            academyDetailProvider('2').overrideWith((_) async => b),
          ],
        );
        addTearDown(container.dispose);
        container.read(parentConcernProvider.notifier).choose('homework');
        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp(
              theme: buildTheme(dark: size == 768),
              home: Scaffold(
                body: MediaQuery(
                  data: MediaQueryData(
                    size: Size(size, 1200),
                    textScaler: const TextScaler.linear(2),
                  ),
                  child: const ComparePage(ids: '1,2'),
                ),
              ),
            ),
          ),
        );
        await tester.pumpAndSettle();
        expect(find.text('숙제와 집에서의 부담'), findsOneWidget);
        expect(find.text('“숙제를 학원에서 마친 뒤 귀가했어요.”'), findsOneWidget);
        expect(find.text('“숙제는 집에서 풀고 다음 수업에서 확인했어요.”'), findsOneWidget);
        expect(find.text('공통으로 상담에서 확인할 항목'), findsOneWidget);
        expect(find.text('배우는 내용과 진도'), findsOneWidget);
        // Exercise the longer cells rather than just the initial viewport.
        await tester.ensureVisible(find.text('“숙제는 집에서 풀고 다음 수업에서 확인했어요.”'));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
        container.read(selectionProvider.notifier).setGradeBand('high');
        await tester.pumpAndSettle();
        expect(find.text('“숙제를 학원에서 마친 뒤 귀가했어요.”'), findsNothing);
        expect(find.text('이 조건에서는 수업의 차이를 판단할 자료가 부족해요.'), findsOneWidget);
        expect(tester.takeException(), isNull);
        container.read(parentConcernProvider.notifier).choose(null);
      },
      skip: !Env.parentCompareEnabled,
    );
  }
}
