# Privacy — Water Tracker (trail logging)

This note covers the **Trail** feature (trial).

## What we collect
- While **Trail** is on and you are sharing your location, the app records GPS points for your current ride (latitude, longitude, and a timestamp).
- Location may continue to update while the app is in the background or not in active use, using the same GPS loop as live sharing.

## How trails are stored
- The **live ride** is kept in memory while you ride.
- When a ride ends (Trail turned off, or the session ends), the ride is **auto-saved on your device** in **IndexedDB** — no export step.
- Each archived ride stores a thinned path and start/end times.
- Archives are retained until total trail storage reaches about **50 MB**. When over that budget, the **oldest archived rides are deleted first**. Storage is never unbounded.
- Turning Trail off clears the live path after archiving; it does not wipe past rides.

## Sharing
- While Trail is on, a **thinned** recent segment of your path may be shared with other riders within about 25 miles of you over the encrypted WebSocket connection (WSS), together with normal position updates.
- Other riders’ live trails are shown as a gray dashed line on the map. Past rides stay on your device unless you load one onto your own map.

## Security and retention
- Live sharing traffic uses **HTTPS / WSS** (encrypted in transit).
- Trail archives live on **your device** (IndexedDB), not as a permanent server-side history in this trial.
- Location trail data is **not sold**.
- Aged-out / over-budget archives are removed automatically; you can also clear a past ride overlay from the map with **Past → Clear map** (that only removes the overlay, not the archive).

## Contact
For privacy questions about this app, contact the app owner (repository: github.com/jlegacy/water-tracker).


## Who can see you
- There are no groups. While you are sharing, every Water Tracker rider within about **25 miles** of you sees your name, position, Leader badge, and SOS status, and you see theirs. Riders drop off each other's maps a little past 25 miles (about 27 miles).
- Your SOS and "gone quiet" alerts go to riders within that range. Direct messages go only to the rider you pick.
- The server keeps live positions in memory only; they are dropped when you leave or after 30 minutes of silence.
