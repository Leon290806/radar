import json, requests, time
S=requests.Session(); S.headers["User-Agent"]="Mozilla/5.0 (privat, Papier-Test)"
A="0x3c58ef422754ff22c7e806336feba0064d8b776b"
for u,p in [("https://data-api.polymarket.com/activity",{"user":A,"limit":3}),("https://data-api.polymarket.com/trades",{"user":A,"limit":3}),
            ("https://data-api.polymarket.com/positions",{"user":A,"limit":3}),("https://lb-api.polymarket.com/profit",{"window":"1d","limit":1}),
            ("https://clob.polymarket.com/markets",{"next_cursor":"MA=="}),("https://gamma-api.polymarket.com/markets",{"limit":1,"order":"id","ascending":"false"})]:
    r=S.get(u,params=p,timeout=40); print(f"\n### {u} -> {r.status_code}", dict((k,v) for k,v in r.headers.items() if k.lower() in ("cf-ray","server","x-region")), r.text[:400])
G="https://api.goldsky.com/api/public/project_cl6mb8i9h0003e201j6li0diw/subgraphs/orderbook-subgraph/0.0.1/gn"
q='{ orderFilledEvents(first: 5, orderBy: timestamp, orderDirection: desc, where: {taker: "%s"}) { id timestamp maker taker makerAssetId takerAssetId makerAmountFilled takerAmountFilled fee transactionHash } }' % A
r=S.post(G,json={"query":q},timeout=40); print("\n### goldsky taker", r.status_code, r.text[:1200])
q2=q.replace("taker:","maker:")
r=S.post(G,json={"query":q2},timeout=40); print("\n### goldsky maker", r.status_code, r.text[:1200])
