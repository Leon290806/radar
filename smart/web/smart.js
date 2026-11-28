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

/* ---------- Kopf ---------- */
const tabs = [["uebersicht", "Übersicht", null], ["trader", "Trader", D.trader.length], ["bewegungen", "Bewegungen", D.bewegungen.length || null],
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
    const xt = [0, Math.floor((x.length - 1) / 2), x.length - 1];
    const kurzZeit = x[x.length - 1] - x[0] < 2 * 864e5;
    const xl = i => kurzZeit ? new Date(x[i]).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) : datum(x[i]);
    (x.length > 2 ? xt : [0, x.length - 1]).forEach((i, j, arr) => { svg += `<text x="${X(i)}" y="${H - 6}" font-size="11" fill="${cssv("--ink3")}" text-anchor="${j === 0 ? "start" : j === arr.length - 1 ? "end" : "middle"}">${esc(xl(i))}</text>`; });
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
    const vergleich = ok(btcR) ? (rendite - btcR) : null;
    el.innerHTML = `
    <div class="h-held">
      <div><div class="h-datum">Papier-Test seit ${esc(datum(P.start))} · ${zahl(tage, tage < 10 ? 1 : 0)} Tage</div>
        <h2 class="h-titel">Hätte man mit Smart Money Geld verdient?</h2>
        <p class="h-unter">Der Radar beobachtet ${D.trader.length} beständige Top-Trader auf Hyperliquid. Halten mehrere dieselbe Richtung, „kauft“ das Papier-Portfolio – mit echten Preisen, Gebühren, Slippage und Funding, aber ohne echtes Geld.</p></div>
      <div class="h-kpis">
        <div><span>Papier-Portfolio</span><b class="${kl(rendite)}">${pct(rendite)}</b><small>${usd(P.wert)} von ${usd(P.start_kapital)}</small></div>
        <div><span>Bitcoin halten</span><b class="${kl(btcR)}">${pct(btcR)}</b><small>${ok(vergleich) ? (vergleich >= 0 ? "Test liegt vorn: " : "Test liegt hinten: ") + pct(vergleich) : "Vergleich ab dem 2. Messpunkt"}</small></div>
        <div><span>Signale jetzt</span><b>${signale}<i> / ${P.pos.length} offen</i></b><small>${zu.length} abgeschlossen · ${zu.length ? pct(gewinnTrades / zu.length, 0, false) + " im Plus" : "noch keine"}</small></div>
      </div>
    </div>
    ${tage < 28 ? `<div class="box warn" style="margin-bottom:16px">Der Test läuft erst ${zahl(tage, tage < 10 ? 1 : 0)} Tage. Aussagekräftig wird das Ergebnis frühestens nach 4–8 Wochen – vorher ist alles Zufall. Bitte kein echtes Geld darauf setzen.</div>` : ""}
    <div class="grid">
      <div class="card c8"><div class="ch"><div><h3 class="ct">Papier-Portfolio gegen Bitcoin</h3><div class="cs">Startkapital ${usd(P.start_kapital)} · ohne Hebel · je Position ${pct(R.POS_ANTEIL, 0, false)}</div></div>
        <div class="legende"><span><i style="background:var(--s1)"></i>Smart-Money-Test</span><span><i style="background:var(--s4)"></i>Bitcoin halten</span></div></div>
        <div class="chart" id="ch-verlauf"></div></div>
      <div class="card c4"><div class="ch"><div><h3 class="ct">Kosten bisher</h3><div class="cs">Simuliert, so wie sie echt anfallen würden</div></div></div>
        <ul class="schritte" style="margin-top:0">
          <li><span>Gebühren ${tippI("Taker-Gebühr " + pct(R.GEBUEHR, 3, false) + " je Ein- und Ausstieg.")}</span><span>${usd(-P.gebuehren, 2)}</span></li>
          <li><span>Funding ${tippI("Bei Perps zahlen Longs (oder Shorts) stündlich eine Gebühr an die Gegenseite. Positiv = erhalten.")}</span><span class="${kl(P.funding)}">${usdVz(P.funding, 2)}</span></li>
          <li><span>Slippage je Trade ${tippI("Annahme: Wir bekommen " + pct(R.SLIPPAGE, 2, false) + " schlechtere Preise als der Mittelkurs.")}</span><span>${pct(R.SLIPPAGE, 2, false)}</span></li>
          <li><span>Freies Kapital</span><span>${usd(P.cash)}</span></li>
        </ul>
        <p class="klein mute" style="margin:12px 0 0">Push aufs Handy bei jedem Papier-Kauf und -Verkauf.</p></div>
    </div>
    <div class="card" style="margin-bottom:16px"><div class="ch"><div><h3 class="ct">Offene Papier-Positionen</h3><div class="cs">Werden geschlossen, sobald weniger als ${R.KONSENS_AUS_TRADER} Trader übrig sind oder die Einigkeit unter ${pct(R.KONSENS_AUS_ANTEIL, 0, false)} fällt</div></div></div>${posTabelle(P.pos)}</div>
    <div class="card"><div class="ch"><div><h3 class="ct">Was die Top-Trader gerade halten</h3><div class="cs">Coins, in denen mindestens 2 der beobachteten Trader eine nennenswerte Position haben</div></div></div>${konsensTabelle(D.konsens)}</div>`;
    linie($("#ch-verlauf", el), V.map(v => v[0]), [{ name: "Smart-Money-Test", farbe: "--s1", v: V.map(v => v[1]), breite: 2.4 }, { name: "Bitcoin halten", farbe: "--s4", v: V.map(v => v[2]), strich: true }], v => usd(v));
  },

  trader(el) {
    const zeilen = D.trader.slice().sort((a, b) => (b.note || 0) - (a.note || 0));
    el.innerHTML = `<p class="erkl">Ausgewählt nach Beständigkeit, nicht nach dem größten Gewinn: mindestens ${R.MIN_TAGE_HISTORIE} Tage Historie, in mindestens ${pct(R.MIN_MONATE_POSITIV, 0, false)} der Monate im Plus, höchstens ${pct(R.MAX_DRAWDOWN, 0, false)} Rückgang, kein einzelner Glückstreffer und Haltedauer lang genug zum Kopieren. Die Auswahl wird täglich neu berechnet.</p>
    <div class="card flach"><div class="tw" style="margin:0;padding:0"><table class="tbl"><thead><tr><th class="l">Trader</th><th>Note ${tippI("0–100, relativ zum besten ausgewählten Trader. Mischt Gewinnmonate, Rendite, Rückgang und Trefferquote.")}</th><th>Konto</th><th>Gewinn gesamt</th><th>Rendite</th><th>Gewinnmonate</th><th>Max. Rückgang</th><th>Haltedauer ${tippI("Median der abgeschlossenen Runden im letzten Monat.")}</th><th>Treffer 30 T.</th><th class="l">Positionen jetzt</th><th>Kopie-Test ${tippI("Was es gebracht hätte, jede neue Position dieses Traders mit " + usd(R.EINZEL_NOTIONAL) + " zu kopieren – mit unserer Verzögerung.")}</th></tr></thead><tbody>
    ${zeilen.map(t => `<tr class="klick" data-trader="${esc(t.adresse)}"><td class="l"><span class="tick">${tName(t.adresse)}</span><div class="firma">${esc(t.tage)} Tage aktiv</div></td>
      <td><span class="note">${t.note ?? "–"}</span></td><td>${kurz(t.konto_jetzt ?? t.konto)}</td><td class="pos">${kurz(t.pnl_gesamt)}</td><td>${pct(t.roi_gesamt, 0)}</td>
      <td>${pct(t.monate_pos, 0, false)} <span class="klein mute">von ${t.monate}</span></td><td class="neg">${pct(-(t.drawdown || 0), 0)}</td><td>${ok(t.haltedauer_std) ? dauer(t.haltedauer_std * 3.6e6) : "–"}</td>
      <td>${pct(t.trefferquote, 0, false)}</td>
      <td class="l">${t.pos.length ? t.pos.slice(0, 4).map(p => `<span class="pchip ${p.r > 0 ? "long" : "short"}">${esc(p.coin)}</span>`).join("") + (t.pos.length > 4 ? `<span class="klein mute"> +${t.pos.length - 4}</span>` : "") : '<span class="mute klein">keine</span>'}</td>
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
          <li><b>Auswahl (täglich):</b> Aus allen ${zahl(A.konten)} Konten der Hyperliquid-Rangliste fallen Hochfrequenz-Bots, kleine und inaktive Konten weg (${zahl(A.vorfilter)} übrig). Die besten ${zahl(A.geprueft)} werden genau geprüft, ${zahl(A.bestanden)} bestehen alle Regeln, die ${zahl(A.ausgewaehlt)} beständigsten werden beobachtet.</li>
          <li><b>Beobachten (alle 15 Min.):</b> Alle offenen Positionen der Trader, die mindestens ${pct(R.MIN_POS_ANTEIL, 0, false)} ihres Kontos ausmachen.</li>
          <li><b>Konsens:</b> Halten mindestens ${R.KONSENS_MIN_TRADER} Trader einen Coin und zeigen mindestens ${pct(R.KONSENS_MIN_ANTEIL, 0, false)} in dieselbe Richtung, eröffnet das Papier-Portfolio eine Position (${pct(R.POS_ANTEIL, 0, false)} des Kapitals, ohne Hebel).</li>
          <li><b>Ausstieg:</b> Wenn weniger als ${R.KONSENS_AUS_TRADER} Trader übrig sind oder die Einigkeit unter ${pct(R.KONSENS_AUS_ANTEIL, 0, false)} fällt.</li>
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
