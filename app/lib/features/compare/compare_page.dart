import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/env.dart';
import '../../core/theme.dart';
import '../../data/models.dart';
import '../../data/parent_comparison.dart';
import '../../data/comparison_articles.dart';
import '../../data/academy_detail.dart';
import '../../data/contact_view_model.dart';
import '../../data/parent_decision.dart';
import '../../data/repository.dart';
import '../../data/source_notes.dart';
import '../../widgets/common.dart';
import '../../widgets/subject_bar.dart';
import '../../widgets/contact.dart';
import '../academy/contact.dart';
import '../feedback/parent_voice_page.dart';
import 'comparison_articles_panel.dart';

class CompareButton extends ConsumerWidget {
  final String academyId;
  const CompareButton({super.key, required this.academyId});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (!Env.parentCompareEnabled) return const SizedBox.shrink();
    final ids = ref.watch(compareProvider);
    return Wrap(
      spacing: 8,
      runSpacing: 4,
      children: [
        OutlinedButton.icon(
          onPressed: () {
            if (!ref.read(compareProvider.notifier).toggle(academyId)) {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('비교는 최대 세 곳까지 담을 수 있어요.')),
              );
            }
          },
          icon: Icon(ids.contains(academyId) ? Icons.check : Icons.add),
          label: Text(ids.contains(academyId) ? '비교에서 빼기' : '비교 담기'),
        ),
        if (ids.isNotEmpty)
          TextButton(
            onPressed: () => context.go('/compare?ids=${ids.join(',')}'),
            child: Text('비교 노트 ${ids.length}곳 →'),
          ),
      ],
    );
  }
}

class ComparePage extends ConsumerStatefulWidget {
  final String? ids;
  const ComparePage({super.key, this.ids});
  @override
  ConsumerState<ComparePage> createState() => _ComparePageState();
}

class _ComparePageState extends ConsumerState<ComparePage> {
  @override
  void initState() {
    super.initState();
    _restore();
  }

  @override
  void didUpdateWidget(covariant ComparePage old) {
    super.didUpdateWidget(old);
    if (old.ids != widget.ids) _restore();
  }

  void _restore() {
    if (widget.ids != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          ref
              .read(compareProvider.notifier)
              .restore(parseCompareIds(widget.ids));
        }
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!Env.parentCompareEnabled) {
      return const Center(child: Text('비교 기능을 준비 중입니다.'));
    }
    final ids = ref.watch(compareProvider);
    final concern = ref.watch(parentConcernProvider);
    final selection = ref.watch(selectionProvider);
    final subject = selection.subject, band = selection.gradeBand;
    final details = [
      for (final id in ids) ref.watch(academyDetailProvider(id)),
    ];
    // An old registration alias and its current ID are one candidate.
    final values = <String, AcademyDetail>{
      for (final d in details.map((d) => d.value).whereType<AcademyDetail>())
        d.id: d,
    }.values.toList();
    final criteria = orderedComparisonCriteria(concern);
    final articles = ref.watch(comparisonArticlesProvider);
    final articleMatches = matchComparisonArticles(
      articles.value ?? [],
      values.map((d) => d.id),
      subject: subject,
      gradeBand: band,
    );
    final sourceNotes = ref.watch(sourceNotesProvider);
    final groups = {
      for (final g in sourceNotes.value ?? <AcademySources>[]) g.academyId: g,
    };
    final guidance = {
      for (final c in criteria)
        c.id: {
          for (final d in values)
            d.id: comparisonGuidance(d, c, subject, groups[d.id]),
        },
    };
    final excerpts = {
      for (final c in criteria)
        c.id: {
          for (final d in values)
            d.id: comparisonExcerpts(d, c, subject: subject, gradeBand: band),
        },
    };
    final readable = criteria
        .where(
          (c) =>
              excerpts[c.id]!.values.any((v) => v.isNotEmpty) ||
              guidance[c.id]!.values.any((v) => v.isNotEmpty),
        )
        .toList();
    final unknown = criteria.where((c) => !readable.contains(c)).toList();
    final firstQuestion = concern != null && unknown.contains(criteria.first)
        ? criteria.first
        : null;
    final text = Theme.of(context).textTheme;
    return ListView(
      padding: const EdgeInsets.symmetric(vertical: 32),
      children: [
        ContentWidth(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('우리 아이에게 중요한 차이부터.', style: text.headlineLarge),
              const SizedBox(height: 12),
              const Text(
                '두세 곳을 함께 다룬 글을 읽고, 진도·숙제·피드백부터 실제 통학까지 비교해보세요. 각 항목에서 무엇을 확인해야 할지 짚어드려요.',
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 4,
                children: [
                  TextButton(
                    onPressed: () => context.go('/rank'),
                    child: const Text('학원 더 찾아보기'),
                  ),
                  if (ids.isNotEmpty)
                    TextButton(
                      onPressed: () {
                        ref.read(compareProvider.notifier).clear();
                        context.go('/compare');
                      },
                      child: const Text('비교 초기화'),
                    ),
                  if (ids.isNotEmpty)
                    TextButton(
                      onPressed: () => copyContactText(
                        context,
                        Uri.base
                            .replace(
                              query: '',
                              fragment: '/compare?ids=${ids.join(',')}',
                            )
                            .toString(),
                        success: '학원 목록 링크를 복사했습니다. 비교 관점은 받는 분이 선택할 수 있어요.',
                      ),
                      child: const Text('학원 목록 링크 복사'),
                    ),
                ],
              ),
              if (ids.isEmpty)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 32),
                  child: Text('학원 목록이나 상세에서 비교할 학원을 최대 세 곳까지 담아주세요.'),
                )
              else ...[
                const SizedBox(height: 16),
                _Note(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('01  비교할 수업과 관심사', style: text.titleMedium),
                      const SizedBox(height: 12),
                      SubjectBar(
                        selected: subject,
                        onChanged: (s) {
                          if (s != null) {
                            ref.read(selectionProvider.notifier).setSubject(s);
                          }
                        },
                      ),
                      const SizedBox(height: 12),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          for (final entry in gradeBandNames.entries)
                            ChoiceChip(
                              label: Text(entry.value),
                              selected: band == entry.key,
                              onSelected: (_) => ref
                                  .read(selectionProvider.notifier)
                                  .setGradeBand(entry.key),
                            ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      const Text('먼저 살펴보고 싶은 것'),
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          for (final entry in const {
                            'foundation': '기초·진도',
                            'homework': '숙제 부담',
                            'questions': '질문·피드백',
                          }.entries)
                            ChoiceChip(
                              label: Text(entry.value),
                              selected: concern == entry.key,
                              onSelected: (on) => ref
                                  .read(parentConcernProvider.notifier)
                                  .choose(on ? entry.key : null),
                            ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Text(
                        concernQuestions[concern] ??
                            '같은 과목·학년의 내용을 먼저 읽고, 학년이 밝혀지지 않은 글은 맥락을 확인하세요.',
                        style: text.bodyMedium,
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 24),
                for (var i = 0; i < details.length; i++)
                  details[i].when(
                    loading: () => Padding(
                      padding: const EdgeInsets.all(12),
                      child: Semantics(
                        label: '학원 ${ids[i]} 정보 불러오는 중',
                        child: const LinearProgressIndicator(),
                      ),
                    ),
                    error: (_, _) => TextButton(
                      onPressed: () =>
                          ref.invalidate(academyDetailProvider(ids[i])),
                      child: Text('학원 ${ids[i]} 정보를 다시 불러오기'),
                    ),
                    data: (d) => d == null
                        ? Text('학원 ID ${ids[i]}의 공개 정보를 찾지 못했습니다.')
                        : const SizedBox.shrink(),
                  ),
                if (values.isNotEmpty) ...[
                  if (values.length == 1)
                    const Padding(
                      padding: EdgeInsets.only(bottom: 16),
                      child: Text(
                        '현재 한 곳을 살펴보고 있어요. 한 곳 더 담으면 같은 항목을 나란히 볼 수 있어요.',
                      ),
                    ),
                  _CriterionSection(
                    title: '이 과목·학년의 반이 있나요?',
                    meaning:
                        '대상 학년 자료가 있어야 상담할 반을 좁힐 수 있어요. 자료가 없는 경우에는 현재 모집 여부부터 물어보세요.',
                    candidates: values,
                    cell: (d) {
                      final target = comparisonTarget(d, subject, band);
                      return Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(target.label, style: text.titleSmall),
                          const SizedBox(height: 8),
                          Text(target.explanation),
                          TextButton(
                            onPressed: () {
                              final keep = [
                                for (var i = 0; i < ids.length; i++)
                                  if (details[i].value?.id != d.id) ids[i],
                              ];
                              ref.read(compareProvider.notifier).restore(keep);
                              context.go('/compare?ids=${keep.join(',')}');
                            },
                            child: const Text('비교에서 빼기'),
                          ),
                        ],
                      );
                    },
                  ),
                  const SizedBox(height: 28),
                  if (values.length >= 2) ...[
                    articles.when(
                      loading: () => const Text('함께 비교한 글을 불러오는 중이에요.'),
                      error: (_, _) => TextButton(
                        onPressed: () =>
                            ref.invalidate(comparisonArticlesProvider),
                        child: const Text('비교 글을 불러오지 못했어요 · 다시 시도'),
                      ),
                      data: (_) => ComparisonArticlesPanel(
                        matches: articleMatches,
                        names: {for (final d in values) d.id: detailName(d)},
                      ),
                    ),
                    const SizedBox(height: 28),
                  ],
                  Text('03  선택을 바꾸는 항목별 비교', style: text.titleLarge),
                  const SizedBox(height: 8),
                  const Text(
                    '공식 안내와 공개 글의 경험을 구별해 읽으세요. 선택한 반에 적용되는지와 현재 운영은 직접 확인해야 합니다. 자료가 적다는 이유로 학원을 낮게 평가하지 않습니다.',
                  ),
                  if (sourceNotes.isLoading)
                    const Padding(
                      padding: EdgeInsets.all(12),
                      child: Text('공식 안내를 불러오는 중이에요.'),
                    ),
                  if (sourceNotes.hasError)
                    TextButton(
                      onPressed: () => ref.invalidate(sourceNotesProvider),
                      child: const Text('공식 안내를 불러오지 못했어요 · 다시 시도'),
                    ),
                  if (firstQuestion != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 20),
                      child: _Note(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(firstQuestion.title, style: text.titleLarge),
                            const SizedBox(height: 8),
                            Text(firstQuestion.meaning),
                            const SizedBox(height: 12),
                            Text(
                              '확인할 내용  ${firstQuestion.checkpoints.join(' / ')}',
                              style: text.labelLarge,
                            ),
                            CriterionArticleLinks(
                              criterionId: firstQuestion.id,
                              matches: articleMatches,
                            ),
                            const SizedBox(height: 8),
                            const Text(
                              '먼저 살펴볼 항목이지만, 선택한 반의 학원별 자료는 아직 부족해요. 같은 질문으로 상담해 비교해보세요.',
                            ),
                            const SizedBox(height: 8),
                            Text('물어볼 질문  ${firstQuestion.question}'),
                          ],
                        ),
                      ),
                    ),
                  for (final c in readable)
                    Padding(
                      padding: const EdgeInsets.only(top: 20),
                      child: _CriterionSection(
                        title: c.title,
                        meaning: c.meaning,
                        readingAid: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              '확인할 내용  ${c.checkpoints.join(' / ')}',
                              style: text.labelLarge,
                            ),
                            CriterionArticleLinks(
                              criterionId: c.id,
                              matches: articleMatches,
                            ),
                          ],
                        ),
                        candidates: values,
                        cell: (d) => _EvidenceCell(
                          key: ValueKey('${d.id}/${c.id}/$subject/$band'),
                          rows: excerpts[c.id]![d.id]!,
                          guidance: guidance[c.id]![d.id]!,
                          caveat: groups[d.id]?.caveat,
                          question: comparisonQuestion(
                            c,
                            excerpts[c.id]![d.id]!,
                            subject,
                            band,
                            hasGuidance: guidance[c.id]![d.id]!.isNotEmpty,
                          ),
                        ),
                      ),
                    ),
                  if (unknown.any((c) => c != firstQuestion))
                    Padding(
                      padding: const EdgeInsets.only(top: 20),
                      child: _Note(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              readable.isEmpty
                                  ? '이 조건에서는 수업의 차이를 판단할 자료가 부족해요.'
                                  : '공통으로 상담에서 확인할 항목',
                              style: text.titleMedium,
                            ),
                            const SizedBox(height: 8),
                            const Text(
                              '선택한 과목·학년에 연결할 자료가 없는 항목은 한곳에 모았어요. 아래 질문의 답을 받으면 비교할 수 있습니다.',
                            ),
                            for (final c in unknown.where(
                              (c) => c != firstQuestion,
                            ))
                              Padding(
                                padding: const EdgeInsets.only(top: 16),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(c.title, style: text.titleSmall),
                                    const SizedBox(height: 4),
                                    Text(c.meaning),
                                    const SizedBox(height: 8),
                                    Text(
                                      '확인할 내용  ${c.checkpoints.join(' / ')}',
                                      style: text.labelLarge,
                                    ),
                                    CriterionArticleLinks(
                                      criterionId: c.id,
                                      matches: articleMatches,
                                    ),
                                    const SizedBox(height: 8),
                                    Text('물어볼 질문  ${c.question}'),
                                  ],
                                ),
                              ),
                          ],
                        ),
                      ),
                    ),
                  const SizedBox(height: 20),
                  _CriterionSection(
                    title: '지점과 위치',
                    meaning:
                        '하교 후 이동 경로와 수업 종료 뒤 귀가 방법을 함께 보세요. 주소만으로 통학 시간이나 셔틀 운행을 판단할 수는 없어요.',
                    candidates: values,
                    cell: (d) => Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        SelectableText(
                          d.academy?.address ?? d.registry?.address ?? '주소 미확인',
                        ),
                        const SizedBox(height: 12),
                        const Text('물어볼 질문  수업 종료 시각과 셔틀 정류장·운행 시간을 알려주세요.'),
                      ],
                    ),
                  ),
                  const SizedBox(height: 28),
                  _CriterionSection(
                    title: '04  이 학원에 물어보기',
                    meaning:
                        '읽은 내용이 현재 반에도 해당하는지 확인하세요. 질문을 복사한 뒤 해당 지점에 직접 문의할 수 있어요.',
                    candidates: values,
                    cell: (d) {
                      final questions = [
                        '${gradeBandNames[band]} ${subjectNames[subject]} 반을 현재 모집하나요?',
                        for (final c in criteria)
                          [
                            if (guidance[c.id]![d.id]!.firstOrNull
                                case final n?)
                              '공식 안내 요약 (선택 학년 적용 미확인): ${n.summary}\n자료 대조: ${n.checkedAt}\n원문: ${n.url}',
                            if (excerpts[c.id]![d.id]!.firstOrNull
                                case final e?)
                              '읽은 내용: “${e.text}”\n원문: ${e.url}',
                            comparisonQuestion(
                              c,
                              excerpts[c.id]![d.id]!,
                              subject,
                              band,
                              hasGuidance: guidance[c.id]![d.id]!.isNotEmpty,
                            ),
                          ].join('\n'),
                        '시간표, 귀가 방법, 수강료 외 교재·테스트 비용과 납부 조건을 알려주세요.',
                        for (final m in articleMatches.where(
                          (m) => m.matched.any((t) => t.academyId == d.id),
                        ))
                          '함께 읽은 비교 글: ${m.article.title}\n작성: ${m.article.publishedAt} · ${m.article.gradeLabel}\n${m.article.scopeNote}\n원문: ${m.article.url}\n이 글에서 다룬 내용 중 현재 문의하는 반과 다른 점을 알려주세요.',
                      ];
                      return Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          FilledButton.icon(
                            onPressed: () => copyContactText(
                              context,
                              '${detailName(d)} 문의 질문\n\n${questions.join('\n\n')}',
                              success: '이 학원의 자료와 질문을 함께 복사했습니다.',
                            ),
                            icon: const Icon(Icons.copy_outlined),
                            label: const Text('이 학원 질문 복사'),
                          ),
                          const SizedBox(height: 12),
                          ContactCard(contact: ContactViewModel.fromDetail(d)),
                        ],
                      );
                    },
                  ),
                ],
              ],
              const SizedBox(height: 28),
              const VoiceInvite(pageType: 'compare'),
              const SizedBox(height: 32),
            ],
          ),
        ),
      ],
    );
  }
}

class _Note extends StatelessWidget {
  final Widget child;
  const _Note({required this.child});
  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.openingPaperOn(dark),
        border: Border.all(color: AppColors.ruleOn(dark)),
        borderRadius: BorderRadius.circular(12),
      ),
      child: child,
    );
  }
}

/// One criterion, one explanation, aligned candidates. On narrow screens the
/// candidate names repeat so each quotation remains attributable while scrolling.
class _CriterionSection extends StatelessWidget {
  final String title, meaning;
  final List<AcademyDetail> candidates;
  final Widget Function(AcademyDetail) cell;
  final Widget? readingAid;
  const _CriterionSection({
    required this.title,
    required this.meaning,
    required this.candidates,
    required this.cell,
    this.readingAid,
  });
  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final text = Theme.of(context).textTheme;
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surfaceOn(dark),
        border: Border.all(color: AppColors.ruleOn(dark)),
        borderRadius: BorderRadius.circular(12),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: double.infinity,
            color: AppColors.openingCanvasOn(dark),
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: text.titleLarge),
                const SizedBox(height: 8),
                Text(meaning),
                if (readingAid != null) ...[
                  const SizedBox(height: 12),
                  readingAid!,
                ],
              ],
            ),
          ),
          LayoutBuilder(
            builder: (context, constraints) {
              final scale = MediaQuery.textScalerOf(context).scale(14) / 14;
              final cols =
                  constraints.maxWidth / scale < candidates.length * 290
                  ? 1
                  : candidates.length;
              return Wrap(
                children: [
                  for (final d in candidates)
                    SizedBox(
                      width: constraints.maxWidth / cols,
                      child: Container(
                        padding: const EdgeInsets.all(20),
                        decoration: BoxDecoration(
                          border: Border(
                            top: BorderSide(color: AppColors.ruleOn(dark)),
                          ),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            TextButton(
                              style: TextButton.styleFrom(
                                padding: EdgeInsets.zero,
                                alignment: Alignment.centerLeft,
                              ),
                              onPressed: () => context.go('/academy/${d.id}'),
                              child: Text(
                                detailName(d),
                                style: text.titleMedium?.copyWith(
                                  color: AppColors.accentOn(dark),
                                ),
                              ),
                            ),
                            const SizedBox(height: 8),
                            cell(d),
                          ],
                        ),
                      ),
                    ),
                ],
              );
            },
          ),
        ],
      ),
    );
  }
}

class _EvidenceCell extends StatefulWidget {
  final List<ComparisonExcerpt> rows;
  final List<SourceNote> guidance;
  final String? caveat;
  final String question;
  const _EvidenceCell({
    super.key,
    required this.rows,
    required this.guidance,
    this.caveat,
    required this.question,
  });
  @override
  State<_EvidenceCell> createState() => _EvidenceCellState();
}

class _EvidenceCellState extends State<_EvidenceCell> {
  bool expanded = false;
  bool showGuidance = false;
  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (widget.rows.isEmpty && widget.guidance.isEmpty) ...[
          Text('이 항목의 자료가 아직 없어요', style: text.titleSmall),
          const SizedBox(height: 6),
          const Text('선택한 과목·학년의 수업이 어떤지 현재 자료로 판단하기 어렵습니다.'),
        ],
        for (final n
            in showGuidance ? widget.guidance : widget.guidance.take(1))
          Padding(
            padding: const EdgeInsets.only(bottom: 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${n.sourceLabel} 요약',
                  style: text.labelLarge?.copyWith(
                    color: AppColors.accentOn(dark),
                  ),
                ),
                const SizedBox(height: 8),
                Text(n.summary, style: text.bodyLarge?.copyWith(height: 1.65)),
                const SizedBox(height: 8),
                Text('선택 학년·반에 적용되는지 확인 필요', style: text.labelMedium),
                Text(
                  '자료 대조 ${n.checkedAt} · 현재 운영 확인 필요',
                  style: text.bodySmall,
                ),
                TextButton.icon(
                  onPressed: () => openExternal(n.url),
                  icon: const Icon(Icons.open_in_new, size: 16),
                  label: const Text('공식 안내 원문'),
                ),
              ],
            ),
          ),
        if (widget.guidance.length > 1)
          TextButton(
            onPressed: () => setState(() => showGuidance = !showGuidance),
            child: Text(
              showGuidance
                  ? '추가 안내 접기'
                  : '추가 공식 안내 ${widget.guidance.length - 1}건',
            ),
          ),
        if (widget.guidance.isNotEmpty && (widget.caveat?.isNotEmpty ?? false))
          Padding(
            padding: const EdgeInsets.only(bottom: 16),
            child: Text(widget.caveat!, style: text.bodySmall),
          ),
        for (final e in expanded ? widget.rows : widget.rows.take(1))
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  e.selfDescription ? '학원 자기 서술의 발췌' : '공개 글의 발췌 · 작성자 성격 미확인',
                  style: text.labelMedium,
                ),
                const SizedBox(height: 8),
                Text(
                  '“${e.text}”',
                  style: text.bodyLarge?.copyWith(height: 1.65),
                ),
                const SizedBox(height: 10),
                Text(e.scope, style: text.labelMedium),
                const SizedBox(height: 4),
                Text(e.dateLabel, style: text.bodySmall),
                TextButton.icon(
                  onPressed: () => openExternal(e.url),
                  icon: const Icon(Icons.open_in_new, size: 16),
                  label: Text('${e.source} 원문'),
                ),
              ],
            ),
          ),
        if (widget.rows.length > 1)
          TextButton(
            onPressed: () => setState(() => expanded = !expanded),
            child: Text(
              expanded ? '다른 글 접기' : '다른 글 ${widget.rows.length - 1}건도 읽기',
            ),
          ),
        const SizedBox(height: 8),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(14),
          color: AppColors.openingCanvasOn(dark),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '이 학원에 확인할 것',
                style: text.labelLarge?.copyWith(
                  color: AppColors.accentOn(dark),
                ),
              ),
              const SizedBox(height: 6),
              Text(widget.question),
            ],
          ),
        ),
      ],
    );
  }
}
