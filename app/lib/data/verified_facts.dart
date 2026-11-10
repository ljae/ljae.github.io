import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../core/env.dart';
import 'contact_view_model.dart';

ContactViewModel applyVerifiedPhone(
  ContactViewModel base,
  Map<String, dynamic>? row,
  DateTime now,
) {
  if (row == null ||
      row['academy_key'] != base.academyId ||
      row['active'] != true ||
      row['source_url'] != 'https://open.neis.go.kr/hub/acaInsTiInfo') {
    return base;
  }
  final checked = DateTime.tryParse('${row['checked_at']}');
  final phone = row['tel'] as String?;
  if (checked == null ||
      checked.isAfter(now.add(const Duration(minutes: 1))) ||
      checked.isBefore(now.subtract(const Duration(days: 30))) ||
      safePhoneDigits(phone) == null) {
    return base;
  }
  return ContactViewModel(
    academyId: base.academyId,
    branchName: base.branchName,
    address: base.address,
    phone: phone,
    officialUrl: base.officialUrl,
    phoneDisputed: base.phoneDisputed,
    homepageDisputed: base.homepageDisputed,
    verifiedAt: checked,
  );
}

final verifiedPhoneProvider = FutureProvider.autoDispose
    .family<Map<String, dynamic>?, String>((ref, id) async {
      if (!Env.hasSupabase || !RegExp(r'^\d{1,20}$').hasMatch(id)) return null;
      final timer = Timer(const Duration(minutes: 1), ref.invalidateSelf);
      ref.onDispose(timer.cancel);
      try {
        return await Supabase.instance.client
            .from('verified_academy_facts')
            .select('academy_key,tel,source_url,checked_at,active')
            .eq('academy_key', id)
            .eq('active', true)
            .maybeSingle()
            .timeout(const Duration(seconds: 2));
      } catch (_) {
        return null;
      } // Keep the dated bundle; never invent a verified value.
    });
