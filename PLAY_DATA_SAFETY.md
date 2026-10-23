# Play Console — Data safety language (Trail)

Paste/adapt the following when filling out Google Play **Data safety**. This file does **not** mean the Console form was submitted — it is copy for Joseph to declare.

## Location
- **Collected:** Yes (precise location while Sharing / Trail is on)
- **Shared:** Yes — with other riders in the user’s selected group while live sharing / Trail is on (thinned path + position)
- **Processed ephemerally?** Live positions are transient on the server for group sharing. **On-device trail archives** are stored in a rolling budget (~50 MB) on the user’s device (IndexedDB), not forever.
- **Retention:** On-device archives until ~50 MB total, then oldest rides removed. Live trail cleared when Trail is off / ride archived. Group-shared thinned segments are not kept as a permanent server trail history in this trial.

## Purpose
- App functionality: group safety / ride tracking — show where riders are and (optionally) a trail history for the user’s past rides.

## Collection notes to declare
- Location may be used **in the background** / when the app is not in use while Sharing is active (same GPS loop as live map sharing). In-app disclosure is shown before enabling Trail.
- Data is encrypted **in transit** (HTTPS/WSS).
- Data is **not sold**.
- Not used for advertising in this trial description.

## User controls
- Trail toggle (default off) with affirmative disclosure before enable.
- Past rides list to view archived rides on the map.
- Leaving the group / ending the session auto-archives the current ride then stops live sharing.

## Background location (Android)
- If the Play listing uses background location, complete the Console declaration, demo video, and prominent disclosure. Native `ACCESS_BACKGROUND_LOCATION` may still need Capacitor/Android config beyond this web/www trial.
