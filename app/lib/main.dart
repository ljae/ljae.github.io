import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'core/brand.dart';
import 'core/env.dart';
import 'core/router.dart';
import 'core/reduced_motion.dart';
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
      // '동작 줄이기'를 **한 곳에서** 확정한다. 웹에서는 Flutter 가
      // 브라우저의 prefers-reduced-motion 을 안 넘겨줘서, 연출을 끄는 길이
      // 정작 이 서비스가 도는 곳에서만 막혀 있었다. 여기서 얹어 두면
      // 아래의 모든 연출(Reveal·Scrub·Tally·StrokeIn)이 그대로 따른다 —
      // 위젯마다 다시 물어보게 두면 언젠가 한 곳을 빠뜨린다.
      builder: (context, child) {
        final mq = MediaQuery.of(context);
        if (mq.disableAnimations || !platformPrefersReducedMotion()) {
          return child ?? const SizedBox.shrink();
        }
        return MediaQuery(
          data: mq.copyWith(disableAnimations: true),
          child: child ?? const SizedBox.shrink(),
        );
      },
    );
  }
}
