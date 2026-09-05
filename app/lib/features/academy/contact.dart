import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme.dart';
import '../../data/models.dart';
// 근거 신고 시트가 쓴다. 레벨테스트 예약 대행은 없앴지만(2026-09-05)
// 신고 접수는 남는다 — 그쪽은 우리가 처리해야 하는 일이다.
import '../../data/reservations.dart';
import '../../widgets/contact.dart';

/// 전화 · 학원 홈페이지 카드.
///
/// 학부모가 학원 정보에서 다음에 하는 일은 둘이다 — 전화를 걸거나,
/// 레벨테스트를 잡거나. 번호를 글자로만 보여 주면 옮겨 적어야 한다.
///
/// ★ 2026-09-05: **레벨테스트 예약 대행을 없앴다.**
///   예전에는 이 화면에서 요청을 접수하고 운영자가 학원에 확인해 회신했다.
///   학원과 제휴가 없는데 중간에 서면, 학부모는 우리에게 신청했다고
///   여기고 학원은 그런 신청을 받은 적이 없다. **레벨테스트는 학원에
///   직접 신청한다** — 우리는 닿는 곳(전화·공식 페이지)만 준다.
///
///   전화도 링크도 없으면 **버튼을 만들지 않는다.** 아무 일도 안 일어나는
///   버튼이 가장 나쁘다.
class ContactCard extends ConsumerWidget {
  final Academy academy;
  const ContactCard({super.key, required this.academy});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final tel = academy.tel;
    final homepage = academy.homepage;

    return DecoratedBox(
      decoration: BoxDecoration(
        color: AppColors.surfaceOn(dark),
        border: Border(
          left: BorderSide(color: AppColors.accentOn(dark), width: AppRule.stroke),
          top: BorderSide(color: AppColors.ruleOn(dark), width: AppRule.hair),
          right: BorderSide(color: AppColors.ruleOn(dark), width: AppRule.hair),
          bottom: BorderSide(color: AppColors.ruleOn(dark), width: AppRule.hair),
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(AppSpace.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.call_outlined, size: 18, color: AppColors.accentOn(dark)),
                const SizedBox(width: 6),
                Text(
                  tel != null ? '전화 $tel' : '전화번호 미공시',
                  style: text.titleMedium,
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              tel != null || homepage != null
                  ? '레벨테스트는 학원에 직접 신청합니다. '
                      '학원실록은 신청을 대신 받지 않습니다.'
                  : '학원이 공시한 연락처가 없습니다. '
                      '알고 계신 연락처가 있으면 정정 요청으로 알려 주세요.',
              style: text.bodySmall,
            ),
            const SizedBox(height: AppSpace.sm),
            Wrap(
              spacing: AppSpace.sm,
              runSpacing: AppSpace.xs,
              children: [
                FilledButton.icon(
                  onPressed: tel == null
                      ? null
                      : () => callAcademy(context, ref, academy),
                  icon: const Icon(Icons.call, size: 16),
                  label: const Text('전화하기'),
                ),
                // 공식 페이지가 있을 때만. 없으면 만들지 않는다 —
                // 링크 없는 '신청하기' 는 아무 일도 일어나지 않는다.
                if (homepage != null)
                  OutlinedButton.icon(
                    onPressed: () => openHomepage(context, ref, academy),
                    icon: const Icon(Icons.open_in_new, size: 16),
                    label: const Text('학원 홈페이지 · 레벨테스트 신청'),
                  ),
                if (tel != null)
                  TextButton.icon(
                    onPressed: () => copyTel(context, ref, academy),
                    icon: const Icon(Icons.copy, size: 14),
                    label: const Text('번호 복사'),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// 상담 전 확인 목록의 한 줄.
class ChecklistItem {
  final String label;

  /// 후기가 이미 말해 준 것. 없으면 '아직 모른다'.
  final String? note;
  final bool confirmed;
  const ChecklistItem(this.label, {this.note, this.confirmed = false});
}

/// 후기·공시가 이미 답한 것과 아직 모르는 것을 나눠 적는다.
///
/// 값은 전부 화면의 다른 자리에서 온다(사실 카드·진입난이도·관점·정원).
/// 여기서 새로 추정하는 것은 없다 — 질문 목록이지 평가가 아니다.
List<ChecklistItem> buildChecklist(Academy a) {
  final items = <ChecklistItem>[];
  String? fact(String key) {
    final f = a.facts[key];
    return (f != null && f.hasValue) ? f.text : null;
  }

  AspectStat? aspect(String key) => a.aspects[key];

  final sel = a.selectivityEvidence.where((c) => c.isActive).toList();
  final failed = sel.where((c) => c.kind == 'sel.test_failed').length;
  final waiting = sel
      .where((c) => c.kind == 'sel.waitlist' || c.kind == 'sel.full')
      .length;
  items.add(ChecklistItem(
    '레벨테스트 일정 · 범위 · 재응시 가능 시기',
    note: failed > 0
        ? '후기에 탈락 사례 $failed건 — 준비 범위를 꼭 물어보세요'
        : sel.isNotEmpty
            ? '후기에 레벨테스트 언급이 있습니다'
            : null,
    confirmed: sel.isNotEmpty,
  ));
  if (waiting > 0) {
    items.add(ChecklistItem(
      '대기 인원과 예상 대기 기간',
      note: '후기에 대기·마감 사례 $waiting건',
      confirmed: true,
    ));
  }

  final freq = fact('fact.class_freq');
  final mins = fact('fact.class_minutes');
  final hours = fact('derived.class_hours');
  final classNote = [
    if (freq != null) '주 $freq',
    if (mins != null) '1회 $mins',
    if (hours != null) '주당 $hours',
  ].join(' · ');
  items.add(ChecklistItem(
    '수업 횟수와 1회 수업 시간',
    note: classNote.isEmpty ? null : '후기: $classNote — 우리 아이 반도 같은지',
    confirmed: classNote.isNotEmpty,
  ));

  final hw = fact('fact.homework');
  final hwAspect = aspect('숙제량');
  items.add(ChecklistItem(
    '숙제 분량과 확인 방식',
    note: hw != null
        ? '후기: 하루 $hw — 아이가 소화할 수 있는 양인지'
        : hwAspect != null
            ? '후기 ${hwAspect.n}건이 숙제량을 ${hwAspect.tone}'
            : null,
    confirmed: hw != null || hwAspect != null,
  ));

  final test = fact('fact.test_freq');
  items.add(ChecklistItem(
    '정기 시험 주기와 결과 안내 방식',
    note: test != null ? '후기: 월 $test' : null,
    confirmed: test != null,
  ));

  items.add(ChecklistItem(
    '반 정원과 반 편성 기준',
    note: a.capacity != null ? '등록 정원 ${a.capacity}명(전체 공시값)' : null,
  ));

  final price = aspect('가격');
  items.add(ChecklistItem(
    '교습비 외 교재비·추가 비용',
    note: price != null ? '후기 ${price.n}건이 비용을 ${price.tone}' : null,
    confirmed: price != null,
  ));

  final care = aspect('관리');
  final teacher = aspect('강사');
  items.add(ChecklistItem(
    '결석 보강 · 상담 주기 · 담당 선생님',
    note: [
      if (care != null) '관리 ${care.tone}(${care.n}건)',
      if (teacher != null) '선생님 ${teacher.tone}(${teacher.n}건)',
    ].join(' · ').ifEmpty(),
    confirmed: care != null || teacher != null,
  ));

  final place = aspect('시설');
  items.add(ChecklistItem(
    '통학 · 셔틀 · 대기 공간',
    note: place != null ? '후기 ${place.n}건이 시설·통학을 ${place.tone}' : null,
    confirmed: place != null,
  ));

  if (a.gradeBands.isNotEmpty) {
    items.add(ChecklistItem(
      '우리 아이 학년 반이 열려 있는지',
      note: '공시·후기 기준 대상: ${a.gradeBands.map((b) => gradeBandNames[b] ?? b).join(' · ')}',
    ));
  }
  return items;
}

extension on String {
  String? ifEmpty() => isEmpty ? null : this;
}

/// 상담 전 확인 목록. 복사해 가져갈 수 있다.
class ConsultChecklist extends StatelessWidget {
  final Academy academy;
  const ConsultChecklist({super.key, required this.academy});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final items = buildChecklist(academy);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpace.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            for (final it in items)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 5),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(
                      it.confirmed
                          ? Icons.check_box_outlined
                          : Icons.check_box_outline_blank,
                      size: 17,
                      color: it.confirmed
                          ? AppColors.verified
                          : AppColors.mutedOn(dark),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(it.label, style: text.bodyLarge),
                          if (it.note != null)
                            Text(
                              it.note!,
                              style: text.bodySmall?.copyWith(
                                color: it.confirmed
                                    ? AppColors.verified
                                    : AppColors.mutedOn(dark),
                              ),
                            ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            const SizedBox(height: AppSpace.xs),
            Align(
              alignment: Alignment.centerRight,
              child: TextButton.icon(
                onPressed: () async {
                  final body = [
                    '${academy.displayName} 상담 전 확인',
                    for (final it in items)
                      '${it.confirmed ? "■" : "□"} ${it.label}'
                          '${it.note != null ? " — ${it.note}" : ""}',
                  ].join('\n');
                  await Clipboard.setData(ClipboardData(text: body));
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('확인 목록을 복사했습니다.')),
                    );
                  }
                },
                icon: const Icon(Icons.copy, size: 14),
                label: const Text('목록 복사'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// ★ 2026-09-05: `ReserveSheet`(레벨테스트 예약 요청 폼)를 없앴다.
///
/// 학원과 제휴가 없는데 중간에 서면, 학부모는 우리에게 신청했다고 여기고
/// 학원은 그런 신청을 받은 적이 없다. 레벨테스트는 **학원에 직접** 신청한다 —
/// 이 화면은 닿는 곳(전화·공식 페이지)만 준다. 이미 들어온 접수는 지우지
/// 않고 `/admin` 예약 탭과 corrections_report 에서 처리한다.

/// '이 학원 글이 아니에요' 신고 시트.
///
/// 사유를 반드시 받는다. 접수는 반영이 아니다 — 파이프라인이 신고된 글을
/// 질문 큐 맨 앞에 올리고 운영자의 답이 판정이 된다. 익명 신고가 곧 삭제가
/// 되면 학원이 불리한 글만 지우는 통로가 된다.
class EvidenceReportSheet extends ConsumerStatefulWidget {
  final Academy academy;
  final Evidence evidence;
  const EvidenceReportSheet({
    super.key,
    required this.academy,
    required this.evidence,
  });

  @override
  ConsumerState<EvidenceReportSheet> createState() => _EvidenceReportSheetState();
}

class _EvidenceReportSheetState extends ConsumerState<EvidenceReportSheet> {
  ReportReason? _reason;
  final _note = TextEditingController();
  bool _sending = false;
  bool _sent = false;

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final hash = widget.evidence.urlHash;
    if (_reason == null || _sending || hash == null) return;
    setState(() => _sending = true);
    try {
      await ref.read(evidenceReportServiceProvider).submit(
            urlHash: hash,
            academyKey: widget.academy.id,
            sourceUrl: widget.evidence.url,
            title: widget.evidence.title,
            reason: _reason!,
            note: _note.text.trim().isEmpty ? null : _note.text.trim(),
          );
      if (mounted) setState(() => _sent = true);
    } catch (e) {
      if (mounted) {
        setState(() => _sending = false);
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('접수하지 못했습니다: $e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final hash = widget.evidence.urlHash;
    return Padding(
      padding: EdgeInsets.only(
        left: AppSpace.md,
        right: AppSpace.md,
        top: AppSpace.md,
        bottom: MediaQuery.viewInsetsOf(context).bottom + AppSpace.md,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('이 글은 ${widget.academy.displayName} 글이 아니에요',
              style: t.textTheme.titleMedium),
          const SizedBox(height: AppSpace.sm),
          Text('[${widget.evidence.ref}] ${widget.evidence.title}',
              style: t.textTheme.bodySmall),
          const SizedBox(height: AppSpace.md),
          if (hash == null)
            Text('이 근거는 옛 데이터라 신고할 수 없습니다. 다음 갱신 후 다시 시도해 주세요.',
                style: t.textTheme.bodyMedium)
          else if (_sent) ...[
            Text(
              '접수됐습니다. 운영자가 확인하면 다음 갱신에서 빠집니다.\n'
              '바로 지워지지 않는 이유: 접수가 곧 편집권이 되면 그것도 왜곡입니다.',
              style: t.textTheme.bodyMedium,
            ),
            const SizedBox(height: AppSpace.md),
            Align(
              alignment: Alignment.centerRight,
              child: FilledButton(
                onPressed: () => Navigator.of(context).pop(),
                child: const Text('닫기'),
              ),
            ),
          ] else ...[
            Wrap(
              spacing: AppSpace.sm,
              runSpacing: AppSpace.xs,
              children: [
                for (final r in ReportReason.values)
                  ChoiceChip(
                    label: Text(r.label),
                    selected: _reason == r,
                    onSelected: (on) => setState(() => _reason = on ? r : null),
                  ),
              ],
            ),
            const SizedBox(height: AppSpace.sm),
            TextField(
              controller: _note,
              maxLength: 500,
              decoration: const InputDecoration(
                labelText: '덧붙일 말 (선택) — 어느 학원 글인지 아시면 적어 주세요',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: AppSpace.sm),
            Align(
              alignment: Alignment.centerRight,
              child: FilledButton(
                onPressed: _reason == null || _sending ? null : _send,
                child: Text(_sending ? '보내는 중…' : '신고 접수'),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
