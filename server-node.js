'use strict';

// ═══════════════════════════════════════════════════════════════════════════
//  Flood Display — Node.js + Express backend
//  Architecture: cleaned data → POST /api/analyse-risk → OpenRouter → display
//
//  SAFETY NOTE: This is a prototype/demo only.
//  In a real emergency system, official data and rule-based thresholds must
//  be validated by Council/SES/Melbourne Water.  AI should only support
//  plain-language communication, NOT make final emergency decisions.
// ═══════════════════════════════════════════════════════════════════════════

require('dotenv').config();  // loads OPENROUTER_API_KEY, OPENROUTER_MODEL from .env

const express = require('express');
const path    = require('path');
const fs      = require('fs');

const app  = express();
const PORT = process.env.PORT || 8080;

// API key and model come from .env — never from the frontend.
const OPENROUTER_API_KEY = process.env.OPENROUTER_API_KEY || '';
const OPENROUTER_MODEL   = process.env.OPENROUTER_MODEL   || 'mistralai/mistral-7b-instruct:free';

// Serve static frontend files (index.html, app.js, style.css, etc.)
app.use(express.static(path.join(__dirname)));
app.use(express.json());

// Allow the GitHub Pages frontend to call this Vercel/local backend.
app.use((req, res, next) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  res.setHeader('Cache-Control', 'no-store');
  if (req.method === 'OPTIONS') return res.status(204).end();
  next();
});

const DISPLAY_STATE_KEY = 'display:state';
let latestDisplayState = {
  lang: 'English',
  risk: 'MEDIUM',
  mode: 'normal',
  night: false,
  selectedDataMode: 'historical',
  displayState: 'PREPARE',
  alarmActive: false,
  alarmSeq: 0,
  updatedAt: new Date().toISOString(),
};

async function readDisplayState() {
  const redisUrl = process.env.UPSTASH_REDIS_REST_URL;
  const redisToken = process.env.UPSTASH_REDIS_REST_TOKEN;

  if (redisUrl && redisToken) {
    const response = await fetch(`${redisUrl.replace(/\/$/, '')}/get/${encodeURIComponent(DISPLAY_STATE_KEY)}`, {
      headers: { Authorization: `Bearer ${redisToken}` },
      cache: 'no-store',
    });
    if (response.ok) {
      const body = await response.json();
      if (body.result) return JSON.parse(body.result);
    }
  }

  return latestDisplayState;
}

async function writeDisplayState(nextState) {
  latestDisplayState = {
    ...latestDisplayState,
    ...nextState,
    updatedAt: nextState.updatedAt || new Date().toISOString(),
  };

  const redisUrl = process.env.UPSTASH_REDIS_REST_URL;
  const redisToken = process.env.UPSTASH_REDIS_REST_TOKEN;

  if (redisUrl && redisToken) {
    const value = encodeURIComponent(JSON.stringify(latestDisplayState));
    await fetch(`${redisUrl.replace(/\/$/, '')}/set/${encodeURIComponent(DISPLAY_STATE_KEY)}/${value}`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${redisToken}` },
    });
  }

  return latestDisplayState;
}

// ─── Rule-based fallback ──────────────────────────────────────────────────
// Returns a deterministic risk signal without calling OpenRouter.
// Used when: API key is missing, OpenRouter is down, or model fails.
// This ensures the demo never breaks completely.
function ruleBasedResult(data) {
  const { riverLevel = 0, rainfall24h = 0, officialWarning = false } = data;

  // HIGH: official warning OR very high river/rain
  if (officialWarning || riverLevel >= 5.0 || rainfall24h >= 80) {
    return {
      riskLevel: 'HIGH',
      displayMode: 'evacuate',
      headline: 'Emergency flood conditions near Maribyrnong.',
      action: 'Follow evacuation instructions now.',
      shortChecklist: [
        'Take emergency bag and documents.',
        'Move to higher ground immediately.',
        'Do not walk or drive through floodwater.',
      ],
      confidenceNote: 'Rule-based fallback — AI service unavailable.',
      source: 'fallback',
    };
  }

  // WATCH: rising river or moderate rain
  if (riverLevel >= 3.5 || rainfall24h >= 40) {
    return {
      riskLevel: 'WATCH',
      displayMode: 'watch',
      headline: 'River level rising near Maribyrnong.',
      action: 'Be ready to leave. Prepare your emergency bag.',
      shortChecklist: [
        'Pack medicine, ID and charger.',
        'Move valuables above floor level.',
        'Monitor official updates closely.',
      ],
      confidenceNote: 'Rule-based fallback — AI service unavailable.',
      source: 'fallback',
    };
  }

  // LOW: normal conditions
  return {
    riskLevel: 'LOW',
    displayMode: 'normal',
    headline: 'River levels within normal range near Maribyrnong.',
    action: 'Stay aware. Check your flood plan.',
    shortChecklist: [
      'Keep phone charged.',
      'Know your safe route.',
      'Check official updates.',
    ],
    confidenceNote: 'Rule-based fallback — AI service unavailable.',
    source: 'fallback',
  };
}

// ─── OpenRouter API call ──────────────────────────────────────────────────
// Sends cleaned flood data to a free LLM via OpenRouter.
// The prompt is strict: the model must return JSON only and must NOT
// invent official warnings beyond the provided input data.
// Requires Node.js 18+ for the built-in fetch API.
async function callOpenRouter(floodData) {
  if (!OPENROUTER_API_KEY) throw new Error('OPENROUTER_API_KEY not set in .env');

  // Build a strict, minimal prompt — keep the model focused and output clean.
  const prompt = `You are a flood risk display assistant for Maribyrnong, Melbourne, Australia.
You receive cleaned flood sensor data and convert it into a simple resident-facing risk signal.

STRICT RULES:
- Do NOT invent or assume official warnings beyond what is provided in the input.
- Only use the input data below — do not add information from memory.
- Return ONLY valid JSON — no markdown, no explanation, no extra text.
- Keep all text short and plain for a small e-ink display (max 12 words per field).
- This is a PROTOTYPE DEMO, not a real emergency system.

Input data:
${JSON.stringify(floodData, null, 2)}

Return exactly this JSON structure:
{
  "riskLevel": "LOW" | "WATCH" | "HIGH",
  "displayMode": "normal" | "watch" | "evacuate",
  "headline": "One sentence describing current conditions (max 12 words)",
  "action": "One clear action sentence for residents (max 12 words)",
  "shortChecklist": ["action 1", "action 2", "action 3"],
  "confidenceNote": "One sentence on data confidence or limitations (max 15 words)"
}`;

  const response = await fetch('https://openrouter.ai/api/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Authorization':  `Bearer ${OPENROUTER_API_KEY}`,
      'Content-Type':   'application/json',
      'HTTP-Referer':   `http://localhost:${PORT}`,  // required by OpenRouter
      'X-Title':        'Flood Display Prototype',
    },
    body: JSON.stringify({
      model:       OPENROUTER_MODEL,
      messages:    [{ role: 'user', content: prompt }],
      temperature: 0.1,   // low = consistent, rule-like output
      max_tokens:  350,
    }),
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`OpenRouter HTTP ${response.status}: ${body.slice(0, 200)}`);
  }

  const json = await response.json();
  const text = (json.choices?.[0]?.message?.content || '').trim();

  // Strip markdown code fences if model wrapped the JSON
  const cleaned = text.replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/i, '');

  const parsed = JSON.parse(cleaned);

  // Validate all required fields are present
  const required = ['riskLevel', 'displayMode', 'headline', 'action', 'shortChecklist', 'confidenceNote'];
  for (const field of required) {
    if (parsed[field] === undefined) throw new Error(`Model response missing field: ${field}`);
  }

  return { ...parsed, source: 'openrouter' };
}

// ─── POST /api/analyse-risk ───────────────────────────────────────────────
// Main AI endpoint.  Frontend sends cleaned flood data; backend returns
// a risk signal.  Falls back to rule-based logic if OpenRouter fails.
//
// Request body:
//   { sourceMode, riverLevel, rainfall24h, officialWarning, location, language }
//
// Response:
//   { riskLevel, displayMode, headline, action, shortChecklist, confidenceNote, source }
app.post('/api/analyse-risk', async (req, res) => {
  const data = req.body;
  console.log('[analyse-risk] input:', JSON.stringify(data));

  try {
    // Step 1: try OpenRouter first
    const result = await callOpenRouter(data);
    console.log('[analyse-risk] AI result:', result.riskLevel, `(${result.source})`);
    res.json(result);
  } catch (err) {
    // Step 2: fallback to rule-based logic — demo never fully breaks
    console.warn('[analyse-risk] OpenRouter failed, using rule-based fallback:', err.message);
    res.json(ruleBasedResult(data));
  }
});

// ─── GET/POST /api/display-state ──────────────────────────────────────────
// Simple remote-sync endpoint for the demo:
// Computer A posts the current display state; Computer B polls it every second.
app.get('/api/display-state', async (req, res) => {
  try {
    res.json(await readDisplayState());
  } catch (err) {
    console.warn('[display-state] read failed:', err.message);
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/display-state', async (req, res) => {
  try {
    const saved = await writeDisplayState(req.body || {});
    res.json({ ok: true, state: saved });
  } catch (err) {
    console.warn('[display-state] write failed:', err.message);
    res.status(500).json({ error: err.message });
  }
});

// ─── GET /api/flood-status ────────────────────────────────────────────────
// Serves the current official mode record from the local JSON file.
// The Python server (server.py) does live VicEmergency API calls here;
// this Node.js version uses the static file for simplicity.
app.get('/api/flood-status', (req, res) => {
  try {
    const filePath = path.join(__dirname, 'data', 'current_official_mode.json');
    const data = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    res.json(data);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ─── GET /api/sources ────────────────────────────────────────────────────
app.get('/api/sources', (req, res) => {
  try {
    const filePath = path.join(__dirname, 'data', 'official_sources.json');
    const data = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    res.json(data);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ─── Start ────────────────────────────────────────────────────────────────
app.listen(PORT, () => {
  console.log(`\nFlood Display (Node.js) running at http://localhost:${PORT}`);
  console.log(`OpenRouter model : ${OPENROUTER_MODEL}`);
  console.log(`API key loaded   : ${OPENROUTER_API_KEY ? 'yes' : 'NO — set OPENROUTER_API_KEY in .env'}`);
  console.log('\nEndpoints:');
  console.log(`  GET  /api/flood-status     (current official data)`);
  console.log(`  POST /api/analyse-risk     (AI risk analysis)`);
  console.log(`  GET  /api/sources          (source registry)\n`);
});
