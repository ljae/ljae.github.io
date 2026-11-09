import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:edutree/data/browser_store.dart' as store;
import 'package:edutree/data/parent_decision.dart';
import 'package:edutree/widgets/parent_journey.dart';

void main() {
  testWidgets('compact preferences leave room for academies and preserve choice', (
    tester,
  ) async {
    store.writePublic('parent.concern.v2', '');
    addTearDown(() => store.writePublic('parent.concern.v2', ''));
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final container = ProviderContainer();
    addTearDown(container.dispose);
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(
          home: Scaffold(
            body: Column(
              children: [
                ParentConcernBar(compact: true),
                Text('Academies'),
              ],
            ),
          ),
        ),
      ),
    );
    expect(find.byType(ChoiceChip), findsNothing);
    expect(tester.getTopLeft(find.text('Academies')).dy, lessThan(100));
    await tester.tap(find.text('비교 기준 고르기'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('숙제 부담'));
    await tester.pumpAndSettle();
    expect(container.read(parentConcernProvider), 'homework');
    await tester.tap(find.text('비교 기준 · 숙제 부담'));
    await tester.pumpAndSettle();
    expect(find.byType(ChoiceChip), findsNothing);
    expect(container.read(parentConcernProvider), 'homework');
    expect(tester.takeException(), isNull);
  });
}
