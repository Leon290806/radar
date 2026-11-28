import json, requests, time
S=requests.Session(); S.headers["User-Agent"]="btc-radar (privat)"
def g(url, **kw):
    t=time.time()
    try:
        r=S.get(url, timeout=60, **kw); dt=round(time.time()-t,1)
        print(f"\n### {url[:120]} -> {r.status_code} {len(r.content)}B {dt}s", {k:v for k,v in r.headers.items() if 'limit' in k.lower() or 'retry' in k.lower()})
        return r
    except Exception as e:
        print("\n###", url, "ERR", e); return None
CM="https://community-api.coinmetrics.io/v4"
r=g(CM+"/catalog/asset-metrics?assets=btc")
if r is not None and r.ok:
    ms=[m["metric"] for m in r.json()["data"][0]["metrics"]]
    print(len(ms), "metrics"); want=[m for m in ms if any(k in m for k in ("Price","CapReal","MVRV","Sply","Iss","Hash","AdrAct","Fee","NVT","SER","CapMrkt","Rev","ROI","VelCur","TxTfrValAdj"))]
    print(want)
r=g(CM+"/timeseries/asset-metrics", params={"assets":"btc","metrics":"PriceUSD,CapMrktCurUSD,CapRealUSD,CapMVRVCur,SplyCur,IssTotUSD,HashRate,AdrActCnt,FeeTotUSD","frequency":"1d","start_time":"2010-07-18","page_size":10000})
if r is not None:
    j=r.json(); d=j.get("data",[]); print("rows",len(d), d[:1], d[-1:] if d else "", "next" if j.get("next_page_url") else "", j.get("error"))
for ep in ["mvrv-zscore","nupl","sopr","puell-multiple","realized-price","sth-realized-price","lth-realized-price","sth-mvrv","lth-mvrv","reserve-risk","rhodl-ratio","nrpl","hashribbons","fear-greed"]:
    r=g(f"https://bitcoin-data.com/v1/{ep}")
    if r is not None:
        try:
            j=r.json(); print(type(j).__name__, len(j) if hasattr(j,'__len__') else '', json.dumps(j[:1] if isinstance(j,list) else j)[:300], json.dumps(j[-1:] if isinstance(j,list) else '')[:200])
        except Exception as e: print(r.text[:200])
    time.sleep(1)
r=g("https://api.alternative.me/fng/?limit=0&format=json")
if r is not None and r.ok: j=r.json()["data"]; print(len(j), j[0], j[-1])
r=g("https://api.blockchain.info/charts/market-price?timespan=all&format=json&sampled=false")
if r is not None and r.ok: j=r.json()["values"]; print(len(j), j[0], j[-1])
r=g("https://api.blockchain.info/charts/mvrv?timespan=all&format=json")
if r is not None: print(r.text[:200])
r=g("https://mempool.space/api/v1/mining/hashrate/all")
if r is not None and r.ok: print(str(r.json())[:200])
