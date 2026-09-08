import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/brand.dart';
import '../../core/theme.dart';
import '../../data/models.dart';
import '../../data/repository.dart';
import '../../widgets/academy_card.dart';
import '../../widgets/annals.dart';
import '../../widgets/common.dart';
import '../../widgets/scroll_stage.dart';

/// 첫 화면 — 「實錄」의 **권두(卷頭)**.
///
/// 카드 그리드를 늘어놓지 않는다. 위에서 아래로 한 번 읽으면 이 서비스가
/// 무엇인지 알게 되는 **판면**으로 짰다. 순서에 이유가 있다:
///
///   1. 표제      우리가 무엇을 묻는지
///   2. 학군      어디를 기록하는지 — 카드가 아니라 **장부의 행**으로
///   3. 산식      어떻게 점수를 내는지 — 자 하나로
///   4. 발췌      실제 기록은 이렇게 생겼다
///   5. 원칙      무엇을 하지 않는지 (먹 바탕)
class HomePage extends ConsumerWidget {
  const HomePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(dataProvider);
    return async.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text('데이터를 불러오지 못했습니다\n$e')),
      data: (data) => ListView(
        padding: EdgeInsets.zero,
        children: [
          _Frontispiece(data: data),
          _RegionLedger(data: data),
          _WeightRuler(meta: data.meta),
          _Excerpt(data: data),
          _Principles(meta: data.meta),
          const _Footer(),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────
// 1. 권두 — 표제
// ─────────────────────────────────────────────────────────────────────

/// 표제면. 왼쪽 색인 여백 + 큰 표제 + 오른쪽 세로 제자(題字).
///
/// 가운데 정렬을 쓰지 않는다. 판면은 왼쪽에 기준선이 있고 오른쪽에
/// 제자와 낙관이 있는 구조라, 그 비대칭이 곧 이 화면의 성격이다.
class _Frontispiece extends StatelessWidget {
  final EduTreeData data;
  const _Frontispiece({required this.data});

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final w = MediaQuery.sizeOf(context).width;
    final narrow = w < 760;
    final showColophon = w >= 980; // 세로 제자를 넣을 자리가 있는가

    return PaperGround(
      grain: true,
      child: Column(
        children: [
          // 상단 계선 두 줄. 실록 판면의 천두선(天頭線)에서 가져왔다.
          Rule(thickness: AppRule.bold, color: AppColors.inkOn(dark)),
          const SizedBox(height: 3),
          const Rule(),
          Padding(
            padding: EdgeInsets.symmetric(vertical: narrow ? 40 : 76),
            child: ContentWidth(
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: IndexRail(
                      rail: _HeroRail(meta: data.meta),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          StrokeIn(
                            index: 0,
                            child: Text(
                              '${spaced(Brand.name)}   ·   卷 一',
                              style: text.labelMedium?.copyWith(
                                color: AppColors.accentOn(dark),
                              ),
                            ),
                          ),
                          const SizedBox(height: AppSpace.md),
                          StrokeIn(
                            index: 1,
                            child: Text(
                              narrow
                                  ? '우리 아이는 지금\n어디에 있고,\n다음엔 어디로\n가야 하나요?'
                                  : '우리 아이는 지금 어디에 있고,\n다음엔 어디로 가야 하나요?',
                              style: narrow
                                  ? text.displayMedium
                                  : text.displayLarge,
                            ),
                          ),
                          const SizedBox(height: AppSpace.lg),
                          StrokeIn(
                            index: 3,
                            child: ConstrainedBox(
                              constraints: const BoxConstraints(maxWidth: 560),
                              child: Text(
                                '${josa(Brand.name, '은는')} 학원 목록이 아니라 학원 사이의 '
                                '길을 적습니다. NEIS 공시로 사실을 확인하고, '
                                '커뮤니티 신호로 평판을 읽어 '
                                '${data.regions.length}개 학군의 진학 경로를 '
                                '한 장의 판면에 올립니다.',
                                style: text.bodyLarge,
                              ),
                            ),
                          ),
                          const SizedBox(height: AppSpace.lg),

                          // 이름의 유래. 주묵 획을 세워 인용임을 표시한다.
                          StrokeIn(
                            index: 4,
                            child: Container(
                              constraints: const BoxConstraints(maxWidth: 560),
                              padding: const EdgeInsets.only(left: 14),
                              decoration: BoxDecoration(
                                border: Border(
                                  left: BorderSide(
                                    color: AppColors.accentOn(dark),
                                    width: AppRule.bold,
                                  ),
                                ),
                              ),
                              child: Text(
                                Brand.nameOrigin,
                                style: text.bodyMedium?.copyWith(
                                  height: 1.62,
                                  color: AppColors.inkOn(dark),
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(height: AppSpace.xl),

                          StrokeIn(
                            index: 5,
                            child: Wrap(
                              spacing: AppSpace.sm,
                              runSpacing: AppSpace.sm,
                              children: [
                                FilledButton(
                                  onPressed: () => context.go('/tree'),
                                  child: const Text('테크트리 열람  →'),
                                ),
                                OutlinedButton(
                                  onPressed: () => context.go('/rank'),
                                  child: const Text('학군별 랭킹'),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(height: AppSpace.xl),
                          _StatLedger(data: data),
                        ],
                      ),
                    ),
                  ),
                  if (showColophon) ...[
                    const SizedBox(width: AppSpace.xl),
                    const _Colophon(),
                  ],
                ],
              ),
            ),
          ),
          const Rule(),
        ],
      ),
    );
  }
}

/// 표제면 왼쪽 색인. 본문은 아니지만 판면에 늘 있어야 하는 것들.
class _HeroRail extends StatelessWidget {
  final Meta meta;
  const _HeroRail({required this.meta});

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final wide = MediaQuery.sizeOf(context).width >= AppSpace.railMinWidth;

    final facts = <Widget>[
      RailFact(spaced('집계일'), _day(meta.generatedAt)),
      RailFact(spaced('표본최소'), '${meta.minSampleForRank}건'),
      RailFact(spaced('반감기'), '${meta.recencyHalflifeDays}일'),
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Rule(thickness: AppRule.bold, extent: 26, color: AppColors.inkOn(dark)),
        const SizedBox(height: AppSpace.md),
        // 좁은 화면에서 레일은 표제 **위**로 올라간다. 거기서도 세로로
        // 쌓아 두면 제목을 만나기 전에 메타 정보 세 줄을 먼저 읽게 된다.
        // 눕히면 신문의 날짜띠처럼 한 줄로 지나간다.
        if (wide) ...facts else Wrap(spacing: AppSpace.lg, children: facts),
      ],
    );
  }

  /// `2026-08-27T03:11:00Z` → `2026.08.27`. 시각까지 적으면 '언제 봤나'가
  /// 아니라 '언제 돌았나'가 되어 읽는 사람에게 쓸모가 없다.
  static String _day(String iso) {
    if (iso.length < 10) return '—';
    return iso.substring(0, 10).replaceAll('-', '.');
  }
}

/// 세로 제자(題字) + 낙관. 이 화면에서 가장 오래 기억될 부분이라
/// 다른 어디에도 다시 쓰지 않는다 — 반복하면 장식이 된다.
class _Colophon extends StatelessWidget {
  const _Colophon();

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    const glyphs = ['學', '院', '實', '錄'];

    return Container(
      padding: const EdgeInsets.fromLTRB(AppSpace.lg, AppSpace.sm, 0, 0),
      decoration: BoxDecoration(
        border: Border(
          left: BorderSide(color: AppColors.ruleOn(dark), width: AppRule.hair),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          for (var i = 0; i < glyphs.length; i++)
            StrokeIn(
              index: i + 2,
              from: Alignment.center,
              child: Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Text(
                  glyphs[i],
                  style: TextStyle(
                    fontFamily: 'Paperlogy',
                    fontSize: 44,
                    fontWeight: FontWeight.w800,
                    height: 1.06,
                    letterSpacing: 0,
                    color: AppColors.inkOn(dark),
                  ),
                ),
              ),
            ),
          const SizedBox(height: AppSpace.md),
          SealPress(
            delay: AppMotion.stagger * 7,
            child: Seal('錄', size: 44, color: AppColors.accentOn(dark)),
          ),
        ],
      ),
    );
  }
}

/// 규모를 장부 한 줄로 적는다. 칸 사이를 세로 계선으로 가른다 —
/// 숫자 넷을 그냥 늘어놓으면 어디까지가 한 칸인지 안 읽힌다.
class _StatLedger extends StatelessWidget {
  final EduTreeData data;
  const _StatLedger({required this.data});

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    // 네 칸이 한 줄에 안 들어가는 폭. 실측: 칸 하나에 라벨+숫자가 약 130,
    // 사이 계선·여백이 41 이라 네 칸이면 약 680 이 필요하다.
    final narrow = MediaQuery.sizeOf(context).width < 760;
    final items = <(String, int)>[
      ('등록 학원', data.meta.registryCount),
      ('채점 대상', data.meta.evaluatedCount),
      ('테크트리 단계', data.stageById.length),
      ('분석한 글', data.meta.mentionCount),
    ];

    return StrokeIn(
      index: 6,
      child: Container(
        decoration: BoxDecoration(
          border: Border(
            top: BorderSide(color: AppColors.inkOn(dark), width: AppRule.thin),
            bottom: BorderSide(
              color: AppColors.ruleOn(dark),
              width: AppRule.hair,
            ),
          ),
        ),
        padding: const EdgeInsets.symmetric(vertical: AppSpace.md),
        child: Wrap(
          spacing: 0,
          runSpacing: AppSpace.md,
          children: [
            for (var i = 0; i < items.length; i++)
              IntrinsicHeight(
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    // 칸 사이 세로 계선. **줄이 접히는 폭에서는 긋지 않는다** —
                    // Wrap 은 어느 항목이 새 줄의 첫 칸이 될지 모르므로,
                    // 접히고 나면 줄 맨 앞에 계선 하나가 홀로 서서 얼룩처럼
                    // 보인다(실측: 500px 에서 '분석한 글' 앞).
                    if (i != 0 && !narrow) ...[
                      const Rule.vertical(),
                      const SizedBox(width: AppSpace.lg),
                    ],
                    Padding(
                      padding: const EdgeInsets.only(right: AppSpace.lg),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          RailLabel(spaced(items[i].$1)),
                          const SizedBox(height: 4),
                          // 장부를 **세어 올린다.** 규모가 이 화면의
                          // 주장이라, 숫자가 굴러가는 동안 자릿수가 늘어나는
                          // 것 자체가 그 주장을 한다.
                          Tally(items[i].$2, size: 27),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────
// 2. 학군 — 카드가 아니라 장부의 행
// ─────────────────────────────────────────────────────────────────────

/// 학군 넷을 **표의 행**으로 적는다.
///
/// 정사각 카드 넷을 늘어놓으면 서로 견줄 수가 없다. 행으로 세우면
/// 학원 수·순유입이 세로로 정렬돼 네 학군의 차이가 바로 읽힌다 —
/// 이 섹션이 하려는 말이 정확히 그 차이다.
class _RegionLedger extends ConsumerWidget {
  final EduTreeData data;
  const _RegionLedger({required this.data});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    return PaperGround(
      deep: true,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: AppSpace.xxl),
        child: ContentWidth(
          child: IndexRail(
            rail: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                RailLabel(spaced('제일권')),
                const SizedBox(height: 6),
                Rule(extent: 26, color: AppColors.accentOn(dark)),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Reveal(
                  child: SectionOpener(
                    '기록하는 곳은 네 학군입니다',
                    kicker: spaced('학군'),
                    subtitle:
                        '서울 전체는 초등학생이 줄고 있습니다(2025년 순유출 −188명). '
                        '그런데 이 네 학군은 모두 순유입입니다. '
                        '그 격차가 학군이라는 말의 실체입니다.',
                  ),
                ),
                Rule(thickness: AppRule.thin, color: AppColors.inkOn(dark)),
                for (var i = 0; i < data.regions.length; i++)
                  _RegionRow(
                    region: data.regions[i],
                    index: i,
                    onTap: () {
                      ref
                          .read(selectionProvider.notifier)
                          .setRegion(data.regions[i].id);
                      context.go('/tree');
                    },
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _RegionRow extends StatefulWidget {
  final Region region;
  final int index;
  final VoidCallback onTap;
  const _RegionRow({
    required this.region,
    required this.index,
    required this.onTap,
  });

  @override
  State<_RegionRow> createState() => _RegionRowState();
}

class _RegionRowState extends State<_RegionRow> {
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final accent = AppColors.accentOn(dark);
    final narrow = MediaQuery.sizeOf(context).width < 720;
    final r = widget.region;
    final trend = r.latestTrend('elementary');

    return Reveal(
      index: widget.index,
      child: MouseRegion(
        onEnter: (_) => setState(() => _hover = true),
        onExit: (_) => setState(() => _hover = false),
        child: GestureDetector(
          onTap: widget.onTap,
          behavior: HitTestBehavior.opaque,
          child: AnimatedContainer(
            duration: AppMotion.quick,
            padding: EdgeInsets.fromLTRB(
              _hover ? 14 : 0,
              narrow ? 16 : 20,
              0,
              narrow ? 16 : 20,
            ),
            decoration: BoxDecoration(
              color: _hover
                  ? accent.withValues(alpha: dark ? 0.09 : 0.05)
                  : Colors.transparent,
              border: Border(
                bottom: BorderSide(
                  color: AppColors.ruleOn(dark),
                  width: AppRule.hair,
                ),
                left: BorderSide(
                  color: _hover ? accent : Colors.transparent,
                  width: AppRule.stroke,
                ),
              ),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // 이름 — 이 섹션의 주인공이라 가장 크게.
                SizedBox(
                  width: narrow ? 104 : 190,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        r.nameKo,
                        style:
                            (narrow ? text.headlineMedium : text.headlineLarge)
                                ?.copyWith(
                                  color: _hover
                                      ? accent
                                      : AppColors.inkOn(dark),
                                ),
                      ),
                      const SizedBox(height: 2),
                      // 좁은 칸에서 'MOKDONG · 양천구' 는 '구' 한 글자만
                      // 다음 줄로 넘어간다. 영문명은 장식이라 먼저 뺀다 —
                      // 줄을 하나 더 쓰면서까지 남길 값이 아니다.
                      Text(
                        narrow
                            ? r.sigungu
                            : '${r.nameEn.toUpperCase()} · ${r.sigungu}',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: text.labelSmall,
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: AppSpace.md),
                if (!narrow)
                  Expanded(
                    child: Padding(
                      padding: const EdgeInsets.only(
                        top: 4,
                        right: AppSpace.md,
                      ),
                      child: Text(
                        r.tagline,
                        style: text.bodyMedium,
                        maxLines: 2,
                      ),
                    ),
                  ),

                // 학원 수 — 장부 숫자로 오른쪽 정렬.
                SizedBox(
                  width: narrow ? 66 : 92,
                  child: LedgerNumber(
                    ledgerCount(r.academyCount),
                    size: narrow ? 19 : 23,
                    label: spaced('학원'),
                    align: CrossAxisAlignment.end,
                  ),
                ),

                // 순유입 — 이 서비스만 보여주는 숫자다.
                SizedBox(
                  width: narrow ? 74 : 104,
                  child: trend == null
                      ? const SizedBox.shrink()
                      : Column(
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                            Text(
                              spaced('초등순유입'),
                              style: text.labelSmall,
                              textAlign: TextAlign.end,
                            ),
                            const SizedBox(height: 4),
                            Row(
                              mainAxisAlignment: MainAxisAlignment.end,
                              children: [
                                Text(
                                  trend.netTransfer >= 0 ? '▲' : '▼',
                                  // 8px 로는 화면에서 점 하나로 보였다.
                                  // 삼각형이 삼각형으로 읽히는 최소 크기다.
                                  style: TextStyle(
                                    fontSize: 11,
                                    height: 1.5,
                                    color: trend.netTransfer >= 0
                                        ? AppColors.rising
                                        : AppColors.falling,
                                  ),
                                ),
                                const SizedBox(width: 3),
                                Text(
                                  '${trend.netTransfer.abs()}',
                                  style: TextStyle(
                                    fontFamily: 'Paperlogy',
                                    fontSize: narrow ? 17 : 21,
                                    fontWeight: FontWeight.w800,
                                    height: 1.0,
                                    letterSpacing: -0.8,
                                    color: trend.netTransfer >= 0
                                        ? AppColors.rising
                                        : AppColors.falling,
                                    fontFeatures: ledgerFigures,
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),
                ),
                const SizedBox(width: AppSpace.sm),
                Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: AnimatedSlide(
                    duration: AppMotion.quick,
                    offset: Offset(_hover ? 0.25 : 0, 0),
                    child: Text(
                      '→',
                      style: TextStyle(
                        fontSize: 17,
                        height: 1.2,
                        color: _hover ? accent : AppColors.mutedOn(dark),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────
// 3. 산식 — 자(尺) 하나
// ─────────────────────────────────────────────────────────────────────

/// 트리스코어의 네 기둥을 **자 하나**로 보여준다.
///
/// 카드 넷에 '35%'를 각각 적으면 네 숫자를 머릿속에서 다시 비교해야 한다.
/// 한 줄에 폭으로 나눠 그으면 비교가 이미 끝나 있다 —
/// 카드의 [PillarWeightBars] 와 같은 원칙을 페이지 크기로 키운 것이다.
/// 산식 — **스크롤이 자(尺)를 긋는다.**
///
/// 이 화면에서 유일하게 스크롤에 매인 구간이다. 네 기둥의 가중치를
/// 숫자로 늘어놓는 대신, 화면을 내리는 동안 왼쪽에서 오른쪽으로 **한 획**을
/// 긋는다. 획이 지나가는 시간이 곧 그 기둥의 폭이고, 폭이 곧 가중치다.
/// 다 그으면 정확히 100% 다 — 연출과 값이 같은 것을 말한다.
///
/// **숫자는 세어 올리지 않는다.** 막대와 같이 세면 중간에 '평판 22%' 같은
/// 값이 화면에 뜬다. 잠깐이라도 틀린 가중치를 보여 주는 것은, 근거 없는
/// 숫자를 내지 않는다는 이 서비스의 규칙과 정면으로 어긋난다.
/// 참값을 **흐림에서 꺼낸다**(획이 그 칸을 지나가면 드러난다).
/// 산식 전문으로 가는 링크.
///
/// 산식(`/method`)은 메뉴에서 뺐다(app_shell.dart `navItems`). 산식은 이
/// 서비스의 존재 이유지만 학부모가 매번 찾는 화면은 아니라, 첫 화면의
/// '산식' 절 설명에서 이 링크 하나로 들어간다. 라우트는 그대로다 —
/// 메뉴에서 빠졌다고 링크까지 사라지면 산식 공개가 말뿐이 된다.
class MethodLink extends StatelessWidget {
  static const label = '산식 전문 보기 →';
  const MethodLink({super.key});

  @override
  Widget build(BuildContext context) => TextButton(
    onPressed: () => context.go('/method'),
    child: const Text(label),
  );
}

class _WeightRuler extends StatelessWidget {
  final Meta meta;
  const _WeightRuler({required this.meta});

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final narrow = MediaQuery.sizeOf(context).width < 820;

    final rows = meta.weights.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    if (rows.isEmpty) return const SizedBox.shrink();

    final total = rows.fold<double>(0, (a, e) => a + e.value);
    if (total <= 0) return const SizedBox.shrink();

    return PaperGround(
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: AppSpace.xxl),
        child: ContentWidth(
          child: IndexRail(
            rail: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                RailLabel(spaced('제이권')),
                const SizedBox(height: 6),
                Rule(extent: 26, color: AppColors.accentOn(dark)),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Reveal(
                  child: SectionOpener(
                    '점수를 만든 자를 그대로 내놓습니다',
                    kicker: spaced('산식'),
                    subtitle:
                        '가중치는 화면에 박아 두지 않고 산식 파일에서 읽습니다. '
                        '내려 보세요 — 획이 지나가는 길이가 곧 가중치입니다.',
                    trailing: const MethodLink(),
                  ),
                ),

                // 여기부터가 스크롤에 매인 구간이다.
                Scrub(
                  builder: (context, t) {
                    // 기둥마다 '획이 자기 칸을 얼마나 지났는지'를 구한다.
                    // 누적 비율로 나누므로 네 칸이 이어진 **한 획**이 된다.
                    final fills = <double>[];
                    var cum = 0.0;
                    for (final r in rows) {
                      final a = cum / total;
                      final b = (cum + r.value) / total;
                      fills.add(
                        b <= a ? 1.0 : ((t - a) / (b - a)).clamp(0.0, 1.0),
                      );
                      cum += r.value;
                    }

                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Rule(
                          thickness: AppRule.thin,
                          color: AppColors.inkOn(dark),
                        ),
                        const SizedBox(height: AppSpace.sm),

                        // ── 자. 채워지지 않은 칸도 자리는 지킨다 —
                        //    옅은 바탕을 깔아 두면 '앞으로 얼마나 남았는지'가
                        //    보이고, 다 차기 전에도 비율이 읽힌다.
                        SizedBox(
                          height: 30,
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              for (var i = 0; i < rows.length; i++) ...[
                                Expanded(
                                  flex: (rows[i].value * 1000).round(),
                                  child: _Segment(
                                    color:
                                        AppColors.pillars[rows[i].key] ??
                                        AppColors.slate,
                                    fill: fills[i],
                                    dark: dark,
                                  ),
                                ),
                                if (i != rows.length - 1)
                                  const SizedBox(width: 3),
                              ],
                            ],
                          ),
                        ),
                        const SizedBox(height: AppSpace.sm),

                        // ── 눈금 글자. 막대와 같은 flex 로 자리를 맞춘다.
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            for (var i = 0; i < rows.length; i++) ...[
                              Expanded(
                                flex: (rows[i].value * 1000).round(),
                                child: _Tick(
                                  pillar: rows[i].key,
                                  weight: rows[i].value,
                                  fill: fills[i],
                                  dark: dark,
                                ),
                              ),
                              if (i != rows.length - 1)
                                const SizedBox(width: 3),
                            ],
                          ],
                        ),

                        const SizedBox(height: AppSpace.lg),
                        // 자와 설명을 붙여 두면 설명 칸이 자의 눈금인 줄 알고
                        // 칸을 맞춰 읽으려 든다. 계선으로 끊어 다른 덩어리라고
                        // 말해 준다 — 설명은 폭이 같고, 자는 폭이 다르다.
                        Rule(color: AppColors.ruleOn(dark)),
                        const SizedBox(height: AppSpace.lg),

                        // ── 설명. 획이 그 칸을 지나가면 따라 나온다.
                        if (narrow)
                          for (var i = 0; i < rows.length; i++)
                            _PillarNote(
                              pillar: rows[i].key,
                              index: i,
                              stacked: true,
                              appear: fills[i],
                            )
                        else
                          IntrinsicHeight(
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.stretch,
                              children: [
                                for (var i = 0; i < rows.length; i++) ...[
                                  if (i != 0) ...[
                                    const Rule.vertical(),
                                    const SizedBox(width: AppSpace.md),
                                  ],
                                  Expanded(
                                    child: Padding(
                                      padding: const EdgeInsets.only(
                                        right: AppSpace.md,
                                      ),
                                      child: _PillarNote(
                                        pillar: rows[i].key,
                                        index: i,
                                        appear: fills[i],
                                      ),
                                    ),
                                  ),
                                ],
                              ],
                            ),
                          ),
                      ],
                    );
                  },
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// 자의 한 칸. 옅은 바탕 위로 획이 지나간 만큼만 진하게 찬다.
class _Segment extends StatelessWidget {
  final Color color;
  final double fill;
  final bool dark;
  const _Segment({required this.color, required this.fill, required this.dark});

  @override
  Widget build(BuildContext context) {
    return Stack(
      fit: StackFit.expand,
      children: [
        ColoredBox(color: color.withValues(alpha: dark ? 0.22 : 0.15)),
        // heightFactor 를 1 로 줘야 자식이 칸 높이를 그대로 받는다.
        // 빼면 ColoredBox 가 세로로 0 이 되어 아무것도 안 그려진다.
        FractionallySizedBox(
          alignment: Alignment.centerLeft,
          widthFactor: fill.clamp(0.0, 1.0),
          heightFactor: 1,
          child: ColoredBox(color: color),
        ),
      ],
    );
  }
}

/// 눈금 하나 — 참값 %와 기둥 이름. 획이 지나가면 흐림에서 꺼낸다.
class _Tick extends StatelessWidget {
  final String pillar;
  final double weight;
  final double fill;
  final bool dark;
  const _Tick({
    required this.pillar,
    required this.weight,
    required this.fill,
    required this.dark,
  });

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    // 칸의 3할쯤 지났을 때부터 드러난다. 0 에서 바로 켜면 획보다 글자가
    // 앞서 나가 '숫자가 먼저 뜨고 막대가 따라오는' 꼴이 된다.
    final p = (((fill - 0.3) / 0.4)).clamp(0.0, 1.0);
    return Opacity(
      opacity: p,
      child: Transform.translate(
        offset: Offset(0, (1 - p) * 6),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '${(weight * 100).toStringAsFixed(0)}%',
              style: TextStyle(
                fontFamily: 'Paperlogy',
                fontSize: 20,
                fontWeight: FontWeight.w800,
                height: 1.1,
                letterSpacing: -1.0,
                color: AppColors.inkOn(dark),
                fontFeatures: ledgerFigures,
              ),
            ),
            Text(
              pillarNames[pillar] ?? pillar,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: text.labelLarge?.copyWith(
                color: AppColors.pillars[pillar],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PillarNote extends StatelessWidget {
  final String pillar;
  final int index;
  final bool stacked;

  /// 자의 획이 이 칸을 얼마나 지났는지(0~1). 설명은 획을 **따라** 나온다 —
  /// 먼저 뜨면 무엇에 대한 설명인지 모르는 채로 읽게 된다.
  final double appear;

  const _PillarNote({
    required this.pillar,
    required this.index,
    this.stacked = false,
    this.appear = 1,
  });

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final color = AppColors.pillars[pillar] ?? AppColors.slate;

    // 칸의 절반을 지났을 때부터 올라온다.
    final p = (((appear - 0.5) / 0.45)).clamp(0.0, 1.0);
    return Opacity(
      opacity: p,
      child: Transform.translate(
        offset: Offset(0, (1 - p) * 10),
        child: Padding(
          padding: EdgeInsets.only(bottom: stacked ? AppSpace.lg : 0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(width: 8, height: 8, color: color),
                  const SizedBox(width: 7),
                  Text(
                    pillarNames[pillar] ?? pillar,
                    style: text.titleMedium?.copyWith(
                      color: AppColors.inkOn(dark),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AppSpace.sm),
              Text(pillarDescriptions[pillar] ?? '', style: text.bodyMedium),
            ],
          ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────
// 4. 발췌
// ─────────────────────────────────────────────────────────────────────

class _Excerpt extends ConsumerWidget {
  final EduTreeData data;
  const _Excerpt({required this.data});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final sel = ref.watch(selectionProvider);
    final top = data.ranking(regionId: sel.regionId).take(3).toList();
    final region = data.regionById[sel.regionId];
    final dark = Theme.of(context).brightness == Brightness.dark;

    return PaperGround(
      deep: true,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: AppSpace.xxl),
        child: ContentWidth(
          child: IndexRail(
            rail: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                RailLabel(spaced('제삼권')),
                const SizedBox(height: 6),
                Rule(extent: 26, color: AppColors.accentOn(dark)),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Reveal(
                  child: SectionOpener(
                    '${region?.nameKo ?? ""} 기록 발췌',
                    kicker: spaced('발췌'),
                    subtitle:
                        '트리스코어 순. 표본 ${data.meta.minSampleForRank}건 미만은 '
                        '등수를 붙이되 근거가 얇다는 것을 카드에 적습니다.',
                    trailing: TextButton(
                      onPressed: () => context.go('/rank'),
                      child: const Text('전체 랭킹 →'),
                    ),
                  ),
                ),
                // 발췌는 세 장뿐이라 한 장씩 그어도 부산스럽지 않다.
                // 랭킹 목록에서는 감싸지 않는다 — 100곳을 줄마다 움직이면
                // 훑어 읽기가 어렵다.
                for (var i = 0; i < top.length; i++)
                  Reveal(
                    index: i,
                    child: AcademyCard(academy: top[i], rank: i + 1, index: i),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────
// 5. 원칙 — 먹 바탕
// ─────────────────────────────────────────────────────────────────────

/// 무엇을 **하지 않는지**를 적는 면. 유일하게 먹으로 눕힌 구간이라
/// 스크롤 중에 한 번 숨을 고르게 되고, 그 자리에 원칙이 온다.
class _Principles extends StatelessWidget {
  final Meta meta;
  const _Principles({required this.meta});

  static const _items = <(String, String)>[
    (
      '없는 과거를 만들지 않습니다',
      '표본이 0이면 점수를 내지 않습니다. 코호트 평균 50점을 채워 넣고 등수를 '
          '붙이면 그건 평가가 아니라 기본값입니다. "아직 안 봤다"와 "보고서 낮았다"는 '
          '다른 상태입니다.',
    ),
    (
      '교습비를 쓰지 않습니다',
      'NEIS는 금액만 주고 교습시간을 주지 않습니다. 주2회 26만원과 주5회 26만원이 '
          '같은 값으로 나란히 섭니다. 비교가 성립하지 않는 숫자는 정보가 아니라 '
          '오해의 원인입니다.',
    ),
    (
      '배정을 확률로 바꾸지 않습니다',
      '중·고 배정은 추첨이되 통학 편의가 반영됩니다. 거리순과 거리값만 적습니다. '
          '실제 배정 결과 자료가 없는 상태에서 퍼센트를 붙이면 근거 없는 숫자입니다.',
    ),
    (
      '원문을 저장하지 않습니다',
      '게시물 본문과 작성자 아이디를 남기지 않습니다. 중복 판별용 해시와 '
          '원문 링크만 둡니다.',
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final narrow = MediaQuery.sizeOf(context).width < 820;

    return Container(
      width: double.infinity,
      color: AppColors.ink,
      padding: const EdgeInsets.symmetric(vertical: AppSpace.xxl),
      child: ContentWidth(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Rule(
                        thickness: AppRule.stroke,
                        extent: 46,
                        color: AppColors.vermilion,
                      ),
                      const SizedBox(height: AppSpace.md),
                      Text(
                        spaced('원칙'),
                        style: text.labelMedium?.copyWith(
                          color: AppColors.goldLight,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        narrow
                            ? '실명 사업자를 다룹니다.\n그래서 하지 않는 것이\n있습니다.'
                            : '실명 사업자를 다룹니다.\n그래서 하지 않는 것이 있습니다.',
                        style: text.headlineLarge?.copyWith(
                          color: AppColors.cream,
                        ),
                      ),
                    ],
                  ),
                ),
                if (!narrow)
                  const SealPress(
                    child: Seal(
                      '信',
                      size: 62,
                      color: AppColors.vermilion,
                      solid: false,
                      tilt: 0.05,
                    ),
                  ),
              ],
            ),
            const SizedBox(height: AppSpace.xl),
            for (var i = 0; i < _items.length; i++)
              Container(
                padding: const EdgeInsets.symmetric(vertical: AppSpace.md),
                decoration: const BoxDecoration(
                  border: Border(
                    top: BorderSide(
                      color: AppColors.inkSoft,
                      width: AppRule.hair,
                    ),
                  ),
                ),
                child: narrow
                    ? Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          _PrincipleTitle(i, _items[i].$1),
                          const SizedBox(height: 6),
                          Text(
                            _items[i].$2,
                            style: text.bodyMedium?.copyWith(
                              color: AppColors.mist,
                            ),
                          ),
                        ],
                      )
                    : Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          SizedBox(
                            width: 300,
                            child: _PrincipleTitle(i, _items[i].$1),
                          ),
                          const SizedBox(width: AppSpace.lg),
                          Expanded(
                            child: Text(
                              _items[i].$2,
                              style: text.bodyMedium?.copyWith(
                                color: AppColors.mist,
                              ),
                            ),
                          ),
                        ],
                      ),
              ),
            const SizedBox(height: AppSpace.lg),
            Text(
              '베이지안 축소 — 모든 평판 점수를 같은 지역·과목 코호트 평균 쪽으로 '
              '${meta.reputationPriorCount}건만큼 끌어당깁니다. 후기 3건짜리 학원이 '
              '1위로 튀지 않습니다.',
              // 먹 판(#14161C) 위의 재색. slate(#6B675E)는 3.2:1 로 12.5px
              // 글자의 AA 에 못 미친다. mist 는 5:1.
              style: text.bodySmall?.copyWith(color: AppColors.mist),
            ),
          ],
        ),
      ),
    );
  }
}

class _PrincipleTitle extends StatelessWidget {
  final int index;
  final String title;
  const _PrincipleTitle(this.index, this.title);

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '0${index + 1}',
          style: const TextStyle(
            fontFamily: 'Paperlogy',
            fontSize: 13,
            fontWeight: FontWeight.w800,
            height: 1.5,
            color: AppColors.vermilion,
            fontFeatures: ledgerFigures,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Text(
            title,
            style: Theme.of(
              context,
            ).textTheme.titleLarge?.copyWith(color: AppColors.cream),
          ),
        ),
      ],
    );
  }
}

// ─────────────────────────────────────────────────────────────────────
// 간기(刊記)
// ─────────────────────────────────────────────────────────────────────

class _Footer extends StatelessWidget {
  const _Footer();

  /// 기존 Open Edu 정적 사이트는 Flutter 라우터 바깥(/openedu/)에 있다.
  /// Uri.base 로 풀면 로컬·운영 어디서든 같은 코드로 열린다.
  void _openOperatorSite() {
    launchUrl(Uri.base.resolve('openedu/'), webOnlyWindowName: '_blank');
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final narrow = MediaQuery.sizeOf(context).width < 720;

    return Container(
      width: double.infinity,
      color: AppColors.navy,
      padding: const EdgeInsets.symmetric(vertical: AppSpace.xl),
      child: ContentWidth(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Rule(color: AppColors.navyBright),
            const SizedBox(height: AppSpace.lg),
            Flex(
              direction: narrow ? Axis.vertical : Axis.horizontal,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SizedBox(
                  width: narrow ? double.infinity : 320,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          const Seal(
                            '實',
                            size: 26,
                            color: AppColors.goldLight,
                            tilt: 0,
                          ),
                          const SizedBox(width: 10),
                          Text(
                            Brand.name,
                            style: text.titleLarge?.copyWith(
                              color: AppColors.cream,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Text(
                        Brand.description,
                        style: text.bodySmall?.copyWith(color: AppColors.mist),
                      ),
                    ],
                  ),
                ),
                if (narrow) const SizedBox(height: AppSpace.lg),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // 운영사 표기. 눈에는 들어오되 화면을 가져가지 않을 만큼만.
                      InkWell(
                        onTap: _openOperatorSite,
                        borderRadius: BorderRadius.circular(AppRadius.sm),
                        child: Padding(
                          padding: const EdgeInsets.symmetric(
                            vertical: 6,
                            horizontal: 2,
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Text(
                                '${Brand.name} 서비스 운영 · ',
                                style: text.bodySmall?.copyWith(
                                  color: AppColors.mist,
                                ),
                              ),
                              Text(
                                Brand.operator,
                                style: text.bodySmall?.copyWith(
                                  color: AppColors.goldLight,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                              const SizedBox(width: 5),
                              const Icon(
                                Icons.north_east,
                                size: 11,
                                color: AppColors.goldLight,
                              ),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '${Brand.operator}는 1:1 원어민 영어 교육 사업을 함께 '
                        '운영합니다. 영어 과목 항목에는 이해상충 가능성이 있어 '
                        '이를 고지합니다.',
                        style: text.bodySmall?.copyWith(color: AppColors.mist),
                      ),
                      const SizedBox(height: AppSpace.md),
                      // 남색 바탕에서 주묵은 대비가 모자란다. 링크는
                      // 금박색으로 바꾼다 — 강조색을 어디서나 쓰는 것보다
                      // 읽히는 쪽이 먼저다.
                      TextButtonTheme(
                        data: TextButtonThemeData(
                          style: TextButton.styleFrom(
                            foregroundColor: AppColors.goldLight,
                          ),
                        ),
                        child: Wrap(
                          children: [
                            TextButton(
                              onPressed: () => context.go('/method'),
                              child: const Text('산식 · 데이터 출처'),
                            ),
                            // 정정 요청 폼은 산식 페이지 맨 아래에 있다
                            // (method_page.dart `_CorrectionForm`). 학원별
                            // 시트는 상세 화면에 따로 있다. 같은 주소로
                            // 보내면서 '정정 요청' 이라고만 적으면 산식
                            // 페이지가 열리는 것이 오작동처럼 읽힌다.
                            TextButton(
                              onPressed: () => context.go('/method'),
                              child: const Text('정정 요청 (산식 페이지 하단)'),
                            ),
                            TextButton(
                              onPressed: _openOperatorSite,
                              child: const Text('Open Edu 회사 소개'),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpace.lg),
            const Rule(color: AppColors.navyBright),
            const SizedBox(height: AppSpace.md),
            Text(
              '© ${Brand.operator} · ${Brand.domain}',
              // 남색 판 위의 slate 는 2.7:1 — 앱에서 가장 낮은 대비였다.
              style: text.labelSmall?.copyWith(color: AppColors.mist),
            ),
          ],
        ),
      ),
    );
  }
}
