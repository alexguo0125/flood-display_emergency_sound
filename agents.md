# Flood Display — Agent / Contributor Guide

## What This Is

An e-ink flood display PWA prototype for Maribyrnong, Victoria. It turns official flood warning levels into simple, action-first messages on an 880×590 px fixed-frame device UI. Designed for elderly and CALD residents under stress.

Run locally:
```bash
python3 server.py   # starts at http://localhost:8080
```

---

## Files

| File | Purpose |
|------|---------|
| `index.html` | Device frame, screen DOM, demo panel, mobile drawer |
| `app.js` | All rendering, state, translations, scenario content |
| `style.css` | Device layout, CSS grid, e-ink visual styling |
| `server.py` | Python backend — fetches VicEmergency feeds, normalises to display payload |
| `data/current_official_mode.json` | Fallback payload for Current Official Mode (no backend) |
| `data/historical_scenario_mode.json` | All five historical scenario records |
| `data/official_sources.json` | Source registry with URLs and provenance notes |
| `manifest.json`, `sw.js` | PWA manifest and service worker |

---

## Two Data Modes

**Current Official Mode** (`state.selectedDataMode === "current"`)
- Calls `/api/flood-status`, which checks public VicEmergency GeoJSON feeds live.
- On most days returns READY (no active warning). This is expected and correct.
- Falls back to `data/current_official_mode.json` if backend is unavailable.

**Historical Scenario Mode** (`state.selectedDataMode === "historical"`)
- Uses controlled prototype records from `data/historical_scenario_mode.json`.
- Not a live warning. Used for demos and testing all five display states.

---

## Display States and Decision Rules

| Official warning level | Display state | Action shown |
|------------------------|--------------|--------------|
| No active warning | READY | Stay prepared |
| Advice | PREPARE | Prepare now |
| Watch and Act | ACT_NOW | Be ready to leave |
| Emergency Warning / Evacuate / Evacuation | LEAVE_NOW | Follow evacuation instructions now |
| Stale or connection_lost | OFFLINE | Follow last known warning |

These rules are applied in `server.py` (`rule_state_for_warning`) and mirrored in `app.js` (`applyDataRecord`).

---

## Frontend Architecture (`app.js`)

### State
```js
const state = {
  lang, risk, mode,         // "normal" | "low_battery" | "connection_lost"
  night, lastRisk,
  liveStatus, dataRecord,
  selectedDataMode,         // "current" | "historical"
  displayState,             // "READY" | "PREPARE" | "ACT_NOW" | "LEAVE_NOW" | "OFFLINE"
  updatedTime, lastKnownUpdate,
};
```

### Render flow
- `render()` — top-level, delegates to `renderNormal()` or `renderOverlay()`
- `renderNormal()` — fills screen from `UI_CONTENT[lang].scenarios[displayState]`
- `renderOverlay()` — full-screen overlay for low battery / connection lost

### Scenario content shape
```js
{
  actionState,   // e.g. "ACT NOW"
  warning,       // e.g. "WATCH AND ACT"
  action,        // one-sentence instruction (primary action)
  happening,     // one-sentence situation summary
  actions,       // array of exactly 3 short action items
  routeDiagram,  // short route label (English-specific; other langs fall back to ui.route.diagram)
  routeNote,     // one-line route note (English-specific; other langs fall back to ui.route.note)
}
```

---

## Translation System

Six languages: English, 中文, Tiếng Việt, Français, 日本語, 한국어.

- `UI_CONTENT["English"]`, `UI_CONTENT["中文"]`, `UI_CONTENT["Tiếng Việt"]` — defined directly.
- `T["Français"]`, `T["日本語"]`, `T["한국어"]` — defined as full objects (controls + trace + scenarios), then assigned via `UI_CONTENT[lang] = T[lang]`.
- `Object.assign(T[lang], {...})` blocks patch in shared UI strings (title, battery, night mode) for Français/日本語/한국어.

When editing non-English scenario content, find the language's full object inside the `T` const (not the early legacy stubs at the top of `T`).

---

## CSS Layout

The device screen uses a vertical flexbox (`.screen-body`) containing:
1. `.alert-card` — main alert (flex-shrink: 0)
2. `.info-grid` — 2-column, 2-row CSS grid (`grid-template-rows: 1fr 1fr`)
   - Col 1 row 1: `.happening-section`
   - Col 1 row 2: `.route-section`
   - Col 2 span 2: `.action-section`
3. `.help-section` — flex-shrink: 0
4. `.trace-panel` — `display: none` (hidden from resident view; kept in DOM for JS)

All `.info-section` cells have `overflow: hidden` to prevent content from pushing siblings off screen.

---

## Backend API (`server.py`)

| Endpoint | Description |
|----------|-------------|
| `GET /api/flood-status` | Live flood status for Maribyrnong (cached 120 s) |
| `GET /api/source-health` | Reachability check for all official source URLs |
| `GET /api/sources` | Returns `data/official_sources.json` |

The backend uses Haversine distance (35 km radius from Maribyrnong) and keyword matching to filter VicEmergency events. No AI/GPT is used to assess risk — all classification is rule-based.

---

## Design Constraints

- **No upload function.** File-based risk analysis was removed. Do not re-add it.
- **No Data Traceability panel on screen.** The `.trace-panel` is hidden (`display: none`). Source provenance is in README and `data/official_sources.json`.
- **Exactly 3 action items per scenario.** The `act-list` layout is tuned for three items; four causes overflow.
- **No AI risk decisions.** Classification is keyword-based rules only. AI could only be used in a secure backend to simplify already-verified official text.
- **Not a real emergency system.** Prototype only. Production use requires approved VicEmergency / EMV / Council data-sharing access.
