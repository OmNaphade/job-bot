import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:job_alert_frontend/models/user.dart';
import 'package:job_alert_frontend/services/api_service.dart';

/// Holds the current session token/user in memory, persisted via
/// shared_preferences (same mechanism this app already used for the old
/// shared API key) so a login survives app restarts. A ChangeNotifier so the
/// root AuthGate widget can swap between the login flow and the app the
/// moment login/logout/session-expiry happens, without any new
/// state-management dependency.
class AuthService extends ChangeNotifier {
  AuthService._internal();
  static final AuthService instance = AuthService._internal();

  static const _tokenPrefsKey = 'auth_token';
  static const _emailPrefsKey = 'auth_email';

  String? token;
  String? userEmail;

  bool get isLoggedIn => token != null;

  /// Loads any persisted session. Call once at startup before runApp.
  Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    token = prefs.getString(_tokenPrefsKey);
    userEmail = prefs.getString(_emailPrefsKey);
  }

  Future<void> signup(String email, String password, {String? inviteCode}) async {
    final response = await ApiService.instance.signup(email, password, inviteCode: inviteCode);
    await _applySession(response);
  }

  Future<void> login(String email, String password) async {
    final response = await ApiService.instance.login(email, password);
    await _applySession(response);
  }

  Future<void> logout() async {
    if (token != null) {
      try {
        await ApiService.instance.logout();
      } catch (_) {
        // Best-effort server-side revocation -- the local session is cleared
        // either way, so a network hiccup here shouldn't trap the user.
      }
    }
    token = null;
    userEmail = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_tokenPrefsKey);
    await prefs.remove(_emailPrefsKey);
    notifyListeners();
  }

  Future<void> _applySession(Map<String, dynamic> response) async {
    final user = User.fromJson(response['user'] as Map<String, dynamic>);
    token = response['token'] as String;
    userEmail = user.email;

    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_tokenPrefsKey, token!);
    await prefs.setString(_emailPrefsKey, userEmail!);
    notifyListeners();
  }
}
