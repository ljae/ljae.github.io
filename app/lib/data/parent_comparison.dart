import 'academy_detail.dart';
import 'contact_view_model.dart';
import 'models.dart';
import 'parent_decision.dart';
import 'source_notes.dart';

/// Reading aids, never school scores or inferred operating facts. Every excerpt
/// must rejoin the public evidence ledger for this academy before it is shown.
class ComparisonCriterion {
  final String id, title, meaning, question;
  final List<String> checkpoints;
  final RegExp terms;
  ComparisonCriterion(
    this.id,
    this.title,
    this.meaning,
    this.question,
    String pattern,
    this.checkpoints,
  ) : terms = RegExp(pattern, caseSensitive: false);
}

final comparisonCriteria = [
  ComparisonCriterion(
    'curriculum',
    '배우는 내용과 진도',
    '교재 이름보다 지금 배우는 수준과 진도를 정하는 방식을 보세요. 기초 보완이 필요한지, 새로운 내용을 확장할지에 따라 선택이 달라집니다.',
    '현재 수준에서 시작할 교재·진도와 수업 목표는 무엇이며, 진도를 따라가기 어려우면 어떻게 조정하나요?',
    r'진도|교재|커리큘럼|수업\s*방식|사고력|선행|독해|문법|토론',
    ['시작 수준·선수학습', '교재·학습 목표', '반 진도·개별 조정'],
  ),
  ComparisonCriterion(
    'feedback',
    '오답·첨삭과 보충',
    '틀린 문제나 글을 누가 어떻게 다시 확인하는지 보세요. 질문 기회와 재점검 방식에 따라 모르는 내용을 남긴 채 넘어갈 가능성이 달라집니다.',
    '질문은 언제 누구에게 하고, 오답·첨삭 후 이해했는지는 어떻게 다시 확인하나요? 별도 보충이 가능한가요?',
    r'오답|첨삭|피드백|클리닉|재시험|질문\s*(시간|기회|받|하|할|을\s*받)|보충\s*(수업|지도|해주|해\s*주)',
    ['질문 시간·담당 교사', '오답·첨삭 후 재점검', '보충·부모에게 전달'],
  ),
  ComparisonCriterion(
    'homework',
    '숙제와 집에서의 부담',
    '분량과 함께 어디서 마치고 누가 확인하는지 보세요. 집에서 쓸 시간과 부모가 도와야 할 일이 달라집니다.',
    '평일 하루 숙제 시간, 집에서 도와줄 부분, 다 못 했을 때의 지도 방식은 어떻게 되나요?',
    r'숙제|과제|예습|복습|워크북',
    ['하루 소요 시간·예습/복습', '부모가 도울 부분', '미완료 시 지도'],
  ),
  ComparisonCriterion(
    'atmosphere',
    '수업 참여와 분위기',
    '반 인원과 실제 발언·질문 기회를 함께 보세요. 발표나 경쟁을 즐기는 아이와 충분히 생각할 시간이 필요한 아이는 확인할 지점이 다릅니다.',
    '실제 들어갈 반의 인원은 몇 명이며, 발표·토론·경쟁 활동에서 소극적인 아이도 참여하도록 어떻게 돕나요?',
    r'분위기|발표|토론|참여|경쟁|소극|적극|반\s*(인원|정원)|명씩|소수\s*정예',
    ['실제 반 인원', '발언·질문 기회', '참여 방식·경쟁 강도'],
  ),
  ComparisonCriterion(
    'entry',
    '입학과 반 이동',
    '시험 유무보다 평가 영역과 배정·이동 기준을 보세요. 지금 입학할 수 있는지뿐 아니라 시작한 반에서 적응할 여지가 있는지도 판단할 수 있어요.',
    '입학 평가의 범위와 반 배정 기준은 무엇이며, 적응이 어렵거나 쉬울 때 반 이동·재평가는 어떻게 하나요?',
    r'레벨\s*테스트|입학\s*(시험|평가)|반\s*(배정|이동)|승급|인터뷰|레테',
    ['평가 범위·준비 수준', '반 배정·대기', '반 이동·재평가'],
  ),
  ComparisonCriterion(
    'routine',
    '시간표와 보강',
    '정규 수업과 숙제를 한 주의 일정에 놓아보세요. 결석 시 보강 요일과 종료 시각까지 확인해야 다른 일정과 함께 다닐 수 있을지 판단할 수 있어요.',
    '가능한 요일·종료 시각과 결석 시 보강 방식을 알려주세요.',
    r'시간표|보강|주\s*[1-7일이삼사오육칠]\s*회|수업\s*시간',
    ['요일·횟수', '결석 시 보강', '정규·보강 종료 시각'],
  ),
  ComparisonCriterion(
    'riding',
    '라이딩·셔틀과 하원',
    '학교에서 학원, 학원에서 집까지의 동선과 보호자가 쓸 시간을 함께 보세요. 셔틀이 있어도 정류장·요일·하원 시각이 맞아야 이용할 수 있어요.',
    concernQuestions['riding']!,
    r'셔틀|통학|라이딩|픽업|주차|(등하원|하원|귀가)\s*(시각|시간|방법)|차량\s*(운행|지원|탑승)',
    ['등원·하원 동선', '셔틀 정류장·운행 요일', '픽업·대기와 보호자 시간'],
  ),
];

List<ComparisonCriterion> orderedComparisonCriteria(String? concern) {
  final first = concernCriteria[concern] ?? 'curriculum';
  return [
    ...comparisonCriteria.where((c) => c.id == first),
    ...comparisonCriteria.where((c) => c.id != first),
  ];
}

class ComparisonExcerpt {
  final String text, url, source;
  final String? subject, band, postedAt;
  final bool selfDescription;
  final bool topicQuote;
  const ComparisonExcerpt({
    required this.text,
    required this.url,
    required this.source,
    this.subject,
    this.band,
    this.postedAt,
    this.selfDescription = false,
    this.topicQuote = false,
  });
  String get scope =>
      '${subjectNames[subject] ?? '과목 미확인'} · ${gradeBandNames[band] ?? '학년 미확인'}';
  String get dateLabel =>
      postedAt == null ? '작성일 미확인 · 수강 시점 미확인' : '글 작성 $postedAt · 수강 시점 미확인';
}

String? _date(String? value) {
  if (value == null || !RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(value)) {
    return null;
  }
  final d = DateTime.tryParse(value);
  return d != null && d.toIso8601String().startsWith(value) ? value : null;
}

// Do not introduce fees through quotations into a cost-free comparison.
final _money = RegExp(r'(\d[\d,.]*\s*(만|천)?\s*원|₩|수강료|교습비|학원비)');

/// Existing editorial summaries of primary sources. These have no grade field:
/// the UI must explicitly keep their applicability to the selected class open.
List<SourceNote> comparisonGuidance(
  AcademyDetail detail,
  ComparisonCriterion c,
  String subject,
  AcademySources? group,
) {
  if (group == null || group.academyId != detail.id) return const [];
  final topic = switch (c.id) {
    'homework' => '숙제',
    'entry' => '입학·레벨테스트',
    'curriculum' || 'feedback' || 'atmosphere' => '수업·교재',
    'routine' || 'riding' => '운영·일정',
    _ => null,
  };
  return group.notes
      .where(
        (n) =>
            n.topic == topic &&
            c.terms.hasMatch(n.summary) &&
            n.isPrimary &&
            n.sourceScope == 'branch' &&
            n.subjects.contains(subject) &&
            n.summary.trim().isNotEmpty &&
            !_money.hasMatch(n.summary) &&
            safeContactUrl(n.url) != null,
      )
      .toList();
}

/// Keep the source wording. The ellipses explicitly mark clipping, not a summary.
String _excerpt(String text, RegExp terms) {
  final match = terms.firstMatch(text);
  if (text.length <= 220 || match == null) return text;
  final start = (match.start - 60).clamp(0, text.length);
  final end = (start + 220).clamp(0, text.length);
  return '${start > 0 ? '…' : ''}${text.substring(start, end)}${end < text.length ? '…' : ''}';
}

List<ComparisonExcerpt> comparisonExcerpts(
  AcademyDetail detail,
  ComparisonCriterion criterion, {
  required String subject,
  required String gradeBand,
}) {
  final academy = detail.academy;
  if (academy == null) return const [];
  // Neither a brand-wide post nor another subject/grade can explain this choice.
  final evidence = academy.evidence
      .where(
        (e) =>
            const {'direct', 'region'}.contains(e.branchBasis) &&
            (e.subject == null || e.subject == subject) &&
            (e.band == null || e.band == gradeBand) &&
            safeContactUrl(e.url) != null,
      )
      .toList();
  final rows = <String, ComparisonExcerpt>{};
  void add(
    String text,
    Evidence e, {
    bool self = false,
    String? date,
    bool topicQuote = false,
  }) {
    if (text.trim().isEmpty || _money.hasMatch(text)) return;
    rows.putIfAbsent(
      e.url,
      () => ComparisonExcerpt(
        text: _excerpt(text, criterion.terms),
        url: e.url,
        source: e.sourceLabel,
        subject: e.subject,
        band: e.band,
        postedAt: _date(date ?? e.postedAt),
        selfDescription: self,
        topicQuote: topicQuote,
      ),
    );
  }

  final profile = academy.profile;
  final section = switch (criterion.id) {
    'homework' => profile?.homework,
    'entry' => profile?.levelTest,
    'curriculum' || 'feedback' || 'atmosphere' => profile?.curriculum,
    'routine' || 'riding' => profile?.ops,
    _ => null,
  };
  for (final quote in section?.quotes ?? const <ProfileQuote>[]) {
    final e = evidence.where((e) => e.url == quote.url).firstOrNull;
    if (e != null && criterion.terms.hasMatch(quote.quote)) {
      add(
        quote.quote,
        e,
        self: quote.isSelf,
        date: quote.postedAt,
        topicQuote: true,
      );
    }
  }
  for (final e in evidence) {
    if (criterion.terms.hasMatch(e.snippet)) add(e.snippet, e);
  }
  final result = rows.values.toList();
  int scoped(ComparisonExcerpt e) =>
      (e.subject == subject ? 1 : 0) + (e.band == gradeBand ? 1 : 0);
  result.sort((a, b) {
    // A topic's existing source quotation is more useful than a newer post's
    // introductory snippet that merely mentions "homework". Scope stays visible.
    if (a.topicQuote != b.topicQuote) return a.topicQuote ? -1 : 1;
    final scope = scoped(b).compareTo(scoped(a));
    if (scope != 0) return scope;
    final date = (b.postedAt ?? '').compareTo(a.postedAt ?? '');
    return date != 0 ? date : a.url.compareTo(b.url);
  });
  return result;
}

class ComparisonTarget {
  final String label, explanation;
  const ComparisonTarget(this.label, this.explanation);
}

ComparisonTarget comparisonTarget(
  AcademyDetail d,
  String subject,
  String band,
) {
  final name = subjectNames[subject] ?? subject;
  final grade = gradeBandNames[band] ?? band;
  final subjects = d.academy?.subjects ?? d.registry!.subjects;
  final bands =
      d.academy?.bandsForSubject(subject) ??
      d.registry!.bandsForSubject(subject);
  final basis =
      (d.academy?.gradeBandBasis ?? d.registry!.gradeBandBasis)[subject]?[band];
  if (!subjects.contains(subject)) {
    return ComparisonTarget('$name 운영 자료 없음', '현재 $name 반을 운영하는지 먼저 문의하세요.');
  }
  if (!bands.contains(band)) {
    return ComparisonTarget(
      '$grade 대상 자료 없음',
      bands.isEmpty
          ? '이 과목의 대상 학년을 아직 확인하지 못했어요.'
          : '자료에 있는 학년: ${bands.map((b) => gradeBandNames[b] ?? b).join(' · ')}. 현재 $grade 모집 여부는 문의하세요.',
    );
  }
  final label = switch (basis) {
    'official' => '공식 안내에 대상 학년 표시',
    'registered' => '공시에 대상 학년 표시',
    'directory' => '소개 자료에 대상 학년 표시',
    'curated' => '학습 단계에서 학년 연결',
    'reviews' => '공개 글에 대상 학년 언급',
    _ => '대상 학년 표시 · 출처 수준 미확인',
  };
  return ComparisonTarget(label, '$name · $grade 자료입니다. 현재 반 개설·모집 여부는 문의하세요.');
}

String comparisonQuestion(
  ComparisonCriterion c,
  List<ComparisonExcerpt> rows,
  String subject,
  String band, {
  bool hasGuidance = false,
}) {
  final target =
      '${gradeBandNames[band] ?? band} ${subjectNames[subject] ?? subject}';
  if (rows.isEmpty) {
    return hasGuidance
        ? '이 안내가 현재 $target 반에도 적용되나요? ${c.question}'
        : '$target 반에 대해 ${c.question}';
  }
  final e = rows.first;
  final scopeMissing = e.subject == null || e.band == null;
  return '${scopeMissing ? '이 글이 $target 반의 이야기인지, ' : '$target 반의 이 경험이 '}'
      '현재도 해당하는지 궁금합니다. ${c.question}';
}
