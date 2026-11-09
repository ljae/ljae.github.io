import 'package:flutter/material.dart';

/// Dataset publication time is not a review's publication or verification date.
class RankingDataNotice extends StatelessWidget {
  const RankingDataNotice({super.key, required this.generatedAt, this.now});
  final String generatedAt;
  final DateTime? now;

  @override
  Widget build(BuildContext context) {
    final date = DateTime.tryParse(generatedAt)?.toLocal();
    final clock = now ?? DateTime.now();
    final valid = date != null && !date.isAfter(clock);
    final stale = valid && clock.difference(date).inDays >= 3;
    final dateLabel = valid
        ? '${date.year}.${date.month.toString().padLeft(2, '0')}.${date.day.toString().padLeft(2, '0')}'
        : '확인 필요';
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 12),
      child: Text(
        '자료 생성일 $dateLabel${stale ? ' · 갱신 지연' : ''}\n'
        '${!valid || stale ? '현재 모집 학년·수업·연락처는 해당 지점에 확인해 주세요.\n' : ''}'
        '순위는 후기와 공개자료의 비교 기준입니다. 아이에게 맞는지는 2~3곳을 비교하고 상담으로 확인해 주세요.',
        style: Theme.of(context).textTheme.bodySmall,
      ),
    );
  }
}
