import 'dart:async';
import 'dart:js_interop';
import 'dart:ui_web' as ui_web;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:web/web.dart' as web;

@JS('hakwonMap.ready')
external bool _ready();

@JS('hakwonMap.init')
external bool _init(
    String id, double lat, double lng, int zoom, String payload);

bool get naverMapAvailable {
  try {
    return _ready();
  } catch (_) {
    // 키가 없어 SDK 를 아예 안 불렀을 때. 예외가 아니라 정상 경로다.
    return false;
  }
}

/// 네이버 지도를 감싼 플랫폼 뷰.
class NaverMapView extends StatefulWidget {
  final double lat;
  final double lng;
  final int zoom;
  final String markersJson;
  const NaverMapView({
    super.key,
    required this.lat,
    required this.lng,
    required this.zoom,
    required this.markersJson,
  });

  @override
  State<NaverMapView> createState() => _NaverMapViewState();
}

class _NaverMapViewState extends State<NaverMapView> {
  static const _viewType = 'hakwon-naver-map';
  static bool _registered = false;

  /// 플랫폼 뷰 id 로 div id 를 정한다.
  ///
  /// 처음에는 creationParams 로 id 를 넘겼는데, 뷰가 DOM 에 붙는 시점과
  /// Dart 가 init 을 부르는 시점이 어긋나 지도가 끝내 그려지지 않았다.
  /// (div 는 만들어졌는데 자식이 0개였다.) 뷰 id 를 콜백으로 받아 쓰면
  /// '붙은 뒤'가 보장된다.
  int? _viewId;
  Timer? _retry;

  @override
  void initState() {
    super.initState();
    if (!_registered) {
      _registered = true;
      ui_web.platformViewRegistry.registerViewFactory(_viewType, (int id) {
        final div = web.document.createElement('div') as web.HTMLDivElement;
        div.id = 'hakwon-map-$id';
        div.style
          ..width = '100%'
          ..height = '100%';
        return div;
      });
    }
  }

  @override
  void dispose() {
    _retry?.cancel();
    super.dispose();
  }

  @override
  void didUpdateWidget(covariant NaverMapView old) {
    super.didUpdateWidget(old);
    if (old.markersJson != widget.markersJson ||
        old.lat != widget.lat ||
        old.zoom != widget.zoom) {
      _draw();
    }
  }

  /// 몇 번 다시 시도한다. 레이아웃이 잡히기 전에 부르면 네이버가 크기 0으로
  /// 지도를 만들어 버려서, 성공(true)할 때까지 짧게 재시도하는 편이 안전하다.
  void _draw({int attempt = 0}) {
    final id = _viewId;
    if (id == null || !mounted) return;

    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      var ok = false;
      try {
        ok = _init('hakwon-map-$id', widget.lat, widget.lng, widget.zoom,
            widget.markersJson);
      } catch (e) {
        if (kDebugMode) debugPrint('naver map init 실패: $e');
      }
      if (!ok && attempt < 5) {
        _retry?.cancel();
        _retry = Timer(Duration(milliseconds: 120 * (attempt + 1)),
            () => _draw(attempt: attempt + 1));
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return HtmlElementView(
      viewType: _viewType,
      onPlatformViewCreated: (id) {
        _viewId = id;
        _draw();
      },
    );
  }
}
