import sys, os, time
sys.path[:0]=["smart","."]
import wetter as W
from datetime import datetime, timezone
ev=W.offene_maerkte(); print("events", len(ev))
infos=[(e,W._event_info(e)) for e in ev]; infos=[x for x in infos if x[1]]; print("mit info", len(infos))
ic=sorted({i["icao"] for _,i in infos})[:5]; print(ic)
st=W.stationen(ic,{}); print(st)
ob=W.beobachtet(ic); print({k:(len(v), min(v)[0] if v else None) for k,v in ob.items()})
r=W._S.get(W.AWC+"/metar", params={"ids":ic[0],"format":"json","hours":168}, timeout=60); print("metar168", r.status_code, len(r.json()) if r.ok else r.text[:200])
werte,off=W.ensemble(st[ic[0]]["lat"], st[ic[0]]["lon"]); print("tage", list(werte["max"].keys()), {d:len(v) for d,v in werte["max"].items()}, off)
heute=datetime.fromtimestamp(time.time()+off, tz=timezone.utc).date().isoformat()
print(W.stations_abweichung(werte, off, ob.get(ic[0],[]), "max", heute))
