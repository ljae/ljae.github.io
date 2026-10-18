import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:edutree/core/theme.dart';
import 'package:edutree/data/comparison_articles.dart';
import 'package:edutree/data/parent_comparison.dart';
import 'package:edutree/features/compare/comparison_articles_panel.dart';
import 'parent_comparison_test.dart' as fixture;

Map<String, dynamic> record({
  String id = 'pair',
  List<String> ids = const ['1', '2'],
}) => {
  'id': id,
  'title': '두 곳의 수업 비교',
  'url': 'https://blog.example.com/$id',
  'author': '작성자',
  'publishedAt': '2023-06-27',
  'reviewedAt': '2026-10-18',
  'subject': 'math',
  'status': 'reviewed',
  'access': 'public',
  'reviewMethod': 'full_text',
  'reason': '반 배정과 숙제에 대한 학원별 설명이 있습니다.',
  'scopeNote': '선택 지점의 현재 반 운영은 문의해야 합니다.',
  'experienceNote': '수강 경험과 조사 내용이 섞인 글입니다. 광고 여부 미확인.',
  'gradeBands': ['elem_low'],
  'academies': [
    for (final id in ids)
      {
        'academyId': id,
        'label': '학원 $id',
        'mapping': 'address',
        'locator': '학원 $id 본문 절',
        'criteria': ['homework', 'entry'],
      },
  ],
};

List<ComparisonArticleMatch> matches(
  List<Map<String, dynamic>> records, {
  List<String> ids = const ['1', '2'],
  String subject = 'math',
  String grade = 'elem_low',
}) => matchComparisonArticles(
  records.map(ComparisonArticle.fromJson).toList(),
  ids,
  subject: subject,
  gradeBand: grade,
);

void main() {
  test(
    'partial triple names the uncovered school; complete coverage is first',
    () {
      final rows = matches(
        [
          record(),
          record(id: 'triple', ids: ['1', '2', '3']),
        ],
        ids: ['1', '2', '3'],
      );
      expect(rows.first.coverageLabel, '선택한 3곳 중 3곳을 다룬 글');
      expect(rows.last.coverageLabel, '선택한 3곳 중 2곳을 다룬 글');
      expect(rows.last.missingIds, ['3']);
      expect(matches([record()], ids: ['1', '1']), isEmpty);
    },
  );
  test('names or title alone cannot pass substantive body coverage', () {
    final weak = record();
    (weak['academies'] as List)[1]['criteria'] = ['entry'];
    expect(matches([weak]), isEmpty);
    final missingLocator = record();
    (missingLocator['academies'] as List)[0]['locator'] = '';
    expect(matches([missingLocator]), isEmpty);
    final unrelated = record();
    (unrelated['academies'] as List)[1]['criteria'] = [
      'curriculum',
      'feedback',
    ];
    expect(matches([unrelated]), isEmpty); // no two common axes
    expect(matches([record()], ids: ['1', '99']), isEmpty);
  });
  test('unreadable, unreviewed, unsafe and wrong-scope records stay out', () {
    for (final change in [
      {'status': 'candidate'},
      {'status': 'withdrawn'},
      {'access': 'login'},
      {'reviewMethod': 'search_snippet'},
      {'url': 'javascript:alert(1)'},
      {'publishedAt': '2025-02-30'},
      {'reviewedAt': ''},
    ]) {
      expect(
        matches([
          {...record(), ...change},
        ]),
        isEmpty,
        reason: '$change',
      );
    }
    expect(matches([record()], subject: 'english'), isEmpty);
    expect(matches([record()], grade: 'high'), isEmpty);
    final unscoped = matches([
      {...record(), 'gradeBands': <String>[]},
    ], grade: 'high').single;
    expect(unscoped.article.gradeLabel, '학년 미확인');
  });
  test(
    'brand context remains explicit and never matches another branch ID',
    () {
      final brand = record();
      (brand['academies'] as List)[0]['mapping'] = 'brand';
      expect(matches([brand]).single.needsBranchCheck, isTrue);
      expect(matches([brand], ids: ['99', '2']), isEmpty);
    },
  );
  test(
    'tracking and mobile duplicates collapse without dropping article IDs',
    () {
      expect(
        comparisonArticleKey(
          'https://m.blog.naver.com/parent/123?utm_source=x#top',
        ),
        comparisonArticleKey(
          'https://blog.naver.com/PostView.naver?blogId=parent&logNo=123',
        ),
      );
      expect(
        comparisonArticleKey('https://blog.example.com/view?id=1'),
        isNot(comparisonArticleKey('https://blog.example.com/view?id=2')),
      );
      final a = {
        ...record(),
        'url': 'https://sample.tistory.com/m/8?utm_source=abc',
      };
      final b = {
        ...record(id: 'copy'),
        'url': 'https://sample.tistory.com/8#part2',
      };
      expect(matches([a, b]).length, 1);
    },
  );
  test(
    'seed links have valid IDs, explicit scope and deliberate pair/triple coverage',
    () {
      final raw =
          (jsonDecode(
                    File(
                      'assets/research/comparison_articles.json',
                    ).readAsStringSync(),
                  )
                  as List)
              .map((j) => Map<String, dynamic>.from(j as Map))
              .toList();
      final data = raw.map(ComparisonArticle.fromJson).toList();
      final knownIds = <String>{
        for (final path in [
          'assets/data/academies.json',
          'assets/data/registry.json',
        ])
          for (final row in jsonDecode(File(path).readAsStringSync()) as List)
            (row as Map)['id'] as String,
      };
      expect(
        data
            .expand((a) => a.academies)
            .every((a) => knownIds.contains(a.academyId)),
        isTrue,
      );
      expect(data.length, 4);
      expect(data.every((a) => a.isReviewed), isTrue);
      expect(data.map((a) => a.id).toSet().length, data.length);
      final english = matchComparisonArticles(
        data,
        ['3000018730', '1000036573', '26427'],
        subject: 'english',
        gradeBand: 'elem_low',
      );
      expect(english.single.matched.length, 3);
      expect(english.single.commonCriteria, isNot(contains('homework')));
      expect(
        matchComparisonArticles(
          data,
          ['14435', '3000030122', '3000018730'],
          subject: 'math',
          gradeBand: 'elem_low',
        ).every((m) => m.missingIds.single == '3000018730'),
        isTrue,
      );
      final broadTitle = data.firstWhere(
        (a) => a.id == 'griminii-math-20250405',
      );
      expect(broadTitle.academies.length, 2); // CMS/Cmath merely mentioned
      expect(broadTitle.gradeLabel, '학년 미확인');
      expect(data.first.isHistorical(DateTime(2026, 10, 18)), isTrue);
    },
  );
  test('separate criteria do not inherit unrelated curriculum quotations', () {
    final d = fixture.academy(
      '1',
      [fixture.evidence('a', '교재와 진도 안내')],
      profile: {
        'curriculum': {
          'quotes': [
            {'url': 'https://example.com/a', 'quote': '교재는 반 진도에 맞춰 공부해요.'},
          ],
        },
      },
    );
    for (final id in ['feedback', 'atmosphere', 'entry', 'routine']) {
      expect(
        comparisonExcerpts(
          d,
          comparisonCriteria.firstWhere((c) => c.id == id),
          subject: 'math',
          gradeBand: 'elem_low',
        ),
        isEmpty,
      );
    }
    expect(orderedComparisonCriteria('questions').first.id, 'feedback');
    expect(comparisonCriteria.every((c) => c.checkpoints.length == 3), isTrue);
  });
  test(
    'admission tutoring and going home after homework do not describe school support or commute',
    () {
      final d = fixture.academy('1', [
        fixture.evidence('prep', '부족한 부분은 과외로 보충했다고 한다. 숙제를 마치고 귀가했다.'),
      ]);
      for (final id in ['feedback', 'routine']) {
        expect(
          comparisonExcerpts(
            d,
            comparisonCriteria.firstWhere((c) => c.id == id),
            subject: 'math',
            gradeBand: 'elem_low',
          ),
          isEmpty,
        );
      }
    },
  );
  for (final width in [320.0, 768.0, 1440.0]) {
    testWidgets(
      'article scope and uncovered school remain visible at $width with large text',
      (tester) async {
        tester.view.physicalSize = Size(width, 1200);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.reset);
        final data = matches([record()], ids: ['1', '2', '3']);
        await tester.pumpWidget(
          MaterialApp(
            theme: buildTheme(dark: width == 768),
            home: Scaffold(
              body: MediaQuery(
                data: const MediaQueryData(textScaler: TextScaler.linear(2)),
                child: SingleChildScrollView(
                  child: ComparisonArticlesPanel(
                    matches: data,
                    names: const {'3': '세 번째 학원'},
                  ),
                ),
              ),
            ),
          ),
        );
        expect(find.text('이 글에서 비교하지 않은 곳: 세 번째 학원'), findsOneWidget);
        expect(find.textContaining('글 작성 2023-06-27'), findsOneWidget);
        final disclosure = find.text('글의 범위·검토 정보');
        await tester.ensureVisible(disclosure);
        await tester.tap(disclosure);
        await tester.pumpAndSettle();
        expect(find.textContaining('본문·접근 확인 2026-10-18'), findsOneWidget);
        expect(find.textContaining('수강 경험과 조사 내용'), findsOneWidget);
        expect(tester.takeException(), isNull);
      },
    );
  }
}
