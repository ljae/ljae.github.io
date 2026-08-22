import 'package:flutter/material.dart';

/// 파이프라인이 내보낸 JSON을 그대로 받는 모델들.
/// 필드명은 pipeline/edutree/build.py 의 export() 와 1:1 대응한다.

class Region {
  final String id;
  final String nameKo;
  final String nameEn;
  final String sigungu;
  final List<String> dongList;
  final String tagline;
  final double lat;
  final double lng;

  const Region({
    required this.id,
    required this.nameKo,
    required this.nameEn,
    required this.sigungu,
    required this.dongList,
    required this.tagline,
    required this.lat,
    required this.lng,
  });

  factory Region.fromJson(Map<String, dynamic> j) {
    final center = (j['center'] as List?) ?? const [37.5, 127.0];
    return Region(
      id: j['id'] as String,
      nameKo: j['name_ko'] as String,
      nameEn: j['name_en'] as String,
      sigungu: j['sigungu'] as String,
      dongList: (j['dong_list'] as List).cast<String>(),
      tagline: (j['tagline'] ?? '') as String,
      lat: (center[0] as num).toDouble(),
      lng: (center[1] as num).toDouble(),
    );
  }
}

class Stage {
  final String id;
  final String trackId;
  final String title;
  final String? subtitle;
  final String? goal;
  final String? exitCriteria;
  final int gradeMin;
  final int gradeMax;
  final int depth;
  final int lane;

  const Stage({
    required this.id,
    required this.trackId,
    required this.title,
    this.subtitle,
    this.goal,
    this.exitCriteria,
    required this.gradeMin,
    required this.gradeMax,
    required this.depth,
    required this.lane,
  });

  factory Stage.fromJson(Map<String, dynamic> j, String trackId) {
    final grade = (j['grade'] as List?) ?? const [1, 12];
    return Stage(
      id: j['id'] as String,
      trackId: trackId,
      title: j['title'] as String,
      subtitle: j['subtitle'] as String?,
      goal: j['goal'] as String?,
      exitCriteria: j['exit_criteria'] as String?,
      gradeMin: (grade[0] as num).toInt(),
      gradeMax: (grade[1] as num).toInt(),
      depth: (j['depth'] as num?)?.toInt() ?? 0,
      lane: (j['lane'] as num?)?.toInt() ?? 0,
    );
  }

  String get gradeLabel => gradeMin == gradeMax
      ? gradeName(gradeMin)
      : '${gradeName(gradeMin)}~${gradeName(gradeMax)}';

  static String gradeName(int g) {
    if (g <= 6) return '초$g';
    if (g <= 9) return '중${g - 6}';
    return '고${g - 9}';
  }
}

enum EdgeType { standard, accelerated, alternative }

class StageEdge {
  final String from;
  final String to;
  final String condition;
  final EdgeType type;

  const StageEdge({
    required this.from,
    required this.to,
    required this.condition,
    required this.type,
  });

  factory StageEdge.fromList(List raw) => StageEdge(
        from: raw[0] as String,
        to: raw[1] as String,
        condition: raw.length > 2 ? (raw[2] as String? ?? '') : '',
        type: switch (raw.length > 3 ? raw[3] : 'standard') {
          'accelerated' => EdgeType.accelerated,
          'alternative' => EdgeType.alternative,
          _ => EdgeType.standard,
        },
      );
}

class Track {
  final String id;
  final String subject;
  final String schoolLevel;
  final String title;
  final String summary;
  final List<Stage> stages;
  final List<StageEdge> edges;

  const Track({
    required this.id,
    required this.subject,
    required this.schoolLevel,
    required this.title,
    required this.summary,
    required this.stages,
    required this.edges,
  });

  factory Track.fromJson(Map<String, dynamic> j) {
    final id = j['id'] as String;
    return Track(
      id: id,
      subject: j['subject'] as String,
      schoolLevel: j['school_level'] as String,
      title: j['title'] as String,
      summary: (j['summary'] ?? '') as String,
      stages: (j['stages'] as List)
          .map((s) => Stage.fromJson(s as Map<String, dynamic>, id))
          .toList(),
      edges: ((j['edges'] as List?) ?? const [])
          .map((e) => StageEdge.fromList(e as List))
          .toList(),
    );
  }
}

class Score {
  final double total;
  final double reputation;
  final double momentum;
  final double transparency;
  final double selectivity;
  final int sampleSize;
  final String confidence;
  final bool isRanked;
  final String momentumDirection;
  final int? rankInRegion;
  final int? regionRankedCount;
  final Map<String, dynamic> breakdown;

  const Score({
    required this.total,
    required this.reputation,
    required this.momentum,
    required this.transparency,
    required this.selectivity,
    required this.sampleSize,
    required this.confidence,
    required this.isRanked,
    required this.momentumDirection,
    this.rankInRegion,
    this.regionRankedCount,
    this.breakdown = const {},
  });

  factory Score.fromJson(Map<String, dynamic> j) => Score(
        total: (j['total'] as num).toDouble(),
        reputation: (j['reputation'] as num).toDouble(),
        momentum: (j['momentum'] as num).toDouble(),
        transparency: (j['transparency'] as num).toDouble(),
        selectivity: (j['selectivity'] as num).toDouble(),
        sampleSize: (j['sampleSize'] as num).toInt(),
        confidence: j['confidence'] as String,
        isRanked: j['isRanked'] as bool,
        momentumDirection: (j['momentumDirection'] ?? 'stable') as String,
        rankInRegion: (j['rankInRegion'] as num?)?.toInt(),
        regionRankedCount: (j['regionRankedCount'] as num?)?.toInt(),
        breakdown: (j['breakdown'] as Map?)?.cast<String, dynamic>() ?? const {},
      );

  double pillar(String key) => switch (key) {
        'reputation' => reputation,
        'momentum' => momentum,
        'transparency' => transparency,
        'selectivity' => selectivity,
        _ => 0,
      };

  String get confidenceLabel => switch (confidence) {
        'high' => '표본 충분',
        'medium' => '표본 보통',
        _ => '표본 부족',
      };
}

class Evidence {
  final String source;
  final String url;
  final String title;
  final String snippet;
  final String? postedAt;
  final double sentiment;
  final double credibility;

  const Evidence({
    required this.source,
    required this.url,
    required this.title,
    required this.snippet,
    this.postedAt,
    required this.sentiment,
    required this.credibility,
  });

  factory Evidence.fromJson(Map<String, dynamic> j) => Evidence(
        source: j['source'] as String,
        url: j['url'] as String,
        title: (j['title'] ?? '') as String,
        snippet: (j['snippet'] ?? '') as String,
        postedAt: j['posted_at'] as String?,
        sentiment: (j['sentiment'] as num?)?.toDouble() ?? 0,
        credibility: (j['credibility'] as num?)?.toDouble() ?? 0,
      );

  String get sourceLabel => switch (source) {
        'naver_cafe' => '네이버 카페',
        'naver_blog' => '네이버 블로그',
        'naver_kin' => '지식iN',
        'cafe_local' => '카페 수집',
        _ => source,
      };
}

class Academy {
  final String id;
  final String name;
  /// 화면에 찍는 이름. 파이프라인이 학군 내 중복을 없앤 뒤 내려준다.
  /// 지점이 여럿이면 도로명이 붙는다: '씨앤씨 (목동서로 389)'
  final String displayNameRaw;
  final String? brand;
  final List<String> aliases;
  final String regionId;
  final List<String> subjects;
  final List<String> schoolLevels;
  final List<String> stages;
  final List<String> flagship;
  final String? address;
  final String? tel;
  final int? capacity;
  final int? tuitionMonthly;
  final String? tuitionRaw;
  final String? registrationStatus;
  final String? establishedOn;
  final bool isVerified;
  final String dataSource;
  final double? lat;
  final double? lng;
  /// NEIS 등록 건수. 1보다 크면 여러 관/과정 등록을 하나로 묶은 것이다.
  final int registrationCount;
  final Score score;
  final List<Evidence> evidence;

  const Academy({
    required this.id,
    required this.name,
    required this.displayNameRaw,
    this.brand,
    required this.aliases,
    required this.regionId,
    required this.subjects,
    required this.schoolLevels,
    required this.stages,
    required this.flagship,
    this.address,
    this.tel,
    this.capacity,
    this.tuitionMonthly,
    this.tuitionRaw,
    this.registrationStatus,
    this.establishedOn,
    required this.isVerified,
    required this.dataSource,
    this.lat,
    this.lng,
    this.registrationCount = 1,
    required this.score,
    required this.evidence,
  });

  factory Academy.fromJson(Map<String, dynamic> j) => Academy(
        id: j['id'] as String,
        name: j['name'] as String,
        displayNameRaw: (j['displayName'] ?? j['name']) as String,
        brand: j['brand'] as String?,
        aliases: ((j['aliases'] as List?) ?? const []).cast<String>(),
        regionId: (j['regionId'] ?? '') as String,
        subjects: ((j['subjects'] as List?) ?? const []).cast<String>(),
        schoolLevels: ((j['schoolLevels'] as List?) ?? const []).cast<String>(),
        stages: ((j['stages'] as List?) ?? const []).cast<String>(),
        flagship: ((j['flagship'] as List?) ?? const []).cast<String>(),
        address: j['address'] as String?,
        tel: j['tel'] as String?,
        capacity: (j['capacity'] as num?)?.toInt(),
        tuitionMonthly: (j['tuitionMonthly'] as num?)?.toInt(),
        tuitionRaw: j['tuitionRaw'] as String?,
        registrationStatus: j['registrationStatus'] as String?,
        establishedOn: j['establishedOn'] as String?,
        isVerified: (j['isVerified'] ?? false) as bool,
        dataSource: (j['dataSource'] ?? 'seed') as String,
        lat: (j['lat'] as num?)?.toDouble(),
        lng: (j['lng'] as num?)?.toDouble(),
        registrationCount: (j['registrationCount'] as num?)?.toInt() ?? 1,
        score: Score.fromJson((j['score'] as Map).cast<String, dynamic>()),
        evidence: ((j['evidence'] as List?) ?? const [])
            .map((e) => Evidence.fromJson((e as Map).cast<String, dynamic>()))
            .toList(),
      );

  /// 큐레이션 브랜드명(brand)을 표시에 쓰지 않는다. 브랜드는 지점을
  /// 구분하지 못해서, 서로 다른 CMS 지점 두 곳이 같은 이름으로 나왔다.
  String get displayName => displayNameRaw;

  /// 브랜드가 실제 학원명과 다를 때만 의미가 있다 (예: 씨엠에스학원 → CMS영재교육)
  String? get brandLabel =>
      (brand != null && brand != name && !name.contains(brand!)) ? brand : null;
  bool isFlagshipOf(String stageId) => flagship.contains(stageId);
}

class Meta {
  final String mode;
  final String generatedAt;
  final int evaluatedCount;
  final int registryCount;
  final int mentionCount;
  final Map<String, double> weights;
  final int minSampleForRank;
  final int reputationPriorCount;
  final int recencyHalflifeDays;

  const Meta({
    required this.mode,
    required this.generatedAt,
    required this.evaluatedCount,
    required this.registryCount,
    required this.mentionCount,
    required this.weights,
    required this.minSampleForRank,
    required this.reputationPriorCount,
    required this.recencyHalflifeDays,
  });

  bool get isDemo => mode == 'demo';

  factory Meta.fromJson(Map<String, dynamic> j) => Meta(
        mode: (j['mode'] ?? 'demo') as String,
        generatedAt: (j['generatedAt'] ?? '') as String,
        evaluatedCount: (j['evaluatedCount'] as num?)?.toInt() ?? 0,
        registryCount: (j['registryCount'] as num?)?.toInt() ?? 0,
        mentionCount: (j['mentionCount'] as num?)?.toInt() ?? 0,
        weights: ((j['weights'] as Map?) ?? const {})
            .map((k, v) => MapEntry(k as String, (v as num).toDouble())),
        minSampleForRank: (j['minSampleForRank'] as num?)?.toInt() ?? 10,
        reputationPriorCount: (j['reputationPriorCount'] as num?)?.toInt() ?? 12,
        recencyHalflifeDays: (j['recencyHalflifeDays'] as num?)?.toInt() ?? 180,
      );
}

/// 등록부 엔트리 — NEIS로 검증됐지만 커뮤니티 수집 대상은 아니었던 학원.
///
/// 점수를 갖지 않는다. '평가했는데 낮은 점수'와 '아직 보지 않음'은 다르고,
/// 둘을 같은 화면에 같은 모양으로 두면 그 자체가 왜곡이다.
class RegistryEntry {
  final String id;
  final String name;
  final String displayName;
  final String regionId;
  final String? dong;
  final List<String> subjects;
  final String? address;
  final int? capacity;
  final int? tuitionMonthly;
  final String? registrationStatus;
  final bool isVerified;
  final int registrationCount;

  const RegistryEntry({
    required this.id,
    required this.name,
    required this.displayName,
    required this.regionId,
    this.dong,
    required this.subjects,
    this.address,
    this.capacity,
    this.tuitionMonthly,
    this.registrationStatus,
    required this.isVerified,
    this.registrationCount = 1,
  });

  factory RegistryEntry.fromJson(Map<String, dynamic> j) => RegistryEntry(
        id: j['id'] as String,
        name: j['name'] as String,
        displayName: (j['displayName'] ?? j['name']) as String,
        regionId: (j['regionId'] ?? '') as String,
        dong: j['dong'] as String?,
        subjects: ((j['subjects'] as List?) ?? const []).cast<String>(),
        address: j['address'] as String?,
        capacity: (j['capacity'] as num?)?.toInt(),
        tuitionMonthly: (j['tuitionMonthly'] as num?)?.toInt(),
        registrationStatus: j['registrationStatus'] as String?,
        isVerified: (j['isVerified'] ?? false) as bool,
      );
}

/// 학교. 학군지도의 주인공이다 — 어느 학교에 배정되느냐가 곧 학군이다.
class School {
  final String id;
  final String name;
  final String level;            // elementary | middle | high
  final String levelLabel;       // 초등학교 | 중학교 | 고등학교
  final String regionId;
  final String? dong;
  final String? foundation;      // 공립 | 사립
  final String? coed;            // 남여공학 | 남 | 여
  final String? highKind;        // 일반고 | 특목고 …
  final String? address;
  final String? homepage;
  final double? lat;
  final double? lng;
  final String? zoneId;
  final String? zoneName;
  final String? eduOffice;
  final List<String> zonePeers;
  /// '통학구역'(초등 1:1) 또는 '학교군 추첨'(중·고)
  final String? assignment;

  const School({
    required this.id,
    required this.name,
    required this.level,
    required this.levelLabel,
    required this.regionId,
    this.dong,
    this.foundation,
    this.coed,
    this.highKind,
    this.address,
    this.homepage,
    this.lat,
    this.lng,
    this.zoneId,
    this.zoneName,
    this.eduOffice,
    this.zonePeers = const [],
    this.assignment,
  });

  factory School.fromJson(Map<String, dynamic> j) => School(
        id: '${j['id']}',
        name: j['name'] as String,
        level: (j['level'] ?? 'elementary') as String,
        levelLabel: (j['levelLabel'] ?? '') as String,
        regionId: (j['regionId'] ?? '') as String,
        dong: j['dong'] as String?,
        foundation: j['foundation'] as String?,
        coed: j['coed'] as String?,
        highKind: j['highKind'] as String?,
        address: j['address'] as String?,
        homepage: j['homepage'] as String?,
        lat: (j['lat'] as num?)?.toDouble(),
        lng: (j['lng'] as num?)?.toDouble(),
        zoneId: j['zoneId'] as String?,
        zoneName: j['zoneName'] as String?,
        eduOffice: j['eduOffice'] as String?,
        zonePeers: ((j['zonePeers'] as List?) ?? const []).cast<String>(),
        assignment: j['assignment'] as String?,
      );

  bool get hasLocation => lat != null && lng != null;
}

/// 아파트 단지. 학군지도에서 '이 집은 어느 학교인가'를 잇는 고리.
class Apartment {
  final String id;
  final String name;
  final String regionId;
  final String? dong;
  final String? address;
  final int? households;
  final int? buildings;
  final double? lat;
  final double? lng;
  /// 이 단지가 속한 학교군들. 중·고는 추첨 배정이라 '배정'이 아니라 '소속'이다.
  final List<ApartmentZone> zones;

  const Apartment({
    required this.id,
    required this.name,
    required this.regionId,
    this.dong,
    this.address,
    this.households,
    this.buildings,
    this.lat,
    this.lng,
    this.zones = const [],
  });

  factory Apartment.fromJson(Map<String, dynamic> j) => Apartment(
        id: '${j['id']}',
        name: (j['name'] ?? '') as String,
        regionId: (j['regionId'] ?? '') as String,
        dong: j['dong'] as String?,
        address: j['address'] as String?,
        households: (j['households'] as num?)?.toInt(),
        buildings: (j['buildings'] as num?)?.toInt(),
        lat: (j['lat'] as num?)?.toDouble(),
        lng: (j['lng'] as num?)?.toDouble(),
        zones: ((j['zones'] as List?) ?? const [])
            .map((z) => ApartmentZone.fromJson((z as Map).cast<String, dynamic>()))
            .toList(),
      );

  bool get hasLocation => lat != null && lng != null;
}

class ApartmentZone {
  final String? zoneId;
  final String? zoneName;
  final String? level;
  final List<String> schools;
  /// 초등 통학구역이면서 학교가 하나일 때만 true — '배정'이라 단정할 수 있다.
  final bool certain;

  const ApartmentZone({
    this.zoneId,
    this.zoneName,
    this.level,
    this.schools = const [],
    this.certain = false,
  });

  factory ApartmentZone.fromJson(Map<String, dynamic> j) => ApartmentZone(
        zoneId: j['zoneId'] as String?,
        zoneName: j['zoneName'] as String?,
        level: j['level'] as String?,
        schools: ((j['schools'] as List?) ?? const []).cast<String>(),
        certain: (j['certain'] ?? false) as bool,
      );

  String get levelLabel => switch (level) {
        'middle' => '중학교',
        'high' => '고등학교',
        _ => '초등학교',
      };

  /// 화면 문구. 추첨을 '배정'이라 쓰지 않는 것이 이 게터의 존재 이유다.
  String get assignmentText {
    if (certain && schools.isNotEmpty) return '${schools.first} 배정';
    if (schools.isEmpty) return zoneName ?? '';
    if (level == 'elementary') return '$zoneName (${schools.length}개교 공동)';
    return '$zoneName · ${schools.length}개교 중 추첨';
  }
}

const schoolLevelColors = <String, int>{
  'elementary': 0xFF2F7DD1,
  'middle': 0xFF1E7A5A,
  'high': 0xFFB4531E,
};

/// 과목 · 학교급 표시 이름
const subjectNames = <String, String>{
  'math': '수학',
  'english': '영어',
  'korean': '국어·논술',
  'science': '과학',
  'etc': '종합·보습',
};

const schoolLevelNames = <String, String>{
  'elementary': '초등',
  'middle': '중등',
  'high': '고등',
};

const pillarNames = <String, String>{
  'reputation': '평판',
  'momentum': '화제성',
  'transparency': '투명성',
  'selectivity': '진입난이도',
};

const pillarDescriptions = <String, String>{
  'reputation': '커뮤니티 후기의 감성을 신뢰도·최신성으로 가중한 값',
  'momentum': '언급량과 12개월 추세로 본 관심도',
  'transparency': 'NEIS 공시 항목 기반 규칙 채점 — 검증 가능',
  'selectivity': '레벨테스트 난이도·대기 언급에서 추정 — 공식 경쟁률 아님',
};

const pillarIcons = <String, IconData>{
  'reputation': Icons.forum_outlined,
  'momentum': Icons.trending_up,
  'transparency': Icons.verified_outlined,
  'selectivity': Icons.filter_alt_outlined,
};
