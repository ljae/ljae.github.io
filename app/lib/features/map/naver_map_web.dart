import 'dart:js_interop';
import 'dart:ui_web' as ui_web;

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
///
/// 뷰 타입을 인스턴스마다 새로 등록하지 않는다. 한 번만 등록하고 div 의
/// id 로 구분한다 — 재등록하면 Flutter 가 중복 등록 예외를 던진다.
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
  static int _seq = 0;

  late final String _elementId = 'hakwon-map-${_seq++}';

  @override
  void initState() {
    super.initState();
    if (!_registered) {
      _registered = true;
      ui_web.platformViewRegistry.registerViewFactory(_viewType, (int id, {Object? params}) {
        final div = web.document.createElement('div') as web.HTMLDivElement;
        div.id = (params as String?) ?? 'hakwon-map-$id';
        div.style
          ..width = '100%'
          ..height = '100%';
        return div;
      });
    }
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

  void _draw() {
    // 플랫폼 뷰가 DOM 에 붙은 다음 프레임에 그린다. 바로 부르면 div 가 없다.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      try {
        _init(_elementId, widget.lat, widget.lng, widget.zoom, widget.markersJson);
      } catch (_) {
        // SDK 미로드·인증 실패. 상위에서 모식도로 대체한다.
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    _draw();
    return HtmlElementView(
      viewType: _viewType,
      creationParams: _elementId,
      onPlatformViewCreated: (_) => _draw(),
    );
  }
}
