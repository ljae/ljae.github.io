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

  /// 학군별 전출입 추이. '학군이 좋으면 전입이 많다'를 수치로 보여준다.
  final List<RegionTrend> trends;

  /// 등록부까지 포함한 학원 수. 파이프라인이 미리 세어 둔다 —
  /// 이 숫자 하나 때문에 첫 화면에서 등록부를 통째로 읽을 이유가 없다.
  final int academyCount;

  /// 그중 채점까지 마친 수
  final int evaluatedCount;

  const Region({
    required this.id,
    required this.nameKo,
    required this.nameEn,
    required this.sigungu,
    required this.dongList,
    required this.tagline,
    required this.lat,
    required this.lng,
    this.trends = const [],
    this.academyCount = 0,
    this.evaluatedCount = 0,
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
      trends: ((j['trends'] as List?) ?? const [])
          .map((t) => RegionTrend.fromJson((t as Map).cast<String, dynamic>()))
          .toList(),
      academyCount: (j['academy_count'] as num?)?.toInt() ?? 0,
      evaluatedCount: (j['evaluated_count'] as num?)?.toInt() ?? 0,
    );
  }

  /// 가장 최근 연도의 학교급별 순유입
  RegionTrend? latestTrend(String level) {
    final rows = trends.where((t) => t.level == level).toList()
      ..sort((a, b) => b.year.compareTo(a.year));
    return rows.isEmpty ? null : rows.first;
  }
}

class RegionTrend {
  final String year;
  final String level;
  final int transferIn;
  final int transferOut;
  final int netTransfer;
  final int schools;

  const RegionTrend({
    required this.year,
    required this.level,
    required this.transferIn,
    required this.transferOut,
    required this.netTransfer,
    required this.schools,
  });

  factory RegionTrend.fromJson(Map<String, dynamic> j) => RegionTrend(
    year: '${j['year']}',
    level: (j['level'] ?? '') as String,
    transferIn: (j['transferIn'] as num?)?.toInt() ?? 0,
    transferOut: (j['transferOut'] as num?)?.toInt() ?? 0,
    netTransfer: (j['netTransfer'] as num?)?.toInt() ?? 0,
    schools: (j['schools'] as num?)?.toInt() ?? 0,
  );
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

  /// 이 구간 밖이지만, 이 구간으로 들어오는 길의 출발점인 단계.
  /// 빼면 '어디서 오는 길인지'가 사라져서 함께 보여 준다.
  final bool inbound;

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
    this.inbound = false,
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
      inbound: j['inbound'] == true,
    );
  }

  String get gradeLabel => gradeMin == gradeMax
      ? gradeName(gradeMin)
      : '${gradeName(gradeMin)}~${gradeName(gradeMax)}';

  /// 0 = 예비초, -1 = 6세, -2 = 5세. 유아 구간은 로드맵 표시 전용이다.
  static String gradeName(int g) {
    if (g <= -2) return '5세';
    if (g == -1) return '6세';
    if (g == 0) return '예비초';
    if (g <= 6) return '초$g';
    if (g <= 9) return '중${g - 6}';
    return '고${g - 9}';
  }

  /// 이 단계가 걸치는 학년 구간. 경계를 걸치면 양쪽 모두에 든다.
  static const _bandRanges = <String, (int, int)>{
    'elem_low': (0, 3),
    'elem_high': (4, 6),
    'middle': (7, 9),
    'high': (10, 12),
  };

  List<String> get gradeBands => [
    for (final MapEntry(key: band, value: (lo, hi)) in _bandRanges.entries)
      if (gradeMin <= hi && gradeMax >= lo) band,
  ];
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

  factory StageEdge.fromList(List<dynamic> raw) => StageEdge(
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
  final String gradeBand;
  final String title;
  final String summary;
  final List<Stage> stages;
  final List<StageEdge> edges;

  const Track({
    required this.id,
    required this.subject,
    required this.gradeBand,
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
      gradeBand: j['grade_band'] as String,
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

  /// 예체능·기타는 채점하지 않아 null 이다. 0 으로 두면 '점수가 나쁘다'로
  /// 읽히므로, 없는 것은 없다고 표시한다.
  final double? transparency;
  final double? selectivity;

  /// academic | non_academic
  final String subjectGroup;
  final int sampleSize;
  final String confidence;
  final bool isRanked;
  final String momentumDirection;
  final int? rankInRegion;
  final int? regionRankedCount;

  /// 의견을 낸 후기 중 긍정 비율. 표본이 충분할 때만 값이 있다.
  /// 중립 서술은 분모에서 뺀다 — 넣으면 어디나 25~40%로 몰려 변별이 안 된다.
  final double? positiveRate;

  /// 진입난이도를 숫자 대신 등급으로. high | medium | mentioned | null.
  ///
  /// 표본 셋으로 만든 '난이도 74점' 은 정밀해 보이지만 그 정밀도가
  /// 근거에 없다. 숫자는 트리스코어 계산에만 쓰고 화면에는 등급과
  /// 인용문을 낸다.
  final String? selectivityTier;

  final Map<String, dynamic> breakdown;

  const Score({
    required this.total,
    required this.reputation,
    required this.momentum,
    this.transparency,
    this.selectivity,
    this.subjectGroup = 'academic',
    required this.sampleSize,
    required this.confidence,
    required this.isRanked,
    required this.momentumDirection,
    this.rankInRegion,
    this.regionRankedCount,
    this.positiveRate,
    this.selectivityTier,
    this.breakdown = const {},
  });

  factory Score.fromJson(Map<String, dynamic> j) => Score(
    total: (j['total'] as num).toDouble(),
    reputation: (j['reputation'] as num).toDouble(),
    momentum: (j['momentum'] as num).toDouble(),
    transparency: (j['transparency'] as num?)?.toDouble(),
    selectivity: (j['selectivity'] as num?)?.toDouble(),
    subjectGroup: (j['subjectGroup'] ?? 'academic') as String,
    sampleSize: (j['sampleSize'] as num).toInt(),
    confidence: j['confidence'] as String,
    isRanked: j['isRanked'] as bool,
    momentumDirection: (j['momentumDirection'] ?? 'stable') as String,
    positiveRate: (j['positiveRate'] as num?)?.toDouble(),
    selectivityTier: j['selectivityTier'] as String?,
    rankInRegion: (j['rankInRegion'] as num?)?.toInt(),
    regionRankedCount: (j['regionRankedCount'] as num?)?.toInt(),
    breakdown: (j['breakdown'] as Map?)?.cast<String, dynamic>() ?? const {},
  );

  /// 값이 없는 기둥(예체능의 투명성·진입난이도)은 0 을 돌려준다.
  /// 화면은 [subjectGroup] 으로 그릴지 말지 먼저 정한다.
  double pillar(String key) => pillarOrNull(key) ?? 0;

  double? pillarOrNull(String key) => switch (key) {
    'reputation' => reputation,
    'momentum' => momentum,
    'transparency' => transparency,
    'selectivity' => selectivity,
    _ => 0,
  };

  /// 진입난이도 등급 표시. 근거가 없으면 null — '쉽다'가 아니라
  /// '아직 모른다'는 뜻이므로 점수도 등급도 내지 않는다.
  String? get selectivityLabel => switch (selectivityTier) {
    'high' => '확인됨 · 높음',
    'medium' => '확인됨 · 중간',
    'mentioned' => '언급됨',
    _ => null,
  };

  /// 표본 0 은 '적다' 가 아니라 '아직 근거가 없다' 다. 둘을 같은 말로
  /// 적으면 50점이 평가 결과처럼 읽힌다.
  String get confidenceLabel => switch (confidence) {
    'high' => '표본 충분',
    'medium' => '표본 보통',
    _ => sampleSize == 0 ? '근거 없음' : '표본 부족',
  };
}

/// 후기에서 뽑아낸 주장 하나. 파이프라인의 claims.py 가 만든다.
///
/// 근거를 못 보여주는 값은 싣지 않는다 — 모든 줄이 인용문과 원문 링크를
/// 갖고, [claimId] 로 '이의'를 받는다. 취소된 줄도 목록에 남는다:
/// 왜 빠졌는지가 보여야 한다.
class ClaimEvidence {
  final String claimId;
  final String kind;
  final String label;
  final String quote;
  final String? url;
  final String? postedAt;

  /// active | revoked | stale
  final String status;
  final String? revokedReason;

  const ClaimEvidence({
    required this.claimId,
    required this.kind,
    required this.label,
    required this.quote,
    this.url,
    this.postedAt,
    this.status = 'active',
    this.revokedReason,
  });

  factory ClaimEvidence.fromJson(Map<String, dynamic> j) => ClaimEvidence(
    claimId: j['claimId'] as String,
    kind: (j['kind'] ?? '') as String,
    label: (j['label'] ?? '') as String,
    quote: (j['quote'] ?? '') as String,
    url: j['url'] as String?,
    postedAt: j['postedAt'] as String?,
    status: (j['status'] ?? 'active') as String,
    revokedReason: j['revokedReason'] as String?,
  );

  bool get isActive => status == 'active';

  String? get statusLabel => switch (status) {
    'revoked' => '이의로 제외됨',
    'stale' => '기한 지남',
    _ => null,
  };
}

/// 운영 사실 한 항목 (숙제량 · 시험 횟수 · 수업 횟수 · 1회 수업).
///
/// [text] 가 null 이면 값을 낼 만큼 근거가 없다는 뜻이다. 그때는 숫자를
/// 지어내지 말고 인용문만 보여준다 — 한 사람의 아이 반 이야기를 그
/// 학원의 사실로 적으면 그건 측정이 아니라 확대다.
class FactCard {
  final String label;
  final String unit;
  final String? text;
  final double? value;
  final int n;

  /// 값이 지나치게 갈려 중앙값을 낼 수 없는 상태.
  final bool disputed;
  final bool stale;
  final List<ClaimEvidence> quotes;

  /// 학년 구간마다 값이 실제로 다를 때만 채워진다.
  /// 주2회와 주5회의 평균 3.5회는 어느 반에도 없는 숫자다.
  final Map<String, FactCard> byBand;

  const FactCard({
    required this.label,
    required this.unit,
    this.text,
    this.value,
    required this.n,
    this.disputed = false,
    this.stale = false,
    this.quotes = const [],
    this.byBand = const {},
  });

  factory FactCard.fromJson(Map<String, dynamic> j) => FactCard(
    label: (j['label'] ?? '') as String,
    unit: (j['unit'] ?? '') as String,
    text: j['text'] as String?,
    value: (j['value'] as num?)?.toDouble(),
    n: (j['n'] as num?)?.toInt() ?? 0,
    disputed: (j['disputed'] ?? false) as bool,
    stale: (j['stale'] ?? false) as bool,
    quotes: ((j['quotes'] as List?) ?? const [])
        .map((e) => ClaimEvidence.fromJson((e as Map).cast<String, dynamic>()))
        .toList(),
    byBand: {
      for (final e in ((j['byBand'] as Map?) ?? const {}).entries)
        e.key as String: FactCard.fromJson(
          (e.value as Map).cast<String, dynamic>(),
        ),
    },
  );

  /// 값을 숫자로 말할 수 있는 상태인가.
  bool get hasValue => text != null;
}

/// 이 학원 근거 중 이의로 빠진 비율.
class DisputeRate {
  final int total;
  final int dropped;
  final double rate;

  const DisputeRate({
    required this.total,
    required this.dropped,
    required this.rate,
  });

  factory DisputeRate.fromJson(Map<String, dynamic> j) => DisputeRate(
    total: (j['total'] as num?)?.toInt() ?? 0,
    dropped: (j['dropped'] as num?)?.toInt() ?? 0,
    rate: (j['rate'] as num?)?.toDouble() ?? 0,
  );
}

class Evidence {
  final String source;
  final String url;
  final String title;
  final String snippet;
  final String? postedAt;
  final double sentiment;
  final double credibility;

  /// 이 글이 이 지점의 근거가 된 이유.
  /// 'region' = 글이 이 권역을 밝혔다. 'brand' = 지역을 밝히지 않아
  /// 같은 브랜드의 여러 지점에 함께 반영됐다.
  final String? branchBasis;

  const Evidence({
    required this.source,
    required this.url,
    required this.title,
    required this.snippet,
    this.postedAt,
    required this.sentiment,
    required this.credibility,
    this.branchBasis,
  });

  factory Evidence.fromJson(Map<String, dynamic> j) => Evidence(
    source: j['source'] as String,
    url: j['url'] as String,
    title: (j['title'] ?? '') as String,
    snippet: (j['snippet'] ?? '') as String,
    postedAt: j['posted_at'] as String?,
    sentiment: (j['sentiment'] as num?)?.toDouble() ?? 0,
    credibility: (j['credibility'] as num?)?.toDouble() ?? 0,
    branchBasis: j['branch_basis'] as String?,
  );

  /// 지점이 특정되지 않은 글인가.
  bool get isBrandWide => branchBasis == 'brand';

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
  final List<String> gradeBands;
  final List<String> stages;

  /// 단계마다 **왜** 붙었는지. `curated`(사람이 적은 큐레이션) ·
  /// `hinted`(이름·교습과정·과정명에 단서) · `inferred`(과목·구간만 보고 추정).
  ///
  /// 예전에는 셋이 구분 없이 한 목록이었다. 화면은 추정을 큐레이션과
  /// 똑같이 보여줬고, 근거 없는 배정이 '이 학원은 영재고 대비'로 읽혔다.
  final Map<String, String> stageBasis;
  final List<String> flagship;
  final String? address;
  final String? tel;
  final int? capacity;
  final String? registrationStatus;
  final String? establishedOn;
  final bool isVerified;
  final String dataSource;
  final double? lat;
  final double? lng;

  /// NEIS 등록 건수. 1보다 크면 여러 관/과정 등록을 하나로 묶은 것이다.
  final int registrationCount;

  /// 통합으로 흡수된 옛 등록번호들. 옛 id 로 저장된 링크·참조를
  /// 현재 학원으로 잇는 데 쓴다 — 통합이 참조를 끊으면 안 된다.
  final List<String> registrationIds;

  final Score score;

  /// 과목별 점수. 한 학원이 여러 과목을 가르쳐도 **근거는 과목마다
  /// 다르다** — 수학 후기 496건짜리 종합학원이 그 점수를 그대로 들고
  /// 과학 랭킹에 오르면 그 순위는 '과학이 좋다'가 아니라 '유명하다'를
  /// 뜻하게 된다. 과목 랭킹은 반드시 이 값을 본다.
  final Map<String, Score> subjectScores;
  final List<Evidence> evidence;

  /// 학부모가 실제로 묻는 것 — 숙제량·시험 횟수·수업 시간.
  ///
  /// 점수가 아니라 **사실**이라 트리스코어에 들어가지 않는다. 숙제가 많은
  /// 것은 좋은 것도 나쁜 것도 아니고, 순위로 바꾸는 순간 그 값이 무엇을
  /// 뜻하는지 설명할 수 없다. 모든 줄이 인용문과 원문 링크를 갖는다.
  final Map<String, FactCard> facts;

  /// 진입난이도의 근거 인용문. 줄마다 claimId 가 있어 '이의'를 받는다.
  /// 취소된 줄도 들어 있다 — 왜 빠졌는지가 보여야 한다.
  final List<ClaimEvidence> selectivityEvidence;

  /// 이 학원 근거 중 이의로 빠진 비율. **숨기면 그 자체가 왜곡이다.**
  final DisputeRate? disputeRate;

  const Academy({
    required this.id,
    required this.name,
    required this.displayNameRaw,
    this.brand,
    required this.aliases,
    required this.regionId,
    required this.subjects,
    required this.gradeBands,
    required this.stages,
    this.stageBasis = const {},
    required this.flagship,
    this.address,
    this.tel,
    this.capacity,
    this.registrationStatus,
    this.establishedOn,
    required this.isVerified,
    required this.dataSource,
    this.lat,
    this.lng,
    this.registrationCount = 1,
    this.registrationIds = const [],
    required this.score,
    this.subjectScores = const {},
    required this.evidence,
    this.facts = const {},
    this.selectivityEvidence = const [],
    this.disputeRate,
  });

  factory Academy.fromJson(Map<String, dynamic> j) => Academy(
    id: j['id'] as String,
    name: j['name'] as String,
    displayNameRaw: (j['displayName'] ?? j['name']) as String,
    brand: j['brand'] as String?,
    aliases: ((j['aliases'] as List?) ?? const []).cast<String>(),
    regionId: (j['regionId'] ?? '') as String,
    subjects: ((j['subjects'] as List?) ?? const []).cast<String>(),
    gradeBands: ((j['gradeBands'] as List?) ?? const []).cast<String>(),
    stages: ((j['stages'] as List?) ?? const []).cast<String>(),
    stageBasis: ((j['stageBasis'] as Map?) ?? const {}).map(
      (k, v) => MapEntry(k as String, v as String),
    ),
    flagship: ((j['flagship'] as List?) ?? const []).cast<String>(),
    address: j['address'] as String?,
    tel: j['tel'] as String?,
    capacity: (j['capacity'] as num?)?.toInt(),
    registrationStatus: j['registrationStatus'] as String?,
    establishedOn: j['establishedOn'] as String?,
    isVerified: (j['isVerified'] ?? false) as bool,
    dataSource: (j['dataSource'] ?? 'seed') as String,
    lat: (j['lat'] as num?)?.toDouble(),
    lng: (j['lng'] as num?)?.toDouble(),
    registrationCount: (j['registrationCount'] as num?)?.toInt() ?? 1,
    registrationIds: ((j['registrationIds'] as List?) ?? const [])
        .cast<String>(),
    score: Score.fromJson((j['score'] as Map).cast<String, dynamic>()),
    subjectScores: {
      for (final e in ((j['subjectScores'] as Map?) ?? const {}).entries)
        e.key as String: Score.fromJson(
          (e.value as Map).cast<String, dynamic>(),
        ),
    },
    evidence: ((j['evidence'] as List?) ?? const [])
        .map((e) => Evidence.fromJson((e as Map).cast<String, dynamic>()))
        .toList(),
    facts: {
      for (final e in ((j['facts'] as Map?) ?? const {}).entries)
        e.key as String: FactCard.fromJson(
          (e.value as Map).cast<String, dynamic>(),
        ),
    },
    selectivityEvidence: ((j['selectivityEvidence'] as List?) ?? const [])
        .map((e) => ClaimEvidence.fromJson((e as Map).cast<String, dynamic>()))
        .toList(),
    disputeRate: j['disputeRate'] == null
        ? null
        : DisputeRate.fromJson(
            (j['disputeRate'] as Map).cast<String, dynamic>(),
          ),
  );

  /// 큐레이션 브랜드명(brand)을 표시에 쓰지 않는다. 브랜드는 지점을
  /// 구분하지 못해서, 서로 다른 CMS 지점 두 곳이 같은 이름으로 나왔다.
  String get displayName => displayNameRaw;

  /// 브랜드가 실제 학원명과 다를 때만 의미가 있다 (예: 씨엠에스학원 → CMS영재교육)
  String? get brandLabel =>
      (brand != null && brand != name && !name.contains(brand!)) ? brand : null;
  bool isFlagshipOf(String stageId) => flagship.contains(stageId);

  /// 이 단계에 붙은 근거. 모르면 'inferred' 로 본다 — 근거를 모르는 것은
  /// 근거가 약한 것이지, 강한 것일 수 없다.
  String stageBasisOf(String stageId) =>
      stages.contains(stageId) ? (stageBasis[stageId] ?? 'inferred') : 'band';

  /// 그 과목의 점수. 과목을 안 주면 대표 점수.
  /// 과목별 점수가 없는 곳(옛 데이터·종합학원)은 대표 점수로 물러난다.
  Score scoreFor(String? subject) =>
      subject == null ? score : (subjectScores[subject] ?? score);
}

/// 한 단계에 걸린 학원 하나 — **어떤 근거로 걸렸는지와 함께.**
///
/// 학원만 넘기면 화면이 그 차이를 말할 수 없다. 큐레이션 매핑과
/// '같은 구간이라 이어 붙인 곳'이 한 목록에 섞여 나오면, 목록은 길어지지만
/// 무엇을 믿어야 하는지는 알 수 없게 된다.
class StageMatch {
  final Academy academy;

  /// curated  사람이 적은 큐레이션 매핑
  /// hinted   학원명·교습과정·과정명에 이 단계의 단서가 있음
  /// inferred 단서가 없어 과목·학년 구간의 대표 단계로 추정
  /// band     이 단계 근거는 없고, 같은 과목·구간이라 이어 붙인 곳
  final String basis;

  const StageMatch(this.academy, this.basis);

  static int rank(String basis) => switch (basis) {
    'curated' => 0,
    'hinted' => 1,
    'inferred' => 2,
    _ => 3,
  };

  bool get isDirect => basis != 'band';

  String? get label => labelFor(basis);

  /// 화면에 적는 말. **추정을 확정처럼 적지 않는다.**
  /// 큐레이션은 굳이 적지 않는다 — 기본값이고, 매번 적으면 읽히지 않는다.
  static String? labelFor(String? basis) => switch (basis) {
    'hinted' => '교습과정에 단서',
    'inferred' => '과목·학년으로 추정',
    'band' => '이 단계 근거 없음 · 같은 구간',
    _ => null,
  };
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
    weights: ((j['weights'] as Map?) ?? const {}).map(
      (k, v) => MapEntry(k as String, (v as num).toDouble()),
    ),
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
    registrationStatus: j['registrationStatus'] as String?,
    isVerified: (j['isVerified'] ?? false) as bool,
  );
}

/// 학교. 학군지도의 주인공이다 — 어느 학교에 배정되느냐가 곧 학군이다.
class School {
  final String id;
  final String name;
  final String level; // elementary | middle | high
  final String levelLabel; // 초등학교 | 중학교 | 고등학교
  final String regionId;
  final String? dong;
  final String? foundation; // 공립 | 사립
  final String? coed; // 남여공학 | 남 | 여
  final String? highKind; // 일반고 | 특목고 …
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

  /// 이 학교로 배정되는 아파트들 (아파트→학교의 역방향)
  final List<ZonedApartment> apartments;

  /// 배정 아파트 세대수 합계. 공시 학생수와 달리 '앞으로 들어올 수요'를 보여준다.
  final int? apartmentHouseholds;

  /// 졸업생 진로 공시(학교알리미). {'year','일반고','특수목적고','자율고','진학률'…}
  /// 항목은 학교급에 따라 다르다. 없으면 아직 수집 전이다.
  final Map<String, dynamic>? careers;

  /// 공시 밖 수기 보완(서울대 진학자 등). 반드시 source 가 함께 있다 —
  /// 출처 없는 값은 파이프라인이 받지 않는다.
  final Map<String, dynamic>? outcomesExtra;

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
    this.apartments = const [],
    this.apartmentHouseholds,
    this.careers,
    this.outcomesExtra,
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
    apartments: ((j['apartments'] as List?) ?? const [])
        .map((a) => ZonedApartment.fromJson((a as Map).cast<String, dynamic>()))
        .toList(),
    apartmentHouseholds: (j['apartmentHouseholds'] as num?)?.toInt(),
    careers: (j['careers'] as Map?)?.cast<String, dynamic>(),
    outcomesExtra: (j['outcomesExtra'] as Map?)?.cast<String, dynamic>(),
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

/// 학교 쪽에서 본 배정 아파트
class ZonedApartment {
  final String name;
  final String? dong;
  final int? households;
  final bool certain;

  const ZonedApartment({
    required this.name,
    this.dong,
    this.households,
    this.certain = false,
  });

  factory ZonedApartment.fromJson(Map<String, dynamic> j) => ZonedApartment(
    name: (j['name'] ?? '') as String,
    dong: j['dong'] as String?,
    households: (j['households'] as num?)?.toInt(),
    certain: (j['certain'] ?? false) as bool,
  );
}

class ApartmentZone {
  final String? zoneId;
  final String? zoneName;
  final String? level;
  final List<String> schools;

  /// 초등 통학구역이면서 학교가 하나일 때만 true — '배정'이라 단정할 수 있다.
  final bool certain;

  /// 중·고 학교군 안에서 집과 가까운 순. 추첨이지만 통학 편의가
  /// 반영되므로 가까운 학교로 갈 확률이 높다. 확률로 환산하지는 않는다 —
  /// 실제 배정 결과 자료가 없는 상태에서 퍼센트를 붙이면 근거 없는 숫자다.
  final List<NearbySchool> nearby;

  const ApartmentZone({
    this.zoneId,
    this.zoneName,
    this.level,
    this.schools = const [],
    this.certain = false,
    this.nearby = const [],
  });

  factory ApartmentZone.fromJson(Map<String, dynamic> j) => ApartmentZone(
    zoneId: j['zoneId'] as String?,
    zoneName: j['zoneName'] as String?,
    level: j['level'] as String?,
    schools: ((j['schools'] as List?) ?? const []).cast<String>(),
    certain: (j['certain'] ?? false) as bool,
    nearby: ((j['nearby'] as List?) ?? const [])
        .map((e) => NearbySchool.fromJson((e as Map).cast<String, dynamic>()))
        .toList(),
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

/// 학교군 안에서 집과 가까운 학교 하나.
class NearbySchool {
  final String name;
  final double km;

  /// '남' · '여' · '남여공학'. 남고·여고를 밝히지 않으면 목록이 거짓이 된다 —
  /// 아들만 있는 집에 '1순위 여고'라고 적어 놓는 셈이다.
  final String? coed;
  const NearbySchool({required this.name, required this.km, this.coed});

  factory NearbySchool.fromJson(Map<String, dynamic> j) => NearbySchool(
    name: (j['name'] ?? '') as String,
    km: (j['km'] as num?)?.toDouble() ?? 0,
    coed: j['coed'] as String?,
  );

  /// 공학이 아닐 때만 붙인다. 대부분이 공학이라 매번 적으면 읽히지 않는다.
  String get coedTag => switch (coed) {
    '남' => ' (남)',
    '여' => ' (여)',
    _ => '',
  };

  /// 1km 미만은 m 로 보여준다. '0.4km' 보다 '400m' 가 걷는 거리로 읽힌다.
  String get distanceLabel =>
      km < 1 ? '${(km * 1000).round()}m' : '${km.toStringAsFixed(1)}km';
}

/// 통합 로드맵 — 과목·구간으로 가르지 않은 전체 그림.
///
/// 5세 영어 → 6세 수학 → 7세 국어 → 초4 재편으로 이어지는 흐름은
/// 과목을 나란히 놓아야 보인다. 유아 단계(roadmapOnly)는 방향 안내일
/// 뿐 랭킹과 연결되지 않는다.
/// 되돌리기 어려운 분기점. "언제 갈리는가" 가 학부모의 실제 질문이다.
class DestinationGate {
  final int grade;
  final String note;
  const DestinationGate({required this.grade, required this.note});

  factory DestinationGate.fromJson(Map<String, dynamic> j) => DestinationGate(
        grade: (j['grade'] as num).toInt(),
        note: (j['note'] ?? '') as String,
      );
}

/// 진로 목적지 — 테크트리의 종점.
///
/// 단계가 '무엇을 배우는가' 라면 목적지는 '어디로 가는가' 다.
/// **큐레이션이다** — 후기에서 추론하지 않는다. 목적지 신호는 글 2.3%
/// 뿐이라 학원에 딱지를 붙일 수는 없지만, '의대는 과탐II를 지난다' 는
/// 이미 아는 사실이라 사람이 적는다.
class Destination {
  final String id;
  final String label;

  /// 국내입시 · 해외 · 특목 · 기타
  final String axis;
  final String? summary;

  /// 과목 → 지나야 하는 단계 id
  final Map<String, List<String>> requires;
  final List<DestinationGate> gates;

  /// false 면 학원을 잇지 않는다. 근거가 얇은 목적지(조기졸업·예체능)는
  /// 길만 보여 주고 누가 그 길인지는 말하지 않는다.
  final bool linkable;

  /// 단계 id → 그 단계에 붙은 학원 수. 길의 어느 대목이 비었는지 보인다.
  ///
  /// **전국 합계다 — 화면에 그대로 쓰지 말 것.** 판은 늘 학군 하나를
  /// 보고 있어서, 이 값을 적으면 학군을 바꿔도 숫자가 안 움직인다.
  /// 그러면 그 숫자가 무엇을 세었는지 알 수 없고, 바로 아래 목록의
  /// 길이와도 어긋난다. 화면은 `EduTreeData.legFor` 로 다시 센다.
  /// 이 값은 빌드 진단용이다(학군 '전체'일 때 같은 수가 나온다).
  final Map<String, int> stageCounts;

  /// 이 길에 놓인 학원 수(중복 제거). 이것도 전국 합계다 —
  /// 화면은 `EduTreeData.destinationAcademyCount` 를 쓴다.
  final int academyCount;

  const Destination({
    required this.id,
    required this.label,
    required this.axis,
    this.summary,
    this.requires = const {},
    this.gates = const [],
    this.linkable = true,
    this.stageCounts = const {},
    this.academyCount = 0,
  });

  /// 이 목적지가 지나는 모든 단계.
  Set<String> get stageIds =>
      {for (final ids in requires.values) ...ids};

  /// 이 길이 지나는 과목 — 표준 순서로.
  ///
  /// `requires` 의 키 순서를 그대로 쓰지 않는다. 그건 사람이 yaml 에 적은
  /// 차례라 목적지마다 다르고, 그러면 판의 열이 행마다 흔들린다.
  List<String> get subjects =>
      orderedSubjects(requires.keys.where((s) => (requires[s] ?? const []).isNotEmpty));

  /// 가장 이른 관문의 학년. 없으면 null.
  /// '언제 갈리는가' 가 학부모의 실제 질문이라 판의 한 칸을 이것에 준다.
  int? get firstGateGrade =>
      gates.isEmpty ? null : gates.map((g) => g.grade).reduce((a, b) => a < b ? a : b);

  factory Destination.fromJson(Map<String, dynamic> j) => Destination(
        id: j['id'] as String,
        label: j['label'] as String,
        axis: (j['axis'] ?? '기타') as String,
        summary: j['summary'] as String?,
        requires: ((j['requires'] as Map?) ?? const {}).map((k, v) =>
            MapEntry(k as String, (v as List).cast<String>())),
        gates: ((j['gates'] as List?) ?? const [])
            .map((e) =>
                DestinationGate.fromJson((e as Map).cast<String, dynamic>()))
            .toList(),
        linkable: (j['linkable'] ?? true) as bool,
        stageCounts: ((j['stageCounts'] as Map?) ?? const {})
            .map((k, v) => MapEntry(k as String, (v as num).toInt())),
        academyCount: (j['academyCount'] as num?)?.toInt() ?? 0,
      );
}

/// 목적지 × 과목 한 칸 — 목적성 판의 최소 단위.
///
/// **목적지 하나에 학원을 한 줄로 세우지 않는다.** 의대의 수학 학원과
/// 과학 학원을 한 줄에 세우면 그 순위가 무엇을 뜻하는지 설명할 수 없다 —
/// 예체능을 학술과 한 줄에 세우지 않는 것과 같은 이유다. 그래서 목적지의
/// 최소 단위는 목적지가 아니라 (목적지 × 과목)이다. 학부모의 질문도
/// 실은 이 단위다: '의대를 보려면 **수학은** 어디까지인가'.
class DestinationLeg {
  final String destId;
  final String subject;

  /// 나이 순으로 세운 단계. 길은 시간 순으로 읽힌다.
  final List<Stage> stages;

  /// 단계 id → 그 단계에 근거가 있는 학원 수 (선택 학군 기준).
  final Map<String, int> counts;

  /// 이 칸에 놓인 학원 수(중복 제거). 단계 수의 합이 아니다 —
  /// 한 학원이 여러 단계를 담당한다.
  final int academyCount;

  /// false 면 학원을 잇지 않기로 한 길이다(조기졸업·예체능).
  /// **'안 이었다'와 '이었는데 비었다'는 다른 상태다.**
  final bool linkable;

  const DestinationLeg({
    required this.destId,
    required this.subject,
    required this.stages,
    this.counts = const {},
    this.academyCount = 0,
    this.linkable = true,
  });

  /// 이 목적지가 이 과목을 아예 지나지 않는다.
  bool get isOffPath => stages.isEmpty;

  /// 지나기는 하는데 학원이 하나도 없다. 큐레이션한 길의 빈 대목이다.
  bool get isEmpty => !isOffPath && linkable && academyCount == 0;

  int countOf(String stageId) => counts[stageId] ?? 0;

  /// 요구는 하는데 학원이 하나도 없는 단계.
  /// 숨기면 채워진 길처럼 읽힌다 — 어디가 비었는지가 이 판의 정보다.
  List<Stage> get emptyStages =>
      [for (final s in stages) if (countOf(s.id) == 0) s];
}

class Roadmap {
  final List<RoadmapMilestone> milestones;
  final List<RoadmapStage> stages;
  final List<StageEdge> edges;

  const Roadmap({
    this.milestones = const [],
    this.stages = const [],
    this.edges = const [],
  });

  bool get isEmpty => stages.isEmpty;

  factory Roadmap.fromJson(Map<String, dynamic> j) => Roadmap(
    milestones: ((j['milestones'] as List?) ?? const [])
        .map(
          (e) => RoadmapMilestone.fromJson((e as Map).cast<String, dynamic>()),
        )
        .toList(),
    stages: ((j['stages'] as List?) ?? const [])
        .map((e) => RoadmapStage.fromJson((e as Map).cast<String, dynamic>()))
        .toList(),
    edges: ((j['edges'] as List?) ?? const [])
        .map((e) => StageEdge.fromList(e as List<dynamic>))
        .toList(),
  );
}

class RoadmapMilestone {
  final int grade;
  final String label;
  final String note;
  const RoadmapMilestone({
    required this.grade,
    required this.label,
    required this.note,
  });

  factory RoadmapMilestone.fromJson(Map<String, dynamic> j) => RoadmapMilestone(
    grade: (j['grade'] as num).toInt(),
    label: (j['label'] ?? '') as String,
    note: (j['note'] ?? '') as String,
  );
}

class RoadmapStage {
  final String id;
  final String subject;
  final String title;
  final String? subtitle;
  final int gradeMin;
  final int gradeMax;
  final int lane;
  final bool roadmapOnly;

  const RoadmapStage({
    required this.id,
    required this.subject,
    required this.title,
    this.subtitle,
    required this.gradeMin,
    required this.gradeMax,
    this.lane = 0,
    this.roadmapOnly = false,
  });

  factory RoadmapStage.fromJson(Map<String, dynamic> j) {
    final g = (j['grade'] as List?) ?? const [1, 12];
    return RoadmapStage(
      id: j['id'] as String,
      subject: (j['subject'] ?? 'etc') as String,
      title: (j['title'] ?? '') as String,
      subtitle: j['subtitle'] as String?,
      gradeMin: (g[0] as num).toInt(),
      gradeMax: (g[1] as num).toInt(),
      lane: (j['lane'] as num?)?.toInt() ?? 0,
      roadmapOnly: j['roadmap_only'] == true,
    );
  }

  String get gradeLabel => gradeMin == gradeMax
      ? Stage.gradeName(gradeMin)
      : '${Stage.gradeName(gradeMin)}~${Stage.gradeName(gradeMax)}';
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
  // 예체능·기타는 만족도와 화제성만으로 순위를 낸다.
  // 진학 경로가 없고 공시로 확인할 것도 적기 때문이다.
  'arts': '예체능',
  'etc': '기타',
};

/// 과목을 늘어놓는 **단 하나의 순서.**
///
/// 화면마다 제각각이었다 — 랭킹은 수학부터, 로드맵은 `['english', 'math',
/// 'korean', 'science']` 를 코드에 박아 영어부터였다. 같은 네 과목이 화면을
/// 옮길 때마다 자리를 바꾸면 손이 기억할 수가 없다.
///
/// 순서의 근거는 **채점 대상의 과목 수**다(실측 2026-08-28, 400곳):
///
///     수학 111 · 영어 88 · 국어 74 · 과학 48 ‖ 예체능 59 · 기타 39
///
/// 수는 야간 수집마다 흔들리므로 날짜를 적어 둔다. **중요한 것은 값이
/// 아니라 차례다** — 수집 회차가 바뀌어도 이 차례는 유지됐다. 뒤집히면
/// 그때 순서를 다시 정하되, 손이 기억한 자리를 바꾸는 값이라 한두 건
/// 차이로는 움직이지 않는다.
///
/// 학술 넷을 앞에, 예체능·기타를 뒤에 둔다. 뒤 둘은 산식이 아예 다르다
/// (평판 60% + 화제성 40%, `NON_ACADEMIC_WEIGHTS`) — 같은 줄에 나란히
/// 두되 사이를 계선으로 끊는 이유가 그것이다.
///
/// 로드맵의 옛 순서(영어부터)는 **시작 나이 순**이라 나름의 뜻이 있었지만,
/// 로드맵은 세로축이 이미 나이다. 가로 순서까지 나이를 말하면 같은 것을
/// 두 번 말하면서 다른 화면과는 어긋난다.
const subjectOrder = <String>[
  'math',
  'english',
  'korean',
  'science',
  'arts',
  'etc',
];

/// 네 기둥을 다 적용하는 과목. 나머지는 평판·화제성만 본다.
const academicSubjects = <String>{'math', 'english', 'korean', 'science'};

bool isAcademicSubject(String? s) => academicSubjects.contains(s);

/// 아무 데서나 온 과목 목록을 **표준 순서로** 세운다.
///
/// 표시 이름이 없는 키는 버린다 — `general` 은 '어느 과목인지 모른다'는
/// 뜻이라 늘어놓을 자리가 없다. 목록에 없는 낯선 키는 뒤에 붙여 둔다:
/// 파이프라인이 새 과목을 내보내기 시작해도 화면에서 조용히 사라지지는
/// 않아야 한다.
List<String> orderedSubjects(Iterable<String> keys) {
  final seen = keys.where(subjectNames.containsKey).toSet();
  return [
    for (final s in subjectOrder)
      if (seen.remove(s)) s,
    ...seen,
  ];
}

/// 학원이 받는 학년대. 학교(초등학교·중학교·고등학교)와는 다른 축이다.
/// 학교는 건물이고, 이건 '몇 학년을 받는 학원인가'다.
const gradeBandNames = <String, String>{
  'elem_low': '예비초~초3',
  'elem_high': '초4~초6',
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
