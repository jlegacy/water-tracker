# Water Tracker Premium — App Store Connect setup

Premium unlocks **breadcrumbs** — the live ride trail and keeping those trails on the map for about 24 hours. Free users see **no** breadcrumb trail at all. Live map, SOS, Leader, messaging, and riders within 50 mi stay free.

Product IDs (must match `PREMIUM.products` in `water-tracker-app/www/index.html`):

| Role | Product ID |
|---|---|
| Subscription group | **Water Tracker Premium** |
| Monthly auto‑renewing | `com.encsr.watertracker.premium.monthly` |
| Yearly auto‑renewing | `com.encsr.watertracker.premium.yearly` |

Plugin: `@capgo/native-purchases` (StoreKit 2). No RevenueCat / server API keys required. After pulling this branch on a Mac: `cd water-tracker-app && npm install && npx cap sync ios`, then rebuild in Xcode.

---

## 1. Paid Apps agreement

1. App Store Connect → **Agreements, Tax, and Banking**.
2. Accept the **Paid Applications** agreement.
3. Complete **Banking** and **Tax** forms. Subscriptions will not clear for sale until this is Active.

## 2. Subscription group + products

1. Open the **Water Tracker** app (`com.encsr.watertracker`).
2. **Subscriptions** → create group named **Water Tracker Premium**.
3. Add two Auto‑Renewable Subscriptions in that group:

### Monthly
- Reference name: `Premium Monthly`
- Product ID: `com.encsr.watertracker.premium.monthly`
- Duration: **1 Month**
- Suggested price: **$2.99 / month** (pick any tier; change later)
- Localization (English U.S.): Display name `Premium Monthly`, description `Save ride breadcrumbs on the map for 24 hours.`

### Yearly
- Reference name: `Premium Yearly`
- Product ID: `com.encsr.watertracker.premium.yearly`
- Duration: **1 Year**
- Suggested price: **$19.99 / year** (about 2 months free vs monthly)
- Localization (English U.S.): Display name `Premium Yearly`, description `Save ride breadcrumbs on the map for 24 hours. Best value.`

4. Add a **Review screenshot** of the in‑app paywall (Past button → Water Tracker Premium sheet) for each product or for the group, per App Store Connect prompts.
5. Submit the subscriptions for review with the next app binary (or as a subscription update if the app is already live).

## 3. Xcode capability + StoreKit config

1. Open `water-tracker-app/ios/App/App.xcworkspace` in Xcode.
2. Target **App** → **Signing & Capabilities** → **+ Capability** → **In‑App Purchase**.
3. For local testing without sandbox: **Product → Scheme → Edit Scheme → Run → Options → StoreKit Configuration** → choose `water-tracker-app/ios/StoreKit/WaterTracker.storekit` (committed in this repo).
4. Sandbox tester: App Store Connect → **Users and Access** → **Sandbox** → **Testers** → create a tester. On the phone, sign out of Media & Purchases (Settings → App Store), then purchase in the app with the sandbox Apple ID when prompted.

## 4. What free vs Premium users get

| Feature | Free | Premium |
|---|---|---|
| Live map, SOS, Leader, riders ≤50 mi, messaging, ramps | Yes | Yes |
| Live breadcrumb trail (current ride) | No | Yes |
| Keep trail on the map after leave / rejoin / reload (24 h) | No | Yes |
| Discover: **Breadcrumbs (Premium)** map button | Opens paywall | Toggles breadcrumbs on/off |

## 5. Paywall copy (Guideline 3.1.2)

The in‑app sheet includes: Monthly and Yearly (prices from StoreKit, never hardcoded for production), Restore Purchases, Privacy Policy link, Apple EULA / Terms of Use link, and the standard auto‑renew disclosure paragraph.

## 6. Dev / QA override

- Playwright / browser: `window.__WT_SET_PREMIUM__(true|false)` or `?premium=1` / `localStorage.wtDevPremium=1`.
- Master kill switch: set `PREMIUM.enabled = false` in `index.html` to unlock trail history for everyone without a store.

## 7. After Connect is configured

1. Mac: `git pull && cd water-tracker-app && npm install && npx cap sync ios`
2. Xcode: Archive → distribute to TestFlight.
3. On device: tap **Breadcrumbs (Premium)** → subscribe with a sandbox tester → confirm the trail restores on the map after relaunch; Restore Purchases on a second install.
