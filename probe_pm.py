import json, requests, time
S=requests.Session(); S.headers["User-Agent"]="Mozilla/5.0 (privat, Papier-Test)"
A="0x3c58ef422754ff22c7e806336feba0064d8b776b"
B="https://data-api.polymarket.com/v2"
o=S.get(B+"/openapi.json",timeout=40).json()
for path in ["/activity","/v2/activity","/trades","/v2/trades","/prices-history","/v2/prices-history"]:
    if path in o.get("paths",{}):
        op=o["paths"][path]["get"]; print("\n=== ", path, [ (p["name"], p.get("schema",{}).get("type"), p.get("schema",{}).get("enum")) for p in op.get("parameters",[])])
r=S.get(B+"/activity",params={"user":A,"limit":4},timeout=40); print("\nactivity",r.status_code, r.text[:1800])
r=S.get(B+"/trades",params={"user":A,"limit":2},timeout=40); print("\ntrades",r.status_code, r.text[:1000])
j=S.get(B+"/activity",params={"user":A,"limit":500,"start":int(time.time())-3600},timeout=40).json()
items=j.get("data", j) if isinstance(j,dict) else j
print("\nletzte Stunde", type(j).__name__, len(items) if hasattr(items,'__len__') else '', list(j.keys()) if isinstance(j,dict) else '')
try:
    x=items[0]; tok=x.get("asset") or x.get("token_id") or x.get("tokenId"); ts=int(x.get("timestamp") or 0)
    r=S.get(B+"/prices-history",params={"token_id":tok,"start":ts-180,"end":ts+600,"bucket_seconds":60},timeout=40); print("\nprices",r.status_code,r.text[:700])
    r=S.get(B+"/prices-history",params={"token_id":tok,"start":ts-180,"end":ts+600},timeout=40); print("\nprices auto",r.status_code,r.text[:700])
    cid=x.get("conditionId") or x.get("condition_id")
    r=S.get("https://gamma-api.polymarket.com/markets",params={"condition_ids":cid},timeout=40); print("\ngamma",r.status_code,r.text[:700])
    from collections import Counter; print(Counter((y.get("type"),y.get("side")) for y in items))
    print("usdc", sum(float(y.get("usdcSize") or 0) for y in items if y.get("type")=="TRADE"))
except Exception as e: print("ERR", e)
