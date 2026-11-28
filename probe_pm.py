import json, requests
S=requests.Session(); S.headers["User-Agent"]="Mozilla/5.0 (privat, Papier-Test)"
G="https://gamma-api.polymarket.com"; K="https://api.elections.kalshi.com/trade-api/v2"
ev=S.get(G+"/events",params={"tag_slug":"fed-rates","closed":"false","limit":50},timeout=40).json()
print("PM fed events", len(ev))
for e in ev[:12]:
    print("-", e["slug"], "|", e["title"], e.get("endDate"))
    if "decision" in e["slug"]:
        for m in e["markets"]: print("    ", m.get("groupItemTitle"), m.get("outcomePrices"), m.get("bestAsk"), m.get("bestBid"), m.get("closed"))
for ser in ["KXFEDDECISION","KXFED","FEDDECISION"]:
    r=S.get(K+"/events",params={"series_ticker":ser,"status":"open","with_nested_markets":"true","limit":5},timeout=40)
    print("\nKalshi", ser, r.status_code)
    try:
        for e in r.json().get("events",[])[:4]:
            print("-", e["event_ticker"], e.get("title"), e.get("sub_title"))
            for m in e.get("markets",[])[:8]: print("    ", m["ticker"], m.get("yes_sub_title"), m.get("yes_bid_dollars"), m.get("yes_ask_dollars"), m.get("last_price_dollars"), m.get("volume_fp") or m.get("volume"))
    except Exception as ex: print(ex, r.text[:300])
r=S.get(K+"/series",params={"category":"Economics"},timeout=40); print("\nseries econ", r.status_code, [ (x["ticker"], x["title"]) for x in r.json().get("series",[])][:60] if r.ok else r.text[:200])
