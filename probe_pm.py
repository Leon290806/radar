import json, requests
S=requests.Session(); S.headers["User-Agent"]="Mozilla/5.0 (privat, Papier-Test)"
K="https://api.elections.kalshi.com/trade-api/v2"
r=S.get(K+"/series",params={"category":"Economics"},timeout=40); print("series", r.status_code)
ser=[(x["ticker"],x["title"]) for x in r.json().get("series",[])] if r.ok else []
print(len(ser)); print([s for s in ser if any(k in s[1].lower() for k in ("cpi","inflation","unemploy","payroll","jobs","gdp"))][:40])
for t in ["KXCPI","KXCPIYOY","KXCPICORE","KXCPICOREYOY","KXU3","KXPAYROLLS","KXGDP"]:
    x=S.get(K+"/events",params={"series_ticker":t,"status":"open","with_nested_markets":"true","limit":2},timeout=40)
    ev=x.json().get("events",[]) if x.ok else []
    print("\nEV", t, x.status_code, len(ev))
    for e in ev[:2]: print("  ", e["event_ticker"], e.get("title"), e.get("sub_title"), [(m["ticker"].rsplit('-',1)[1], m.get("yes_sub_title"), m.get("yes_bid_dollars"), m.get("yes_ask_dollars")) for m in e.get("markets",[])[:9]])
