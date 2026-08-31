import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:edutree/core/brand.dart';
import 'package:edutree/core/theme.dart';
import 'package:edutree/data/models.dart';
import 'package:edutree/data/repository.dart';
import 'package:edutree/widgets/annals.dart';
import 'package:edutree/widgets/scroll_stage.dart';
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
      id: 'x',
      trackId: 't',
      title: '테스트',
      gradeMin: 4,
      gradeMax: 8,
      depth: 0,
      lane: 0,
    );
    expect(s.gradeLabel, '초4~중2');
    expect(Stage.gradeName(12), '고3');
  });

  test('예비초는 0으로 들어와 초1 앞에 놓인다', () {
    expect(Stage.gradeName(0), '예비초');
    const s = Stage(
      id: 'x',
      trackId: 't',
      title: '연산',
      gradeMin: 0,
      gradeMax: 3,
      depth: 0,
      lane: 0,
    );
    expect(s.gradeLabel, '예비초~초3');
  });

  test('학년 구간은 경계를 걸치면 양쪽 모두에 든다', () {
    // 사고력(초1~초4)은 저학년 학부모도 고학년 학부모도 함께 찾는 단계다.
    const spanning = Stage(
      id: 'x',
      trackId: 't',
      title: '사고력',
      gradeMin: 1,
      gradeMax: 4,
      depth: 0,
      lane: 0,
    );
    expect(spanning.gradeBands, ['elem_low', 'elem_high']);

    const single = Stage(
      id: 'y',
      trackId: 't',
      title: '수능',
      gradeMin: 10,
      gradeMax: 12,
      depth: 0,
      lane: 0,
    );
    expect(single.gradeBands, ['high']);
  });

  test('Selection.trackId 는 과목·학년구간을 트랙 키로 합친다', () {
    const sel = Selection(subject: 'math', gradeBand: 'elem_low');
    expect(sel.trackId, 'math_elem_low');
  });

  test('같은 값이면 같은 상태다 — 헛된 재구성을 막는 기준', () {
    const a = Selection(
      regionId: 'daechi',
      subject: 'math',
      gradeBand: 'middle',
    );
    const b = Selection(
      regionId: 'daechi',
      subject: 'math',
      gradeBand: 'middle',
    );
    expect(a, b);
    expect(a.hashCode, b.hashCode);
    expect(a == a.copyWith(gradeBand: 'high'), isFalse);
  });

  testWidgets('앱이 프로바이더 스코프 안에서 뜬다', (tester) async {
    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(home: Scaffold(body: Text('에듀트리'))),
      ),
    );
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
    await tester.pumpWidget(
      wheel(const [('all', '전체'), ('daechi', '대치'), ('mokdong', '목동')]),
    );
    await tester.pumpAndSettle();

    final controller = tester.state<State<WheelSelector<String>>>(
      find.byType(WheelSelector<String>),
    );
    // 굴림 위치가 '대치'(1번 칸)여야 한다.
    final wheelView = tester.widget<ListWheelScrollView>(
      find.byType(ListWheelScrollView),
    );
    expect(
      (wheelView.controller as FixedExtentScrollController).selectedItem,
      1,
    );
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
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ProviderScope(
              child: RoadmapView(data: data, regionId: 'daechi'),
            ),
          ),
        ),
      );
      await tester.pump();
    }

    addTearDown(tester.view.reset);

    await pumpAt(375);
    expect(
      find.byType(PageView),
      findsOneWidget,
      reason: '휴대폰 폭에서는 과목별 페이지로 넘긴다',
    );

    await pumpAt(1200);
    expect(
      find.byType(PageView),
      findsNothing,
      reason: '넓은 화면에서는 네 과목을 나란히 둔다',
    );
  });

  group('로고 표장(LogoMark)', () {
    // 로고를 PNG 에서 그리기로 바꾼 **이유가 이것 하나**다. 한지 바탕에
    // 맞춘 먹빛 마크는 먹빛 판면에서 사라지고, 바탕을 깔면 어두운 헤더에
    // 흰 딱지가 붙는다. 다시 래스터로 돌아가면 이 시험이 먼저 깨진다.
    testWidgets('먹빛 판면에서 색이 뒤집힌다', (tester) async {
      Future<Color> inkOf(Brightness b) async {
        await tester.pumpWidget(
          MaterialApp(
            theme: ThemeData(brightness: b),
            home: const Scaffold(body: Center(child: LogoMark(size: 48))),
          ),
        );
        // **MaterialApp 은 테마를 200ms 에 걸쳐 보간한다**(AnimatedTheme).
        // 두 번째 pump 직후에 읽으면 아직 앞 테마 쪽 값이라, 다크로 바꿔
        // 놓고도 밝은 색을 보게 된다 — 여기서 한 번 속았다.
        await tester.pumpAndSettle();
        final paint = tester.widget<CustomPaint>(
          find.descendant(
            of: find.byType(LogoMark),
            matching: find.byType(CustomPaint),
          ),
        );
        return (paint.painter! as dynamic).ink as Color;
      }

      final light = await inkOf(Brightness.light);
      final dark = await inkOf(Brightness.dark);

      expect(light, AppColors.ink);
      expect(dark, AppColors.darkInk);
      expect(light, isNot(dark));
    });

    // 헤더는 폭에 따라 로고 크기를 달리 준다(HeaderLayout). 격자를 크기로
    // 나눠 그리므로 어느 크기에서도 마크가 상자를 넘지 않아야 한다.
    testWidgets('주어진 크기를 넘지 않는다', (tester) async {
      for (final s in [16.0, 28.0, 44.0]) {
        await tester.pumpWidget(
          MaterialApp(home: Scaffold(body: Center(child: LogoMark(size: s)))),
        );
        expect(tester.getSize(find.byType(LogoMark)), Size(s, s));
      }
    });
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
                  child: Row(
                    children: [Expanded(child: SizedBox(key: key, height: 20))],
                  ),
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
                    child: Row(
                      children: [
                        Expanded(child: SizedBox(key: key, height: 10)),
                      ],
                    ),
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

  group('조사', () {
    test('받침이 있으면 앞 글자, 없으면 뒤 글자', () {
      // 실제로 틀려 있던 것 — '록'에 받침 ㄱ 이 있으니 '은'이다.
      expect(josa('학원실록', '은는'), '학원실록은');
      expect(josa('대치', '은는'), '대치는');
      expect(josa('학원실록', '이가'), '학원실록이');
      expect(josa('테크트리', '이가'), '테크트리가');
      expect(josa('산식', '을를'), '산식을');
      expect(josa('학군지도', '을를'), '학군지도를');
      expect(josa('목동', '과와'), '목동과');
      expect(josa('반포', '과와'), '반포와');
    });

    test('브랜드 이름이 바뀌어도 조사가 따라온다', () {
      // 이 파일의 첫 줄이 '이름을 바꿀 때 손댈 곳은 여기 하나뿐이다' 라고
      // 약속한다. 조사를 손으로 적으면 그 약속이 깨진다.
      expect(josa(Brand.name, '은는'), '학원실록은');
      expect(josa('에듀트리', '은는'), '에듀트리는');
    });

    test('한글이 아니면 받침 없는 쪽으로 둔다', () {
      // 소리로 정해지는 자리라 글자만 봐서는 알 수 없다. 이 경우에는
      // 함수를 쓰지 말고 문장을 손으로 적으라고 문서에 적어 뒀다.
      expect(josa('Open Edu', '은는'), 'Open Edu는');
      expect(josa('', '은는'), '는');
    });
  });

  group('과목 순서', () {
    test('표준 순서로 세운다 — 들어온 차례와 무관하게', () {
      expect(orderedSubjects(['science', 'etc', 'math', 'arts', 'english']), [
        'math',
        'english',
        'science',
        'arts',
        'etc',
      ]);
    });

    test('표시 이름이 없는 키는 버린다 — general 은 모른다는 뜻이다', () {
      expect(orderedSubjects(['general', 'math']), ['math']);
      expect(orderedSubjects(['general']), isEmpty);
    });

    test('같은 과목이 두 번 와도 한 번만 나온다', () {
      expect(orderedSubjects(['math', 'math', 'english']), ['math', 'english']);
    });

    test('학술과 비학술이 갈린다 — 산식이 다르기 때문', () {
      expect(isAcademicSubject('math'), isTrue);
      expect(isAcademicSubject('arts'), isFalse);
      expect(isAcademicSubject('etc'), isFalse);
      expect(isAcademicSubject(null), isFalse);
    });

    test('모든 과목이 이름과 색을 갖는다', () {
      for (final s in subjectOrder) {
        expect(subjectNames[s], isNotNull, reason: '$s 에 표시 이름이 없다');
        // 'art' 로 적어 두고 'arts' 로 찾는 바람에 예체능만 색 없이
        // 회색으로 떨어져 있었다. 키가 어긋나면 조용히 회색이 된다.
        expect(AppColors.subjects[s], isNotNull, reason: '$s 에 색이 없다');
      }
    });
  });

  group('로드맵 자리 계산(RoadmapLanes)', () {
    Roadmap withStages(List<RoadmapStage> stages) =>
        Roadmap(stages: stages);

    RoadmapStage st(String id, int min, int max, {int lane = 0}) =>
        RoadmapStage(
            id: id, subject: 'math', title: id, gradeMin: min, gradeMax: max,
            lane: lane);

    // 고3 수학이 실제로 이렇다 — 내신·수능·최상위·N수 넷이 한 학년에
    // 동시에 열려 있다. 예전 배치는 lane 0/1 두 자리만 알아서 넷 중
    // 둘이 같은 자리에 포개졌고, 위 카드가 아래 카드의 학원 이름을
    // 통째로 덮었다.
    test('겹치는 단계는 서로 다른 칸에 선다', () {
      final lanes = RoadmapLanes.of(withStages([
        st('naesin', 10, 12, lane: 1),
        st('suneung', 10, 12, lane: 1),
        st('top', 11, 12, lane: 0),
        st('nsu', 12, 12, lane: 1),
      ]));

      final seats = {
        for (final id in ['naesin', 'suneung', 'top', 'nsu'])
          id: lanes.laneOfStage(id),
      };
      expect(seats.values.toSet().length, 4, reason: '넷이 전부 다른 칸이다');
      expect(lanes.countFor('math'), 4);
    });

    test('겹치지 않으면 같은 칸을 다시 쓴다', () {
      // 자리를 아끼지 않으면 안 겹치는 단계까지 폭이 좁아진다.
      final lanes = RoadmapLanes.of(withStages([
        st('a', 0, 3),
        st('b', 4, 6),
        st('c', 7, 9),
      ]));
      expect(lanes.countFor('math'), 1);
      expect(lanes.laneOfStage('a'), 0);
      expect(lanes.laneOfStage('c'), 0);
    });

    test('yaml 의 lane 은 같은 학년에서 시작한 것들의 차례로 남는다', () {
      final lanes = RoadmapLanes.of(withStages([
        st('right', 0, 4, lane: 1),
        st('left', 0, 4, lane: 0),
      ]));
      expect(lanes.laneOfStage('left'), 0);
      expect(lanes.laneOfStage('right'), 1);
    });

    // 학년 한 칸짜리 카드(72px)에 표제 두 줄 + 학년 표기 + 학원 세 줄을
    // 밀어 넣고 있었다 — 실측 43px 넘침. 넘친 부분은 그려지지 않으므로
    // **학원 이름이 통째로 사라진다.** 넘침은 시험에서 예외로 잡히므로
    // 카드를 그려 보는 것만으로 검사가 된다.
    testWidgets('짧은 카드에서도 내용이 넘치지 않는다', (tester) async {
      tester.view.physicalSize = const Size(1400, 1200);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);

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
        // 학년 한 칸짜리 단계. 이어 붙일 학원이 셋 다 있어도 넘치면 안 된다.
        academies: [
          for (var i = 0; i < 3; i++)
            Academy(
              id: 'a$i',
              name: '아주긴이름의학원$i',
              displayNameRaw: '아주긴이름의학원$i',
              aliases: const [],
              regionId: 'daechi',
              subjects: const ['math'],
              gradeBands: const [],
              stages: const ['one'],
              stageBasis: const {'one': 'curated'},
              flagship: const [],
              isVerified: true,
              dataSource: 'neis',
              score: const Score(
                total: 60,
                reputation: 60,
                momentum: 60,
                sampleSize: 20,
                confidence: 'high',
                isRanked: true,
                momentumDirection: 'stable',
              ),
              evidence: const [],
            ),
        ],
        roadmap: withStages([st('one', 12, 12)]),
      );

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ProviderScope(
              child: RoadmapView(data: data, regionId: 'daechi'),
            ),
          ),
        ),
      );
      await tester.pump();
      expect(tester.takeException(), isNull);
    });

    // 실제 화면에서 카드가 겹치지 않는지까지 본다. 자리 계산이 맞아도
    // 배치에서 안 쓰면 소용이 없다 — 예전에 경로선이 옛 규칙에 남아
    // 카드와 다른 곳을 가리켰다.
    testWidgets('카드끼리 화면에서 겹치지 않는다', (tester) async {
      tester.view.physicalSize = const Size(1400, 2400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);

      final roadmap = withStages([
        st('naesin', 10, 12, lane: 1),
        st('suneung', 10, 12, lane: 1),
        st('top', 11, 12, lane: 0),
      ]);
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

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ProviderScope(
              child: RoadmapView(data: data, regionId: 'daechi'),
            ),
          ),
        ),
      );
      await tester.pump();

      Rect rectOf(String title) => tester.getRect(
          find.ancestor(of: find.text(title), matching: find.byType(Container))
              .first);

      final rects = [
        for (final id in ['naesin', 'suneung', 'top']) rectOf(id),
      ];
      for (var i = 0; i < rects.length; i++) {
        for (var j = i + 1; j < rects.length; j++) {
          expect(rects[i].overlaps(rects[j]), isFalse,
              reason: '$i 번과 $j 번 카드가 포개졌다 — 학원 이름이 가려진다');
        }
      }
    });
  });

  group('스크롤 연출', () {
    // Reveal 은 `Opacity` 를 거쳐 그린다. 열림 정도를 그 값으로 읽는다.
    double openness(WidgetTester tester, Key key) {
      final f = find
          .ancestor(of: find.byKey(key), matching: find.byType(Opacity))
          .first;
      return tester.widget<Opacity>(f).opacity;
    }

    Widget page(Widget target, {double before = 1000, double after = 1000}) {
      return MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: Column(
              children: [
                SizedBox(height: before),
                target,
                SizedBox(height: after),
              ],
            ),
          ),
        ),
      );
    }

    testWidgets('만들어질 때가 아니라 화면에 들어올 때 열린다', (tester) async {
      const key = ValueKey('r');
      await tester.pumpWidget(
        page(const Reveal(child: SizedBox(key: key, width: 300, height: 60))),
      );
      await tester.pump();

      // 시험 화면은 800×600. 위쪽 여백이 1000 이라 아직 화면 밖이다.
      expect(
        openness(tester, key),
        0.0,
        reason: '화면 밖인데 이미 열려 있으면 연출이 통째로 낭비된다',
      );

      await tester.drag(
        find.byType(SingleChildScrollView),
        const Offset(0, -700),
      );
      await tester.pumpAndSettle();
      expect(openness(tester, key), 1.0);
    });

    testWidgets('한 번 열면 되올려도 닫지 않는다', (tester) async {
      const key = ValueKey('r');
      await tester.pumpWidget(
        page(const Reveal(child: SizedBox(key: key, width: 300, height: 60))),
      );
      await tester.drag(
        find.byType(SingleChildScrollView),
        const Offset(0, -700),
      );
      await tester.pumpAndSettle();
      expect(openness(tester, key), 1.0);

      // 다시 위로. 읽은 것을 되감는 화면은 없다.
      await tester.drag(
        find.byType(SingleChildScrollView),
        const Offset(0, 700),
      );
      await tester.pumpAndSettle();
      expect(openness(tester, key), 1.0);
    });

    testWidgets('모션을 끄면 즉시 온전히 보인다', (tester) async {
      const key = ValueKey('r');
      await tester.pumpWidget(
        const MediaQuery(
          data: MediaQueryData(disableAnimations: true),
          child: MaterialApp(
            home: Scaffold(
              body: Reveal(child: SizedBox(key: key, width: 300, height: 60)),
            ),
          ),
        ),
      );
      // Opacity 를 거치지 않는다 — 감쌀 것 없이 자식 그대로다.
      expect(
        find.ancestor(of: find.byKey(key), matching: find.byType(Opacity)),
        findsNothing,
      );
    });

    testWidgets('Scrub 은 지나가는 동안 0에서 1로 찬다', (tester) async {
      var seen = -1.0;
      await tester.pumpWidget(
        page(
          Scrub(
            builder: (_, t) {
              seen = t;
              return const SizedBox(width: 300, height: 200);
            },
          ),
        ),
      );
      await tester.pump();
      expect(seen, 0.0, reason: '화면 아래에 있을 때는 아직 안 그어진다');

      await tester.drag(
        find.byType(SingleChildScrollView),
        const Offset(0, -700),
      );
      await tester.pumpAndSettle();
      expect(seen, greaterThan(0.0));
      expect(seen, lessThan(1.0), reason: '가운데쯤에서는 아직 그리는 중이어야 한다');

      await tester.drag(
        find.byType(SingleChildScrollView),
        const Offset(0, -600),
      );
      await tester.pumpAndSettle();
      expect(seen, 1.0);
    });

    testWidgets('Scrub 은 되감지 않는다', (tester) async {
      var seen = -1.0;
      await tester.pumpWidget(
        page(
          Scrub(
            builder: (_, t) {
              seen = t;
              return const SizedBox(width: 300, height: 200);
            },
          ),
        ),
      );
      await tester.drag(
        find.byType(SingleChildScrollView),
        const Offset(0, -1300),
      );
      await tester.pumpAndSettle();
      expect(seen, 1.0);

      await tester.drag(
        find.byType(SingleChildScrollView),
        const Offset(0, 1300),
      );
      await tester.pumpAndSettle();
      expect(seen, 1.0, reason: '기록이 지워지는 것처럼 보이면 안 된다');
    });

    testWidgets('모션을 끄면 Scrub 은 다 그은 상태를 준다', (tester) async {
      var seen = -1.0;
      await tester.pumpWidget(
        MediaQuery(
          data: const MediaQueryData(disableAnimations: true),
          child: MaterialApp(
            home: Scaffold(
              body: SingleChildScrollView(
                child: Column(
                  children: [
                    const SizedBox(height: 1000),
                    Scrub(
                      builder: (_, t) {
                        seen = t;
                        return const SizedBox(width: 300, height: 200);
                      },
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      );
      await tester.pump();
      expect(seen, 1.0, reason: '동작이 정보를 쥐고 있으면 안 된다');
    });

    testWidgets('Tally 는 모션을 끄면 최종값을 그대로 적는다', (tester) async {
      await tester.pumpWidget(
        const MediaQuery(
          data: MediaQueryData(disableAnimations: true),
          child: MaterialApp(home: Scaffold(body: Tally(5531))),
        ),
      );
      expect(find.text('5,531'), findsOneWidget);
    });

    testWidgets('Tally 는 세어 올린 뒤 최종값에서 멈춘다', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(body: SingleChildScrollView(child: Tally(5531))),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 120));
      // 세는 중 — 아직 최종값이 아니다
      expect(find.text('5,531'), findsNothing);
      await tester.pumpAndSettle();
      expect(find.text('5,531'), findsOneWidget);
    });

    testWidgets('머리띠: 스크롤할 것이 없으면 가득 찬다', (tester) async {
      final n = ValueNotifier<double>(0);
      addTearDown(n.dispose);
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ReadingProgress(
              notifier: n,
              child: SingleChildScrollView(
                child: Container(height: 100, color: const Color(0xFF000000)),
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(n.value, 1.0, reason: '0 이면 고장으로 보인다');
    });

    testWidgets('머리띠: 안쪽 가로 스크롤에는 움직이지 않는다', (tester) async {
      final n = ValueNotifier<double>(0);
      addTearDown(n.dispose);
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ReadingProgress(
              notifier: n,
              child: const SingleChildScrollView(
                child: Column(
                  children: [
                    SizedBox(
                      height: 80,
                      child: SingleChildScrollView(
                        key: ValueKey('side'),
                        scrollDirection: Axis.horizontal,
                        child: SizedBox(width: 3000, height: 80),
                      ),
                    ),
                    SizedBox(height: 2000),
                  ],
                ),
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      final before = n.value;

      await tester.drag(
        find.byKey(const ValueKey('side')),
        const Offset(-400, 0),
      );
      await tester.pumpAndSettle();
      expect(n.value, before, reason: '테크트리의 가로 스크롤이 머리띠를 밀면 안 된다');
    });
  });

  group('테크트리 단계 목록', () {
    Academy academy(
      String id, {
      List<String> stages = const [],
      Map<String, String> basis = const {},
      List<String> bands = const [],
      double total = 50,
    }) => Academy(
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
          lane: 0,
        ),
        Stage(
          id: 'comp',
          trackId: 'math_elem_high',
          title: '경시 · 심화',
          gradeMin: 4,
          gradeMax: 6,
          depth: 1,
          lane: 0,
        ),
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
      final data = dataWith([
        academy('교과만', stages: ['basic']),
      ]);
      expect(data.academiesForStage('comp', regionId: 'daechi'), isEmpty);
    });

    test('fillTo 를 주면 같은 구간에서 채우되 band 로 표시한다', () {
      final data = dataWith([
        academy('경시', stages: ['comp'], basis: {'comp': 'hinted'}, total: 60),
        academy('교과', stages: ['basic'], total: 70),
      ]);
      final got = data.academiesForStage('comp', regionId: 'daechi', fillTo: 2);
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
      final got = data.academiesForStage('comp', regionId: 'daechi', fillTo: 3);
      expect(got.single.academy.id, '구간미상');
      expect(got.single.basis, 'band');
    });

    test('근거가 충분하면 이어 붙이지 않는다', () {
      final data = dataWith([
        academy('a', stages: ['comp'], basis: {'comp': 'hinted'}),
        academy('b', stages: ['comp'], basis: {'comp': 'hinted'}),
        academy('c', stages: ['basic']),
      ]);
      final got = data.academiesForStage('comp', regionId: 'daechi', fillTo: 2);
      expect(got.length, 2);
      expect(got.every((m) => m.isDirect), isTrue);
    });
  });

  // ── 새 필드가 없는 번들도 읽는다 ────────────────────────────
  //
  // 앱은 배포되는 순간 바뀌지만 번들은 다음 야간 수집에서야 바뀐다.
  // 그래서 **새 필드를 읽는 코드가 옛 번들을 먼저 만난다** — 주장(claim)
  // 분해를 넣은 회차가 정확히 그랬다. 여기서 터지면 화면이 통째로 빈다.
  group('옛 번들 호환', () {
    Map<String, dynamic> legacy() => {
      'id': 'A1',
      'name': '가나수학학원',
      'displayName': '가나수학',
      'regionId': 'daechi',
      'subjects': ['math'],
      'gradeBands': ['middle'],
      'stages': <String>[],
      'flagship': <String>[],
      'isVerified': true,
      'dataSource': 'neis',
      'evidence': <dynamic>[],
      'score': {
        'total': 61.2,
        'reputation': 55.0,
        'momentum': 48.0,
        'transparency': 70.0,
        'selectivity': 40.0,
        'sampleSize': 12,
        'confidence': 'medium',
        'isRanked': true,
        'momentumDirection': 'stable',
      },
    };

    test('facts·selectivityEvidence·disputeRate 가 없어도 읽힌다', () {
      final a = Academy.fromJson(legacy());
      expect(a.facts, isEmpty);
      expect(a.selectivityEvidence, isEmpty);
      expect(a.disputeRate, isNull);
    });

    test('selectivityTier 가 없으면 등급을 지어내지 않는다', () {
      final a = Academy.fromJson(legacy());
      expect(a.score.selectivityTier, isNull);
      // 근거가 없으면 '쉽다'가 아니라 아무 말도 하지 않는다.
      expect(a.score.selectivityLabel, isNull);
      // 옛 번들의 진입난이도 숫자는 그대로 읽는다 — 화면이 비지 않는다.
      expect(a.score.pillarOrNull('selectivity'), 40.0);
    });

    test('새 필드가 있으면 그대로 읽는다', () {
      final a = Academy.fromJson({
        ...legacy(),
        'score': {...legacy()['score'] as Map, 'selectivityTier': 'medium'},
        'facts': {
          'fact.class_freq': {
            'label': '수업 횟수',
            'unit': '회/주',
            'text': '3회',
            'value': 3,
            'n': 4,
            'quotes': [
              {'claimId': 'c1', 'quote': '수업은 주 3회', 'url': 'https://x'},
            ],
          },
        },
        'selectivityEvidence': [
          {
            'claimId': 'c2',
            'kind': 'sel.waitlist',
            'label': '대기·웨이팅',
            'quote': '대기 두 달',
            'status': 'revoked',
            'revokedReason': '지금은 다름',
          },
        ],
        'disputeRate': {'total': 5, 'dropped': 1, 'rate': 0.2},
      });
      expect(a.score.selectivityLabel, '확인됨 · 중간');
      expect(a.facts['fact.class_freq']!.hasValue, isTrue);
      expect(a.facts['fact.class_freq']!.quotes.single.claimId, 'c1');
      // 취소된 근거는 사라지지 않고 사유와 함께 남는다 — 그냥 지우면
      // 다음 사람이 같은 이의를 다시 제기한다.
      final ev = a.selectivityEvidence.single;
      expect(ev.isActive, isFalse);
      expect(ev.statusLabel, '이의로 제외됨');
      expect(a.disputeRate!.dropped, 1);
    });
  });

  group('진로 목적지', () {
    // 같은 그래프를 축만 바꿔 읽는다. 판이 답해야 하는 것은 셋이다:
    // 이 길이 어느 과목을 지나는가 · 언제 갈리는가 · 그 대목이 얼마나 찼나.
    const mathTrack = Track(
      id: 'math_high',
      subject: 'math',
      gradeBand: 'high',
      title: '고등 수학',
      summary: '',
      stages: [
        Stage(
          id: 'm_naesin',
          trackId: 'math_high',
          title: '고등 내신',
          gradeMin: 10,
          gradeMax: 12,
          depth: 0,
          lane: 0,
        ),
        Stage(
          id: 'm_top',
          trackId: 'math_high',
          title: '최상위 · 심화',
          gradeMin: 11,
          gradeMax: 12,
          depth: 1,
          lane: 0,
        ),
      ],
      edges: [],
    );
    const sciTrack = Track(
      id: 'sci_high',
      subject: 'science',
      gradeBand: 'high',
      title: '고등 과학',
      summary: '',
      stages: [
        Stage(
          id: 's_two',
          trackId: 'sci_high',
          title: '과탐 II',
          gradeMin: 11,
          gradeMax: 12,
          depth: 0,
          lane: 0,
        ),
      ],
      edges: [],
    );

    // requires 를 일부러 과학부터 적는다 — 판의 열은 사람이 yaml 에 적은
    // 차례가 아니라 표준 과목 순서를 따라야 행마다 안 흔들린다.
    const medical = Destination(
      id: 'dest_medical',
      label: '의대 · 의치한',
      axis: '국내입시',
      summary: '과탐 II 와 수학 최상위가 갈림길.',
      requires: {
        'science': ['s_two'],
        'math': ['m_naesin', 'm_top'],
      },
      gates: [
        DestinationGate(grade: 11, note: '과탐 II 선택'),
        DestinationGate(grade: 10, note: '고1 내신이 사실상 전제'),
      ],
    );
    const early = Destination(
      id: 'dest_early',
      label: '조기졸업 · 검정고시',
      axis: '기타',
      linkable: false,
      requires: {
        'math': ['m_naesin'],
      },
    );

    Academy aca(String id, String region, List<String> stages) => Academy(
      id: id,
      name: id,
      displayNameRaw: id,
      aliases: const [],
      regionId: region,
      subjects: const ['math'],
      gradeBands: const ['high'],
      stages: stages,
      stageBasis: {for (final s in stages) s: 'curated'},
      flagship: const [],
      isVerified: true,
      dataSource: 'neis',
      score: const Score(
        total: 60,
        reputation: 60,
        momentum: 60,
        sampleSize: 20,
        confidence: 'high',
        isRanked: true,
        momentumDirection: 'stable',
      ),
      evidence: const [],
    );

    EduTreeData board() => EduTreeData(
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
      tracks: const [mathTrack, sciTrack],
      // 로드맵이 비면 RoadmapView 가 안내문만 내므로, 축을 넘나드는
      // 시험이 성립하지 않는다.
      roadmap: const Roadmap(
        stages: [
          RoadmapStage(
            id: 'm_naesin',
            subject: 'math',
            title: '고등 내신',
            gradeMin: 10,
            gradeMax: 12,
          ),
          RoadmapStage(
            id: 's_two',
            subject: 'science',
            title: '과탐 II',
            gradeMin: 11,
            gradeMax: 12,
          ),
        ],
      ),
      academies: [
        aca('대치A', 'daechi', ['m_naesin']),
        aca('대치B', 'daechi', ['m_naesin', 'm_top']),
        aca('목동C', 'mokdong', ['m_naesin']),
      ],
      destinations: const [medical, early],
    );

    test('칸은 학군 기준으로 다시 센다 — 전국 합계를 적으면 판과 어긋난다', () {
      final data = board();
      expect(
        data.legFor(medical, 'math', regionId: 'daechi').academyCount,
        2,
        reason: '목동 학원은 대치 판의 숫자에 들어가면 안 된다',
      );
      expect(data.legFor(medical, 'math', regionId: 'all').academyCount, 3);
      // 학원 수는 단계별 수의 합이 아니다 — 한 학원이 여러 단계를 담당한다.
      expect(
        data.legFor(medical, 'math', regionId: 'daechi').countOf('m_naesin'),
        2,
      );
      expect(
        data.legFor(medical, 'math', regionId: 'daechi').countOf('m_top'),
        1,
      );
    });

    test('지나지 않음 · 비었음 · 잇지 않음은 서로 다른 상태다', () {
      final data = board();

      final english = data.legFor(medical, 'english', regionId: 'daechi');
      expect(english.isOffPath, isTrue, reason: '이 길은 영어를 요구하지 않는다');
      expect(english.isEmpty, isFalse, reason: '지나지 않는 것은 빈 것이 아니다');

      final science = data.legFor(medical, 'science', regionId: 'daechi');
      expect(science.isOffPath, isFalse);
      expect(science.isEmpty, isTrue, reason: '요구하는데 학원이 0곳 — 큐레이션한 길의 빈 대목');
      expect(science.emptyStages.map((s) => s.id), ['s_two']);

      final notLinked = data.legFor(early, 'math', regionId: 'daechi');
      expect(notLinked.linkable, isFalse);
      expect(notLinked.academyCount, 0);
      expect(
        notLinked.isEmpty,
        isFalse,
        reason: '학원을 안 잇기로 한 길을 비었다고 적으면 근거가 얇다는 판단이 지워진다',
      );
      expect(notLinked.stages.length, 1, reason: '길은 그대로 그린다');
    });

    test('열은 표준 과목 순서를 따른다 — yaml 에 적은 차례가 아니라', () {
      expect(medical.subjects, ['math', 'science']);
    });

    test('갈림은 가장 이른 관문이다', () {
      expect(medical.firstGateGrade, 10);
      expect(early.firstGateGrade, isNull);
    });

    test('단계 → 목적지 역방향도 읽힌다', () {
      final data = board();
      expect(data.destinationsForStage('m_naesin').map((d) => d.id), [
        'dest_medical',
        'dest_early',
      ]);
      expect(data.destinationsForStage('s_two').map((d) => d.id), [
        'dest_medical',
      ]);
      expect(data.destinationsForStage('없는단계'), isEmpty);
    });

    test('학원을 잇지 않는 길은 세지 않는다', () {
      final data = board();
      expect(data.destinationAcademyCount(early, regionId: 'daechi'), 0);
      expect(data.destinationAcademyCount(medical, regionId: 'daechi'), 2);
    });

    // 목적성 판을 걷어낸 뒤에도 **고른 길이 로드맵을 밝힌다**는 것은
    // 그대로여야 한다. 선택은 이제 로드맵 안의 목적지 줄이 하고,
    // 상태는 destinationProvider 하나가 들고 있다.
    testWidgets('고른 길이 로드맵을 밝힌다', (tester) async {
      tester.view.physicalSize = const Size(1200, 900);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);

      final data = board();
      final c = ProviderContainer();
      addTearDown(c.dispose);
      c.read(destinationProvider.notifier).select('dest_medical');

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: c,
          child: MaterialApp(
            home: Scaffold(
              body: RoadmapView(data: data, regionId: 'daechi'),
            ),
          ),
        ),
      );
      await tester.pump();
      expect(
        find.text('과탐 II 와 수학 최상위가 갈림길.'),
        findsOneWidget,
        reason: '로드맵이 고른 길의 요약을 적는다',
      );
    });
  });

  group('랭킹 목록', () {
    Academy academy(
      String id, {
      required int sample,
      required double total,
      List<String> subjects = const ['math'],
    }) => Academy(
      id: id,
      name: id,
      displayNameRaw: id,
      aliases: const [],
      regionId: 'daechi',
      subjects: subjects,
      gradeBands: const [],
      stages: const [],
      stageBasis: const {},
      flagship: const [],
      isVerified: true,
      dataSource: 'neis',
      score: Score(
        total: total,
        reputation: total,
        momentum: total,
        sampleSize: sample,
        confidence: sample >= 30
            ? 'high'
            : sample >= 10
            ? 'medium'
            : 'low',
        // 파이프라인과 같은 규칙: 표본 10건 이상만 순위 기준을 넘는다.
        isRanked: sample >= 10,
        momentumDirection: 'stable',
      ),
      evidence: const [],
    );

    EduTreeData dataWith(List<Academy> rows) => EduTreeData(
      meta: const Meta(
        mode: 'test',
        generatedAt: '',
        evaluatedCount: 0,
        registryCount: 0,
        mentionCount: 0,
        weights: {},
        nonAcademicWeights: {},
        minSampleForRank: 10,
        reputationPriorCount: 12,
        recencyHalflifeDays: 180,
      ),
      regions: const [],
      tracks: const [],
      academies: rows,
      roadmap: const Roadmap(),
    );

    test('표본 0 은 순위 목록에 넣지 않는다', () {
      // 점수가 코호트 평균(50)으로 채워져 있어 등수를 붙이면 그건
      // 평가가 아니라 기본값이다.
      final data = dataWith([
        academy('근거없음', sample: 0, total: 90),
        academy('근거있음', sample: 12, total: 40),
      ]);
      final got = data.ranking(regionId: 'daechi', subject: 'math');
      expect(got.map((a) => a.id), ['근거있음']);
      expect(data.unscored('daechi', subject: 'math').single.id, '근거없음');
    });

    test('★ 근거가 두꺼운 쪽을 먼저 세운다', () {
      // 실측: 7개 조합에서 표본 1~2건이 표본 47~130건짜리를 제치고
      // 1위였다. '표본 부족'이라 적는 것만으로는 부족하다 — 자리 자체가
      // 근거의 두께를 말해야 한다.
      final data = dataWith([
        academy('표본1건', sample: 1, total: 58),
        academy('표본130건', sample: 130, total: 54),
        academy('표본47건', sample: 47, total: 52),
        academy('표본2건', sample: 2, total: 57),
      ]);
      final got = data.ranking(regionId: 'daechi', subject: 'math');
      expect(got.map((a) => a.id), [
        '표본130건', // 순위 기준을 넘은 것끼리 점수순
        '표본47건',
        '표본1건', // 그 아래가 '표본 부족' — 이 층 안에서도 점수순이다
        '표본2건',
      ]);
      // 점수만 보면 58점짜리가 1위였다. 층이 갈려 아래로 내려간다.
      expect(got.first.scoreFor('math').total, lessThan(58));
    });

    test('같은 층 안에서는 점수순, 동점이면 id 순', () {
      // 동점 tie-break 가 없으면 회차마다 등수가 흔들린다.
      final data = dataWith([
        academy('나', sample: 20, total: 50),
        academy('가', sample: 20, total: 50),
        academy('다', sample: 20, total: 60),
      ]);
      final got = data.ranking(regionId: 'daechi', subject: 'math');
      expect(got.map((a) => a.id), ['다', '가', '나']);
    });
  });
}
