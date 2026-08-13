import 'package:flutter/material.dart';
import 'package:job_alert_frontend/theme/app_colors.dart';

/// Premium minimal dark SaaS design system: near-black dark surfaces, a single
/// restrained accent color, crisp typography, and subtle borders instead of
/// heavy shadows. Dark is the primary design target; light follows the same
/// token shapes so `ThemeMode.system` still looks intentional.
class AppTheme {
  AppTheme._();

  static const _seed = Color(0xFF6366F1);

  static ThemeData light() => _build(Brightness.light);
  static ThemeData dark() => _build(Brightness.dark);

  static ThemeData _build(Brightness brightness) {
    final isDark = brightness == Brightness.dark;
    final base = ColorScheme.fromSeed(seedColor: _seed, brightness: brightness);
    final colorScheme = isDark
        ? base.copyWith(
            surface: const Color(0xFF0B0C10),
            surfaceContainerLow: const Color(0xFF121319),
            surfaceContainerHighest: const Color(0xFF1C1E26),
            outlineVariant: const Color(0xFF2A2C36),
          )
        : base;

    return ThemeData(
      useMaterial3: true,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: colorScheme.surface,
      extensions: [isDark ? AppStatusColors.dark : AppStatusColors.light],
      textTheme: _textTheme(colorScheme),
      appBarTheme: AppBarTheme(
        centerTitle: false,
        elevation: 0,
        scrolledUnderElevation: 1,
        backgroundColor: colorScheme.surface,
        foregroundColor: colorScheme.onSurface,
        titleTextStyle: TextStyle(
          color: colorScheme.onSurface,
          fontSize: 19,
          fontWeight: FontWeight.w700,
          letterSpacing: -0.2,
        ),
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        color: colorScheme.surfaceContainerLow,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: BorderSide(color: colorScheme.outlineVariant.withValues(alpha: isDark ? 0.7 : 0.5)),
        ),
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 20),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          textStyle: const TextStyle(fontWeight: FontWeight.w600, letterSpacing: -0.1),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 20),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          textStyle: const TextStyle(fontWeight: FontWeight.w600),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 20),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          side: BorderSide(color: colorScheme.outlineVariant),
          textStyle: const TextStyle(fontWeight: FontWeight.w600),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          textStyle: const TextStyle(fontWeight: FontWeight.w600),
          foregroundColor: colorScheme.primary,
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: colorScheme.surfaceContainerHighest.withValues(alpha: isDark ? 0.55 : 0.4),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: colorScheme.outlineVariant.withValues(alpha: 0.7)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: colorScheme.primary, width: 1.4),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: colorScheme.error, width: 1.2),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: colorScheme.secondaryContainer,
        labelStyle: TextStyle(color: colorScheme.onSecondaryContainer, fontWeight: FontWeight.w600, fontSize: 12),
        side: BorderSide.none,
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
      listTileTheme: const ListTileThemeData(
        contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      ),
      dividerTheme: DividerThemeData(
        color: colorScheme.outlineVariant.withValues(alpha: isDark ? 0.6 : 0.7),
        space: 1,
      ),
    );
  }

  static TextTheme _textTheme(ColorScheme colorScheme) {
    return TextTheme(
      headlineSmall: TextStyle(fontWeight: FontWeight.w700, letterSpacing: -0.4, color: colorScheme.onSurface),
      titleLarge: TextStyle(fontWeight: FontWeight.w700, letterSpacing: -0.3, color: colorScheme.onSurface),
      titleMedium: TextStyle(fontWeight: FontWeight.w600, color: colorScheme.onSurface),
      bodyLarge: TextStyle(color: colorScheme.onSurface),
      bodyMedium: TextStyle(color: colorScheme.onSurface),
      bodySmall: TextStyle(color: colorScheme.onSurfaceVariant),
      labelLarge: const TextStyle(fontWeight: FontWeight.w600),
    );
  }
}
