import 'package:flutter/material.dart';
import 'package:job_alert_frontend/models/notification_settings.dart';
import 'package:job_alert_frontend/services/api_service.dart';
import 'package:job_alert_frontend/widgets/section_label.dart';

class NotificationSettingsScreen extends StatefulWidget {
  const NotificationSettingsScreen({super.key});

  @override
  State<NotificationSettingsScreen> createState() => _NotificationSettingsScreenState();
}

class _NotificationSettingsScreenState extends State<NotificationSettingsScreen> {
  final ApiService _apiService = ApiService.instance;
  final _telegramTokenController = TextEditingController();
  final _telegramChatIdController = TextEditingController();
  final _slackWebhookController = TextEditingController();
  final _discordWebhookController = TextEditingController();

  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _telegramTokenController.dispose();
    _telegramChatIdController.dispose();
    _slackWebhookController.dispose();
    _discordWebhookController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final json = await _apiService.fetchNotificationSettings();
      final settings = NotificationSettings.fromJson(json);
      setState(() {
        _telegramTokenController.text = settings.telegramBotToken ?? '';
        _telegramChatIdController.text = settings.telegramChatId ?? '';
        _slackWebhookController.text = settings.slackWebhookUrl ?? '';
        _discordWebhookController.text = settings.discordWebhookUrl ?? '';
        _loading = false;
      });
    } catch (error) {
      setState(() {
        _error = 'Failed to load notification settings: $error';
        _loading = false;
      });
    }
  }

  Future<void> _save() async {
    final settings = NotificationSettings(
      telegramBotToken: _telegramTokenController.text,
      telegramChatId: _telegramChatIdController.text,
      slackWebhookUrl: _slackWebhookController.text,
      discordWebhookUrl: _discordWebhookController.text,
    );
    try {
      await _apiService.updateNotificationSettings(settings.toJson());
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Notification settings saved')));
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed to save: $error')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(title: const Text('Notifications')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
              children: [
                if (_error != null)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Text(_error!, style: TextStyle(color: colorScheme.error)),
                  ),
                Text(
                  'Alerts go to every channel you configure below — leave any of them blank to skip that channel.',
                  style: TextStyle(fontSize: 12, color: colorScheme.onSurfaceVariant),
                ),
                const SizedBox(height: 20),
                const SectionLabel('Telegram'),
                TextField(
                  controller: _telegramTokenController,
                  decoration: const InputDecoration(labelText: 'Bot token', hintText: 'From @BotFather'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _telegramChatIdController,
                  decoration: const InputDecoration(labelText: 'Chat ID'),
                ),
                const SizedBox(height: 20),
                const SectionLabel('Slack'),
                TextField(
                  controller: _slackWebhookController,
                  decoration: const InputDecoration(labelText: 'Incoming webhook URL'),
                ),
                const SizedBox(height: 20),
                const SectionLabel('Discord'),
                TextField(
                  controller: _discordWebhookController,
                  decoration: const InputDecoration(labelText: 'Channel webhook URL'),
                ),
                const SizedBox(height: 24),
                FilledButton.icon(
                  onPressed: _save,
                  icon: const Icon(Icons.save_rounded),
                  label: const Text('Save notification settings'),
                ),
              ],
            ),
    );
  }
}
