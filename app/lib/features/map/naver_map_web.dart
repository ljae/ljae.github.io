import 'dart:async';
import 'dart:js_interop';
import 'dart:ui_web' as ui_web;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';
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

  /// 초기화를 타이머로 돌린다.
  ///
  /// 처음에는 addPostFrameCallback 을 썼는데 init 이 단 한 번도 호출되지
  /// 않았다. 그 콜백은 '다음 프레임'에 실행되는데, 정적인 화면에서는 다음
  /// 프레임이 예약되지 않아 영원히 오지 않는다. 타이머는 프레임과 무관하게
  /// 반드시 발화한다.
  ///
  /// 재시도가 필요한 이유는 따로 있다. 레이아웃이 잡히기 전에 부르면
  /// 네이버가 크기 0으로 지도를 만들어 버린다. 그래서 컨테이너에 실제
  /// 크기가 생길 때까지 기다린다.
  void _draw({int attempt = 0}) {
    final id = _viewId;
    if (id == null || !mounted) return;

    _retry?.cancel();
    _retry = Timer(Duration(milliseconds: attempt == 0 ? 16 : 150 * attempt), () {
      if (!mounted) return;
      final elementId = 'hakwon-map-$id';
      var ok = false;
      try {
        final el = web.document.getElementById(elementId) as web.HTMLElement?;
        // 크기가 0이면 지도가 접힌 채로 만들어진다. 다음 시도로 미룬다.
        if (el != null && el.clientWidth > 0 && el.clientHeight > 0) {
          ok = _init(elementId, widget.lat, widget.lng, widget.zoom,
              widget.markersJson);
        }
      } catch (e) {
        if (kDebugMode) debugPrint('naver map init 실패: $e');
      }
      if (ok) {
        _pump();
      } else if (attempt < 8) {
        _draw(attempt: attempt + 1);
      }
    });
  }

  /// 지도를 만든 뒤 프레임을 몇 번 강제로 돌린다.
  ///
  /// 지도는 정상적으로 그려져 있는데 화면에 안 나오다가, 클릭 한 번이면
  /// 즉시 나타났다. 정적인 화면에서는 플러터가 프레임을 예약하지 않아
  /// 플랫폼 뷰가 재합성되지 않기 때문이다. 입력이 들어오면 프레임이 돌고
  /// 그제서야 합성된다.
  ///
  /// JS 쪽에서 opacity·display 를 흔들어 봐도 소용없었다. 다시 그려야 하는
  /// 주체가 브라우저가 아니라 플러터의 합성기이기 때문이다.
  void _pump({int left = 12}) {
    if (!mounted || left <= 0) return;
    SchedulerBinding.instance.scheduleFrame();
    Timer(const Duration(milliseconds: 180), () => _pump(left: left - 1));
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
