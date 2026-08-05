import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:job_alert_frontend/services/server_config.dart';

class ApiService {
  ApiService._internal();

  static final ApiService instance = ApiService._internal();

  static const _timeout = Duration(seconds: 10);

  String baseUrl = ServerConfig.defaultBaseUrl();
  String? apiKey;

  /// Loads the persisted backend URL/API key (or platform default). Call
  /// once at startup before the first screen makes a request.
  Future<void> init() async {
    baseUrl = await ServerConfig.loadBaseUrl();
    apiKey = await ServerConfig.loadApiKey();
  }

  Future<void> setBaseUrl(String url) async {
    final normalized = ServerConfig.normalize(url);
    await ServerConfig.saveBaseUrl(normalized);
    baseUrl = normalized;
  }

  Future<void> setApiKey(String? key) async {
    await ServerConfig.saveApiKey(key);
    apiKey = (key == null || key.trim().isEmpty) ? null : key.trim();
  }

  Future<bool> checkHealth({String? url}) async {
    try {
      final response = await http.get(Uri.parse('${url ?? baseUrl}/health')).timeout(_timeout);
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

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
    return {
      if (json) 'Content-Type': 'application/json',
      if (apiKey != null) 'X-API-Key': apiKey!,
    };
  }

  void _checkOk(http.Response response, String action) {
    if (response.statusCode == 401) {
      throw Exception('Failed to $action: 401 unauthorized — check the API key in Server Connection');
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception('Failed to $action: ${response.statusCode} ${response.reasonPhrase}');
    }
  }
}
