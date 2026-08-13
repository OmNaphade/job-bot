class NotificationSettings {
  final String? telegramBotToken;
  final String? telegramChatId;
  final String? slackWebhookUrl;
  final String? discordWebhookUrl;

  const NotificationSettings({
    this.telegramBotToken,
    this.telegramChatId,
    this.slackWebhookUrl,
    this.discordWebhookUrl,
  });

  factory NotificationSettings.fromJson(Map<String, dynamic> json) => NotificationSettings(
        telegramBotToken: json['telegram_bot_token'] as String?,
        telegramChatId: json['telegram_chat_id'] as String?,
        slackWebhookUrl: json['slack_webhook_url'] as String?,
        discordWebhookUrl: json['discord_webhook_url'] as String?,
      );

  Map<String, dynamic> toJson() => {
        'telegram_bot_token': _blankToNull(telegramBotToken),
        'telegram_chat_id': _blankToNull(telegramChatId),
        'slack_webhook_url': _blankToNull(slackWebhookUrl),
        'discord_webhook_url': _blankToNull(discordWebhookUrl),
      };

  static String? _blankToNull(String? value) => (value == null || value.trim().isEmpty) ? null : value.trim();
}
