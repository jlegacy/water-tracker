# Water Tracker Privacy Policy

**Effective date:** October 25, 2026 (**TODO**: confirm)
**Provider:** **TODO**: legal name of the person or entity publishing Water Tracker
**Contact:** **TODO**: confirm contact email (suggested: jlegacy007@gmail.com)

Water Tracker is a live map that lets people on boats, jet skis and kayaks see each other on the water. This policy explains what the app uses, who can see it, and how long it is kept.

## The short version
- **No accounts.** No sign-up, email, phone number or password.
- **No tracking, ads or analytics.** We don't sell data or share it with advertisers or data brokers.
- **Live positions live in server memory only**, and are dropped when you leave or after 30 minutes of silence.
- **Ride breadcrumbs stay on your phone** when you have Premium (kept about 24 hours). Free users do not get a breadcrumb trail.

## What the app uses

| Data | Why | Where it goes | How long |
|---|---|---|---|
| Display name you type | Shown to nearby riders | Our server (memory), nearby riders | Until you leave or 30 min of silence |
| Precise location (foreground and background) | Show you to riders within 50 miles; SOS and "gone quiet" alerts | Our server (memory), riders within 50 miles of you | Until you leave or 30 min of silence |
| Leader badge and SOS status | Shown to riders within 50 miles | Our server (memory), riders within 50 miles | Same as above |
| Messages you send | Delivered to the rider you pick, or to riders within 50 miles for a broadcast | Relayed by our server; not stored | Not stored after delivery |
| Random rider ID | Lets a reconnect resume the same rider | Your device (local storage), our server (memory) | On device until you clear app data |
| Ride trail / breadcrumbs (GPS points and times) | Draw your path; let you view past rides (Premium) | Your device (IndexedDB). A thinned recent segment is shared live with riders within 50 miles while Breadcrumbs is on | **Premium:** deleted 24 h after saving (~50 MB cap). **Free:** no breadcrumbs collected or drawn |
| Premium subscription status (App Store) | Unlock trail history / Past rides | Apple processes the purchase; the app caches entitlement on your device | Until you cancel or the subscription expires |
| Name and marker preference | Remember your settings | Your device only | Until you clear app data |

## Who can see you
- There are no groups and no range setting. Every rider sees everyone within **50 miles**; zooming the map only changes the view.
- While you are sharing, any rider within about **50 miles** sees your name, position, Leader badge, SOS status and, if Breadcrumbs (Premium) is on, your recent trail.
- A rider stops seeing you a little past 50 miles (at 52 miles).
- SOS and "gone quiet" alerts go to riders within 50 miles. Direct messages go only to the rider you pick.

## Background location
If you allow "Always" location, the app keeps sharing your position while it is in the background, so other riders can still find you with your phone in a pocket or dry bag. Sharing stops when you leave the session or turn off location for Water Tracker in Settings.

## Third parties
- **Map tiles** are loaded from OpenStreetMap's tile servers (tile.openstreetmap.org). Those servers receive your IP address and the map area being viewed, under the [OSMF privacy policy](https://osmfoundation.org/wiki/Privacy_Policy).
- **Boat ramps and marinas** come from OpenStreetMap data bundled with the app. If the bundled file can't load, the app asks our server for ramps near the map center.
- **Hosting:** our server runs on Render (render.com), which may keep standard request logs such as IP addresses.
- We use no advertising, analytics or crash-reporting SDKs.

## Security
All traffic uses HTTPS and secure WebSockets (WSS). We keep no database of positions or location history.

## Your choices
- **Premium** is an optional auto‑renewing App Store subscription that unlocks breadcrumbs (live trail + 24 h history) and Past rides. Manage or cancel in iOS Settings → Apple ID → Subscriptions. Purchases use Apple's payment system; we do not receive your card details.
- Leave a session at any time to stop sharing and be removed from other riders' maps.
- Deny or limit location access in iOS Settings; the app can't show you to others without it.
- Delete the app or clear its data to remove saved trails, the rider ID and preferences from your device.

## Children
Water Tracker is not directed at children under 13, and we don't knowingly collect personal information from them.

## Changes
If this policy changes, we'll update the effective date above and post the new version at https://water-tracker-yz68.onrender.com/privacy.

## Contact
**TODO**: confirm contact email (suggested: jlegacy007@gmail.com). Source code: github.com/jlegacy/water-tracker.
