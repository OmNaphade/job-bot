import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiService {
  static const String baseUrl = 'http://127.0.0.1:9000';

  Future<List<dynamic>> fetchJobs() async {
    final response = await http.get(Uri.parse('$baseUrl/jobs'));
    if (response.statusCode != 200) {
      throw Exception('Failed to fetch jobs: ${response.statusCode} ${response.reasonPhrase}');
    }
    return jsonDecode(response.body) as List<dynamic>;
  }

  Future<Map<String, dynamic>> addJob(Map<String, dynamic> payload) async {
    final response = await http.post(
      Uri.parse('$baseUrl/jobs'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(payload),
    );
    if (response.statusCode != 200) {
      throw Exception('Failed to create job: ${response.statusCode} ${response.reasonPhrase}');
    }
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> runIngestion() async {
    final response = await http.post(Uri.parse('$baseUrl/ingest'));
    if (response.statusCode != 200) {
      throw Exception('Failed to run ingestion: ${response.statusCode} ${response.reasonPhrase}');
    }
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<List<dynamic>> fetchPreferences() async {
    final response = await http.get(Uri.parse('$baseUrl/preferences'));
    if (response.statusCode != 200) {
      throw Exception('Failed to fetch preferences: ${response.statusCode} ${response.reasonPhrase}');
    }
    return jsonDecode(response.body) as List<dynamic>;
  }

  Future<Map<String, dynamic>> updateKeywords(List<String> includeKeywords, List<String> excludeKeywords) async {
    final response = await http.post(
      Uri.parse('$baseUrl/ingest/keywords'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'include_keywords': includeKeywords, 'exclude_keywords': excludeKeywords}),
    );
    if (response.statusCode != 200) {
      throw Exception('Failed to update keywords: ${response.statusCode} ${response.reasonPhrase}');
    }
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> fetchIngestionSettings() async {
    final response = await http.get(Uri.parse('$baseUrl/ingestion/settings'));
    if (response.statusCode != 200) {
      throw Exception('Failed to fetch ingestion settings: ${response.statusCode} ${response.reasonPhrase}');
    }
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> updateIngestionSettings(Map<String, dynamic> payload) async {
    final response = await http.put(
      Uri.parse('$baseUrl/ingestion/settings'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(payload),
    );
    if (response.statusCode != 200) {
      throw Exception('Failed to update ingestion settings: ${response.statusCode} ${response.reasonPhrase}');
    }
    return jsonDecode(response.body) as Map<String, dynamic>;
  }
}
