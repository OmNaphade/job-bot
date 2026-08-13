import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:job_alert_frontend/main.dart';
import 'package:job_alert_frontend/services/auth_service.dart';
import 'package:job_alert_frontend/widgets/section_label.dart';

void main() {
  tearDown(() {
    AuthService.instance.token = null;
    AuthService.instance.userEmail = null;
  });

  testWidgets('JobAlertApp shows the login screen when logged out', (WidgetTester tester) async {
    await tester.pumpWidget(const JobAlertApp());
    await tester.pump();

    expect(find.text('Welcome back'), findsOneWidget);
  });

  testWidgets('JobAlertApp renders the app bar once logged in, without waiting on the network', (WidgetTester tester) async {
    AuthService.instance.token = 'fake-token';
    AuthService.instance.userEmail = 'user@example.com';

    await tester.pumpWidget(const JobAlertApp());
    // Deliberately a single pump, not pumpAndSettle -- HomeScreen kicks off a real
    // HTTP call in initState, which has no backend to resolve against in a test
    // environment. We only assert on the synchronous first frame.
    await tester.pump();

    expect(find.text('Job Alerts'), findsOneWidget);
  });

  testWidgets('SectionLabel renders its text in uppercase', (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(home: Scaffold(body: SectionLabel('sources'))),
    );

    expect(find.text('SOURCES'), findsOneWidget);
  });
}
