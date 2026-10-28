# Play Console — Data safety language (Ride Radar)

Paste/adapt the following when filling out Google Play **Data safety**. This file does **not** mean the Console form was submitted — it is copy for Joseph to declare. Keep aligned with `PRIVACY.md` (last updated October 27, 2026).

## Location
- **Collected:** Yes (precise location while the user has joined and is sharing).
- **Shared:** Yes — with other app users within about **50 miles** while live sharing is on (display name, position, Leader/SOS status). Breadcrumb trails are **not** shared; only the rider sees their own. There are no groups or invitations: anyone signed in nearby can see you while you share. The on-map ring is **display-only** (view zoom); it does not change who can see you.
- **Processed ephemerally?** Live positions are transient on the server (**in memory only**). They are dropped when the rider leaves or after about **30 minutes** of silence. **No** server location history database.
- **On-device breadcrumbs (Premium only):** stored in IndexedDB on the user’s device, auto-deleted after about **24 hours** (~50 MB cap). Free users record **no** trail. Users can wipe trails with **Delete my trails**.
- **Retention (live):** until leave or ~30 min silence on the server; device preferences / rider ID until the user clears app data.

## Purpose
- App functionality: nearby-rider safety map — show where riders are; optional Premium breadcrumbs kept on-device for about 24 hours.

## Collection notes to declare
- Location may be used **in the background** / when the app is not in use while sharing is active (Capacitor background geolocation). Prominent disclosure before enabling breadcrumbs on Premium.
- Data is encrypted **in transit** (HTTPS/WSS).
- Data is **not sold**.
- Not used for advertising.
- **Push notifications:** not currently implemented; safety alerts use the live WebSocket only.

## User controls
- Leave session to stop sharing.
- **Breadcrumbs (Premium)** / paywall for trail features; free users get no trail.
- **Delete my trails** wipes on-device archives, draft and live trail (nothing sent to the server for the wipe).
- System location permission (While Using / Always).

## Purchases (if / when Play Billing ships)
- Subscriptions would be processed by Google Play; the app would not receive card details. (Current shipping Premium is **App Store / StoreKit** on iOS.)

## Background location (Android)
- If the Play listing uses background location, complete the Console declaration, demo video, and prominent disclosure. Native `ACCESS_BACKGROUND_LOCATION` may still need Capacitor/Android config beyond the web/www build.
