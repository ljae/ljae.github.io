import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:edutree/data/models.dart';
import 'package:edutree/data/repository.dart';
import 'package:edutree/widgets/wheel_selector.dart';

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
}
