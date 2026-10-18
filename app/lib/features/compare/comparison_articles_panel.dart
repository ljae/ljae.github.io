import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../core/theme.dart';
import '../../data/comparison_articles.dart';
import '../../data/contact_view_model.dart';
import '../../data/models.dart';
import '../../data/parent_comparison.dart';
import '../../widgets/contact.dart';

Future<void> openComparisonArticle(BuildContext context, String url) async {
  final uri = safeContactUrl(url);
  if (uri == null) return;
  try {
    if (await launchUrl(uri, mode: LaunchMode.externalApplication)) return;
  } catch (_) {
    // A blocked popup or unavailable browser still leaves a usable link.
  }
  if (context.mounted) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: const Text('글을 열지 못했어요. 링크를 복사해 브라우저에서 열어주세요.'),
        action: SnackBarAction(
          label: '링크 복사',
          onPressed: () => copyContactText(context, url),
        ),
      ),
    );
  }
}

class ComparisonArticlesPanel extends StatelessWidget {
  final List<ComparisonArticleMatch> matches;
  final Map<String, String> names;
  const ComparisonArticlesPanel({
    super.key,
    required this.matches,
    required this.names,
  });
  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('02  같은 글에서 두세 곳 함께 읽기', style: text.titleLarge),
        const SizedBox(height: 8),
        const Text(
          '학원별 설명이 있고 공통 항목을 비교할 수 있는 글을 골랐어요. 글쓴이의 경험·조사 시점과 우리 아이의 조건을 함께 보세요.',
        ),
        const SizedBox(height: 16),
        if (matches.isEmpty)
          const Text(
            '이 조합·과목·학년에 연결해 검토한 비교 글은 아직 없어요. 아래의 학원별 자료와 상담 질문을 활용해주세요.',
          ),
        for (final m in matches)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: _ArticleCard(
              key: ValueKey(m.article.id),
              match: m,
              names: names,
            ),
          ),
      ],
    );
  }
}

class _ArticleCard extends StatefulWidget {
  final ComparisonArticleMatch match;
  final Map<String, String> names;
  const _ArticleCard({super.key, required this.match, required this.names});
  @override
  State<_ArticleCard> createState() => _ArticleCardState();
}

class _ArticleCardState extends State<_ArticleCard> {
  bool expanded = false;
  @override
  Widget build(BuildContext context) {
    final m = widget.match, a = m.article;
    final text = Theme.of(context).textTheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final topics = comparisonCriteria.where(
      (c) => m.commonCriteria.contains(c.id),
    );
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.openingPaperOn(dark),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.ruleOn(dark)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            m.coverageLabel,
            style: text.labelLarge?.copyWith(color: AppColors.accentOn(dark)),
          ),
          const SizedBox(height: 8),
          Text(a.title, style: text.titleLarge),
          const SizedBox(height: 8),
          Text(
            '본문에서 다룬 대상: ${m.matched.map((t) => t.label).join(' · ')}',
            style: text.labelLarge,
          ),
          if (m.missingIds.isNotEmpty)
            Text(
              '이 글에서 비교하지 않은 곳: ${m.missingIds.map((id) => widget.names[id] ?? id).join(' · ')}',
              style: text.labelLarge,
            ),
          const SizedBox(height: 8),
          Text(a.reason),
          const SizedBox(height: 10),
          Text(
            '함께 읽을 항목  ${topics.map((c) => c.title).join(' / ')}',
            style: text.bodySmall,
          ),
          const SizedBox(height: 10),
          Text(
            '${a.author} · 글 작성 ${a.publishedAt} · ${subjectNames[a.subject]} · ${a.gradeLabel}',
            style: text.bodySmall,
          ),
          const SizedBox(height: 6),
          Text(
            '${m.needsBranchCheck ? '브랜드·지역 참고 · 선택 지점 확인 필요' : '글 속 주소 대조 · 현재 운영 확인 필요'}'
            '${a.isHistorical(DateTime.now()) ? '\n작성 후 2년이 지난 글 · 당시 경험과 운영을 읽는 자료입니다.' : ''}',
            style: text.labelMedium,
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 4,
            children: [
              TextButton.icon(
                onPressed: () => openComparisonArticle(context, a.url),
                icon: const Icon(Icons.open_in_new, size: 17),
                label: const Text('비교 글 원문 읽기'),
              ),
              TextButton(
                onPressed: () => setState(() => expanded = !expanded),
                child: Text(expanded ? '글의 범위·검토 정보 접기' : '글의 범위·검토 정보'),
              ),
            ],
          ),
          if (expanded) ...[
            const Divider(),
            Text(a.scopeNote),
            const SizedBox(height: 8),
            Text(a.experienceNote),
            const SizedBox(height: 8),
            Text(
              '본문·접근 확인 ${a.reviewedAt} · 학원의 현재 운영을 확인한 날짜가 아닙니다.',
              style: text.bodySmall,
            ),
            for (final t in m.matched)
              Text('읽을 부분: ${t.locator}', style: text.bodySmall),
            TextButton.icon(
              onPressed: () => copyContactText(context, a.url),
              icon: const Icon(Icons.copy_outlined, size: 16),
              label: const Text('비교 글 링크 복사'),
            ),
          ],
        ],
      ),
    );
  }
}

/// Link context is retained: an article never becomes a current branch fact.
class CriterionArticleLinks extends StatelessWidget {
  final String criterionId;
  final List<ComparisonArticleMatch> matches;
  const CriterionArticleLinks({
    super.key,
    required this.criterionId,
    required this.matches,
  });
  @override
  Widget build(BuildContext context) => Wrap(
    spacing: 8,
    runSpacing: 4,
    children: [
      for (final m in matches.where(
        (m) => m.commonCriteria.contains(criterionId),
      ))
        TextButton.icon(
          onPressed: () => openComparisonArticle(context, m.article.url),
          icon: const Icon(Icons.open_in_new, size: 15),
          label: Text(
            '비교 글 · ${m.matched.map((t) => t.label).join('·')} (${m.article.publishedAt.substring(0, 4)})',
          ),
        ),
    ],
  );
}
