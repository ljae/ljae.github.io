import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme.dart';
import '../../data/models.dart';
import '../../data/reservations.dart';
import '../../widgets/contact.dart';

/// 전화 · 레벨테스트 예약 카드.
///
/// 학부모가 학원 정보에서 다음에 하는 일은 둘이다 — 전화를 걸거나,
/// 레벨테스트를 잡거나. 번호를 글자로만 보여 주면 옮겨 적어야 한다.
///
/// 예약은 **요청 접수**다. 학원과 제휴가 없고, 확정처럼 보이는 접수는
/// 헛걸음의 책임을 우리에게 가져온다. 운영자가 학원에 연락해 잇고
/// 연락처로 회신한다. 화면이 그렇게 말한다.
class ContactCard extends ConsumerWidget {
  final Academy academy;
  const ContactCard({super.key, required this.academy});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final tel = academy.tel;
    final canReserve = ref.watch(reservationServiceProvider).enabled;

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
              tel != null
                  ? 'NEIS 등록 번호입니다. 레벨테스트 예약은 학원이 확정합니다 — '
                      '요청을 남기시면 운영자가 학원에 확인해 회신드립니다.'
                  : '공시에 전화번호가 없습니다. 예약 요청을 남기시면 운영자가 '
                      '연락처를 찾아 잇습니다.',
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
                OutlinedButton.icon(
                  onPressed: () => showModalBottomSheet<void>(
                    context: context,
                    isScrollControlled: true,
                    showDragHandle: true,
                    constraints: const BoxConstraints(maxWidth: 640),
                    builder: (_) => ReserveSheet(
                      academy: academy,
                      enabled: canReserve,
                    ),
                  ),
                  icon: const Icon(Icons.event_available_outlined, size: 16),
                  label: const Text('레벨테스트 예약 문의'),
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

/// 레벨테스트 예약 요청 시트.
///
/// 위에는 전화로 물어볼 것, 아래에는 요청 폼. 접수 기능이 없어도(Supabase
/// 미연결) 전화 안내는 나온다 — 빈 시트는 정보가 아니다.
class ReserveSheet extends ConsumerStatefulWidget {
  final Academy academy;
  final bool enabled;
  const ReserveSheet({super.key, required this.academy, required this.enabled});

  @override
  ConsumerState<ReserveSheet> createState() => _ReserveSheetState();
}

class _ReserveSheetState extends ConsumerState<ReserveSheet> {
  final _name = TextEditingController();
  final _contact = TextEditingController();
  final _preferred = TextEditingController();
  final _note = TextEditingController();
  String? _band;
  String? _subject;
  bool _sending = false;
  bool _sent = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    final bands = widget.academy.gradeBands;
    if (bands.length == 1) _band = bands.first;
    final subs = orderedSubjects(widget.academy.subjects)
        .where((s) => subjectNames.containsKey(s))
        .toList();
    if (subs.length == 1) _subject = subs.first;
  }

  @override
  void dispose() {
    _name.dispose();
    _contact.dispose();
    _preferred.dispose();
    _note.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_contact.text.trim().length < 5) {
      setState(() => _error = '회신받으실 연락처를 입력해 주세요.');
      return;
    }
    setState(() {
      _sending = true;
      _error = null;
    });
    try {
      await ref.read(reservationServiceProvider).submit(
            academyKey: widget.academy.id,
            academyName: widget.academy.displayName,
            contact: _contact.text.trim(),
            parentName:
                _name.text.trim().isEmpty ? null : _name.text.trim(),
            childBand: _band,
            subject: _subject,
            preferred: _preferred.text.trim().isEmpty
                ? null
                : _preferred.text.trim(),
            note: _note.text.trim().isEmpty ? null : _note.text.trim(),
          );
      unawaited(ref.read(actionLogProvider).log(widget.academy.id, 'reserve'));
      if (mounted) setState(() => _sent = true);
    } catch (_) {
      if (mounted) {
        setState(() {
          _sending = false;
          _error = '접수에 실패했습니다. 잠시 후 다시 시도해 주세요.';
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final a = widget.academy;
    final subs = orderedSubjects(a.subjects)
        .where((s) => subjectNames.containsKey(s))
        .toList();
    final bands = a.gradeBands.isEmpty ? gradeBandNames.keys.toList() : a.gradeBands;
    final ask = buildChecklist(a).take(4).toList();

    return Padding(
      padding: EdgeInsets.only(
        left: AppSpace.md,
        right: AppSpace.md,
        bottom: MediaQuery.viewInsetsOf(context).bottom + AppSpace.lg,
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('${a.displayName} — 레벨테스트 예약 문의', style: text.titleLarge),
            const SizedBox(height: 4),
            Text(
              '가장 빠른 길은 전화입니다. 전화하실 때 이것부터 물어보세요.',
              style: text.bodySmall,
            ),
            const SizedBox(height: AppSpace.sm),
            for (final it in ask)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Text('· ${it.label}'
                    '${it.note != null ? "  (${it.note})" : ""}',
                    style: text.bodyMedium),
              ),
            const SizedBox(height: AppSpace.sm),
            Wrap(
              spacing: AppSpace.sm,
              children: [
                FilledButton.icon(
                  onPressed: a.tel == null
                      ? null
                      : () => callAcademy(context, ref, a),
                  icon: const Icon(Icons.call, size: 16),
                  label: Text(a.tel != null ? '전화 ${a.tel}' : '전화번호 미공시'),
                ),
              ],
            ),
            const SizedBox(height: AppSpace.lg),
            Text('전화가 어려우시면 요청을 남겨 주세요', style: text.titleMedium),
            const SizedBox(height: 4),
            Text(
              '운영자가 학원에 확인해 연락처로 회신드립니다. 예약 확정은 학원이 '
              '합니다. 접수 내용은 공개되지 않습니다.',
              style: text.bodySmall,
            ),
            const SizedBox(height: AppSpace.md),
            if (!widget.enabled)
              Text('현재 접수 기능을 사용할 수 없습니다. 전화로 문의해 주세요.',
                  style: text.bodyMedium)
            else if (_sent) ...[
              Text(
                '접수됐습니다. 확인되는 대로 회신드립니다.\n'
                '확정된 일정이 아닙니다 — 학원의 답을 받은 뒤에 알려 드립니다.',
                style: text.bodyMedium,
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
              Text('아이 학년', style: text.labelMedium),
              const SizedBox(height: 4),
              Wrap(
                spacing: AppSpace.sm,
                runSpacing: AppSpace.xs,
                children: [
                  for (final b in bands)
                    ChoiceChip(
                      label: Text(gradeBandNames[b] ?? b),
                      selected: _band == b,
                      onSelected: (on) => setState(() => _band = on ? b : null),
                    ),
                ],
              ),
              if (subs.length > 1) ...[
                const SizedBox(height: AppSpace.sm),
                Text('과목', style: text.labelMedium),
                const SizedBox(height: 4),
                Wrap(
                  spacing: AppSpace.sm,
                  runSpacing: AppSpace.xs,
                  children: [
                    for (final s in subs)
                      ChoiceChip(
                        label: Text(subjectNames[s] ?? s),
                        selected: _subject == s,
                        onSelected: (on) =>
                            setState(() => _subject = on ? s : null),
                      ),
                  ],
                ),
              ],
              const SizedBox(height: AppSpace.md),
              TextField(
                controller: _contact,
                decoration: const InputDecoration(
                  border: OutlineInputBorder(),
                  labelText: '회신받으실 연락처 (전화 또는 이메일) *',
                ),
              ),
              const SizedBox(height: AppSpace.sm),
              TextField(
                controller: _name,
                decoration: const InputDecoration(
                  border: OutlineInputBorder(),
                  labelText: '보호자 성함 (선택)',
                ),
              ),
              const SizedBox(height: AppSpace.sm),
              TextField(
                controller: _preferred,
                decoration: const InputDecoration(
                  border: OutlineInputBorder(),
                  labelText: '희망 일시 (선택)',
                  helperText: '예: 이번 주 토요일 오전, 평일 5시 이후',
                ),
              ),
              const SizedBox(height: AppSpace.sm),
              TextField(
                controller: _note,
                maxLines: 3,
                maxLength: 1000,
                decoration: const InputDecoration(
                  border: OutlineInputBorder(),
                  labelText: '덧붙일 말 (선택)',
                  helperText: '현재 다니는 학원, 목표, 궁금한 점',
                ),
              ),
              if (_error != null) ...[
                const SizedBox(height: AppSpace.sm),
                Text(_error!,
                    style: text.bodySmall?.copyWith(color: AppColors.rising)),
              ],
              const SizedBox(height: AppSpace.md),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: _sending ? null : _submit,
                  child: Text(_sending ? '접수 중…' : '예약 요청 남기기'),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

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
