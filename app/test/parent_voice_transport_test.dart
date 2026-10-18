import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:edutree/data/parent_voice.dart';

void main() {
  test('real Supabase SDK empty 204 deletion clears the receipt', () async {
    final client = SupabaseClient(
      'https://test.invalid',
      'public-test-key',
      httpClient: MockClient((request) async {
        expect(request.url.path, '/functions/v1/parent-voice/delete');
        expect(request.url.query, isEmpty);
        expect(
          (jsonDecode(request.body) as Map)['receiptId'],
          '00000000-0000-4000-8000-000000000001',
        );
        return http.Response(
          '',
          204,
          headers: {'content-type': 'application/json; charset=utf-8'},
        );
      }),
    );
    addTearDown(client.dispose);
    final service = ParentVoiceService(parentVoiceRequest(client));
    service.remember('00000000-0000-4000-8000-000000000001.${'a' * 43}');
    await service.delete();
    expect(service.lastCode, isNull);
  });
}
