import 'academy_detail.dart';
import 'models.dart';

Uri? safeContactUrl(String? value) {
  if (value == null || RegExp(r'[\s\\\x00-\x1f]').hasMatch(value.trim())) {
    return null;
  }
  final uri = Uri.tryParse(value.trim());
  return uri != null &&
          (uri.scheme == 'http' || uri.scheme == 'https') &&
          uri.host.isNotEmpty &&
          uri.userInfo.isEmpty
      ? uri
      : null;
}

String? safePhoneDigits(String? value) {
  if (value == null || !RegExp(r'^\+?[0-9() .-]+$').hasMatch(value.trim())) {
    return null;
  }
  final digits = value.replaceAll(RegExp(r'[^0-9]'), '');
  if (digits.length < 8 ||
      digits.length > 13 ||
      RegExp(r'^(\d)\1+$').hasMatch(digits)) {
    return null;
  }
  if (value.trim().startsWith('+')) {
    return digits.startsWith('82') ? '+$digits' : null;
  }
  if (!(digits.startsWith('0') || digits.length == 8)) return null;
  return digits;
}

/// A contact belongs to one entity. Reading a bundle is not source verification.
class ContactViewModel {
  final String academyId;
  final String branchName;
  final String? address;
  final String? _phone;
  final String? _officialUrl;
  final bool phoneDisputed, homepageDisputed;
  String? get phone =>
      !phoneDisputed && safePhoneDigits(_phone) != null ? _phone : null;
  String? get officialUrl =>
      !homepageDisputed ? safeContactUrl(_officialUrl)?.toString() : null;
  const ContactViewModel({
    required this.academyId,
    required this.branchName,
    this.address,
    String? phone,
    String? officialUrl,
    this.phoneDisputed = false,
    this.homepageDisputed = false,
  }) : _phone = phone,
       _officialUrl = officialUrl;
  factory ContactViewModel.fromAcademy(Academy a) => ContactViewModel(
    academyId: a.id,
    branchName: a.displayName,
    address: a.address,
    phone: safePhoneDigits(a.tel) == null ? null : a.tel!.trim(),
    officialUrl: safeContactUrl(a.homepage)?.toString(),
  );
  factory ContactViewModel.fromDetail(AcademyDetail d) => d.academy != null
      ? ContactViewModel.fromAcademy(d.academy!)
      : ContactViewModel(
          academyId: d.id,
          branchName: d.registry!.displayName,
          address: d.registry!.address,
        );
  bool get hasContact => phone != null || officialUrl != null;
  String get provenance => '수집 자료의 연락처 · 지점별 원출처 대조일과 최근 연결 여부 미확인';
}
