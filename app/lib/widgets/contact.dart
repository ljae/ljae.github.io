import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/theme.dart';
import '../data/models.dart';
import '../data/contact_view_model.dart';
import '../data/reservations.dart';
import 'annals.dart';

/// Every external action uses the same validation and failure path.
Future<void> openExternal(String url) async {
  final uri = safeContactUrl(url);
  if (uri == null) return;
  try {
    await launchUrl(uri, mode: LaunchMode.externalApplication);
  } catch (_) {
    /* Caller has no context. */
  }
}

String telDigits(String tel) => safePhoneDigits(tel) ?? '';

Future<bool> copyContactText(
  BuildContext context,
  String value, {
  String success = '복사했습니다.',
}) async {
  try {
    await Clipboard.setData(ClipboardData(text: value));
    if (context.mounted) {
      ScaffoldMessenger.maybeOf(
        context,
      )?.showSnackBar(SnackBar(content: Text(success)));
    }
    return true;
  } catch (_) {
    if (context.mounted) {
      await showDialog<void>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('직접 선택해서 복사해주세요'),
          content: SelectableText(value),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('닫기'),
            ),
          ],
        ),
      );
    }
    return false;
  }
}

Future<void> callContact(
  BuildContext context,
  WidgetRef ref,
  ContactViewModel contact,
) async {
  final number = safePhoneDigits(contact.phone);
  if (number == null) return;
  unawaited(ref.read(actionLogProvider).log(contact.academyId, 'call'));
  var opened = false;
  try {
    opened = await launchUrl(
      Uri(scheme: 'tel', path: number),
      webOnlyWindowName: '_self',
    );
  } catch (_) {
    opened = false;
  }
  if (!opened && context.mounted) {
    await copyContactText(
      context,
      contact.phone!,
      success: '전화 앱을 열 수 없어 번호를 복사했습니다.',
    );
  }
}

Future<void> homepageContact(
  BuildContext context,
  WidgetRef ref,
  ContactViewModel contact,
) async {
  final uri = safeContactUrl(contact.officialUrl);
  if (uri == null) return;
  unawaited(ref.read(actionLogProvider).log(contact.academyId, 'homepage'));
  var opened = false;
  try {
    opened = await launchUrl(uri, mode: LaunchMode.externalApplication);
  } catch (_) {
    opened = false;
  }
  if (!opened && context.mounted) {
    await copyContactText(
      context,
      uri.toString(),
      success: '페이지를 열 수 없어 주소를 복사했습니다.',
    );
  }
}

Future<void> callAcademy(
  BuildContext context,
  WidgetRef ref,
  Academy academy,
) => callContact(context, ref, ContactViewModel.fromAcademy(academy));
Future<void> openHomepage(
  BuildContext context,
  WidgetRef ref,
  Academy academy,
) => homepageContact(context, ref, ContactViewModel.fromAcademy(academy));
Future<void> copyTel(
  BuildContext context,
  WidgetRef ref,
  Academy academy,
) async {
  final contact = ContactViewModel.fromAcademy(academy);
  if (contact.phone == null) return;
  unawaited(ref.read(actionLogProvider).log(academy.id, 'copy_tel'));
  await copyContactText(context, contact.phone!, success: '전화번호를 복사했습니다.');
}

/// 랭킹 카드의 '전화' 꼬리표. 상세로 들어가지 않고 바로 건다.
class CallTag extends ConsumerWidget {
  final Academy academy;
  const CallTag({super.key, required this.academy});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (safePhoneDigits(academy.tel) == null) return const SizedBox.shrink();
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
      return Text(
        text,
        style: style,
        maxLines: maxLines,
        overflow: maxLines == null ? null : TextOverflow.ellipsis,
      );
    }
    final pattern = RegExp(
      terms.map((t) => t.split('').map(RegExp.escape).join(r'\s*')).join('|'),
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
