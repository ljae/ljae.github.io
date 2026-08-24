import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/brand.dart';
import '../../core/theme.dart';
import '../../data/models.dart';
import '../../data/corrections.dart';
import '../../data/repository.dart';
import '../../widgets/common.dart';

/// 산식 공개 페이지.
///
/// 실명 사업자를 점수로 줄 세우는 서비스가 신뢰를 얻는 방법은 하나뿐이다.
/// 계산 방법을 통째로 보여주고, 틀렸을 때 고칠 창구를 여는 것.
class MethodPage extends ConsumerWidget {
  const MethodPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(dataProvider);
    return async.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text('$e')),
      data: (data) {
        final text = Theme.of(context).textTheme;
        final meta = data.meta;

        return ListView(
          padding: const EdgeInsets.symmetric(vertical: AppSpace.lg),
          children: [
            ContentWidth(
              max: 860,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('트리스코어는 어떻게 계산되나요', style: text.displayMedium),
                  const SizedBox(height: AppSpace.sm),
                  Text(
                    '${Brand.name}는 랭킹 산식을 공개합니다. '
                    '점수가 어떻게 나왔는지 설명할 수 없다면, 그 점수로 학원을 줄 세울 자격도 없다고 봅니다.',
                    style: text.bodyLarge,
                  ),
                  const SizedBox(height: AppSpace.xl),

                  _Formula(meta: meta),
                  const SizedBox(height: AppSpace.xl),

                  // 무거운 기둥부터. 화면 순서가 곧 우선순위를 말한다.
                  for (final key in (pillarNames.keys.toList()
                    ..sort((a, b) => (meta.weights[b] ?? 0)
                        .compareTo(meta.weights[a] ?? 0))))
                    _PillarDetail(pillar: key, weight: meta.weights[key] ?? 0),

                  const SizedBox(height: AppSpace.xl),
                  const SectionHeader('표본이 적으면 순위를 매기지 않습니다'),
                  _Prose(
                    '후기 3건으로 만점을 받은 학원이 후기 200건으로 평균을 받은 학원보다 위에 오는 것은 '
                    '통계가 아니라 사고입니다. 그래서 두 가지 장치를 둡니다.\n\n'
                    '첫째, 베이지안 축소. 모든 학원의 평판 점수를 같은 지역·과목 코호트의 평균 쪽으로 '
                    '${meta.reputationPriorCount}건만큼 끌어당깁니다. 표본이 적을수록 평균에 가깝게 눌립니다.\n\n'
                    '둘째, 최소 표본. 유효 후기 ${meta.minSampleForRank}건 미만인 학원은 순위에서 아예 빼고 '
                    '별도 목록으로 보여줍니다. 점수가 나빠서가 아니라, 적은 표본으로 등수를 매기는 것이 '
                    '그 학원에 부당하기 때문입니다.',
                  ),

                  const SizedBox(height: AppSpace.xl),
                  const SectionHeader('긍정률은 무엇인가요'),
                  _Prose(
                    '트리스코어 옆에 붙는 값입니다. 점수 하나만으로는 그것이 무엇을 뜻하는지 '
                    '읽히지 않아서, 근거를 가늠할 수 있는 값을 함께 둡니다.\n\n'
                    '분모는 의견을 낸 후기만 셉니다. 좋다고도 나쁘다고도 하지 않은 중립 서술은 '
                    '빼고, 긍정과 부정을 표현한 글만 놓고 그중 긍정의 비율을 냅니다. 중립까지 넣으면 '
                    '어디나 25~40%에 몰려 변별이 되지 않습니다 — 국내 커뮤니티 글에는 정보 전달 위주의 '
                    '중립 서술이 많기 때문입니다.\n\n'
                    '이 값도 신뢰도·최신성으로 가중합니다. 유효 후기가 ${meta.minSampleForRank}건 미만이면 '
                    '표시하지 않습니다. 설문으로 받은 추천 의향이 아니라 공개된 글에서 읽어낸 값이므로, '
                    '다른 서비스의 추천율과 같은 값이 아닙니다.',
                  ),

                  const SizedBox(height: AppSpace.xl),
                  const SectionHeader('무엇을 가장 무겁게 보나요'),
                  const _Prose(
                    '평판과 진입난이도를 각각 35%로, 가장 무겁게 둡니다. 학부모가 실제로 묻는 것이 '
                    '"평이 좋은가"와 "가고 싶어도 갈 수 있는가" 둘이기 때문입니다. 들어가기 어렵다는 '
                    '사실 자체가 수요의 가장 정직한 표현이고, 자리가 남는 학원과 대기를 거는 학원을 '
                    '같은 저울에 놓으면 지금 학원가의 현황이 보이지 않습니다.\n\n'
                    '화제성과 투명성은 각각 15%입니다. 화제성은 좋고 나쁨이 아니라 "지금 많이 '
                    '이야기되는가"일 뿐이고, 투명성은 공시를 성실히 했는지를 볼 뿐 수업의 질과는 '
                    '다른 이야기이기 때문입니다.',
                  ),

                  const SizedBox(height: AppSpace.xl),
                  const SectionHeader('예체능·기타는 두 가지만 봅니다'),
                  const _Prose(
                    '미술·음악·체육 학원과 그 외 학원은 만족도(평판)와 화제성 두 축으로만 '
                    '순위를 냅니다. 각각 60%와 40%입니다.\n\n'
                    '투명성을 빼는 이유는, 예능 학원의 교습과정 공시가 "미술" 한 줄인 경우가 '
                    '많기 때문입니다. 상세도를 점수로 치면 학원의 실제 차이가 아니라 공시 습관을 '
                    '재게 됩니다. 진입난이도를 빼는 이유는 레벨테스트나 대기 개념이 없는 곳이 '
                    '대부분이라 신호가 잡히지 않기 때문입니다. 없는 것을 0점으로 치면 그것이 '
                    '곧 왜곡입니다.\n\n'
                    '순위는 과목별로만 냅니다. 수학 학원과 미술 학원을 한 줄에 세우면 그 순위가 '
                    '무엇을 뜻하는지 설명할 수 없습니다.',
                  ),

                  const SizedBox(height: AppSpace.xl),
                  const SectionHeader('최근 글에 더 무게를 둡니다'),
                  const _Prose(
                    '학원은 강사가 바뀌고 반 편성이 바뀝니다. 3년 전 후기와 지난달 후기가 같은 '
                    '무게일 수 없습니다. 그래서 모든 글에 반감기 180일의 감쇠를 겁니다 — '
                    '6개월 된 글은 0.37, 1년 된 글은 0.13의 무게를 받습니다.\n\n'
                    '평판, 화제성, 진입난이도 모두에 적용됩니다. 특히 진입난이도는 "지금 들어갈 '
                    '수 있는가"를 말해야 하는 값이라, 오래된 대기 언급이 현재처럼 읽히면 '
                    '안 됩니다.\n\n'
                    '작성일을 알 수 없는 글(카페 검색 결과는 날짜를 주지 않습니다)은 6개월 된 '
                    '글과 같은 무게로 둡니다. 모르는 것을 최신으로도, 오래된 것으로도 '
                    '취급하지 않기 위해서입니다. 다만 저희가 처음 발견한 날짜는 기록해 두고, '
                    '그 이후 새로 나타난 글에는 발견일을 작성일로 씁니다.',
                  ),

                  const SizedBox(height: AppSpace.xl),
                  const SectionHeader('가중치가 곧 영향력이 되도록'),
                  const _Prose(
                    '가중치를 35%로 올리는 것만으로는 부족했습니다. 가중치가 같아도 점수가 좁은 '
                    '구간에만 몰려 있으면 순위를 거의 가르지 못합니다.\n\n'
                    '실제로 그랬습니다. 평판은 감성값 -1~+1을 0~100에 그대로 옮겼는데, 실제 감성이 '
                    '0.00~0.78 구간에만 살아서 점수가 53~65에 눌려 있었습니다. 가중치는 35%인데 '
                    '순위에 미치는 영향은 네 기둥 중 가장 작았습니다.\n\n'
                    '그래서 평판도 화제성이 쓰던 방식(코호트 z점수)으로 통일했습니다. 같은 지역·과목 '
                    '학원들 사이에서 몇 표준편차만큼 앞서는지를 봅니다. 가중치가 뜻하는 바와 실제 '
                    '영향이 어긋나면, 산식을 공개하는 의미가 없습니다.',
                  ),

                  const SizedBox(height: AppSpace.xl),
                  const SectionHeader('교습비를 쓰지 않는 이유'),
                  const _Prose(
                    'NEIS 공시는 금액을 주지만 교습시간을 주지 않습니다. 주 2회 26만원과 '
                    '주 5회 26만원이 같은 값으로 나란히 서게 됩니다. 비교가 성립하지 않는 '
                    '숫자를 화면에 올리면 그것은 정보가 아니라 오해의 원인입니다.\n\n'
                    '시세도 지역과 과목마다 다릅니다. 같은 40만원이 어떤 과목에서는 비싸고 '
                    '어떤 과목에서는 평균입니다. 이 맥락을 함께 줄 수 없다면 금액만 보여주는 '
                    '것이 오히려 판단을 흐립니다.\n\n'
                    '그래서 교습비는 점수에서도 화면에서도 뺐습니다. 실제 금액은 학원에 직접 '
                    '확인하시는 편이 정확합니다.',
                  ),

                  const SizedBox(height: AppSpace.xl),
                  const SectionHeader('등급반별 난이도를 내놓지 않는 이유'),
                  const _Prose(
                    '"그 학원 심화반에 들어갈 수 있나"가 학부모가 실제로 묻는 질문이라는 것을 '
                    '알고 있습니다. 그래서 반 이름 주변에서 난이도·대기 언급을 세어 반별 '
                    '난이도를 만들어 봤습니다.\n\n'
                    '되지 않았습니다. 채점 대상 400곳 전체에서 반 이름과 난이도 표현이 함께 '
                    '붙은 글이 186건뿐이었고, 그중 상당수가 지역명과 과목을 나열한 광고글이었습니다. '
                    '계산 결과도 기초반이 최상위반보다 어렵게 나왔습니다.\n\n'
                    '숫자를 내면 정밀해 보이지만 근거가 없습니다. 대신 테크트리의 단계별 '
                    '진입 기준을 보세요 — 그쪽은 사람이 정리한 것이라 무엇을 통과해야 하는지가 '
                    '분명합니다.',
                  ),

                  const SizedBox(height: AppSpace.xl),
                  const SectionHeader('후기마다 무게가 다릅니다'),
                  const _Prose(
                    '같은 한 줄이어도 누가 썼는지에 따라 점수에 실리는 무게가 다릅니다. '
                    '세 단계로 나눕니다.\n\n'
                    '커뮤니티에서 수집한 글은 가장 낮습니다. 작성자를 확인할 수 없고 광고가 섞이기 '
                    '때문입니다. 학원실록에 로그인해 남긴 후기는 그보다 높습니다 — 학원당 1인 1건이고 '
                    '별점과 관점이 구조화돼 있습니다. 재원 증빙이 확인된 후기가 가장 높습니다.\n\n'
                    '재원 인증에 만점을 주지는 않습니다. 확인한 것은 "실제로 다녔다"이지 '
                    '"이 평가가 옳다"가 아니기 때문입니다.\n\n'
                    '인증 과정에서 증빙 이미지는 서버에 저장하지 않습니다. 영수증에는 이름과 연락처가 '
                    '함께 찍히고, 확인이 끝나면 남길 이유가 없는 정보입니다.',
                  ),

                  const SizedBox(height: AppSpace.xl),
                  const SectionHeader('데이터는 어디서 오나요'),
                  const _SourceTable(),

                  const SizedBox(height: AppSpace.xl),
                  const SectionHeader('광고와 후기를 어떻게 구분하나요'),
                  const _Prose(
                    '체험단·원고료·협찬 문구, 연락처와 외부 링크, 해시태그 도배, 같은 어절의 기계적 반복 — '
                    '이런 신호를 모아 게시물마다 스팸 점수를 매깁니다. 0.6을 넘으면 점수 계산에서 제외하고, '
                    '그 아래여도 신뢰도 가중치를 그만큼 깎습니다.\n\n'
                    '한 작성자가 같은 학원에 네 번 이상 등장하면 바이럴로 보고 가중치를 반비례로 줄입니다. '
                    '작성자 식별에는 해시값만 쓰며 원본 아이디는 저장하지 않습니다.',
                  ),

                  const SizedBox(height: AppSpace.xl),
                  const SectionHeader('순위 이력은 언제부터인가요'),
                  const _Prose(
                    '2026년 8월 23일부터 매 수집마다 순위를 기록합니다. 그 이전 기록은 없습니다 — '
                    '저희 산식의 과거 순위는 어디에도 존재하지 않으므로 만들어 넣지 않습니다.\n\n'
                    '학원 상세의 추이 그래프와 랭킹 목록의 상승·하락 표시는 이 기록에서 나옵니다. '
                    '점수 옆의 상승·보합 화살표는 다른 값입니다 — 그쪽은 언급량 추세이고, 순위 변동이 '
                    '아닙니다.',
                  ),

                  const SizedBox(height: AppSpace.xl),
                  const SectionHeader('무엇을 하지 않나요'),
                  const _DoNotList(),

                  const SizedBox(height: AppSpace.xl),
                  const _CorrectionForm(),

                  const SizedBox(height: AppSpace.xl),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(AppSpace.md),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('이해상충 고지', style: text.titleMedium),
                          const SizedBox(height: 6),
                          Text(
                            '${Brand.name}의 운영사 ${Brand.operator}는 1:1 원어민 영어 교육 사업을 '
                            '함께 운영합니다. 영어 과목의 평가에 이해상충 소지가 있으므로 이를 명시합니다. '
                            '${Brand.operator}의 자체 서비스는 랭킹 대상에 포함하지 않습니다.',
                            style: text.bodyMedium,
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: AppSpace.md),
                  Text(
                    '데이터 생성 시각: ${meta.generatedAt.isEmpty ? "—" : meta.generatedAt}  ·  '
                    '모드: ${meta.mode}  ·  분석 글 ${meta.mentionCount}건',
                    style: text.bodySmall,
                  ),
                  const SizedBox(height: AppSpace.xxl),
                ],
              ),
            ),
          ],
        );
      },
    );
  }
}

class _Formula extends StatelessWidget {
  final Meta meta;
  const _Formula({required this.meta});

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    // 무거운 기둥부터. 마지막 항목 뒤에는 '+' 를 붙이지 않는다.
    final sorted = pillarNames.keys.toList()
      ..sort((a, b) =>
          (meta.weights[b] ?? 0).compareTo(meta.weights[a] ?? 0));
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpace.lg),
      decoration: BoxDecoration(
        color: dark ? AppColors.darkSurface : AppColors.ink,
        borderRadius: BorderRadius.circular(AppRadius.md),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('트리스코어',
            style: TextStyle(
                fontFamily: 'Paperlogy',
                fontSize: 12,
                color: AppColors.mist)),
        const SizedBox(height: AppSpace.sm),
        Wrap(
          crossAxisAlignment: WrapCrossAlignment.center,
          runSpacing: 4,
          children: [
            for (final key in sorted) ...[
              Text('${(meta.weights[key]! * 100).toStringAsFixed(0)}%',
                  style: TextStyle(
                    fontFamily: 'Paperlogy',
                    fontSize: 22,
                    fontWeight: FontWeight.w800,
                    color: AppColors.pillars[key],
                  )),
              const SizedBox(width: 5),
              Text('· ${pillarNames[key]}',
                  style: const TextStyle(
                      fontFamily: 'Paperlogy',
                      fontSize: 17,
                      color: Colors.white)),
              if (key != sorted.last)
                const Padding(
                  padding: EdgeInsets.symmetric(horizontal: 12),
                  child: Text('+',
                      style: TextStyle(
                          fontFamily: 'Paperlogy',
                          fontSize: 17,
                          color: AppColors.mist)),
                ),
            ],
          ],
        ),
        const SizedBox(height: AppSpace.md),
        const Text('각 기둥은 0–100점으로 따로 계산한 뒤 위 비율로 합칩니다.',
            style: TextStyle(
                fontFamily: 'Paperlogy',
                fontSize: 13,
                height: 1.6,
                color: AppColors.mist)),
      ]),
    );
  }
}

class _PillarDetail extends StatelessWidget {
  final String pillar;
  final double weight;
  const _PillarDetail({required this.pillar, required this.weight});

  static const _details = <String, List<String>>{
    'reputation': [
      '커뮤니티 게시물마다 감성 점수(-1 ~ +1)를 매깁니다.',
      '각 글의 가중치 = 신뢰도 × 최신성. 최신성은 반감기 180일 지수 감쇠입니다.',
      '신뢰도는 글 길이, 구체적 수치(학년·개월·등급), 1인칭 경험 서술, 실제 수강 이력 언급으로 매깁니다.',
      '가중 평균을 코호트 평균 쪽으로 축소합니다(베이지안 축소).',
      '축소한 값을 같은 지역·과목 코호트의 z점수로 옮깁니다 — 50 + 15z. '
          '아래 "가중치가 곧 영향력이 되도록"을 보세요.',
    ],
    'momentum': [
      '최근 90일 언급량을 로그 스케일로 잡고, 같은 지역·과목 코호트 안에서 z점수로 표준화합니다 (60%).',
      '최근 12개월 월별 언급량의 선형 추세 기울기를 봅니다 (40%).',
      '상승·보합·하락 화살표는 이 기울기에서 나옵니다.',
    ],
    'transparency': [
      '등록상태 정상 30점 — 휴원·폐원이면 감점.',
      '정원 공시 20점 · 교습과정 상세 25점.',
      '운영 지속기간 25점 — 개설일 기준 로그 스케일.',
      '네 기둥 중 유일하게 100% 검증 가능한 항목입니다.',
      '교습비 항목은 뺐습니다 — 아래 "교습비를 쓰지 않는 이유"를 보세요.',
    ],
    'selectivity': [
      '레벨테스트 난이도 언급 40% · 대기/마감 언급 30% · 정원 대비 언급량 30%.',
      '표본이 적으면 중앙(50)으로 끌어당깁니다(사전표본 10건) — 12건으로 '
          '"난이도 100"은 측정이 아니라 잡음이기 때문입니다.',
      '공식 경쟁률이 아니라 커뮤니티 언급에서 추정한 값입니다. '
          '화면에 "추정" 표시를 답니다.',
      '등급반(심화반·최상위반)별 난이도는 내놓지 않습니다 — 아래를 보세요.',
    ],
  };

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final color = AppColors.pillars[pillar]!;
    return Card(
      margin: const EdgeInsets.only(bottom: AppSpace.md),
      child: Padding(
        padding: const EdgeInsets.all(AppSpace.md),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Icon(pillarIcons[pillar], size: 18, color: color),
            const SizedBox(width: AppSpace.sm),
            Text(pillarNames[pillar]!, style: text.titleLarge),
            const SizedBox(width: AppSpace.sm),
            Chip2('${(weight * 100).toStringAsFixed(0)}%', color: color),
            if (pillar == 'selectivity') ...[
              const SizedBox(width: 6),
              const Chip2('추정', color: AppColors.estimated),
            ],
          ]),
          const SizedBox(height: AppSpace.sm),
          for (final line in _details[pillar]!)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Padding(
                  padding: const EdgeInsets.only(top: 7, right: 8),
                  child:
                      Container(width: 4, height: 4, decoration: BoxDecoration(
                          color: color, shape: BoxShape.circle)),
                ),
                Expanded(child: Text(line, style: text.bodyLarge)),
              ]),
            ),
        ]),
      ),
    );
  }
}

class _SourceTable extends StatelessWidget {
  const _SourceTable();

  static const rows = [
    ('NEIS 학원교습소정보', '학원명·주소·정원·교습과정·등록상태', '공공데이터 · 자유 이용', true),
    ('네이버 검색 오픈 API', '카페글·블로그·지식iN 스니펫', '공식 API · 약관 준수', true),
    ('큐레이션 테크트리', '단계 구성과 진급 경로', '직접 작성 · 근거 게시물 수 병기', true),
  ];

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Column(children: [
      for (final (name, use, status, ok) in rows)
        Card(
          margin: const EdgeInsets.only(bottom: AppSpace.sm),
          child: Padding(
            padding: const EdgeInsets.all(AppSpace.md),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Icon(ok ? Icons.check_circle_outline : Icons.info_outline,
                  size: 17, color: AppColors.verified),
              const SizedBox(width: AppSpace.sm),
              Expanded(
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(name, style: text.titleMedium),
                      Text(use, style: text.bodyMedium),
                      const SizedBox(height: 3),
                      Chip2(status, color: AppColors.verified),
                    ]),
              ),
            ]),
          ),
        ),
    ]);
  }
}

class _DoNotList extends StatelessWidget {
  const _DoNotList();

  static const items = [
    '게시물 본문을 저장하거나 재배포하지 않습니다. 원문은 링크로만 안내합니다.',
    '작성자의 아이디·닉네임을 저장하지 않습니다. 중복 판별용 해시만 남깁니다.',
    '광고비를 받고 순위를 바꾸지 않습니다. 광고를 싣게 되면 순위와 분리해 표시합니다.',
    '표본이 부족한 학원에 순위를 붙이지 않습니다.',
    '"최악의 학원" 같은 하위 랭킹을 만들지 않습니다.',
    '수집을 거부한 사이트의 글을 가져오지 않습니다. robots.txt 와 '
        '콘텐츠 신호를 먼저 확인하고, 도구를 바꿔 우회하지 않습니다.',
    '근거가 모자란 지표를 만들어 내지 않습니다. 교습비와 등급반별 난이도가 '
        '그래서 빠져 있습니다.',
    '추천 이유를 설명할 수 없는 개인화 추천을 하지 않습니다.',
  ];

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Column(
      children: [
        for (final item in items)
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpace.sm),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Icon(Icons.block, size: 15, color: AppColors.estimated),
              const SizedBox(width: AppSpace.sm),
              Expanded(child: Text(item, style: text.bodyLarge)),
            ]),
          ),
      ],
    );
  }
}

/// 정정 요청 폼.
///
/// 한동안 입력값을 받아 놓고 아무 데도 보내지 않았다. 화면에는
/// '접수되었습니다' 라고 띄우면서 글은 버렸다. 창구가 있는 척하는 것은
/// 창구가 없는 것보다 나쁘다 — 관계자는 답을 기다리게 되고 우리는
/// 요청이 온 줄도 모른다.
class _CorrectionForm extends ConsumerStatefulWidget {
  const _CorrectionForm();

  @override
  ConsumerState<_CorrectionForm> createState() => _CorrectionFormState();
}

class _CorrectionFormState extends ConsumerState<_CorrectionForm> {
  final _academy = TextEditingController();
  final _body = TextEditingController();
  final _contact = TextEditingController();
  String _type = 'fix';
  bool _sent = false;
  bool _busy = false;
  String? _error;

  static const types = [
    ('fix', '사실과 다른 정보'),
    ('defamation', '명예훼손 소지'),
    ('closed', '폐원·휴원'),
    ('other', '기타'),
  ];

  @override
  void dispose() {
    _academy.dispose();
    _body.dispose();
    _contact.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpace.lg),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('정정 요청', style: text.headlineMedium),
          const SizedBox(height: 6),
          Text(
            '학원 운영자 또는 관계자가 사실과 다른 내용을 발견한 경우 정정을 요청할 수 있습니다. '
            '로그인은 필요 없습니다. 접수 내용은 공개되지 않으며 운영자가 직접 검토합니다. '
            '자동으로 반영하지 않는 이유는, 창구가 곧 편집권이 되면 그것도 또 다른 왜곡이기 '
            '때문입니다. 남겨 주신 연락처로 7일 이내에 처리 결과를 회신합니다.',
            style: text.bodyMedium,
          ),
          const SizedBox(height: AppSpace.md),
          if (_sent)
            Container(
              padding: const EdgeInsets.all(AppSpace.md),
              decoration: BoxDecoration(
                color: AppColors.verified.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(AppRadius.sm),
              ),
              child: Row(children: [
                const Icon(Icons.check_circle,
                    size: 18, color: AppColors.verified),
                const SizedBox(width: AppSpace.sm),
                Expanded(
                  child: Text(
                    '접수되었습니다. 남겨 주신 연락처로 7일 이내에 처리 결과를 '
                    '회신드립니다.',
                    style: text.bodyMedium,
                  ),
                ),
              ]),
            )
          else ...[
            ChipRow<String>(
              options: types,
              selected: _type,
              onChanged: (v) => setState(() => _type = v),
            ),
            const SizedBox(height: AppSpace.md),
            TextField(
              controller: _academy,
              decoration: const InputDecoration(
                  labelText: '학원명', border: OutlineInputBorder()),
            ),
            const SizedBox(height: AppSpace.sm),
            TextField(
              controller: _body,
              maxLines: 4,
              decoration: const InputDecoration(
                labelText: '어떤 내용이 사실과 다른지 구체적으로 적어주세요',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: AppSpace.sm),
            TextField(
              controller: _contact,
              decoration: const InputDecoration(
                  labelText: '회신받을 연락처(이메일 또는 전화)',
                  border: OutlineInputBorder()),
            ),
            const SizedBox(height: AppSpace.md),
            if (_error != null) ...[
              Text(_error!,
                  style: text.bodySmall?.copyWith(color: AppColors.rising)),
              const SizedBox(height: AppSpace.sm),
            ],
            FilledButton(
              onPressed: _busy ? null : () async {
                if (_academy.text.trim().isEmpty ||
                    _body.text.trim().isEmpty ||
                    _contact.text.trim().isEmpty) {
                  ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('모든 항목을 입력해 주세요')));
                  return;
                }
                setState(() { _busy = true; _error = null; });
                try {
                  await ref.read(correctionServiceProvider).submit(
                        // 이 폼은 학원명을 손으로 받는다. 학원 상세의 폼과
                        // 달리 어느 학원인지 특정할 수 없어, 검토 단계에서
                        // 사람이 대조한다.
                        academyKey: 'unmatched',
                        academyName: _academy.text.trim(),
                        requester: '미기재',
                        contact: _contact.text.trim(),
                        kind: _type,
                        message: _body.text.trim(),
                      );
                } catch (_) {
                  if (mounted) {
                    setState(() {
                      _busy = false;
                      _error = '접수에 실패했습니다. 잠시 후 다시 시도해 주세요.';
                    });
                  }
                  return;
                }
                if (!mounted) return;
                setState(() { _busy = false; _sent = true; });
              },
              child: Text(_busy ? '보내는 중…' : '정정 요청 보내기'),
            ),
          ],
        ]),
      ),
    );
  }
}

class _Prose extends StatelessWidget {
  final String text;
  const _Prose(this.text);

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: AppSpace.md),
        child: Text(text, style: Theme.of(context).textTheme.bodyLarge),
      );
}
