import json, requests, re
S=requests.Session(); S.headers["User-Agent"]="Mozilla/5.0 (privat, Papier-Test)"
G="https://gamma-api.polymarket.com"
for params in [{"tag_slug":"weather","closed":"false","limit":5},{"tag_slug":"temperature","closed":"false","limit":5}]:
    r=S.get(G+"/events",params=params,timeout=40); print("\n### events",params,r.status_code,len(r.content))
    try:
        ev=r.json(); print(len(ev))
        for e in ev[:3]:
            print("-", e.get("title"), e.get("slug"), e.get("endDate"), "markets:", len(e.get("markets",[])))
        if ev:
            e=ev[0]; print("DESC:", (e.get("description") or "")[:900])
            for m in e.get("markets",[])[:3]: print("  m", m.get("question"), m.get("groupItemTitle"), m.get("outcomePrices"), m.get("bestAsk"), m.get("bestBid"), m.get("lastTradePrice"), m.get("clobTokenIds","")[:60], m.get("liquidity"), m.get("volume24hr"))
    except Exception as ex: print(ex, r.text[:300])
r=S.get(G+"/public-search",params={"q":"highest temperature tokyo","limit_per_type":3},timeout=40); print("\n### search", r.status_code, r.text[:600])
o=S.get("https://ensemble-api.open-meteo.com/v1/ensemble",params={"latitude":35.55,"longitude":139.78,"daily":"temperature_2m_max","models":"ecmwf_ifs025","forecast_days":3,"timezone":"Asia/Tokyo"},timeout=40)
print("\n### openmeteo ens", o.status_code, o.text[:700])
k=S.get("https://api.elections.kalshi.com/trade-api/v2/markets",params={"limit":3,"status":"open","series_ticker":"KXFED"},timeout=40); print("\n### kalshi", k.status_code, k.text[:600])
