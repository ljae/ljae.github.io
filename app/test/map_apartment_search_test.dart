import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:edutree/data/models.dart';
import 'package:edutree/data/repository.dart';
import 'package:edutree/features/map/map_page.dart';

void main() {
  testWidgets(
    'an apartment beyond the old top40 can be found by its spaced or compact name',
    (tester) async {
      final a =
          (jsonDecode(File('assets/data/apartments.json').readAsStringSync())
                  as List)
              .map(
                (e) => Apartment.fromJson(Map<String, dynamic>.from(e as Map)),
              )
              .toList();
      final rows = MapData(apartments: a).apartmentsIn('daechi');
      expect(
        rows.indexWhere((a) => a.name.contains('푸르지오 발라드')),
        greaterThanOrEqualTo(40),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: MapApartmentList(apartments: rows),
            ),
          ),
        ),
      );
      await tester.enterText(
        find.byKey(const Key('apartment-search')),
        '푸르지오발라드',
      );
      await tester.pump();
      expect(find.text('대치 푸르지오 발라드'), findsOneWidget);
      await tester.enterText(
        find.byKey(const Key('apartment-search')),
        '없는단지123',
      );
      await tester.pump();
      expect(find.text('검색한 아파트가 없습니다. 이름이나 주소를 바꿔보세요.'), findsOneWidget);
    },
  );
}
