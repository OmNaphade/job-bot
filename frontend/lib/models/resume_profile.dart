class ResumeProfile {
  final List<String> skills;
  final List<String> titles;
  final double? yearsExperience;
  final String? seniority;
  final List<String> locations;
  final List<String> education;
  final String? sourceFilename;
  final DateTime uploadedAt;
  final DateTime updatedAt;

  const ResumeProfile({
    required this.skills,
    required this.titles,
    this.yearsExperience,
    this.seniority,
    required this.locations,
    required this.education,
    this.sourceFilename,
    required this.uploadedAt,
    required this.updatedAt,
  });

  factory ResumeProfile.fromJson(Map<String, dynamic> json) => ResumeProfile(
        skills: List<String>.from(json['skills'] as List? ?? const []),
        titles: List<String>.from(json['titles'] as List? ?? const []),
        yearsExperience: (json['years_experience'] as num?)?.toDouble(),
        seniority: json['seniority'] as String?,
        locations: List<String>.from(json['locations'] as List? ?? const []),
        education: List<String>.from(json['education'] as List? ?? const []),
        sourceFilename: json['source_filename'] as String?,
        uploadedAt: DateTime.parse(json['uploaded_at'] as String),
        updatedAt: DateTime.parse(json['updated_at'] as String),
      );
}
