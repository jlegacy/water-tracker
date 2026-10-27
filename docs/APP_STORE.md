# Water Tracker — App Store Submission Docs

Matches the app as of Premium freemium (#115–#116) and privacy refresh Oct 27, 2026. Bundle ID `com.encsr.watertracker`, version 1.0. Lines marked **TODO** need the owner's input before submission.

---

## 1. App Store Connect metadata

| Field | Value |
|---|---|
| App name (≤30) | Water Tracker |
| Subtitle (≤30) | Live map for riders on the water |
| Primary category | Navigation |
| Secondary category | Sports |
| Price | **TODO** (pricing tier not decided) |
| Support URL | **TODO** |
| Marketing URL | **TODO** (optional) |
| Privacy Policy URL | https://water-tracker-yz68.onrender.com/privacy |
| Privacy contact | **TODO**: confirm (suggested jlegacy007@gmail.com) |
| Copyright | **TODO** (e.g. "2026 [legal name]") |
| Keywords (≤100) | `boat,jet ski,pwc,kayak,river,lake,ramp,marina,rider,group ride,location,sos,map,trail,water` |

**Promotional text (≤170)**
> See every rider within 50 miles on the water, mark the leader, and send an SOS to everyone around you. No account needed.

**Description**
> Water Tracker puts you and the riders around you on one live map, so a day on the river or lake stays together.
>
> - No sign-up. Enter a display name and you're on the map.
> - Everyone nearby. You automatically see every rider within 50 miles; pinch to zoom the view.
> - Fast start. A rough location circle appears right away, then sharpens as precise GPS locks on.
> - Leader badge. Anyone can mark themselves Leader so the group knows who to follow.
> - SOS. One tap alerts every rider within 50 miles, and riders who go quiet are flagged.
> - Ride trail. Your path is drawn as a dashed line and auto-saved on your phone for 24 hours, then deleted.
> - Ramps and marinas. Show nearby boat ramps and marinas from bundled OpenStreetMap data.
> - Offline-safe. When the connection drops, the map locks with a clear "No internet connection" notice and resumes when you're back.
>
> Water Tracker keeps sharing your position in the background while you ride, so others can still find you with your phone in a pocket. Continued use of GPS in the background can decrease battery life.
>
> Map data © OpenStreetMap contributors.

**What's New (1.0):** First release.

### Age rating questionnaire

| Question | Answer |
|---|---|
| Cartoon/realistic violence, sexual content, nudity, profanity, horror, drugs/alcohol/tobacco, gambling, contests, mature themes, medical info | None |
| Unrestricted web access | No |
| User-generated content / messaging between users | **Yes**: display names and direct/broadcast messages between nearby riders. **TODO**: confirm in-app report/block exists or add it (Guideline 1.2) |
| Shares location with other users | Yes (live position to riders within 50 miles) |
| Expected rating | **TODO**: confirm in App Store Connect (likely 12+ due to user-to-user communication and location sharing) |

---

## 2. App Privacy ("nutrition label")

**Tracking:** No. The app does not track users across other companies' apps or websites. No ads, analytics or third-party SDKs (no Firebase, Sentry, etc.).

| Data type | Collected | Linked to identity | Used for tracking | Purpose |
|---|---|---|---|---|
| Precise Location | Yes | No | No | App Functionality |
| User Content → Other (display name, messages) | Yes | No | No | App Functionality |
| Identifiers → User ID | Yes (random rider ID on device) | No | No | App Functionality |
| Purchases | Yes (Premium subscription / entitlement via StoreKit; Apple processes payment) | No | No | App Functionality |
| Contact info, Health, Financial (card details), Contacts, Browsing, Search, Usage Data, Diagnostics | No | — | — | — |

Notes (keep aligned with `PRIVACY.md`, last updated October 27, 2026):
- No accounts, emails or phone numbers. A random **rider ID (User ID)** is generated on the device and kept in local storage so a reconnect resumes the same rider. It is not tied to a person or hardware identifier.
- Everyone within ~**50 miles** sees each other while sharing. The map **ring is display-only** (pinch-to-zoom); it does not change visibility.
- The server keeps live positions **in memory only**. They are dropped when the rider leaves or after about **30 minutes** of silence. There is no database. Nothing is sold or shared with advertisers.
- **Breadcrumbs are Premium only**, stored **on the device** (IndexedDB) for about **24 hours** (~50 MB cap). Free users record no trail. **Delete my trails** wipes on-device trails. While Breadcrumbs is on, a thinned recent segment is shared with riders within 50 miles.
- Premium: Apple App Store / StoreKit processes payment; the app caches entitlement locally and never receives card details.
- **Push notifications are not currently used**; SOS / gone-quiet alerts go over the WebSocket while connected.
- Ramps/marinas come from a file bundled with the app. If that file fails to load, the app falls back to `/api/ramps` with the map center.
- Map tiles are fetched from tile.openstreetmap.org (tile coordinates + IP). Disclosed in the privacy policy.
- All traffic uses HTTPS/WSS.
- Privacy URL: https://water-tracker-yz68.onrender.com/privacy

---

## 3. App Review notes

**Sign-in:** No login and no demo account are needed.

**How to test**
1. Launch the app, enter any display name, and tap Start (the map opens at a 5 mi view).
2. Allow location ("While Using", then "Always" when prompted). A faded rough circle appears at once and turns solid once precise GPS locks on.
3. Pinch to zoom; the radius readout and ring show the current view only. Every rider within 50 mi is always shown (they drop off past 52 mi).
4. To see other riders, open the app on a second device within 5 mi, or the web version at **TODO**: give reviewers the URL, or confirm the web build may be shared. Both riders appear with names.
5. Tap Leader to show the leader badge on your marker for other riders.
6. Tap SOS. Every rider within 50 miles receives the alert. Tap again to cancel.
7. Tap Ramps to show nearby boat ramps/marinas. A toast shows the count ("N ramps/marinas nearby").
8. Premium / StoreKit testing: unlock breadcrumbs (sandbox or StoreKit config), move, confirm a gray dashed trail and Past rides (24 h on device). Free users see no trail; **Breadcrumbs (Premium)** opens the paywall.
9. Turn on Airplane Mode. The map locks with "No internet connection / Map locked until connection returns" and unlocks when back online.

Reviewers in areas without other riders will see only themselves. That is expected.

**Background location justification (Guideline 5.1.1 / 2.5.4)**
Water Tracker is a live group-safety map for people on boats, jet skis and kayaks. Riders keep the phone in a dry bag or pocket, with the screen off. Background location keeps the rider visible to nearby riders and keeps SOS and "gone quiet" alerts meaningful. Without it, a rider would vanish from everyone's map the moment the screen locks, which defeats the safety purpose. Location is used only while the rider has joined and is sharing. Leaving or stopping sharing ends updates. Updates are throttled to save battery.

**24-hour trail retention rationale**
Trails exist so a rider can see where they've been during the current day on the water, for example to retrace a route back to the ramp. They are kept only on the device and expire 24 h after saving, with a ~50 MB cap that deletes the oldest first. No server-side location history is kept. This is disclosed in the in-app notice and in the privacy policy.

**Info.plist purpose strings (current)**
- `NSLocationWhenInUseUsageDescription`: "Water Tracker uses your location to show you and nearby riders (up to 50 miles) on the map."
- `NSLocationAlwaysAndWhenInUseUsageDescription`: "Water Tracker keeps sharing your position with nearby riders (up to 50 miles) while the app is in the background, so riders can find each other on the water."
- `UIBackgroundModes`: `location`, `fetch`. **TODO**: confirm `fetch` (Background App Refresh) is actually used, or remove it. Apple may ask for a justification.

**Third-party content:** Map tiles and ramp/marina data © OpenStreetMap contributors (ODbL), with attribution shown in-app.

---

## 4. Export compliance

- Uses encryption: **Yes, only standard exempt encryption** (HTTPS/WSS via Apple's system networking). No proprietary or custom cryptography.
- Answer in App Store Connect: "Does your app use encryption?" Yes. "Does it qualify for any exemptions?" Yes: it uses only encryption that is exempt (standard protocols via the OS, Category 5 Part 2 note 4 / mass-market). No export documentation is required.
- Recommended: add `ITSAppUsesNonExemptEncryption` = `NO` to Info.plist to skip this question on every build. **TODO**: not currently set.

---

## TODO summary
1. Price tier
2. Support URL
3. Marketing URL (optional)
4. Privacy policy: last updated Oct 27, 2026 on /privacy — still need confirmed contact email and legal entity name (placeholders in PRIVACY.md)
5. Copyright holder name
6. In-app report/block for user content (Guideline 1.2)
7. Final age rating confirmation
8. Reviewer test URL / second-device instructions
9. Justify or remove the `fetch` background mode
10. Add `ITSAppUsesNonExemptEncryption = NO`


---

## Premium (auto-renewing subscription)

See **[SUBSCRIPTIONS.md](./SUBSCRIPTIONS.md)** for App Store Connect setup.

- Group: Water Tracker Premium
- Products: `com.encsr.watertracker.premium.monthly`, `com.encsr.watertracker.premium.yearly`
- Free forever: live map, SOS, Leader, messaging, riders within 50 mi, ramps (no breadcrumbs)
- Premium: live breadcrumbs + 24 h trail history + Past rides
- Map button **Breadcrumbs (Premium)** opens the paywall for free users
- Paywall includes Restore, Privacy, Terms (EULA), and auto-renew disclosure (Guideline 3.1.2)
