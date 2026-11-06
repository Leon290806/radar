# -*- coding: utf-8 -*-
"""Erzeugt das Dashboard: eine einzelne HTML-Datei, optimiert fürs Handy, hell & dunkel."""
import datetime as dt
import html as _h
import json

import numpy as np


def _e(s):
    return _h.escape(str(s))


def _zahl(x, nk=2):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "–"
    return f"{x:,.{nk}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(x, nk=1, vz=True):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "–"
    return (f"{x * 100:+.{nk}f} %" if vz else f"{x * 100:.{nk}f} %").replace(".", ",")


def _klasse(x):
    if x is None or not np.isfinite(x) or abs(x) < 1e-9:
        return ""
    return "pos" if x > 0 else "neg"


def _d(iso, fmt="%d.%m."):
    return dt.date.fromisoformat(iso).strftime(fmt) if iso else "–"


def _wsym(t):
    return "€" if t.upper().endswith(".DE") else "$"


CSS = """
:root{--bg:#f4f4f1;--card:#fcfcfb;--ink:#0b0b0b;--ink2:#5a5955;--ink3:#8a8984;--line:#e6e5e0;
--s1:#2a78d6;--s2:#eb6834;--good:#0a7f0a;--bad:#c93333;--goodbg:#e7f4e7;--badbg:#fbeaea;--chip:#efeee9;--warn:#9a6a00}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#111110;--card:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;
--ink3:#8f8e86;--line:#2c2c2a;--s1:#3987e5;--s2:#d95926;--good:#4cc44c;--bad:#ec6b6b;--goodbg:#173017;--badbg:#3a1b1b;--chip:#262624;--warn:#e0a52a}}
:root[data-theme="dark"]{--bg:#111110;--card:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--ink3:#8f8e86;--line:#2c2c2a;--s1:#3987e5;
--s2:#d95926;--good:#4cc44c;--bad:#ec6b6b;--goodbg:#173017;--badbg:#3a1b1b;--chip:#262624;--warn:#e0a52a}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,system-ui,sans-serif;
font-variant-numeric:tabular-nums}
main{max-width:640px;margin:0 auto;padding:20px 16px 56px}
header{display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin-bottom:14px}
h1{font-size:22px;margin:0;letter-spacing:-.02em}
.stand{color:var(--ink3);font-size:13px}
.pill{font-size:12px;font-weight:600;padding:3px 9px;border-radius:999px;white-space:nowrap}
.pill.on{background:var(--goodbg);color:var(--good)}.pill.off{background:var(--badbg);color:var(--bad)}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px;margin-bottom:14px}
.lbl{font-size:12px;font-weight:600;color:var(--ink3);text-transform:uppercase;letter-spacing:.06em;margin:0 0 10px}
.hero .aktion{display:inline-block;font-size:12px;font-weight:700;letter-spacing:.06em;padding:4px 10px;border-radius:999px;
background:var(--goodbg);color:var(--good)}
.hero .tick{font-size:30px;font-weight:700;letter-spacing:-.02em;margin:10px 0 0}
.hero .firma{color:var(--ink2);font-size:15px}
.hero .gross{font-size:20px;font-weight:600;margin:14px 0 2px}
.hero .klein{color:var(--ink2);font-size:14px}
.schritte{list-style:none;padding:0;margin:16px 0 0;border-top:1px solid var(--line)}
.schritte li{display:flex;justify-content:space-between;gap:12px;padding:10px 0;border-bottom:1px solid var(--line);font-size:15px}
.schritte li span:first-child{color:var(--ink2)}.schritte li span:last-child{font-weight:600;text-align:right}
.score{display:flex;align-items:center;gap:10px;margin-top:14px;font-size:14px;color:var(--ink2)}
.score .bahn{flex:1;height:6px;border-radius:3px;background:var(--chip);position:relative;overflow:hidden}
.score .bahn i{position:absolute;left:0;top:0;bottom:0;border-radius:3px;background:var(--s1)}
.gruende{list-style:none;padding:0;margin:14px 0 0}
.gruende li{padding:6px 0 6px 26px;position:relative;font-size:15px}
.gruende li:before{content:"";position:absolute;left:2px;top:11px;width:12px;height:7px;border-left:2px solid var(--good);
border-bottom:2px solid var(--good);transform:rotate(-45deg)}
.ruhe .gross{font-size:22px;font-weight:700;margin:0}
.weitere{list-style:none;padding:0;margin:14px 0 0}
.weitere li{display:flex;gap:10px;align-items:flex-start;padding:10px 0;border-top:1px solid var(--line);font-size:15px}
.tag{flex:none;font-size:11px;font-weight:700;letter-spacing:.05em;padding:3px 8px;border-radius:999px;background:var(--chip);
min-width:84px;text-align:center;text-transform:uppercase}
.t-verk{color:var(--bad);background:var(--badbg)}.t-stopp{color:var(--ink2)}.t-kauf{color:var(--good);background:var(--goodbg)}
.kpis{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:14px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px}
.kpi .k{font-size:12px;color:var(--ink3)}.kpi .v{font-size:22px;font-weight:700;margin-top:2px;letter-spacing:-.01em}
.kpi .n{font-size:12px;color:var(--ink3);margin-top:2px}
.pos{color:var(--good)}.neg{color:var(--bad)}
.legende{display:flex;gap:16px;font-size:13px;color:var(--ink2);margin-bottom:6px}
.legende i{display:inline-block;width:14px;height:3px;border-radius:2px;margin-right:6px;vertical-align:middle}
#chart{position:relative}#chart svg{display:block;width:100%;height:220px;touch-action:pan-y}
#tip{position:absolute;pointer-events:none;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px 10px;
font-size:13px;box-shadow:0 4px 14px rgba(0,0,0,.12);display:none;white-space:nowrap}
.pos-liste{list-style:none;padding:0;margin:0}
.pos-liste>li{border-top:1px solid var(--line)}.pos-liste>li:first-child{border-top:0}
details>summary{list-style:none;cursor:pointer}details>summary::-webkit-details-marker{display:none}
.zeile{display:grid;grid-template-columns:1fr auto;gap:2px 12px;padding:12px 0}
.zeile .t{font-weight:600}.zeile .r{text-align:right;font-weight:600}.zeile .u{font-size:13px;color:var(--ink3)}
.zeile .ur{font-size:13px;color:var(--ink3);text-align:right}
.mini{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.05em;padding:1px 6px;border-radius:999px;
background:var(--chip);color:var(--ink3);margin-left:6px;vertical-align:2px;text-transform:uppercase}
.mini.live{color:var(--s1)}
.detail{font-size:14px;color:var(--ink2);padding:0 0 12px}
.detail ul{margin:6px 0 0;padding-left:18px}
.fort{height:4px;border-radius:2px;background:var(--chip);margin-top:6px;overflow:hidden}.fort i{display:block;height:100%;background:var(--s1)}
.leer{color:var(--ink3);font-size:15px;margin:0}
.mehr summary{color:var(--s1);font-size:14px;padding-top:10px}
.fuss{color:var(--ink3);font-size:12px;line-height:1.5;margin-top:22px}
a{color:var(--s1);text-decoration:none}
.demo{background:var(--bad);color:#fff;border-radius:12px;padding:10px 14px;font-weight:600;font-size:14px;margin-bottom:14px}
"""

JS = r"""
(function(){
const D=JSON.parse(document.getElementById('kurve').textContent);
if(!D.d.length) return;
const box=document.getElementById('chart'),svg=box.querySelector('svg'),tip=document.getElementById('tip');
const W=600,H=220,pl=8,pr=46,pt=10,pb=22;
const alle=D.p.concat(D.b.filter(v=>v!==null));
let lo=Math.min(...alle),hi=Math.max(...alle);const pad=(hi-lo)*0.08||1;lo-=pad;hi+=pad;
const x=i=>pl+(W-pl-pr)*i/Math.max(D.d.length-1,1), y=v=>pt+(H-pt-pb)*(1-(v-lo)/(hi-lo));
const pfad=a=>{let s='';a.forEach((v,i)=>{if(v===null)return;s+=(s?'L':'M')+x(i).toFixed(1)+' '+y(v).toFixed(1)});return s};
const css=getComputedStyle(document.documentElement);
const c1=css.getPropertyValue('--s1').trim(),c2=css.getPropertyValue('--s2').trim(),ln=css.getPropertyValue('--line').trim(),i3=css.getPropertyValue('--ink3').trim();
let g='';
[lo+ (hi-lo)*0.25, lo+(hi-lo)*0.5, lo+(hi-lo)*0.75].forEach(v=>{g+=`<line x1="${pl}" x2="${W-pr}" y1="${y(v)}" y2="${y(v)}" stroke="${ln}" stroke-width="1"/>`+
 `<text x="${W-pr+6}" y="${y(v)+4}" font-size="11" fill="${i3}">${Math.round(v)}</text>`});
if(D.live>0){const lx=x(D.live);g+=`<line x1="${lx}" x2="${lx}" y1="${pt}" y2="${H-pb}" stroke="${i3}" stroke-dasharray="3 4"/>`+
 `<text x="${lx+5}" y="${pt+10}" font-size="11" fill="${i3}">Live</text>`;}
g+=`<text x="${pl}" y="${H-4}" font-size="11" fill="${i3}">${D.d[0].slice(8,10)}.${D.d[0].slice(5,7)}.${D.d[0].slice(2,4)}</text>`+
   `<text x="${W-pr}" y="${H-4}" font-size="11" fill="${i3}" text-anchor="end">${D.d[D.d.length-1].slice(8,10)}.${D.d[D.d.length-1].slice(5,7)}.</text>`;
g+=`<path d="${pfad(D.b)}" fill="none" stroke="${c2}" stroke-width="2" stroke-linejoin="round"/>`;
g+=`<path d="${pfad(D.p)}" fill="none" stroke="${c1}" stroke-width="2" stroke-linejoin="round"/>`;
g+=`<line id="kx" y1="${pt}" y2="${H-pb}" stroke="${i3}" stroke-width="1" visibility="hidden"/>`+
   `<circle id="kp" r="4" fill="${c1}" stroke="var(--card)" stroke-width="2" visibility="hidden"/>`+
   `<circle id="kb" r="4" fill="${c2}" stroke="var(--card)" stroke-width="2" visibility="hidden"/>`;
svg.setAttribute('viewBox',`0 0 ${W} ${H}`);svg.setAttribute('preserveAspectRatio','none');svg.innerHTML=g;
const kx=svg.querySelector('#kx'),kp=svg.querySelector('#kp'),kb=svg.querySelector('#kb');
const f=v=>(v-100>=0?'+':'')+(v-100).toFixed(1).replace('.',',')+' %';
function zeig(ev){const r=svg.getBoundingClientRect();const fx=(ev.clientX-r.left)/r.width*W;
 let i=Math.round((fx-pl)/(W-pl-pr)*(D.d.length-1));i=Math.max(0,Math.min(D.d.length-1,i));
 const xx=x(i);kx.setAttribute('x1',xx);kx.setAttribute('x2',xx);kx.setAttribute('visibility','visible');
 kp.setAttribute('cx',xx);kp.setAttribute('cy',y(D.p[i]));kp.setAttribute('visibility','visible');
 if(D.b[i]!==null){kb.setAttribute('cx',xx);kb.setAttribute('cy',y(D.b[i]));kb.setAttribute('visibility','visible')}
 const dd=D.d[i];tip.innerHTML=`<b>${dd.slice(8,10)}.${dd.slice(5,7)}.${dd.slice(0,4)}</b><br>`+
 `<span style="color:${c1}">●</span> Radar ${f(D.p[i])}<br>`+(D.b[i]!==null?`<span style="color:${c2}">●</span> S&amp;P 500 ${f(D.b[i])}`:'');
 tip.style.display='block';const px=xx/W*r.width;tip.style.left=Math.min(Math.max(px-70,0),r.width-150)+'px';tip.style.top='-6px';}
function weg(){tip.style.display='none';[kx,kp,kb].forEach(e=>e.setAttribute('visibility','hidden'))}
svg.addEventListener('pointermove',zeig);svg.addEventListener('pointerdown',zeig);svg.addEventListener('pointerleave',weg);
})();
"""


def _trade_zeile(tr, heute_iso):
    t = tr["ticker"]
    live = '<span class="mini live">Live</span>' if tr["modus"] == "Live" else '<span class="mini">Rückblick</span>'
    st = tr["status"]
    if st == "geschlossen":
        r = tr["ergebnis"]
        rechts = f'<span class="{_klasse(r)}">{_pct(r)}</span>'
        unten_r = tr["ausstieg_grund"]
        verlauf = (f"Kauf {_d(tr['einstieg_datum'])} zu {_zahl(tr['einstieg_kurs'])} {_wsym(t)} → "
                   f"Verkauf {_d(tr['ausstieg_datum'])} zu {_zahl(tr['ausstieg_kurs'])} {_wsym(t)}")
    elif st == "offen":
        r = tr["kurs"] / tr["einstieg_kurs"] - 1 if tr.get("kurs") else 0.0
        rechts = f'<span class="{_klasse(r)}">{_pct(r)}</span>'
        unten_r = "läuft"
        verlauf = f"Kauf {_d(tr['einstieg_datum'])} zu {_zahl(tr['einstieg_kurs'])} {_wsym(t)} · Stopp {_zahl(tr['stopp'])}"
    elif st == "verpasst":
        rechts, unten_r, verlauf = "–", "ausgelassen", tr.get("ausstieg_grund", "")
    else:
        rechts, unten_r, verlauf = "neu", "Kauf morgen", "Kauf zur nächsten Eröffnung"
    gr = "".join(f"<li>{_e(g)}</li>" for g in tr.get("gruende", []))
    return (f'<li><details><summary><div class="zeile"><div class="t">{_e(t)}{live}</div><div class="r">{rechts}</div>'
            f'<div class="u">{_d(tr["signal_datum"])} · {_pct(tr["gewicht"], 0, False)} · Score {tr["score"]:.0f}</div>'
            f'<div class="ur">{_e(unten_r)}</div></div></summary>'
            f'<div class="detail">{_e(tr.get("firma", t))}<br>{_e(verlauf)}<ul>{gr}</ul></div></details></li>')


def erstelle(dep, aktionen, kand, cfg, regime, oddlot, hinweise, demo=False):
    schwelle = cfg.SCHWELLE if regime else cfg.SCHWELLE_RISK_OFF
    kurve = dep["kurve"]
    heute_iso = dep["letzter_tag"]
    # Kennzahlen
    eq0, eq1 = kurve[0][1], kurve[-1][1]
    b = [k[2] for k in kurve]
    b0 = next((v for v in b if v), None)
    perf = eq1 / eq0 - 1
    bperf = (b[-1] / b0 - 1) if b0 and b[-1] else None
    gz = [t for t in dep["trades"] if t["status"] == "geschlossen"]
    quote = np.mean([t["ergebnis"] > 0 for t in gz]) if gz else None
    offen = [t for t in dep["trades"] if t["status"] == "offen"]
    invest = sum(t["stueck"] * t.get("kurs", t["einstieg_kurs"]) for t in offen) / eq1 if eq1 else 0
    eqs = np.array([k[1] for k in kurve])
    maxdd = float((eqs / np.maximum.accumulate(eqs) - 1).min()) if len(eqs) else 0
    live_idx = next((i for i, k in enumerate(kurve) if k[3] == "Live"), -1)
    tage_live = sum(1 for k in kurve if k[3] == "Live")

    o = [f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#111110" media="(prefers-color-scheme: dark)">
<title>Radar</title><style>{CSS}</style></head><body><main>
<header><div><h1>Radar</h1><div class="stand">Stand {_d(heute_iso, '%d.%m.%Y')} · nach US-Börsenschluss</div></div>
<span class="pill {'on' if regime else 'off'}">{'Markt: Aufwärts' if regime else 'Markt: Vorsicht'}</span></header>"""]
    if demo:
        o.append('<div class="demo">Demo mit erfundenen Daten – nicht danach handeln.</div>')

    # --- Heute -------------------------------------------------------------
    kauf = [a for a in aktionen if a["typ"] == "kaufen"]
    rest = [a for a in aktionen if a["typ"] != "kaufen"]
    if kauf:
        a = kauf[0]
        tr = a["trade"]
        sym = _wsym(tr["ticker"])
        gr = "".join(f"<li>{_e(g)}</li>" for g in tr["gruende"])
        stk = f" · ca. {a['stueck']} Stück" if a["stueck"] > 0 else " · Bruchstücke nutzen"
        euro = f'<div class="klein">≈ {_zahl(a["eur"], 0)} €{stk}</div>' if cfg.ZEIGE_EURO else ""
        o.append(f"""<section class="card hero"><span class="aktion">KAUFEN</span>
<div class="tick">{_e(tr['ticker'])}</div><div class="firma">{_e(tr['firma'])}</div>
<div class="gross">{_pct(tr['gewicht'], 0, False)} des Portfolios</div>{euro}
<ul class="schritte"><li><span>Kaufen</span><span>morgen zur Eröffnung, Limit {_zahl(tr['limit'])} {sym}</span></li>
<li><span>Stopp-Order danach</span><span>ca. {_zahl(tr['stopp_hinweis'])} {sym}</span></li>
<li><span>Plan</span><span>bis zu {cfg.HALTEDAUER} Handelstage, Stopp wird nachgezogen</span></li></ul>
<div class="score">Überzeugung<div class="bahn"><i style="width:{tr['score']:.0f}%"></i></div><b>{tr['score']:.0f}</b></div>
<ul class="gruende">{gr}</ul></section>""")
    else:
        naechst = ""
        if kand:
            t, sc = kand[0]
            naechst = f'<div class="klein" style="margin-top:8px">Stärkster Kandidat: <b>{_e(t)}</b> mit Score {sc:.0f} (Schwelle heute {schwelle})</div>'
        o.append(f"""<section class="card hero ruhe"><div class="lbl">Heute</div><p class="gross">Nichts Neues kaufen</p>
<div class="klein">Kein Signal ist stark genug. Abwarten ist hier die Strategie.</div>{naechst}</section>""")
    if rest:
        zeilen = []
        for a in rest:
            tr = a["trade"]
            sym = _wsym(tr["ticker"])
            if a["typ"] == "verkaufen":
                zeilen.append(f'<li><span class="tag t-verk">Verkaufen</span><span><b>{_e(tr["ticker"])}</b> morgen zur Eröffnung – '
                              f'{_e(tr["verkaufen_geplant"])}</span></li>')
            elif a["typ"] == "gestoppt":
                zeilen.append(f'<li><span class="tag t-verk">Ausgestoppt</span><span><b>{_e(tr["ticker"])}</b> bei ca. '
                              f'{_zahl(tr["ausstieg_kurs"])} {sym} ({_pct(tr["ergebnis"])}). Falls deine Stopp-Order nicht '
                              f'ausgeführt wurde: morgen verkaufen.</span></li>')
            elif a["typ"] == "stopp":
                zeilen.append(f'<li><span class="tag t-stopp">Stopp hoch</span><span><b>{_e(tr["ticker"])}</b> Stopp auf '
                              f'{_zahl(tr["stopp"])} {sym} anheben</span></li>')
        o.append(f'<section class="card"><div class="lbl">Außerdem zu tun</div><ul class="weitere" style="margin:0">{"".join(zeilen)}</ul></section>')

    # --- Kennzahlen ----------------------------------------------------------
    o.append(f"""<div class="kpis">
<div class="kpi"><div class="k">Radar-Portfolio</div><div class="v {_klasse(perf)}">{_pct(perf)}</div><div class="n">seit {_d(kurve[0][0], '%d.%m.%y')}</div></div>
<div class="kpi"><div class="k">S&amp;P 500</div><div class="v {_klasse(bperf)}">{_pct(bperf)}</div><div class="n">gleicher Zeitraum</div></div>
<div class="kpi"><div class="k">Trefferquote</div><div class="v">{_pct(quote, 0, False) if quote is not None else '–'}</div><div class="n">{len(gz)} abgeschlossene Trades</div></div>
<div class="kpi"><div class="k">Investiert</div><div class="v">{_pct(invest, 0, False)}</div><div class="n">max. Rückgang {_pct(maxdd, 1)}</div></div></div>""")

    # --- Kurve -------------------------------------------------------------
    daten = {"d": [k[0] for k in kurve], "p": [round(k[1] / eq0 * 100, 3) for k in kurve],
             "b": [round(k[2] / b0 * 100, 3) if k[2] and b0 else None for k in kurve], "live": live_idx}
    o.append(f"""<section class="card"><div class="lbl">Wertentwicklung</div>
<div class="legende"><span><i style="background:var(--s1)"></i>Radar</span><span><i style="background:var(--s2)"></i>S&amp;P 500</span></div>
<div id="chart"><svg role="img" aria-label="Wertentwicklung Radar gegen S&amp;P 500"></svg><div id="tip"></div></div>
<div class="stand" style="margin-top:6px">Links der gestrichelten Linie: Rückblick (simuliert mit denselben Regeln). Rechts: live, {tage_live} Handelstag(e).</div>
<script type="application/json" id="kurve">{json.dumps(daten)}</script></section>""")

    # --- Offene Positionen -------------------------------------------------
    o.append('<section class="card"><div class="lbl">Im Portfolio</div>')
    if offen:
        o.append('<ul class="pos-liste">')
        for tr in sorted(offen, key=lambda t: t["einstieg_datum"], reverse=True):
            r = tr.get("kurs", tr["einstieg_kurs"]) / tr["einstieg_kurs"] - 1
            anteil = tr["stueck"] * tr.get("kurs", tr["einstieg_kurs"]) / eq1
            sym = _wsym(tr["ticker"])
            gr = "".join(f"<li>{_e(g)}</li>" for g in tr["gruende"])
            vk = f" · <b>Verkauf morgen</b>" if tr.get("verkaufen_geplant") else ""
            o.append(f"""<li><details><summary><div class="zeile"><div class="t">{_e(tr['ticker'])}</div>
<div class="r {_klasse(r)}">{_pct(r)}</div><div class="u">{_pct(anteil, 0, False)} · seit {_d(tr['einstieg_datum'])}{vk}</div>
<div class="ur">Stopp {_zahl(tr['stopp'])} {sym}</div></div>
<div class="fort"><i style="width:{min(tr['tage'] / cfg.HALTEDAUER, 1) * 100:.0f}%"></i></div></summary>
<div class="detail">{_e(tr['firma'])} · Tag {tr['tage']} von {cfg.HALTEDAUER}<br>Kauf {_zahl(tr['einstieg_kurs'])} {sym} → jetzt {_zahl(tr.get('kurs'))} {sym}
<ul>{gr}</ul></div></details></li>""")
        o.append(f'</ul><div class="stand" style="margin-top:4px">Rest: {_pct(max(0, 1 - invest), 0, False)} Cash / Geldmarkt</div>')
    else:
        o.append('<p class="leer">Gerade 100 % Cash.</p>')
    o.append("</section>")

    # --- Verlauf -----------------------------------------------------------
    alle = sorted(dep["trades"], key=lambda t: (t["signal_datum"], t["id"]), reverse=True)
    o.append('<section class="card"><div class="lbl">Verlauf aller Empfehlungen</div>')
    if alle:
        o.append('<ul class="pos-liste">' + "".join(_trade_zeile(t, heute_iso) for t in alle[:12]) + "</ul>")
        if len(alle) > 12:
            o.append(f'<details class="mehr"><summary>Alle {len(alle)} anzeigen</summary><ul class="pos-liste">'
                     + "".join(_trade_zeile(t, heute_iso) for t in alle[12:]) + "</ul></details>")
    else:
        o.append('<p class="leer">Noch keine Empfehlungen.</p>')
    o.append("</section>")

    # --- Beobachten & Sonderchancen ------------------------------------------
    if kand:
        zeilen = "".join(f'<li><div class="zeile"><div class="t">{_e(t)}</div><div class="r">{sc:.0f}</div></div></li>' for t, sc in kand)
        o.append(f'<section class="card"><details><summary class="lbl" style="margin:0">Beobachten · knapp unter der Schwelle ›</summary>'
                 f'<ul class="pos-liste" style="margin-top:8px">{zeilen}</ul></details></section>')
    if oddlot:
        zeilen = "".join(f'<li><div class="zeile"><div class="t">{_e(z["firma"])}</div><div class="r">'
                         f'<a href="{_e(z["link"])}" target="_blank" rel="noopener">Dokument</a></div>'
                         f'<div class="u">{_e(", ".join(z["ticker"]) or "–")} · Meldung {_e(z["datum"])}</div></div></li>' for z in oddlot[:6])
        o.append('<section class="card"><details><summary class="lbl" style="margin:0">Sonderchancen · Odd-Lot-Angebote ›</summary>'
                 '<div class="detail" style="padding-top:8px">US-Rückkäufe mit Vorrang für Aktionäre unter 100 Aktien. Separat vom '
                 'Portfolio: max. 99 Stück kaufen und andienen, wenn der Angebotspreis klar über dem Kurs liegt und dein Broker '
                 f'US-Tender abwickelt.</div><ul class="pos-liste">{zeilen}</ul></details></section>')
    if hinweise:
        o.append('<section class="card"><details><summary class="lbl" style="margin:0">Hinweise ›</summary><div class="detail" style="padding-top:8px">'
                 + "<br>".join(_e(h) for h in hinweise) + "</div></details></section>")

    o.append(f"""<div class="fuss">Regeln: Kauf nur bei Score ≥ {cfg.SCHWELLE} (bei schwachem Markt ≥ {cfg.SCHWELLE_RISK_OFF}), höchstens eine
neue Empfehlung pro Tag und {cfg.MAX_POSITIONEN} Positionen. Größe {cfg.GEWICHT_MIN:.0%}–{cfg.GEWICHT_MAX:.0%} je nach Score, max.
{cfg.MAX_VERLUST_PRO_TRADE:.0%} Portfolio-Verlust pro Trade bis zum Stopp. Verkauf bei Stopp oder nach {cfg.HALTEDAUER} Handelstagen.
Musterdepot inkl. {_pct(cfg.KOSTEN, 1, False)} Kosten je Order, ohne Steuern und Dividenden. Daten: Yahoo Finance, SEC EDGAR. Kein Anlagerat.</div>
</main><script>{JS}</script></body></html>""")
    return "\n".join(o)
