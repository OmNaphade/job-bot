import 'package:flutter/material.dart';
import 'package:job_alert_frontend/screens/config_screen.dart';
import 'package:job_alert_frontend/screens/keyword_config_screen.dart';
import 'package:job_alert_frontend/screens/notification_settings_screen.dart';
import 'package:job_alert_frontend/screens/run_history_screen.dart';
import 'package:job_alert_frontend/screens/server_settings_screen.dart';
import 'package:job_alert_frontend/services/auth_service.dart';

/// Single settings home, replacing the four/five separate AppBar icons the
/// home screen used to carry -- keeps the dashboard's own AppBar to just the
/// essentials and gives every settings screen (plus logout) one place to live.
class SettingsHubScreen extends StatelessWidget {
  const SettingsHubScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(
        padding: const EdgeInsets.symmetric(vertical: 8),
        children: [
          if (AuthService.instance.userEmail != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 16),
              child: Row(
                children: [
                  CircleAvatar(
                    radius: 20,
                    backgroundColor: colorScheme.primaryContainer,
                    child: Icon(Icons.person_rounded, color: colorScheme.onPrimaryContainer),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      AuthService.instance.userEmail!,
                      style: const TextStyle(fontWeight: FontWeight.w600),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            ),
          _SettingsTile(
            icon: Icons.tune_rounded,
            title: 'Ingestion sources',
            subtitle: 'RSS feeds, LinkedIn/Naukri/Indeed alerts, poll interval',
            onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const ConfigScreen())),
          ),
          _SettingsTile(
            icon: Icons.filter_alt_outlined,
            title: 'Keyword filters',
            subtitle: 'What counts as a match',
            onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const KeywordConfigScreen())),
          ),
          _SettingsTile(
            icon: Icons.notifications_active_outlined,
            title: 'Notifications',
            subtitle: 'Telegram, Slack, Discord',
            onTap: () =>
                Navigator.of(context).push(MaterialPageRoute(builder: (_) => const NotificationSettingsScreen())),
          ),
          _SettingsTile(
            icon: Icons.history_rounded,
            title: 'Run history',
            subtitle: 'Past ingestion checks',
            onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const RunHistoryScreen())),
          ),
          _SettingsTile(
            icon: Icons.dns_rounded,
            title: 'Server connection',
            subtitle: 'Backend URL',
            onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const ServerSettingsScreen())),
          ),
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 8),
            child: Divider(height: 1),
          ),
          _SettingsTile(
            icon: Icons.logout_rounded,
            title: 'Log out',
            iconColor: colorScheme.error,
            titleColor: colorScheme.error,
            onTap: () => AuthService.instance.logout(),
          ),
        ],
      ),
    );
  }
}

class _SettingsTile extends StatelessWidget {
  const _SettingsTile({
    required this.icon,
    required this.title,
    this.subtitle,
    required this.onTap,
    this.iconColor,
    this.titleColor,
  });

  final IconData icon;
  final String title;
  final String? subtitle;
  final VoidCallback onTap;
  final Color? iconColor;
  final Color? titleColor;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return ListTile(
      leading: Icon(icon, color: iconColor ?? colorScheme.onSurfaceVariant),
      title: Text(title, style: TextStyle(fontWeight: FontWeight.w600, color: titleColor)),
      subtitle: subtitle != null ? Text(subtitle!) : null,
      trailing: Icon(Icons.chevron_right_rounded, color: colorScheme.outline),
      onTap: onTap,
    );
  }
}
