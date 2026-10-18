import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../data/academy_detail.dart';
import '../data/models.dart';
import '../data/parent_decision.dart';
import '../data/repository.dart';
import '../data/riding_plan.dart';
import 'contact.dart';

/// Public location and explicitly personal travel notes stay separate.
class RidingCard extends ConsumerWidget {
  final AcademyDetail detail;
  const RidingCard({super.key, required this.detail});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final selection = ref.watch(selectionProvider);
    final key = ridingKey(detail.id, selection.subject, selection.gradeBand);
    final plan = ref.watch(ridingPlansProvider)[key];
    final address = detail.academy?.address ?? detail.registry?.address;
    final text = Theme.of(context).textTheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SelectableText(
          address?.trim().isNotEmpty == true ? address! : '주소 미확인',
        ),
        if (address?.trim().isNotEmpty == true)
          Wrap(
            spacing: 8,
            children: [
              TextButton.icon(
                onPressed: () => openExternal(
                  'https://map.naver.com/p/search/${Uri.encodeComponent(address!)}',
                ),
                icon: const Icon(Icons.route_outlined, size: 18),
                label: const Text('지도에서 동선 확인'),
              ),
              TextButton(
                onPressed: () => copyContactText(context, address!),
                child: const Text('주소 복사'),
              ),
            ],
          ),
        const Text(
          '출발지는 지도에서 직접 입력해주세요. 학교→학원과 학원→집을 각각 확인하고, 직접 픽업한다면 주차·대기 장소도 살펴보세요.',
        ),
        const SizedBox(height: 12),
        const Text(
          '셔틀·하원 조건은 현재 반에 문의 필요',
          style: TextStyle(fontWeight: FontWeight.w600),
        ),
        const Text('셔틀 운행 여부·정류장·요일, 정확한 종료 시각과 보강일 귀가 방법을 함께 확인해주세요.'),
        const Divider(height: 28),
        Text(
          '내 이동 조건 · ${gradeBandNames[selection.gradeBand]} ${subjectNames[selection.subject]}',
          style: text.titleSmall,
        ),
        const SizedBox(height: 8),
        if (plan == null)
          const Text('아직 적은 이동 조건이 없어요. 실제로 확인한 시간과 가능한 동선을 적으면 비교 노트에도 이어집니다.')
        else ...[
          Text(ridingModes[plan.mode]!),
          Text(
            [
              if (plan.oneWayMinutes != null)
                '내가 확인한 편도 ${plan.oneWayMinutes}분',
              if (plan.days != null) '주 ${plan.days}회',
              if (plan.finish != null) '검토 중인 하원 ${plan.finish}',
            ].join(' · '),
          ),
          Text(ridingFits[plan.fit]!, style: text.titleSmall),
          if (plan.weeklyGuardianMinutes case final minutes?) ...[
            const SizedBox(height: 8),
            Text('보호자 주간 이동·대기 $minutes분', style: text.titleMedium),
            Text(
              '내가 입력한 하루 ${plan.guardianMinutes}분 × 주 ${plan.days}회. 등원·하원에 드는 시간을 합쳐 입력한 값입니다.',
              style: text.bodySmall,
            ),
          ] else
            const Text('하루 보호자 시간과 주간 횟수를 모두 적으면 한 주의 부담을 비교할 수 있어요.'),
          const SizedBox(height: 8),
          Text(
            '내 메모 · 입력 ${plan.updatedAt} · 학원의 확인된 운영 정보가 아닙니다.',
            style: text.bodySmall,
          ),
        ],
        const SizedBox(height: 12),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            OutlinedButton.icon(
              onPressed: () => showModalBottomSheet<void>(
                context: context,
                isScrollControlled: true,
                useSafeArea: true,
                builder: (_) => _RidingEditor(
                  detail: detail,
                  planKey: key,
                  plan: plan,
                  scope:
                      '${gradeBandNames[selection.gradeBand]} ${subjectNames[selection.subject]}',
                ),
              ),
              icon: const Icon(Icons.edit_outlined, size: 18),
              label: Text(plan == null ? '라이딩 메모 작성' : '라이딩 메모 수정'),
            ),
            TextButton(
              onPressed: () => copyContactText(
                context,
                '${detailName(detail)} 라이딩 문의\n${ridingInquiry(plan)}',
              ),
              child: const Text('이동 조건 포함 질문 복사'),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Text('이동 메모는 이 기기에만 보관하며 서버나 비교 링크로 보내지 않습니다.', style: text.bodySmall),
      ],
    );
  }
}

class _RidingEditor extends ConsumerStatefulWidget {
  final AcademyDetail detail;
  final String planKey, scope;
  final RidingPlan? plan;
  const _RidingEditor({
    required this.detail,
    required this.planKey,
    required this.scope,
    this.plan,
  });
  @override
  ConsumerState<_RidingEditor> createState() => _RidingEditorState();
}

class _RidingEditorState extends ConsumerState<_RidingEditor> {
  final form = GlobalKey<FormState>();
  late final TextEditingController oneWay, guardian, finish;
  late String mode, fit;
  int? days;
  @override
  void initState() {
    super.initState();
    final p = widget.plan;
    mode = p?.mode ?? 'unknown';
    fit = p?.fit ?? 'unknown';
    days = p?.days;
    oneWay = TextEditingController(text: p?.oneWayMinutes?.toString() ?? '');
    guardian = TextEditingController(
      text: p?.guardianMinutes?.toString() ?? '',
    );
    finish = TextEditingController(text: p?.finish ?? '');
  }

  @override
  void dispose() {
    oneWay.dispose();
    guardian.dispose();
    finish.dispose();
    super.dispose();
  }

  void done(bool stored, {bool removed = false}) {
    final messenger = ScaffoldMessenger.of(context);
    Navigator.pop(context);
    messenger.showSnackBar(
      SnackBar(
        content: Text(
          stored
              ? removed
                    ? '이 반의 라이딩 메모를 지웠습니다.'
                    : '이동 조건을 저장했습니다. 학원 소개와 비교 노트에서 함께 볼 수 있어요.'
              : removed
              ? '화면에서는 지웠지만 기기 저장소를 지우지 못했습니다. 다시 열면 이전 메모가 남아 있을 수 있어요.'
              : '기기 저장소에 보관하지 못했습니다. 현재 화면에서만 사용할 수 있어요.',
        ),
      ),
    );
  }

  Widget minutes(
    TextEditingController controller,
    String label,
    String helper,
    int max,
  ) => TextFormField(
    controller: controller,
    keyboardType: TextInputType.number,
    inputFormatters: [FilteringTextInputFormatter.digitsOnly],
    decoration: InputDecoration(
      labelText: label,
      helperText: helper,
      helperMaxLines: 3,
      suffixText: '분',
    ),
    validator: (v) {
      if (v == null || v.trim().isEmpty) return null;
      final n = int.tryParse(v);
      return n != null && n >= 0 && n <= max ? null : '0~$max분 사이로 입력해주세요.';
    },
  );
  @override
  Widget build(BuildContext context) => SafeArea(
    child: SingleChildScrollView(
      padding: EdgeInsets.fromLTRB(
        20,
        24,
        20,
        24 + MediaQuery.viewInsetsOf(context).bottom,
      ),
      child: Form(
        key: form,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '${detailName(widget.detail)} 라이딩 메모',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            Text(widget.scope),
            const SizedBox(height: 8),
            const Text(
              '직접 확인한 조건만 적어주세요. 집·학교 주소와 아이의 이름은 저장하지 않습니다. 항목을 비워두면 미확인으로 남습니다.',
            ),
            const SizedBox(height: 20),
            DropdownButtonFormField<String>(
              initialValue: mode,
              isExpanded: true,
              decoration: const InputDecoration(labelText: '이동 방법'),
              items: [
                for (final e in ridingModes.entries)
                  DropdownMenuItem(value: e.key, child: Text(e.value)),
              ],
              onChanged: (v) => setState(() => mode = v!),
            ),
            const SizedBox(height: 16),
            minutes(
              oneWay,
              '확인한 편도 이동 시간 · 선택',
              '지도에서 확인하거나 실제 이동해본 시간을 적어주세요.',
              240,
            ),
            const SizedBox(height: 16),
            DropdownButtonFormField<int>(
              initialValue: days,
              isExpanded: true,
              decoration: const InputDecoration(labelText: '주간 등원 횟수 · 선택'),
              items: [
                const DropdownMenuItem<int>(value: null, child: Text('미확인')),
                for (var i = 1; i <= 7; i++)
                  DropdownMenuItem(value: i, child: Text('주 $i회')),
              ],
              onChanged: (v) => setState(() => days = v),
            ),
            const SizedBox(height: 16),
            minutes(
              guardian,
              '하루 보호자 이동·대기 시간 · 선택',
              '학원에 가는 하루 동안 등원·하원 라이딩과 왕복·대기를 모두 합친 시간입니다.',
              1440,
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: finish,
              keyboardType: TextInputType.datetime,
              decoration: const InputDecoration(
                labelText: '검토 중인 하원 시각 · 선택',
                hintText: '예: 18:30',
              ),
              validator: (v) =>
                  v == null ||
                      v.trim().isEmpty ||
                      RegExp(r'^([01]\d|2[0-3]):[0-5]\d$').hasMatch(v.trim())
                  ? null
                  : '18:30처럼 24시간 형식으로 입력해주세요.',
            ),
            const SizedBox(height: 16),
            DropdownButtonFormField<String>(
              initialValue: fit,
              isExpanded: true,
              decoration: const InputDecoration(labelText: '내 일정에서의 하원 동선'),
              items: [
                for (final e in ridingFits.entries)
                  DropdownMenuItem(value: e.key, child: Text(e.value)),
              ],
              onChanged: (v) => setState(() => fit = v!),
            ),
            const SizedBox(height: 24),
            Wrap(
              spacing: 10,
              runSpacing: 8,
              children: [
                FilledButton(
                  onPressed: () {
                    if (!form.currentState!.validate()) return;
                    final plan = RidingPlan(
                      mode: mode,
                      fit: fit,
                      days: days,
                      oneWayMinutes: int.tryParse(oneWay.text),
                      guardianMinutes: int.tryParse(guardian.text),
                      finish: finish.text.trim().isEmpty
                          ? null
                          : finish.text.trim(),
                      updatedAt: DateTime.now()
                          .toIso8601String()
                          .split('T')
                          .first,
                    );
                    done(
                      ref
                          .read(ridingPlansProvider.notifier)
                          .save(widget.planKey, plan),
                    );
                  },
                  child: const Text('내 기기에 저장'),
                ),
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('취소'),
                ),
                if (widget.plan != null)
                  TextButton(
                    onPressed: () => done(
                      ref
                          .read(ridingPlansProvider.notifier)
                          .remove(widget.planKey),
                      removed: true,
                    ),
                    child: const Text('이 반의 메모 지우기'),
                  ),
              ],
            ),
          ],
        ),
      ),
    ),
  );
}
