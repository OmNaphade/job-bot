class IngestionConfig {
  final bool enableRssSources;
  final bool enableLinkedInAlerts;
  final bool enableNaukriAlerts;
  final bool allowDirectScraping;
  final int pollIntervalHours;

  const IngestionConfig({
    this.enableRssSources = false,
    this.enableLinkedInAlerts = false,
    this.enableNaukriAlerts = false,
    this.allowDirectScraping = false,
    this.pollIntervalHours = 4,
  });

  factory IngestionConfig.fromJson(Map<String, dynamic> json) => IngestionConfig(
        enableRssSources: json['enable_rss_sources'] as bool? ?? false,
        enableLinkedInAlerts: json['enable_linkedin_alerts'] as bool? ?? false,
        enableNaukriAlerts: json['enable_naukri_alerts'] as bool? ?? false,
        allowDirectScraping: json['allow_direct_scraping'] as bool? ?? false,
        pollIntervalHours: json['poll_interval_hours'] as int? ?? 4,
      );

  Map<String, dynamic> toJson() => {
        'enable_rss_sources': enableRssSources,
        'enable_linkedin_alerts': enableLinkedInAlerts,
        'enable_naukri_alerts': enableNaukriAlerts,
        'allow_direct_scraping': allowDirectScraping,
        'poll_interval_hours': pollIntervalHours,
      };
}
