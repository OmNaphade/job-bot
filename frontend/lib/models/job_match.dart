class JobMatch {
  final int id;
  final String title;
  final String company;
  final String location;
  final String link;
  final String source;
  final String? postedAt;
  final String? logoUrl;
  final double matchScore;

  const JobMatch({
    required this.id,
    required this.title,
    required this.company,
    required this.location,
    required this.link,
    required this.source,
    this.postedAt,
    this.logoUrl,
    required this.matchScore,
  });

  factory JobMatch.fromJson(Map<String, dynamic> json) => JobMatch(
        id: json['id'] as int,
        title: json['title'] as String,
        company: json['company'] as String,
        location: json['location'] as String,
        link: json['link'] as String,
        source: json['source'] as String,
        postedAt: json['posted_at'] as String?,
        logoUrl: json['logo_url'] as String?,
        matchScore: (json['match_score'] as num).toDouble(),
      );
}
