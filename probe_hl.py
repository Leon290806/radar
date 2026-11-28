import json, time, requests
t=time.time()
r=requests.get("https://stats-data.hyperliquid.xyz/Mainnet/leaderboard",timeout=60)
print("leaderboard",r.status_code,len(r.content),"bytes",round(time.time()-t,1),"s")
L=r.json()
rows=L.get("leaderboardRows",L if isinstance(L,list) else [])
print("keys top",list(L.keys())[:5] if isinstance(L,dict) else type(L),"rows",len(rows))
print(json.dumps(rows[0])[:900])
def wp(r,w):
    for k,v in r["windowPerformances"]:
        if k==w: return v
big=[r for r in rows if float(r.get("accountValue") or 0)>100000]
print("rows >100k acct",len(big))
mon=sorted(big,key=lambda r:-float(wp(r,"month")["pnl"]))[:5]
for r in mon: print(r["ethAddress"],r.get("displayName"),r["accountValue"],wp(r,"month"),wp(r,"allTime"))
H="https://api.hyperliquid.xyz/info"
a=mon[0]["ethAddress"]
for body in [{"type":"clearinghouseState","user":a},{"type":"portfolio","user":a},{"type":"userFillsByTime","user":a,"startTime":int((time.time()-30*86400)*1000)}]:
    x=requests.post(H,json=body,timeout=30)
    print("\n==",body["type"],x.status_code,len(x.content))
    j=x.json()
    s=json.dumps(j)
    print(s[:1500])
    if body["type"]=="userFillsByTime": print("fills",len(j)); print(json.dumps(j[-1]) if j else "")
    if body["type"]=="portfolio": print([p[0] for p in j]); print({p[0]:{k:len(v) if isinstance(v,list) else v for k,v in p[1].items()} for p in j})
x=requests.post(H,json={"type":"allMids"},timeout=30); print("allMids",x.status_code,list(x.json().items())[:3])
