import json, requests
S=requests.Session(); S.headers["User-Agent"]="Mozilla/5.0 (privat, Papier-Test)"
G="https://gamma-api.polymarket.com"
ev=S.get(G+"/events",params={"slug":"highest-temperature-in-tokyo-on-november-29-2026"},timeout=40).json()
print("slug-abfrage", len(ev)); e=ev[0]; print("tags", [t.get("slug") for t in e.get("tags",[])])
print("DESC", e["description"][:1200])
for m in e["markets"]: print(" ", repr(m.get("groupItemTitle")), m.get("outcomePrices"), "ask", m.get("bestAsk"), "bid", m.get("bestBid"), "liq", m.get("liquidityNum"), "closed", m.get("closed"), m.get("endDate"))
for tag in [t.get("slug") for t in e.get("tags",[])]:
    r=S.get(G+"/events",params={"tag_slug":tag,"closed":"false","limit":500},timeout=60).json()
    print("tag", tag, len(r), [x["slug"] for x in r[:4]])
st=S.get("https://aviationweather.gov/api/data/stationinfo",params={"ids":"RJTT,KLGA,EGLC","format":"json"},timeout=40); print("station", st.status_code, st.text[:500])
mt=S.get("https://aviationweather.gov/api/data/metar",params={"ids":"RJTT","format":"json","hours":24},timeout=40); print("metar", mt.status_code, len(mt.content), mt.text[:400])
ev2=S.get(G+"/events",params={"slug":"highest-temperature-in-nyc-on-november-29-2026"},timeout=40).json()
if ev2: print("NYC", ev2[0]["description"][:400], [m.get("groupItemTitle") for m in ev2[0]["markets"]])
