import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:edutree/data/corrections.dart';
import 'package:edutree/data/browser_store.dart' as store;

void main() {
  test(
    'an uncertain submission retries the same capability and status reveals only the reply',
    () async {
      store.writeSession('correction.receipt.v1', null);
      final sent = <Map<String, dynamic>>[];
      final client = SupabaseClient(
        'https://test.invalid',
        'public-test-key',
        httpClient: MockClient((request) async {
          final body = Map<String, dynamic>.from(
            jsonDecode(request.body) as Map,
          );
          if (request.url.path.endsWith('/correction_submit_ai')) {
            sent.add(body);
            if (sent.length == 1) {
              throw http.ClientException('synthetic interrupted response');
            }
            return http.Response(
              jsonEncode({
                'id': body['p_id'],
                'status': 'received',
                'reply': null,
              }),
              200,
              headers: {'content-type': 'application/json'},
            );
          }
          expect(request.url.path, '/rest/v1/rpc/correction_receipt_ai');
          expect(body.keys.toSet(), {'p_id', 'p_secret'});
          return http.Response(
            '{"status":"reviewing","reply":"학원실록 AI 검토: 확인 중입니다."}',
            200,
            headers: {'content-type': 'application/json'},
          );
        }),
      );
      addTearDown(client.dispose);
      final service = CorrectionService(client);
      Future<void> submit() => service.submit(
        academyKey: '123',
        academyName: '검증학원',
        requester: 'test',
        contact: 'test@example.invalid',
        kind: 'fix',
        message: '공개된 전화번호를 확인해 주세요.',
      );
      await expectLater(submit(), throwsA(isA<http.ClientException>()));
      expect(service.hasReceiptFor('123'), false);
      await submit();
      expect(sent.length, 2);
      expect(sent[0], sent[1]);
      expect((sent[0]['p_secret'] as String).length, 43);
      final stored = store.readSession('correction.receipt.v1')!;
      expect(stored, isNot(contains('test@example.invalid')));
      expect(stored, isNot(contains('전화번호')));
      expect((await service.status('123'))['reply'], contains('학원실록 AI'));
      await expectLater(service.status('124'), throwsStateError);
      expect(CorrectionService(client).hasReceiptFor('123'), true);
      store.writeSession('correction.receipt.v1', null);
    },
  );
}
