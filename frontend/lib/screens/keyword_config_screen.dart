import 'package:flutter/material.dart';
import 'package:job_alert_frontend/services/api_service.dart';
import 'package:job_alert_frontend/widgets/section_label.dart';

class KeywordConfigScreen extends StatefulWidget {
  const KeywordConfigScreen({super.key});

  @override
  State<KeywordConfigScreen> createState() => _KeywordConfigScreenState();
}

class _KeywordConfigScreenState extends State<KeywordConfigScreen> {
  final ApiService _apiService = ApiService.instance;
  final TextEditingController _includeController = TextEditingController();
  final TextEditingController _excludeController = TextEditingController();

  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadPreferences();
  }

  Future<void> _loadPreferences() async {
    try {
      final preferences = await _apiService.fetchPreferences();
      final include = preferences.where((p) => p['kind'] == 'include').map((p) => p['keyword'] as String).toList();
      final exclude = preferences.where((p) => p['kind'] == 'exclude').map((p) => p['keyword'] as String).toList();
      setState(() {
        _includeController.text = include.join(', ');
        _excludeController.text = exclude.join(', ');
        _loading = false;
      });
    } catch (error) {
      setState(() {
        _error = 'Failed to load saved keywords: $error';
        _loading = false;
      });
    }
  }

  Future<void> _saveConfig() async {
    final includeKeywords = _includeController.text.split(',').map((value) => value.trim()).where((value) => value.isNotEmpty).toList();
    final excludeKeywords = _excludeController.text.split(',').map((value) => value.trim()).where((value) => value.isNotEmpty).toList();

    try {
      await _apiService.updateKeywords(includeKeywords, excludeKeywords);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Keywords updated')));
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed to update keywords: $error')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(title: const Text('Keyword Filters')),
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
                const SectionLabel('Include (any match is enough)'),
                TextField(
                  controller: _includeController,
                  maxLines: 3,
                  decoration: const InputDecoration(hintText: 'backend, full stack, python, spring boot'),
                ),
                const SizedBox(height: 20),
                const SectionLabel('Exclude (blocks a match)'),
                TextField(
                  controller: _excludeController,
                  maxLines: 3,
                  decoration: const InputDecoration(hintText: 'senior, staff, principal, manager'),
                ),
                const SizedBox(height: 8),
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  child: Text(
                    'Comma-separated. Matched against the job title, company, and location.',
                    style: TextStyle(fontSize: 12, color: colorScheme.onSurfaceVariant),
                  ),
                ),
                const SizedBox(height: 16),
                FilledButton.icon(
                  onPressed: _saveConfig,
                  icon: const Icon(Icons.save_rounded),
                  label: const Text('Save keyword filters'),
                ),
              ],
            ),
    );
  }
}
