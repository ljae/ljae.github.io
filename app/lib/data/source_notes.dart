import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Editorial source notes are separate from nightly scores and AI profiles.
class SourceNote {
  final String topic, title, summary, url, checkedAt;
  final String? publishedAt;
  final String? shortSummary;
  final String kind;
  final String sourceScope;
  final List<String> subjects;
  const SourceNote({
    required this.topic,
    required this.title,
    required this.summary,
    required this.url,
    required this.checkedAt,
    this.publishedAt,
    this.shortSummary,
    this.kind = 'official',
    this.sourceScope = 'branch',
    this.subjects = const [],
  });

  factory SourceNote.fromJson(Map<String, dynamic> j) => SourceNote(
    topic: j['topic'] as String,
    title: j['title'] as String,
    summary: j['summary'] as String,
    url: j['url'] as String,
    checkedAt: j['checkedAt'] as String,
    publishedAt: j['publishedAt'] as String?,
    shortSummary: j['shortSummary'] as String?,
    kind: (j['kind'] ?? 'official') as String,
    sourceScope: (j['sourceScope'] ?? 'branch') as String,
    subjects: ((j['subjects'] as List?) ?? const []).cast<String>(),
  );

  bool supports(String? subject) =>
      subject == null ||
      subjects.contains(subject) ||
      (kind == 'directory' && topic == '운영·일정');
  bool get isPrimary => kind == 'official' || kind == 'academy_blog';
  String get sourceLabel => kind == 'directory'
      ? '학원 소개 · 주소 대조'
      : kind == 'media'
      ? '언론 보도'
      : kind == 'review_aggregator'
      ? '공개 후기 집계'
      : sourceScope == 'brand'
      ? '브랜드 공통 안내'
      : sourceScope == 'admission'
      ? '공식 입학 안내'
      : kind == 'academy_blog'
      ? '학원 게시글'
      : '공식 안내';
}

class AcademySources {
  final String academyId, name, scope, caveat;
  final List<SourceNote> notes;
  const AcademySources({
    required this.academyId,
    required this.name,
    required this.scope,
    required this.caveat,
    required this.notes,
  });

  factory AcademySources.fromJson(Map<String, dynamic> j) => AcademySources(
    academyId: j['academyId'] as String,
    name: j['name'] as String,
    scope: j['scope'] as String,
    caveat: j['caveat'] as String,
    notes: (j['notes'] as List)
        .map((n) => SourceNote.fromJson(Map<String, dynamic>.from(n as Map)))
        .toList(),
  );

  SourceNote? compactNote(String topic, {String? subject}) => notes
      .where(
        (n) =>
            n.topic == topic &&
            n.isPrimary &&
            n.supports(subject) &&
            (n.shortSummary?.trim().isNotEmpty ?? false),
      )
      .firstOrNull;
}

Future<String> _loadTextAsset(String path) async {
  // loadString switches to compute() above 50 KB. Decoding here keeps the
  // asset loader deterministic in tests and avoids a needless isolate hop.
  final data = await rootBundle.load(path);
  return utf8.decode(
    data.buffer.asUint8List(data.offsetInBytes, data.lengthInBytes),
  );
}

final sourceNotesProvider = FutureProvider<List<AcademySources>>((ref) async {
  final raw = await _loadTextAsset('assets/research/source_notes.json');
  final directory = await _loadTextAsset('assets/data/directory_sources.json');
  final grades = await _loadTextAsset('assets/data/grade_sources.json');
  final groups =
      [
            ...jsonDecode(raw) as List,
            ...jsonDecode(directory) as List,
            ...jsonDecode(grades) as List,
          ]
          .map(
            (j) => AcademySources.fromJson(Map<String, dynamic>.from(j as Map)),
          )
          .toList();
  final merged = <String, AcademySources>{};
  for (final group in groups) {
    final previous = merged[group.academyId];
    merged[group.academyId] = previous == null
        ? group
        : AcademySources(
            academyId: group.academyId,
            name: previous.name,
            scope: previous.scope,
            caveat: '${previous.caveat}\n${group.caveat}',
            notes: [...previous.notes, ...group.notes],
          );
  }
  return merged.values.toList();
});
