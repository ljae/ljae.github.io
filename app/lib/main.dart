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
