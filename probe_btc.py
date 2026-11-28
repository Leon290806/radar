import json, requests, os
os.makedirs("out", exist_ok=True)
CM="https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
r=requests.get(CM, params={"assets":"btc","metrics":"PriceUSD,CapMrktCurUSD,CapMVRVCur,SplyCur,IssTotUSD,HashRate,AdrActCnt","frequency":"1d","start_time":"2010-07-18","page_size":10000}, timeout=90)
j=r.json(); print("cm", r.status_code, len(j.get("data",[])), bool(j.get("next_page_url")))
json.dump(j["data"], open("out/cm.json","w"))
f=requests.get("https://api.alternative.me/fng/?limit=0&format=json", timeout=60).json()["data"]; json.dump(f, open("out/fng.json","w")); print("fng", len(f))
bg={}
for ep in ["sth-realized-price","lth-realized-price","sopr","sth-mvrv"]:
    x=requests.get(f"https://bitcoin-data.com/v1/{ep}", params={"startday":"2011-01-01"}, timeout=60)
    print(ep, x.status_code, len(x.content)); 
    if x.ok: bg[ep]=x.json(); print(" ", len(bg[ep]), bg[ep][0] if bg[ep] else "")
json.dump(bg, open("out/bg.json","w"))
