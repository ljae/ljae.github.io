import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'academy_detail.dart';
import 'models.dart';
import 'browser_store.dart' as store;

const parentConcerns = <String, String>{
  'foundation': '기초를 차근차근 다지고 싶어요',
  'homework': '숙제 부담이 걱정돼요',
  'questions': '질문하기 편한 수업을 찾고 있어요',
};
const concernQuestions = <String, String>{
  'foundation': '기초가 비어 있는 부분을 어떻게 확인하고 보완하나요?',
  'homework': '하루 숙제 분량과 어려워할 때의 피드백은 어떻게 되나요?',
  'questions': '이해하지 못한 부분을 언제, 어떻게 질문할 수 있나요?',
};

class ConcernNotifier extends Notifier<String?> {
  @override
  String? build() {
    final value = store.readPublic('parent.concern.v2');
    return parentConcerns.containsKey(value) ? value : null;
  }

  void choose(String? value) {
    state = parentConcerns.containsKey(value) ? value : null;
    store.writePublic('parent.concern.v2', state ?? '');
  }
}

final parentConcernProvider = NotifierProvider<ConcernNotifier, String?>(
  ConcernNotifier.new,
);

List<String> parseCompareIds(String? value) => (value ?? '')
    .split(',')
    .where((id) => RegExp(r'^\d{1,20}$').hasMatch(id))
    .toSet()
    .take(3)
    .toList();

class CompareNotifier extends Notifier<List<String>> {
  @override
  List<String> build() =>
      parseCompareIds(store.readPublic('parent.compare.v2'));
  bool toggle(String id) {
    if (!RegExp(r'^\d{1,20}$').hasMatch(id)) return false;
    if (state.contains(id)) {
      state = [...state]..remove(id);
      _save();
      return true;
    }
    if (state.length >= 3) return false;
    state = [...state, id];
    _save();
    return true;
  }

  void restore(List<String> ids) {
    state = parseCompareIds(ids.join(','));
    _save();
  }

  void clear() {
    state = const [];
    _save();
  }

  void _save() => store.writePublic('parent.compare.v2', state.join(','));
}

final compareProvider = NotifierProvider<CompareNotifier, List<String>>(
  CompareNotifier.new,
);

String detailName(AcademyDetail d) =>
    d.academy?.displayName ?? d.registry!.displayName;
List<String> inquiryQuestions({String? concern}) => [
  '현재 우리 아이 학년에 맞는 반이 열려 있나요?',
  concernQuestions[concern] ?? '수업 방식과 숙제·피드백은 어떻게 진행되나요?',
  '수강료 외 교재·테스트 비용과 납부 조건도 알려주세요.',
];
String gradeContext(AcademyDetail d, String subject) {
  final bands =
      d.academy?.bandsForSubject(subject) ??
      d.registry!.bandsForSubject(subject);
  if (bands.isEmpty) return '대상 학년 미확인 · 학원에 문의해주세요';
  final basis =
      (d.academy?.gradeBandBasis ?? d.registry!.gradeBandBasis)[subject] ??
      const <String, String>{};
  final labels = <String, String>{
    'official': '공식 안내',
    'registered': '공시',
    'directory': '소개 자료 대조',
    'curated': '큐레이션 단계',
    'reviews': '후기 언급',
  };
  return bands
      .map(
        (b) => '${gradeBandNames[b] ?? b} (${labels[basis[b]] ?? '근거 수준 미확인'})',
      )
      .join(' · ');
}
