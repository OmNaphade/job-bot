import 'package:flutter/material.dart';

/// Semantic status colors beyond Material's ColorScheme (success/warning have
/// no standard slot) -- accessed via `Theme.of(context).appStatusColors`.
/// Replaces the hardcoded `Colors.green` literals that used to appear
/// per-widget in run_history_screen.dart and server_settings_screen.dart.
@immutable
class AppStatusColors extends ThemeExtension<AppStatusColors> {
  const AppStatusColors({required this.success, required this.warning});

  final Color success;
  final Color warning;

  static const light = AppStatusColors(success: Color(0xFF15803D), warning: Color(0xFFB45309));
  static const dark = AppStatusColors(success: Color(0xFF4ADE80), warning: Color(0xFFFBBF24));

  @override
  AppStatusColors copyWith({Color? success, Color? warning}) =>
      AppStatusColors(success: success ?? this.success, warning: warning ?? this.warning);

  @override
  AppStatusColors lerp(ThemeExtension<AppStatusColors>? other, double t) {
    if (other is! AppStatusColors) return this;
    return AppStatusColors(
      success: Color.lerp(success, other.success, t) ?? success,
      warning: Color.lerp(warning, other.warning, t) ?? warning,
    );
  }
}

extension AppStatusColorsX on ThemeData {
  AppStatusColors get appStatusColors => extension<AppStatusColors>() ?? AppStatusColors.light;
}

/// Per-job-source brand accent colors and display labels -- one place so the
/// same source reads identically on the job list, run history, and anywhere
/// else a source badge appears.
class SourceColors {
  SourceColors._();

  static const _palette = {
    'weworkremotely': Color(0xFF60A5FA),
    'himalayas': Color(0xFF22D3EE),
    'unstop': Color(0xFFFB923C),
    'foundit': Color(0xFFC084FC),
    'linkedin_alerts': Color(0xFF4DA6FF),
    'naukri_alerts': Color(0xFFF472B6),
    'manual': Color(0xFF94A3B8),
  };

  static const _labels = {
    'weworkremotely': 'We Work Remotely',
    'himalayas': 'Himalayas',
    'unstop': 'Unstop',
    'foundit': 'Foundit',
    'linkedin_alerts': 'LinkedIn',
    'naukri_alerts': 'Naukri',
    'manual': 'Manual',
    'sample': 'Sample',
  };

  static Color of(String source, Color fallback) => _palette[source] ?? fallback;

  static String label(String source) => _labels[source] ?? source;
}
