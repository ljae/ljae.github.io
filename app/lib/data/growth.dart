import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../core/env.dart';
import 'admin.dart';

class GrowthService {
  final SupabaseClient? db;
  const GrowthService(this.db);

  Future<List<Map<String, dynamic>>> reports() async {
    if (db == null) return [];
    final rows = await db!
        .from('growth_reports')
        .select(
          'id,property,source,search_type,range_start,range_end,imported_at',
        )
        .order('range_end', ascending: false)
        .order('range_start', ascending: false)
        .order('imported_at', ascending: false)
        .limit(50);
    return rows.map((r) => Map<String, dynamic>.from(r)).toList();
  }

  Future<Map<String, dynamic>> overview(String id) async =>
      await db!.rpc<Map<String, dynamic>>(
        'growth_overview',
        params: {'p_snapshot_id': id},
      );

  Future<List<Map<String, dynamic>>> tasks(int page) async {
    final rows = await db!
        .from('growth_tasks')
        .select()
        .order('severity')
        .order('impact_impressions', ascending: false)
        .order('id')
        .range(page * 25, page * 25 + 24);
    return rows.map((r) => Map<String, dynamic>.from(r)).toList();
  }

  Future<void> transition(
    Map<String, dynamic> task,
    String state,
    String note,
  ) async {
    await db!.rpc<dynamic>(
      'growth_transition_task',
      params: {
        'p_task_id': task['id'],
        'p_expected_version': task['version'],
        'p_target_state': state,
        'p_note': note,
      },
    );
  }

  Future<void> recordChange(
    String taskId,
    String commit,
    String deployId,
    String url,
  ) async {
    await db!.rpc<dynamic>(
      'growth_record_change',
      params: {
        'p_task_id': taskId,
        'p_commit_sha': commit,
        'p_deploy_id': deployId,
        'p_verification_url': url,
      },
    );
  }

  Future<List<Map<String, dynamic>>> experiments() async {
    final rows = await db!
        .from('growth_experiments')
        .select()
        .order('created_at', ascending: false)
        .limit(50);
    return rows.map((r) => Map<String, dynamic>.from(r)).toList();
  }

  Future<void> createExperiment(
    String hypothesis,
    List<String> treatment,
    List<String> control,
  ) async {
    await db!.rpc<dynamic>(
      'growth_create_experiment',
      params: {
        'p_property': 'sc-domain:openedu4u.com',
        'p_hypothesis': hypothesis,
        'p_treatment_urls': treatment,
        'p_control_urls': control,
        'p_primary_metric': 'clicks',
      },
    );
  }
}

final growthServiceProvider = Provider<GrowthService>(
  (ref) => GrowthService(Env.hasSupabase ? Supabase.instance.client : null),
);

/// Recheck authorization and discard report caches when the signed-in account changes.
final growthAuthIdentityProvider = StreamProvider<String?>((ref) async* {
  if (!Env.hasSupabase) {
    yield null;
    return;
  }
  final auth = Supabase.instance.client.auth;
  yield auth.currentUser?.id;
  yield* auth.onAuthStateChange
      .map((event) => event.session?.user.id)
      .distinct();
});

final growthAccessProvider = FutureProvider<bool>((ref) async {
  final user = await ref.watch(growthAuthIdentityProvider.future);
  if (user == null) return false;
  return ref.watch(adminServiceProvider).isAdmin();
});

// Fetch only after an affirmative admin check, including when providers are read directly.
Future<void> requireGrowthAdmin(Ref ref) async {
  if (!await ref.watch(growthAccessProvider.future)) {
    throw StateError('ADMIN_REQUIRED');
  }
}

final growthReportsProvider = FutureProvider<List<Map<String, dynamic>>>((
  ref,
) async {
  await requireGrowthAdmin(ref);
  return ref.watch(growthServiceProvider).reports();
});
final growthOverviewProvider =
    FutureProvider.family<Map<String, dynamic>, String>((ref, id) async {
      await requireGrowthAdmin(ref);
      return ref.watch(growthServiceProvider).overview(id);
    });
final growthTasksProvider =
    FutureProvider.family<List<Map<String, dynamic>>, int>((ref, page) async {
      await requireGrowthAdmin(ref);
      return ref.watch(growthServiceProvider).tasks(page);
    });
final growthExperimentsProvider = FutureProvider<List<Map<String, dynamic>>>((
  ref,
) async {
  await requireGrowthAdmin(ref);
  return ref.watch(growthServiceProvider).experiments();
});
