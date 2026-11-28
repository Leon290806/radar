import json, requests
CM="https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
for m in ["PriceUSD","CapMrktCurUSD","CapMVRVCur","SplyCur","IssTotUSD","HashRate","AdrActCnt","TxTfrValAdjUSD","FeeTotUSD","CapMVRVFF","SplyAct1yr","RevUSD","NVTAdj"]:
    r=requests.get(CM, params={"assets":"btc","metrics":m,"frequency":"1d","start_time":"2010-07-18","page_size":10000}, timeout=60)
    j=r.json(); d=j.get("data",[])
    print(m, r.status_code, len(d), d[0] if d else j.get("error",{}).get("message","")[:120], d[-1] if d else "", "MORE" if j.get("next_page_url") else "")
r=requests.get("https://community-api.coinmetrics.io/v4/catalog-v2/asset-metrics", params={"assets":"btc"}, timeout=60)
print("catalog", r.status_code, r.text[:300])
