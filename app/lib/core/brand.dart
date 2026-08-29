/// 브랜드 상수 — 이름을 바꿀 때 손댈 곳은 여기 하나뿐이다.
class Brand {
  static const name = '학원실록';
  static const nameEn = 'Hakwon Silok';
  static const tagline = '대치 · 목동 · 반포 · 잠실 학원 테크트리';
  static const description = '공공데이터로 검증하고 커뮤니티 신호로 읽는 학원 기록';

  /// 이름의 유래를 화면에서 한 번은 설명해 준다.
  static const nameOrigin =
      '조선왕조실록이 사실을 있는 그대로 남겼듯, 학원 정보를 검증된 기록으로 남깁니다.';
  static const operator = 'Open Edu';
  static const operatorUrl = '/openedu/';
  static const domain = 'openedu4u.com';
}

/// 앞말에 조사를 붙인다 — `josa(Brand.name, '은는')` → `학원실록은`.
///
/// 조사는 앞말의 **받침**으로 갈린다. 이름을 상수 하나로 두기로 한 이상
/// 조사도 이름에서 파생시켜야 한다. 손으로 적으면 이름을 바꿔도 조사가
/// 따라오지 않고, 실제로 그래서 **'학원실록는'** 이 두 화면에 나가 있었다
/// (‘록’에 받침 ㄱ 이 있으니 ‘은’이 맞다).
///
/// [pair] 는 **받침 있을 때 · 없을 때** 순서의 두 글자다:
/// `'은는'` · `'이가'` · `'을를'` · `'과와'`.
///
/// **한글 음절로 끝날 때만 판정한다.** 영문·숫자로 끝나는 말의 조사는 글자가
/// 아니라 소리로 정해져서(‘Open Edu는’·‘3은’·‘7은’) 코드가 알 수 없다 —
/// 그럴 때는 받침 없는 쪽을 주되, 어차피 맞지 않을 수 있으니 그런 말에는
/// 쓰지 말고 문장을 손으로 적을 것.
///
/// `(으)로` 는 받침 ㄹ 이 예외라서(‘서울로’·‘대치로’) 두 글자 짝으로는 못
/// 담는다. 필요해지면 여기에 따로 만들 것 — 이 함수로 흉내 내지 말 것.
String josa(String word, String pair) {
  // 조사 짝은 전부 한글 음절 두 개라 UTF-16 한 칸씩 차지한다.
  // 그래서 `characters` 패키지를 들이지 않고 인덱스로 충분하다 —
  // 이 파일은 상수만 두기로 해서 import 가 하나도 없다.
  assert(pair.length == 2, "조사 짝은 '은는' 처럼 두 글자다");
  return word + (_hasBatchim(word) ? pair[0] : pair[1]);
}

/// 마지막 글자에 받침이 있는가. 한글 음절이 아니면 `false`.
///
/// 한글 음절은 유니코드에서 `초성·중성·종성`이 한 칸으로 합쳐져 있어,
/// 시작점(0xAC00)에서의 거리를 28(종성 가짓수)로 나눈 나머지가 곧 받침이다.
/// 나머지가 0 이면 받침이 없다.
bool _hasBatchim(String word) {
  if (word.isEmpty) return false;
  final code = word.runes.last;
  if (code < 0xAC00 || code > 0xD7A3) return false;
  return (code - 0xAC00) % 28 != 0;
}
