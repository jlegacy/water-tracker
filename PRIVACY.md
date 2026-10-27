# Water Tracker Privacy Policy

**Last updated:** October 27, 2026  
**Effective date:** October 27, 2026  
**Provider:** Joseph Legacy  
**Contact:** jlegacy007@gmail.com

Water Tracker is a live map that lets people on boats, jet skis and kayaks see each other on the water. This policy explains what the app uses, who can see it, and how long it is kept.

## The short version
- **No accounts.** No sign-up, email, phone number or password.
- **No tracking, ads or analytics.** We don’t sell your data or share it with advertisers or data brokers.
- **Everyone within about 50 miles sees everyone else** while they are sharing. The map ring is display-only (pinch to zoom the view); it does not hide you or change who can see you.
- **Live positions live in server memory only**, and are dropped when you leave or after about 30 minutes of silence.
- **Breadcrumbs are Premium only**, stored only on your device (IndexedDB) for about 24 hours. Free users record and draw no trail.
- **App Store subscriptions** are processed by Apple. We never receive your payment card details; the app only caches whether Premium is active.

## What the app uses

| Data | Why | Where it goes | How long |
|---|---|---|---|
| Display name you type | Shown to nearby riders | Our server (memory only); riders within ~50 miles | Until you leave, or ~30 minutes of silence |
| Precise location (while sharing, including background if you allow Always) | Show you on the map to nearby riders; SOS and “gone quiet” alerts | Our server (memory only); riders within ~50 miles | Until you leave, or ~30 minutes of silence |
| Leader badge and SOS status | Shown to nearby riders | Our server (memory only); riders within ~50 miles | Same as above |
| Messages you send | Delivered to the rider you pick, or to nearby riders for a broadcast | Relayed by our server; not stored after delivery | Not kept after delivery |
| Rider ID (a random **User ID** created on your device) | Lets a reconnect resume the same rider session | Your device (local storage); our server (memory only while you are present) | On device until you clear app data; on the server only while your session is live (then purged as above) |
| Breadcrumbs / ride trail (GPS points and times) — **Premium only** | Draw your path and open Past rides | **Your device only** (IndexedDB). While Breadcrumbs is on, a thinned recent segment is also shared live with riders within ~50 miles | Auto-deleted about **24 hours** after saving (~50 MB cap, oldest first). Free users: **not collected or drawn** |
| Premium subscription entitlement | Unlock breadcrumbs and Past rides | Apple (App Store / StoreKit) processes the purchase and billing. The app caches an entitlement flag on your device | Until you cancel or the subscription expires; clear app data to remove the local cache |
| Name and marker preference | Remember your settings | Your device only | Until you clear app data |

### What the server keeps (and does not)
- The server keeps **in memory only**: your rider ID, display name, latest position, Leader/SOS flags, and connection state for nearby sharing.
- There is **no database** of positions or location history on the server.
- A rider is removed when they leave, or after about **30 minutes** with no updates (`PURGE_SECS`).
- “Gone quiet” / stale alerts are sent over the live WebSocket to riders within ~50 miles; they are not stored as a history.

## Who can see you
- There are **no groups** and no privacy range setting. While you are sharing, **every rider within about 50 miles** can see your name, position, Leader badge and SOS status.
- The on-map **radius ring and mi readout are display-only** (they follow pinch-to-zoom). They do not limit visibility; you still appear to everyone within ~50 miles.
- If Breadcrumbs (Premium) is on, nearby riders also see a thinned recent path.
- A rider stops seeing you a little past 50 miles (about 52 miles).
- SOS and “gone quiet” alerts go to riders within ~50 miles. Direct messages go only to the rider you pick.

## Breadcrumbs (Premium)
- **Free users:** the app does **not** record or draw a breadcrumb trail.
- **Subscribers:** the live trail is drawn on your map, auto-saved on the device, kept about 24 hours, and listed under Past rides.
- Use **Delete my trails** (in the marker / Look panel) to wipe saved rides, the draft and the live trail on this phone. Nothing is sent to the server for that wipe.
- Discover Premium with the **Breadcrumbs (Premium)** map button (opens the paywall). Safety features stay free.

## App Store subscriptions and payments
- Premium is an optional auto-renewing subscription sold through the **Apple App Store** (StoreKit). Monthly and yearly product IDs are listed in `docs/SUBSCRIPTIONS.md`.
- **Apple** handles payment, receipts and billing. Water Tracker **does not receive** your Apple ID password, card number or other payment details.
- The app reads StoreKit purchase / entitlement state and **caches** whether Premium is active on your device (local storage), and refreshes it when you launch the app. You can Restore Purchases from the paywall.
- Manage or cancel in iOS Settings → Apple ID → Subscriptions.

## Background location
If you allow **Always** location, the app keeps sharing your position while it is in the background (for example with the phone in a pocket or dry bag), so nearby riders can still find you and SOS / “gone quiet” alerts stay meaningful. Sharing runs only while you have joined a session. It stops when you leave the session or turn off location for Water Tracker in Settings. Continued use of GPS in the background can decrease battery life.

## Push notifications
Water Tracker **does not currently send push notifications** (APNs / FCM). Safety alerts (SOS and “gone quiet”) are delivered over the live WebSocket while the app has a connection. A phone whose app is fully suspended may not see an alert until the app is opened again. If push is added later, this policy will be updated before it ships.

## Third parties
- **Map tiles** are loaded from OpenStreetMap’s tile servers (tile.openstreetmap.org). Those servers receive your IP address and the map area being viewed, under the [OSMF privacy policy](https://osmfoundation.org/wiki/Privacy_Policy).
- **Boat ramps and marinas** come from OpenStreetMap data bundled with the app. If the bundled file can’t load, the app asks our server for ramps near the map center.
- **Hosting:** our server runs on Render (render.com), which may keep standard request logs such as IP addresses.
- **Apple:** App Store purchases and StoreKit entitlement checks go through Apple.
- We use **no** advertising, analytics or crash-reporting SDKs.

## No selling or sharing for ads
We do **not** sell your personal information. We do **not** share it with advertisers, data brokers or other companies for their marketing. Live sharing with nearby riders (as described above) is the product’s safety function, not advertising.

## Security
All traffic uses HTTPS and secure WebSockets (WSS). We keep no database of positions or location history.

## Your choices
- Leave a session at any time to stop sharing and be removed from other riders’ maps.
- Deny or limit location access in system Settings; the app can’t show you to others without it.
- **Delete my trails** removes on-device breadcrumbs. Deleting the app or clearing its data also removes the rider ID, preferences and cached Premium entitlement from the device.
- Manage Premium in Apple Subscriptions settings.

## Children
Water Tracker is not directed at children under 13, and we don’t knowingly collect personal information from them. If you believe a child under 13 has provided information through the app, contact jlegacy007@gmail.com and we will delete what we can control (server memory sessions clear on leave / purge; on-device data is under the device owner’s control).

## Changes
If this policy changes, we’ll update the **Last updated** date above and post the new version at https://water-tracker-yz68.onrender.com/privacy.

## Contact
Questions about this policy: **jlegacy007@gmail.com**  
Source code: https://github.com/jlegacy/water-tracker
