import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:job_alert_frontend/models/job_match.dart';
import 'package:job_alert_frontend/screens/resume_upload_screen.dart';
import 'package:job_alert_frontend/services/api_service.dart';
import 'package:job_alert_frontend/theme/app_colors.dart';
import 'package:url_launcher/url_launcher.dart';

/// Body-only widget (no Scaffold/AppBar of its own) -- embedded as a tab
/// under HomeScreen's shared Scaffold + BottomNavigationBar, same reasoning
/// as JobsTab.
class MatchesTab extends StatefulWidget {
  const MatchesTab({super.key});

  @override
  State<MatchesTab> createState() => _MatchesTabState();
}

class _MatchesTabState extends State<MatchesTab> {
  final ApiService _apiService = ApiService.instance;
  late Future<List<dynamic>> _matchesFuture;

  @override
  void initState() {
    super.initState();
    _matchesFuture = _apiService.fetchMatches();
  }

  void _reload() {
    setState(() => _matchesFuture = _apiService.fetchMatches());
  }

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: () async {
        final future = _apiService.fetchMatches();
        setState(() => _matchesFuture = future);
        await future;
      },
      child: FutureBuilder<List<dynamic>>(
        future: _matchesFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return _MatchesErrorState(error: snapshot.error.toString(), onRetry: _reload);
          }
          final matches = snapshot.data ?? [];
          if (matches.isEmpty) {
            return const _NoMatchesState();
          }
          return ListView.builder(
            padding: const EdgeInsets.only(bottom: 88, top: 8),
            itemCount: matches.length,
            itemBuilder: (context, index) => _MatchCard(match: JobMatch.fromJson(matches[index] as Map<String, dynamic>)),
          );
        },
      ),
    );
  }
}

class _MatchCard extends StatelessWidget {
  const _MatchCard({required this.match});

  final JobMatch match;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final scorePercent = (match.matchScore.clamp(0, 1) * 100).round();

    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: () => _openLink(context, match.link),
        onLongPress: () => _copyLink(context, match.link),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildAvatar(match.logoUrl, match.company, match.source, colorScheme),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(match.title, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15)),
                    const SizedBox(height: 4),
                    Text(
                      '${match.company} · ${match.location}',
                      style: TextStyle(color: colorScheme.onSurfaceVariant, fontSize: 13),
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(
                            color: colorScheme.tertiary.withValues(alpha: 0.16),
                            borderRadius: BorderRadius.circular(20),
                          ),
                          child: Text(
                            '$scorePercent% match',
                            style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: colorScheme.tertiary),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(
                            color: SourceColors.of(match.source, colorScheme.primary).withValues(alpha: 0.14),
                            borderRadius: BorderRadius.circular(20),
                          ),
                          child: Text(
                            SourceColors.label(match.source),
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                              color: SourceColors.of(match.source, colorScheme.primary),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              IconButton(
                tooltip: 'Copy link',
                icon: const Icon(Icons.copy_rounded, size: 18),
                onPressed: () => _copyLink(context, match.link),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildAvatar(String? logoUrl, String company, String source, ColorScheme colorScheme) {
    final sourceColor = SourceColors.of(source, colorScheme.primary);
    final initialAvatar = CircleAvatar(
      radius: 20,
      backgroundColor: sourceColor.withValues(alpha: 0.16),
      child: Text(
        company.isNotEmpty ? company[0].toUpperCase() : '?',
        style: TextStyle(color: sourceColor, fontWeight: FontWeight.w700),
      ),
    );
    if (logoUrl == null || logoUrl.isEmpty) return initialAvatar;

    return ClipOval(
      child: Image.network(
        logoUrl,
        width: 40,
        height: 40,
        fit: BoxFit.cover,
        errorBuilder: (context, error, stackTrace) => initialAvatar,
      ),
    );
  }

  Future<void> _openLink(BuildContext context, String link) async {
    final uri = Uri.tryParse(link);
    final opened = uri != null && await canLaunchUrl(uri) && await launchUrl(uri, mode: LaunchMode.externalApplication);
    if (!opened && context.mounted) {
      Clipboard.setData(ClipboardData(text: link));
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("Couldn't open the link — copied instead")));
    }
  }

  void _copyLink(BuildContext context, String link) {
    Clipboard.setData(ClipboardData(text: link));
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Link copied')));
  }
}

class _NoMatchesState extends StatelessWidget {
  const _NoMatchesState();

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.auto_awesome_outlined, size: 56, color: colorScheme.outline),
            const SizedBox(height: 16),
            Text(
              'No personalized matches yet',
              style: TextStyle(fontSize: 17, fontWeight: FontWeight.w600, color: colorScheme.onSurface),
            ),
            const SizedBox(height: 8),
            Text(
              'Upload a resume and we\'ll rank your incoming jobs by how well they match it.',
              textAlign: TextAlign.center,
              style: TextStyle(color: colorScheme.onSurfaceVariant),
            ),
            const SizedBox(height: 20),
            FilledButton.icon(
              onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const ResumeUploadScreen())),
              icon: const Icon(Icons.upload_file_rounded),
              label: const Text('Upload resume'),
            ),
          ],
        ),
      ),
    );
  }
}

class _MatchesErrorState extends StatelessWidget {
  const _MatchesErrorState({required this.error, required this.onRetry});

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
            Text('Couldn\'t load matches', style: TextStyle(fontWeight: FontWeight.w600, color: colorScheme.onSurface)),
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
