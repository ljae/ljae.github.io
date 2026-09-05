import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/theme.dart';
import '../data/models.dart';
import '../data/reservations.dart';
import 'annals.dart';

/// 외부 링크. http(s) 만 연다 — 데이터에 든 주소를 그대로 믿지 않는다.
Future<void> openExternal(String url) async {
  final uri = Uri.tryParse(url);
  if (uri == null || !(uri.scheme == 'http' || uri.scheme == 'https')) return;
  await launchUrl(uri, mode: LaunchMode.externalApplication);
}

/// 전화번호에서 숫자만. '02-552-6003' → '025526003'.
String telDigits(String tel) => tel.replaceAll(RegExp(r'[^0-9+]'), '');

/// 전화를 건다. 못 거는 기기(데스크톱 브라우저)에서는 번호를 복사하고
/// 그렇게 말한다 — 아무 일도 안 일어나는 버튼이 가장 나쁘다.
///
/// 누른 사실만 기록한다(누가인지는 없다). 학부모가 전화를 거는 학원은
/// 우리가 근거를 더 찾아야 할 학원이다 — 다음 회차 수집 우선순위에 쓴다.
Future<void> callAcademy(
  BuildContext context,
  WidgetRef ref,
  Academy academy,
) async {
  final tel = academy.tel;
  if (tel == null || tel.isEmpty) return;
  unawaited(ref.read(actionLogProvider).log(academy.id, 'call'));
  final messenger = ScaffoldMessenger.maybeOf(context);
  var ok = false;
  try {
    ok = await launchUrl(
      Uri(scheme: 'tel', path: telDigits(tel)),
      webOnlyWindowName: '_self',
    );
  } catch (_) {
    ok = false;
  }
  if (!ok) {
    await Clipboard.setData(ClipboardData(text: tel));
    messenger?.showSnackBar(
      SnackBar(content: Text('이 기기에서는 전화를 걸 수 없어 번호를 복사했습니다: $tel')),
    );
  }
}

/// 학원 공식 페이지로 보낸다. **레벨테스트 신청도 여기서 한다** —
/// 학원실록이 대신 접수하지 않는다(2026-09-05).
///
/// 링크가 없으면 호출되지 않는다. 화면이 버튼을 만들지 않기 때문이다.
Future<void> openHomepage(
  BuildContext context,
  WidgetRef ref,
  Academy academy,
) async {
  final url = academy.homepage;
  if (url == null || url.isEmpty) return;
  unawaited(ref.read(actionLogProvider).log(academy.id, 'homepage'));
  final messenger = ScaffoldMessenger.maybeOf(context);
  var ok = false;
  try {
    ok = await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
  } catch (_) {
    ok = false;
  }
  if (!ok) {
    await Clipboard.setData(ClipboardData(text: url));
    messenger?.showSnackBar(
      SnackBar(content: Text('페이지를 열 수 없어 주소를 복사했습니다: $url')),
    );
  }
}

Future<void> copyTel(
  BuildContext context,
  WidgetRef ref,
  Academy academy,
) async {
  final tel = academy.tel;
  if (tel == null) return;
  unawaited(ref.read(actionLogProvider).log(academy.id, 'copy_tel'));
  // 비동기 뒤에 context 를 쓰지 않는다 — 먼저 집어 둔다.
  final messenger = ScaffoldMessenger.maybeOf(context);
  await Clipboard.setData(ClipboardData(text: tel));
  messenger?.showSnackBar(SnackBar(content: Text('전화번호를 복사했습니다: $tel')));
}

/// 랭킹 카드의 '전화' 꼬리표. 상세로 들어가지 않고 바로 건다.
class CallTag extends ConsumerWidget {
  final Academy academy;
  const CallTag({super.key, required this.academy});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (academy.tel == null) return const SizedBox.shrink();
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Tooltip(
      message: '전화 ${academy.tel}',
      child: InkWell(
        onTap: () => callAcademy(context, ref, academy),
        child: TagMark(
          '전화',
          color: AppColors.accentOn(dark),
          icon: Icons.call_outlined,
        ),
      ),
    );
  }
}

/// 출처 번호. [3] 처럼 각진 칸에 장부 숫자로 찍는다.
class RefMark extends StatelessWidget {
  final int n;
  final bool small;
  const RefMark(this.n, {super.key, this.small = false});

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: small ? 4 : 6,
        vertical: small ? 1 : 3,
      ),
      decoration: BoxDecoration(
        border: Border.all(color: AppColors.ruleOn(dark), width: AppRule.hair),
        borderRadius: BorderRadius.circular(AppRadius.sm),
      ),
      child: Text(
        '$n',
        style: TextStyle(
          fontFamily: 'Paperlogy',
          fontSize: small ? 10.5 : 12,
          fontWeight: FontWeight.w700,
          height: 1.1,
          color: AppColors.inkOn(dark),
          fontFeatures: ledgerFigures,
        ),
      ),
    );
  }
}

/// 발췌에서 굵게 찍을 이름들. 등록명·브랜드·별칭과 업종어를 뗀 알맹이.
///
/// 두 글자 별칭(정상·시대)은 뺀다 — 발췌 안의 '정상' 을 전부 굵게 찍으면
/// 그게 곧 오독이다. 파이프라인이 두 글자 이름을 표지 곁에서만 인정하는
/// 것과 같은 이유이고, 화면에서는 굳이 위험을 무릅쓸 이유가 없다.
List<String> nameTerms(Academy a) {
  final out = <String>{};
  final trade = RegExp(r'(학원|교습소|어학원|아카데미|에듀|스쿨|캠퍼스|센터|연구소)+$');
  final region = RegExp(r'^(대치|목동|반포|잠실|서울|송파|서초|양천|강남)\s*');
  void add(String? s) {
    if (s == null) return;
    final t = s.trim();
    if (t.length < 3) return;
    out.add(t);
    final core = t.replaceFirst(trade, '');
    if (core.length >= 3) out.add(core);
    final stripped = t.replaceFirst(region, '');
    if (stripped != t && stripped.length >= 3) {
      out.add(stripped);
      final c2 = stripped.replaceFirst(trade, '');
      if (c2.length >= 3) out.add(c2);
    }
  }

  add(a.name);
  add(a.brand);
  for (final x in a.aliases) {
    add(x);
  }
  return out.toList()..sort((x, y) => y.length - x.length);
}

/// 본문에서 이름을 굵게. 띄어쓰기가 끼어 있어도('청담 어학원') 찾는다.
class HighlightedText extends StatelessWidget {
  final String text;
  final List<String> terms;
  final TextStyle? style;
  final TextStyle? highlight;
  final int? maxLines;
  const HighlightedText(
    this.text, {
    super.key,
    required this.terms,
    this.style,
    this.highlight,
    this.maxLines,
  });

  @override
  Widget build(BuildContext context) {
    if (terms.isEmpty || text.isEmpty) {
      return Text(text, style: style, maxLines: maxLines,
          overflow: maxLines == null ? null : TextOverflow.ellipsis);
    }
    final pattern = RegExp(
      terms
          .map((t) => t.split('').map(RegExp.escape).join(r'\s*'))
          .join('|'),
      caseSensitive: false,
    );
    final spans = <TextSpan>[];
    var last = 0;
    for (final m in pattern.allMatches(text)) {
      if (m.start > last) {
        spans.add(TextSpan(text: text.substring(last, m.start)));
      }
      spans.add(TextSpan(text: m.group(0), style: highlight));
      last = m.end;
    }
    if (last < text.length) spans.add(TextSpan(text: text.substring(last)));
    return Text.rich(
      TextSpan(style: style, children: spans),
      maxLines: maxLines,
      overflow: maxLines == null ? null : TextOverflow.ellipsis,
    );
  }
}
