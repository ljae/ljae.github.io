import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme.dart';
import '../../data/models.dart';
import '../../data/parent_reports.dart';
import '../../data/repository.dart';
import '../../widgets/annals.dart';
import '../../widgets/annals_controls.dart';
import '../../widgets/common.dart';

/// 학부모 제보 — `/tell?academy=<id>`.
///
/// 학원 한 곳에 대해 고르기만 하는 30초짜리 폼이다. **적는 칸이 없다.**
/// 학원을 찾는 검색 칸은 이 기기 안에서만 쓰이고 서버로 가지 않는다.
///
/// 화면은 둘로 갈린다. 학원을 정하는 [ParentReportPage] 와, 정해진 학원에
/// 답을 고르는 [ParentReportForm]. 폼은 학원 id 와 이름만 받으므로 데이터
/// 없이도 시험할 수 있다.
class ParentReportPage extends ConsumerWidget {
  final String? academyId;
  const ParentReportPage({super.key, this.academyId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final data = ref.watch(dataProvider);
    final asked = academyId?.trim() ?? '';

    Widget body;
    if (data.hasError && !data.hasValue) {
      body = _Notice(
        '학원 목록을 불러오지 못했습니다.',
        action: ('다시 불러오기', () => ref.invalidate(dataProvider)),
      );
    } else if (!data.hasValue) {
      body = const _Notice('학원 목록을 불러오는 중입니다…');
    } else if (asked.isEmpty) {
      body = _AcademyPicker(data: data.requireValue);
    } else {
      final scored = data.requireValue.academyById[asked];
      if (scored != null) {
        // 옛 등록번호로 들어와도 지금의 id 로 보낸다.
        body = ParentReportForm(
          key: ValueKey(scored.id),
          academyId: scored.id,
          academyName: scored.displayName,
        );
      } else {
        // 채점 대상이 아니면 등록부에서 찾는다. 아직 점수를 매긴 적 없는
        // 학원이야말로 제보가 가장 값진 곳이다.
        final registry = ref.watch(registryProvider);
        final listed = registry.value?.where((r) => r.id == asked).firstOrNull;
        if (listed != null) {
          body = ParentReportForm(
            key: ValueKey(listed.id),
            academyId: listed.id,
            academyName: listed.displayName,
          );
        } else if (registry.isLoading) {
          body = const _Notice('학원을 찾는 중입니다…');
        } else {
          // 목록에 없는 id 로는 받지 않는다 — 없는 학원에 답이 쌓인다.
          body = Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _Notice(
                registry.hasError
                    ? '등록부를 불러오지 못해 주소의 학원을 확인하지 못했습니다. 아래에서 다시 골라주세요.'
                    : '주소의 학원을 찾지 못했습니다. 아래에서 다시 골라주세요.',
              ),
              const SizedBox(height: AppSpace.md),
              _AcademyPicker(data: data.requireValue),
            ],
          );
        }
      }
    }

    return ListView(
      padding: const EdgeInsets.symmetric(vertical: AppSpace.lg),
      children: [
        ContentWidth(
          max: 760,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SectionOpener(
                '다녀 본 학원, 30초만 알려주세요',
                kicker: '학부모 제보',
                subtitle:
                    '고르기만 하면 됩니다. 적는 칸은 없고 로그인도 필요 없습니다. '
                    '제보는 어느 학원의 근거를 더 찾아볼지 정하는 데 쓰입니다.',
              ),
              body,
              const SizedBox(height: AppSpace.xl),
            ],
          ),
        ),
      ],
    );
  }
}

/// 안내 한 줄. 왼쪽에 획을 세운다 — 떠 있는 상자가 아니라 본문의 한 대목이다.
class _Notice extends StatelessWidget {
  final String text;
  final (String, VoidCallback)? action;
  const _Notice(this.text, {this.action});

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Semantics(
      liveRegion: true,
      child: DecoratedBox(
        decoration: BoxDecoration(
          border: Border(
            left: BorderSide(
              color: AppColors.accentOn(dark),
              width: AppRule.stroke,
            ),
          ),
        ),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 6, 0, 6),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(text, style: Theme.of(context).textTheme.bodyMedium),
              if (action != null)
                TextButton(onPressed: action!.$2, child: Text(action!.$1)),
            ],
          ),
        ),
      ),
    );
  }
}

/// 학원 고르기. 검색은 헤더 검색과 **같은 것**을 쓴다
/// (`EduTreeData.search` + `RegistryEntry.matchesQuery`).
class _AcademyPicker extends ConsumerStatefulWidget {
  final EduTreeData data;
  const _AcademyPicker({required this.data});

  @override
  ConsumerState<_AcademyPicker> createState() => _AcademyPickerState();
}

class _AcademyPickerState extends ConsumerState<_AcademyPicker> {
  static const _shown = 20;
  String _query = '';

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final q = _query.trim();
    // 등록부는 찾기 시작할 때 처음 읽는다(헤더 검색과 같다).
    final registry = q.isEmpty ? null : ref.watch(registryProvider);
    final hits = q.isEmpty
        ? const <SearchHit>[]
        : <SearchHit>[
            ...widget.data.search(q),
            for (final r in registry?.value ?? const <RegistryEntry>[])
              if (r.matchesQuery(q)) SearchHit.listed(r),
          ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('어느 학원인가요', style: text.titleMedium),
        const SizedBox(height: AppSpace.sm),
        ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
          child: TextField(
            key: const ValueKey('tell-academy-search'),
            autocorrect: false,
            decoration: const InputDecoration(
              labelText: '학원 이름으로 찾기',
              helperText: '찾는 말은 이 기기 안에서만 쓰이고 보내지 않습니다.',
            ),
            onChanged: (v) => setState(() => _query = v),
          ),
        ),
        const SizedBox(height: AppSpace.md),
        if (q.isNotEmpty && hits.isEmpty)
          Text(
            registry?.isLoading ?? false
                ? '등록부에서 찾는 중입니다…'
                : "'$q' 에 맞는 학원이 없습니다. 등록명이 다를 수 있습니다.",
            style: text.bodyMedium,
          ),
        if (hits.isNotEmpty) const Rule(),
        for (final hit in hits.take(_shown)) ...[
          InkWell(
            key: ValueKey('tell-pick-${hit.id}'),
            onTap: () =>
                context.go('/tell?academy=${Uri.encodeQueryComponent(hit.id)}'),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 11),
              child: SizedBox(
                width: double.infinity,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(hit.name, style: text.titleSmall),
                    Text(
                      [
                        widget.data.regionById[hit.regionId]?.nameKo,
                        orderedSubjects(
                          hit.subjects,
                        ).map((s) => subjectNames[s]!).join(', '),
                      ].where((s) => s != null && s.isNotEmpty).join(' · '),
                      style: text.bodySmall,
                    ),
                  ],
                ),
              ),
            ),
          ),
          const Rule(),
        ],
        if (hits.length > _shown)
          Padding(
            padding: const EdgeInsets.only(top: AppSpace.sm),
            child: Text(
              '${hits.length}곳 중 $_shown곳만 보입니다. 이름을 더 적어 좁혀주세요.',
              style: text.bodySmall,
            ),
          ),
      ],
    );
  }
}

/// 정해진 학원에 답을 고르는 폼. 접수되면 같은 자리가 접수 기록으로 바뀐다.
class ParentReportForm extends ConsumerStatefulWidget {
  final String academyId;
  final String academyName;
  const ParentReportForm({
    super.key,
    required this.academyId,
    required this.academyName,
  });

  /// 보내기 단추 위에 적는 동의 한 줄.
  static const consent =
      '답은 익명입니다. 이름·연락처는 받지 않고, 아이 학년은 학년대만 저장합니다. '
      '여러 학부모의 답을 합친 수로만 보여 주며 랭킹 점수는 바꾸지 않습니다.';

  static const unavailable =
      '지금은 제보를 받을 수 없습니다. 접수 서버가 연결되지 않아 보내도 저장되지 않으므로 보내기를 꺼 두었습니다.';

  @override
  ConsumerState<ParentReportForm> createState() => _ParentReportFormState();
}

class _ParentReportFormState extends ConsumerState<ParentReportForm> {
  String? _gradeBand, _relation, _subject, _levelTest, _homework;
  int? _sessions;
  bool _busy = false;
  String? _message;

  /// 서버가 받았다고 답한 답과 그 결과. 있으면 접수 기록을 보여 준다.
  (ParentReport, ReportOutcome)? _receipt;

  ParentReport get _report => ParentReport(
    academyId: widget.academyId,
    gradeBand: _gradeBand,
    relation: _relation,
    subject: _subject,
    levelTest: _levelTest,
    sessionsPerWeek: _sessions,
    homework: _homework,
  );

  Future<void> _submit(ParentReportService service) async {
    if (_busy) return;
    final report = _report;
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      final outcome = await service.submit(report);
      if (!mounted) return;
      setState(() {
        if (outcome == ReportOutcome.limited) {
          _message =
              '접수되지 않았습니다. 오늘 받을 수 있는 제보 수에 닿았습니다'
              '(한 기기에서 하루 다섯 학원까지). 내일 다시 보내주세요.';
        } else {
          _receipt = (report, outcome);
        }
      });
    } on ReportFailure catch (e) {
      if (mounted) setState(() => _message = e.message);
    } catch (_) {
      if (mounted) {
        setState(() => _message = '보내지 못했습니다. 저장되지 않았습니다. 다시 시도해주세요.');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final service = ref.watch(parentReportsProvider);
    final text = Theme.of(context).textTheme;
    final receipt = _receipt;
    if (receipt != null) return _receiptView(context, receipt.$1, receipt.$2);

    final missing = _report.missing;
    final canSend =
        service.enabled && !service.spent && !_busy && missing.isEmpty;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(widget.academyName, style: text.titleLarge),
        TextButton(
          onPressed: _busy ? null : () => context.go('/tell'),
          child: const Text('다른 학원 고르기'),
        ),
        const SizedBox(height: AppSpace.sm),
        if (!service.enabled) ...[
          const _Notice(ParentReportForm.unavailable),
          const SizedBox(height: AppSpace.md),
        ],
        const Rule(),
        _field(
          '아이 학년대',
          required: true,
          hint: '정확한 학년은 받지 않습니다.',
          child: _segments(
            'grade',
            reportGradeBands,
            _gradeBand,
            (v) => _gradeBand = v,
          ),
        ),
        _field(
          '이 학원과의 관계',
          required: true,
          child: _segments(
            'relation',
            reportRelations,
            _relation,
            (v) => _relation = v,
          ),
        ),
        _field(
          '과목',
          child: _segments(
            'subject',
            reportSubjects,
            _subject,
            (v) => _subject = v,
          ),
        ),
        _field(
          '레벨테스트',
          child: _segments(
            'leveltest',
            reportLevelTests,
            _levelTest,
            (v) => _levelTest = v,
          ),
        ),
        _field(
          '주당 수업 횟수',
          child: _segments(
            'sessions',
            [for (final n in reportSessions) (n, '$n회')],
            _sessions,
            (v) => _sessions = v,
          ),
        ),
        _field(
          '숙제량',
          child: _segments(
            'homework',
            reportHomework,
            _homework,
            (v) => _homework = v,
          ),
        ),
        const SizedBox(height: AppSpace.md),
        ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 620),
          child: Text(
            ParentReportForm.consent,
            key: const ValueKey('tell-consent'),
            style: text.bodySmall,
          ),
        ),
        const SizedBox(height: AppSpace.md),
        FilledButton(
          key: const ValueKey('tell-submit'),
          onPressed: canSend ? () => _submit(service) : null,
          child: Text(_busy ? '보내는 중…' : '익명으로 보내기'),
        ),
        if (service.enabled && missing.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: AppSpace.sm),
            child: Text(
              '${missing.join(' · ')} 항목을 고르면 보낼 수 있습니다.',
              style: text.bodySmall,
            ),
          ),
        if (service.enabled && service.spent)
          const Padding(
            padding: EdgeInsets.only(top: AppSpace.sm),
            child: _Notice(
              '이 브라우저는 저장소를 쓸 수 없어 한 번만 제보할 수 있습니다. 이미 한 번 접수했습니다.',
            ),
          ),
        if (_message != null)
          Padding(
            padding: const EdgeInsets.only(top: AppSpace.md),
            child: _Notice(_message!),
          ),
      ],
    );
  }

  Widget _field(
    String label, {
    required Widget child,
    bool required = false,
    String? hint,
  }) {
    final text = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.only(top: AppSpace.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('$label · ${required ? '필수' : '선택'}', style: text.labelLarge),
          if (hint != null) Text(hint, style: text.bodySmall),
          const SizedBox(height: 6),
          child,
        ],
      ),
    );
  }

  /// 한 줄짜리 고르기. 고른 칸을 다시 누르면 비운다 — 선택 항목을 잘못
  /// 눌렀을 때 되돌릴 길이 있어야 한다. 좁은 화면에서는 옆으로 민다
  /// (줄을 바꾸면 한 칸짜리 표가 깨진다).
  Widget _segments<T extends Object>(
    String name,
    List<(T, String)> options,
    T? selected,
    void Function(T?) assign,
  ) => SingleChildScrollView(
    scrollDirection: Axis.horizontal,
    child: IgnorePointer(
      ignoring: _busy,
      child: RuledSegments<T?>(
        key: ValueKey('tell-$name'),
        options: options,
        selected: selected,
        onChanged: (v) => setState(() {
          assign(v == selected ? null : v);
          _message = null;
        }),
      ),
    ),
  );

  Widget _receiptView(
    BuildContext context,
    ParentReport report,
    ReportOutcome outcome,
  ) {
    final text = Theme.of(context).textTheme;
    return Semantics(
      liveRegion: true,
      child: Column(
        key: const ValueKey('tell-receipt'),
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('접수했습니다', style: text.headlineSmall),
          const SizedBox(height: AppSpace.xs),
          Text(widget.academyName, style: text.titleMedium),
          const SizedBox(height: AppSpace.sm),
          Text(
            outcome == ReportOutcome.duplicate
                ? '이 기기에서 이 학원에 보낸 답이 이미 있어 새 답으로 바꿨습니다. 한 건으로 셉니다.'
                : '서버가 받았다고 확인했습니다. 한 기기의 답은 학원마다 한 건으로 셉니다.',
            style: text.bodyMedium,
          ),
          const SizedBox(height: AppSpace.md),
          const Rule(),
          for (final (label, value) in report.lines) ...[
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 9),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SizedBox(
                    width: 104,
                    child: Text(label, style: text.bodySmall),
                  ),
                  Expanded(child: Text(value, style: text.bodyMedium)),
                ],
              ),
            ),
            const Rule(),
          ],
          const SizedBox(height: AppSpace.md),
          ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 620),
            child: Text(
              '보낸 것은 위에 적힌 것이 전부입니다. 접수는 화면 반영과 다릅니다 — '
              '이 답으로 랭킹 점수가 바뀌지 않고, 어느 학원의 근거를 더 찾아볼지 정하는 데 쓰입니다.',
              style: text.bodySmall,
            ),
          ),
          const SizedBox(height: AppSpace.md),
          Wrap(
            spacing: 12,
            runSpacing: 8,
            children: [
              OutlinedButton(
                onPressed: () => context.go('/tell'),
                child: const Text('다른 학원 제보하기'),
              ),
              TextButton(
                onPressed: () => context.go('/academy/${widget.academyId}'),
                child: const Text('이 학원 보기'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
