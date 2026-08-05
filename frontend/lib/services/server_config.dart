import 'package:flutter/foundation.dart' show kIsWeb, defaultTargetPlatform, TargetPlatform;
import 'package:shared_preferences/shared_preferences.dart';

/// Persists and resolves the backend base URL.
///
/// `127.0.0.1` only ever means "this same device", so a phone can't reach a
/// backend running on your PC through it. The Android emulator's host-loopback
/// alias (`10.0.2.2`) is a reasonable default when running in an emulator, but
/// a real phone on the same Wi-Fi needs the PC's actual LAN IP (see
/// [ServerSettingsScreen] for where that's entered and persisted).
class ServerConfig {
  ServerConfig._();

  static const _prefsKey = 'backend_base_url';
  static const _apiKeyPrefsKey = 'backend_api_key';

  static String defaultBaseUrl() {
    if (kIsWeb) return 'http://127.0.0.1:9000';
    if (defaultTargetPlatform == TargetPlatform.android) return 'http://10.0.2.2:9000';
    return 'http://127.0.0.1:9000';
  }

  static Future<String> loadBaseUrl() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_prefsKey) ?? defaultBaseUrl();
  }

  static Future<void> saveBaseUrl(String url) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_prefsKey, normalize(url));
  }

  /// The X-API-Key header value, if the backend has API_KEY configured.
  /// Null/empty means auth is off (the default) -- see backend/.env.example.
  static Future<String?> loadApiKey() async {
    final prefs = await SharedPreferences.getInstance();
    final value = prefs.getString(_apiKeyPrefsKey);
    return (value == null || value.isEmpty) ? null : value;
  }

  static Future<void> saveApiKey(String? apiKey) async {
    final prefs = await SharedPreferences.getInstance();
    if (apiKey == null || apiKey.trim().isEmpty) {
      await prefs.remove(_apiKeyPrefsKey);
    } else {
      await prefs.setString(_apiKeyPrefsKey, apiKey.trim());
    }
  }

  static String normalize(String url) {
    var value = url.trim();
    if (!value.startsWith('http://') && !value.startsWith('https://')) {
      value = 'http://$value';
    }
    while (value.endsWith('/')) {
      value = value.substring(0, value.length - 1);
    }
    return value;
  }
}
