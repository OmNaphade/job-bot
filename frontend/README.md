# job_alert_frontend

Flutter dashboard for the [Job Alert Platform](../README.md) — view stored jobs, trigger on-demand checks, and manage source/keyword configuration. It's a client for the FastAPI backend in [`../backend`](../backend); it doesn't do any ingestion itself and isn't required for the bot to function (see the root [README](../README.md#about)).

## How to run

### 1. Start the backend first

The app needs a running backend to talk to — see the root [README § Usage](../README.md#usage) or [bot_docs/OPERATIONS.md](../bot_docs/OPERATIONS.md#backend) for full setup. Quick version:

```bash
cd ../backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
REM edit .env with real values, then:
uvicorn main:app --reload --host 127.0.0.1 --port 9000
```

### 2. Run the Flutter app

```bash
cd frontend
flutter pub get
flutter run -d chrome    # or: flutter run -d windows
```

Other targets work the same way — list what's available on your machine with `flutter devices`, then `flutter run -d <device-id>`.

### 3. Point it at your backend

By default the app targets `127.0.0.1:9000` (`10.0.2.2:9000` on the Android emulator, the emulator's alias for the host's loopback). If your backend runs elsewhere, open **Settings → Server connection** (or the button offered directly on the "couldn't reach the backend" error screen), enter the backend URL, tap **Test connection**, then **Save** — this is persisted across app restarts via `shared_preferences`. Then sign up or log in with your own account — the app opens to the login screen by default; there's no shared API key to enter anymore.

Running on a real Android/iOS device (not an emulator) needs your PC's LAN IP instead of `127.0.0.1`, plus the backend bound to `0.0.0.0` — full walkthrough in [bot_docs/OPERATIONS.md § Running on a phone](../bot_docs/OPERATIONS.md#running-on-a-phone-androidios).

## Building

```bash
flutter build web       # static site, output in build/web
flutter build windows    # Windows desktop exe
flutter build apk        # Android APK (needs the Android SDK)
```

## Testing

```bash
flutter analyze
flutter test
```

Runs in CI on every push/PR via [`.github/workflows/ci.yml`](../.github/workflows/ci.yml).

## Project layout

```
lib/
├── main.dart          # AuthGate: routes to LoginScreen or HomeScreen based on session state
├── models/            # IngestionConfig, NotificationSettings, User
├── screens/           # login, signup, home, settings hub, ingestion sources, keywords,
│                      # notifications, run history, server connection
├── services/          # api_service (backend HTTP client, attaches session token),
│                      # auth_service (session state, signup/login/logout),
│                      # server_config (persisted backend URL)
├── theme/             # app_colors, app_theme — dark-first Material 3 design tokens
└── widgets/
```

## Learn more

This was scaffolded from the standard Flutter template — if you're new to Flutter itself rather than this project specifically:

- [Write your first Flutter app](https://docs.flutter.dev/get-started/codelab)
- [Flutter docs](https://docs.flutter.dev/)
