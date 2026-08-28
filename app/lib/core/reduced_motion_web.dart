import 'package:web/web.dart' as web;

/// 브라우저의 `prefers-reduced-motion` 을 직접 읽는다.
///
/// 세션 중에 값이 바뀌는 일은 거의 없어 구독하지 않고 그릴 때마다 읽는다.
/// `matchMedia` 의 결과는 브라우저가 들고 있어 싸다.
bool platformPrefersReducedMotion() {
  try {
    return web.window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  } catch (_) {
    // 아주 옛 브라우저. 못 읽으면 '안 켰다'로 본다 —
    // 여기서 켜 버리면 멀쩡한 사람에게 연출이 통째로 사라진다.
    return false;
  }
}
