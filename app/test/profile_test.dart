import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:edutree/core/theme.dart';
import 'package:edutree/data/models.dart';
import 'package:edutree/features/academy/profile_section.dart';
import 'package:edutree/widgets/academy_card.dart';
import 'package:edutree/widgets/annals.dart';

/// '학부모가 그리는 이 학원' — 파이프라인 계약(docs/PROFILES.md)의 화면 쪽.
///
/// 픽스처는 pipeline/tests/fixtures/profile_sample.json 의 사본이다. 계약이
/// 바뀌면 양쪽을 함께 고친다.
void main() {
  Map<String, dynamic> fixture() =>
      (jsonDecode(File('test/fixtures/profile_sample.json').readAsStringSync())
              as Map)
          .cast<String, dynamic>();

  /// 실제 academies.json 한 줄의 최소 꼴. 근거 목록에 첫 인용의 원문이 이미
  /// [1] 로 있다 — 같은 원문이면 같은 번호를 받아야 한다.
  Map<String, dynamic> academyJson({Map<String, dynamic>? profile}) => {
    'id': 'a1',
    'name': '테스트어학원',
    'regionId': 'daechi',
    'subjects': ['english'],
    'score': {
      'total': 60,
      'reputation': 60,
      'momentum': 60,
      'transparency': 60,
      'selectivity': 60,
      'sampleSize': 40,
      'confidence': 'high',
      'isRanked': true,
    },
    'evidence': [
      {
        'source': 'cafe',
        'url': 'https://cafe.naver.com/x/1',
        'title': '첫 글',
        'snippet': '',
        'ref': 1,
      },
    ],
    'profile': ?profile,
  };

  Academy academy({AcademyProfile? profile}) => Academy(
    id: 'a1',
    name: '테스트어학원',
    displayNameRaw: '테스트어학원',
    aliases: const [],
    regionId: 'daechi',
    subjects: const ['english'],
    gradeBands: const [],
    stages: const [],
    flagship: const [],
    isVerified: false,
    dataSource: 'neis',
    score: const Score(
      total: 60,
      reputation: 60,
      momentum: 60,
      transparency: 60,
      selectivity: 60,
      sampleSize: 40,
      confidence: 'high',
      isRanked: true,
      momentumDirection: 'stable',
    ),
    evidence: const [],
    profile: profile,
  );

  group('모델', () {
    test('profile 이 있으면 읽고, 인용 원문은 근거 목록과 같은 번호를 받는다', () {
      final a = Academy.fromJson(academyJson(profile: fixture()));
      final p = a.profile;
      expect(p, isNotNull);
      expect(p!.sources, 38);
      expect(p.model, 'gemini-3.7-flash');
      expect(p.levelTest?.band, 'S');
      expect(p.levelTest?.hard, '컷·라이팅');
      expect(p.homework?.load, '중상');
      expect(p.fit?.goodFor, hasLength(2));
      expect(p.fit?.caution, hasLength(2));
      expect(p.ops?.shuttle, isFalse);
      expect(p.ops?.quotes.single.isSelf, isTrue);
      expect(p.oneLiner, '레테 S · 숙제 중상 · 자체교재 노블 정독');
      expect(p.hasContent, isTrue);

      final refs = a.sourceRefs;
      // 근거 목록에 이미 있던 원문은 그 번호 그대로.
      expect(refs['https://cafe.naver.com/x/1'], 1);
      // 새 원문은 그 뒤 번호를 차례로. 프로필 인용 9건 중 1건이 겹치므로 8.
      expect(refs['https://cafe.naver.com/x/2'], 2);
      expect(refs['https://www.gangmom.kr/institute/abc'], 9);
      expect(refs, hasLength(9));
    });

    test('profile 이 없으면 null 이고 번호 장부도 그대로다', () {
      final a = Academy.fromJson(academyJson());
      expect(a.profile, isNull);
      expect(a.sourceRefs, {'https://cafe.naver.com/x/1': 1});
    });

    test('다섯 절이 전부 비면 내용이 없다', () {
      final j = fixture();
      for (final k in ['levelTest', 'homework', 'curriculum', 'fit', 'ops']) {
        j[k] = null;
      }
      final p = AcademyProfile.fromJson(j);
      expect(p.hasContent, isFalse);
      expect(p.sections, isEmpty);
      expect(p.oneLiner, isNotNull, reason: '한 줄은 절과 별개로 온다');
    });

    test('같은 글의 인용 둘은 근거 한 건이다', () {
      const s = ProfileSection(
        note: 'x',
        quotes: [
          ProfileQuote(quote: 'a', url: 'u1'),
          ProfileQuote(quote: 'b', url: 'u1'),
          ProfileQuote(quote: 'c', url: 'u2'),
        ],
      );
      expect(s.sourceCount, 2);
    });
  });

  group('상세 — 학부모가 그리는 이 학원', () {
    const firstQuote = '“문제는 어렵지 않은데 라이팅 컷이 높아서 떨어졌어요”';

    Future<void> pump(
      WidgetTester tester,
      Academy a, {
      Brightness brightness = Brightness.light,
    }) async {
      tester.view.physicalSize = const Size(1000, 2400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(brightness: brightness),
          home: Scaffold(body: ProfilePanel(academy: a)),
        ),
      );
      await tester.pump();
    }

    testWidgets('절이 뜨고, 빈 절은 "아직 근거 부족", 행을 누르면 인용이 펼쳐진다', (
      tester,
    ) async {
      final j = fixture();
      j['curriculum'] = null; // 근거 부족으로 온 절
      await pump(tester, academy(profile: AcademyProfile.fromJson(j)));

      expect(find.text('학부모가 그리는 이 학원'), findsOneWidget);
      expect(find.textContaining('후기 38건을 AI가 추려 적었습니다'), findsOneWidget);
      for (final label in ['레벨테스트', '숙제', '커리큘럼', '잘 맞는 아이', '주의', '위치·운영']) {
        expect(find.text(label), findsOneWidget, reason: '$label 행');
      }
      // 빈 절은 빈칸이 아니라 말로 적는다 — 커리큘럼 하나뿐.
      expect(find.text('아직 근거 부족'), findsOneWidget);
      // 등급은 꼬리표. 주묵이 아니라 추정색.
      final band = tester.widget<TagMark>(find.widgetWithText(TagMark, 'S'));
      expect(band.color, AppColors.estimatedOn(false));
      expect(band.color, isNot(AppColors.accentOn(false)));
      expect(find.widgetWithText(TagMark, '중상'), findsOneWidget);
      // 본문과 근거 수.
      expect(
        find.text('문제 자체보다 합격 컷과 라이팅 채점이 까다롭다는 평이 반복된다.'),
        findsOneWidget,
      );
      expect(find.text('· 말하고 참여하며 책을 좋아하는 아이'), findsOneWidget);
      expect(find.text('· 반·교사차를 확인할 것'), findsOneWidget);
      expect(find.text('근거 2건'), findsNWidgets(4)); // 레테·숙제·잘맞·주의
      expect(find.text('근거 1건'), findsOneWidget); // 운영
      // 맨 아래 한 줄.
      expect(find.text('생성 2026-09-17 · 모델 gemini-3.7-flash'), findsOneWidget);

      // 인용은 접혀 있다. 행을 누르면 열리고, 다시 누르면 닫힌다.
      expect(find.text(firstQuote), findsNothing);
      await tester.tap(find.text('레벨테스트'));
      await tester.pump();
      expect(find.text(firstQuote), findsOneWidget);
      expect(find.text('2026-02-11'), findsOneWidget);
      await tester.tap(find.text('레벨테스트'));
      await tester.pump();
      expect(find.text(firstQuote), findsNothing);

      // 학원 자기 서술은 꼬리표로 가른다.
      expect(find.text('학원 자기 서술'), findsNothing);
      await tester.tap(find.text('위치·운영'));
      await tester.pump();
      expect(find.text('“셔틀은 운행하지 않습니다”'), findsOneWidget);
      expect(find.widgetWithText(TagMark, '학원 자기 서술'), findsOneWidget);

      // 빈 절은 눌러도 아무것도 안 열린다.
      await tester.tap(find.text('커리큘럼'));
      await tester.pump();
      expect(find.text('아직 근거 부족'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('profile 이 없거나 다섯 절이 전부 비면 절 자체를 그리지 않는다', (
      tester,
    ) async {
      await pump(tester, academy());
      expect(find.text('학부모가 그리는 이 학원'), findsNothing);

      await pump(tester, academy(profile: const AcademyProfile(sources: 3)));
      expect(find.text('학부모가 그리는 이 학원'), findsNothing);
      expect(find.text('아직 근거 부족'), findsNothing);
    });

    testWidgets('먹빛 판면에서도 같은 절이 뜨고 색이 뒤집힌다', (tester) async {
      await pump(
        tester,
        academy(profile: AcademyProfile.fromJson(fixture())),
        brightness: Brightness.dark,
      );
      expect(find.text('학부모가 그리는 이 학원'), findsOneWidget);
      final band = tester.widget<TagMark>(find.widgetWithText(TagMark, 'S'));
      expect(band.color, AppColors.estimatedOn(true));
      await tester.tap(find.text('숙제'));
      await tester.pump();
      expect(find.text('“숙제가 날마다 달라서 어떤 날은 두 시간”'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  });

  group('랭킹', () {
    // 맞춤 필터는 없앴다. 관점 감성으로 '선생님 평 좋은' 을 거르는 것은
    // 근거가 얇고, 그 자리를 프로필 카드가 맡는다. 되살아나면 여기서 잡힌다.
    test('맞춤 필터가 남지 않았다', () {
      final src = File(
        'lib/features/ranking/ranking_page.dart',
      ).readAsStringSync();
      expect(src.contains('_Fit'), isFalse);
      expect(src.contains('맞춤'), isFalse);
      expect(src.contains("'조건에 맞는 학원이 없습니다'"), isTrue);
    });

    testWidgets('카드는 프로필 한 줄을 적고, 없으면 아무것도 안 적는다', (tester) async {
      tester.view.physicalSize = const Size(900, 600);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);
      const line = '레테 S · 숙제 중상 · 자체교재 노블 정독';

      Future<void> pump(Academy a) async {
        await tester.pumpWidget(
          ProviderScope(
            child: MaterialApp(
              home: Scaffold(
                body: AcademyCard(academy: a, showPillars: false),
              ),
            ),
          ),
        );
        await tester.pump();
      }

      await pump(academy(profile: AcademyProfile.fromJson(fixture())));
      expect(find.text(line), findsOneWidget);
      final t = tester.widget<Text>(find.text(line));
      expect(t.maxLines, 1);
      expect(t.style?.color, AppColors.mutedOn(false));

      await pump(academy());
      expect(find.text(line), findsNothing);
      expect(tester.takeException(), isNull);
    });
  });
}
