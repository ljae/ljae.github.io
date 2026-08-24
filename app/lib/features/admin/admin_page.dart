import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/theme.dart';
import '../../data/admin.dart';
import '../../data/repository.dart';
import '../../widgets/common.dart';

/// 참조 글 검수 관리자 화면.
///
/// 랭킹이 커뮤니티 글에서 나오는 이상, 무엇을 근거로 삼았는지 사람이
/// 확인할 수 있어야 한다. 다만 사람이 영원히 누르게 두면 그건 자동화가
/// 아니라 노동이다 — 반려할 때 남긴 사유가 크롤 규칙이 되어 다음
/// 수집부터 같은 글이 안 올라오게 하는 것이 이 화면의 핵심이다.
class AdminPage extends ConsumerStatefulWidget {
  const AdminPage({super.key});

  @override
  ConsumerState<AdminPage> createState() => _AdminPageState();
}

class _AdminPageState extends ConsumerState<AdminPage> {
  int _tab = 0;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final service = ref.watch(adminServiceProvider);
    final enabled = service.enabled;
    final isAdmin = ref.watch(isAdminProvider);

    return ListView(
      padding: const EdgeInsets.symmetric(vertical: AppSpace.lg),
      children: [
        ContentWidth(
          max: 1000,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SectionHeader('참조 글 검수',
                  subtitle: '랭킹 근거로 쓰인 글을 확인하고, 잘못 잡힌 글을 '
                      '반려합니다. 반려 사유는 다음 수집의 필터가 됩니다.'),
              if (!enabled)
                Text('Supabase 연결이 없어 검수 기능을 쓸 수 없습니다.',
                    style: text.bodyLarge)
              else if (!service.signedIn)
                const _SignIn()
              else if (isAdmin.value == false)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(AppSpace.md),
                    child: Text(
                      '이 계정은 운영자로 등록되어 있지 않습니다. '
                      '등록은 데이터베이스에서만 가능합니다.',
                      style: text.bodyLarge,
                    ),
                  ),
                )
              else ...[
                const _SourceList(),
                const SizedBox(height: AppSpace.lg),
                SegmentedButton<int>(
                  showSelectedIcon: false,
                  segments: const [
                    ButtonSegment(value: 0, label: Text('검수 대기')),
                    ButtonSegment(value: 1, label: Text('크롤 규칙')),
                  ],
                  selected: {_tab},
                  onSelectionChanged: (v) => setState(() => _tab = v.first),
                ),
                const SizedBox(height: AppSpace.md),
                if (_tab == 0) const _PendingList() else const _RulesPanel(),
              ],
              const SizedBox(height: AppSpace.xxl),
            ],
          ),
        ),
      ],
    );
  }
}

/// 어떤 사이트를 참조하는지 밝힌다. 랭킹의 출처를 묻는 질문에
/// 화면이 스스로 답할 수 있어야 한다.
class _SourceList extends StatelessWidget {
  const _SourceList();

  static const sources = [
    ('네이버 블로그', 'https://section.blog.naver.com',
        '검색 API. 최신순으로 받아 학원명이 본문에 나온 글만 근거로 씁니다.'),
    ('네이버 카페', 'https://section.cafe.naver.com',
        '검색 API. 공개 글만 받습니다. 로그인이 필요한 카페는 수집하지 않습니다.'),
    ('네이버 지식iN', 'https://kin.naver.com',
        '검색 API. 질문·답변에서 학원 언급을 봅니다.'),
    ('학원실록 자체 후기', '',
        '로그인 후 남긴 후기. 재원 인증분은 신뢰도를 더 높게 줍니다.'),
  ];

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpace.md),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('참조하는 곳', style: text.titleMedium),
          const SizedBox(height: 6),
          for (final (name, url, note) in sources)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Icon(Icons.link, size: 14, color: AppColors.mist),
                const SizedBox(width: 6),
                Expanded(
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        InkWell(
                          onTap: url.isEmpty
                              ? null
                              : () => launchUrl(Uri.parse(url),
                                  webOnlyWindowName: '_blank'),
                          child: Text(name,
                              style: text.labelLarge?.copyWith(
                                  color: url.isEmpty
                                      ? null
                                      : AppColors.navyBright)),
                        ),
                        Text(note, style: text.bodySmall),
                      ]),
                ),
              ]),
            ),
          const SizedBox(height: 6),
          Text(
            'robots.txt 나 콘텐츠 신호로 수집을 거부한 사이트는 참조하지 않습니다. '
            '본문은 저장하지 않고 원문 링크로만 안내합니다.',
            style: text.bodySmall,
          ),
        ]),
      ),
    );
  }
}

class _PendingList extends ConsumerWidget {
  const _PendingList();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final async = ref.watch(pendingReviewsProvider(null));

    return async.when(
      loading: () => const Padding(
        padding: EdgeInsets.all(AppSpace.xl),
        child: Center(child: CircularProgressIndicator()),
      ),
      error: (e, _) => Text('불러오지 못했습니다: $e', style: text.bodyMedium),
      data: (rows) {
        // 같은 글이 여러 학원에 걸리면 화면에서는 하나로 묶는다.
        // 읽기는 한 번, 판정은 학원별로.
        final groups = ReviewGroup.from(rows);
        if (groups.isEmpty) {
          return Padding(
            padding: const EdgeInsets.symmetric(vertical: AppSpace.xl),
            child: Text(
                '검수 대기 글이 없습니다. 다음 수집에서 새 글이 올라옵니다.',
                style: text.bodyMedium),
          );
        }
        return Column(children: [
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpace.sm),
            child: Row(children: [
              Text('글 ${groups.length}건 · 판정 ${rows.length}건',
                  style: text.labelLarge),
              const Spacer(),
              Flexible(
                child: Text('신뢰도가 높은 글부터 — 점수에 영향이 큰 순서입니다',
                    textAlign: TextAlign.right, style: text.bodySmall),
              ),
            ]),
          ),
          for (final g in groups)
            _ReviewTile(key: ValueKey(g.items.first.urlHash), group: g),
        ]);
      },
    );
  }
}

class _ReviewTile extends ConsumerStatefulWidget {
  final ReviewGroup group;
  const _ReviewTile({super.key, required this.group});

  @override
  ConsumerState<_ReviewTile> createState() => _ReviewTileState();
}

class _ReviewTileState extends ConsumerState<_ReviewTile> {
  /// 이미 판정한 항목. 학원별로 따로 눌렀을 때를 위해 남긴다.
  final _judged = <String>{};
  bool _busy = false;

  bool get _done => _judged.length >= widget.group.items.length;

  Future<bool> _judge(String verdict,
      {String? reason, List<String>? only}) async {
    final targets = only ??
        [for (final i in widget.group.items) i.urlHash];
    setState(() => _busy = true);
    try {
      await ref
          .read(adminServiceProvider)
          .judgeMany(targets, verdict, reason: reason);
      if (mounted) {
        setState(() {
          _judged.addAll(targets);
          _busy = false;
        });
      }
      return true;
    } catch (_) {
      if (!mounted) return false;
      setState(() => _busy = false);
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('처리에 실패했습니다.')));
      return false;
    }
  }

  /// 재분류 — 버리지 않고 옮긴다.
  ///
  /// 네 학원을 비교하는 글이 한 곳에만 붙는 일이 있다. 반려밖에 없으면
  /// 멀쩡한 글이 통째로 사라지고, 어느 학원 글인지 사람이 아는 정보도
  /// 함께 사라진다.
  Future<void> _reclassify() async {
    final result = await showModalBottomSheet<_Reassignment>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      constraints: const BoxConstraints(maxWidth: 640),
      builder: (_) => _ReclassifySheet(group: widget.group),
    );
    if (result == null || !mounted) return;

    setState(() => _busy = true);
    try {
      await ref.read(adminServiceProvider).reassign(
            widget.group.items.map((i) => i.urlHash).toList(),
            keep: result.keep,
            targets: result.targets,
          );
      if (!mounted) return;
      // 이 글은 다 처리됐다. _done 은 판정한 항목 수로 정해진다.
      setState(() =>
          _judged.addAll(widget.group.items.map((i) => i.urlHash)));
      ref.invalidate(pendingReviewsProvider);
    } catch (e) {
      if (mounted) setState(() => _busy = false);
    }
  }

  /// 반려하면 사유를 묻고, 이어서 규칙으로 굳힐지 묻는다.
  /// 여기서 규칙이 안 생기면 사람이 같은 글을 영원히 누르게 된다.
  Future<void> _reject() async {
    final reason = await showModalBottomSheet<String>(
      context: context,
      builder: (_) => const _ReasonSheet(),
    );
    if (reason == null || !mounted) return;
    final ok = await _judge('rejected', reason: reason);
    if (!ok || !mounted) return;
    if (reason == 'person' ||
        reason == 'irrelevant' ||
        reason == 'sale' ||
        reason == 'other_region') {
      final made = await showModalBottomSheet<bool>(
        context: context,
        isScrollControlled: true,
        showDragHandle: true,
        constraints: const BoxConstraints(maxWidth: 640),
        builder: (_) => _RuleSheet(group: widget.group, reason: reason),
      );
      if (made == true) ref.invalidate(crawlRulesProvider);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_done) return const SizedBox.shrink();
    final text = Theme.of(context).textTheme;
    final g = widget.group;
    final remaining =
        g.items.where((i) => !_judged.contains(i.urlHash)).toList();

    return Card(
      margin: const EdgeInsets.only(bottom: AppSpace.sm),
      child: Padding(
        padding: const EdgeInsets.all(AppSpace.md),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Wrap(spacing: 6, runSpacing: 4, children: [
            Chip2(g.sourceLabel, color: AppColors.slate),
            if (g.postedAt != null)
              Text('${g.postedAt!.year}.${g.postedAt!.month}.${g.postedAt!.day}',
                  style: text.bodySmall),
          ]),
          const SizedBox(height: 6),
          Text(g.title, style: text.titleMedium),
          if (g.snippet.isNotEmpty) ...[
            const SizedBox(height: 3),
            Text(g.snippet,
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
                style: text.bodyMedium),
          ],
          const SizedBox(height: AppSpace.sm),

          // 이 글이 근거로 붙은 학원들. 한 글이 여러 학원을 언급하면
          // 판정은 학원별이어야 한다 — 한쪽에서 오검출이어도 다른 쪽에서는
          // 정상 근거일 수 있다. 개별로 빼려면 칩의 × 를 누른다.
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('근거로 붙은 학원 ${remaining.length}곳',
                style: text.bodySmall),
            const SizedBox(width: AppSpace.sm),
            Expanded(
              child: Wrap(spacing: 5, runSpacing: 5, children: [
                for (final i in remaining)
                  InputChip(
                    label: Text(
                        i.academyName.isEmpty ? i.academyKey : i.academyName,
                        style: const TextStyle(fontSize: 11.5)),
                    visualDensity: VisualDensity.compact,
                    onDeleted: _busy
                        ? null
                        : () => _judge('rejected',
                            reason: 'different_academy', only: [i.urlHash]),
                    deleteIcon: const Icon(Icons.close, size: 14),
                    tooltip: '이 학원에서만 제외',
                  ),
              ]),
            ),
          ]),

          const SizedBox(height: AppSpace.sm),
          Row(children: [
            if (g.sourceUrl != null)
              TextButton.icon(
                onPressed: () => launchUrl(Uri.parse(g.sourceUrl!),
                    webOnlyWindowName: '_blank'),
                icon: const Icon(Icons.open_in_new, size: 14),
                label: const Text('원문'),
              ),
            const Spacer(),
            TextButton(
              onPressed: _busy ? null : _reclassify,
              child: const Text('재분류'),
            ),
            const SizedBox(width: AppSpace.sm),
            OutlinedButton(
              onPressed: _busy ? null : _reject,
              style:
                  OutlinedButton.styleFrom(foregroundColor: AppColors.rising),
              child: const Text('전체 반려'),
            ),
            const SizedBox(width: AppSpace.sm),
            FilledButton(
              onPressed: _busy ? null : () => _judge('confirmed'),
              child: const Text('전체 확인'),
            ),
          ]),
        ]),
      ),
    );
  }
}

/// 재분류 결과. 남길 학원(검수 키)과 새로 붙일 학원(id)은 별개다 —
/// 넷 중 하나는 맞고 셋이 틀린 경우가 있다.
class _Reassignment {
  final List<String> keep;
  final List<String> targets;
  const _Reassignment({required this.keep, required this.targets});
}

class _ReclassifySheet extends ConsumerStatefulWidget {
  final ReviewGroup group;
  const _ReclassifySheet({required this.group});

  @override
  ConsumerState<_ReclassifySheet> createState() => _ReclassifySheetState();
}

class _ReclassifySheetState extends ConsumerState<_ReclassifySheet> {
  final _query = TextEditingController();
  late final Set<String> _keep = {};      // 검수 키 (url_hash)
  final Set<String> _targets = {};        // 학원 id
  final Map<String, String> _targetNames = {};

  @override
  void dispose() {
    _query.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final data = ref.watch(dataProvider).value;
    final q = _query.text.trim();
    final hits = (data == null || q.length < 2)
        ? const <SearchHit>[]
        : data.search(q).take(8).toList();

    return Padding(
      padding: EdgeInsets.only(
          left: AppSpace.md,
          right: AppSpace.md,
          bottom: MediaQuery.viewInsetsOf(context).bottom + AppSpace.lg),
      child: SingleChildScrollView(
        child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('어느 학원 글인가요', style: text.titleLarge),
              const SizedBox(height: 4),
              Text(
                '반려는 글을 버리지만 재분류는 옮깁니다. 여러 학원을 비교하는 '
                '글이 한 곳에만 붙었을 때, 맞는 학원을 지목하면 다음 수집부터 '
                '그 학원의 근거가 됩니다.',
                style: text.bodySmall,
              ),
              const SizedBox(height: AppSpace.md),

              Text('지금 붙어 있는 학원 — 맞는 것만 남기세요',
                  style: text.labelLarge),
              const SizedBox(height: 6),
              Wrap(spacing: 6, runSpacing: 6, children: [
                for (final i in widget.group.items)
                  FilterChip(
                    label: Text(
                        i.academyName.isEmpty ? i.academyKey : i.academyName,
                        style: const TextStyle(fontSize: 12)),
                    selected: _keep.contains(i.urlHash),
                    onSelected: (on) => setState(() =>
                        on ? _keep.add(i.urlHash) : _keep.remove(i.urlHash)),
                  ),
              ]),
              const SizedBox(height: AppSpace.md),

              Text('이 글의 주인공 학원 찾기', style: text.labelLarge),
              const SizedBox(height: 6),
              TextField(
                controller: _query,
                onChanged: (_) => setState(() {}),
                decoration: const InputDecoration(
                  border: OutlineInputBorder(),
                  isDense: true,
                  prefixIcon: Icon(Icons.search, size: 18),
                  hintText: '학원 이름 (두 글자 이상)',
                ),
              ),
              if (hits.isNotEmpty)
                ConstrainedBox(
                  constraints: const BoxConstraints(maxHeight: 220),
                  child: ListView(
                    shrinkWrap: true,
                    children: [
                      for (final h in hits)
                        ListTile(
                          dense: true,
                          title: Text(h.name),
                          subtitle: Text(
                              data?.regionById[h.regionId]?.nameKo ??
                                  h.regionId),
                          trailing: Icon(
                            _targets.contains(h.id)
                                ? Icons.check_circle
                                : Icons.add_circle_outline,
                            size: 18,
                          ),
                          onTap: () => setState(() {
                            if (!_targets.remove(h.id)) {
                              _targets.add(h.id);
                              _targetNames[h.id] = h.name;
                            }
                          }),
                        ),
                    ],
                  ),
                ),
              if (_targets.isNotEmpty) ...[
                const SizedBox(height: AppSpace.sm),
                Wrap(spacing: 6, runSpacing: 6, children: [
                  for (final id in _targets)
                    InputChip(
                      label: Text(_targetNames[id] ?? id,
                          style: const TextStyle(fontSize: 12)),
                      onDeleted: () => setState(() => _targets.remove(id)),
                      deleteIcon: const Icon(Icons.close, size: 14),
                    ),
                ]),
              ],

              const SizedBox(height: AppSpace.md),
              Row(children: [
                TextButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: const Text('취소'),
                ),
                const Spacer(),
                FilledButton(
                  // 아무것도 안 고르면 전체 반려와 같아진다. 그건 반려
                  // 버튼이 할 일이므로 여기서는 막는다.
                  onPressed: (_keep.isEmpty && _targets.isEmpty)
                      ? null
                      : () => Navigator.of(context).pop(_Reassignment(
                            keep: _keep.toList(),
                            targets: _targets.toList(),
                          )),
                  child: const Text('재분류'),
                ),
              ]),
            ]),
      ),
    );
  }
}

class _ReasonSheet extends StatelessWidget {
  const _ReasonSheet();

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(AppSpace.md),
        child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('왜 근거로 쓸 수 없나요', style: text.titleMedium),
              const SizedBox(height: 4),
              Text('사유는 크롤러 개선에 그대로 쓰입니다.', style: text.bodySmall),
              const SizedBox(height: AppSpace.sm),
              for (final e in rejectReasons.entries)
                ListTile(
                  dense: true,
                  title: Text(e.value),
                  onTap: () => Navigator.of(context).pop(e.key),
                ),
            ]),
      ),
    );
  }
}

/// 우리 4개 권역 밖의 지역어. 반려 사유가 '다른 지역 지점' 일 때
/// 제목에서 찾아 규칙 초안으로 채운다.
///
/// 파이프라인에도 같은 목록이 있지만(analyze.OTHER_REGION_WORDS) 여기 것은
/// **초안을 채우기 위한 것**일 뿐이다. 실제로 거는 규칙은 사람이 확인한
/// 문자열이고, 목록에 없는 지역은 직접 적으면 된다.
const _otherRegionHints = <String>[
  '분당', '평촌', '일산', '동탄', '수지', '판교', '광교', '중계', '노원',
  '부산', '대구', '광주', '대전', '울산', '천안', '세종', '청주', '전주',
  '김포', '용인', '안양', '산본', '화성', '청라', '송도', '인천', '수원',
  '군포', '안산', '시흥', '부천', '광명', '하남', '강동', '도봉', '금천',
  '중랑', '광진', '성동', '용산', '은평', '마포', '성북', '강서', '구로',
  '관악', '동작', '성남', '위례', '고양', '파주', '제주', '창원',
];

/// 반려를 규칙으로 굳히는 시트.
class _RuleSheet extends ConsumerStatefulWidget {
  final ReviewGroup group;
  /// 반려 사유. 사유마다 걸어야 할 규칙의 종류가 다르다.
  final String reason;
  const _RuleSheet({required this.group, this.reason = 'person'});

  @override
  ConsumerState<_RuleSheet> createState() => _RuleSheetState();
}

class _RuleSheetState extends ConsumerState<_RuleSheet> {
  final _pattern = TextEditingController();
  final _reason = TextEditingController();
  String _scope = 'academy';
  bool _busy = false;

  bool get _isRegion => widget.reason == 'other_region';
  String get _kind => _isRegion ? 'exclude_region' : 'exclude_keyword';

  @override
  void initState() {
    super.initState();
    if (!_isRegion) return;
    // 제목에 실제로 나온 지역어만 초안으로 넣는다. 목록 전체를 넣으면
    // 사람이 읽지 않고 저장하게 되고, 그러면 규칙이 아니라 사고가 된다.
    final titles = widget.group.items.map((i) => i.title).join(' ');
    final found = _otherRegionHints.where(titles.contains).toList();
    if (found.isNotEmpty) {
      _pattern.text = found.join('|');
      _reason.text = '${found.first} 지점 글이라 이 학원의 근거가 아님';
    }
  }

  @override
  void dispose() {
    _pattern.dispose();
    _reason.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Padding(
      padding: EdgeInsets.only(
          left: AppSpace.md,
          right: AppSpace.md,
          bottom: MediaQuery.viewInsetsOf(context).bottom + AppSpace.lg),
      child: SingleChildScrollView(
        child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('같은 글이 다시 안 올라오게 할까요', style: text.titleLarge),
              const SizedBox(height: 4),
              Text(
                _isRegion
                    ? '제목에 이 지역이 나오는 글을 다음 수집부터 제외합니다. '
                      '본문이 아니라 제목만 봅니다 — 본문의 지역명은 대개 '
                      '함께 언급된 다른 학원의 상호입니다.'
                    : '이 글에서 걸러야 할 낱말을 적으면 다음 수집부터 제외합니다. '
                      '예: 뮤지컬 배우와 이름이 겹칠 때 "뮤지컬|공연|배우".',
                style: text.bodySmall,
              ),
              const SizedBox(height: AppSpace.md),
              SegmentedButton<String>(
                showSelectedIcon: false,
                segments: [
                  ButtonSegment(
                      value: 'academy',
                      label: Text(widget.group.items.length > 1
                          ? '이 학원들에만'
                          : '${widget.group.academyNames.first}에만')),
                  const ButtonSegment(value: 'global', label: Text('전체에')),
                ],
                selected: {_scope},
                onSelectionChanged: (v) => setState(() => _scope = v.first),
              ),
              const SizedBox(height: AppSpace.md),
              TextField(
                controller: _pattern,
                decoration: InputDecoration(
                  border: const OutlineInputBorder(),
                  labelText: _isRegion
                      ? '제외할 지역 (여러 개는 | 로 구분) *'
                      : '제외할 낱말 (여러 개는 | 로 구분) *',
                  hintText: _isRegion ? '분당|평촌|일산' : '뮤지컬|공연|배우|커튼콜',
                ),
              ),
              const SizedBox(height: AppSpace.sm),
              TextField(
                controller: _reason,
                decoration: InputDecoration(
                  border: const OutlineInputBorder(),
                  labelText: '이유 * — 나중에 이 규칙을 지울지 판단하는 근거',
                  hintText: _isRegion
                      ? '분당 지점 글이라 이 학원의 근거가 아님'
                      : '뮤지컬 배우 윤도영과 학원명이 같아 오검출',
                ),
              ),
              const SizedBox(height: AppSpace.md),
              Row(children: [
                TextButton(
                  onPressed: () => Navigator.of(context).pop(false),
                  child: const Text('규칙 없이 넘어가기'),
                ),
                const Spacer(),
                FilledButton(
                  onPressed: _busy
                      ? null
                      : () async {
                          if (_pattern.text.trim().isEmpty ||
                              _reason.text.trim().isEmpty) {
                            return;
                          }
                          setState(() => _busy = true);
                          try {
                            // 학원 범위면 이 글에 걸린 학원 전부에 건다.
                            // 동명이인 오검출은 대개 그 학원 하나의 문제지만,
                            // 한 글이 여러 학원에 걸렸다면 같은 이유로
                            // 전부 잘못 붙은 것이다.
                            for (final key in _scope == 'academy'
                                ? widget.group.items
                                    .map((i) => i.academyKey)
                                    .toSet()
                                : {null}) {
                              await ref.read(adminServiceProvider).addRule(
                                    kind: _kind,
                                    pattern: _pattern.text.trim(),
                                    reason: _reason.text.trim(),
                                    scope: _scope,
                                    academyKey: key,
                                  );
                            }
                            if (context.mounted) {
                              Navigator.of(context).pop(true);
                            }
                          } catch (_) {
                            if (context.mounted) setState(() => _busy = false);
                          }
                        },
                  child: Text(_busy ? '저장 중…' : '규칙 추가'),
                ),
              ]),
            ]),
      ),
    );
  }
}

class _RulesPanel extends ConsumerWidget {
  const _RulesPanel();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final async = ref.watch(crawlRulesProvider);

    return async.when(
      loading: () => const Padding(
        padding: EdgeInsets.all(AppSpace.xl),
        child: Center(child: CircularProgressIndicator()),
      ),
      error: (e, _) => Text('불러오지 못했습니다: $e', style: text.bodyMedium),
      data: (rules) => Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '검수에서 나온 규칙입니다. 매 수집마다 적용되어 같은 오검출이 '
              '반복되지 않게 합니다. 효과가 없으면 끄면 됩니다.',
              style: text.bodySmall,
            ),
            const SizedBox(height: AppSpace.sm),
            if (rules.isEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: AppSpace.lg),
                child: Text('아직 규칙이 없습니다. 글을 반려하면서 만들어집니다.',
                    style: text.bodyMedium),
              )
            else
              for (final r in rules)
                Card(
                  margin: const EdgeInsets.only(bottom: AppSpace.sm),
                  child: Padding(
                    padding: const EdgeInsets.all(AppSpace.md),
                    child: Row(children: [
                      Expanded(
                        child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Wrap(spacing: 6, children: [
                                Chip2(
                                    r.scope == 'global'
                                        ? '전체'
                                        : (r.academyKey ?? '학원'),
                                    color: AppColors.navy),
                                Text(r.kindLabel, style: text.bodySmall),
                              ]),
                              const SizedBox(height: 4),
                              Text(r.pattern, style: text.titleMedium),
                              Text(r.reason, style: text.bodySmall),
                              if (r.hits > 0)
                                Text('${r.hits}건 걸러냄',
                                    style: text.bodySmall
                                        ?.copyWith(color: AppColors.verified)),
                            ]),
                      ),
                      Switch(
                        value: r.active,
                        onChanged: (v) async {
                          await ref
                              .read(adminServiceProvider)
                              .toggleRule(r.id, v);
                          ref.invalidate(crawlRulesProvider);
                        },
                      ),
                    ]),
                  ),
                ),
          ]),
    );
  }
}

/// 운영자 로그인. 후기와 같은 방식 — 비밀번호를 만들지 않는다.
class _SignIn extends ConsumerStatefulWidget {
  const _SignIn();

  @override
  ConsumerState<_SignIn> createState() => _SignInState();
}

class _SignInState extends ConsumerState<_SignIn> {
  final _email = TextEditingController();
  String? _notice;
  bool _busy = false;

  @override
  void dispose() {
    _email.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpace.md),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('운영자 로그인', style: text.titleMedium),
          const SizedBox(height: 4),
          Text('등록된 운영자 계정만 검수 화면을 볼 수 있습니다.',
              style: text.bodySmall),
          const SizedBox(height: AppSpace.md),
          TextField(
            controller: _email,
            keyboardType: TextInputType.emailAddress,
            decoration: const InputDecoration(
                labelText: '이메일', border: OutlineInputBorder()),
          ),
          if (_notice != null) ...[
            const SizedBox(height: 6),
            Text(_notice!, style: text.bodySmall),
          ],
          const SizedBox(height: AppSpace.sm),
          FilledButton(
            onPressed: _busy
                ? null
                : () async {
                    setState(() { _busy = true; _notice = null; });
                    try {
                      await ref
                          .read(adminServiceProvider)
                          .signIn(_email.text.trim());
                      if (mounted) {
                        setState(() => _notice = '로그인 링크를 보냈습니다.');
                      }
                    } catch (e) {
                      if (mounted) setState(() => _notice = '전송 실패: $e');
                    } finally {
                      if (mounted) setState(() => _busy = false);
                    }
                  },
            child: Text(_busy ? '보내는 중…' : '로그인 링크 받기'),
          ),
        ]),
      ),
    );
  }
}
