(function () {
"use strict";
const D = JSON.parse(document.getElementById("daten").textContent);
const $ = (s, el) => (el || document).querySelector(s);
const $$ = (s, el) => Array.from((el || document).querySelectorAll(s));
const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const ok = x => x !== null && x !== undefined && isFinite(x);
const zahl = (x, nk = 0) => ok(x) ? Number(x).toLocaleString("de-DE", { minimumFractionDigits: nk, maximumFractionDigits: nk }) : "–";
const usd = (x, nk = 0) => ok(x) ? zahl(x, nk) + " $" : "–";
const vz = x => ok(x) && x > 0 ? "+" : "";
const usdVz = (x, nk = 0) => ok(x) ? vz(x) + zahl(x, nk) + " $" : "–";
const pct = (x, nk = 1, mitVz = true) => ok(x) ? (mitVz ? vz(x) : "") + zahl(x * 100, nk) + " %" : "–";
const kl = x => !ok(x) || Math.abs(x) < 1e-9 ? "" : (x > 0 ? "pos" : "neg");
const kurz = (x) => { if (!ok(x)) return "–"; const a = Math.abs(x); return a >= 1e9 ? zahl(x / 1e9, 1) + " Mrd. $" : a >= 1e6 ? zahl(x / 1e6, 1) + " Mio. $" : a >= 1e4 ? zahl(x / 1e3, 0) + " Tsd. $" : usd(x); };
const preis = x => !ok(x) ? "–" : x >= 1000 ? zahl(x, 0) : x >= 10 ? zahl(x, 2) : x >= 1 ? zahl(x, 3) : zahl(x, 5);
const zeit = ms => ms ? new Date(ms).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "–";
const datum = ms => ms ? new Date(ms).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "2-digit" }) : "–";
const dauer = ms => { if (!ok(ms)) return "–"; const h = ms / 3.6e6; return h < 1 ? Math.max(1, Math.round(h * 60)) + " Min." : h < 48 ? zahl(h, h < 10 ? 1 : 0) + " Std." : zahl(h / 24, 1) + " Tage"; };
const tippI = txt => `<span class="tipp" tabindex="0" data-tipp="${esc(txt)}">?</span>`;
const richt = r => r > 0 ? `<span class="rt long">Long</span>` : `<span class="rt short">Short</span>`;
try { const t = JSON.parse(localStorage.getItem("radar_thema") || "null"); if (t) document.documentElement.dataset.theme = t; } catch (e) { }

const P = D.portfolio, R = D.regeln;
const TR = {}; D.trader.forEach(t => TR[t.adresse] = t);
const kurzAdr = a => a ? a.slice(0, 6) + "…" + a.slice(-4) : "–";
const tName = a => { const t = TR[a]; return t && t.name ? esc(t.name) : kurzAdr(a); };
const tLink = a => `<span class="tlink" data-trader="${esc(a)}">${tName(a)}</span>`;
const scan = a => `https://hypurrscan.io/address/${a}`;
const rendite = P.wert / P.start_kapital - 1;
const V = P.verlauf || [];
const btcR = V.length && ok(V[V.length - 1][2]) ? V[V.length - 1][2] / P.start_kapital - 1 : null;
const tage = P.start ? (D.stand - P.start) / 864e5 : 0;
const zu = P.trades || [];
const gewinnTrades = zu.filter(t => t.ergebnis > 0).length;
const SPG = D.spiegel || { pos: [], trades: [], verlauf: [], netto: [], je_trader: {}, kapital: R.SPIEGEL_KAPITAL };
const spR = ok(SPG.wert) ? SPG.wert / SPG.kapital - 1 : null;
const SV = SPG.verlauf || [];
const spTage = SPG.start ? (D.stand - SPG.start) / 864e5 : 0;
const spBtcR = SV.length && ok(SV[SV.length - 1][2]) ? SV[SV.length - 1][2] / SPG.kapital - 1 : btcR;
/* gemeinsame Zeitachse für den Vergleich (Rendite in % seit Start des jeweiligen Tests) */
function vergleichsReihen() {
  const ts = Array.from(new Set(V.map(v => v[0]).concat(SV.map(v => v[0])))).sort((a, b) => a - b);
  const nimm = (reihe, idx, basis) => { let j = 0, letzt = null; return ts.map(t => { while (j < reihe.length && reihe[j][0] <= t) { if (ok(reihe[j][idx])) letzt = reihe[j][idx] / basis - 1; j++; } return letzt; }); };
  const btc = SV.length ? nimm(SV, 2, SPG.kapital) : nimm(V, 2, P.start_kapital);
  return { ts, sp: nimm(SV, 1, SPG.kapital), ko: nimm(V, 1, P.start_kapital), btc };
}

/* ---------- Kopf ---------- */
const tabs = [["uebersicht", "Übersicht", null], ["spiegel", "Spiegel-Portfolio", SPG.pos.length || null], ["scanner", "Markt-Scanner", D.wetter ? (D.wetter.signale || []).filter(x => x.signal).length || null : null], ["tracking", "Tracking", (D.polymarket || []).reduce((n, t) => n + (t.n || 0), 0) || null], ["trader", "Trader", D.trader.length], ["bewegungen", "Bewegungen", D.bewegungen.length || null],
  ["kopie", "Kopier-Test", D.kopien.length || null], ["trades", "Papier-Trades", zu.length || null], ["methode", "Methode", null]];
document.body.innerHTML = `
<header class="kopf"><div class="in">
  <div class="zeile1">
    <div class="marke"><div class="logo"><svg viewBox="0 0 24 24" fill="none" style="stroke:var(--card)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2"/></svg></div>
      <div>${window.radarMenue ? radarMenue("smart", "Smart-Money-Radar") : "<h1>Smart-Money-Radar</h1>"}<div class="stand">Stand ${esc(zeit(D.stand))}<span class="lang"> · ${D.trader.length} Trader auf Hyperliquid · prüft alle 15 Min.</span></div></div></div>
    <div class="rechts">
      <span class="pill" title="Es werden keine echten Orders gesendet. Alle Ergebnisse sind simuliert – inklusive Gebühren, Slippage und Funding."><i style="background:var(--warn)"></i>Nur Papier-Test</span>
      <a class="pill nur-desktop" href="https://github.com/${esc(D.repo)}/actions/workflows/smart.yml" target="_blank" rel="noopener" title="Öffnet GitHub: dort „Run workflow“ tippen.">↻ Jetzt prüfen</a>
      <button class="ikon" id="thema" aria-label="Hell/Dunkel"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg></button>
    </div>
  </div>
  <nav class="tabs">${tabs.map(([k, t, z], i) => `<button data-tab="${k}" class="${i === 0 ? "aktiv" : ""}">${t}${z ? `<span class="zahl">${z}</span>` : ""}</button>`).join("")}</nav>
</div></header>
<main>${tabs.map(([k], i) => `<section class="tab${i === 0 ? " aktiv" : ""}" id="t-${k}"></section>`).join("")}</main>
<div class="modal"><div class="blatt"><div class="blatt-kopf"><div id="m-kopf"></div><button class="schliessen">×</button></div><div class="blatt-inhalt" id="m-inhalt"></div></div></div>`;
$("#thema").addEventListener("click", () => {
  const dunkel = document.documentElement.dataset.theme ? document.documentElement.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  const neu = dunkel ? "light" : "dark"; document.documentElement.dataset.theme = neu;
  try { localStorage.setItem("radar_thema", JSON.stringify(neu)); } catch (e) { }
  zeichneCharts();
});
const gerendert = {};
function zeigeTab(k) {
  $$("nav.tabs button").forEach(b => b.classList.toggle("aktiv", b.dataset.tab === k));
  $$("section.tab").forEach(s => s.classList.toggle("aktiv", s.id === "t-" + k));
  if (!gerendert[k]) { gerendert[k] = true; RENDER[k]($("#t-" + k)); }
  try { history.replaceState(null, "", "#" + k); } catch (e) { }
  zeichneCharts();
}
$$("nav.tabs button").forEach(b => b.addEventListener("click", () => zeigeTab(b.dataset.tab)));

/* ---------- Linien-Chart ---------- */
const CHARTS = [];
const cssv = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
function linie(host, x, serien, fmt) {
  CHARTS.push(() => {
    if (!host.isConnected || !host.offsetParent) return;
    const W = host.clientWidth || 600, H = 260, pl = 4, pr = 62, pt = 12, pb = 24;
    if (x.length < 2) { host.innerHTML = '<div class="leer">Noch zu wenige Messpunkte – der Verlauf füllt sich mit jedem Lauf.</div>'; return; }
    const alle = []; serien.forEach(s => s.v.forEach(v => ok(v) && alle.push(v)));
    let lo = Math.min(...alle), hi = Math.max(...alle); if (hi - lo < 1e-9) { lo -= 1; hi += 1; }
    const pad = (hi - lo) * 0.08; lo -= pad; hi += pad;
    const X = i => pl + (W - pl - pr) * (x[i] - x[0]) / ((x[x.length - 1] - x[0]) || 1);
    const Y = v => pt + (H - pt - pb) * (1 - (v - lo) / (hi - lo));
    const ticks = []; const n = 4; for (let k = 0; k <= n; k++) ticks.push(lo + (hi - lo) * k / n);
    let svg = `<svg width="${W}" height="${H}">`;
    ticks.forEach(t => { svg += `<line x1="${pl}" x2="${W - pr}" y1="${Y(t)}" y2="${Y(t)}" stroke="${cssv("--line2")}"/><text x="${W - pr + 8}" y="${Y(t) + 4}" font-size="11" fill="${cssv("--ink3")}">${esc(fmt(t))}</text>`; });
    const kurzZeit = x[x.length - 1] - x[0] < 2 * 864e5;
    const t0 = x[0], t1 = x[x.length - 1];
    [t0, (t0 + t1) / 2, t1].forEach((t, j) => {
      const xp = pl + (W - pl - pr) * (t - t0) / ((t1 - t0) || 1);
      const txt = kurzZeit ? new Date(t).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) : datum(t);
      svg += `<text x="${xp}" y="${H - 6}" font-size="11" fill="${cssv("--ink3")}" text-anchor="${j === 0 ? "start" : j === 2 ? "end" : "middle"}">${esc(txt)}</text>`; });
    serien.forEach(s => {
      let d = "", an = false;
      s.v.forEach((v, i) => { if (!ok(v)) { an = false; return; } d += (an ? "L" : "M") + X(i).toFixed(1) + " " + Y(v).toFixed(1); an = true; });
      svg += `<path d="${d}" fill="none" stroke="${cssv(s.farbe)}" stroke-width="${s.breite || 2}" ${s.strich ? 'stroke-dasharray="5 4"' : ""} stroke-linejoin="round"/>`;
    });
    svg += `<line class="hlin" x1="0" x2="0" y1="${pt}" y2="${H - pb}" stroke="${cssv("--ink3")}" stroke-dasharray="3 3" style="display:none"/></svg>`;
    host.innerHTML = svg + '<div class="tip"></div>';
    const tip = $(".tip", host), hl = $(".hlin", host), el = $("svg", host);
    el.addEventListener("mousemove", ev => {
      const r = el.getBoundingClientRect(), mx = ev.clientX - r.left;
      let best = 0, bd = 1e9; x.forEach((_, i) => { const d = Math.abs(X(i) - mx); if (d < bd) { bd = d; best = i; } });
      hl.setAttribute("x1", X(best)); hl.setAttribute("x2", X(best)); hl.style.display = "";
      tip.innerHTML = `<div class="tk">${esc(zeit(x[best]))}</div>` + serien.map(s => `<div class="tz"><span><i style="background:var(${s.farbe})"></i>${esc(s.name)}</span><b>${esc(fmt(s.v[best]))}</b></div>`).join("");
      tip.style.display = "block"; tip.style.left = Math.min(Math.max(0, X(best) + 12), W - 190) + "px"; tip.style.top = "8px";
    });
    el.addEventListener("mouseleave", () => { tip.style.display = "none"; hl.style.display = "none"; });
  });
}
function zeichneCharts() { CHARTS.forEach(f => f()); }
window.addEventListener("resize", () => { clearTimeout(window._rz); window._rz = setTimeout(zeichneCharts, 150); });

/* ---------- Bausteine ---------- */
function konsensBalken(c) {
  const l = c.long / c.n * 100;
  return `<div class="kbar" title="${c.long} Long · ${c.short} Short"><i class="l" style="width:${l}%"></i><i class="s" style="width:${100 - l}%"></i></div>`;
}
function konsensTabelle(liste) {
  if (!liste.length) return `<div class="leer">Gerade halten höchstens einzelne Trader denselben Coin.</div>`;
  return `<div class="tw"><table class="tbl"><thead><tr><th class="l">Coin</th><th class="l">Long / Short</th><th>Trader</th><th>Einigkeit</th><th>Volumen Long</th><th>Volumen Short</th><th class="l">Status</th></tr></thead><tbody>
  ${liste.map(c => `<tr><td class="l tick">${esc(c.coin)}</td><td class="l">${konsensBalken(c)}<span class="klein mute">${c.long} L · ${c.short} S</span></td><td>${c.n}</td><td>${pct(c.anteil, 0, false)}</td>
    <td>${kurz(c.wert_long)}</td><td>${kurz(c.wert_short)}</td>
    <td class="l">${c.gehalten ? `<span class="status aktiv">Papier: ${c.richtung > 0 ? "Long" : "Short"}</span>` : c.signal ? `<span class="status test">Signal</span>` : `<span class="mute klein">uneinig / zu wenige</span>`}</td></tr>`).join("")}
  </tbody></table></div>`;
}
function posTabelle(liste) {
  if (!liste.length) return `<div class="leer">Keine offene Papier-Position. Sobald mindestens ${R.KONSENS_MIN_TRADER} Top-Trader zu ${pct(R.KONSENS_MIN_ANTEIL, 0, false)} dieselbe Richtung halten, eröffnet der Test eine.</div>`;
  return `<div class="tw"><table class="tbl"><thead><tr><th class="l">Coin</th><th class="l">Richtung</th><th>Einstieg</th><th>Aktuell</th><th>Einsatz</th><th>Ergebnis</th><th>Seit</th><th>Trader beim Einstieg</th></tr></thead><tbody>
  ${liste.map(p => `<tr><td class="l tick">${esc(p.coin)}</td><td class="l">${richt(p.r)}</td><td>${preis(p.ein)}</td><td>${preis(p.px)}</td><td>${usd(p.notional)}</td>
    <td class="${kl(p.erg)}">${usdVz(p.erg)} <span class="klein">(${pct(p.pct)})</span></td><td>${dauer(D.stand - p.zeit)}</td><td>${p.n || "–"} (${pct(p.anteil, 0, false)})</td></tr>`).join("")}
  </tbody></table></div>`;
}

/* ---------- Tabs ---------- */
const RENDER = {
  uebersicht(el) {
    const signale = D.konsens.filter(c => c.signal).length;
    const vg = ok(spR) && ok(spBtcR) ? spR - spBtcR : null;
    const kopienErg = D.trader.reduce((s, t) => s + (t.kopie ? t.kopie.ergebnis + t.kopie.offen_erg : 0), 0);
    el.innerHTML = `
    <div class="h-held">
      <div><div class="h-datum">Papier-Test seit ${esc(datum(P.start))} · ${zahl(tage, tage < 10 ? 1 : 0)} Tage</div>
        <h2 class="h-titel">Hätte man mit Smart Money Geld verdient?</h2>
        <p class="h-unter">${D.trader.length} beständige Top-Trader auf Hyperliquid, zwei Papier-Portfolios mit je ${usd(SPG.kapital)}: Das <b>Spiegel-Portfolio</b> kopiert alle Trader anteilig nach ihrer Note, das <b>Konsens-Portfolio</b> kauft nur, wenn sich mehrere einig sind. Echte Preise, Gebühren, Slippage und Funding – aber kein echtes Geld.</p></div>
      <div class="h-kpis">
        <div><span>Spiegel-Portfolio</span><b class="${kl(spR)}">${pct(spR)}</b><small>${usd(SPG.wert)} · ${SPG.pos.length} Positionen</small></div>
        <div><span>Konsens-Portfolio</span><b class="${kl(rendite)}">${pct(rendite)}</b><small>${signale} Signale · ${P.pos.length} offen</small></div>
        <div><span>Bitcoin halten</span><b class="${kl(spBtcR)}">${pct(spBtcR)}</b><small>${ok(vg) ? (vg >= 0 ? "Spiegel liegt vorn: " : "Spiegel liegt hinten: ") + pct(vg) : "Vergleich ab dem 2. Messpunkt"}</small></div>
      </div>
    </div>
    ${tage < 28 ? `<div class="box warn" style="margin-bottom:16px">Der Test läuft erst ${zahl(tage, tage < 10 ? 1 : 0)} Tage. Aussagekräftig wird das Ergebnis frühestens nach 4–8 Wochen – vorher ist alles Zufall. Bitte kein echtes Geld darauf setzen.</div>` : ""}
    <div class="grid">
      <div class="card c8"><div class="ch"><div><h3 class="ct">Rendite seit Start</h3><div class="cs">Alle Tests ohne Hebel, nach Kosten</div></div>
        <div class="legende"><span><i style="background:var(--s7)"></i>Spiegel</span><span><i style="background:var(--s1)"></i>Konsens</span><span><i style="background:var(--s4)"></i>Bitcoin halten</span></div></div>
        <div class="chart" id="ch-verlauf"></div></div>
      <div class="card c4"><div class="ch"><div><h3 class="ct">Die drei Tests</h3><div class="cs">Was davon funktioniert, zeigt sich erst nach Wochen</div></div></div>
        <ul class="schritte" style="margin-top:0">
          <li><span>Spiegel-Portfolio ${tippI("Kapital nach Note auf alle Trader verteilt, jede Position anteilig kopiert. Wie Copy-Trading.")}</span><span class="${kl(spR)}">${pct(spR)}</span></li>
          <li><span>Konsens-Portfolio ${tippI("Kauft nur, wenn mindestens " + R.KONSENS_MIN_TRADER + " Trader zu " + pct(R.KONSENS_MIN_ANTEIL, 0, false) + " dieselbe Richtung halten.")}</span><span class="${kl(rendite)}">${pct(rendite)}</span></li>
          <li><span>Einzel-Kopien ${tippI("Jede neue Position mit festen " + usd(R.EINZEL_NOTIONAL) + " kopiert – misst vor allem die Verzögerungskosten.")}</span><span class="${kl(kopienErg)}">${usdVz(kopienErg)}</span></li>
          <li><span>Bitcoin halten</span><span class="${kl(spBtcR)}">${pct(spBtcR)}</span></li>
        </ul>
        <p class="klein mute" style="margin:12px 0 0">Push aufs Handy: Konsens-Käufe und -Verkäufe, Spiegel-Trades ab ${usd(R.SPIEGEL_PUSH_AB)}, jeden Abend ab ${R.TAGES_PUSH_STUNDE} Uhr der Tagesstand.</p></div>
    </div>
    <div class="card" style="margin-bottom:16px"><div class="ch"><div><h3 class="ct">Konsens-Positionen</h3><div class="cs">Werden geschlossen, sobald weniger als ${R.KONSENS_AUS_TRADER} Trader übrig sind oder die Einigkeit unter ${pct(R.KONSENS_AUS_ANTEIL, 0, false)} fällt</div></div></div>${posTabelle(P.pos)}</div>
    <div class="card"><div class="ch"><div><h3 class="ct">Was die Top-Trader gerade halten</h3><div class="cs">Coins, in denen mindestens 2 der beobachteten Trader eine nennenswerte Position haben</div></div></div>${konsensTabelle(D.konsens)}</div>`;
    const vr = vergleichsReihen();
    linie($("#ch-verlauf", el), vr.ts, [{ name: "Spiegel", farbe: "--s7", v: vr.sp, breite: 2.4 }, { name: "Konsens", farbe: "--s1", v: vr.ko, breite: 2 }, { name: "Bitcoin halten", farbe: "--s4", v: vr.btc, strich: true }], v => pct(v, 1));
  },

  spiegel(el) {
    const je = Object.entries(SPG.je_trader || {}).sort((a, b) => (b[1].gewicht || 0) - (a[1].gewicht || 0));
    const offenErg = SPG.pos.reduce((s, p) => s + (p.erg || 0), 0);
    const einsatz = SPG.pos.reduce((s, p) => s + p.notional, 0);
    const sTr = SPG.trades || [];
    el.innerHTML = `<p class="erkl">${usd(SPG.kapital)} werden nach der Note auf die ${D.trader.length} Trader verteilt – bessere Trader bekommen mehr. Hält ein Trader 20 % seines Kontos in ETH long, hält sein Anteil hier ebenfalls 20 % in ETH long. Nutzt er Hebel, wird proportional heruntergerechnet, damit nie mehr als das eigene Kapital im Markt ist. Fällt ein Trader bei der täglichen Auswahl heraus, werden seine Positionen geschlossen; neue bekommen sofort ihren Anteil.</p>
    <div class="kpis">
      <div class="kpi"><div class="k">Wert</div><div class="v">${usd(SPG.wert)}</div><div class="n">Start ${usd(SPG.kapital)} am ${esc(datum(SPG.start))}</div></div>
      <div class="kpi"><div class="k">Rendite</div><div class="v ${kl(spR)}">${pct(spR)}</div><div class="n">Bitcoin im selben Zeitraum ${pct(spBtcR)}</div></div>
      <div class="kpi"><div class="k">Im Markt</div><div class="v">${usd(einsatz)}</div><div class="n">${SPG.pos.length} Positionen · Buchwert ${usdVz(offenErg)}</div></div>
      <div class="kpi"><div class="k">Kosten bisher</div><div class="v neg">${usd(-SPG.gebuehren)}</div><div class="n">Funding ${usdVz(SPG.funding)} · ${sTr.length} Abschlüsse</div></div>
    </div>
    <div class="grid">
      <div class="card c7"><div class="ch"><div><h3 class="ct">Aufteilung nach Trader</h3><div class="cs">Gewicht aus der Note · Ergebnis nach Gebühren und Funding</div></div></div>
        ${je.length ? `<div class="tw"><table class="tbl"><thead><tr><th class="l">Trader</th><th>Gewicht</th><th>Budget</th><th>Im Markt</th><th>Pos.</th><th>Ergebnis</th></tr></thead><tbody>
        ${je.map(([a, v]) => `<tr class="klick" data-trader="${esc(a)}"><td class="l">${TR[a] ? `<span class="tick">${tName(a)}</span>` : `<span class="mute">${kurzAdr(a)} (ausgeschieden)</span>`}</td>
          <td><span class="gbar"><i style="width:${Math.min(100, (v.gewicht || 0) * 100 / Math.max(...je.map(x => x[1].gewicht || 0), 0.0001))}%"></i></span>${pct(v.gewicht, 1, false)}</td>
          <td>${usd(v.budget)}</td><td>${usd(v.einsatz)}</td><td>${v.positionen}</td><td class="${kl(v.realisiert + v.offen_erg)}">${usdVz(v.realisiert + v.offen_erg)}</td></tr>`).join("")}
        </tbody></table></div>` : '<div class="leer">Noch keine Aufteilung.</div>'}</div>
      <div class="card c5"><div class="ch"><div><h3 class="ct">Netto-Ausrichtung nach Coin</h3><div class="cs">Summe aller gespiegelten Positionen</div></div></div>
        ${SPG.netto.length ? `<div class="tw"><table class="tbl"><thead><tr><th class="l">Coin</th><th>Long</th><th>Short</th><th>Netto</th><th>Trader</th></tr></thead><tbody>
        ${SPG.netto.slice(0, 20).map(n => `<tr><td class="l tick">${esc(n.coin)}</td><td class="pos">${usd(n.long)}</td><td class="neg">${usd(n.short)}</td><td class="${kl(n.long - n.short)}">${usdVz(n.long - n.short)}</td><td>${n.trader}</td></tr>`).join("")}
        </tbody></table></div>` : '<div class="leer">Keine offenen Positionen.</div>'}</div>
    </div>
    <div class="card" style="margin-bottom:16px"><div class="ch"><div><h3 class="ct">Offene Spiegel-Positionen</h3></div></div>
      ${SPG.pos.length ? `<div class="tw"><table class="tbl karten"><thead><tr><th class="l">Trader</th><th class="l">Coin</th><th class="l">Richtung</th><th>Einsatz</th><th>Einstieg</th><th>Aktuell</th><th>Seit</th><th>Ergebnis</th></tr></thead><tbody>
      ${SPG.pos.map(p => `<tr><td class="l">${tLink(p.a)}</td><td class="l tick">${esc(p.coin)}</td><td class="l">${richt(p.r)}</td><td>${usd(p.notional)}</td><td>${preis(p.ein)}</td><td>${preis(p.px)}</td><td>${dauer(D.stand - p.zeit)}</td><td class="m-r ${kl(p.erg)}">${usdVz(p.erg)} <span class="klein">(${pct(p.pct)})</span></td></tr>`).join("")}
      </tbody></table></div>` : '<div class="leer">Keine offenen Positionen.</div>'}</div>
    <div class="card"><div class="ch"><div><h3 class="ct">Letzte Abschlüsse</h3><div class="cs">Ganz oder teilweise geschlossen</div></div></div>
      ${sTr.length ? `<div class="tw"><table class="tbl karten"><thead><tr><th class="l">Zeit</th><th class="l">Trader</th><th class="l">Coin</th><th class="l">Richtung</th><th>Einsatz</th><th>Dauer</th><th class="l">Grund</th><th>Ergebnis</th></tr></thead><tbody>
      ${sTr.slice(0, 100).map(t => `<tr><td class="l mute">${esc(zeit(t.zeit_aus))}</td><td class="l">${tLink(t.a)}</td><td class="l tick">${esc(t.coin)}</td><td class="l">${richt(t.r)}</td><td>${usd(t.notional)}</td><td>${dauer(t.zeit_aus - t.zeit_ein)}</td><td class="l mute klein">${esc(t.grund)}${t.teil ? " (Teil)" : ""}</td><td class="m-r ${kl(t.ergebnis)}">${usdVz(t.ergebnis, 2)}</td></tr>`).join("")}
      </tbody></table></div>` : '<div class="leer">Noch kein Abschluss.</div>'}</div>`;
  },

  scanner(el) {
    const W = D.wetter;
    if (!W) { el.innerHTML = '<div class="leer">Der Scanner läuft beim nächsten Durchgang zum ersten Mal.</div>'; return; }
    const sig = (W.signale || []).filter(x => x.signal), wert = W.kapital + W.ergebnis;
    const b = W.brier || {};
    const pc = x => ok(x) ? zahl(x * 100, 0) + " %" : "–";
    const artTxt = a => a === "highest" ? "Höchst" : "Tiefst";
    el.innerHTML = `<div class="box warn" style="margin-bottom:16px">Reiner Papier-Test mit öffentlichen Daten – es wird nichts gewettet. Die Teilnahme an Polymarket ist von Deutschland aus nicht erlaubt.</div>
    <div class="h-held" style="margin-bottom:16px">
      <div><div class="h-datum">Wetter-Märkte · letzter Scan ${esc(zeit((W.letzter_scan || 0) * 1000))}</div>
        <h2 class="h-titel">Wo liegt der Markt daneben?</h2>
        <p class="h-unter">Für jede Temperatur-Wette auf Polymarket rechnet der Scanner mit 82 Wetter-Modellläufen (ECMWF + GFS) für genau die Flughafen-Station, nach der aufgelöst wird, korrigiert um den Fehler des Modells an dieser Station in den letzten 7 Tagen – plus die heute schon gemessenen Werte. Weicht die Wahrscheinlichkeit um mindestens ${zahl(W.regeln.vorteil * 100)} Prozentpunkte vom Preis ab, „kauft“ er auf Papier ${usd(W.regeln.einsatz)}.</p></div>
      <div class="h-kpis">
        <div><span>Papierkapital</span><b class="${kl(W.ergebnis)}">${usd(wert)}</b><small>${usdVz(W.ergebnis)} seit Start</small></div>
        <div><span>Trades</span><b>${zahl(W.n)}<i> / ${zahl(W.offen.length)} offen</i></b><small>${W.n ? pct(W.gewonnen / W.n, 0, false) + " gewonnen" : "noch nichts aufgelöst"}</small></div>
        <div><span>Modell gegen Markt ${tippI("Brier-Score über alle aufgelösten Spannen: je kleiner, desto treffsicherer. Liegt das Modell unter dem Markt, sieht es mehr als die anderen Händler.")}</span><b>${ok(b.modell) ? zahl(b.modell, 3) : "–"}<i> / ${ok(b.markt) ? zahl(b.markt, 3) : "–"}</i></b><small>${b.n ? zahl(b.n) + " Spannen · " + (b.modell < b.markt ? "Modell besser" : "Markt besser") : "Messung startet nach erster Auflösung"}</small></div>
      </div>
    </div>
    ${W.fehler ? `<div class="box fehler" style="margin-bottom:16px">Letzter Scan fehlgeschlagen: ${esc(W.fehler)}</div>` : ""}
    <div class="card" style="margin-bottom:16px"><div class="ch"><div><h3 class="ct">Aktuelle Signale</h3><div class="cs">${zahl((W.signale || []).length)} Märkte geprüft · ${zahl(sig.length)} mit genug Abweichung</div></div></div>
      ${sig.length ? `<div class="tw"><table class="tbl karten"><thead><tr><th class="l">Stadt</th><th class="l">Wette</th><th class="l">Tag</th><th>gemessen</th><th>Modell-Mitte</th><th class="l">Empfehlung</th><th>Modell</th><th>Preis</th><th>Vorteil</th></tr></thead><tbody>
      ${sig.map(x => `<tr><td class="l"><b>${esc(x.stadt)}</b><div class="firma">${esc(x.icao)} · noch ${zahl(Math.max(0, x.stunden_rest))} Std.</div></td><td class="l">${artTxt(x.art)}temperatur</td><td class="l">${esc(datum(x.datum))}</td>
        <td>${ok(x.beobachtet) ? zahl(x.beobachtet, 1) + " °C" : "–"}</td><td>${zahl(x.ens_median, 1)} °C</td>
        <td class="l"><span class="rt ${x.signal.seite === "JA" ? "long" : "short"}">${x.signal.seite}</span> ${esc(x.signal.titel)}</td><td>${pc(x.signal.seite === "JA" ? x.signal.p : 1 - x.signal.p)}</td><td>${zahl(x.signal.preis * 100, 1)} ¢</td><td class="m-r pos">+${zahl(x.signal.vorteil * 100, 0)} Pkt.</td></tr>`).join("")}
      </tbody></table></div>` : '<div class="leer">Gerade keine Abweichung, die groß genug ist. Der Markt liegt nah am Modell.</div>'}</div>
    <div class="grid">
      <div class="card c6"><div class="ch"><div><h3 class="ct">Offene Papier-Trades</h3><div class="cs">Werden nach Auflösung (meist am Folgetag) abgerechnet</div></div></div>
        ${W.offen.length ? `<div class="tw"><table class="tbl"><thead><tr><th class="l">Markt</th><th class="l">Wette</th><th>Preis</th><th>Modell</th></tr></thead><tbody>
        ${W.offen.map(t => `<tr><td class="l">${esc(t.stadt)} <span class="mute klein">${artTxt(t.art)} · ${esc(datum(t.datum))}</span></td><td class="l"><span class="rt ${t.seite === "JA" ? "long" : "short"}">${t.seite}</span> ${esc(t.titel)}</td><td>${zahl(t.preis * 100, 1)} ¢</td><td>${pc(t.seite === "JA" ? t.p : 1 - t.p)}</td></tr>`).join("")}
        </tbody></table></div>` : '<div class="leer">Keine offenen Trades.</div>'}</div>
      <div class="card c6"><div class="ch"><div><h3 class="ct">Papierkapital</h3><div class="cs">Start ${usd(W.kapital)} · ${usd(W.regeln.einsatz)} je Signal</div></div></div><div class="chart" id="ch-wx"></div></div>
    </div>
    <div class="card"><div class="ch"><div><h3 class="ct">Abgerechnete Trades</h3></div></div>
      ${W.trades.length ? `<div class="tw"><table class="tbl karten"><thead><tr><th class="l">Markt</th><th class="l">Wette</th><th>Preis</th><th>Modell</th><th class="l">Ausgang</th><th>Ergebnis</th></tr></thead><tbody>
      ${W.trades.map(t => `<tr><td class="l">${esc(t.stadt)} <span class="mute klein">${artTxt(t.art)} · ${esc(datum(t.datum))}</span></td><td class="l"><span class="rt ${t.seite === "JA" ? "long" : "short"}">${t.seite}</span> ${esc(t.titel)}</td><td>${zahl(t.preis * 100, 1)} ¢</td><td>${pc(t.seite === "JA" ? t.p : 1 - t.p)}</td>
        <td class="l">${t.gewonnen ? '<span class="status aktiv">gewonnen</span>' : '<span class="status" style="background:var(--badbg);color:var(--bad)">verloren</span>'}</td><td class="m-r ${kl(t.erg)}">${usdVz(t.erg, 2)}</td></tr>`).join("")}
      </tbody></table></div>` : '<div class="leer">Noch nichts aufgelöst – Temperatur-Märkte werden am Tag nach dem Messtag abgerechnet.</div>'}</div>
    <p class="fuss">Methode: Ensemble-Vorhersage von Open-Meteo (ECMWF IFS 0,25° mit 51 und GFS mit 31 Läufen) für die Koordinaten der Auflösungs-Station, Unsicherheit Station ↔ Modell ${zahl(W.regeln.sigma_heute, 1)} °C (heute) bzw. ${zahl(W.regeln.sigma_morgen, 1)} °C (morgen), gemessene Werte aus den METAR-Meldungen (aviationweather.gov). Signale nur bei mind. ${usd(W.regeln.liq)} Liquidität, Einstieg mit ${pct(W.regeln.slippage, 0, false)} Aufschlag. Später kommen Fed- und Politik-Märkte über den Vergleich mit anderen Prognosebörsen dazu.</p>`;
    const V3 = W.verlauf || [];
    linie($("#ch-wx", el), V3.map(v => v[0]), [{ name: "Papierkapital", farbe: "--s3", v: V3.map(v => v[1]), breite: 2.2 }], v => usd(v));
  },

  tracking(el) {
    const L = D.polymarket || [];
    if (!L.length) { el.innerHTML = '<div class="leer">Noch kein Trader im Tracking.</div>'; return; }
    el.innerHTML = L.map((T, i) => {
      const wR = T.kapital + (T.real || 0), wI = T.kapital + (T.ideal || 0);
      const tq = n => T.n ? n / T.n : null;
      const abger = T.n - T.verpasst;
      return `<div class="box warn" style="margin-bottom:16px">Reiner Papier-Test mit öffentlichen Daten – es wird nichts gewettet. Die Teilnahme an Polymarket ist von Deutschland aus nicht erlaubt.</div>
      <div class="h-held" style="margin-bottom:16px">
        <div><div class="h-datum">Polymarket-Tracking seit ${esc(zeit(T.start * 1000))}</div>
          <h2 class="h-titel"><a href="https://polymarket.com/@${esc(T.name)}" target="_blank" rel="noopener" style="color:inherit">${esc(T.name)} ↗</a></h2>
          <p class="h-unter">Jeder seiner Käufe wird nach Auflösung des Markts mit ${usd(T.kapital)} Papierkapital nachgerechnet: <b>ideal</b> zu seinem Preis (in der Praxis unmöglich) und <b>realistisch</b> zum Preis ~${T.regeln.verzug} s später plus ${pct(T.regeln.slippage, 0, false)} Slippage. Schließt der Markt vorher, ist der Trade verpasst.</p></div>
        <div class="h-kpis">
          <div><span>Kopie realistisch</span><b class="${kl(T.real)}">${pct(T.real / T.kapital, 2)}</b><small>${usd(wR)} · ${usdVz(T.real)}</small></div>
          <div><span>Kopie ideal</span><b class="${kl(T.ideal)}">${pct(T.ideal / T.kapital, 2)}</b><small>${usd(wI)} · ${usdVz(T.ideal)}</small></div>
          <div><span>Er selbst</span><b class="${kl(T.er)}">${usdVz(T.er)}</b><small>mit seinen echten Einsätzen (${usd(T.er_einsatz)})</small></div>
        </div>
      </div>
      ${T.fehler ? `<div class="box fehler" style="margin-bottom:16px">Letzter Abruf fehlgeschlagen: ${esc(T.fehler)}</div>` : ""}
      <div class="kpis">
        <div class="kpi"><div class="k">Trades abgerechnet</div><div class="v">${zahl(T.n)}</div><div class="n">${zahl(T.offen)} warten auf Marktende</div></div>
        <div class="kpi"><div class="k">Verpasst ${tippI("Der Markt war schon zu, bevor die Kopie hätte kaufen können – er kauft oft in den letzten Sekunden.")}</div><div class="v">${T.n ? pct(T.verpasst / T.n, 0, false) : "–"}</div><div class="n">${zahl(T.verpasst)} von ${zahl(T.n)} zu spät</div></div>
        <div class="kpi"><div class="k">Treffer ideal</div><div class="v">${tq(T.gewonnen_ideal) !== null ? pct(tq(T.gewonnen_ideal), 0, false) : "–"}</div><div class="n">gewonnene Wetten</div></div>
        <div class="kpi"><div class="k">Rendite je Einsatz (realistisch)</div><div class="v ${kl(T.real)}">${T.real_einsatz ? pct(T.real / T.real_einsatz, 1) : "–"}</div><div class="n">ideal ${T.ideal_einsatz ? pct(T.ideal / T.ideal_einsatz, 1) : "–"} · er ${T.er_einsatz ? pct(T.er / T.er_einsatz, 1) : "–"}</div></div>
      </div>
      <div class="grid"><div class="card c12"><div class="ch"><div><h3 class="ct">Papierkapital</h3><div class="cs">Start ${usd(T.kapital)} · Einsatz ${usd(T.regeln.basis)} bei seinem typischen Einsatz (${usd(T.regeln.min)}–${usd(T.regeln.max)}) · Gebühr-Annahme ${pct(T.regeln.gebuehr, 1, false)}</div></div>
        <div class="legende"><span><i style="background:var(--s7)"></i>realistisch</span><span><i style="background:var(--s1)"></i>ideal</span></div></div>
        <div class="chart" id="ch-pm-${i}"></div></div></div>
      <div class="card"><div class="ch"><div><h3 class="ct">Letzte abgerechnete Trades</h3></div></div>
        ${T.trades.length ? `<div class="tw"><table class="tbl karten"><thead><tr><th class="l">Zeit</th><th class="l">Markt</th><th class="l">Tipp</th><th>vor Ende ${tippI("So viele Sekunden vor Marktschluss hat er gekauft.")}</th><th>sein Preis</th><th>Kopie-Preis</th><th>Einsatz</th><th class="l">Ausgang</th><th>Ergebnis ideal</th><th>Ergebnis realistisch</th></tr></thead><tbody>
        ${T.trades.map(t => `<tr><td class="l mute">${esc(zeit(t.ts * 1000))}</td><td class="l wrap klein">${esc(t.titel)}</td><td class="l"><span class="rt ${t.outcome === "Up" ? "long" : "short"}">${esc(t.outcome)}</span></td>
          <td>${t.sekunden_vor_ende < 120 ? t.sekunden_vor_ende + " s" : Math.round(t.sekunden_vor_ende / 60) + " Min."}</td><td>${zahl(t.preis * 100, 1)} ¢</td>
          <td>${t.verpasst ? '<span class="mute">verpasst</span>' : zahl(t.preis_r * 100, 1) + " ¢"}</td><td>${usd(t.einsatz)}</td>
          <td class="l">${t.gewonnen ? '<span class="status aktiv">gewonnen</span>' : '<span class="status" style="background:var(--badbg);color:var(--bad)">verloren</span>'}</td>
          <td class="${kl(t.erg_i)}">${usdVz(t.erg_i, 2)}</td><td class="m-r ${kl(t.erg_r)}">${t.verpasst ? "–" : usdVz(t.erg_r, 2)}</td></tr>`).join("")}
        </tbody></table></div>` : `<div class="leer">Noch nichts abgerechnet. Seine Märkte laufen 5–15 Minuten; abgerechnet wird nach Marktende beim nächsten Lauf.</div>`}</div>`;
    }).join('<div style="height:24px"></div>');
    L.forEach((T, i) => { const V2 = T.verlauf || []; linie($("#ch-pm-" + i, el), V2.map(v => v[0]), [{ name: "realistisch", farbe: "--s7", v: V2.map(v => v[1]), breite: 2.4 }, { name: "ideal", farbe: "--s1", v: V2.map(v => v[2]) }], v => usd(v)); });
  },

  trader(el) {
    const zeilen = D.trader.slice().sort((a, b) => (b.note || 0) - (a.note || 0));
    el.innerHTML = `<p class="erkl">Ausgewählt nach Beständigkeit, nicht nach dem größten Gewinn: mindestens ${R.MIN_TAGE_HISTORIE} Tage Historie, in mindestens ${pct(R.MIN_MONATE_POSITIV, 0, false)} der Monate im Plus, höchstens ${pct(R.MAX_DRAWDOWN, 0, false)} Rückgang, kein einzelner Glückstreffer und Haltedauer lang genug zum Kopieren. Die Auswahl wird täglich neu berechnet.</p>
    <div class="card flach"><div class="tw" style="margin:0;padding:0"><table class="tbl"><thead><tr><th class="l">Trader</th><th>Note ${tippI("0–100, relativ zum besten ausgewählten Trader. Mischt Gewinnmonate, Rendite, Rückgang und Trefferquote.")}</th><th>Konto</th><th>Gewinn gesamt</th><th>Rendite</th><th>Gewinnmonate</th><th>Max. Rückgang</th><th>Haltedauer ${tippI("Median der abgeschlossenen Runden im letzten Monat.")}</th><th>Treffer 30 T.</th><th class="l">Positionen jetzt</th><th>Spiegel ${tippI("Anteil am Spiegel-Portfolio und dessen Ergebnis für diesen Trader.")}</th><th>Kopie-Test ${tippI("Was es gebracht hätte, jede neue Position dieses Traders mit " + usd(R.EINZEL_NOTIONAL) + " zu kopieren – mit unserer Verzögerung.")}</th></tr></thead><tbody>
    ${zeilen.map(t => `<tr class="klick" data-trader="${esc(t.adresse)}"><td class="l"><span class="tick">${tName(t.adresse)}</span><div class="firma">${esc(t.tage)} Tage aktiv</div></td>
      <td><span class="note">${t.note ?? "–"}</span></td><td>${kurz(t.konto_jetzt ?? t.konto)}</td><td class="pos">${kurz(t.pnl_gesamt)}</td><td>${pct(t.roi_gesamt, 0)}</td>
      <td>${pct(t.monate_pos, 0, false)} <span class="klein mute">von ${t.monate}</span></td><td class="neg">${pct(-(t.drawdown || 0), 0)}</td><td>${ok(t.haltedauer_std) ? dauer(t.haltedauer_std * 3.6e6) : "–"}</td>
      <td>${pct(t.trefferquote, 0, false)}</td>
      <td class="l">${t.pos.length ? t.pos.slice(0, 4).map(p => `<span class="pchip ${p.r > 0 ? "long" : "short"}">${esc(p.coin)}</span>`).join("") + (t.pos.length > 4 ? `<span class="klein mute"> +${t.pos.length - 4}</span>` : "") : '<span class="mute klein">keine</span>'}</td>
      <td class="${kl(t.spiegel && (t.spiegel.realisiert + t.spiegel.offen_erg))}">${t.spiegel ? pct(t.spiegel.gewicht, 1, false) + `<div class="firma">${usdVz(t.spiegel.realisiert + t.spiegel.offen_erg)}</div>` : "–"}</td>
      <td class="${kl(t.kopie && (t.kopie.ergebnis + t.kopie.offen_erg))}">${t.kopie && (t.kopie.anzahl || t.kopie.offen) ? usdVz(t.kopie.ergebnis + t.kopie.offen_erg) + `<div class="firma">${t.kopie.anzahl} fertig · ${t.kopie.offen} offen</div>` : '<span class="mute klein">noch nichts</span>'}</td></tr>`).join("")}
    </tbody></table></div></div>`;
  },

  bewegungen(el) {
    el.innerHTML = `<p class="erkl">Was die beobachteten Trader zwischen zwei Prüfungen getan haben. Positionen unter ${pct(R.MIN_POS_ANTEIL, 0, false)} ihres Kontos oder ${usd(R.MIN_POS_USD)} werden ignoriert.</p>
    <div class="card">${D.bewegungen.length ? `<div class="tw"><table class="tbl karten"><thead><tr><th class="l">Zeit</th><th class="l">Trader</th><th class="l">Aktion</th><th class="l">Coin</th><th class="l">Richtung</th><th>Größe</th></tr></thead><tbody>
    ${D.bewegungen.map(b => `<tr><td class="l mute">${esc(zeit(b.zeit))}</td><td class="l">${tLink(b.a)}</td><td class="l"><span class="akt ${b.art === "geschlossen" ? "zu" : "auf"}">${esc(b.art)}</span></td><td class="l tick">${esc(b.coin)}</td><td class="l">${richt(b.r)}</td><td class="m-r">${kurz(b.wert)}</td></tr>`).join("")}
    </tbody></table></div>` : `<div class="leer">Noch keine Bewegungen erfasst – ab dem zweiten Lauf erscheinen hier neue und geschlossene Positionen.</div>`}</div>`;
  },

  kopie(el) {
    const st = D.trader.map(t => t.kopie).filter(k => k);
    const n = st.reduce((s, k) => s + k.anzahl, 0), erg = st.reduce((s, k) => s + k.ergebnis, 0), offen = st.reduce((s, k) => s + k.offen_erg, 0);
    const verz = D.kopien.concat().filter(k => ok(k.verz)).map(k => k.verz);
    const verzD = verz.length ? verz.reduce((a, b) => a + b, 0) / verz.length : null;
    const treffer = D.kopien.length ? D.kopien.filter(k => k.ergebnis > 0).length / D.kopien.length : null;
    el.innerHTML = `<p class="erkl">Zweiter, strengerer Test: Jede <b>neue</b> Position eines Traders wird sofort beim nächsten Lauf mit ${usd(R.EINZEL_NOTIONAL)} kopiert und geschlossen, wenn er schließt. So sieht man, ob einzelne Trader trotz Verzögerung kopierbar sind – und wie viel schlechter unser Einstiegspreis ist als seiner.</p>
    <div class="kpis">
      <div class="kpi"><div class="k">Kopien abgeschlossen</div><div class="v">${zahl(n)}</div><div class="n">${treffer !== null ? pct(treffer, 0, false) + " im Plus" : "noch keine"}</div></div>
      <div class="kpi"><div class="k">Ergebnis abgeschlossen</div><div class="v ${kl(erg)}">${usdVz(erg)}</div><div class="n">nach Gebühren und Slippage</div></div>
      <div class="kpi"><div class="k">Offene Kopien</div><div class="v ${kl(offen)}">${usdVz(offen)}</div><div class="n">aktueller Buchwert</div></div>
      <div class="kpi"><div class="k">Verzögerungskosten ${tippI("Wie viel schlechter unser Einstieg im Schnitt war als der Einstiegspreis des Traders. Das ist der Preis dafür, dass wir erst nach ihm handeln.")}</div><div class="v ${verzD > 0 ? "neg" : verzD < 0 ? "pos" : ""}">${ok(verzD) ? pct(verzD, 2, false) : "–"}</div><div class="n">je Kopie im Schnitt</div></div>
    </div>
    <div class="card">${D.kopien.length ? `<div class="tw"><table class="tbl karten"><thead><tr><th class="l">Geschlossen</th><th class="l">Trader</th><th class="l">Coin</th><th class="l">Richtung</th><th>Einstieg</th><th>Ausstieg</th><th>Dauer</th><th>Verzögerung</th><th>Ergebnis</th></tr></thead><tbody>
      ${D.kopien.map(k => `<tr><td class="l mute">${esc(zeit(k.zeit_aus))}</td><td class="l">${tLink(k.a)}</td><td class="l tick">${esc(k.coin)}</td><td class="l">${richt(k.r)}</td><td>${preis(k.ein)}</td><td>${preis(k.aus)}</td><td>${dauer(k.zeit_aus - k.zeit_ein)}</td><td class="${ok(k.verz) && k.verz > 0 ? "neg" : ""}">${ok(k.verz) ? pct(k.verz, 2, false) : "–"}</td><td class="m-r ${kl(k.ergebnis)}">${usdVz(k.ergebnis, 2)}</td></tr>`).join("")}
    </tbody></table></div>` : `<div class="leer">Noch keine abgeschlossene Kopie. Bestehende Positionen werden bewusst nicht kopiert, weil ihr Einstiegszeitpunkt unbekannt ist – nur neue.</div>`}</div>`;
  },

  trades(el) {
    el.innerHTML = `<div class="card">${zu.length ? `<div class="tw"><table class="tbl karten"><thead><tr><th class="l">Geschlossen</th><th class="l">Coin</th><th class="l">Richtung</th><th>Einstieg</th><th>Ausstieg</th><th>Dauer</th><th>Trader</th><th class="l">Grund</th><th>Ergebnis</th></tr></thead><tbody>
      ${zu.map(t => `<tr><td class="l mute">${esc(zeit(t.zeit_aus))}</td><td class="l tick">${esc(t.coin)}</td><td class="l">${richt(t.r)}</td><td>${preis(t.ein)}</td><td>${preis(t.aus)}</td><td>${dauer(t.zeit_aus - t.zeit_ein)}</td><td>${t.trader_ein || "–"}</td><td class="l mute klein">${esc(t.grund)}</td><td class="m-r ${kl(t.ergebnis)}">${usdVz(t.ergebnis, 2)} <span class="klein">(${pct(t.pct)})</span></td></tr>`).join("")}
    </tbody></table></div>` : `<div class="leer">Noch kein abgeschlossener Papier-Trade.</div>`}</div>`;
  },

  methode(el) {
    const A = D.auswahl || {};
    el.innerHTML = `<div class="grid">
      <div class="card c6"><h3 class="ct">So funktioniert der Test</h3>
        <ol class="gedanken" style="margin-top:14px">
          <li><b>Auswahl (täglich neu):</b> Neue Trader, die alle Regeln erfüllen, kommen dazu; wer sie nicht mehr erfüllt, scheidet aus. Aus allen ${zahl(A.konten)} Konten der Hyperliquid-Rangliste fallen Hochfrequenz-Bots, kleine und inaktive Konten weg (${zahl(A.vorfilter)} übrig). Die besten ${zahl(A.geprueft)} werden genau geprüft, ${zahl(A.bestanden)} bestehen alle Regeln, die ${zahl(A.ausgewaehlt)} beständigsten werden beobachtet.</li>
          <li><b>Beobachten (alle 15 Min.):</b> Alle offenen Positionen der Trader, die mindestens ${pct(R.MIN_POS_ANTEIL, 0, false)} ihres Kontos ausmachen.</li>
          <li><b>Konsens:</b> Halten mindestens ${R.KONSENS_MIN_TRADER} Trader einen Coin und zeigen mindestens ${pct(R.KONSENS_MIN_ANTEIL, 0, false)} in dieselbe Richtung, eröffnet das Papier-Portfolio eine Position (${pct(R.POS_ANTEIL, 0, false)} des Kapitals, ohne Hebel).</li>
          <li><b>Ausstieg:</b> Wenn weniger als ${R.KONSENS_AUS_TRADER} Trader übrig sind oder die Einigkeit unter ${pct(R.KONSENS_AUS_ANTEIL, 0, false)} fällt.</li>
          <li><b>Spiegel-Portfolio:</b> ${usd(R.SPIEGEL_KAPITAL)} nach Note verteilt; jede Position ab ${pct(R.MIN_POS_SPIEGEL_ANTEIL, 0, false)} des Trader-Kontos wird anteilig gespiegelt, Hebel wird herausgerechnet. Größen werden nachgezogen, wenn sie mehr als ${pct(R.SPIEGEL_ANPASSEN_AB, 0, false)} abweichen.</li>
          <li><b>Ehrliche Kosten:</b> ${pct(R.GEBUEHR, 3, false)} Gebühr und ${pct(R.SLIPPAGE, 2, false)} Slippage je Ein- und Ausstieg, stündliches Funding.</li>
        </ol></div>
      <div class="card c6"><h3 class="ct">Worauf du achten solltest</h3>
        <ul class="gruende warnliste">
          <li>Vergangener Erfolg der Trader sagt wenig über die Zukunft. Genau das prüft dieser Test.</li>
          <li>Öffentliche Positionen können Täuschung sein: Ein Wal kann hier long sein und woanders absichern. Der Konsens mehrerer Trader soll das abfedern.</li>
          <li>Erst nach 4–8 Wochen und mindestens 20–30 abgeschlossenen Trades ist das Ergebnis mehr als Zufall.</li>
          <li>Vor echtem Geld: klären, ob Hyperliquid für dich in Deutschland rechtlich in Ordnung ist, und ohne Hebel starten.</li>
        </ul>
        <div class="fakten" style="margin-top:16px">
          <div><span>Letzte Auswahl</span><b>${esc(zeit(A.zeit))}</b></div><div><span>Dauer</span><b>${zahl(A.dauer_s)} s</b></div>
          <div><span>Min. Konto</span><b>${kurz(R.MIN_KONTO_USD)}</b></div><div><span>Min. Haltedauer</span><b>${R.MIN_HALTEDAUER_STD} Std.</b></div>
        </div></div>
    </div>
    <div class="card" style="margin-bottom:16px"><div class="ch"><div><h3 class="ct">Knapp gescheitert</h3><div class="cs">Große Gewinner, die nicht beobachtet werden – und warum</div></div></div>
      ${D.abgelehnt.length ? `<div class="tw"><table class="tbl"><thead><tr><th class="l">Trader</th><th>Gewinn gesamt</th><th>Rendite</th><th>Gewinnmonate</th><th>Rückgang</th><th class="l">Grund</th></tr></thead><tbody>
      ${D.abgelehnt.map(t => `<tr><td class="l"><a href="${scan(t.adresse)}" target="_blank" rel="noopener">${t.name ? esc(t.name) : kurzAdr(t.adresse)}</a></td><td>${kurz(t.pnl_gesamt)}</td><td>${pct(t.roi_gesamt, 0)}</td><td>${pct(t.monate_pos, 0, false)}</td><td>${pct(-(t.drawdown || 0), 0)}</td><td class="l wrap klein">${esc((t.gruende || []).join(", "))}</td></tr>`).join("")}
      </tbody></table></div>` : `<div class="leer">–</div>`}</div>
    <div class="card"><h3 class="ct">Protokoll</h3><ul class="liste" style="margin-top:8px">${D.protokoll.length ? D.protokoll.map(p => `<li><span class="mute klein">${esc(zeit(p.zeit))}</span> · ${esc(p.text)}</li>`).join("") : '<li class="mute">Keine Meldungen.</li>'}</ul></div>`;
  },
};

/* ---------- Trader-Detail ---------- */
function traderDetail(a) {
  const t = TR[a]; if (!t) return;
  $("#m-kopf").innerHTML = `<div class="lbl">Trader</div><div class="gross-tick" style="font-size:26px">${tName(a)}</div><a class="klein" href="${scan(a)}" target="_blank" rel="noopener">${esc(a)} ↗</a>`;
  const k = t.kopie || {};
  $("#m-inhalt").innerHTML = `<div class="kpis">
    <div class="kpi"><div class="k">Note</div><div class="v">${t.note ?? "–"}</div><div class="n">von 100</div></div>
    <div class="kpi"><div class="k">Konto</div><div class="v">${kurz(t.konto_jetzt ?? t.konto)}</div><div class="n">${esc(t.tage)} Tage Historie</div></div>
    <div class="kpi"><div class="k">Gewinn gesamt</div><div class="v pos">${kurz(t.pnl_gesamt)}</div><div class="n">Rendite ${pct(t.roi_gesamt, 0)}</div></div>
    <div class="kpi"><div class="k">Letzte 30 Tage</div><div class="v ${kl(t.pnl_monat)}">${kurz(t.pnl_monat)}</div><div class="n">Woche ${kurz(t.pnl_woche)}</div></div>
    <div class="kpi"><div class="k">Kopie-Test</div><div class="v ${kl((k.ergebnis || 0) + (k.offen_erg || 0))}">${k.anzahl || k.offen ? usdVz((k.ergebnis || 0) + (k.offen_erg || 0)) : "–"}</div><div class="n">${k.anzahl || 0} fertig · Verzögerung ${ok(k.verz) ? pct(k.verz, 2, false) : "–"}</div></div>
  </div>
  <div class="fakten" style="margin-bottom:18px">
    <div><span>Gewinnmonate</span><b>${pct(t.monate_pos, 0, false)} von ${t.monate}</b></div><div><span>Max. Rückgang</span><b>${pct(-(t.drawdown || 0), 0)}</b></div>
    <div><span>Trades 30 T.</span><b>${zahl(t.schliessungen)}</b></div><div><span>Trefferquote</span><b>${pct(t.trefferquote, 0, false)}</b></div>
    <div><span>Größter Trade</span><b>${pct(t.top_anteil, 0, false)} des Gewinns</b></div><div><span>Haltedauer</span><b>${ok(t.haltedauer_std) ? dauer(t.haltedauer_std * 3.6e6) : "–"}</b></div>
  </div>
  <h3 class="ct" style="margin-bottom:8px">Offene Positionen</h3>
  ${t.pos.length ? `<div class="tw"><table class="tbl"><thead><tr><th class="l">Coin</th><th class="l">Richtung</th><th>Größe</th><th>Einstieg</th><th>Aktuell</th><th>Hebel</th><th>Buchgewinn</th></tr></thead><tbody>
    ${t.pos.map(p => `<tr><td class="l tick">${esc(p.coin)}</td><td class="l">${richt(p.r)}</td><td>${kurz(p.wert)}</td><td>${preis(p.einstieg)}</td><td>${preis(D.preise[p.coin])}</td><td>${p.hebel ? p.hebel + "×" : "–"}</td><td class="${kl(p.upnl)}">${usdVz(p.upnl)}</td></tr>`).join("")}
  </tbody></table></div>` : '<div class="leer">Gerade keine nennenswerte Position.</div>'}
  <h3 class="ct" style="margin:18px 0 8px">Letzte Bewegungen</h3>
  <ul class="liste">${D.bewegungen.filter(b => b.a === a).slice(0, 15).map(b => `<li><span class="mute klein">${esc(zeit(b.zeit))}</span> · <span class="akt ${b.art === "geschlossen" ? "zu" : "auf"}">${esc(b.art)}</span> ${richt(b.r)} <b>${esc(b.coin)}</b> · ${kurz(b.wert)}</li>`).join("") || '<li class="mute">Noch keine erfasst.</li>'}</ul>`;
  $(".modal").classList.add("offen");
}
document.addEventListener("click", ev => {
  const tr = ev.target.closest("[data-trader]");
  if (tr) { traderDetail(tr.dataset.trader); return; }
  if (ev.target.closest(".schliessen") || ev.target.classList.contains("modal")) $(".modal").classList.remove("offen");
});
document.addEventListener("keydown", ev => { if (ev.key === "Escape") $(".modal").classList.remove("offen"); });

const start = (location.hash || "").slice(1);
zeigeTab(RENDER[start] ? start : "uebersicht");
})();
