import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'models.dart';
import 'repository.dart';

/// A registry record is a detail with public facts, not a zero-score Academy.
class AcademyDetail {
  final Academy? academy;
  final RegistryEntry? registry;

  const AcademyDetail.evaluated(Academy value)
    : academy = value,
      registry = null;
  const AcademyDetail.listed(RegistryEntry value)
    : registry = value,
      academy = null;

  String get id => academy?.id ?? registry!.id;
}

final academyDetailProvider = FutureProvider.family<AcademyDetail?, String>((
  ref,
  id,
) async {
  final data = await ref.watch(dataProvider.future);
  final direct = data.academies.where((a) => a.id == id).firstOrNull;
  if (direct != null) return AcademyDetail.evaluated(direct);
  // Wait for the registry before declaring a URL missing. Keep errors retryable.
  final registry = await ref.watch(registryProvider.future);
  final listed = registry.where((a) => a.id == id).firstOrNull;
  if (listed != null) return AcademyDetail.listed(listed);
  final merged = data.academyById[id];
  if (merged != null) return AcademyDetail.evaluated(merged);
  final listedAlias = registry
      .where((a) => a.registrationIds.contains(id))
      .firstOrNull;
  return listedAlias == null ? null : AcademyDetail.listed(listedAlias);
});
