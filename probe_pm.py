import json, requests, datetime as dt
S=requests.Session(); S.headers["User-Agent"]="Mozilla/5.0 (privat, Papier-Test)"
G="https://gamma-api.polymarket.com"
e=S.get(G+"/events",params={"slug":"highest-temperature-in-nyc-on-november-29-2026"},timeout=40).json()[0]
print("DESC2", e["description"][1100:3200])
heute=dt.date.today().isoformat()
r=S.get(G+"/events",params={"tag_slug":"daily-temperature","closed":"false","end_date_min":heute+"T00:00:00Z","limit":500},timeout=60).json()
print("\nOFFEN", len(r)); from collections import Counter
print(Counter(x["slug"].rsplit("-on-",1)[1] for x in r))
print(sorted(set(x["slug"].split("-on-")[0] for x in r))[:80])
