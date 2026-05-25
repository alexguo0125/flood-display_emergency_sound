#!/usr/bin/env python3
"""Official-source backend for the Flood Display prototype."""

from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import json
import math
import os
import time


PORT = int(os.environ.get("PORT", "8080"))
ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE_SECONDS = 120

MARIBYRNONG = {
    "name": "Maribyrnong",
    "lat": -37.772,
    "lon": 144.889,
    "radius_km": 35,
    "terms": [
        "maribyrnong",
        "footscray",
        "yarraville",
        "seddon",
        "maidstone",
        "braybrook",
        "avondale heights",
        "ascot vale",
        "moonee ponds",
        "flemington",
    ],
}

LIVE_SOURCES = [
    {
        "id": "vicemergency-events",
        "name": "VicEmergency public events GeoJSON",
        "url": "https://emergency.vic.gov.au/public/events-geojson.json",
        "parser": "events",
    },
    {
        "id": "vicemergency-osom-delta",
        "name": "VicEmergency OSOM delta",
        "url": "https://emergency.vic.gov.au/public/osom-delta.json",
        "parser": "osom",
    },
]

HEALTH_SOURCES = [
    *LIVE_SOURCES,
    {
        "id": "vicemergency-impact-areas",
        "name": "VicEmergency impact areas GeoJSON",
        "url": "https://emergency.vic.gov.au/public/impact-areas-geojson.json",
    },
    {
        "id": "bom-waterdata-sos",
        "name": "BOM Water Data Online SOS API",
        "url": "https://www.bom.gov.au/waterdata/services?service=SOS&version=2.0&request=GetCapabilities",
    },
]

_cached_status = None
_cached_at = 0


def fetch_bytes(url):
    request = Request(
        url,
        headers={
            "Accept": "application/json,text/xml,*/*",
            "User-Agent": "flood-display-proof-of-concept/1.0",
        },
    )
    with urlopen(request, timeout=20) as response:
        return response.read()


def fetch_json(url):
    return json.loads(fetch_bytes(url).decode("utf-8"))


def build_flood_status():
    global _cached_status, _cached_at

    now = time.time()
    if _cached_status and now - _cached_at < CACHE_SECONDS:
        status = dict(_cached_status)
        status["cached"] = True
        return status

    all_items = []
    errors = []

    for source in LIVE_SOURCES:
        try:
            data = fetch_json(source["url"])
            if source["parser"] == "events":
                all_items.extend(parse_vicemergency_events(data))
            elif source["parser"] == "osom":
                all_items.extend(parse_osom_delta(data))
        except Exception as exc:
            errors.append({
                "id": source["id"],
                "name": source["name"],
                "error": str(exc),
            })

    relevant = [item for item in all_items if is_relevant_to_maribyrnong(item)]
    relevant.sort(key=lambda item: severity_score(item["risk"]), reverse=True)

    status = status_from_event(relevant[0], relevant, errors) if relevant else low_status(all_items, errors)
    _cached_status = status
    _cached_at = now

    response = dict(status)
    response["cached"] = False
    return response


def parse_vicemergency_events(data):
    features = data.get("features", []) if isinstance(data, dict) else []
    items = []

    for feature in features:
        properties = feature.get("properties", {}) or {}
        text = " ".join(
            str(value)
            for value in [
                properties.get("webHeadline"),
                properties.get("sourceTitle"),
                properties.get("name"),
                properties.get("location"),
                properties.get("category1"),
                properties.get("category2"),
                properties.get("status"),
                properties.get("sourceOrg"),
            ]
            if value
        )

        items.append({
            "id": str(properties.get("id") or properties.get("eventId") or properties.get("sourceId") or text),
            "title": properties.get("webHeadline")
            or properties.get("sourceTitle")
            or properties.get("name")
            or properties.get("category2")
            or properties.get("category1")
            or "Official emergency event",
            "location": properties.get("location") or "",
            "category": " / ".join(str(value) for value in [properties.get("category1"), properties.get("category2")] if value),
            "status": properties.get("status") or "",
            "updatedAt": properties.get("updated")
            or properties.get("created")
            or data.get("properties", {}).get("lastUpdated")
            or utc_now(),
            "url": properties.get("url") or "https://www.emergency.vic.gov.au/",
            "source": "VicEmergency public events GeoJSON",
            "coordinates": point_from_geometry(feature.get("geometry")),
            "text": text,
            "risk": classify_risk(text),
        })

    return items


def parse_osom_delta(data):
    text = json.dumps(data or {})
    if len(text) < 120:
        return []

    return [{
        "id": f"osom-{data.get('lastModified') or int(time.time())}",
        "title": "VicEmergency OSOM delta update",
        "location": "",
        "category": "Emergency message delta",
        "status": "",
        "updatedAt": data.get("lastModified") or utc_now(),
        "url": "https://emergency.vic.gov.au/",
        "source": "VicEmergency OSOM delta",
        "coordinates": None,
        "text": text,
        "risk": classify_risk(text),
    }]


def point_from_geometry(geometry):
    if not geometry:
        return None

    if geometry.get("type") == "Point" and isinstance(geometry.get("coordinates"), list):
        coords = geometry["coordinates"]
        return {"lon": float(coords[0]), "lat": float(coords[1])}

    if geometry.get("type") == "GeometryCollection":
        for item in geometry.get("geometries", []):
            if item.get("type") == "Point":
                return point_from_geometry(item)

    return None


def is_relevant_to_maribyrnong(item):
    haystack = item.get("text", "").lower()
    place_match = any(term in haystack for term in MARIBYRNONG["terms"])
    flood_match = any(
        term in haystack
        for term in ["flood", "river", "rain", "storm", "flash flood", "road closed", "closed road"]
    )
    coordinates = item.get("coordinates")
    nearby = False

    if coordinates:
        nearby = distance_km(
            coordinates["lat"],
            coordinates["lon"],
            MARIBYRNONG["lat"],
            MARIBYRNONG["lon"],
        ) <= MARIBYRNONG["radius_km"]

    return flood_match and (place_match or nearby)


def classify_risk(text):
    value = text.lower()
    high_terms = [
        "emergency warning",
        "evacuate",
        "evacuation",
        "major flood",
        "move to higher ground",
        "too late to leave",
        "severe",
    ]
    medium_terms = [
        "flood warning",
        "watch and act",
        "prepare",
        "moderate flood",
        "minor flood",
        "flood watch",
        "responding",
        "request for assistance",
        "storm",
        "road closed",
        "flash flood",
    ]

    if any(term in value for term in high_terms):
        return "HIGH"
    if any(term in value for term in medium_terms):
        return "MEDIUM"
    return "LOW"


def severity_score(risk):
    return {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(risk, 0)


def status_from_event(event, relevant, errors):
    warning_level = warning_level_for_event(event)
    display_state = rule_state_for_warning(warning_level, "current")
    return {
        "mode": "Current Official Mode",
        "scenario": display_state,
        "risk": event["risk"],
        "headline": event["title"],
        "happening": f"{event.get('category') or 'Official event'}"
        f"{' near ' + event['location'] if event.get('location') else ''}. "
        f"{'Status: ' + event['status'] + '.' if event.get('status') else ''}".strip(),
        "primaryAction": "Follow official emergency instructions now."
        if event["risk"] == "HIGH"
        else "Monitor official warnings and prepare early.",
        "actions": actions_for_risk(event["risk"]),
        "updatedAt": event["updatedAt"],
        "timestamp": event["updatedAt"],
        "source": event["source"],
        "sourceUrl": event["url"],
        "targetArea": MARIBYRNONG["name"],
        "location": MARIBYRNONG["name"],
        "officialWarningLevel": warning_level,
        "rainfallTrend": "unknown",
        "riverTrend": "unknown",
        "dataStatus": "current",
        "isRealCurrentWarning": True,
        "ruleUsed": rule_label_for_state(display_state),
        "provenanceNote": "Current Official Mode uses public official endpoint checks where available; it does not represent approved formal VicEmergency data-feed access.",
        "matchedEvents": relevant[:5],
        "sourceErrors": errors,
        "officialDataNotice": "Proof-of-concept uses public official endpoints. Production deployment should use approved VicEmergency/EMV/Council data-sharing access.",
    }


def low_status(all_items, errors):
    display_state = "READY"
    return {
        "mode": "Current Official Mode",
        "scenario": "CURRENT_NORMAL",
        "risk": "LOW",
        "headline": "No official flood warning found for Maribyrnong",
        "happening": f"Checked official public feeds and found no current flood warning matching {MARIBYRNONG['name']}.",
        "primaryAction": "Stay aware",
        "actions": actions_for_risk("LOW"),
        "updatedAt": utc_now(),
        "timestamp": utc_now(),
        "source": "VicEmergency public events GeoJSON",
        "sourceUrl": "https://emergency.vic.gov.au/public/events-geojson.json",
        "targetArea": MARIBYRNONG["name"],
        "location": MARIBYRNONG["name"],
        "officialWarningLevel": "No active warning",
        "rainfallTrend": "normal",
        "riverTrend": "stable",
        "dataStatus": "current",
        "isRealCurrentWarning": True,
        "ruleUsed": rule_label_for_state(display_state),
        "provenanceNote": "Current Official Mode uses public official endpoint checks where available; it does not represent approved formal VicEmergency data-feed access.",
        "matchedEvents": [],
        "checkedEventCount": len(all_items),
        "sourceErrors": errors,
        "officialDataNotice": "Proof-of-concept uses public official endpoints. Production deployment should use approved VicEmergency/EMV/Council data-sharing access.",
    }


def warning_level_for_event(event):
    text = f"{event.get('title', '')} {event.get('text', '')}".lower()
    if any(term in text for term in ["evacuate", "evacuation", "emergency warning"]):
        return "Emergency Warning - Evacuate"
    if any(term in text for term in ["watch and act", "flood warning"]):
        return "Watch and Act"
    if "advice" in text or event.get("risk") == "MEDIUM":
        return "Advice"
    return "No active warning"


def rule_state_for_warning(warning_level, data_status):
    warning = warning_level.lower()
    if data_status in ["stale", "connection_lost"]:
        return "OFFLINE"
    if "emergency warning" in warning or "evacuate" in warning or "evacuation" in warning:
        return "LEAVE_NOW"
    if "watch and act" in warning:
        return "ACT_NOW"
    if "advice" in warning:
        return "PREPARE"
    return "READY"


def rule_label_for_state(display_state):
    return {
        "READY": "No active warning -> READY",
        "PREPARE": "Advice -> PREPARE",
        "ACT_NOW": "Watch and Act -> ACT_NOW",
        "LEAVE_NOW": "Emergency Warning/Evacuate -> LEAVE_NOW",
        "OFFLINE": "stale/connection_lost -> OFFLINE",
    }.get(display_state, "Official warning level -> display state")


def actions_for_risk(risk):
    if risk == "HIGH":
        return [
            "Move to higher ground if advised.",
            "Take phone, medicine, keys and documents.",
            "Do not walk or drive through floodwater.",
            "Check family and neighbours.",
        ]
    if risk == "MEDIUM":
        return [
            "Prepare your emergency bag.",
            "Move valuables above floor level.",
            "Move car and pets to higher ground.",
            "Keep monitoring official warnings.",
        ]
    return [
        "Keep monitoring official updates.",
        "Review your household flood plan.",
        "Keep phone charged.",
        "Know your safe route.",
    ]


def distance_km(lat1, lon1, lat2, lon2):
    radius = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def source_health():
    results = []

    for source in HEALTH_SOURCES:
        started = time.time()
        try:
            body = fetch_bytes(source["url"])
            results.append({
                "id": source["id"],
                "name": source["name"],
                "url": source["url"],
                "ok": True,
                "bytes": len(body),
                "latencyMs": round((time.time() - started) * 1000),
            })
        except Exception as exc:
            results.append({
                "id": source["id"],
                "name": source["name"],
                "url": source["url"],
                "ok": False,
                "error": str(exc),
            })

    return {"checkedAt": utc_now(), "sources": results}


def utc_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class FloodDisplayHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def end_headers(self):
        if self.path.startswith("/api/"):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)

        try:
            if parsed.path == "/api/flood-status":
                self.send_json(build_flood_status())
                return

            if parsed.path == "/api/source-health":
                self.send_json(source_health())
                return

            if parsed.path == "/api/sources":
                with open(os.path.join(ROOT, "data", "official_sources.json"), encoding="utf-8") as handle:
                    self.send_json(json.load(handle))
                return

            super().do_GET()
        except Exception as exc:
            self.send_json({
                "error": str(exc),
                "officialDataNotice": "Use public official feeds for proof-of-concept only; request approved access for production deployment.",
            }, status=500)

    def send_json(self, body, status=200):
        payload = json.dumps(body, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main():
    server = ThreadingHTTPServer(("", PORT), FloodDisplayHandler)
    print(f"Flood Display running at http://localhost:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
