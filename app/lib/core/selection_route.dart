import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../data/repository.dart';
import '../widgets/content_loading.dart';

const validRegions = {'all', 'daechi', 'mokdong', 'banpo', 'jamsil'};
const validSubjects = {'math', 'english', 'korean', 'science', 'arts', 'etc'};
const validBands = {'elem_low', 'elem_high', 'middle', 'high'};

Selection selectionFromUri(Uri uri, Selection current) {
  final q = uri.queryParameters;
  final track = q['track'] ?? '';
  final split = track.indexOf('_');
  final trackSubject = split < 0 ? null : track.substring(0, split);
  final trackBand = split < 0 ? null : track.substring(split + 1);
  String choose(String? value, Set<String> valid, String fallback) =>
      value == null
      ? fallback
      : valid.contains(value)
      ? value
      : fallback;
  return current.copyWith(
    regionId: choose(q['region'], validRegions, current.regionId),
    subject: choose(
      q['subject'] ?? trackSubject,
      validSubjects,
      current.subject,
    ),
    gradeBand: choose(q['band'] ?? trackBand, validBands, current.gradeBand),
  );
}

/// Apply explicit URL conditions before rendering results; preserve browser history.
class SelectionRoute extends ConsumerStatefulWidget {
  final Uri uri;
  final Widget child;
  const SelectionRoute({super.key, required this.uri, required this.child});

  @override
  ConsumerState<SelectionRoute> createState() => _SelectionRouteState();
}

class _SelectionRouteState extends ConsumerState<SelectionRoute> {
  bool _ready = false;
  bool _applying = false;
  final _bucket = PageStorageBucket();

  @override
  void initState() {
    super.initState();
    _schedule();
  }

  @override
  void didUpdateWidget(covariant SelectionRoute oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.uri != widget.uri) {
      _ready = false;
      _schedule();
    }
  }

  void _schedule() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      _applying = true;
      final current = ref.read(selectionProvider);
      ref
          .read(selectionProvider.notifier)
          .restore(selectionFromUri(widget.uri, current));
      _applying = false;
      setState(() => _ready = true);
    });
  }

  @override
  Widget build(BuildContext context) {
    ref.listen(selectionProvider, (_, next) {
      if (_applying ||
          !_ready ||
          GoRouter.of(context).routeInformationProvider.value.uri != widget.uri) {
        return;
      }
      final params = {
        ...widget.uri.queryParameters,
        'region': next.regionId,
        'subject': next.subject,
        'band': next.gradeBand,
      };
      if (params.containsKey('track')) params['track'] = next.trackId;
      final updated = widget.uri.replace(queryParameters: params);
      if (updated != widget.uri) context.go(updated.toString());
    });
    if (!_ready) return const ContentLoading();
    return PageStorage(
      bucket: _bucket,
      child: KeyedSubtree(
        key: PageStorageKey(widget.uri.toString()),
        child: widget.child,
      ),
    );
  }
}
