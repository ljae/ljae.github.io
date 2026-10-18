import 'dart:convert';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'contact_view_model.dart';
import 'models.dart';
import 'parent_comparison.dart';

/// Editorial reading links, kept outside academy scores and factual profiles.
/// Coverage means the body discusses an axis, not that its claims are verified.
class ArticleAcademy {
  final String academyId, label, mapping, locator;
  final Set<String> criteria;
  const ArticleAcademy({
    required this.academyId,
    required this.label,
    required this.mapping,
    required this.locator,
    required this.criteria,
  });
  factory ArticleAcademy.fromJson(Map<String, dynamic> j) => ArticleAcademy(
    academyId: j['academyId'] as String,
    label: j['label'] as String,
    mapping: j['mapping'] as String,
    locator: j['locator'] as String,
    criteria: (j['criteria'] as List).cast<String>().toSet(),
  );
}

class ComparisonArticle {
  final String id, title, url, author, publishedAt, reviewedAt, subject;
  final String status, access, reviewMethod, reason, scopeNote, experienceNote;
  final Set<String> gradeBands;
  final List<ArticleAcademy> academies;
  const ComparisonArticle({
    required this.id,
    required this.title,
    required this.url,
    required this.author,
    required this.publishedAt,
    required this.reviewedAt,
    required this.subject,
    required this.status,
    required this.access,
    required this.reviewMethod,
    required this.reason,
    required this.scopeNote,
    required this.experienceNote,
    required this.gradeBands,
    required this.academies,
  });
  factory ComparisonArticle.fromJson(Map<String, dynamic> j) =>
      ComparisonArticle(
        id: j['id'] as String,
        title: j['title'] as String,
        url: j['url'] as String,
        author: j['author'] as String,
        publishedAt: j['publishedAt'] as String,
        reviewedAt: j['reviewedAt'] as String,
        subject: j['subject'] as String,
        status: j['status'] as String,
        access: j['access'] as String,
        reviewMethod: j['reviewMethod'] as String,
        reason: j['reason'] as String,
        scopeNote: j['scopeNote'] as String,
        experienceNote: j['experienceNote'] as String,
        gradeBands: (j['gradeBands'] as List).cast<String>().toSet(),
        academies: (j['academies'] as List)
            .map(
              (v) =>
                  ArticleAcademy.fromJson(Map<String, dynamic>.from(v as Map)),
            )
            .toList(),
      );
  bool get isReviewed =>
      status == 'reviewed' &&
      access == 'public' &&
      reviewMethod == 'full_text' &&
      safeContactUrl(url) != null &&
      _validDate(publishedAt) &&
      _validDate(reviewedAt) &&
      reason.isNotEmpty &&
      scopeNote.isNotEmpty &&
      experienceNote.isNotEmpty;
  String get gradeLabel => gradeBands.isEmpty
      ? '학년 미확인'
      : gradeBands.map((b) => gradeBandNames[b] ?? b).join(' · ');
  bool isHistorical(DateTime now) =>
      now.difference(DateTime.parse(publishedAt)).inDays > 730;
}

bool _validDate(String v) =>
    RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(v) &&
    (DateTime.tryParse(v)?.toIso8601String().startsWith(v) ?? false);

/// Dedupe mobile/tracking variants without discarding meaningful query IDs.
String? comparisonArticleKey(String raw) {
  final uri = safeContactUrl(raw);
  if (uri == null) return null;
  var host = uri.host.toLowerCase(), path = uri.path;
  final params = Map<String, String>.from(uri.queryParameters)
    ..removeWhere((k, _) => k.startsWith('utm_') || k == 'fbclid');
  if (host == 'm.blog.naver.com') host = 'blog.naver.com';
  if (host == 'blog.naver.com' &&
      params.containsKey('blogId') &&
      params.containsKey('logNo')) {
    path = '/${params['blogId']}/${params['logNo']}';
    params.clear();
  }
  if (host.endsWith('.tistory.com')) {
    path = path.replaceFirst(RegExp(r'^/m/'), '/');
  }
  final keys = params.keys.toList()..sort();
  return Uri(
    scheme: 'https',
    host: host,
    port: uri.hasPort ? uri.port : null,
    path: path,
    queryParameters: keys.isEmpty ? null : {for (final k in keys) k: params[k]},
  ).toString();
}

class ComparisonArticleMatch {
  final ComparisonArticle article;
  final List<ArticleAcademy> matched;
  final List<String> missingIds;
  final Set<String> commonCriteria;
  final int selectedCount;
  const ComparisonArticleMatch({
    required this.article,
    required this.matched,
    required this.missingIds,
    required this.commonCriteria,
    required this.selectedCount,
  });
  String get coverageLabel => '선택한 $selectedCount곳 중 ${matched.length}곳을 다룬 글';
  bool get needsBranchCheck => matched.any((a) => a.mapping != 'address');
}

List<ComparisonArticleMatch> matchComparisonArticles(
  List<ComparisonArticle> articles,
  Iterable<String> selectedIds, {
  required String subject,
  required String gradeBand,
}) {
  final ids = selectedIds.toSet();
  if (ids.length < 2 || ids.length > 3) return const [];
  final axes = comparisonCriteria.map((c) => c.id).toSet();
  final results = <ComparisonArticleMatch>[];
  for (final a in articles) {
    if (!a.isReviewed ||
        a.subject != subject ||
        (a.gradeBands.isNotEmpty && !a.gradeBands.contains(gradeBand))) {
      continue;
    }
    final targets = <String, ArticleAcademy>{};
    for (final t in a.academies) {
      if (ids.contains(t.academyId) &&
          const {'address', 'regional_brand', 'brand'}.contains(t.mapping) &&
          t.locator.isNotEmpty &&
          t.criteria.intersection(axes).length >= 2) {
        targets[t.academyId] = t;
      }
    }
    if (targets.length < 2) continue;
    // Every displayed candidate has substantive coverage on shared axes.
    final common = targets.values
        .map((t) => t.criteria.intersection(axes))
        .reduce((a, b) => a.intersection(b));
    if (common.length < 2) continue;
    results.add(
      ComparisonArticleMatch(
        article: a,
        matched: targets.values.toList(),
        selectedCount: ids.length,
        missingIds: ids.difference(targets.keys.toSet()).toList(),
        commonCriteria: common,
      ),
    );
  }
  results.sort((a, b) {
    var c = b.matched.length.compareTo(a.matched.length);
    if (c != 0) return c;
    c = a.needsBranchCheck.toString().compareTo(b.needsBranchCheck.toString());
    if (c != 0) return c;
    c = b.commonCriteria.length.compareTo(a.commonCriteria.length);
    if (c != 0) return c;
    c = b.article.publishedAt.compareTo(a.article.publishedAt);
    return c != 0 ? c : a.article.id.compareTo(b.article.id);
  });
  final seen = <String>{};
  return results
      .where((r) => seen.add(comparisonArticleKey(r.article.url)!))
      .toList();
}

final comparisonArticlesProvider = FutureProvider<List<ComparisonArticle>>((
  ref,
) async {
  final raw = await rootBundle.loadString(
    'assets/research/comparison_articles.json',
  );
  return (jsonDecode(raw) as List)
      .map(
        (j) => ComparisonArticle.fromJson(Map<String, dynamic>.from(j as Map)),
      )
      .toList();
});
