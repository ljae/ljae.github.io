import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'core/brand.dart';
import 'core/env.dart';
import 'core/router.dart';
import 'core/theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Supabase 키가 없으면 초기화하지 않는다. 후기·로그인 기능만 꺼지고
  // 테크트리·랭킹은 정적 번들만으로 그대로 동작한다.
  if (Env.hasSupabase) {
    await Supabase.initialize(
      url: Env.supabaseUrl,
      // Supabase 가 anon key → publishable key 로 이름을 바꿨다.
      // 값의 성격은 같다: 공개돼도 되는 키이고 RLS 가 보호한다.
      publishableKey: Env.supabaseAnonKey,
      // PKCE 를 쓴다. 기본값(implicit)은 토큰을 URL 해시에 담아 보내는데,
      // 이 앱은 해시 라우팅(/#/admin)을 쓰므로 두 해시가 충돌해
      // 'otp_expired' 처럼 보이는 실패가 난다. PKCE 는 ?code= 쿼리로
      // 오기 때문에 라우팅과 부딪히지 않는다.
      authOptions: const FlutterAuthClientOptions(
        authFlowType: AuthFlowType.pkce,
      ),
    );
  }
  runApp(const ProviderScope(child: EduTreeApp()));
}

class EduTreeApp extends StatelessWidget {
  const EduTreeApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: '${Brand.name} — ${Brand.tagline}',
      debugShowCheckedModeBanner: false,
      theme: buildTheme(dark: false),
      darkTheme: buildTheme(dark: true),
      themeMode: ThemeMode.system,
      routerConfig: router,
    );
  }
}
