import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:job_alert_frontend/models/resume_profile.dart';
import 'package:job_alert_frontend/services/api_service.dart';
import 'package:job_alert_frontend/widgets/section_label.dart';

class ResumeUploadScreen extends StatefulWidget {
  const ResumeUploadScreen({super.key});

  @override
  State<ResumeUploadScreen> createState() => _ResumeUploadScreenState();
}

class _ResumeUploadScreenState extends State<ResumeUploadScreen> {
  final ApiService _apiService = ApiService.instance;

  bool _loading = true;
  bool _busy = false;
  String? _error;
  ResumeProfile? _profile;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final json = await _apiService.fetchResumeProfile();
      setState(() {
        _profile = json == null ? null : ResumeProfile.fromJson(json);
        _loading = false;
      });
    } catch (error) {
      setState(() {
        _error = 'Failed to load your resume: $error';
        _loading = false;
      });
    }
  }

  Future<void> _pickAndUpload() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['pdf'],
      withData: true,
    );
    final file = result?.files.single;
    if (file?.bytes == null) return; // user cancelled the picker

    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final json = await _apiService.uploadResume(file!.bytes!, file.name);
      if (!mounted) return;
      setState(() {
        _profile = ResumeProfile.fromJson(json);
        _busy = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Resume uploaded and parsed')));
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = 'Upload failed: $error';
        _busy = false;
      });
    }
  }

  Future<void> _delete() async {
    setState(() => _busy = true);
    try {
      await _apiService.deleteResume();
      if (!mounted) return;
      setState(() {
        _profile = null;
        _busy = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = 'Failed to delete: $error';
        _busy = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(title: const Text('Resume')),
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
                  'Upload a PDF resume and we\'ll extract your skills, titles, and experience to '
                  'personalize your job matches. Only the extracted data is kept, not the file itself.',
                  style: TextStyle(fontSize: 12, color: colorScheme.onSurfaceVariant),
                ),
                const SizedBox(height: 20),
                FilledButton.icon(
                  onPressed: _busy ? null : _pickAndUpload,
                  icon: _busy
                      ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.upload_file_rounded),
                  label: Text(_profile == null ? 'Upload resume (PDF)' : 'Replace resume'),
                ),
                if (_profile != null) ...[
                  const SizedBox(height: 24),
                  _ProfileSummary(profile: _profile!),
                  const SizedBox(height: 16),
                  OutlinedButton.icon(
                    onPressed: _busy ? null : _delete,
                    icon: Icon(Icons.delete_outline_rounded, color: colorScheme.error),
                    label: Text('Delete resume', style: TextStyle(color: colorScheme.error)),
                  ),
                ],
              ],
            ),
    );
  }
}

class _ProfileSummary extends StatelessWidget {
  const _ProfileSummary({required this.profile});

  final ResumeProfile profile;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (profile.sourceFilename != null) ...[
          Row(
            children: [
              const Icon(Icons.description_outlined, size: 18),
              const SizedBox(width: 8),
              Expanded(child: Text(profile.sourceFilename!, overflow: TextOverflow.ellipsis)),
            ],
          ),
          const SizedBox(height: 16),
        ],
        if (profile.seniority != null || profile.yearsExperience != null)
          Text(
            [
              if (profile.seniority != null) profile.seniority!,
              if (profile.yearsExperience != null) '${profile.yearsExperience!.toStringAsFixed(0)} yrs experience',
            ].join(' · '),
            style: const TextStyle(fontWeight: FontWeight.w600),
          ),
        if (profile.titles.isNotEmpty) ...[
          const SizedBox(height: 16),
          const SectionLabel('Titles'),
          _ChipWrap(values: profile.titles),
        ],
        if (profile.skills.isNotEmpty) ...[
          const SizedBox(height: 16),
          const SectionLabel('Skills'),
          _ChipWrap(values: profile.skills),
        ],
        if (profile.locations.isNotEmpty) ...[
          const SizedBox(height: 16),
          const SectionLabel('Locations'),
          _ChipWrap(values: profile.locations),
        ],
        if (profile.education.isNotEmpty) ...[
          const SizedBox(height: 16),
          const SectionLabel('Education'),
          _ChipWrap(values: profile.education),
        ],
      ],
    );
  }
}

class _ChipWrap extends StatelessWidget {
  const _ChipWrap({required this.values});

  final List<String> values;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: values.map((value) => Chip(label: Text(value))).toList(),
    );
  }
}
