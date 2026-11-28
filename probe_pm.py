import json, requests, time
S=requests.Session(); S.headers["User-Agent"]="Mozilla/5.0 (privat, Papier-Test)"
A="0x3c58ef422754ff22c7e806336feba0064d8b776b"; B="https://data-api.polymarket.com/v2"
items=S.get(B+"/activity",params={"user":A,"limit":40},timeout=40).json()["data"]
from collections import Counter; print(Counter((y["type"],y.get("side")) for y in items)); print("zeitraum", (items[0]["timestamp"]-items[-1]["timestamp"])/3600, "h")
for x in [y for y in items if y["type"]=="TRADE"][:3]:
    slug=x["slug"]; print("\n----", x["title"], x["outcome"], "price", x["price"], "t", x["timestamp"])
    m=S.get("https://gamma-api.polymarket.com/markets",params={"slug":slug},timeout=40).json()
    if m: mm=m[0]; print("gamma", mm.get("closed"), mm.get("outcomes"), mm.get("outcomePrices"), mm.get("clobTokenIds")[:200] if mm.get("clobTokenIds") else None, mm.get("umaResolutionStatus"), mm.get("endDate"))
    toks=json.loads(m[0]["clobTokenIds"]) if m else [x["token_id"]]
    for i,t in enumerate(toks):
        ph=S.get(B+"/prices-history",params={"token_id":t,"start":x["timestamp"]-300,"end":x["timestamp"]+900,"bucket_seconds":60},timeout=40).json()["data"]
        print(" token",i,"(seiner)" if t==x["token_id"] else "", [(p["timestamp"]-x["timestamp"], p["price"]) for p in ph][:12])
red=[y for y in items if y["type"]=="REDEEM"][:2]; print("\nREDEEM sample", json.dumps(red)[:600])
j=S.get(B+"/activity",params={"user":A,"limit":500,"start":int(time.time())-86400},timeout=40).json(); print("24h:", len(j["data"]), j["pagination"])
