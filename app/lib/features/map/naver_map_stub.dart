import 'package:flutter/material.dart';

/// 웹이 아닌 플랫폼용. 네이버 지도 JS SDK 는 웹에서만 동작한다.
/// iOS·Android 는 네이티브 SDK 가 따로 있으므로 나중에 여기만 교체하면 된다.
bool get naverMapAvailable => false;

class NaverMapView extends StatelessWidget {
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
  Widget build(BuildContext context) => const SizedBox.shrink();
}
