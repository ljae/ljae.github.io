import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:edutree/data/models.dart';
import 'package:edutree/features/academy/contact.dart';
import 'package:edutree/widgets/contact.dart';

Academy _academy({
  List<Evidence> evidence = const [],
  Map<String, FactCard> facts = const {},
  Map<String, AspectStat> aspects = const {},
  List<ClaimEvidence> sel = const [],
  int? capacity,
  List<String> aliases = const ['ILE', '아이엘이어학원'],
}) =>
    Academy(
      id: '1',
      name: '아이엘이어학원',
      displayNameRaw: '아이엘이',
      brand: 'ILE',
      aliases: aliases,
      regionId: 'daechi',
      subjects: const ['english'],
      gradeBands: const ['elem_low', 'elem_high'],
      stages: const [],
      flagship: const [],
      isVerified: true,
      dataSource: 'neis',
      capacity: capacity,
      score: const Score(
        total: 60,
        reputation: 60,
        momentum: 50,
        transparency: 80,
        selectivity: 70,
        sampleSize: 40,
        confidence: 'high',
        isRanked: true,
        momentumDirection: 'stable',
      ),
      evidence: evidence,
      facts: facts,
      aspects: aspects,
      selectivityEvidence: sel,
    );

Evidence _ev(int ref, String url, String title, String snippet) => Evidence(
      source: 'naver_blog',
      url: url,
      title: title,
      snippet: snippet,
      sentiment: 0.5,
      credibility: 0.8,
      ref: ref,
      inTitle: true,
      mentions: 2,
    );

void main() {
  test('nameTerms 는 두 글자 별칭을 빼고 긴 것부터 세운다', () {
    final terms = nameTerms(_academy(aliases: const ['ILE', '시대']));
    expect(terms.first, '아이엘이어학원');
    expect(terms, contains('아이엘이'));
    expect(terms, contains('ILE'));
    expect(terms, isNot(contains('시대')));
  });

  test('sourceRefs 는 근거 번호를 그대로 쓰고 새 원문에는 다음 번호를 준다', () {
    final a = _academy(
      evidence: [
        _ev(1, 'https://a', '첫 글', '아이엘이 좋아요'),
        _ev(2, 'https://b', '둘째 글', 'ILE 어려움'),
      ],
      sel: const [
        ClaimEvidence(claimId: 'x', kind: 'sel.waitlist', label: '대기', quote: 'q',
            url: 'https://b'),
        ClaimEvidence(claimId: 'y', kind: 'sel.full', label: '마감', quote: 'q',
            url: 'https://c'),
      ],
    );
    final refs = a.sourceRefs;
    expect(refs['https://a'], 1);
    expect(refs['https://b'], 2);   // 같은 원문은 같은 번호
    expect(refs['https://c'], 3);   // 근거 목록에 없던 원문은 그 다음
  });

  test('옛 번들(ref 없음)도 목록 순서로 번호를 받는다', () {
    final a = Academy.fromJson({
      'id': '1', 'name': 'x', 'regionId': 'daechi',
      'score': {'total': 1, 'reputation': 50, 'momentum': 50,
        'transparency': 50, 'selectivity': 50, 'sampleSize': 0,
        'confidence': 'low', 'isRanked': false, 'momentumDirection': 'stable'},
      'evidence': [
        {'source': 'naver_cafe', 'url': 'https://a', 'title': 't', 'snippet': 's'},
        {'source': 'naver_cafe', 'url': 'https://b', 'title': 't', 'snippet': 's'},
      ],
    });
    expect(a.evidence.map((e) => e.ref), [1, 2]);
    expect(a.evidence.first.matchLabel, '본문에 언급');
  });

  test('상담 전 확인 목록은 후기가 답한 것을 확인으로, 모르는 것을 질문으로 적는다', () {
    final a = _academy(
      facts: const {
        'fact.class_freq': FactCard(label: '수업 횟수', unit: '회/주', text: '2회~3회', value: 2, n: 5),
      },
      aspects: const {
        '가격': AspectStat(key: '가격', label: '비용', n: 3, mean: -0.4, positive: 0, negative: 3),
      },
      sel: const [
        ClaimEvidence(claimId: 'x', kind: 'sel.test_failed', label: '탈락', quote: 'q'),
      ],
      capacity: 120,
    );
    final items = buildChecklist(a);
    final byLabel = {for (final it in items) it.label: it};
    expect(byLabel['레벨테스트 일정 · 범위 · 재응시 가능 시기']!.confirmed, isTrue);
    expect(byLabel['레벨테스트 일정 · 범위 · 재응시 가능 시기']!.note, contains('탈락 사례 1건'));
    expect(byLabel['수업 횟수와 1회 수업 시간']!.note, contains('주 2회~3회'));
    expect(byLabel['교습비 외 교재비·추가 비용']!.note, contains('아쉽다고 말함'));
    expect(byLabel['정기 시험 주기와 결과 안내 방식']!.confirmed, isFalse);
    expect(byLabel['반 정원과 반 편성 기준']!.note, contains('120명'));
    expect(byLabel['우리 아이 학년 반이 열려 있는지']!.note, contains('예비초~초3'));
  });

  test('AspectStat.tone 은 숫자를 말로 옮긴다', () {
    const good = AspectStat(key: 'k', label: 'l', n: 3, mean: 0.5, positive: 3, negative: 0);
    const bad = AspectStat(key: 'k', label: 'l', n: 3, mean: -0.5, positive: 0, negative: 3);
    const mixed = AspectStat(key: 'k', label: 'l', n: 3, mean: 0.0, positive: 1, negative: 1);
    expect(good.tone, '좋게 말함');
    expect(bad.tone, '아쉽다고 말함');
    expect(mixed.tone, '엇갈림');
  });

  testWidgets('HighlightedText 는 띄어쓰기가 끼어도 이름을 굵게 찍는다', (tester) async {
    await tester.pumpWidget(const MaterialApp(
      home: Scaffold(
        body: HighlightedText(
          '대치 아이엘이 어학원 레테 후기, ILE 어렵다',
          terms: ['아이엘이어학원', '아이엘이', 'ILE'],
          highlight: TextStyle(fontWeight: FontWeight.w700),
        ),
      ),
    ));
    final rich = tester.widget<Text>(find.byType(Text));
    final span = rich.textSpan as TextSpan;
    final bold = span.children!
        .whereType<TextSpan>()
        .where((s) => s.style?.fontWeight == FontWeight.w700)
        .map((s) => s.text)
        .toList();
    expect(bold, ['아이엘이 어학원', 'ILE']);
  });

  testWidgets('RefMark 는 번호를 찍는다', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: Scaffold(body: RefMark(7))));
    expect(find.text('7'), findsOneWidget);
  });
}
