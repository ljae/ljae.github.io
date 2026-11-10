import 'package:flutter_test/flutter_test.dart';
import 'package:edutree/data/contact_view_model.dart';
import 'package:edutree/data/verified_facts.dart';
void main(){
 const base=ContactViewModel(academyId:'123',branchName:'검증학원',phone:'02-111-2222');
 final now=DateTime.utc(2026,11,10);
 Map<String,dynamic> row()=>{'academy_key':'123','active':true,'source_url':'https://open.neis.go.kr/hub/acaInsTiInfo','checked_at':now.toIso8601String(),'tel':'02-333-4444'};
 test('only a fresh official record belonging to the same branch replaces contact',(){expect(applyVerifiedPhone(base,row(),now).phone,'02-333-4444');for(final invalid in [row()..['academy_key']='124',row()..['active']=false,row()..['source_url']='https://untrusted.example',row()..['checked_at']=now.subtract(const Duration(days:31)).toIso8601String(),row()..['checked_at']=now.add(const Duration(hours:1)).toIso8601String(),row()..['tel']='00000000']) {expect(applyVerifiedPhone(base,invalid,now),same(base));}});
 test('an existing contact dispute remains held after an overlay read',(){const held=ContactViewModel(academyId:'123',branchName:'검증학원',phoneDisputed:true);expect(applyVerifiedPhone(held,row(),now).phone,isNull);});
}
