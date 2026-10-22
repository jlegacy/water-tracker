# Safety alerts and push notifications (TODO)

The server now detects riders who go quiet (`stale_monitor` in `main.py`): no update for
`STALE_SECS` (default 90 s) marks them stale and sends `{type:'alert', id, name, lastSeen}`
once to their group over the WebSocket, then `{type:'recovered'}` when they report again.
Silent riders stay on the map greyed out with "last seen"; they are purged after
`PURGE_SECS` (default 30 min) or on an explicit `{type:'leave'}`.

**Not done yet: real push.** A phone whose app is fully suspended only sees the alert when it
reopens. To deliver alerts to backgrounded phones:

1. Create an APNs key (Apple Developer) and a Firebase project (FCM) for `com.encsr.watertracker`.
2. Add `@capacitor/push-notifications` to `water-tracker-app`, register on start, and send the
   device token to the server in the `join` message.
3. Store tokens per rider/group on the server; in `check_stale()` (marked `TODO(push)`), send
   the alert to the group's tokens via APNs/FCM.
4. Put credentials in Heroku config vars. Never commit keys.

Env vars for testing: `STALE_SECS`, `STALE_CHECK_SECS`, `PURGE_SECS`.
