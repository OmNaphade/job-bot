import 'package:flutter/material.dart';
import 'package:job_alert_frontend/services/api_service.dart';

class RunHistoryScreen extends StatefulWidget {
  const RunHistoryScreen({super.key});

  @override
  State<RunHistoryScreen> createState() => _RunHistoryScreenState();
}

class _RunHistoryScreenState extends State<RunHistoryScreen> {
  final ApiService _apiService = ApiService.instance;
  late Future<List<dynamic>> _runsFuture;

  @override
  void initState() {
    super.initState();
    _runsFuture = _apiService.fetchIngestionRuns();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Ingestion Run History')),
      body: RefreshIndicator(
        onRefresh: () async {
          final future = _apiService.fetchIngestionRuns();
          setState(() => _runsFuture = future);
          await future;
        },
        child: FutureBuilder<List<dynamic>>(
          future: _runsFuture,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snapshot.hasError) {
              return _ErrorState(error: snapshot.error.toString());
            }
            final runs = snapshot.data ?? [];
            if (runs.isEmpty) {
              return const _EmptyState();
            }
            return ListView.builder(
              padding: const EdgeInsets.symmetric(vertical: 8),
              itemCount: runs.length,
              itemBuilder: (context, index) => _RunCard(run: runs[index] as Map<String, dynamic>),
            );
          },
        ),
      ),
    );
  }
}

class _RunCard extends StatelessWidget {
  const _RunCard({required this.run});

  final Map<String, dynamic> run;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final status = (run['status'] as String?) ?? 'unknown';
    final isSuccess = status == 'success';
    final startedAt = (run['started_at'] as String?) ?? '';
    final errorMessage = run['error_message'] as String?;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  isSuccess ? Icons.check_circle_rounded : Icons.error_rounded,
                  color: isSuccess ? Colors.green : colorScheme.error,
                  size: 18,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    _formatTimestamp(startedAt),
                    style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: (isSuccess ? Colors.green : colorScheme.error).withValues(alpha: 0.14),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    status,
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: isSuccess ? Colors.green : colorScheme.error,
                    ),
                  ),
                ),
              ],
            ),
            if (isSuccess) ...[
              const SizedBox(height: 10),
              Wrap(
                spacing: 16,
                runSpacing: 4,
                children: [
                  _Stat(label: 'Fetched', value: run['fetched_count']),
                  _Stat(label: 'Matched', value: run['matched_count']),
                  _Stat(label: 'New', value: run['new_count']),
                  _Stat(label: 'Delivered', value: run['delivered_count']),
                ],
              ),
            ] else if (errorMessage != null) ...[
              const SizedBox(height: 8),
              Text(
                errorMessage,
                style: TextStyle(fontSize: 12, color: colorScheme.onSurfaceVariant),
              ),
            ],
          ],
        ),
      ),
    );
  }

  String _formatTimestamp(String iso) {
    if (iso.isEmpty) return 'Unknown time';
    final parsed = DateTime.tryParse(iso);
    if (parsed == null) return iso;
    final local = parsed.toLocal();
    String two(int n) => n.toString().padLeft(2, '0');
    return '${local.year}-${two(local.month)}-${two(local.day)} ${two(local.hour)}:${two(local.minute)}';
  }
}

class _Stat extends StatelessWidget {
  const _Stat({required this.label, required this.value});

  final String label;
  final Object? value;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Text.rich(
      TextSpan(
        children: [
          TextSpan(text: '${value ?? 0} ', style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13)),
          TextSpan(
            text: label,
            style: TextStyle(fontSize: 12, color: colorScheme.onSurfaceVariant),
          ),
        ],
      ),
    );
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
            Icon(Icons.history_rounded, size: 56, color: colorScheme.outline),
            const SizedBox(height: 16),
            Text(
              'No runs yet',
              style: TextStyle(fontSize: 17, fontWeight: FontWeight.w600, color: colorScheme.onSurface),
            ),
            const SizedBox(height: 8),
            Text(
              'Run history shows up here after the first ingestion check, manual or scheduled.',
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
  const _ErrorState({required this.error});

  final String error;

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
            Text("Couldn't load run history", style: TextStyle(fontWeight: FontWeight.w600, color: colorScheme.onSurface)),
            const SizedBox(height: 4),
            Text(error, textAlign: TextAlign.center, style: TextStyle(color: colorScheme.onSurfaceVariant, fontSize: 12)),
          ],
        ),
      ),
    );
  }
}
