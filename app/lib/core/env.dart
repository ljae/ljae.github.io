/// 빌드 시점에 주입되는 설정.
///
/// 키는 성격이 둘로 갈린다. 섞으면 사고가 난다.
///
///   서버 전용 (절대 앱에 넣지 않는다) — .env 에만 둔다
///     NEIS_API_KEY, NAVER_CLIENT_SECRET, SUPABASE_SERVICE_KEY,
///     NAVER_MAP_CLIENT_SECRET(지오코딩용)
///
///   클라이언트 공개 (앱 번들에 들어가고, 브라우저에서 보인다)
///     NAVER_MAP_KEY_ID  — 콘솔의 도메인 허용목록으로 보호한다
///     SUPABASE_ANON_KEY — RLS 로 보호한다
///
/// 공개 키를 '숨기는' 것은 불가능하다. 콘솔에서 도메인을 제한하고 RLS 를
/// 걸어 두는 것이 유일한 보호다. 저장소에 커밋하지 않는 이유는 유출 방지가
/// 아니라, 키를 바꿀 때 코드를 고치지 않기 위해서다.
///
/// 주입:
///   flutter run -d chrome --dart-define=SUPABASE_URL=... --dart-define=...
///   (배포는 .github/workflows/deploy.yml 이 시크릿에서 넣는다)
class Env {
  static const supabaseUrl = String.fromEnvironment('SUPABASE_URL');
  static const supabaseAnonKey = String.fromEnvironment('SUPABASE_ANON_KEY');

  /// 지도 JS SDK 용. index.html 에도 같은 값이 주입된다.
  static const naverMapKeyId = String.fromEnvironment('NAVER_MAP_KEY_ID');

  static bool get hasSupabase =>
      supabaseUrl.isNotEmpty && supabaseAnonKey.isNotEmpty;
  static bool get hasNaverMap => naverMapKeyId.isNotEmpty;
}
