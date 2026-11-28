import json, re, requests, time
S=requests.Session(); S.headers["User-Agent"]="Mozilla/5.0 (privat, Papier-Test)"
def g(u, **p):
    r=S.get(u, params=p, timeout=40); print(f"\n### {r.url[:150]} -> {r.status_code} {len(r.content)}B"); return r
r=g("https://gamma-api.polymarket.com/public-search", q="antsaslyku", search_profiles="true")
print(r.text[:600])
addr=None
try:
    for pr in r.json().get("profiles",[]) or []:
        print(pr.get("name"), pr.get("proxyWallet")); 
        if (pr.get("name") or "").lower()=="antsaslyku": addr=pr.get("proxyWallet")
except Exception as e: print(e)
if not addr:
    h=g("https://polymarket.com/@antsaslyku")
    m=re.search(r'"proxyWallet":"(0x[0-9a-fA-F]{40})"', h.text); addr=m.group(1) if m else None
print("ADDR", addr)
if addr:
    a=g("https://data-api.polymarket.com/activity", user=addr, limit=5)
    print(json.dumps(a.json()[:3], indent=0)[:2500])
    t=g("https://data-api.polymarket.com/trades", user=addr, limit=3); print(t.text[:800])
    v=g("https://data-api.polymarket.com/value", user=addr); print(v.text[:300])
    x=a.json()
    if x:
        tok=x[0].get("asset"); cid=x[0].get("conditionId"); ts=int(x[0].get("timestamp",0))
        ph=g("https://clob.polymarket.com/prices-history", market=tok, startTs=ts-120, endTs=ts+600, fidelity=1); print(ph.text[:600])
        mk=g("https://gamma-api.polymarket.com/markets", condition_ids=cid); print(mk.text[:900])
        # older activity count last hour
        a2=g("https://data-api.polymarket.com/activity", user=addr, limit=500, start=int(time.time())-3600); 
        try: print("letzte Stunde:", len(a2.json()), {k: sum(1 for y in a2.json() if y.get("type")==k) for k in ("TRADE","REDEEM","MERGE","SPLIT")})
        except Exception as e: print(e)
        bk=g("https://clob.polymarket.com/book", token_id=tok); print(bk.text[:300])
