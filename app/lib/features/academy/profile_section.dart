import 'package:flutter/material.dart';

import '../../core/theme.dart';
import '../../data/models.dart';
import '../../widgets/annals.dart';
import '../../widgets/common.dart';
import '../../widgets/contact.dart';

/// 공개 글의 요약. 적합성 판단은 표시하지 않고 근거를 함께 보여준다.
class ProfilePanel extends StatefulWidget {
  final Academy academy;
  const ProfilePanel({super.key, required this.academy});

  @override
  State<ProfilePanel> createState() => _ProfilePanelState();
}

enum _Row { levelTest, homework, curriculum, ops }

class _ProfilePanelState extends State<ProfilePanel> {
  final Set<_Row> _open = {};

  @override
  Widget build(BuildContext context) {
    final profile = widget.academy.profile;
    if (profile == null || !profile.hasContent) return const SizedBox.shrink();
    final text = Theme.of(context).textTheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    // 한 번만 센다 — getter 가 매번 다시 매기는 값이다.
    final refs = widget.academy.sourceRefs;
    final rows = <(_Row, String, ProfileSection?)>[
      (_Row.levelTest, '레벨테스트', profile.levelTest),
      (_Row.homework, '숙제', profile.homework),
      (_Row.curriculum, '커리큘럼', profile.curriculum),
      (_Row.ops, '위치·운영', profile.ops),
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SectionHeader(
          '공개 글에서 읽은 수업 정보',
          subtitle:
              '자료 ${profile.sources}건을 읽고 AI가 요약했습니다. 아래 인용은 '
              '요약의 근거이며, 요약 자체의 정확성을 보장하지 않습니다. '
              '공식 안내와 작성 시점을 함께 확인해 주세요.',
        ),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(AppSpace.md),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (var i = 0; i < rows.length; i++) ...[
                  if (i > 0) Rule(color: AppColors.ruleSoftOn(dark)),
                  _ProfileRow(
                    kind: rows[i].$1,
                    label: rows[i].$2,
                    section: rows[i].$3,
                    refs: refs,
                    open: _open.contains(rows[i].$1),
                    onToggle: () => setState(() {
                      if (!_open.add(rows[i].$1)) _open.remove(rows[i].$1);
                    }),
                  ),
                ],
                const SizedBox(height: AppSpace.sm),
                // 문장의 임자를 밝힌다. 산식에 안 들어가므로 모델을 갈아끼워도
                // 되지만, 그래서 더 적어 둔다.
                Text(
                  '생성 ${profile.generatedAt} · 모델 ${profile.model}',
                  style: text.bodySmall?.copyWith(
                    color: AppColors.mutedOn(dark),
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

/// 장부 행 하나. 왼쪽 라벨 셀(96px) + 오른쪽 본문.
class _ProfileRow extends StatelessWidget {
  final _Row kind;
  final String label;
  final ProfileSection? section;
  final Map<String, int> refs;
  final bool open;
  final VoidCallback onToggle;
  const _ProfileRow({
    required this.kind,
    required this.label,
    required this.section,
    required this.refs,
    required this.open,
    required this.onToggle,
  });

  bool get _empty {
    final s = section;
    return s == null ||
        s.quotes.isEmpty ||
        (s.note == null &&
            s.band == null &&
            s.load == null &&
            s.shuttle == null);
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final s = section;
    final empty = _empty;

    // 이 절의 인용이 받은 번호. 원문 목록·사실 카드와 같은 번호다.
    final numbers = empty
        ? const <int>[]
        : (s!.quotes.map((q) => refs[q.url]).whereType<int>().toSet().toList()
            ..sort());

    return InkWell(
      onTap: empty ? null : onToggle,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 9),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(
              width: 96,
              child: Text(
                label,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: text.labelMedium,
              ),
            ),
            Expanded(
              child: empty
                  ? Text(
                      '아직 근거 부족',
                      style: text.bodyMedium?.copyWith(
                        color: AppColors.mutedOn(dark),
                      ),
                    )
                  : Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        if (_tags(s!, dark) case final tags
                            when tags.isNotEmpty) ...[
                          Wrap(spacing: 6, runSpacing: 4, children: tags),
                          const SizedBox(height: 6),
                        ],
                        ..._body(s, text),
                        const SizedBox(height: 4),
                        Wrap(
                          spacing: 4,
                          runSpacing: 3,
                          crossAxisAlignment: WrapCrossAlignment.center,
                          children: [
                            Text(
                              '근거 ${s.sourceCount}건',
                              style: text.bodySmall?.copyWith(
                                color: AppColors.mutedOn(dark),
                              ),
                            ),
                            for (final n in numbers) RefMark(n, small: true),
                            Icon(
                              open ? Icons.expand_less : Icons.expand_more,
                              size: 15,
                              color: AppColors.mutedOn(dark),
                            ),
                          ],
                        ),
                        if (open)
                          for (final q in s.quotes)
                            _ProfileQuoteTile(quote: q, ref: refs[q.url]),
                      ],
                    ),
            ),
          ],
        ),
      ),
    );
  }

  /// 등급 꼬리표. 추정색이다 — 주묵을 쓰지 않는다.
  List<Widget> _tags(ProfileSection s, bool dark) => switch (kind) {
    _Row.levelTest => [
      if (s.band case final band?)
        TagMark(band, color: AppColors.estimatedOn(dark)),
      if (s.hard case final hard?)
        TagMark('$hard 어려움', color: AppColors.mutedOn(dark)),
    ],
    _Row.homework => [
      if (s.load case final load?)
        TagMark(load, color: AppColors.estimatedOn(dark)),
    ],
    _Row.ops => [
      if (s.shuttle case final shuttle?)
        TagMark(
          shuttle ? '셔틀 있음' : '셔틀 없음',
          color: AppColors.mutedOn(dark),
          icon: Icons.directions_bus_outlined,
        ),
    ],
    _ => const [],
  };

  List<Widget> _body(ProfileSection s, TextTheme text) => [
    if (s.note case final note?) Text(note, style: text.bodyMedium),
  ];
}

/// 인용 한 줄. 사실 카드의 인용(`_ClaimQuote`)과 같은 얼굴 — 따옴표·날짜·
/// [번호]·원문 링크. 이의 버튼은 없다. 프로필 문장은 주장(claim)이 아니라
/// 인용의 요약이고, 인용 자체가 틀렸으면 근거 줄의 신고로 간다.
class _ProfileQuoteTile extends StatelessWidget {
  final ProfileQuote quote;
  final int? ref;
  const _ProfileQuoteTile({required this.quote, this.ref});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('“${quote.quote}”', style: text.bodySmall),
                const SizedBox(height: 2),
                Wrap(
                  spacing: 6,
                  runSpacing: 2,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    Text(
                      quote.postedAt ?? '작성일 미상',
                      style: text.labelSmall?.copyWith(
                        color: AppColors.mutedOn(dark),
                      ),
                    ),
                    Text(
                      Uri.tryParse(quote.url)?.host ?? '',
                      style: text.labelSmall,
                    ),
                    if (!quote.isSelf) const Text('공개 글 · 작성자 성격 미확인'),
                    // 학원이 스스로 말한 것은 학부모 후기와 같은 얼굴로
                    // 두지 않는다.
                    if (quote.isSelf)
                      TagMark(
                        '학원 자기 서술',
                        color: AppColors.mutedOn(dark),
                        icon: Icons.storefront_outlined,
                      ),
                  ],
                ),
              ],
            ),
          ),
          if (ref case final n?)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: RefMark(n, small: true),
            ),
          if (quote.url.isNotEmpty)
            IconButton(
              tooltip: '원문 보기',
              icon: const Icon(Icons.open_in_new, size: 16),
              onPressed: () => openExternal(quote.url),
            ),
        ],
      ),
    );
  }
}
