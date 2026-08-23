import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/env.dart';
import '../../core/theme.dart';
import '../../data/models.dart';
import '../../data/reviews.dart';
import '../../widgets/common.dart';

/// 학원실록 자체 후기 영역.
///
/// 커뮤니티에서 모은 '근거'와 구분해서 보여준다. 이쪽은 로그인한 학부모가
/// 별점과 관점을 구조화해 남긴 것이고, 저쪽은 공개 글에서 신호만 뽑은 것이다.
/// 둘을 같은 목록에 섞으면 어느 쪽이 검증된 것인지 알 수 없게 된다.
/// 후기 목록에 걸린 필터. 화면을 벗어나면 사라지는 값이라 화면에 둔다.
class ReviewFilter {
  final String? band;
  final String? subject;
  const ReviewFilter({this.band, this.subject});

  @override
  bool operator ==(Object other) =>
      other is ReviewFilter && other.band == band && other.subject == subject;

  @override
  int get hashCode => Object.hash(band, subject);
}

class ReviewFilterNotifier extends Notifier<ReviewFilter> {
  @override
  ReviewFilter build() => const ReviewFilter();

  void setBand(String? v) => state = ReviewFilter(band: v, subject: state.subject);
  void setSubject(String? v) => state = ReviewFilter(band: state.band, subject: v);
}

final reviewFilterProvider =
    NotifierProvider<ReviewFilterNotifier, ReviewFilter>(
        ReviewFilterNotifier.new);

class ReviewSection extends ConsumerWidget {
  final String academyId;
  final String academyName;
  const ReviewSection(
      {super.key, required this.academyId, required this.academyName});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (!Env.hasSupabase) return const SizedBox.shrink();

    final text = Theme.of(context).textTheme;
    final async = ref.watch(reviewsProvider(academyId));
    final service = ref.watch(reviewServiceProvider);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SectionHeader('학원실록 후기',
            subtitle: '로그인한 학부모가 직접 남긴 후기입니다. 커뮤니티에서 수집한 근거와 구분해 표시합니다.',
            trailing: FilledButton.icon(
              onPressed: () => _openForm(context, ref),
              icon: const Icon(Icons.edit_outlined, size: 16),
              label: Text(service.signedIn ? '후기 쓰기' : '로그인하고 쓰기'),
            )),
        async.when(
          loading: () => const Padding(
            padding: EdgeInsets.all(AppSpace.lg),
            child: Center(child: CircularProgressIndicator()),
          ),
          error: (e, _) => Text('후기를 불러오지 못했습니다', style: text.bodyMedium),
          data: (rows) => rows.isEmpty
              ? Card(
                  child: Padding(
                    padding: const EdgeInsets.all(AppSpace.lg),
                    child: Row(children: [
                      const Icon(Icons.rate_review_outlined,
                          size: 18, color: AppColors.mist),
                      const SizedBox(width: AppSpace.sm),
                      Expanded(
                        child: Text(
                          '아직 후기가 없습니다. 첫 후기를 남겨 주세요 — '
                          '다니셨던 기간과 구체적인 경험이 담긴 글일수록 다른 학부모에게 도움이 됩니다.',
                          style: text.bodyMedium,
                        ),
                      ),
                    ]),
                  ),
                )
              : _FilteredReviews(rows: rows),
        ),
      ],
    );
  }

  void _openForm(BuildContext context, WidgetRef ref) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      constraints: const BoxConstraints(maxWidth: 640),
      builder: (_) => _ReviewForm(academyId: academyId, academyName: academyName),
    );
  }
}

class _ReviewTile extends ConsumerWidget {
  final UserReview review;
  const _ReviewTile({super.key, required this.review});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    return Card(
      margin: const EdgeInsets.only(bottom: AppSpace.sm),
      child: Padding(
        padding: const EdgeInsets.all(AppSpace.md),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            for (var i = 0; i < 5; i++)
              Icon(i < review.rating ? Icons.star_rounded : Icons.star_outline_rounded,
                  size: 16, color: AppColors.gold),
            const SizedBox(width: AppSpace.sm),
            Text(review.nickname, style: text.labelLarge),
            if (review.verified) ...[
              const SizedBox(width: 6),
              const Chip2('재원 확인', color: AppColors.verified,
                  icon: Icons.verified_rounded),
            ],
            if (review.isMine) ...[
              const SizedBox(width: 6),
              const Chip2('내 후기', color: AppColors.navy),
              if (!review.verified) ...[
                const SizedBox(width: 6),
                _VerifyButton(reviewId: review.id),
              ],
            ],
            const Spacer(),
            Text('${review.createdAt.year}.${review.createdAt.month}.${review.createdAt.day}',
                style: text.bodySmall),
          ]),
          const SizedBox(height: AppSpace.sm),
          Text(review.body, style: text.bodyLarge),
          if (review.gradeBand != null ||
              review.subject != null ||
              review.tags.isNotEmpty) ...[
            const SizedBox(height: 6),
            Wrap(spacing: 5, runSpacing: 5, children: [
              if (review.gradeBand != null)
                Chip2(gradeBandNames[review.gradeBand] ?? review.gradeBand!,
                    color: AppColors.navyBright),
              if (review.subject != null)
                Chip2(subjectNames[review.subject] ?? review.subject!,
                    color: AppColors.transparency),
              for (final t in review.tags)
                Chip2(t.replaceAll('_', ' '), color: AppColors.mist),
            ]),
          ],
          if (review.aspects.isNotEmpty) ...[
            const SizedBox(height: AppSpace.sm),
            Wrap(spacing: 6, runSpacing: 6, children: [
              for (final e in review.aspects.entries)
                Chip2('${e.key} ${e.value}',
                    color: AppColors.reputation),
            ]),
          ],
        ]),
      ),
    );
  }
}

class _ReviewForm extends ConsumerStatefulWidget {
  final String academyId;
  final String academyName;
  const _ReviewForm({required this.academyId, required this.academyName});

  @override
  ConsumerState<_ReviewForm> createState() => _ReviewFormState();
}

class _ReviewFormState extends ConsumerState<_ReviewForm> {
  final _body = TextEditingController();
  final _email = TextEditingController();
  int _rating = 5;
  final _aspects = <String, int>{};
  String? _gradeBand;
  String? _subject;
  final _tags = <String>{};
  bool _busy = false;
  String? _notice;

  static const aspectKeys = ['강사', '관리', '커리큘럼', '가격', '숙제량'];

  // supabase/06 의 valid_review_tags 어휘와 같아야 한다.
  // 자유 태그를 받지 않는 이유: 곧바로 스팸·홍보 통로가 된다.
  static const tagKeys = [
    '숙제량_많음', '숙제량_적음', '관리_꼼꼼', '피드백_빠름', '레테_어려움',
    '분위기_엄격', '분위기_자유로움', '시설_좋음', '셔틀_운행', '상담_친절',
    '교재_자체', '선행_위주', '내신_위주', '소수정예', '대형강의',
  ];

  @override
  void dispose() {
    _body.dispose();
    _email.dispose();
    super.dispose();
  }

  Future<void> _sendLink() async {
    if (!_email.text.contains('@')) {
      setState(() => _notice = '이메일 주소를 확인해 주세요');
      return;
    }
    setState(() => _busy = true);
    try {
      await ref.read(reviewServiceProvider).signInWithEmail(_email.text.trim());
      setState(() => _notice = '로그인 링크를 보냈습니다. 메일함을 확인해 주세요.');
    } catch (e) {
      setState(() => _notice = '전송 실패: $e');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _submit() async {
    if (_body.text.trim().length < 20) {
      setState(() => _notice = '20자 이상 적어 주세요. 짧은 글은 다른 학부모에게 도움이 되지 않습니다.');
      return;
    }
    setState(() => _busy = true);
    try {
      await ref.read(reviewServiceProvider).submit(
            academyId: widget.academyId,
            rating: _rating,
            body: _body.text.trim(),
            aspects: _aspects,
            gradeBand: _gradeBand,
            subject: _subject,
            tags: _tags.toList(),
          );
      ref.invalidate(reviewsProvider(widget.academyId));
      if (mounted) Navigator.of(context).pop();
    } catch (e) {
      setState(() => _notice = '등록 실패: $e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final signedIn = ref.watch(reviewServiceProvider).signedIn;

    return Padding(
      padding: EdgeInsets.fromLTRB(AppSpace.lg, 0, AppSpace.lg,
          MediaQuery.viewInsetsOf(context).bottom + AppSpace.lg),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(widget.academyName, style: text.headlineMedium),
            Text(signedIn ? '후기 남기기' : '로그인이 필요합니다', style: text.bodyMedium),
            const SizedBox(height: AppSpace.lg),

            if (!signedIn) ...[
              Text('이메일로 로그인 링크를 보내드립니다. 비밀번호는 만들지 않습니다.',
                  style: text.bodyMedium),
              const SizedBox(height: AppSpace.sm),
              TextField(
                controller: _email,
                keyboardType: TextInputType.emailAddress,
                decoration: const InputDecoration(
                    labelText: '이메일', border: OutlineInputBorder()),
              ),
              const SizedBox(height: AppSpace.md),
              FilledButton(
                onPressed: _busy ? null : _sendLink,
                child: Text(_busy ? '보내는 중…' : '로그인 링크 받기'),
              ),
            ] else ...[
              Row(children: [
                for (var i = 1; i <= 5; i++)
                  IconButton(
                    onPressed: () => setState(() => _rating = i),
                    icon: Icon(
                        i <= _rating
                            ? Icons.star_rounded
                            : Icons.star_outline_rounded,
                        color: AppColors.gold, size: 30),
                  ),
                const SizedBox(width: AppSpace.sm),
                Text('$_rating점', style: text.titleMedium),
              ]),
              const SizedBox(height: AppSpace.sm),
              // 학년·과목을 붙이면 나중에 '초2 수학 후기'만 걸러 볼 수 있다.
              Text('자녀 학년 (선택)', style: text.labelMedium),
              const SizedBox(height: 6),
              Wrap(spacing: 6, runSpacing: 6, children: [
                for (final e in gradeBandNames.entries)
                  ChoiceChip(
                    label: Text(e.value),
                    selected: _gradeBand == e.key,
                    onSelected: (v) =>
                        setState(() => _gradeBand = v ? e.key : null),
                  ),
              ]),
              const SizedBox(height: AppSpace.sm),
              Text('과목 (선택)', style: text.labelMedium),
              const SizedBox(height: 6),
              Wrap(spacing: 6, runSpacing: 6, children: [
                for (final e in subjectNames.entries)
                  if (e.key != 'etc')
                    ChoiceChip(
                      label: Text(e.value),
                      selected: _subject == e.key,
                      onSelected: (v) =>
                          setState(() => _subject = v ? e.key : null),
                    ),
              ]),
              const SizedBox(height: AppSpace.sm),
              Text('키워드 (최대 5개)', style: text.labelMedium),
              const SizedBox(height: 6),
              Wrap(spacing: 6, runSpacing: 6, children: [
                for (final k in tagKeys)
                  FilterChip(
                    label: Text(k.replaceAll('_', ' ')),
                    selected: _tags.contains(k),
                    onSelected: (v) => setState(() {
                      if (v && _tags.length < 5) {
                        _tags.add(k);
                      } else {
                        _tags.remove(k);
                      }
                    }),
                  ),
              ]),
              const SizedBox(height: AppSpace.sm),
              Text('관점별 평가 (선택)', style: text.labelMedium),
              const SizedBox(height: 6),
              Wrap(spacing: 6, runSpacing: 6, children: [
                for (final k in aspectKeys)
                  FilterChip(
                    label: Text(_aspects.containsKey(k) ? '$k 좋음' : k),
                    selected: _aspects.containsKey(k),
                    onSelected: (v) => setState(() {
                      if (v) {
                        _aspects[k] = 1;
                      } else {
                        _aspects.remove(k);
                      }
                    }),
                  ),
              ]),
              const SizedBox(height: AppSpace.md),
              TextField(
                controller: _body,
                maxLines: 6,
                decoration: const InputDecoration(
                  labelText: '어떤 점이 좋았고 어떤 점이 아쉬웠나요? (20자 이상)',
                  helperText: '다니신 기간과 구체적인 경험이 담길수록 도움이 됩니다',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: AppSpace.md),
              FilledButton(
                onPressed: _busy ? null : _submit,
                child: Text(_busy ? '등록 중…' : '후기 등록'),
              ),
            ],

            if (_notice != null) ...[
              const SizedBox(height: AppSpace.md),
              Text(_notice!,
                  style: text.bodyMedium?.copyWith(color: AppColors.estimated)),
            ],
            const SizedBox(height: AppSpace.md),
            Text(
              '후기는 실명 사업자에 대한 평가입니다. 사실과 다른 내용이나 비방은 '
              '삭제될 수 있습니다. 학원 관계자는 후기를 작성할 수 없습니다.',
              style: text.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}

/// 학년·과목으로 후기를 걸러 본다.
///
/// 후기가 쌓이면 '우리 아이와 같은 구간' 글만 보고 싶어진다. 초6 학부모의
/// 후기와 예비초 학부모의 후기는 같은 학원이라도 다른 이야기다.
/// 후기가 적을 때 필터 줄이 먼저 보이면 허전하므로 4건부터 내놓는다.
class _FilteredReviews extends ConsumerWidget {
  final List<UserReview> rows;
  const _FilteredReviews({required this.rows});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    final f = ref.watch(reviewFilterProvider);
    final notifier = ref.read(reviewFilterProvider.notifier);

    // 실제로 달린 값만 선택지로 내놓는다. 없는 구간을 눌러 빈 화면을
    // 보게 만들 이유가 없다.
    final bands = <String>{for (final r in rows) ?r.gradeBand};
    final subjects = <String>{for (final r in rows) ?r.subject};
    final showFilter = rows.length >= 4 && (bands.length > 1 || subjects.length > 1);

    final shown = rows.where((r) =>
        (f.band == null || r.gradeBand == f.band) &&
        (f.subject == null || r.subject == f.subject)).toList();

    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      if (showFilter) ...[
        Wrap(spacing: 6, runSpacing: 6, children: [
          for (final b in gradeBandNames.keys)
            if (bands.contains(b))
              FilterChip(
                label: Text(gradeBandNames[b]!),
                selected: f.band == b,
                onSelected: (v) => notifier.setBand(v ? b : null),
              ),
          for (final sub in subjectNames.keys)
            if (subjects.contains(sub))
              FilterChip(
                label: Text(subjectNames[sub]!),
                selected: f.subject == sub,
                onSelected: (v) => notifier.setSubject(v ? sub : null),
              ),
        ]),
        const SizedBox(height: AppSpace.sm),
      ],
      if (shown.isEmpty)
        Padding(
          padding: const EdgeInsets.symmetric(vertical: AppSpace.lg),
          child: Text('이 조건에 맞는 후기가 아직 없습니다.',
              style: text.bodyMedium),
        )
      else
        for (final r in shown) _ReviewTile(key: ValueKey(r.id), review: r),
    ]);
  }
}

/// 내 후기에 붙는 재원 인증 요청 버튼.
///
/// 증빙 이미지는 받지 않는다 — 영수증에는 이름·연락처가 함께 찍히고,
/// 확인이 끝나면 남길 이유가 없는 정보다. 요청만 남기고 운영자가
/// 개별 연락으로 확인한다. 사진을 서버에 쌓아 두는 쪽이 더 쉬웠겠지만,
/// 쌓아 둘 이유가 없는 개인정보는 애초에 받지 않는 편이 맞다.
class _VerifyButton extends ConsumerStatefulWidget {
  final String reviewId;
  const _VerifyButton({required this.reviewId});

  @override
  ConsumerState<_VerifyButton> createState() => _VerifyButtonState();
}

class _VerifyButtonState extends ConsumerState<_VerifyButton> {
  bool _sent = false;
  bool _busy = false;

  @override
  Widget build(BuildContext context) {
    if (_sent) {
      return const Chip2('인증 확인 중', color: AppColors.estimated);
    }
    return TextButton(
      onPressed: _busy ? null : () async {
        setState(() => _busy = true);
        try {
          await ref.read(reviewServiceProvider).requestVerification(widget.reviewId);
          if (mounted) setState(() => _sent = true);
        } catch (_) {
          if (!context.mounted) return;
          setState(() => _busy = false);
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
              content: Text('요청에 실패했습니다. 잠시 후 다시 시도해 주세요.')));
        }
      },
      style: TextButton.styleFrom(
        padding: const EdgeInsets.symmetric(horizontal: 8),
        minimumSize: Size.zero,
        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
        textStyle: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w600),
      ),
      child: Text(_busy ? '요청 중…' : '재원 인증 요청'),
    );
  }
}
