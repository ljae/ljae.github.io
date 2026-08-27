import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:edutree/data/models.dart';
import 'package:edutree/data/repository.dart';
import 'package:edutree/widgets/annals.dart';
import 'package:edutree/widgets/wheel_selector.dart';
import 'package:edutree/features/techtree/roadmap_view.dart';

void main() {
  test('Score.pillar 는 각 기둥 값을 그대로 돌려준다', () {
    const score = Score(
      total: 61.2,
      reputation: 70,
      momentum: 40,
      transparency: 90,
      selectivity: 30,
      sampleSize: 24,
      confidence: 'medium',
      isRanked: true,
      momentumDirection: 'rising',
    );
    expect(score.pillar('reputation'), 70);
    expect(score.pillar('transparency'), 90);
    expect(score.confidenceLabel, '표본 보통');
  });

  test('Stage.gradeLabel 은 학년 코드를 한국식 표기로 바꾼다', () {
    const s = Stage(
      id: 'x', trackId: 't', title: '테스트',
      gradeMin: 4, gradeMax: 8, depth: 0, lane: 0,
    );
    expect(s.gradeLabel, '초4~중2');
    expect(Stage.gradeName(12), '고3');
  });

  test('예비초는 0으로 들어와 초1 앞에 놓인다', () {
    expect(Stage.gradeName(0), '예비초');
    const s = Stage(
      id: 'x', trackId: 't', title: '연산',
      gradeMin: 0, gradeMax: 3, depth: 0, lane: 0,
    );
    expect(s.gradeLabel, '예비초~초3');
  });

  test('학년 구간은 경계를 걸치면 양쪽 모두에 든다', () {
    // 사고력(초1~초4)은 저학년 학부모도 고학년 학부모도 함께 찾는 단계다.
    const spanning = Stage(
      id: 'x', trackId: 't', title: '사고력',
      gradeMin: 1, gradeMax: 4, depth: 0, lane: 0,
    );
    expect(spanning.gradeBands, ['elem_low', 'elem_high']);

    const single = Stage(
      id: 'y', trackId: 't', title: '수능',
      gradeMin: 10, gradeMax: 12, depth: 0, lane: 0,
    );
    expect(single.gradeBands, ['high']);
  });

  test('Selection.trackId 는 과목·학년구간을 트랙 키로 합친다', () {
    const sel = Selection(subject: 'math', gradeBand: 'elem_low');
    expect(sel.trackId, 'math_elem_low');
  });

  test('같은 값이면 같은 상태다 — 헛된 재구성을 막는 기준', () {
    const a = Selection(regionId: 'daechi', subject: 'math', gradeBand: 'middle');
    const b = Selection(regionId: 'daechi', subject: 'math', gradeBand: 'middle');
    expect(a, b);
    expect(a.hashCode, b.hashCode);
    expect(a == a.copyWith(gradeBand: 'high'), isFalse);
  });

  testWidgets('앱이 프로바이더 스코프 안에서 뜬다', (tester) async {
    await tester.pumpWidget(const ProviderScope(
      child: MaterialApp(home: Scaffold(body: Text('에듀트리'))),
    ));
    expect(find.text('에듀트리'), findsOneWidget);
  });

  testWidgets('목록이 늦게 도착해도 휠이 선택값을 가리킨다', (tester) async {
    // 학군 목록은 데이터가 도착해야 채워진다. 첫 빌드에는 '전체' 하나뿐이라
    // 'daechi' 를 못 찾고 휠이 0번 칸에 선다. 그 뒤 목록이 채워져도
    // selected 는 그대로라, 값 변화만 보던 예전 코드는 아무것도 하지 않았다.
    // 결과는 화면에 '전체', 실제 선택은 '대치' 였다.
    Widget wheel(List<(String, String)> options) => MaterialApp(
          home: Scaffold(
            body: WheelSelector<String>(
              label: '학군',
              options: options,
              selected: 'daechi',
              onChanged: (_) {},
            ),
          ),
        );

    await tester.pumpWidget(wheel(const [('all', '전체')]));
    await tester.pumpWidget(wheel(const [
      ('all', '전체'),
      ('daechi', '대치'),
      ('mokdong', '목동'),
    ]));
    await tester.pumpAndSettle();

    final controller = tester
        .state<State<WheelSelector<String>>>(find.byType(WheelSelector<String>));
    // 굴림 위치가 '대치'(1번 칸)여야 한다.
    final wheelView = tester.widget<ListWheelScrollView>(
        find.byType(ListWheelScrollView));
    expect((wheelView.controller as FixedExtentScrollController).selectedItem, 1);
    expect(controller.mounted, isTrue);
  });

  testWidgets('좁은 화면에서는 로드맵이 한 과목씩 넘어간다', (tester) async {
    // 모바일에서 네 과목을 가로 스크롤로 밀게 하면 세로·가로 두 방향을
    // 오가게 된다. 한 과목만 펴고 전환은 스와이프에 맡긴다.
    final roadmap = Roadmap(
      stages: [
        for (final s in ['english', 'math', 'korean'])
          RoadmapStage(
            id: '\$s-1',
            subject: s,
            title: '\$s 시작',
            gradeMin: 0,
            gradeMax: 2,
          ),
      ],
    );
    final data = EduTreeData(
      meta: const Meta(
        mode: 'test',
        generatedAt: '',
        evaluatedCount: 0,
        registryCount: 0,
        mentionCount: 0,
        weights: {},
        minSampleForRank: 10,
        reputationPriorCount: 12,
        recencyHalflifeDays: 180,
      ),
      regions: const [],
      tracks: const [],
      academies: const [],
      roadmap: roadmap,
    );

    Future<void> pumpAt(double width) async {
      tester.view.physicalSize = Size(width, 900);
      tester.view.devicePixelRatio = 1.0;
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: ProviderScope(
            child: RoadmapView(data: data, regionId: 'daechi'),
          ),
        ),
      ));
      await tester.pump();
    }

    addTearDown(tester.view.reset);

    await pumpAt(375);
    expect(find.byType(PageView), findsOneWidget,
        reason: '휴대폰 폭에서는 과목별 페이지로 넘긴다');

    await pumpAt(1200);
    expect(find.byType(PageView), findsNothing,
        reason: '넓은 화면에서는 네 과목을 나란히 둔다');
  });

  group('획 등장(StrokeIn)', () {
    // 처음엔 `Align(widthFactor:)` 로 열었다. 그러면 애니메이션 도중의
    // 폭이 곧 **레이아웃 폭**이 되어 자식이 실제로 좁아진다 — 랭킹 목록
    // 캡처에서 카드마다 오른쪽 끝이 다른 자리에서 잘려 있었다.
    // 지금은 클리퍼로 그리기만 자르므로 폭이 늘 그대로여야 한다.
    testWidgets('애니메이션 도중에도 자식의 폭이 줄지 않는다', (tester) async {
      const key = ValueKey('inner');

      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: Center(
              child: SizedBox(
                width: 400,
                child: StrokeIn(
                  child: Row(children: [Expanded(child: SizedBox(key: key, height: 20))]),
                ),
              ),
            ),
          ),
        ),
      );

      // 시작 직후 — 아직 거의 안 열린 시점
      await tester.pump(const Duration(milliseconds: 60));
      expect(tester.getSize(find.byKey(key)).width, 400);

      // 중간
      await tester.pump(const Duration(milliseconds: 250));
      expect(tester.getSize(find.byKey(key)).width, 400);

      // 끝
      await tester.pumpAndSettle();
      expect(tester.getSize(find.byKey(key)).width, 400);
    });

    testWidgets('모션을 끄면 획을 긋지 않고 바로 내놓는다', (tester) async {
      const key = ValueKey('inner');
      await tester.pumpWidget(
        const MediaQuery(
          data: MediaQueryData(disableAnimations: true),
          child: MaterialApp(
            home: Scaffold(
              body: Center(
                child: SizedBox(
                  width: 300,
                  child: StrokeIn(
                    child: Row(children: [Expanded(child: SizedBox(key: key, height: 10))]),
                  ),
                ),
              ),
            ),
          ),
        ),
      );
      // 한 프레임만에 온전한 폭이어야 한다. 기다릴 것이 없다.
      expect(tester.getSize(find.byKey(key)).width, 300);
      expect(find.byType(ClipRect), findsNothing);
    });
  });

  group('테크트리 단계 목록', () {
    Academy academy(String id,
            {List<String> stages = const [],
            Map<String, String> basis = const {},
            List<String> bands = const [],
            double total = 50}) =>
        Academy(
          id: id,
          name: id,
          displayNameRaw: id,
          aliases: const [],
          regionId: 'daechi',
          subjects: const ['math'],
          gradeBands: bands,
          stages: stages,
          stageBasis: basis,
          flagship: const [],
          isVerified: true,
          dataSource: 'neis',
          score: Score(
            total: total,
            reputation: total,
            momentum: total,
            sampleSize: 20,
            confidence: 'high',
            isRanked: true,
            momentumDirection: 'stable',
          ),
          evidence: const [],
        );

    // 초4~초6 수학 트랙. '경시'는 이 구간에만, '교과 기본'은 초등 전체.
    const track = Track(
      id: 'math_elem_high',
      subject: 'math',
      gradeBand: 'elem_high',
      title: '초4~초6 수학',
      summary: '',
      stages: [
        Stage(
            id: 'basic',
            trackId: 'math_elem_high',
            title: '연산 · 교과 기본',
            gradeMin: 0,
            gradeMax: 6,
            depth: 0,
            lane: 0),
        Stage(
            id: 'comp',
            trackId: 'math_elem_high',
            title: '경시 · 심화',
            gradeMin: 4,
            gradeMax: 6,
            depth: 1,
            lane: 0),
      ],
      edges: [],
    );

    EduTreeData dataWith(List<Academy> rows) => EduTreeData(
          meta: const Meta(
            mode: 'test',
            generatedAt: '',
            evaluatedCount: 0,
            registryCount: 0,
            mentionCount: 0,
            weights: {},
            minSampleForRank: 10,
            reputationPriorCount: 12,
            recencyHalflifeDays: 180,
          ),
          regions: const [],
          tracks: [track],
          academies: rows,
          roadmap: const Roadmap(),
        );

    test('단계에 붙은 근거를 그대로 들고 온다', () {
      final data = dataWith([
        academy('큐레이션', stages: ['comp'], basis: {'comp': 'curated'}),
        academy('단서', stages: ['comp'], basis: {'comp': 'hinted'}),
      ]);
      final got = data.academiesForStage('comp', regionId: 'daechi');
      expect(got.map((m) => m.basis).toSet(), {'curated', 'hinted'});
      expect(got.every((m) => m.isDirect), isTrue);
    });

    test('근거가 없으면 근거를 지어내지 않고 비워 둔다', () {
      final data = dataWith([academy('교과만', stages: ['basic'])]);
      expect(data.academiesForStage('comp', regionId: 'daechi'), isEmpty);
    });

    test('fillTo 를 주면 같은 구간에서 채우되 band 로 표시한다', () {
      final data = dataWith([
        academy('경시', stages: ['comp'], basis: {'comp': 'hinted'}, total: 60),
        academy('교과', stages: ['basic'], total: 70),
      ]);
      final got =
          data.academiesForStage('comp', regionId: 'daechi', fillTo: 2);
      expect(got.length, 2);
      // 근거 있는 곳이 먼저. 점수가 낮아도 이어 붙인 곳보다 앞이다.
      expect(got.first.academy.id, '경시');
      expect(got.first.isDirect, isTrue);
      expect(got.last.basis, 'band');
      expect(got.last.label, contains('같은 구간'));
    });

    test('학년 구간이 비면 어느 구간에도 걸린다 — 필터와 같게 읽는다', () {
      // 파이프라인이 빈 grade_bands 를 '아무 구간도 아님'으로 읽어
      // 등록부 78%가 테크트리에서 통째로 사라진 적이 있다.
      final data = dataWith([academy('구간미상', bands: const [])]);
      final got =
          data.academiesForStage('comp', regionId: 'daechi', fillTo: 3);
      expect(got.single.academy.id, '구간미상');
      expect(got.single.basis, 'band');
    });

    test('근거가 충분하면 이어 붙이지 않는다', () {
      final data = dataWith([
        academy('a', stages: ['comp'], basis: {'comp': 'hinted'}),
        academy('b', stages: ['comp'], basis: {'comp': 'hinted'}),
        academy('c', stages: ['basic']),
      ]);
      final got =
          data.academiesForStage('comp', regionId: 'daechi', fillTo: 2);
      expect(got.length, 2);
      expect(got.every((m) => m.isDirect), isTrue);
    });
  });
}
