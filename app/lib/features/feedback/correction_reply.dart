import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../data/corrections.dart';

class CorrectionReplyPanel extends ConsumerStatefulWidget {
  final String academyKey;
  const CorrectionReplyPanel({super.key, required this.academyKey});
  @override
  ConsumerState<CorrectionReplyPanel> createState() =>
      _CorrectionReplyPanelState();
}

class _CorrectionReplyPanelState extends ConsumerState<CorrectionReplyPanel> {
  String? _reply;
  String? _error;
  bool _busy = false;
  Future<void> _refresh() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final r = await ref
          .read(correctionServiceProvider)
          .status(widget.academyKey);
      if (mounted) setState(() => _reply = r['reply'] as String?);
    } catch (_) {
      if (mounted) setState(() => _error = '답변을 불러오지 못했습니다. 다시 확인해주세요.');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        _reply ??
            '정정 요청을 접수했습니다. AI가 공개 근거를 검토합니다. 확인된 단순 정보는 반영하고, 근거가 부족하거나 서로 다르면 담당자가 확인합니다.',
      ),
      const SizedBox(height: 8),
      const Text('이 기기에서 다시 열어 답변을 확인할 수 있습니다. 연락처와 요청 원문은 공개되지 않습니다.'),
      if (_error != null) Text(_error!),
      OutlinedButton(
        onPressed: _busy ? null : _refresh,
        child: Text(_busy ? '확인 중…' : 'AI 답변 확인'),
      ),
    ],
  );
}
