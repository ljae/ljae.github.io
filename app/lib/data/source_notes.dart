import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Editorial source notes are separate from nightly scores and AI profiles.
class SourceNote {
  final String topic, title, summary, url, checkedAt;
  final String? publishedAt;
  const SourceNote({
    required this.topic,
    required this.title,
    required this.summary,
    required this.url,
    required this.checkedAt,
    this.publishedAt,
  });

  factory SourceNote.fromJson(Map<String, dynamic> j) => SourceNote(
    topic: j['topic'] as String,
    title: j['title'] as String,
    summary: j['summary'] as String,
    url: j['url'] as String,
    checkedAt: j['checkedAt'] as String,
    publishedAt: j['publishedAt'] as String?,
  );
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
}

final sourceNotesProvider = FutureProvider<List<AcademySources>>((ref) async {
  final raw = await rootBundle.loadString('assets/research/source_notes.json');
  return (jsonDecode(raw) as List)
      .map((j) => AcademySources.fromJson(Map<String, dynamic>.from(j as Map)))
      .toList();
});
