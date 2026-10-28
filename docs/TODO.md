# Backlog

- **Haptics on SOS:** the app does not vibrate when an SOS comes in.
- **iOS haptics for gone-quiet:** iOS WebKit ignores `navigator.vibrate`, so iPhones never buzz for the gone-quiet alert. Use the Capacitor Haptics plugin (`@capacitor/haptics`) in the native build, falling back to `navigator.vibrate` on web/Android.
