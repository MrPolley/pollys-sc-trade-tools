#!/usr/bin/env python3
"""
Fetches current commodity buy/sell prices and stock levels from the UEX API 2.0
for every station used across Polly's Trade Tools, and writes a single
data/prices.json file that the HTML tools load at runtime.

Requires the environment variable UEX_API_TOKEN to be set (a Bearer token from
https://uexcorp.space/api/apps). NEVER hardcode the token in this file or any
committed file -- pass it via an environment variable / GitHub Actions secret.

Requires the `requests` package (pip install requests).

Usage:
    export UEX_API_TOKEN="your-token-here"
    python3 fetch_uex_prices.py

Output:
    data/prices.json
"""

import json
import os
import sys
import time
import requests
from datetime import datetime, timezone

API_BASE = "https://api.uexcorp.uk/2.0"
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "prices.json")

# Realistic browser headers -- Cloudflare's bot protection (error 1010) blocks
# requests that don't look like they came from an actual browser: a plain
# User-Agent isn't enough by itself, it also checks for the accompanying
# headers a real browser always sends alongside it.
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://uexcorp.space/",
    "Origin": "https://uexcorp.space",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}

STATIONS_OF_INTEREST = {
    "Everus Harbor": ["everus harbor"],
    "Port Tressler": ["port tressler"],
    "ARC-L1": ["arc-l1"],
    "ARC-L2": ["arc-l2"],
    "ARC-L3": ["arc-l3"],
    "ARC-L4": ["arc-l4"],
    "CRU-L1": ["cru-l1"],
    "CRU-L4": ["cru-l4"],
    "CRU-L5": ["cru-l5"],
    "MIC-L1": ["mic-l1"],
    "MIC-L2": ["mic-l2"],
    "HUR-L1": ["hur-l1"],
    "HUR-L3": ["hur-l3"],
    "HUR-L4": ["hur-l4"],
    "Seraphim": ["seraphim"],
    "Baijini Point": ["baijini point"],
    "TDD New Babbage": ["new babbage"],
    "Levski": ["levski"],
    "ArcCorp 045": ["arccorp 045", "arccorp mining area 045"],
    "Rustville": ["rustville"],
    "Rod's Fuel 'N Supplies": ["rod's fuel", "rods fuel"],
    "Gaslight": ["gaslight"],
    "Ruin Station": ["ruin station"],
    "Endgame": ["endgame"],
    "Seer's Canyon": ["seer's canyon", "seers canyon"],
    "Dudley & Daughters": ["dudley"],
    "Megumi": ["megumi"],
    "Checkmate": ["checkmate"],
    "Starlight Service": ["starlight service"],
    "Stanton Gateway (Pyro)": ["stanton gateway"],
    "Nyx Gateway (Stanton)": ["nyx gateway"],
    "Terra Gateway (Stanton)": ["terra gateway"],
    "TDD Area 18": ["area 18", "area18"],
}


def api_get(session, path, token=None, retries=3):
    url = f"{API_BASE}/{path}"
    headers = dict(BROWSER_HEADERS)
    if token:
        headers["Authorization"] = f"Bearer {token}"

    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            print(f"Attempt {attempt}: HTTP {resp.status_code} for {url}: {resp.text[:500]}",
                  file=sys.stderr)
            if resp.status_code in (403, 429) and attempt < retries:
                time.sleep(3 * attempt)
                continue
            resp.raise_for_status()
        except requests.RequestException as e:
            last_exc = e
            print(f"Attempt {attempt}: request error for {url}: {e}", file=sys.stderr)
            if attempt < retries:
                time.sleep(3 * attempt)
    if last_exc:
        raise last_exc
    raise RuntimeError(f"Failed to fetch {url} after {retries} attempts")


def match_station(terminal_name_lower):
    for our_label, substrings in STATIONS_OF_INTEREST.items():
        for s in substrings:
            if s in terminal_name_lower:
                return our_label
    return None


def main():
    token = os.environ.get("UEX_API_TOKEN")
    if not token:
        print("WARNING: UEX_API_TOKEN not set. commodities_prices_all does not "
              "require auth, so continuing without it -- but other endpoints may fail.",
              file=sys.stderr)

    session = requests.Session()

    print("Fetching commodities_prices_all ...", file=sys.stderr)
    prices_resp = api_get(session, "commodities_prices_all", token)
    if prices_resp.get("status") != "ok":
        print(f"Unexpected API status: {prices_resp.get('status')}", file=sys.stderr)
        sys.exit(1)
    rows = prices_resp.get("data", [])
    print(f"Received {len(rows)} price rows.", file=sys.stderr)

    stations = {label: {"buy": [], "sell": []} for label in STATIONS_OF_INTEREST}
    matched_labels_seen = set()

    for row in rows:
        terminal_name = row.get("terminal_name") or ""
        our_label = match_station(terminal_name.lower())
        if not our_label:
            continue
        matched_labels_seen.add(our_label)

        commodity_name = row.get("commodity_name")
        price_buy = row.get("price_buy") or 0
        price_sell = row.get("price_sell") or 0
        scu_buy_stock = row.get("scu_buy") or 0

        if price_buy and price_buy > 0:
            stations[our_label]["buy"].append({
                "name": commodity_name,
                "price": round(price_buy),
                "stock": round(scu_buy_stock),
            })
        if price_sell and price_sell > 0:
            stations[our_label]["sell"].append({
                "name": commodity_name,
                "price": round(price_sell),
            })

    missing = set(STATIONS_OF_INTEREST) - matched_labels_seen
    if missing:
        print(f"WARNING: no data matched for: {sorted(missing)}. "
              f"UEX may have renamed these terminals -- update STATIONS_OF_INTEREST.",
              file=sys.stderr)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "UEX API 2.0 (commodities_prices_all)",
        "stations": stations,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Wrote {OUTPUT_PATH}", file=sys.stderr)
    print(f"Matched {len(matched_labels_seen)}/{len(STATIONS_OF_INTEREST)} known stations.", file=sys.stderr)


if __name__ == "__main__":
    main()

