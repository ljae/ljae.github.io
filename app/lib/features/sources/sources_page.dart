import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme.dart';
import '../../data/source_notes.dart';
import '../../widgets/common.dart';
import '../../widgets/contact.dart';

const sourceTopics = ['입학·레벨테스트', '수업·교재', '숙제', '운영·일정'];

class SourcesPage extends ConsumerStatefulWidget {
  const SourcesPage({super.key});
  @override
  ConsumerState<SourcesPage> createState() => _SourcesPageState();
}

class _SourcesPageState extends ConsumerState<SourcesPage> {
  String topic = sourceTopics.first;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return ref
        .watch(sourceNotesProvider)
        .when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (_, _) => Center(
            child: TextButton(
              onPressed: () => ref.invalidate(sourceNotesProvider),
              child: const Text('자료를 불러오지 못했습니다 · 다시 시도'),
            ),
          ),
          data: (rows) => ListView(
            padding: const EdgeInsets.all(AppSpace.md),
            children: [
              ContentWidth(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('원출처로 비교하기', style: text.headlineLarge),
                    const SizedBox(height: AppSpace.sm),
                    Text(
                      '대치 영어학원 ${rows.length}곳의 공식 안내를 먼저 확인했습니다. '
                      '학교급·학군 공통 필터와 별도로 보는 조사 자료입니다. '
                      '학원의 설명은 학부모의 평가와 구분하며, 점수나 적합성 판단에 쓰지 않습니다.',
                      style: text.bodyMedium,
                    ),
                    const SizedBox(height: AppSpace.md),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        for (final t in sourceTopics)
                          ChoiceChip(
                            label: Text(t),
                            selected: topic == t,
                            onSelected: (_) => setState(() => topic = t),
                          ),
                      ],
                    ),
                    const SizedBox(height: AppSpace.md),
                    LayoutBuilder(
                      builder: (context, box) => Wrap(
                        spacing: AppSpace.md,
                        runSpacing: AppSpace.md,
                        children: [
                          for (final row in rows)
                            SizedBox(
                              width: box.maxWidth >= 800
                                  ? (box.maxWidth - AppSpace.md) / 2
                                  : box.maxWidth,
                              child: SourceNoteCard(
                                sources: row,
                                topic: topic,
                                linkToAcademy: true,
                              ),
                            ),
                        ],
                      ),
                    ),
                    const SizedBox(height: AppSpace.lg),
                    Text('읽는 기준', style: text.titleMedium),
                    const SizedBox(height: AppSpace.sm),
                    const Text(
                      '확인일은 이 페이지를 읽은 날짜이며 게시일과 다릅니다. '
                      '같은 기관의 여러 문서는 독립적인 후기 여러 건이 아닙니다. '
                      '자료가 없다는 표시는 숙제가 없거나 입학이 쉽다는 뜻이 아닙니다. '
                      '반별 과제 시간·피드백·현재 모집 여부는 상담에서 확인해 주세요.',
                    ),
                    TextButton.icon(
                      onPressed: () => openExternal(
                        'https://m.blog.naver.com/greenyulma/224374345103',
                      ),
                      icon: const Icon(Icons.open_in_new, size: 16),
                      label: const Text('구성 참고: 대치 영어학원 정보 요약 (AI 정리 글)'),
                    ),
                    const Text(
                      '참고 블로그의 평가·순위는 옮기지 않았습니다. '
                      '학원별 원문을 확인한 자료만 이 비교 화면에 싣습니다.',
                    ),
                  ],
                ),
              ),
            ],
          ),
        );
  }
}

class AcademySourcePanel extends ConsumerWidget {
  final String academyId;
  const AcademySourcePanel({super.key, required this.academyId});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return ref
        .watch(sourceNotesProvider)
        .when(
          loading: () => const SizedBox.shrink(),
          error: (_, _) => TextButton(
            onPressed: () => ref.invalidate(sourceNotesProvider),
            child: const Text('공식 자료 다시 불러오기'),
          ),
          data: (rows) {
            final sources = rows
                .where((r) => r.academyId == academyId)
                .firstOrNull;
            if (sources == null) return const SizedBox.shrink();
            return Padding(
              padding: const EdgeInsets.only(bottom: AppSpace.xl),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const SectionHeader(
                    '공식 안내에서 확인한 것',
                    subtitle: '학원 자기 서술 · 후기 요약과 구분해 읽어 주세요.',
                  ),
                  SourceNoteCard(sources: sources),
                  TextButton(
                    onPressed: () => context.push('/sources'),
                    child: const Text('다른 학원과 항목별 비교 →'),
                  ),
                ],
              ),
            );
          },
        );
  }
}

class SourceNoteCard extends StatelessWidget {
  final AcademySources sources;
  final String? topic;
  final bool linkToAcademy;
  const SourceNoteCard({
    super.key,
    required this.sources,
    this.topic,
    this.linkToAcademy = false,
  });

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final notes = sources.notes
        .where((n) => topic == null || n.topic == topic)
        .toList();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpace.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(sources.name, style: text.titleLarge),
            Text(sources.scope, style: text.bodySmall),
            const SizedBox(height: AppSpace.sm),
            if (notes.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: AppSpace.lg),
                child: Text('확인한 자료 없음\n반별 안내와 실제 소요 시간을 상담에서 확인해 주세요.'),
              ),
            for (final note in notes) ...[
              const Divider(),
              Text('${note.topic} · 학원 공식 안내', style: text.labelMedium),
              const SizedBox(height: 6),
              Text(note.summary, style: text.bodyMedium),
              const SizedBox(height: 6),
              Text(
                '게시 ${note.publishedAt ?? "일자 미상"} · 확인 ${note.checkedAt}',
                style: text.bodySmall,
              ),
              TextButton.icon(
                onPressed: () => openExternal(note.url),
                icon: const Icon(Icons.open_in_new, size: 16),
                label: Text('${note.title} ↗\n${Uri.parse(note.url).host}'),
              ),
            ],
            const Divider(),
            Text(sources.caveat, style: text.bodySmall),
            if (linkToAcademy)
              TextButton(
                onPressed: () => context.push('/academy/${sources.academyId}'),
                child: const Text('등록 정보와 후기 보기 →'),
              ),
          ],
        ),
      ),
    );
  }
}
