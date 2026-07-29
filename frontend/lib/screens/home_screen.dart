import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:job_alert_frontend/screens/config_screen.dart';
import 'package:job_alert_frontend/screens/keyword_config_screen.dart';
import 'package:job_alert_frontend/services/api_service.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final ApiService _apiService = ApiService();
  late Future<List<dynamic>> _jobsFuture;
  bool _runningIngestion = false;

  @override
  void initState() {
    super.initState();
    _jobsFuture = _apiService.fetchJobs();
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Job Alerts'),
        actions: [
          IconButton(
            tooltip: 'Ingestion settings',
            icon: const Icon(Icons.tune_rounded),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const ConfigScreen()),
            ),
          ),
          IconButton(
            tooltip: 'Keyword filters',
            icon: const Icon(Icons.filter_alt_outlined),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const KeywordConfigScreen()),
            ),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          final future = _apiService.fetchJobs();
          setState(() => _jobsFuture = future);
          await future;
        },
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
              child: SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  onPressed: _runningIngestion ? null : _runIngestion,
                  icon: _runningIngestion
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                        )
                      : const Icon(Icons.sync_rounded),
                  label: Text(_runningIngestion ? 'Checking now…' : 'Check for new jobs now'),
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.bolt_rounded, size: 16, color: colorScheme.tertiary),
                  const SizedBox(width: 4),
                  Expanded(
                    child: Text(
                      'The bot also checks automatically in the background — this is just for right now.',
                      style: TextStyle(fontSize: 12, color: colorScheme.onSurfaceVariant),
                    ),
                  ),
                ],
              ),
            ),
            Expanded(
              child: FutureBuilder<List<dynamic>>(
                future: _jobsFuture,
                builder: (context, snapshot) {
                  if (snapshot.connectionState == ConnectionState.waiting) {
                    return const Center(child: CircularProgressIndicator());
                  }
                  if (snapshot.hasError) {
                    return _ErrorState(error: snapshot.error.toString(), onRetry: _reload);
                  }
                  final jobs = snapshot.data ?? [];
                  if (jobs.isEmpty) {
                    return const _EmptyState();
                  }
                  return ListView.builder(
                    padding: const EdgeInsets.only(bottom: 88, top: 4),
                    itemCount: jobs.length,
                    itemBuilder: (context, index) => _JobCard(job: jobs[index] as Map<String, dynamic>),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _reload() {
    setState(() => _jobsFuture = _apiService.fetchJobs());
  }

  Future<void> _runIngestion() async {
    setState(() => _runningIngestion = true);
    try {
      final result = await _apiService.runIngestion();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            '${result['matched']} matched · ${result['new']} new · ${result['delivered']} sent to Telegram',
          ),
        ),
      );
      _reload();
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed to run ingestion: $error')));
    } finally {
      if (mounted) setState(() => _runningIngestion = false);
    }
  }
}

class _JobCard extends StatelessWidget {
  const _JobCard({required this.job});

  final Map<String, dynamic> job;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final source = (job['source'] as String?) ?? 'unknown';
    final title = (job['title'] as String?) ?? 'Untitled';
    final company = (job['company'] as String?) ?? '-';
    final location = (job['location'] as String?) ?? '-';
    final link = job['link'] as String?;

    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: link == null ? null : () => _copyLink(context, link),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              CircleAvatar(
                radius: 20,
                backgroundColor: _sourceColor(source, colorScheme).withValues(alpha: 0.16),
                child: Text(
                  company.isNotEmpty ? company[0].toUpperCase() : '?',
                  style: TextStyle(color: _sourceColor(source, colorScheme), fontWeight: FontWeight.w700),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15)),
                    const SizedBox(height: 4),
                    Text(
                      '$company · $location',
                      style: TextStyle(color: colorScheme.onSurfaceVariant, fontSize: 13),
                    ),
                    const SizedBox(height: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: _sourceColor(source, colorScheme).withValues(alpha: 0.14),
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: Text(
                        _sourceLabel(source),
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          color: _sourceColor(source, colorScheme),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              if (link != null)
                IconButton(
                  tooltip: 'Copy link',
                  icon: const Icon(Icons.copy_rounded, size: 18),
                  onPressed: () => _copyLink(context, link),
                ),
            ],
          ),
        ),
      ),
    );
  }

  void _copyLink(BuildContext context, String link) {
    Clipboard.setData(ClipboardData(text: link));
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Link copied')));
  }

  String _sourceLabel(String source) {
    const labels = {
      'weworkremotely': 'We Work Remotely',
      'himalayas': 'Himalayas',
      'unstop': 'Unstop',
      'foundit': 'Foundit',
      'linkedin_alerts': 'LinkedIn',
      'naukri_alerts': 'Naukri',
      'manual': 'Manual',
      'sample': 'Sample',
    };
    return labels[source] ?? source;
  }

  Color _sourceColor(String source, ColorScheme colorScheme) {
    const palette = {
      'weworkremotely': Color(0xFF2563EB),
      'himalayas': Color(0xFF0891B2),
      'unstop': Color(0xFFEA580C),
      'foundit': Color(0xFF9333EA),
      'linkedin_alerts': Color(0xFF0A66C2),
      'naukri_alerts': Color(0xFFDB2777),
      'manual': Color(0xFF64748B),
    };
    return palette[source] ?? colorScheme.primary;
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.work_outline_rounded, size: 56, color: colorScheme.outline),
            const SizedBox(height: 16),
            Text(
              'No jobs yet',
              style: TextStyle(fontSize: 17, fontWeight: FontWeight.w600, color: colorScheme.onSurface),
            ),
            const SizedBox(height: 8),
            Text(
              'Turn on a source in settings and add some keyword filters — new matches will show up here and on Telegram.',
              textAlign: TextAlign.center,
              style: TextStyle(color: colorScheme.onSurfaceVariant),
            ),
          ],
        ),
      ),
    );
  }
}

class _ErrorState extends StatelessWidget {
  const _ErrorState({required this.error, required this.onRetry});

  final String error;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.error_outline_rounded, size: 48, color: colorScheme.error),
            const SizedBox(height: 12),
            Text('Couldn\'t reach the backend', style: TextStyle(fontWeight: FontWeight.w600, color: colorScheme.onSurface)),
            const SizedBox(height: 4),
            Text(error, textAlign: TextAlign.center, style: TextStyle(color: colorScheme.onSurfaceVariant, fontSize: 12)),
            const SizedBox(height: 16),
            OutlinedButton.icon(onPressed: onRetry, icon: const Icon(Icons.refresh_rounded), label: const Text('Retry')),
          ],
        ),
      ),
    );
  }
}
