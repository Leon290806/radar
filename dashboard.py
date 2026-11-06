# -*- coding: utf-8 -*-
"""Dashboard mit Reitern: Heute · Portfolio · Verlauf · Insider · Scanner · Statistik · Lernen.
Eine einzelne HTML-Datei, optimiert fürs Handy, hell & dunkel."""
import datetime as dt
import html as _h
import json
from collections import defaultdict

import numpy as np


# ---------------------------------------------------------------------------
# Formatierung
# ---------------------------------------------------------------------------
def _e(s):
    return _h.escape(str(s))


def _ok(x):
    return x is not None and not (isinstance(x, float) and not np.isfinite(x))


def _zahl(x, nk=2):
    if not _ok(x):
        return "–"
    return f"{x:,.{nk}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(x, nk=1, vz=True):
    if not _ok(x):
        return "–"
    return (f"{x * 100:+.{nk}f} %" if vz else f"{x * 100:.{nk}f} %").replace(".", ",")


def _kl(x):
    if not _ok(x) or abs(x) < 1e-9:
        return ""
    return "pos" if x > 0 else "neg"


def _d(iso, fmt="%d.%m."):
    return dt.date.fromisoformat(iso).strftime(fmt) if iso else "–"


def _sym(t):
    return "€" if t.upper().endswith(".DE") else "$"


def _geld(x):
    if x >= 1e6:
        return f"{_zahl(x / 1e6, 2)} Mio. $"
    return f"{_zahl(x / 1e3, 0)} Tsd. $"


# ---------------------------------------------------------------------------
# Mini-Chart (statisches SVG)
# ---------------------------------------------------------------------------
def _spark(v, stopp=None, ergebnis=None):
    if not v or len(v["c"]) < 2:
        return ""
    c = v["c"]
    lo, hi = min(c + ([stopp] if stopp else [])), max(c)
    if hi - lo < 1e-9:
        hi = lo + 1
    W, H, p = 320, 72, 6
    x = lambda i: p + (W - 2 * p) * i / (len(c) - 1)
    y = lambda val: p + (H - 2 * p) * (1 - (val - lo) / (hi - lo))
    pfad = " ".join(f"{'M' if i == 0 else 'L'}{x(i):.1f} {y(val):.1f}" for i, val in enumerate(c))
    o = [f'<svg class="spark" viewBox="0 0 {W} {H}" preserveAspectRatio="none" aria-hidden="true">']
    if v.get("ein") is not None:
        a = v["ein"]
        b = v["aus"] if v.get("aus") is not None else len(c) - 1
        o.append(f'<rect x="{x(a):.1f}" y="0" width="{max(x(b) - x(a), 1):.1f}" height="{H}" class="halte"/>')
    if stopp:
        o.append(f'<line x1="{p}" x2="{W - p}" y1="{y(stopp):.1f}" y2="{y(stopp):.1f}" class="stopplinie"/>')
    o.append(f'<path d="{pfad}" class="kurs"/>')
    if v.get("sig") is not None:
        o.append(f'<circle cx="{x(v["sig"]):.1f}" cy="{y(c[v["sig"]]):.1f}" r="3" class="sig"/>')
    if v.get("ein") is not None:
        o.append(f'<circle cx="{x(v["ein"]):.1f}" cy="{y(c[v["ein"]]):.1f}" r="4" class="ein"/>')
    if v.get("aus") is not None:
        kl = "aus-pos" if (ergebnis or 0) > 0 else "aus-neg"
        o.append(f'<circle cx="{x(v["aus"]):.1f}" cy="{y(c[v["aus"]]):.1f}" r="4" class="{kl}"/>')
    o.append("</svg>")
    return "".join(o)


CSS = """
:root{--bg:#f4f4f1;--card:#fcfcfb;--ink:#0b0b0b;--ink2:#5a5955;--ink3:#8a8984;--line:#e6e5e0;--chip:#efeee9;
--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--good:#0a7f0a;--bad:#c93333;--goodbg:#e7f4e7;--badbg:#fbeaea;--halte:rgba(42,120,214,.08)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#111110;--card:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;
--ink3:#8f8e86;--line:#2c2c2a;--chip:#262624;--s1:#3987e5;--s2:#d95926;--s3:#199e70;--good:#4cc44c;--bad:#ec6b6b;
--goodbg:#173017;--badbg:#3a1b1b;--halte:rgba(57,135,229,.12)}}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,system-ui,sans-serif;
font-variant-numeric:tabular-nums}
.kopf{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line)}
.kopf .in{max-width:680px;margin:0 auto;padding:14px 16px 0}
.titel{display:flex;justify-content:space-between;align-items:baseline;gap:12px}
h1{font-size:21px;margin:0;letter-spacing:-.02em}
.stand{color:var(--ink3);font-size:13px}
.pill{font-size:12px;font-weight:600;padding:3px 9px;border-radius:999px;white-space:nowrap}
.pill.on{background:var(--goodbg);color:var(--good)}.pill.off{background:var(--badbg);color:var(--bad)}
nav{display:flex;gap:4px;overflow-x:auto;scrollbar-width:none;margin:10px -16px 0;padding:0 16px}
nav::-webkit-scrollbar{display:none}
nav button{flex:none;font:inherit;font-size:14px;font-weight:600;color:var(--ink3);background:none;border:0;padding:9px 10px 11px;
border-bottom:2px solid transparent;cursor:pointer}
nav button.aktiv{color:var(--ink);border-bottom-color:var(--s1)}
main{max-width:680px;margin:0 auto;padding:16px 16px 56px}
section.tab{display:none}section.tab.aktiv{display:block}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px;margin-bottom:14px}
.lbl{font-size:12px;font-weight:600;color:var(--ink3);text-transform:uppercase;letter-spacing:.06em;margin:0 0 10px}
.klein{color:var(--ink2);font-size:14px}.mini-t{color:var(--ink3);font-size:13px}
.aktion{display:inline-block;font-size:12px;font-weight:700;letter-spacing:.06em;padding:4px 10px;border-radius:999px;background:var(--goodbg);color:var(--good)}
.tick{font-size:30px;font-weight:700;letter-spacing:-.02em;margin:10px 0 0}
.gross{font-size:20px;font-weight:600;margin:14px 0 2px}.ruhe{font-size:22px;font-weight:700;margin:0}
.schritte{list-style:none;padding:0;margin:16px 0 0;border-top:1px solid var(--line)}
.schritte li{display:flex;justify-content:space-between;gap:12px;padding:10px 0;border-bottom:1px solid var(--line);font-size:15px}
.schritte li span:first-child{color:var(--ink2)}.schritte li span:last-child{font-weight:600;text-align:right}
.balken{display:flex;align-items:center;gap:10px;margin-top:14px;font-size:14px;color:var(--ink2)}
.bahn{flex:1;height:6px;border-radius:3px;background:var(--chip);position:relative;overflow:hidden}
.bahn i{position:absolute;left:0;top:0;bottom:0;border-radius:3px;background:var(--s1)}
.gruende{list-style:none;padding:0;margin:14px 0 0}
.gruende li{padding:5px 0 5px 24px;position:relative;font-size:15px}
.gruende li:before{content:"";position:absolute;left:2px;top:10px;width:11px;height:6px;border-left:2px solid var(--good);
border-bottom:2px solid var(--good);transform:rotate(-45deg)}
.weitere{list-style:none;padding:0;margin:0}
.weitere li{display:flex;gap:10px;align-items:flex-start;padding:10px 0;border-top:1px solid var(--line);font-size:15px}
.weitere li:first-child{border-top:0}
.tag{flex:none;font-size:11px;font-weight:700;letter-spacing:.05em;padding:3px 8px;border-radius:999px;background:var(--chip);
min-width:88px;text-align:center;text-transform:uppercase;color:var(--ink2)}
.t-rot{color:var(--bad);background:var(--badbg)}
.kpis{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:14px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px}
.kpi .k{font-size:12px;color:var(--ink3)}.kpi .v{font-size:22px;font-weight:700;margin-top:2px;letter-spacing:-.01em}
.kpi .n{font-size:12px;color:var(--ink3);margin-top:2px}
.pos{color:var(--good)}.neg{color:var(--bad)}
.legende{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:13px;color:var(--ink2);margin-bottom:6px}
.legende i{display:inline-block;width:14px;height:3px;border-radius:2px;margin-right:6px;vertical-align:middle}
.legende i.blk{height:10px;width:10px;border-radius:3px}
.chart{position:relative}.chart svg{display:block;width:100%;height:220px;touch-action:pan-y}
.tip{position:absolute;pointer-events:none;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px 10px;
font-size:13px;box-shadow:0 4px 14px rgba(0,0,0,.12);display:none;white-space:nowrap;z-index:2}
ul.liste{list-style:none;padding:0;margin:0}ul.liste>li{border-top:1px solid var(--line)}ul.liste>li:first-child{border-top:0}
details>summary{list-style:none;cursor:pointer}details>summary::-webkit-details-marker{display:none}
.zeile{display:grid;grid-template-columns:1fr auto;gap:2px 12px;padding:12px 0}
.zeile .t{font-weight:600}.zeile .r{text-align:right;font-weight:600}.zeile .u{font-size:13px;color:var(--ink3)}
.zeile .ur{font-size:13px;color:var(--ink3);text-align:right}
.chip{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.05em;padding:1px 6px;border-radius:999px;
background:var(--chip);color:var(--ink3);margin-left:6px;vertical-align:2px;text-transform:uppercase}
.chip.live{color:var(--s1)}
.detail{font-size:14px;color:var(--ink2);padding:0 0 14px}
.detail ul{margin:6px 0 0;padding-left:18px}
.fakten{display:grid;grid-template-columns:1fr 1fr;gap:6px 16px;margin:10px 0}
.fakten div span{display:block;font-size:12px;color:var(--ink3)}.fakten div b{font-weight:600;color:var(--ink)}
.spark{display:block;width:100%;height:72px;margin:6px 0 4px}
.spark .kurs{fill:none;stroke:var(--ink2);stroke-width:1.6;vector-effect:non-scaling-stroke}
.spark .halte{fill:var(--halte)}.spark .stopplinie{stroke:var(--bad);stroke-width:1;stroke-dasharray:4 4;vector-effect:non-scaling-stroke}
.spark .ein{fill:var(--s1);stroke:var(--card);stroke-width:2}.spark .sig{fill:var(--ink3)}
.spark .aus-pos{fill:var(--good);stroke:var(--card);stroke-width:2}.spark .aus-neg{fill:var(--bad);stroke:var(--card);stroke-width:2}
.fort{height:4px;border-radius:2px;background:var(--chip);margin-top:6px;overflow:hidden}.fort i{display:block;height:100%;background:var(--s1)}
.filter{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px}
.filter button{font:inherit;font-size:13px;font-weight:600;padding:6px 12px;border-radius:999px;border:1px solid var(--line);
background:var(--card);color:var(--ink2);cursor:pointer}
.filter button.aktiv{background:var(--ink);color:var(--card);border-color:var(--ink)}
.stapel{display:flex;height:10px;border-radius:5px;overflow:hidden;background:var(--chip);gap:2px}
.stapel i{display:block;height:100%}
.stapel-wrap{position:relative;margin-top:8px}.schwelle{position:absolute;top:-4px;bottom:-4px;width:2px;background:var(--ink)}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{padding:8px 6px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
th{font-size:12px;font-weight:600;color:var(--ink3)}th:first-child,td:first-child{text-align:left}
.tw{overflow-x:auto;margin:0 -4px}
.monate{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}
.monat{border-radius:10px;padding:8px;background:var(--chip);font-size:12px}
.monat b{display:block;font-size:14px;margin-top:2px}
.leer{color:var(--ink3);font-size:15px;margin:0}
.fehler{background:var(--badbg);color:var(--bad);border-radius:10px;padding:10px 12px;font-size:14px}
.okbox{background:var(--goodbg);color:var(--good);border-radius:10px;padding:10px 12px;font-size:14px}
.fuss{color:var(--ink3);font-size:12px;line-height:1.5;margin-top:18px}
a{color:var(--s1);text-decoration:none}
.demo{background:var(--bad);color:#fff;border-radius:12px;padding:10px 14px;font-weight:600;font-size:14px;margin-bottom:14px}
.mehr summary{color:var(--s1);font-size:14px;padding-top:10px}
p.erkl{font-size:14px;color:var(--ink2);margin:0 0 12px}
"""

JS = r"""
(function(){
const tabs=[...document.querySelectorAll('nav button')];
function zeige(id){tabs.forEach(b=>b.classList.toggle('aktiv',b.dataset.t===id));
 document.querySelectorAll('section.tab').forEach(s=>s.classList.toggle('aktiv',s.id===id));
 try{history.replaceState(null,'','#'+id)}catch(e){}; window.scrollTo(0,0); zeichneAlle();}
tabs.forEach(b=>b.addEventListener('click',()=>zeige(b.dataset.t)));
const start=(location.hash||'#heute').slice(1);
// Filter im Verlauf
document.querySelectorAll('.filter button').forEach(b=>b.addEventListener('click',()=>{
 document.querySelectorAll('.filter button').forEach(x=>x.classList.toggle('aktiv',x===b));
 const f=b.dataset.f; document.querySelectorAll('#verlauf-liste>li').forEach(li=>{
  const k=li.dataset; let an=true;
  if(f==='live')an=k.modus==='Live'; else if(f==='rueck')an=k.modus!=='Live';
  else if(f==='gew')an=k.erg>0; else if(f==='verl')an=k.erg<0; else if(f==='offen')an=k.status==='offen'||k.status==='geplant';
  li.style.display=an?'':'none';});}));
// Linien-Charts
const css=getComputedStyle(document.documentElement);
const farbe=v=>css.getPropertyValue(v).trim();
function zeichne(box){
 if(!box.offsetParent)return; const D=JSON.parse(box.querySelector('script').textContent); if(!D.d.length)return;
 const svg=box.querySelector('svg'),tip=box.querySelector('.tip'); const W=600,H=220,pl=8,pr=46,pt=10,pb=22;
 const alle=[].concat(...D.s.map(s=>s.v.filter(v=>v!==null)));let lo=Math.min(...alle),hi=Math.max(...alle);
 const pad=(hi-lo)*0.08||1;lo-=pad;hi+=pad;
 const x=i=>pl+(W-pl-pr)*i/Math.max(D.d.length-1,1),y=v=>pt+(H-pt-pb)*(1-(v-lo)/(hi-lo));
 const pfad=a=>{let s='',neu=true;a.forEach((v,i)=>{if(v===null){neu=true;return}s+=(neu?'M':'L')+x(i).toFixed(1)+' '+y(v).toFixed(1);neu=false});return s};
 const ln=farbe('--line'),i3=farbe('--ink3');let g='';
 [0.25,0.5,0.75].forEach(f=>{const v=lo+(hi-lo)*f;g+=`<line x1="${pl}" x2="${W-pr}" y1="${y(v)}" y2="${y(v)}" stroke="${ln}"/>`+
  `<text x="${W-pr+6}" y="${y(v)+4}" font-size="11" fill="${i3}">${Math.round(v)}</text>`});
 if(D.live>0){const lx=x(D.live);g+=`<line x1="${lx}" x2="${lx}" y1="${pt}" y2="${H-pb}" stroke="${i3}" stroke-dasharray="3 4"/>`+
  `<text x="${lx+5}" y="${pt+10}" font-size="11" fill="${i3}">Live</text>`}
 const dfmt=s=>s.slice(8,10)+'.'+s.slice(5,7)+'.'+s.slice(2,4);
 g+=`<text x="${pl}" y="${H-4}" font-size="11" fill="${i3}">${dfmt(D.d[0])}</text><text x="${W-pr}" y="${H-4}" font-size="11" fill="${i3}" text-anchor="end">${dfmt(D.d[D.d.length-1])}</text>`;
 D.s.slice().reverse().forEach(s=>{g+=`<path d="${pfad(s.v)}" fill="none" stroke="${farbe(s.f)}" stroke-width="2" stroke-linejoin="round"/>`});
 g+=`<line class="kx" y1="${pt}" y2="${H-pb}" stroke="${i3}" visibility="hidden"/>`;
 D.s.forEach((s,k)=>{g+=`<circle class="kp${k}" r="4" fill="${farbe(s.f)}" stroke="${farbe('--card')}" stroke-width="2" visibility="hidden"/>`});
 svg.setAttribute('viewBox',`0 0 ${W} ${H}`);svg.setAttribute('preserveAspectRatio','none');svg.innerHTML=g;
 const kx=svg.querySelector('.kx');const f=v=>(v-100>=0?'+':'')+(v-100).toFixed(1).replace('.',',')+' %';
 function an(ev){const r=svg.getBoundingClientRect();let i=Math.round(((ev.clientX-r.left)/r.width*W-pl)/(W-pl-pr)*(D.d.length-1));
  i=Math.max(0,Math.min(D.d.length-1,i));const xx=x(i);kx.setAttribute('x1',xx);kx.setAttribute('x2',xx);kx.setAttribute('visibility','visible');
  let t=`<b>${dfmt(D.d[i])}</b>`;D.s.forEach((s,k)=>{const c=svg.querySelector('.kp'+k);if(s.v[i]===null){c.setAttribute('visibility','hidden');return}
   c.setAttribute('cx',xx);c.setAttribute('cy',y(s.v[i]));c.setAttribute('visibility','visible');
   t+=`<br><span style="color:${farbe(s.f)}">●</span> ${s.n} ${f(s.v[i])}`});
  tip.innerHTML=t;tip.style.display='block';const px=xx/W*r.width;tip.style.left=Math.min(Math.max(px-80,0),r.width-170)+'px';tip.style.top='-8px'}
 function weg(){tip.style.display='none';svg.querySelectorAll('circle,.kx').forEach(e=>e.setAttribute('visibility','hidden'))}
 svg.onpointermove=an;svg.onpointerdown=an;svg.onpointerleave=weg;}
function zeichneAlle(){document.querySelectorAll('.chart').forEach(zeichne)}
zeige(document.getElementById(start)?start:'heute');
window.addEventListener('resize',zeichneAlle);
})();
"""


def _chart(serien, daten, live_idx, label):
    d = {"d": daten, "s": serien, "live": live_idx}
    leg = "".join(f'<span><i style="background:var({s["f"]})"></i>{_e(s["n"])}</span>' for s in serien)
    return (f'<div class="legende">{leg}</div><div class="chart"><svg role="img" aria-label="{_e(label)}"></svg>'
            f'<div class="tip"></div><script type="application/json">{json.dumps(d)}</script></div>')


def _fakten(paare):
    return '<div class="fakten">' + "".join(f"<div><span>{_e(k)}</span><b>{v}</b></div>" for k, v in paare) + "</div>"


def _trade_li(tr, v, par):
    t, st = tr["ticker"], tr["status"]
    chip = '<span class="chip live">Live</span>' if tr["modus"] == "Live" else '<span class="chip">Rückblick</span>'
    erg = None
    if st == "geschlossen":
        erg = tr["ergebnis"]
        rechts, unten = f'<span class="{_kl(erg)}">{_pct(erg)}</span>', tr["ausstieg_grund"]
    elif st == "offen":
        erg = tr["kurs"] / tr["einstieg_kurs"] - 1
        rechts, unten = f'<span class="{_kl(erg)}">{_pct(erg)}</span>', f"läuft · Tag {tr['tage']}"
    elif st == "verpasst":
        rechts, unten = "–", "ausgelassen"
    else:
        rechts, unten = "neu", "Kauf morgen"
    fakten = [("Signal", _d(tr["signal_datum"], "%d.%m.%Y")), ("Gewicht", _pct(tr["gewicht"], 0, False)),
              ("Score", f"{tr['score']:.0f}"), ("Auslöser", " + ".join(tr.get("typen", [])) or "–")]
    if tr.get("einstieg_datum") and st != "verpasst":
        fakten.append(("Kauf", f"{_d(tr['einstieg_datum'])} · {_zahl(tr['einstieg_kurs'])} {_sym(t)}"))
    if st == "geschlossen":
        fakten.append(("Verkauf", f"{_d(tr['ausstieg_datum'])} · {_zahl(tr['ausstieg_kurs'])} {_sym(t)}"))
        if _ok(tr.get("markt")):
            fakten.append(("S&P 500 gleiche Zeit", _pct(tr["markt"])))
            fakten.append(("Mehrrendite", f'<span class="{_kl(tr["ueber_markt"])}">{_pct(tr["ueber_markt"])}</span>'))
    if st == "offen":
        fakten.append(("Stopp", f"{_zahl(tr['stopp'])} {_sym(t)}"))
    gr = "".join(f"<li>{_e(g)}</li>" for g in tr.get("gruende", []))
    stopp = tr.get("stopp") if st == "offen" else None
    data = f'data-modus="{tr["modus"]}" data-status="{st}" data-erg="{erg if _ok(erg) else 0}"'
    return (f'<li {data}><details><summary><div class="zeile"><div class="t">{_e(t)}{chip}</div><div class="r">{rechts}</div>'
            f'<div class="u">{_d(tr["signal_datum"])} · {_pct(tr["gewicht"], 0, False)} · {_e(" + ".join(tr.get("typen", [])))}</div>'
            f'<div class="ur">{_e(unten)}</div></div></summary><div class="detail">{_e(tr.get("firma", t))}'
            f'{_spark(v, stopp, erg)}{_fakten(fakten)}<ul>{gr}</ul></div></details></li>')


# ---------------------------------------------------------------------------
# Hauptfunktion
# ---------------------------------------------------------------------------
def erstelle(dep, aktionen, kand, par, regime, oddlot, hinweise, feed, ins_status, verlaeufe, firmen, demo=False):
    schwelle = par.SCHWELLE if regime else par.SCHWELLE_RISK_OFF
    kurve = dep["kurve"]
    heute = dep["letzter_tag"]
    eq = np.array([k[1] for k in kurve])
    b = [k[2] for k in kurve]
    b0 = next((x for x in b if x), None)
    perf = eq[-1] / eq[0] - 1
    bperf = (b[-1] / b0 - 1) if b0 and b[-1] else None
    gz = [t for t in dep["trades"] if t["status"] == "geschlossen"]
    offen = [t for t in dep["trades"] if t["status"] == "offen"]
    quote = np.mean([t["ergebnis"] > 0 for t in gz]) if gz else None
    akt_anteil = sum(t["stueck"] * t.get("kurs", t["einstieg_kurs"]) for t in offen) / eq[-1] if eq[-1] else 0
    maxdd = float((eq / np.maximum.accumulate(eq) - 1).min())
    live_idx = next((i for i, k in enumerate(kurve) if k[3] == "Live"), -1)
    tage_live = sum(1 for k in kurve if k[3] == "Live")
    # Kern-Vergleich: nur S&P 500 mit 200-Tage-Filter
    kern = [100.0]
    for i in range(1, len(kurve)):
        r = kurve[i - 1][5] if len(kurve[i - 1]) > 5 else 1
        if r and kurve[i][2] and kurve[i - 1][2]:
            kern.append(kern[-1] * kurve[i][2] / kurve[i - 1][2])
        else:
            kern.append(kern[-1] * (1 + par.GELDMARKT_ZINS) ** (1 / 252))
    daten = [k[0] for k in kurve]
    s_radar = [round(x / eq[0] * 100, 2) for x in eq]
    s_spx = [round(x / b0 * 100, 2) if x and b0 else None for x in b]

    o = [f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="robots" content="noindex">
<title>Radar</title><style>{CSS}</style></head><body>
<div class="kopf"><div class="in"><div class="titel"><div><h1>Radar</h1><div class="stand">Stand {_d(heute, '%d.%m.%Y')} · nach US-Börsenschluss</div></div>
<span class="pill {'on' if regime else 'off'}">{'Markt: Aufwärts' if regime else 'Markt: Vorsicht'}</span></div>
<nav>{''.join(f'<button data-t="{i}">{n}</button>' for i, n in [('heute', 'Heute'), ('portfolio', 'Portfolio'), ('verlauf', 'Verlauf'), ('insider', 'Insider'), ('scanner', 'Scanner'), ('statistik', 'Statistik'), ('lernen', 'Lernen')])}</nav>
</div></div><main>"""]
    if demo:
        o.append('<div class="demo">Demo mit erfundenen Daten – nicht danach handeln.</div>')

    # ===================== HEUTE =====================
    o.append('<section class="tab" id="heute">')
    kauf = [a for a in aktionen if a["typ"] == "kaufen"]
    rest = [a for a in aktionen if a["typ"] != "kaufen"]
    if kauf:
        a = kauf[0]
        tr = a["trade"]
        sy = _sym(tr["ticker"])
        euro = ""
        if par.ZEIGE_EURO:
            stk = f" · ca. {a['stueck']} Stück" if a["stueck"] > 0 else " · Bruchstücke nutzen"
            euro = f'<div class="klein">≈ {_zahl(a["eur"], 0)} €{stk}</div>'
        gr = "".join(f"<li>{_e(g)}</li>" for g in tr["gruende"])
        o.append(f"""<div class="card"><span class="aktion">KAUFEN</span><div class="tick">{_e(tr['ticker'])}</div>
<div class="klein">{_e(tr['firma'])}</div><div class="gross">{_pct(tr['gewicht'], 0, False)} des Portfolios</div>{euro}
<ul class="schritte"><li><span>Kaufen</span><span>morgen zur Eröffnung, Limit {_zahl(tr['limit'])} {sy}</span></li>
<li><span>Stopp-Order danach</span><span>ca. {_zahl(tr['stopp_hinweis'])} {sy}</span></li>
<li><span>Plan</span><span>bis zu {tr.get('parameter', {}).get('HALTEDAUER', par.HALTEDAUER)} Handelstage, Stopp wird nachgezogen</span></li></ul>
<div class="balken">Überzeugung<div class="bahn"><i style="width:{tr['score']:.0f}%"></i></div><b>{tr['score']:.0f}</b></div>
<ul class="gruende">{gr}</ul>{_spark(verlaeufe.get(tr['id']))}</div>""")
    else:
        n = ""
        if kand:
            n = f'<div class="klein" style="margin-top:8px">Stärkster Kandidat: <b>{_e(kand[0][0])}</b> mit Score {kand[0][1]:.0f} (Schwelle heute {schwelle}) – Details im Reiter Scanner.</div>'
        o.append(f'<div class="card"><div class="lbl">Heute</div><p class="ruhe">Nichts Neues kaufen</p>'
                 f'<div class="klein">Kein Signal ist stark genug. Freies Geld bleibt im {"S&amp;P-500-ETF" if regime else "Geldmarkt"}.</div>{n}</div>')
    if rest:
        z = []
        for a in rest:
            tr = a["trade"]
            sy = _sym(tr["ticker"])
            if a["typ"] == "verkaufen":
                z.append(f'<li><span class="tag t-rot">Verkaufen</span><span><b>{_e(tr["ticker"])}</b> morgen zur Eröffnung – {_e(tr["verkaufen_geplant"])}</span></li>')
            elif a["typ"] == "gestoppt":
                z.append(f'<li><span class="tag t-rot">Ausgestoppt</span><span><b>{_e(tr["ticker"])}</b> bei ca. {_zahl(tr["ausstieg_kurs"])} {sy} '
                         f'({_pct(tr["ergebnis"])}). Falls deine Stopp-Order nicht lief: morgen verkaufen.</span></li>')
            else:
                z.append(f'<li><span class="tag">Stopp hoch</span><span><b>{_e(tr["ticker"])}</b> Stopp auf {_zahl(tr["stopp"])} {sy} anheben</span></li>')
        o.append(f'<div class="card"><div class="lbl">Außerdem zu tun</div><ul class="weitere">{"".join(z)}</ul></div>')
    mehr = perf - bperf if _ok(bperf) else None
    o.append(f"""<div class="kpis">
<div class="kpi"><div class="k">Radar-Portfolio</div><div class="v {_kl(perf)}">{_pct(perf)}</div><div class="n">seit {_d(kurve[0][0], '%d.%m.%y')}</div></div>
<div class="kpi"><div class="k">S&amp;P 500</div><div class="v {_kl(bperf)}">{_pct(bperf)}</div><div class="n">gleicher Zeitraum</div></div>
<div class="kpi"><div class="k">Mehrrendite</div><div class="v {_kl(mehr)}">{_pct(mehr)}</div><div class="n">Radar minus S&amp;P 500</div></div>
<div class="kpi"><div class="k">Einzelaktien</div><div class="v">{_pct(akt_anteil, 0, False)}</div><div class="n">Rest im {'ETF' if regime else 'Geldmarkt'}</div></div></div>""")
    o.append('<div class="card"><div class="lbl">Wertentwicklung</div>'
             + _chart([{"n": "Radar", "f": "--s1", "v": s_radar}, {"n": "S&P 500", "f": "--s2", "v": s_spx}], daten, live_idx, "Radar gegen S&P 500")
             + f'<div class="mini-t" style="margin-top:6px">Links der gestrichelten Linie: Rückblick mit denselben Regeln. Rechts: live ({tage_live} Handelstag{"e" if tage_live != 1 else ""}).</div></div>')
    o.append("</section>")

    # ===================== PORTFOLIO =====================
    o.append('<section class="tab" id="portfolio"><div class="card"><div class="lbl">Aufteilung</div>')
    farben = ["--s1", "--s2", "--s3", "--ink2", "--ink3"]
    teile = [(t["ticker"], t["stueck"] * t.get("kurs", t["einstieg_kurs"]) / eq[-1]) for t in offen]
    kern_anteil = max(0.0, 1 - sum(w for _, w in teile))
    o.append('<div class="stapel">' + "".join(f'<i style="width:{w * 100:.1f}%;background:var({farben[i % 5]})"></i>' for i, (_, w) in enumerate(teile))
             + f'<i style="width:{kern_anteil * 100:.1f}%;background:var(--chip)"></i></div><div class="legende" style="margin-top:10px">'
             + "".join(f'<span><i class="blk" style="background:var({farben[i % 5]})"></i>{_e(t)} {_pct(w, 0, False)}</span>' for i, (t, w) in enumerate(teile))
             + f'<span><i class="blk" style="background:var(--chip);outline:1px solid var(--line)"></i>{"S&amp;P-500-ETF" if regime else "Geldmarkt"} {_pct(kern_anteil, 0, False)}</span></div></div>')
    if offen:
        for tr in sorted(offen, key=lambda x: x["einstieg_datum"], reverse=True):
            r = tr["kurs"] / tr["einstieg_kurs"] - 1
            sy = _sym(tr["ticker"])
            hd = tr.get("parameter", {}).get("HALTEDAUER", par.HALTEDAUER)
            rest_tage = hd - tr["tage"]
            fakten = [("Kauf", f"{_d(tr['einstieg_datum'])} · {_zahl(tr['einstieg_kurs'])} {sy}"), ("Aktuell", f"{_zahl(tr['kurs'])} {sy}"),
                      ("Stopp", f"{_zahl(tr['stopp'])} {sy}"), ("Abstand zum Stopp", _pct(tr["stopp"] / tr["kurs"] - 1)),
                      ("Haltedauer", f"Tag {tr['tage']} von {hd}"), ("Auslöser", " + ".join(tr.get("typen", [])) or "–")]
            vk = '<div class="okbox" style="margin-top:8px">Verkauf morgen zur Eröffnung (Zeitstopp).</div>' if tr.get("verkaufen_geplant") else ""
            o.append(f"""<div class="card"><div class="zeile" style="padding-top:0"><div class="t" style="font-size:20px">{_e(tr['ticker'])}</div>
<div class="r {_kl(r)}" style="font-size:20px">{_pct(r)}</div><div class="u">{_e(tr['firma'])}</div><div class="ur">noch {max(rest_tage, 0)} Tage</div></div>
{_spark(verlaeufe.get(tr['id']), tr['stopp'], r)}<div class="fort"><i style="width:{min(tr['tage'] / hd, 1) * 100:.0f}%"></i></div>
{_fakten(fakten)}<ul class="gruende">{''.join(f'<li>{_e(g)}</li>' for g in tr['gruende'])}</ul>{vk}</div>""")
    else:
        o.append('<div class="card"><p class="leer">Keine Einzelaktien im Portfolio – alles im ' + ("S&amp;P-500-ETF." if regime else "Geldmarkt.") + "</p></div>")
    o.append('<p class="mini-t">Mini-Chart: blauer Punkt = Kauf, blaue Fläche = Haltezeit, rote Linie = Stopp.</p></section>')

    # ===================== VERLAUF =====================
    alle = sorted(dep["trades"], key=lambda t: (t["signal_datum"], t["id"]), reverse=True)
    o.append('<section class="tab" id="verlauf"><div class="card"><div class="lbl">Alle Empfehlungen</div>'
             '<div class="filter">' + "".join(f'<button data-f="{f}"{" class=aktiv" if f == "alle" else ""}>{n}</button>' for f, n in
                                              [("alle", "Alle"), ("live", "Live"), ("rueck", "Rückblick"), ("offen", "Offen"), ("gew", "Gewinner"), ("verl", "Verlierer")])
             + '</div><ul class="liste" id="verlauf-liste">' + "".join(_trade_li(t, verlaeufe.get(t["id"]), par) for t in alle) + "</ul>")
    if not alle:
        o.append('<p class="leer">Noch keine Empfehlungen.</p>')
    o.append('</div><p class="mini-t">Antippen für Details: Kursverlauf, Kauf/Verkauf, Vergleich mit dem S&amp;P 500 und die Gründe.</p></section>')

    # ===================== INSIDER =====================
    o.append('<section class="tab" id="insider"><div class="card"><div class="lbl">Insider-Käufe (SEC Form 4)</div>'
             '<p class="erkl">Vorstände und Aufsichtsräte, die Aktien ihrer eigenen Firma mit eigenem Geld kaufen. '
             'Am stärksten: mehrere Insider in kurzer Zeit („Cluster“). Käufe aus Sparplänen (10b5-1) zählen nicht.</p>')
    if ins_status.get("ok"):
        o.append(f'<div class="okbox">{ins_status["anzahl"]} Insider-Käufe geladen'
                 + (f' ({_d(ins_status.get("von"), "%d.%m.%y")} – {_d(ins_status.get("bis"), "%d.%m.%y")})' if ins_status.get("von") else "") + ".</div>")
    else:
        o.append(f'<div class="fehler">Insider-Daten wurden nicht geladen: {_e(ins_status.get("fehler") or "unbekannter Grund")}</div>')
    o.append("</div>")
    if feed:
        o.append('<div class="card"><div class="lbl">Letzte 45 Tage · S&amp;P 500 &amp; Nasdaq 100</div><ul class="liste">')
        for f in feed[:30]:
            badge = '<span class="chip live">Cluster</span>' if f["cluster"] else ""
            plan = " · Sparplan" if f["plan"] else ""
            fakten = [("Gekauft", _geld(f["wert"])), ("Insider", str(f["n"])), ("Ø Kaufpreis", f"{_zahl(f['preis'])} $"),
                      ("Seitdem", f'<span class="{_kl(f["seit"])}">{_pct(f["seit"])}</span>'),
                      ("Letzte Meldung", _d(f["letzte"], "%d.%m.%y")), ("Score heute", f"{f['score']:.0f}" if _ok(f["score"]) else "–")]
            o.append(f'<li><details><summary><div class="zeile"><div class="t">{_e(f["ticker"])}{badge}</div><div class="r">{_geld(f["wert"])}</div>'
                     f'<div class="u">{f["n"]} Insider · {_e(", ".join(f["rollen"]) or "–")}{plan}</div>'
                     f'<div class="ur {_kl(f["seit"])}">{_pct(f["seit"])}</div></div></summary>'
                     f'<div class="detail">{_e(firmen.get(f["ticker"], f["ticker"]))}<br>{_e(", ".join(f["namen"]))}{_fakten(fakten)}</div></details></li>')
        o.append("</ul></div>")
    elif ins_status.get("ok"):
        o.append('<div class="card"><p class="leer">In den letzten 45 Tagen keine nennenswerten Insider-Käufe im Universum.</p></div>')
    o.append("</section>")

    # ===================== SCANNER =====================
    wM, wP, wI = par.GEWICHT_MOMENTUM, par.GEWICHT_PEAD, par.GEWICHT_INSIDER
    o.append(f'<section class="tab" id="scanner"><div class="card"><div class="lbl">Stärkste Aktien heute</div>'
             f'<p class="erkl">Score 0–100 aus drei Bausteinen. Gekauft wird ab {schwelle} (schwarzer Strich). Momentum allein reicht nie.</p>'
             f'<div class="legende"><span><i class="blk" style="background:var(--s1)"></i>Momentum (max. {wM * 100:.0f})</span>'
             f'<span><i class="blk" style="background:var(--s2)"></i>Kurssprung nach Zahlen (max. {wP * 100:.0f})</span>'
             f'<span><i class="blk" style="background:var(--s3)"></i>Insider (max. {wI * 100:.0f})</span></div><ul class="liste">')
    for t, sc, k in kand:
        teil = [(100 * wM * k["M"], "--s1"), (100 * wP * k["P"], "--s2"), (100 * wI * k["I"], "--s3")]
        bar = "".join(f'<i style="width:{v:.1f}%;background:var({f})"></i>' for v, f in teil if v > 0)
        o.append(f'<li><div class="zeile"><div class="t">{_e(t)}</div><div class="r">{sc:.0f}</div>'
                 f'<div class="u">{_e(firmen.get(t, t))}</div><div class="ur">{"über Schwelle" if sc >= schwelle else f"fehlen {schwelle - sc:.0f}"}</div></div>'
                 f'<div class="stapel-wrap" style="margin:-4px 0 12px"><div class="stapel">{bar}</div>'
                 f'<div class="schwelle" style="left:{schwelle}%"></div></div></li>')
    if not kand:
        o.append('<p class="leer">Heute keine Kandidaten.</p>')
    o.append("</ul></div></section>")

    # ===================== STATISTIK =====================
    o.append('<section class="tab" id="statistik"><div class="card"><div class="lbl">Vergleich</div>'
             + _chart([{"n": "Radar", "f": "--s1", "v": s_radar}, {"n": "S&P 500", "f": "--s2", "v": s_spx},
                       {"n": "Nur Kern (S&P mit Trendfilter)", "f": "--s3", "v": [round(x, 2) for x in kern]}], daten, live_idx, "Vergleich")
             + '<div class="mini-t" style="margin-top:6px">„Nur Kern“ zeigt, was ohne Einzelaktien herausgekommen wäre. Der Abstand dazu ist der Beitrag der Empfehlungen.</div></div>')
    gew = [t["ergebnis"] for t in gz if t["ergebnis"] > 0]
    verl = [t["ergebnis"] for t in gz if t["ergebnis"] <= 0]
    halte = []
    for t in gz:
        try:
            halte.append(np.busday_count(t["einstieg_datum"], t["ausstieg_datum"]))
        except Exception:
            pass
    o.append('<div class="card"><div class="lbl">Kennzahlen</div>' + _fakten([
        ("Abgeschlossene Trades", str(len(gz))), ("Trefferquote", _pct(quote, 0, False) if quote is not None else "–"),
        ("Ø Gewinn", _pct(np.mean(gew)) if gew else "–"), ("Ø Verlust", _pct(np.mean(verl)) if verl else "–"),
        ("Gewinn/Verlust-Verhältnis", _zahl(abs(np.mean(gew) / np.mean(verl)), 2) if gew and verl and np.mean(verl) else "–"),
        ("Ø Mehrrendite je Trade", _pct(np.mean([t.get("ueber_markt", 0) for t in gz])) if gz else "–"),
        ("Ø Haltedauer", f"{np.mean(halte):.0f} Tage" if halte else "–"), ("Max. Rückgang", _pct(maxdd)),
        ("Bester Trade", _pct(max((t["ergebnis"] for t in gz), default=None))), ("Schlechtester Trade", _pct(min((t["ergebnis"] for t in gz), default=None))),
    ]) + "</div>")
    grp = defaultdict(list)
    for t in gz:
        typ = [x for x in t.get("typen", []) if x != "Momentum"]
        grp[" + ".join(typ) or "nur Momentum"].append(t)
    if grp:
        o.append('<div class="card"><div class="lbl">Nach Auslöser</div><div class="tw"><table><tr><th>Auslöser</th><th>Trades</th><th>Treffer</th><th>Ø Ergebnis</th><th>Ø vs. S&amp;P</th></tr>'
                 + "".join(f'<tr><td>{_e(k)}</td><td>{len(v)}</td><td>{_pct(np.mean([x["ergebnis"] > 0 for x in v]), 0, False)}</td>'
                           f'<td class="{_kl(np.mean([x["ergebnis"] for x in v]))}">{_pct(np.mean([x["ergebnis"] for x in v]))}</td>'
                           f'<td class="{_kl(np.mean([x.get("ueber_markt", 0) for x in v]))}">{_pct(np.mean([x.get("ueber_markt", 0) for x in v]))}</td></tr>'
                           for k, v in sorted(grp.items(), key=lambda kv: -len(kv[1])))
                 + "</table></div></div>")
    monate = defaultdict(list)
    for k in kurve:
        monate[k[0][:7]].append(k)
    mz, vor = [], None
    for m, ks in sorted(monate.items()):
        e_end, b_end = ks[-1][1], ks[-1][2]
        if vor:
            mz.append((m, e_end / vor[0] - 1, (b_end / vor[1] - 1) if b_end and vor[1] else None))
        vor = (e_end, b_end)
    if mz:
        mn = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
        o.append('<div class="card"><div class="lbl">Monate · Radar (S&amp;P 500)</div><div class="monate">'
                 + "".join(f'<div class="monat">{mn[int(m[5:7]) - 1]} {m[2:4]}<b class="{_kl(r)}">{_pct(r)}</b><span class="mini-t">({_pct(bm)})</span></div>' for m, r, bm in mz[-12:])
                 + "</div></div>")
    o.append("</section>")

    # ===================== LERNEN =====================
    L = dep.get("lernen") or {}
    namen = {"SCHWELLE": "Kauf-Schwelle", "HALTEDAUER": "Max. Haltedauer (Tage)", "STOPP_ATR_NACHZIEH": "Nachzieh-Stopp (× ATR)",
             "GEWICHT_MOMENTUM": "Gewicht Momentum", "GEWICHT_PEAD": "Gewicht Zahlen", "GEWICHT_INSIDER": "Gewicht Insider"}
    o.append('<section class="tab" id="lernen"><div class="card"><div class="lbl">So lernt der Radar</div>'
             f'<p class="erkl">Etwa alle {par.LERN_INTERVALL} Handelstage spielt er die letzten ~{par.LERN_FENSTER} Tage mit vielen Varianten '
             'seiner Einstellungen durch. Ist eine Variante klar besser (Rendite abzüglich halbem Max-Rückgang, mind. '
             f'{par.LERN_MIN_TRADES} Trades, {par.LERN_MARGE:.0%} Vorsprung), übernimmt er sie für die Zukunft. '
             'Vergangene Empfehlungen werden nie verändert. Die Vorsicht ist Absicht: Wer jedem Zufallstreffer folgt, verliert live.</p>'
             '<div class="lbl" style="margin-top:6px">Aktuelle Einstellungen</div>'
             + _fakten([(namen[k], (_pct(getattr(par, k), 0, False) if k.startswith("GEWICHT") else _zahl(getattr(par, k), 1 if isinstance(getattr(par, k), float) else 0)))
                        for k in namen]) + "</div>")
    if L.get("datum"):
        akt, best = L["aktuell"], L["bester"]
        o.append(f'<div class="card"><div class="lbl">Letzte Prüfung · {_d(L["datum"], "%d.%m.%Y")}</div>'
                 f'<p class="erkl">{L["varianten"]} Varianten auf {_d(L["fenster"][0], "%d.%m.%y")} – {_d(L["fenster"][1], "%d.%m.%y")} getestet. '
                 + ("<b>Neue Einstellungen übernommen.</b>" if L.get("gewechselt") else "Keine Variante war klar besser – Einstellungen bleiben.") + "</p>"
                 + '<div class="tw"><table><tr><th>Variante</th><th>Lernteil</th><th>Prüfteil</th><th>Trades</th></tr>'
                 + f'<tr><td><b>aktuell</b></td><td>{_pct(akt["lern"])}</td><td>{_pct(akt["pruef"])}</td><td>{akt["trades"]}</td></tr>'
                 + "".join(f'<tr><td>{_e(z["gewichte"])} · {z["parameter"]["SCHWELLE"]} · {z["parameter"]["HALTEDAUER"]} T · {_zahl(z["parameter"]["STOPP_ATR_NACHZIEH"], 1)}×</td>'
                           f'<td class="{_kl(z["lern"])}">{_pct(z["lern"])}</td><td class="{_kl(z["pruef"])}">{_pct(z["pruef"])}</td><td>{z["trades"]}</td></tr>'
                           for z in L.get("top", [])[:6])
                 + '</table></div><p class="mini-t" style="margin-top:8px">Werte = Rendite minus halber Max-Rückgang. Gewählt wird nach dem Lernteil; '
                 'übernommen nur, wenn die Variante auch im später liegenden Prüfteil klar besser ist.</p></div>')
        if L.get("historie"):
            o.append('<div class="card"><div class="lbl">Änderungen</div><ul class="liste">'
                     + "".join(f'<li><div class="zeile"><div class="t">{_d(h["datum"], "%d.%m.%Y")}</div><div class="r"></div>'
                               f'<div class="u">{_e(h["grund"])}</div></div></li>' for h in reversed(L["historie"])) + "</ul></div>")
    else:
        o.append('<div class="card"><p class="leer">Die erste Prüfung läuft beim nächsten Tageslauf.</p></div>')
    o.append("</section>")

    # ===================== Fuß =====================
    extra = ""
    if oddlot:
        extra += ('<div class="card"><details><summary class="lbl" style="margin:0">Sonderchancen · Odd-Lot-Angebote ›</summary><ul class="liste" style="margin-top:8px">'
                  + "".join(f'<li><div class="zeile"><div class="t">{_e(z["firma"])}</div><div class="r"><a href="{_e(z["link"])}" target="_blank" rel="noopener">Dokument</a></div>'
                            f'<div class="u">{_e(", ".join(z["ticker"]) or "–")} · {_e(z["datum"])}</div></div></li>' for z in oddlot[:6]) + "</ul></details></div>")
    if hinweise:
        extra += ('<div class="card"><details><summary class="lbl" style="margin:0">Hinweise ›</summary><div class="detail" style="padding-top:8px">'
                  + "<br>".join(_e(h) for h in hinweise) + "</div></details></div>")
    o.append(extra)
    o.append(f"""<div class="fuss">Regeln: Kauf ab Score {par.SCHWELLE} (schwacher Markt: {par.SCHWELLE_RISK_OFF}), max. eine neue Empfehlung pro Tag und
{par.MAX_POSITIONEN} Positionen, Größe {par.GEWICHT_MIN * 100:.0f}–{par.GEWICHT_MAX * 100:.0f} % je nach Score, max. {par.MAX_VERLUST_PRO_TRADE * 100:.0f} % Portfolio-Verlust pro Trade.
Freies Geld liegt im S&amp;P-500-ETF (Markt über 200-Tage-Linie) bzw. im Geldmarkt. Musterdepot inkl. Kosten, ohne Steuern und Dividenden.
Rückblick nutzt heutige Indexmitglieder und ist daher geschönt. Daten: Yahoo Finance, SEC EDGAR. Kein Anlagerat.</div>
</main><script>{JS}</script></body></html>""")
    return "\n".join(o)
