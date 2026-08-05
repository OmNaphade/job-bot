import 'package:flutter/material.dart';
import 'package:job_alert_frontend/models/ingestion_config.dart';
import 'package:job_alert_frontend/services/api_service.dart';
import 'package:job_alert_frontend/widgets/section_label.dart';

class ConfigScreen extends StatefulWidget {
  const ConfigScreen({super.key});

  @override
  State<ConfigScreen> createState() => _ConfigScreenState();
}

class _ConfigScreenState extends State<ConfigScreen> {
  final ApiService _apiService = ApiService.instance;

  bool _loading = true;
  String? _error;
  bool rssEnabled = false;
  bool linkedinEnabled = false;
  bool naukriEnabled = false;
  bool directScrapingEnabled = false;
  int pollIntervalHours = 4;

  @override
  void initState() {
    super.initState();
    _loadConfig();
  }

  Future<void> _loadConfig() async {
    try {
      final json = await _apiService.fetchIngestionSettings();
      final config = IngestionConfig.fromJson(json);
      setState(() {
        rssEnabled = config.enableRssSources;
        linkedinEnabled = config.enableLinkedInAlerts;
        naukriEnabled = config.enableNaukriAlerts;
        directScrapingEnabled = config.allowDirectScraping;
        pollIntervalHours = config.pollIntervalHours;
        _loading = false;
      });
    } catch (error) {
      setState(() {
        _error = 'Failed to load settings: $error';
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(title: const Text('Ingestion Settings')),
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
                const SectionLabel('Sources'),
                Card(
                  margin: EdgeInsets.zero,
                  child: Column(
                    children: [
                      SwitchListTile(
                        title: const Text('RSS / JSON feeds'),
                        subtitle: const Text('WeWorkRemotely, Himalayas, and any feed URLs you configure.'),
                        value: rssEnabled,
                        onChanged: (value) => setState(() => rssEnabled = value),
                      ),
                      const Divider(height: 1),
                      SwitchListTile(
                        title: const Text('LinkedIn alerts'),
                        subtitle: const Text('Reads your saved-search alert emails — never scrapes LinkedIn.'),
                        value: linkedinEnabled,
                        onChanged: (value) => setState(() => linkedinEnabled = value),
                      ),
                      const Divider(height: 1),
                      SwitchListTile(
                        title: const Text('Naukri alerts'),
                        subtitle: const Text('Reads your saved-search alert emails — never scrapes Naukri.'),
                        value: naukriEnabled,
                        onChanged: (value) => setState(() => naukriEnabled = value),
                      ),
                      const Divider(height: 1),
                      SwitchListTile(
                        title: const Text('Allow direct scraping'),
                        subtitle: const Text('Off by default to protect your accounts.'),
                        value: directScrapingEnabled,
                        onChanged: (value) => setState(() => directScrapingEnabled = value),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 20),
                const SectionLabel('Schedule'),
                Card(
                  margin: EdgeInsets.zero,
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            const Text('Poll interval'),
                            Text('$pollIntervalHours h', style: TextStyle(color: colorScheme.primary, fontWeight: FontWeight.w700)),
                          ],
                        ),
                        Slider(
                          value: pollIntervalHours.toDouble(),
                          min: 1,
                          max: 24,
                          divisions: 23,
                          label: '$pollIntervalHours h',
                          onChanged: (value) => setState(() => pollIntervalHours = value.round()),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 24),
                FilledButton.icon(
                  onPressed: _saveConfig,
                  icon: const Icon(Icons.save_rounded),
                  label: const Text('Save configuration'),
                ),
              ],
            ),
    );
  }

  Future<void> _saveConfig() async {
    final config = IngestionConfig(
      enableRssSources: rssEnabled,
      enableLinkedInAlerts: linkedinEnabled,
      enableNaukriAlerts: naukriEnabled,
      allowDirectScraping: directScrapingEnabled,
      pollIntervalHours: pollIntervalHours,
    );

    if (!mounted) return;
    try {
      await _apiService.updateIngestionSettings(config.toJson());
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Configuration saved')));
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed to save configuration: $error')));
    }
  }
}
