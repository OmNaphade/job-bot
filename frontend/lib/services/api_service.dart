import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:job_alert_frontend/services/auth_service.dart';
import 'package:job_alert_frontend/services/server_config.dart';

class ApiService {
  ApiService._internal();

  static final ApiService instance = ApiService._internal();

  static const _timeout = Duration(seconds: 10);

  String baseUrl = ServerConfig.defaultBaseUrl();

  /// Loads the persisted backend URL (or platform default). Call once at
  /// startup before the first screen makes a request.
  Future<void> init() async {
    baseUrl = await ServerConfig.loadBaseUrl();
  }

  Future<void> setBaseUrl(String url) async {
    final normalized = ServerConfig.normalize(url);
    await ServerConfig.saveBaseUrl(normalized);
    baseUrl = normalized;
  }

  Future<bool> checkHealth({String? url}) async {
    try {
      final response = await http.get(Uri.parse('${url ?? baseUrl}/health')).timeout(_timeout);
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  // --- Auth ---

  Future<Map<String, dynamic>> signup(String email, String password, {String? inviteCode}) async {
    final response = await http
        .post(
          Uri.parse('$baseUrl/auth/signup'),
          headers: _headers(json: true),
          body: jsonEncode({
            'email': email,
            'password': password,
            if (inviteCode != null && inviteCode.trim().isNotEmpty) 'invite_code': inviteCode.trim(),
          }),
        )
        .timeout(_timeout);
    _checkAuthOk(response, 'sign up');
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> login(String email, String password) async {
    final response = await http
        .post(
          Uri.parse('$baseUrl/auth/login'),
          headers: _headers(json: true),
          body: jsonEncode({'email': email, 'password': password}),
        )
        .timeout(_timeout);
    _checkAuthOk(response, 'log in');
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<void> logout() async {
    await http.post(Uri.parse('$baseUrl/auth/logout'), headers: _headers()).timeout(_timeout);
  }

  // --- Jobs / preferences / ingestion ---

  Future<List<dynamic>> fetchJobs() async {
    final response = await _get('/jobs');
    return jsonDecode(response.body) as List<dynamic>;
  }

  Future<Map<String, dynamic>> addJob(Map<String, dynamic> payload) async {
    final response = await _post('/jobs', payload);
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> runIngestion() async {
    final response = await http
        .post(Uri.parse('$baseUrl/ingest'), headers: _headers())
        .timeout(const Duration(seconds: 60));
    _checkOk(response, 'run ingestion');
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<List<dynamic>> fetchPreferences() async {
    final response = await _get('/preferences');
    return jsonDecode(response.body) as List<dynamic>;
  }

  Future<Map<String, dynamic>> updateKeywords(List<String> includeKeywords, List<String> excludeKeywords) async {
    final response = await _post('/ingest/keywords', {
      'include_keywords': includeKeywords,
      'exclude_keywords': excludeKeywords,
    });
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> fetchIngestionSettings() async {
    final response = await _get('/ingestion/settings');
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> updateIngestionSettings(Map<String, dynamic> payload) async {
    final response = await http
        .put(
          Uri.parse('$baseUrl/ingestion/settings'),
          headers: _headers(json: true),
          body: jsonEncode(payload),
        )
        .timeout(_timeout);
    _checkOk(response, 'update ingestion settings');
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> fetchNotificationSettings() async {
    final response = await _get('/notification-settings');
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> updateNotificationSettings(Map<String, dynamic> payload) async {
    final response = await http
        .put(
          Uri.parse('$baseUrl/notification-settings'),
          headers: _headers(json: true),
          body: jsonEncode(payload),
        )
        .timeout(_timeout);
    _checkOk(response, 'update notification settings');
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<List<dynamic>> fetchIngestionRuns({int limit = 20}) async {
    final response = await _get('/ingestion/runs?limit=$limit');
    return jsonDecode(response.body) as List<dynamic>;
  }

  Future<http.Response> _get(String path) async {
    final response = await http.get(Uri.parse('$baseUrl$path'), headers: _headers()).timeout(_timeout);
    _checkOk(response, 'GET $path');
    return response;
  }

  Future<http.Response> _post(String path, Map<String, dynamic> payload) async {
    final response = await http
        .post(
          Uri.parse('$baseUrl$path'),
          headers: _headers(json: true),
          body: jsonEncode(payload),
        )
        .timeout(_timeout);
    _checkOk(response, 'POST $path');
    return response;
  }

  Map<String, String> _headers({bool json = false}) {
    final token = AuthService.instance.token;
    return {
      if (json) 'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
  }

  /// For already-authenticated endpoints: a 401 here means the session
  /// expired or was revoked server-side, so it drops the user back to the
  /// login screen (via AuthService.logout()'s listeners) instead of showing
  /// a generic error they have no way to act on.
  void _checkOk(http.Response response, String action) {
    if (response.statusCode == 401) {
      AuthService.instance.logout();
      throw Exception('Your session expired — please log in again');
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception('Failed to $action: ${_extractDetail(response)}');
    }
  }

  /// For the signup/login endpoints themselves: a 401/403/409 here is a
  /// normal "wrong password" / "invite code required" / "email taken"
  /// outcome, not a session expiring -- must not trigger a logout loop.
  void _checkAuthOk(http.Response response, String action) {
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception(_extractDetail(response));
    }
  }

  String _extractDetail(http.Response response) {
    try {
      final body = jsonDecode(response.body);
      if (body is Map && body['detail'] != null) return body['detail'].toString();
    } catch (_) {
      // fall through to the generic status line below
    }
    return '${response.statusCode} ${response.reasonPhrase}';
  }
}
