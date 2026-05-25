# Flood Display

E-ink flood display prototype with a small official-source backend.

The backend checks public official feeds first, normalizes the result into a tiny display payload, and keeps static guidance sources documented separately from live APIs.

The resident-facing UI is action-first. The main message is Ready, Prepare, Act Now, Leave Now, or Offline, followed by the official warning level and a short household action. Low/Medium/High remains as a secondary badge for quick scanning, but it is not the main communication model.

## UI Design

The resident-facing screen is action-first, designed for elderly and CALD residents who may be under stress during an urgent flood event.

- The main display intentionally shows fewer words: the main alert state, one instruction sentence, three key actions, a help number, and the source timestamp.
- The Data Traceability panel has been removed from the visible screen to reduce complexity for residents. Detailed source provenance, rule logic, and scenario classification are documented in this README and in the source data files instead.
- Historical Scenario Mode is controlled prototype data modelled on official warning structure and Maribyrnong flood context. It is not a live warning.
- The prototype tests last-mile understanding: whether residents can quickly know what to do, regardless of language or literacy level.

## Source Provenance

All scenario data and decision rules are documented here, not on the resident screen.

Decision rules applied by the prototype:
- No active warning → READY
- Advice → PREPARE
- Watch and Act → ACT NOW
- Emergency Warning / Evacuate / Evacuation → LEAVE NOW
- Stale or connection_lost → OFFLINE / LAST KNOWN WARNING

Historical Scenario Mode is based on: the Australian Warning System, SES Maribyrnong flood guide, Maribyrnong Council River Watch, Melbourne Water Maribyrnong River flood model and maps, BOM Water Data Online, and public reporting on the October 2022 Maribyrnong River flood. See `data/official_sources.json` for the full source registry.

## Run Locally

### Option A — Python server (existing, no AI analysis)

```bash
python3 server.py
```

Then open `http://localhost:8080`.  
Useful endpoints: `/api/flood-status` · `/api/source-health` · `/api/sources`

---

### Option B — Node.js server (with AI risk analysis via OpenRouter)

This runs instead of the Python server.  Both serve on port 8080 — run one at a time.

#### 1. Install dependencies

Requires Node.js 18 or later (uses the built-in `fetch` API).

```bash
npm install
```

#### 2. Create your `.env` file

```bash
cp .env.example .env
# then edit .env and paste your OpenRouter API key
```

Get a free API key at <https://openrouter.ai/>.  
Browse free models at <https://openrouter.ai/models?q=free>.

`.env` contents:

```
OPENROUTER_API_KEY=sk-or-xxxxxxxxxxxxxxxxxx
OPENROUTER_MODEL=mistralai/mistral-7b-instruct:free
PORT=8080
```

> **Why keep the key in `.env` and not in the frontend?**  
> The API key is a secret credential. If it were placed in frontend JavaScript, anyone who opens DevTools could copy it and run up charges on your account. The backend receives the cleaned data from the browser, adds the key server-side, and calls OpenRouter — the key never reaches the user's browser.

#### 3. Run the Node.js server

```bash
npm start
# or: node server-node.js
```

Then open `http://localhost:8080`.

#### 4. How the AI pipeline works

1. In the Demo Controls panel, set river level and rainfall values (or click **Fill from current scenario** to auto-fill based on the current display state).
2. Click **Analyse Risk with AI ▶**.
3. The frontend sends the cleaned data to `POST /api/analyse-risk`.
4. The backend (`server-node.js`) forwards the data to OpenRouter with a strict prompt — the model transforms the input into a JSON risk signal and must not invent official warnings.
5. The backend returns the JSON to the frontend and displays it in the demo panel.
6. Click **Apply to display** to update the e-ink screen.

If OpenRouter fails (key missing, network error, model error), the backend returns a rule-based fallback result — the demo never breaks.

#### 5. Endpoints

```
GET  /api/flood-status    — current official data (from local JSON file)
POST /api/analyse-risk    — AI risk analysis (calls OpenRouter)
GET  /api/sources         — source registry
```

## Two-mode data design and source provenance

This prototype uses a two-mode data design so the 2-minute demo can show both normal current conditions and high-urgency flood states without pretending that a historical or test scenario is happening today.

### Current Official Mode

Current Official Mode represents current official information for Maribyrnong. It checks public official source references and the public VicEmergency events GeoJSON endpoint where available. On most demo days it should show READY / No active warning because there may be no real flood warning today.

This mode does not claim approved formal VicEmergency feed access. A real deployment would need approved data-sharing or feed access with VicEmergency, Emergency Management Victoria, council and/or water authorities.

### Historical Scenario Mode

Historical Scenario Mode is controlled prototype data for demo and testing only. It is not a live current warning. It lets the same display pipeline demonstrate:

- READY / No active warning
- PREPARE / Advice
- ACT NOW / Watch and Act
- LEAVE NOW / Emergency Warning or Evacuate
- OFFLINE / Connection lost or stale data

The historical scenario records are based on official warning structure and real Maribyrnong flood context, including the Australian Warning System levels, SES Maribyrnong flood guidance, Maribyrnong Council River Watch information, Melbourne Water Maribyrnong River flood model/maps, rainfall and river-level references, BOM Water Data Online, and public reporting on the October 2022 Maribyrnong River flood and Rivervue flood-risk impacts.

Both modes use the same transparent rule engine:

- No active warning -> READY
- Advice -> PREPARE
- Watch and Act -> ACT NOW
- Emergency Warning, Evacuate, or Evacuation -> LEAVE NOW
- stale or connection_lost -> OFFLINE / LAST KNOWN WARNING

The prototype does not predict floods. It tests the last-mile communication layer: turning trusted official flood information into simple household actions on an e-ink display. AI/GPT is not used to decide emergency risk. In future, GPT could only be used in a secure backend to simplify already verified official data into plain-language messages.

The prototype does not replace SES, VicEmergency, council or emergency-service instructions. In a real emergency, residents should follow official warnings and call 000 if life is in danger.

## Multilingual dynamic content

English is only the default starting language. The display uses structured multilingual scenario content for:

- English
- 中文
- Tiếng Việt
- Français
- 日本語
- 한국어

Resident-facing scenario messages switch with the language selector, including the main alert, official warning wording, big action sentence, what-is-happening text, do-now checklist, safe-route text, help text, historical-scenario note, and data traceability labels where practical.

This supports CALD communities and is part of the project’s design-justice goal: emergency information should be simple, local, action-focused and understandable across language groups.

Scenario and source files:

- `data/current_official_mode.json`
- `data/historical_scenario_mode.json`
- `data/official_sources.json`

## Data Sources

Live pipeline sources:

- Australian Warning System: https://www.australianwarningsystem.com.au/
- VicEmergency: https://emergency.vic.gov.au/
- VicEmergency public events GeoJSON: https://emergency.vic.gov.au/public/events-geojson.json
- VicEmergency OSOM delta: secondary public emergency-message feed.

Checked or documented sources:

- VicEmergency impact areas GeoJSON: usable later for affected-area polygons.
- SES Maribyrnong flood guide: https://www.ses.vic.gov.au/plan-and-stay-safe/flood-guides/maribyrnong-city-council
- Maribyrnong Council River Watch: https://www.maribyrnong.vic.gov.au/Residents/Emergency-Management/River-Watch-Riverine-Flooding-and-Information
- Melbourne Water Maribyrnong River flood model/maps: https://letstalk.melbournewater.com.au/maribyrnong-river-flood-model/maribyrnong-river-flood-model-maps
- Melbourne Water rainfall and river levels: https://www.melbournewater.com.au/water-and-environment/water-management/rainfall-and-river-levels
- BOM Water Data Online: https://www.bom.gov.au/waterdata/
- Victorian Ombudsman Maribyrnong/Rivervue flood-risk report: https://www.ombudsman.vic.gov.au/our-impact/investigation-reports/when-the-water-rises-flood-risk-at-two-housing-estates/
- Victoria WMIS: official water monitoring portal for exploring and downloading water data.
- VicTraffic / Transport Victoria: useful for road closures, but API access needs an account/API key.

See `data/official_sources.json` for the current source registry.

## Remote display sync and alarm sound

This version adds a simple two-computer demo sync flow.

- Computer A acts as the controller and pushes the current screen state to the backend.
- Computer B acts as the resident display and polls the backend every 1 second.
- The remote state includes warning scenario, language, night mode, low battery/connection-lost mode, and remote alarm sound on/off.

Open Computer A as controller:

```text
https://YOUR-GITHUB-PAGES-LINK/index.html?controller=1&api=https://YOUR-VERCEL-BACKEND.vercel.app
```

Open Computer B as display:

```text
https://YOUR-GITHUB-PAGES-LINK/index.html?display=1&api=https://YOUR-VERCEL-BACKEND.vercel.app
```

The `api=` value is saved in browser localStorage after the first use, so later you can usually open only `?controller=1` or `?display=1` on the same browser.

### Remote alarm sound

The controller panel includes **Remote Alarm ON** and **Remote Alarm OFF**. When the controller turns the alarm on, the display computer receives the command through `/api/display-state` and plays the built-in siren sound.

Important browser limitation: the display computer must click **Enable remote alarm sound** once before sound can play. This is required by browser autoplay rules. After that, the alarm can be controlled remotely from Computer A.

### Backend endpoint

New endpoint:

```text
GET  /api/display-state
POST /api/display-state
```

For local Express testing, this is implemented in `server-node.js`. For Vercel serverless deployment, this is also implemented in `api/display-state.js`.

For reliable Vercel sync, set these environment variables in Vercel:

```text
UPSTASH_REDIS_REST_URL=...
UPSTASH_REDIS_REST_TOKEN=...
```

Without Upstash Redis, the endpoint falls back to temporary memory, which may work for a quick demo but can reset when Vercel cold-starts a function.
