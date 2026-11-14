import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:edutree/data/browser_store.dart' as store;
import 'package:edutree/data/repository.dart';

/// 학년 구간은 방문을 넘어 기억한다. 처음 온 사람은 예비초~초3.
void main() {
  tearDown(() => SelectionNotifier.persist = false);

  test('첫 방문과 알 수 없는 값은 예비초~초3', () {
    expect(initialSelection(null).gradeBand, 'elem_low');
    expect(initialSelection('nursery').gradeBand, 'elem_low');
    expect(initialSelection('middle').gradeBand, 'middle');
    expect(initialSelection('middle').regionId, 'daechi');
  });

  test('고른 학년을 저장하고 다음 방문에 되살린다', () {
    SelectionNotifier.persist = true;
    store.writePublic(gradeBandStoreKey, 'bogus');

    final first = ProviderContainer();
    expect(first.read(selectionProvider).gradeBand, 'elem_low');
    first.read(selectionProvider.notifier).setGradeBand('high');
    expect(store.readPublic(gradeBandStoreKey), 'high');
    // 학군만 바꿔도 학년 기억은 그대로다.
    first.read(selectionProvider.notifier).setRegion('mokdong');
    expect(store.readPublic(gradeBandStoreKey), 'high');
    first.dispose();

    final next = ProviderContainer(); // 다음 방문
    expect(next.read(selectionProvider).gradeBand, 'high');
    // 링크의 ?band= 로 들어온 것도 그 사람의 최근 선택이다.
    next
        .read(selectionProvider.notifier)
        .restore(next.read(selectionProvider).copyWith(gradeBand: 'middle'));
    expect(store.readPublic(gradeBandStoreKey), 'middle');
    next.dispose();
  });

  test('테스트 환경에서는 저장소에 쓰지 않는다', () {
    store.writePublic(gradeBandStoreKey, 'elem_high');
    final c = ProviderContainer();
    expect(c.read(selectionProvider).gradeBand, 'elem_low');
    c.read(selectionProvider.notifier).setGradeBand('middle');
    expect(store.readPublic(gradeBandStoreKey), 'elem_high');
    c.dispose();
  });
}
