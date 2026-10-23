# Water Tracker (Capacitor)

Native iOS/Android shell for Water Tracker. **Production builds load the UI from local `www/`** (no remote WebView wrapper) and talk to the live API/WebSocket on Render.

Live API: `https://water-tracker-yz68.onrender.com`

## Why local `www`

Apple guideline 4.2 often rejects apps that are only a thin shell around a remote website (`server.url`). Production `capacitor.config.json` has **no** `server` block. The map UI ships inside the app; only live rider data and ramp lookups hit Render.

The same `www/` files are what FastAPI serves for the browser site (`main.py` → `FileResponse(WWW_DIR / "index.html")`), so web and native stay in sync.

## Production rebuild (Mac)

```bash
cd water-tracker-app
npm install
npx cap sync ios
# then Archive / Distribute in Xcode (set DEVELOPMENT_TEAM)
```

Android: `npx cap sync android` then open in Android Studio.

## Dev: remote WebView (optional)

To point the shell at the live site while iterating (old behavior):

```bash
cp capacitor.config.dev.json capacitor.config.json
npx cap sync ios
```

Restore production config from git when done (`capacitor.config.json` without `server.url`). Dev config has **no** `cleartext` — HTTPS only.

## API origin behavior

Client bootstrap in `www/index.html`:

- Served from Render/Heroku → empty `API_ORIGIN` (same-origin `/ws`, `/api/...`)
- Capacitor / `file:` / localhost preview → `https://water-tracker-yz68.onrender.com`

## Do not

- Re-add `server.url` + `cleartext` for App Store builds
- Remove `www/ramps_us.json` (native apps load ramps from this bundled file)
