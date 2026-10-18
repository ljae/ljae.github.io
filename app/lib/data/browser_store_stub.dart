final _public = <String, String>{};
final _session = <String, String>{};
String? readPublic(String key) => _public[key];
bool writePublic(String key, String value) {
  _public[key] = value;
  return true;
}

String? readSession(String key) => _session[key];
bool writeSession(String key, String? value) {
  if (value == null) {
    _session.remove(key);
  } else {
    _session[key] = value;
  }
  return true;
}
