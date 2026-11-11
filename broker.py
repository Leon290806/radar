# -*- coding: utf-8 -*-
"""
Broker-Anbindung: führt die Empfehlungen des Radars automatisch bei Alpaca aus (Standard: Paper Trading = Spielgeld).

Ablauf bei jedem Abendlauf (nach US-Börsenschluss):
  1. Eigene offene Orders des Radars löschen (sie werden mit aktuellen Werten neu gesetzt).
  2. Positionen, die der Radar verkauft hat (Zeitstopp, Stopp, ...), zur nächsten Eröffnung verkaufen.
  3. Für jede offene Position eine Stopp-Order (GTC) zum aktuellen, nachgezogenen Stopp setzen.
  4. Neue Kaufsignale als Limit-Kauf für den nächsten Handelstag – mit angehängter Stopp-Order (OTO).
  5. Freies Geld wie im Musterdepot im S&P-500-ETF (SPY) halten – im Abwärtstrend nicht.
Der Radar fasst nur Aktien an, die er selbst empfohlen hat. Eigene Käufe im Konto bleiben unberührt.
Während die Börse offen ist, werden keine Orders gesendet – dann wird nur der Kontostand gelesen.

Schlüssel als GitHub-Secrets: ALPACA_KEY_ID und ALPACA_SECRET_KEY. Ohne Schlüssel passiert nichts.
"""
import datetime as dt
import math
import os
import time

import requests

PAPER = "https://paper-api.alpaca.markets"
LIVE = "https://api.alpaca.markets"
PREFIX = "radar"


class Alpaca:
    def __init__(self, key, secret, live=False):
        self.url = LIVE if live else PAPER
        self.h = {"APCA-API-KEY-ID": key.strip(), "APCA-API-SECRET-KEY": secret.strip()}

    def _r(self, methode, pfad, **kw):
        for versuch in range(3):
            r = requests.request(methode, self.url + pfad, headers=self.h, timeout=30, **kw)
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(2 * (versuch + 1))
                continue
            break
        if r.status_code >= 400:
            raise RuntimeError(f"{methode} {pfad}: HTTP {r.status_code} {r.text[:200]}")
        return r.json() if r.text else None

    def get(self, pfad, **params):
        return self._r("GET", pfad, params=params or None)

    def post(self, pfad, daten):
        return self._r("POST", pfad, json=daten)

    def delete(self, pfad):
        return self._r("DELETE", pfad)


def _bestellen(a, erg, order):
    """Order senden; ein Fehler bei einer Order stoppt nicht die übrigen."""
    try:
        a.post("/v2/orders", order)
        return True
    except Exception as e:
        erg["fehler"].append(f"{order.get('side')} {order.get('symbol')} ({order.get('type')}): {str(e)[:220]}")
        return False


def _us(t):
    return "." not in t and "^" not in t and "=" not in t


def _f(x, n=2):
    try:
        return round(float(x), n)
    except (TypeError, ValueError):
        return None


def _oid(text):
    return f"{PREFIX}-{text}-{dt.datetime.utcnow():%Y%m%d%H%M%S%f}"[:48]


def schnappschuss(a, eigene, kern="SPY"):
    """Kontostand, Positionen, offene Orders und Verlauf lesen."""
    konto = a.get("/v2/account")
    pos = a.get("/v2/positions")
    orders = a.get("/v2/orders", status="open", limit=500, nested="true")
    stopps = {}
    for o in orders:
        for x in [o] + (o.get("legs") or []):
            if x.get("side") == "sell" and x.get("type") in ("stop", "stop_limit") and x.get("stop_price"):
                stopps[x["symbol"]] = _f(x["stop_price"])
    verlauf = {"t": [], "eq": []}
    try:
        h = a.get("/v2/account/portfolio/history", period="1A", timeframe="1D")
        for ts, eq in zip(h.get("timestamp") or [], h.get("equity") or []):
            if eq:
                verlauf["t"].append(dt.datetime.utcfromtimestamp(ts).date().isoformat())
                verlauf["eq"].append(round(float(eq), 2))
    except Exception:
        pass
    return {
        "konto": {"equity": _f(konto.get("equity")), "cash": _f(konto.get("cash")), "kaufkraft": _f(konto.get("buying_power")),
                  "vortag": _f(konto.get("last_equity")), "waehrung": konto.get("currency", "USD"), "status": konto.get("status"),
                  "nummer": (konto.get("account_number") or "")[-4:]},
        "positionen": sorted([{"t": p["symbol"], "qty": _f(p["qty"], 4), "einstand": _f(p["avg_entry_price"]), "kurs": _f(p["current_price"]),
                               "wert": _f(p["market_value"]), "gv": _f(p["unrealized_pl"]), "gv_pct": _f(p["unrealized_plpc"], 4),
                               "heute": _f(p.get("unrealized_intraday_plpc"), 4), "stopp": stopps.get(p["symbol"]),
                               "radar": p["symbol"] in eigene or p["symbol"] == kern} for p in pos], key=lambda x: -(x["wert"] or 0)),
        "orders": [{"t": o["symbol"], "seite": o["side"], "typ": o["type"], "qty": _f(o.get("qty"), 4), "limit": _f(o.get("limit_price")),
                    "stopp": _f(o.get("stop_price")), "status": o["status"], "tif": o.get("time_in_force"),
                    "radar": (o.get("client_order_id") or "").startswith(PREFIX), "zeit": (o.get("submitted_at") or "")[:16]}
                   for o in orders],
        "verlauf": verlauf,
    }


def synchronisieren(dep, cfg, regime, kern_kurs, kern=None):
    """Gleicht das Broker-Konto mit dem Journal ab. Rückgabe: kurzer Text fürs Protokoll (ohne Ticker)."""
    key, sec = os.environ.get("ALPACA_KEY_ID"), os.environ.get("ALPACA_SECRET_KEY")
    if not getattr(cfg, "BROKER_AKTIV", True) or not key or not sec:
        dep["broker"] = {"verbunden": False}
        return "Broker: nicht verbunden (keine Schlüssel)."
    live = bool(getattr(cfg, "BROKER_LIVE", False))
    a = Alpaca(key, sec, live)
    alt = dep.get("broker") or {}
    eigene = set(alt.get("eigene") or [])
    erg = {"verbunden": True, "modus": "Live (echtes Geld)" if live else "Paper Trading (Spielgeld)",
           "zeit": dt.datetime.now().strftime("%d.%m.%Y %H:%M"), "aktionen": [], "fehler": [], "start": alt.get("start")}
    try:
        uhr = a.get("/v2/clock")
        konto = a.get("/v2/account")
        if konto.get("trading_blocked") or konto.get("account_blocked"):
            raise RuntimeError("Konto ist für den Handel gesperrt.")
        equity = float(konto["equity"])
        erg["start"] = erg["start"] or {"datum": dt.date.today().isoformat(), "equity": equity}
        kern = kern or getattr(cfg, "BROKER_KERN_TICKER", "SPY")
        erg["kern"] = kern
        alt_kern = {t for t in (alt.get("kern_alt") or []) + [alt.get("kern") or getattr(cfg, "BROKER_KERN_TICKER", "SPY")] if t and t != kern}
        erg["kern_alt"] = sorted(alt_kern)
        if uhr.get("is_open"):
            erg["aktionen"].append({"typ": "info", "text": "Börse offen – keine Orders gesendet, nur Kontostand gelesen."})
        else:
            pos = {p["symbol"]: p for p in a.get("/v2/positions")}
            # 1) eigene offene Orders löschen
            for o in a.get("/v2/orders", status="open", limit=500):
                if (o.get("client_order_id") or "").startswith(PREFIX):
                    a.delete(f"/v2/orders/{o['id']}")
            time.sleep(2)
            soll = {tr["ticker"]: tr for tr in dep["trades"] if tr["status"] in ("offen", "geplant") and _us(tr["ticker"])}
            cash = float(konto.get("cash") or 0)
            # 1b) alter Kern-ETF (z. B. SPY, wenn der Kern jetzt QLD ist) wird verkauft
            for sym in list(alt_kern):
                if sym in pos and sym not in soll and float(pos[sym]["qty"]) > 0:
                    qty = abs(float(pos[sym]["qty"]))
                    if not _bestellen(a, erg, {"symbol": sym, "qty": str(qty), "side": "sell", "type": "market", "time_in_force": "day",
                                          "client_order_id": _oid("kernalt")}):
                        continue
                    erg["aktionen"].append({"typ": "kern", "t": sym, "qty": qty, "text": f"Kern wechselt zu {kern} – alten Kern-ETF verkaufen"})
                    cash += float(pos[sym]["market_value"])
                elif sym not in pos:
                    alt_kern.discard(sym)
            erg["kern_alt"] = sorted(alt_kern)
            # 2) Verkaufen, was der Radar nicht mehr hält (nur eigene Positionen)
            for sym, p in pos.items():
                if sym == kern or sym in soll or sym not in eigene:
                    continue
                qty = abs(float(p["qty"]))
                if qty > 0:
                    if not _bestellen(a, erg, {"symbol": sym, "qty": str(qty), "side": "sell", "type": "market", "time_in_force": "day",
                                          "client_order_id": _oid("aus")}):
                        continue
                    erg["aktionen"].append({"typ": "verkaufen", "t": sym, "qty": qty, "text": "Radar hat verkauft – Verkauf zur Eröffnung"})
                    cash += float(p["market_value"])
                    eigene.discard(sym)
            # 3) Stopp-Orders für gehaltene Positionen
            einzel_wert = 0.0
            for sym, tr in soll.items():
                if tr["status"] != "offen":
                    continue
                if sym not in pos:
                    # Nachkauf: Position aus dem Musterdepot fehlt im Konto (z. B. Neuaufbau, Limit nicht erreicht).
                    # Nur, wenn der Kurs kaum über dem Einstieg liegt, genug Abstand zum Stopp ist und noch Zeit bleibt.
                    kurs, ein, st = float(tr.get("kurs") or 0), float(tr.get("einstieg_kurs") or 0), float(tr.get("stopp") or 0)
                    rest = (tr.get("parameter") or {}).get("HALTEDAUER", 40) - int(tr.get("tage") or 0)
                    grund = None
                    if not getattr(cfg, "BROKER_NACHKAUF", True):
                        grund = "Nachkauf ausgeschaltet"
                    elif not (kurs > 0 and ein > 0 and st > 0):
                        grund = "keine Kursdaten"
                    elif kurs > ein * (1 + getattr(cfg, "BROKER_NACHKAUF_MAX_UEBER", 0.03)):
                        grund = f"Kurs schon {kurs / ein - 1:.0%} über dem Einstieg"
                    elif (kurs - st) / kurs < getattr(cfg, "BROKER_NACHKAUF_MIN_STOPP", 0.03):
                        grund = f"nur {(kurs - st) / kurs:.1%} bis zum Stopp"
                    elif rest < 10:
                        grund = f"nur noch {rest} Tage Haltedauer"
                    if grund:
                        erg["aktionen"].append({"typ": "hinweis", "t": sym, "text": f"Im Musterdepot offen, im Konto nicht – kein Nachkauf ({grund})"})
                        continue
                    limit = round(kurs * 1.01, 2)
                    qty = math.floor(min(float(tr.get("gewicht") or 0.08) * equity, max(cash, 0) * 0.98) / limit)
                    if qty < 1:
                        continue
                    if _bestellen(a, erg, {"symbol": sym, "qty": str(qty), "side": "buy", "type": "limit", "time_in_force": "day",
                                           "limit_price": f"{limit:.2f}", "order_class": "oto",
                                           "stop_loss": {"stop_price": f"{st:.2f}"}, "client_order_id": _oid("nach")}):
                        einzel_wert += qty * limit
                        cash -= qty * limit
                        eigene.add(sym)
                        erg["aktionen"].append({"typ": "kaufen", "t": sym, "qty": qty, "preis": _f(limit),
                                                "text": f"Nachkauf (im Musterdepot seit {tr.get('einstieg_datum', '')}) – Limit {limit:.2f} mit Stopp {st:.2f}".replace(".", ",")})
                    continue
                qty = int(float(pos[sym]["qty"]))
                einzel_wert += float(pos[sym]["market_value"])
                eigene.add(sym)
                if qty > 0 and tr.get("stopp"):
                    if not _bestellen(a, erg, {"symbol": sym, "qty": str(qty), "side": "sell", "type": "stop", "time_in_force": "gtc",
                                          "stop_price": f"{tr['stopp']:.2f}", "client_order_id": _oid("stopp")}):
                        continue
                    erg["aktionen"].append({"typ": "stopp", "t": sym, "qty": qty, "preis": _f(tr["stopp"]), "text": "Stopp-Order gesetzt"})
            # 4) neue Käufe: Limit für den nächsten Handelstag + angehängter Stopp
            for sym, tr in soll.items():
                if tr["status"] != "geplant" or sym in pos:
                    continue
                qty = math.floor(min(tr["gewicht"] * equity, max(cash, 0) * 0.98) / tr["limit"])
                if qty < 1:
                    erg["aktionen"].append({"typ": "hinweis", "t": sym, "text": "Kontowert zu klein für 1 Stück"})
                    continue
                if not _bestellen(a, erg, {"symbol": sym, "qty": str(qty), "side": "buy", "type": "limit", "time_in_force": "day",
                                      "limit_price": f"{tr['limit']:.2f}", "order_class": "oto",
                                      "stop_loss": {"stop_price": f"{tr['stopp_hinweis']:.2f}"}, "client_order_id": _oid("kauf")}):
                    continue
                einzel_wert += qty * tr["limit"]
                cash -= qty * tr["limit"]
                eigene.add(sym)
                erg["aktionen"].append({"typ": "kaufen", "t": sym, "qty": qty, "preis": _f(tr["limit"]),
                                        "text": f"Limit-Kauf ({tr['gewicht'] * 100:.0f} % des Kontos) mit Stopp {tr['stopp_hinweis']:.2f}".replace(".", ",")})
            # 5) Kern: freies Geld im S&P-500-ETF (im Abwärtstrend nicht)
            if getattr(cfg, "BROKER_KERN", True) and kern_kurs and kern_kurs > 0:
                ist = float(pos[kern]["market_value"]) if kern in pos else 0.0
                ziel = max(0.0, (equity - einzel_wert) * 0.97) if regime else 0.0
                diff = ziel - ist
                qty = math.floor(abs(diff) / kern_kurs)
                if abs(diff) > 0.03 * equity and qty >= 1:
                    seite = "buy" if diff > 0 else "sell"
                    if seite == "sell" and kern in pos:
                        qty = min(qty, int(float(pos[kern]["qty"])))
                    if seite == "buy":                       # ohne Kredit: nur mit vorhandenem Geld
                        qty = min(qty, math.floor(max(cash, 0) * 0.98 / kern_kurs))
                        # Hebel-ETFs sind nicht beleihbar und Verkaufserlöse (z. B. alter Kern) zählen erst nach der
                        # Ausführung – deshalb nur so viel, wie das Konto jetzt tatsächlich kaufen kann; Rest am nächsten Abend.
                        try:
                            k2 = a.get("/v2/account")
                            frei = min(float(k2.get("non_marginable_buying_power") or 0), float(k2.get("buying_power") or 0))
                            if frei > 0 and qty * kern_kurs > frei * 0.97:
                                qty = math.floor(frei * 0.97 / kern_kurs)
                                erg["aktionen"].append({"typ": "info", "t": kern, "text": "Kern wird in zwei Schritten getauscht: Rest kauft der Radar, sobald der Verkauf ausgeführt ist"})
                        except Exception:
                            pass
                    if qty >= 1:
                        if _bestellen(a, erg, {"symbol": kern, "qty": str(qty), "side": seite, "type": "market", "time_in_force": "day",
                                               "client_order_id": _oid("kern")}):
                            erg["aktionen"].append({"typ": "kern", "t": kern, "qty": qty,
                                                    "text": ("Kern aufstocken" if seite == "buy" else "Kern verringern") + " zur Eröffnung"})
    except Exception as e:
        erg["fehler"].append(str(e)[:300])
    try:
        erg.update(schnappschuss(a, eigene, kern))
    except Exception as e:
        erg["fehler"].append(f"Kontostand nicht lesbar: {str(e)[:200]}")
    erg["eigene"] = sorted(eigene)
    dep["broker"] = erg
    n = sum(1 for x in erg["aktionen"] if x["typ"] in ("kaufen", "verkaufen", "stopp", "kern"))
    import re
    arten = sorted({re.sub(r"\b[A-Z]{1,5}\b", "…", f)[:120] for f in erg["fehler"]})
    return f"Broker: verbunden ({erg['modus']}), {n} Order(s) gesendet" + (f", {len(erg['fehler'])} Fehler: " + " | ".join(arten) if erg["fehler"] else "") + "."
