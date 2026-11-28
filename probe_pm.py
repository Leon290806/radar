import json, requests
S=requests.Session(); S.headers["User-Agent"]="Mozilla/5.0 (privat, Papier-Test)"
G="https://gamma-api.polymarket.com"; K="https://api.elections.kalshi.com/trade-api/v2"
for tag in ["inflation","macro-indicators","economy","gdp","labor"]:
    ev=S.get(G+"/events",params={"tag_slug":tag,"closed":"false","limit":60},timeout=40).json()
    print("\nPM", tag, len(ev))
    for e in ev[:25]:
        ms=[m.get("groupItemTitle") for m in e.get("markets",[])][:6]
        print(" -", e["slug"][:70], "|", e["title"][:70], "|", e.get("endDate","")[:10], ms)
for ser in ["KXCPI","KXCPIYOY","KXCPICORE","KXU3","KXPAYROLLS","KXGDP","KXJOBLESSCLAIMS"]:
    r=S.get(K+"/events",params={"series_ticker":ser,"status":"open","with_nested_markets":"true","limit":3},timeout=40)
    try:
        for e in r.json().get("events",[])[:2]:
            print("\nKalshi", ser, e["event_ticker"], e.get("title"), e.get("sub_title"), [(m["ticker"].rsplit('-',1)[1], m.get("yes_sub_title"), m.get("yes_bid_dollars"), m.get("yes_ask_dollars")) for m in e.get("markets",[])[:8]])
    except Exception as ex: print(ser, r.status_code, r.text[:150])
