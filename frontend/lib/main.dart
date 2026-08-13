import 'package:flutter/material.dart';
import 'package:job_alert_frontend/screens/home_screen.dart';
import 'package:job_alert_frontend/screens/login_screen.dart';
import 'package:job_alert_frontend/services/api_service.dart';
import 'package:job_alert_frontend/services/auth_service.dart';
import 'package:job_alert_frontend/theme/app_theme.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await ApiService.instance.init();
  await AuthService.instance.init();
  runApp(const JobAlertApp());
}

class JobAlertApp extends StatelessWidget {
  const JobAlertApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Job Alert',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      darkTheme: AppTheme.dark(),
      themeMode: ThemeMode.system,
      home: const AuthGate(),
    );
  }
}

/// Swaps between the login flow and the app the moment AuthService's session
/// state changes (login, signup, logout, or a 401 forcing a logout) --
/// listens via AuthService's own ChangeNotifier, no routing package needed.
class AuthGate extends StatefulWidget {
  const AuthGate({super.key});

  @override
  State<AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<AuthGate> {
  @override
  void initState() {
    super.initState();
    AuthService.instance.addListener(_onAuthChanged);
  }

  @override
  void dispose() {
    AuthService.instance.removeListener(_onAuthChanged);
    super.dispose();
  }

  void _onAuthChanged() {
    if (mounted) setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    return AuthService.instance.isLoggedIn ? const HomeScreen() : const LoginScreen();
  }
}
