import 'package:flutter/material.dart';
import 'package:job_alert_frontend/services/api_service.dart';
import 'package:job_alert_frontend/services/server_config.dart';
import 'package:job_alert_frontend/widgets/section_label.dart';

class ServerSettingsScreen extends StatefulWidget {
  const ServerSettingsScreen({super.key});

  @override
  State<ServerSettingsScreen> createState() => _ServerSettingsScreenState();
}

class _ServerSettingsScreenState extends State<ServerSettingsScreen> {
  final ApiService _apiService = ApiService.instance;
  late final TextEditingController _urlController;
  late final TextEditingController _apiKeyController;

  bool _testing = false;
  bool? _lastTestOk;
  bool _obscureApiKey = true;

  @override
  void initState() {
    super.initState();
    _urlController = TextEditingController(text: _apiService.baseUrl);
    _apiKeyController = TextEditingController(text: _apiService.apiKey ?? '');
  }

  @override
  void dispose() {
    _urlController.dispose();
    _apiKeyController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(title: const Text('Server Connection')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
        children: [
          const SectionLabel('Backend URL'),
          TextField(
            controller: _urlController,
            keyboardType: TextInputType.url,
            decoration: const InputDecoration(hintText: 'http://192.168.1.42:9000'),
            onChanged: (_) => setState(() => _lastTestOk = null),
          ),
          const SizedBox(height: 8),
          Text(
            "On a real phone, 127.0.0.1/localhost means the phone itself — it can never reach a backend "
            "running on your PC. Use your PC's LAN IP instead: on Windows run `ipconfig` and look for "
            "the IPv4 address (e.g. 192.168.1.42), then start the backend with "
            "`uvicorn main:app --host 0.0.0.0 --port 9000` so it accepts connections from other devices. "
            "Your phone and PC must be on the same Wi-Fi network, and Windows Firewall may need to allow "
            "inbound connections on port 9000.",
            style: TextStyle(fontSize: 12, color: colorScheme.onSurfaceVariant),
          ),
          const SizedBox(height: 20),
          const SectionLabel('API Key (optional)'),
          TextField(
            controller: _apiKeyController,
            obscureText: _obscureApiKey,
            decoration: InputDecoration(
              hintText: 'Only needed if the backend has API_KEY set',
              suffixIcon: IconButton(
                icon: Icon(_obscureApiKey ? Icons.visibility_rounded : Icons.visibility_off_rounded),
                onPressed: () => setState(() => _obscureApiKey = !_obscureApiKey),
              ),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Leave blank unless you set API_KEY in the backend\'s .env — required once the backend '
            'is reachable beyond 127.0.0.1, so anyone on the same network can\'t use it without this key.',
            style: TextStyle(fontSize: 12, color: colorScheme.onSurfaceVariant),
          ),
          const SizedBox(height: 20),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _testing ? null : _testConnection,
                  icon: _testing
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.network_check_rounded),
                  label: Text(_testing ? 'Testing…' : 'Test connection'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: FilledButton.icon(
                  onPressed: _save,
                  icon: const Icon(Icons.save_rounded),
                  label: const Text('Save'),
                ),
              ),
            ],
          ),
          if (_lastTestOk != null) ...[
            const SizedBox(height: 16),
            Row(
              children: [
                Icon(
                  _lastTestOk! ? Icons.check_circle_rounded : Icons.error_rounded,
                  color: _lastTestOk! ? Colors.green : colorScheme.error,
                  size: 18,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    _lastTestOk! ? 'Reached the backend successfully.' : "Couldn't reach the backend at this URL.",
                    style: TextStyle(color: _lastTestOk! ? Colors.green : colorScheme.error),
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }

  Future<void> _testConnection() async {
    setState(() {
      _testing = true;
      _lastTestOk = null;
    });
    final ok = await _apiService.checkHealth(url: ServerConfig.normalize(_urlController.text));
    if (!mounted) return;
    setState(() {
      _testing = false;
      _lastTestOk = ok;
    });
  }

  Future<void> _save() async {
    await _apiService.setBaseUrl(_urlController.text);
    await _apiService.setApiKey(_apiKeyController.text);
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Server connection saved')),
    );
    Navigator.of(context).pop(true);
  }
}
