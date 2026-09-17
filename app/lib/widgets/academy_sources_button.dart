import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../data/source_notes.dart';

/// 특징을 뒷받침하는 자료는 학원 안에서만 펼쳐 본다.
class AcademySourcesButton extends StatelessWidget {
  final AcademySources sources;
  final String? subject;
  const AcademySourcesButton({super.key, required this.sources, this.subject});

  @override
  Widget build(BuildContext context) {
    final notes = sources.notes.where((n) => n.supports(subject)).toList();
    if (notes.isEmpty) return const SizedBox.shrink();
    return TextButton.icon(
      icon: const Icon(Icons.source_outlined, size: 15),
      label: Text('확인한 출처 ${notes.map((n) => n.url).toSet().length}개'),
      style: TextButton.styleFrom(padding: EdgeInsets.zero),
      onPressed: () => showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        showDragHandle: true,
        builder: (context) => SafeArea(
          child: SizedBox(
            height: MediaQuery.sizeOf(context).height * .7,
            child: ListView(
              padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
              children: [
                Text(
                  '${sources.name} · 확인한 출처',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 12),
                Text(sources.scope),
                const SizedBox(height: 8),
                Text(
                  sources.caveat,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                for (final note in notes) ...[
                  const Divider(height: 32),
                  Text(
                    '${note.topic} · ${note.sourceLabel}',
                    style: Theme.of(context).textTheme.labelMedium,
                  ),
                  const SizedBox(height: 8),
                  Text(note.summary),
                  const SizedBox(height: 8),
                  Text(
                    '확인 ${note.checkedAt}${note.publishedAt == null ? '' : ' · 게시 ${note.publishedAt}'}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                  TextButton.icon(
                    onPressed: () async {
                      final uri = Uri.tryParse(note.url);
                      if (uri == null ||
                          !['https', 'http'].contains(uri.scheme)) {
                        return;
                      }
                      final opened = await launchUrl(
                        uri,
                        mode: LaunchMode.externalApplication,
                        webOnlyWindowName: '_blank',
                      );
                      if (!opened && context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text('출처를 열지 못했습니다. 잠시 후 다시 시도해주세요.'),
                          ),
                        );
                      }
                    },
                    icon: const Icon(Icons.open_in_new, size: 16),
                    label: Text(note.title),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
