/// 사용자가 '동작 줄이기'를 켰는지. 플랫폼마다 알아내는 길이 다르다.
///
/// 네이티브에서는 Flutter 가 `MediaQuery.disableAnimations` 로 이미 넘겨준다.
/// **웹은 그렇지 않았다** — 브라우저는 `prefers-reduced-motion: reduce` 로
/// 분명히 말하는데(실측: 크롬이 `matches=true` 를 주는 상태에서도
/// `MediaQuery.disableAnimations` 는 false 였다) Flutter 쪽 값이 안 따라왔다.
/// 그래서 연출을 끄는 길이 **웹에서만 통째로 막혀** 있었다.
/// 이 서비스가 실제로 도는 곳이 웹이므로, 웹에서는 미디어 쿼리를 직접 읽어
/// 그 값을 얹는다.
library;

export 'reduced_motion_stub.dart'
    if (dart.library.js_interop) 'reduced_motion_web.dart';
