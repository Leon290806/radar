(function () {
"use strict";
const D = JSON.parse(document.getElementById("daten").textContent);
const $ = (s, el) => (el || document).querySelector(s);
const $$ = (s, el) => Array.from((el || document).querySelectorAll(s));
const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const ok = x => x !== null && x !== undefined && isFinite(x);
const zahl = (x, nk = 0) => ok(x) ? Number(x).toLocaleString("de-DE", { minimumFractionDigits: nk, maximumFractionDigits: nk }) : "–";
const usd = (x, nk = 0) => ok(x) ? zahl(x, nk) + " $" : "–";
const kurzUsd = x => !ok(x) ? "–" : x >= 1e6 ? zahl(x / 1e6, 2) + " Mio. $" : x >= 1e4 ? zahl(x / 1e3, 1) + " Tsd. $" : x >= 100 ? zahl(x, 0) + " $" : zahl(x, 2) + " $";
const pct = (x, nk = 0, vz = true) => ok(x) ? (vz && x > 0 ? "+" : "") + zahl(x * 100, nk) + " %" : "–";
const kl = x => !ok(x) || Math.abs(x) < 1e-9 ? "" : (x > 0 ? "pos" : "neg");
const datum = s => { if (!s) return "–"; const [y, m, d] = s.split("-"); return `${d}.${m}.${y}`; };
const zeit = ms => ms ? new Date(ms).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "–";
const tippI = txt => `<span class="tipp" tabindex="0" data-tipp="${esc(txt)}">?</span>`;
try { const t = JSON.parse(localStorage.getItem("radar_thema") || "null"); if (t) document.documentElement.dataset.theme = t; } catch (e) { }
const cssv = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();

const ZF = { "Strong Buy": "--zsb", "Akkumulieren": "--zak", "Halten": "--zha", "Reduzieren": "--zre", "Strong Sell": "--zss" };
const zoneVon = s => { if (!ok(s)) return null; for (const [g, n] of D.zonen_def) if (s >= g) return n; return "Strong Sell"; };
const zTag = z => z ? `<span class="ztag" style="--zf:var(${ZF[z]})">${esc(z)}</span>` : "–";
const S = D.serien, K = D.kennzahlen, ZS = {}; D.zonen.forEach(z => ZS[z.zone] = z);
const zst = ZS[D.zone] || {};
const plAbw = D.preis / D.pl.fair - 1;

/* ---------- Kopf ---------- */
const tabs = [["uebersicht", "Übersicht"], ["bewertung", "Bewertung"], ["onchain", "On-Chain"], ["zyklus", "Zyklus"], ["stimmung", "Stimmung"], ["gelernt", "Gelernt & Backtest"], ["methode", "Methode"]];
document.body.innerHTML = `
<header class="kopf"><div class="in">
  <div class="zeile1">
    <div class="marke"><div class="logo"><svg viewBox="0 0 24 24" fill="none" style="stroke:var(--card)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 5h6a3 3 0 0 1 0 6H8zM8 11h7a3 3 0 0 1 0 6H8zM8 5v12M10 3v2M13 3v2M10 17v2M13 17v2"/></svg></div>
      <div>${window.radarMenue ? radarMenue("bitcoin", "Bitcoin-Radar") : "<h1>Bitcoin-Radar</h1>"}<div class="stand">Daten bis ${esc(datum(D.datum))}<span class="lang"> · aktualisiert ${esc(zeit(D.stand))} · täglich</span></div></div></div>
    <div class="rechts">
      <span class="pill">${zTag(D.zone)}<b style="margin-left:2px">${zahl(D.score)}</b></span>
      <button class="ikon" id="thema" aria-label="Hell/Dunkel"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg></button>
    </div>
  </div>
  <nav class="tabs">${tabs.map(([k, t], i) => `<button data-tab="${k}" class="${i === 0 ? "aktiv" : ""}">${t}</button>`).join("")}</nav>
</div></header>
<main>${tabs.map(([k], i) => `<section class="tab${i === 0 ? " aktiv" : ""}" id="t-${k}"></section>`).join("")}</main>`;
$("#thema").addEventListener("click", () => {
  const dunkel = document.documentElement.dataset.theme ? document.documentElement.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  const neu = dunkel ? "light" : "dark"; document.documentElement.dataset.theme = neu;
  try { localStorage.setItem("radar_thema", JSON.stringify(neu)); } catch (e) { }
  zeichne();
});
const gerendert = {};
function zeigeTab(k) {
  $$("nav.tabs button").forEach(b => b.classList.toggle("aktiv", b.dataset.tab === k));
  $$("section.tab").forEach(s => s.classList.toggle("aktiv", s.id === "t-" + k));
  if (!gerendert[k]) { gerendert[k] = true; RENDER[k]($("#t-" + k)); }
  try { history.replaceState(null, "", "#" + k); } catch (e) { }
  zeichne();
}
$$("nav.tabs button").forEach(b => b.addEventListener("click", () => zeigeTab(b.dataset.tab)));

/* ---------- Charts ---------- */
const CH = [];
function zeichne() { CH.forEach(f => f()); }
window.addEventListener("resize", () => { clearTimeout(window._rz); window._rz = setTimeout(zeichne, 150); });
const ms = s => typeof s === "number" ? s : Date.parse(s + "T00:00:00Z");
function logTicks(lo, hi) {
  const out = []; for (let e = Math.floor(Math.log10(lo)); e <= Math.ceil(Math.log10(hi)); e++) [1, 2, 5].forEach(m => { const v = m * 10 ** e; if (v >= lo && v <= hi) out.push(v); });
  return out.length > 7 ? out.filter(v => /^1/.test(String(v))) : out;
}
function linTicks(lo, hi, n = 4) { const r = hi - lo || 1, roh = r / n, p = 10 ** Math.floor(Math.log10(roh)); const s = [1, 2, 2.5, 5, 10].map(x => x * p).find(x => r / x <= n) || 10 * p; const out = []; for (let v = Math.ceil(lo / s) * s; v <= hi + 1e-9; v += s) out.push(+v.toFixed(10)); return out; }
/* cfg: x[], serien[{name,farbe,v,breite,strich,flaeche}], log, fmt, xfmt, hoehe, baender[{von,bis,farbe}], hlinien[{v,txt,farbe}], vlinien[{x,txt}], ymin, ymax */
function chart(host, cfg) {
  CH.push(() => {
    if (!host.isConnected || !host.offsetParent) return;
    const W = host.clientWidth || 600, H = cfg.hoehe || 300, pl = 4, pr = 64, pt = 12, pb = 24;
    const xs = cfg.x.map(ms), n = xs.length;
    const L = v => cfg.log ? Math.log10(v) : v;
    let alle = []; cfg.serien.forEach(s => s.v.forEach(v => { if (ok(v) && (!cfg.log || v > 0)) alle.push(v); }));
    (cfg.hlinien || []).forEach(h => alle.push(h.v));
    if (!alle.length) { host.innerHTML = '<div class="leer">Keine Daten</div>'; return; }
    let lo = cfg.ymin ?? Math.min(...alle), hi = cfg.ymax ?? Math.max(...alle);
    if (cfg.log) { lo = lo / 1.15; hi = hi * 1.15; } else { const p = (hi - lo) * 0.06 || 1; if (cfg.ymin == null) lo -= p; if (cfg.ymax == null) hi += p; }
    const x0 = xs[0], x1 = xs[n - 1];
    const X = t => pl + (W - pl - pr) * (t - x0) / ((x1 - x0) || 1);
    const Y = v => pt + (H - pt - pb) * (1 - (L(v) - L(lo)) / ((L(hi) - L(lo)) || 1));
    const fmt = cfg.fmt || (v => zahl(v, 2));
    let svg = `<svg width="${W}" height="${H}">`;
    (cfg.baender || []).forEach(b => { const a = X(ms(b.von)), e = X(ms(b.bis)); if (e > a) svg += `<rect x="${a}" y="${pt}" width="${e - a}" height="${H - pt - pb}" fill="${cssv(b.farbe)}" opacity="${b.deck || 0.13}"/>`; });
    (cfg.log ? logTicks(lo, hi) : linTicks(lo, hi)).forEach(t => { svg += `<line x1="${pl}" x2="${W - pr}" y1="${Y(t)}" y2="${Y(t)}" stroke="${cssv("--line2")}"/><text x="${W - pr + 8}" y="${Y(t) + 4}" font-size="11" fill="${cssv("--ink3")}">${esc(fmt(t))}</text>`; });
    (cfg.hlinien || []).forEach(h => { svg += `<line x1="${pl}" x2="${W - pr}" y1="${Y(h.v)}" y2="${Y(h.v)}" stroke="${cssv(h.farbe || "--ink3")}" stroke-dasharray="4 4"/>${h.txt ? `<text x="${pl + 4}" y="${Y(h.v) - 4}" font-size="11" fill="${cssv(h.farbe || "--ink3")}">${esc(h.txt)}</text>` : ""}`; });
    const kurzSpanne = x1 - x0 < 6 * 365 * 864e5;
    const xfmt = cfg.xfmt || (t => { const d = new Date(t); return kurzSpanne ? String(d.getUTCMonth() + 1).padStart(2, "0") + "/" + String(d.getUTCFullYear()).slice(2) : d.getUTCFullYear(); });
    const nt = Math.max(2, Math.min(8, Math.floor(W / 90)));
    for (let k = 0; k < nt; k++) { const t = x0 + (x1 - x0) * k / (nt - 1); svg += `<text x="${X(t)}" y="${H - 6}" font-size="11" fill="${cssv("--ink3")}" text-anchor="${k === 0 ? "start" : k === nt - 1 ? "end" : "middle"}">${esc(xfmt(t))}</text>`; }
    cfg.serien.forEach(s => {
      let d = "", an = false;
      s.v.forEach((v, i) => { if (!ok(v) || (cfg.log && v <= 0)) { an = false; return; } d += (an ? "L" : "M") + X(xs[i]).toFixed(1) + " " + Y(v).toFixed(1); an = true; });
      svg += `<path d="${d}" fill="none" stroke="${cssv(s.farbe)}" stroke-width="${s.breite || 1.8}" ${s.strich ? 'stroke-dasharray="5 4"' : ""} stroke-linejoin="round" opacity="${s.deck || 1}"/>`;
    });
    (cfg.vlinien || []).forEach(v => { svg += `<line x1="${X(ms(v.x))}" x2="${X(ms(v.x))}" y1="${pt}" y2="${H - pb}" stroke="${cssv(v.farbe || "--ink")}" stroke-width="1.5"/>${v.txt ? `<text x="${X(ms(v.x)) - 4}" y="${pt + 12}" font-size="11" font-weight="600" text-anchor="end" fill="${cssv(v.farbe || "--ink")}">${esc(v.txt)}</text>` : ""}`; });
    svg += `<line class="hl" x1="0" x2="0" y1="${pt}" y2="${H - pb}" stroke="${cssv("--ink3")}" stroke-dasharray="3 3" style="display:none"/></svg>`;
    host.innerHTML = svg + '<div class="tip"></div>';
    const tip = $(".tip", host), hl = $(".hl", host), el = $("svg", host);
    el.addEventListener("mousemove", ev => {
      const r = el.getBoundingClientRect(), mx = ev.clientX - r.left;
      let b = 0, bd = 1e18; xs.forEach((t, i) => { const d = Math.abs(X(t) - mx); if (d < bd) { bd = d; b = i; } });
      hl.setAttribute("x1", X(xs[b])); hl.setAttribute("x2", X(xs[b])); hl.style.display = "";
      tip.innerHTML = `<div class="tk">${esc(cfg.tipx ? cfg.tipx(cfg.x[b]) : datum(cfg.x[b]))}</div>` + cfg.serien.filter(s => ok(s.v[b])).map(s => `<div class="tz"><span><i style="background:var(${s.farbe})"></i>${esc(s.name)}</span><b>${esc((s.fmt || fmt)(s.v[b]))}</b></div>`).join("") + (cfg.tipextra ? cfg.tipextra(b) : "");
      tip.style.display = "block"; tip.style.left = Math.min(Math.max(0, X(xs[b]) + 12), W - 200) + "px"; tip.style.top = "8px";
    });
    el.addEventListener("mouseleave", () => { tip.style.display = "none"; hl.style.display = "none"; });
  });
}
const zonenBaender = () => D.zonen_verlauf.map(z => ({ von: z.von, bis: z.bis || D.datum, farbe: ZF[z.zone] }));
const leg = l => `<div class="legende">${l.map(([n, f, s]) => `<span><i style="background:var(${f})${s ? ";opacity:.6" : ""}"></i>${esc(n)}</span>`).join("")}</div>`;
const karte = (titel, unter, inhalt, cls = "c12", rechts = "") => `<div class="card ${cls}"><div class="ch"><div><h3 class="ct">${titel}</h3>${unter ? `<div class="cs">${unter}</div>` : ""}</div>${rechts}</div>${inhalt}</div>`;
const ab = (jahre) => { const g = new Date(Date.parse(D.datum) - jahre * 365.25 * 864e5).toISOString().slice(0, 10); const i = S.t.findIndex(t => t >= g); return i < 0 ? 0 : i; };
const teil = (i0, ...keys) => keys.map(k => S[k].slice(i0));

/* ---------- Bausteine ---------- */
function skala() {
  const seg = [["Strong Sell", 0, 20], ["Reduzieren", 20, 40], ["Halten", 40, 60], ["Akkumulieren", 60, 80], ["Strong Buy", 80, 100]];
  return `<div class="skala">${seg.map(([z, a, b]) => `<div style="--zf:var(${ZF[z]});flex:${b - a}" class="${z === D.zone ? "an" : ""}"><span>${z}</span></div>`).join("")}
    <i class="marker" style="left:${Math.max(0, Math.min(100, D.score))}%"><b>${zahl(D.score)}</b></i></div>
    <div class="skala-a"><span>teuer</span><span>günstig</span></div>`;
}
function signal(p) { if (!ok(p)) return '<span class="mute klein">zu wenig Daten</span>'; return p <= 0.25 ? '<span class="sig g">günstig</span>' : p >= 0.75 ? '<span class="sig t">teuer</span>' : '<span class="sig n">neutral</span>'; }
function wertText(i) {
  const v = i.wert; if (!ok(v)) return "–";
  return { pl_abw: pct(10 ** v - 1) + " zum fairen Wert", mvrv_z: zahl(v, 2), mayer: zahl(v, 2), ma200w_ratio: zahl(v, 2) + "×", puell: zahl(v, 2),
    ath_ratio: pct(v - 1) + " unter Hoch", pi: zahl(v, 2), zyklus: pct(Math.exp(-v) - 1, 0) + " (frühere Zyklen, 12 M.)", fng: zahl(v) }[i.k] || zahl(v, 2);
}
function indikatorTabelle(liste) {
  return `<div class="tw"><table class="tbl"><thead><tr><th class="l">Indikator</th><th class="l">Aktuell</th><th class="l">Historisch ${tippI("Perzentil seit Beginn der Daten: 0 % = so günstig wie nie, 100 % = so teuer wie nie.")}</th><th class="l">Signal</th><th>Gewicht ${tippI("Vom Modell gelernt: wie gut der Indikator in der Vergangenheit schwache und starke Folgejahre vorhergesagt hat. Höchstens " + pct(D.regeln.max_gewicht, 0, false) + ".")}</th></tr></thead><tbody>
  ${liste.map(i => `<tr><td class="l"><b>${esc(i.name)}</b> ${tippI(i.erkl)}</td><td class="l">${esc(wertText(i))}</td>
    <td class="l"><span class="pbar"><i style="left:${(i.perzentil ?? 0.5) * 100}%"></i></span><span class="klein mute">${ok(i.perzentil) ? zahl(i.perzentil * 100) + " %" : "–"}</span></td>
    <td class="l">${signal(i.perzentil)}</td><td>${i.gewicht ? pct(i.gewicht, 0, false) : '<span class="mute">0 %</span>'}</td></tr>`).join("")}</tbody></table></div>`;
}

/* ---------- Tabs ---------- */
const RENDER = {
  uebersicht(el) {
    const treiber = D.indikatoren.filter(i => i.gewicht > 0 && ok(i.beitrag)).sort((a, b) => Math.abs(b.beitrag) - Math.abs(a.beitrag)).slice(0, 4);
    const satz = D.zone === "Strong Buy" ? "historisch eine der günstigsten Phasen" : D.zone === "Akkumulieren" ? "günstig bewertet – historisch eine gute Phase zum schrittweisen Kaufen"
      : D.zone === "Halten" ? "fair bewertet" : D.zone === "Reduzieren" ? "teuer – historisch folgten oft schwache Jahre" : "extrem teuer – historisch nahe an Zyklus-Hochs";
    el.innerHTML = `
    <div class="b-held" style="--zf:var(${ZF[D.zone]})">
      <div><div class="b-label">Langfrist-Einschätzung · ${esc(datum(D.datum))}</div>
        <div class="b-zone">${esc(D.zone)}</div>
        <p class="b-satz">Bitcoin ist nach ${D.indikatoren.length} Langfrist-Indikatoren aktuell <b>${satz}</b>.
        ${ok(zst.median_12m) ? `In ${zahl(zst.tage)} vergleichbaren Tagen seit 2014 lag Bitcoin 12 Monate später im Median bei <b>${pct(zst.median_12m)}</b> und in <b>${pct(zst.anteil_plus, 0, false)}</b> der Fälle im Plus.` : ""}</p>
        ${skala()}</div>
      <div class="b-kpis">
        <div><span>Kurs</span><b>${usd(D.preis)}</b><small>${pct(K.ath_ratio - 1)} unter dem Allzeithoch</small></div>
        <div><span>Fairer Wert (Power Law)</span><b>${usd(D.pl.fair)}</b><small>Kurs ${pct(plAbw)} ${plAbw < 0 ? "darunter" : "darüber"}</small></div>
        <div><span>Ø Einstand aller Coins</span><b>${usd(K.realized)}</b><small>Realized Price · MVRV ${zahl(K.mvrv, 2)}</small></div>
        <div><span>Halving-Zyklus</span><b>Tag ${zahl(D.zyklus.tag)}</b><small>nächstes Halving in ~${zahl(D.zyklus.tage_bis)} Tagen</small></div>
      </div>
    </div>
    <div class="grid">
      ${karte("Warum diese Einschätzung?", "Die Indikatoren mit dem größten Einfluss auf den heutigen Score", `<ul class="treiber">${treiber.map(i => `<li><div><b>${esc(i.name)}</b> ${signal(i.perzentil)}<div class="klein mute">${esc(wertText(i))} · historisch bei ${zahl(i.perzentil * 100)} % · Gewicht ${pct(i.gewicht, 0, false)}</div></div></li>`).join("")}</ul>
        <div class="score-vor">${[[7, "vor 7 Tagen"], [30, "vor 30 Tagen"], [90, "vor 90 Tagen"], [365, "vor 1 Jahr"]].map(([n, t]) => `<div><span>${t}</span><b>${zahl(D.score_vor[n])}</b>${zTag(zoneVon(D.score_vor[n]))}</div>`).join("")}</div>`, "c5")}
      ${karte("Was nach jeder Zone passierte", "Alle Tage seit 2014 – jeweils mit dem Wissen von damals bewertet", `<div class="tw"><table class="tbl"><thead><tr><th class="l">Zone</th><th>Tage</th><th>12 Monate später ${tippI("Median der Kursveränderung 12 Monate nach einem Tag in dieser Zone.")}</th><th>im Plus</th><th>Rückgang danach ${tippI("Median des größten Kursrückgangs in den folgenden 12 Monaten.")}</th></tr></thead><tbody>
        ${D.zonen.map(z => `<tr class="${z.zone === D.zone ? "hl" : ""}"><td class="l">${zTag(z.zone)}</td><td>${zahl(z.tage)}</td><td class="${kl(z.median_12m)}">${pct(z.median_12m)}</td><td>${pct(z.anteil_plus, 0, false)}</td><td class="neg">${pct(z.median_rueckgang)}</td></tr>`).join("")}</tbody></table></div>`, "c7")}
    </div>
    <div class="grid">${karte("Kurs, fairer Wert und Einschätzung seit 2014", "Logarithmisch · Hintergrund = Zone, die das Modell an diesem Tag angezeigt hätte", '<div class="chart" id="ch-u1"></div>', "c12",
      leg([["Kurs", "--ink"], ["Power-Law fair", "--s7"], ["Realized Price", "--s3"]]))}</div>
    <div class="grid">${karte("Gesamt-Score", "0 = extrem teuer · 100 = extrem günstig", '<div class="chart" id="ch-u2"></div>', "c12")}</div>
    <div class="card">${indikatorTabelle(D.indikatoren)}</div>
    <p class="fuss">Keine Anlageberatung. Das Modell kennt nur 3–4 vollständige Bitcoin-Zyklen; die Vergangenheit muss sich nicht wiederholen. Die Einschätzung ist für Monate bis Jahre gedacht, nicht für kurzfristiges Trading.</p>`;
    const i0 = S.t.findIndex(t => t >= "2014-01-01");
    const [t, p, f, r] = teil(i0, "t", "preis", "pl_fair", "realized");
    chart($("#ch-u1", el), { x: t, log: true, hoehe: 340, fmt: kurzUsd, baender: zonenBaender(), serien: [{ name: "Kurs", farbe: "--ink", v: p, breite: 1.6 }, { name: "Power-Law fair", farbe: "--s7", v: f, strich: true }, { name: "Realized Price", farbe: "--s3", v: r }],
      tipextra: b => `<div class="te">Score ${zahl(S.score[i0 + b])} · ${esc(zoneVon(S.score[i0 + b]) || "")}</div>` });
    chart($("#ch-u2", el), { x: t, hoehe: 200, ymin: 0, ymax: 100, fmt: v => zahl(v), baender: zonenBaender(), serien: [{ name: "Score", farbe: "--ink", v: S.score.slice(i0), breite: 1.6 }],
      hlinien: [{ v: 80, farbe: "--zsb" }, { v: 20, farbe: "--zss" }] });
  },

  bewertung(el) {
    const i3 = ab(4);
    el.innerHTML = `<p class="erkl">Das <b>Power-Law-Modell</b> beschreibt den Bitcoin-Kurs als Potenzfunktion der Zeit seit dem ersten Block (2009): Kurs ≈ 10^${zahl(D.pl.a, 2)} × Tage^${zahl(D.pl.b, 2)}. Auf einer doppelt-logarithmischen Skala ist das eine Gerade, um die der Kurs seit 15 Jahren pendelt. Die Bänder zeigen, wo 96 % aller Tage lagen.</p>
    <div class="kpis">
      <div class="kpi"><div class="k">Fairer Wert heute</div><div class="v">${usd(D.pl.fair)}</div><div class="n">Kurs ${pct(plAbw)}</div></div>
      <div class="kpi"><div class="k">Untere Linie ${tippI("Nur 2 % aller Tage lagen darunter – historisch eine Zone für Bärenmarkt-Tiefs.")}</div><div class="v">${usd(D.pl.unten)}</div><div class="n">${pct(D.preis / D.pl.unten - 1)} entfernt</div></div>
      <div class="kpi"><div class="k">Obere Linie</div><div class="v">${kurzUsd(D.pl.oben)}</div><div class="n">frühere Blasen-Hochs</div></div>
      <div class="kpi"><div class="k">Fairer Wert in 12 Monaten</div><div class="v">${usd(D.pl.fair_1j)}</div><div class="n">${pct(D.pl.fair_1j / D.pl.fair - 1)} Wachstum des Modells</div></div>
    </div>
    <div class="grid">${karte("Power Law seit 2010", "Logarithmisch", '<div class="chart" id="ch-b1"></div>', "c12", leg([["Kurs", "--ink"], ["fair", "--s7"], ["untere / obere Linie", "--s7", 1]]))}</div>
    <div class="grid">
      ${karte("Mayer Multiple", `Kurs ÷ 200-Tage-Linie · heute ${zahl(K.mayer, 2)} · unter 0,8 war historisch selten`, '<div class="chart" id="ch-b2"></div>', "c6")}
      ${karte("200-Wochen-Linie", `heute ${usd(K.ma200w)} · Kurs ${pct(K.ma200w_ratio - 1)} ${K.ma200w_ratio < 1 ? "darunter – das gab es fast nur an Zyklus-Tiefs" : "darüber"}`, '<div class="chart" id="ch-b3"></div>', "c6")}
    </div>`;
    chart($("#ch-b1", el), { x: S.t, log: true, hoehe: 360, fmt: kurzUsd, serien: [{ name: "Kurs", farbe: "--ink", v: S.preis, breite: 1.5 }, { name: "fair", farbe: "--s7", v: S.pl_fair, strich: true, breite: 2 }, { name: "untere Linie", farbe: "--s7", v: S.pl_unten, deck: 0.5 }, { name: "obere Linie", farbe: "--s7", v: S.pl_oben, deck: 0.5 }] });
    chart($("#ch-b2", el), { x: S.t.slice(ab(12)), hoehe: 220, fmt: v => zahl(v, 1), serien: [{ name: "Mayer", farbe: "--s1", v: S.mayer.slice(ab(12)) }], hlinien: [{ v: 1, txt: "1,0" }, { v: 2.4, txt: "2,4 (überhitzt)", farbe: "--zss" }, { v: 0.8, txt: "0,8", farbe: "--zsb" }] });
    chart($("#ch-b3", el), { x: S.t.slice(i3), log: true, hoehe: 220, fmt: kurzUsd, serien: [{ name: "Kurs", farbe: "--ink", v: S.preis.slice(i3) }, { name: "200-Wochen-Linie", farbe: "--s2", v: S.ma200w.slice(i3), breite: 2 }] });
  },

  onchain(el) {
    const i4 = ab(4);
    el.innerHTML = `<p class="erkl">On-Chain-Daten zeigen, zu welchem Preis die Coins zuletzt bewegt wurden. Der <b>Realized Price</b> ist der durchschnittliche Einstandspreis aller Bitcoin. <b>Kurzfrist-Halter</b> (unter 155 Tagen) reagieren nervös, <b>Langfrist-Halter</b> sind die „starken Hände“. Liegt der Kurs unter der Kostenbasis der Kurzfrist-Halter, sind die Neuen im Verlust – typisch für Bärenmärkte und ihre Tiefs.</p>
    <div class="kpis">
      <div class="kpi"><div class="k">Realized Price</div><div class="v">${usd(K.realized)}</div><div class="n">Kurs ${pct(D.preis / K.realized - 1)}</div></div>
      <div class="kpi"><div class="k">Kostenbasis Kurzfrist-Halter</div><div class="v">${usd(K.sth)}</div><div class="n">${ok(K.sth) ? (D.preis < K.sth ? "Kurs darunter – Neue im Verlust" : "Kurs darüber") : "keine Daten"}</div></div>
      <div class="kpi"><div class="k">Kostenbasis Langfrist-Halter</div><div class="v">${usd(K.lth)}</div><div class="n">${ok(K.lth) ? "Kurs " + pct(D.preis / K.lth - 1) : "keine Daten"}</div></div>
      <div class="kpi"><div class="k">MVRV-Z-Score</div><div class="v">${zahl(K.mvrv_z, 2)}</div><div class="n">unter 0 = historische Kaufzone · über 6 = Blase</div></div>
      <div class="kpi"><div class="k">NUPL</div><div class="v">${zahl(K.nupl, 2)}</div><div class="n">${K.nupl < 0 ? "Kapitulation" : K.nupl < 0.25 ? "Hoffnung / Angst" : K.nupl < 0.5 ? "Optimismus" : K.nupl < 0.75 ? "Glaube / Gier" : "Euphorie"}</div></div>
      <div class="kpi"><div class="k">SOPR (7 Tage)</div><div class="v">${zahl(K.sopr, 3)}</div><div class="n">${ok(K.sopr) ? (K.sopr < 1 ? "Coins werden mit Verlust verkauft" : "Coins werden mit Gewinn verkauft") : "–"}</div></div>
    </div>
    <div class="grid">${karte("Kurs gegen Kostenbasis", "Letzte 4 Jahre · logarithmisch" + (K.bg_datum ? " · Halter-Daten bis " + datum(K.bg_datum) : ""), '<div class="chart" id="ch-o1"></div>', "c12", leg([["Kurs", "--ink"], ["Realized Price", "--s3"], ["Kurzfrist-Halter", "--s2"], ["Langfrist-Halter", "--s7"]]))}</div>
    <div class="grid">
      ${karte("MVRV-Z-Score seit 2012", "Grün unter 0: frühere Zyklus-Tiefs · Rot über 6: frühere Hochs", '<div class="chart" id="ch-o2"></div>', "c6")}
      ${karte("NUPL", "Anteil des unrealisierten Gewinns am Marktwert", '<div class="chart" id="ch-o3"></div>', "c6")}
    </div>
    <div class="grid">
      ${karte("Puell Multiple", "Miner-Einnahmen gegen Jahresschnitt · unter 0,5 = Miner-Kapitulation", '<div class="chart" id="ch-o4"></div>', "c6")}
      ${karte("SOPR (7-Tage-Schnitt)", "Über 1 = Verkäufe mit Gewinn · unter 1 = mit Verlust", '<div class="chart" id="ch-o5"></div>', "c6")}
    </div>`;
    chart($("#ch-o1", el), { x: S.t.slice(i4), log: true, hoehe: 320, fmt: kurzUsd, serien: [{ name: "Kurs", farbe: "--ink", v: S.preis.slice(i4), breite: 1.6 }, { name: "Realized Price", farbe: "--s3", v: S.realized.slice(i4), breite: 2 }, { name: "Kurzfrist-Halter", farbe: "--s2", v: S.sth.slice(i4) }, { name: "Langfrist-Halter", farbe: "--s7", v: S.lth.slice(i4) }] });
    const i12 = S.t.findIndex(t => t >= "2012-01-01");
    chart($("#ch-o2", el), { x: S.t.slice(i12), hoehe: 230, fmt: v => zahl(v, 1), serien: [{ name: "MVRV-Z", farbe: "--s1", v: S.mvrv_z.slice(i12) }], hlinien: [{ v: 0, farbe: "--zsb", txt: "0" }, { v: 6, farbe: "--zss", txt: "6" }] });
    chart($("#ch-o3", el), { x: S.t.slice(i12), hoehe: 230, fmt: v => zahl(v, 2), ymin: -0.5, ymax: 1, serien: [{ name: "NUPL", farbe: "--s7", v: S.nupl.slice(i12) }], hlinien: [{ v: 0, farbe: "--zsb" }, { v: 0.75, farbe: "--zss", txt: "Euphorie" }] });
    chart($("#ch-o4", el), { x: S.t.slice(i12), hoehe: 230, log: true, fmt: v => zahl(v, 1), serien: [{ name: "Puell", farbe: "--s4", v: S.puell.slice(i12) }], hlinien: [{ v: 0.5, farbe: "--zsb", txt: "0,5" }, { v: 4, farbe: "--zss", txt: "4" }] });
    chart($("#ch-o5", el), { x: S.t.slice(i4), hoehe: 230, fmt: v => zahl(v, 3), serien: [{ name: "SOPR", farbe: "--s2", v: S.sopr.slice(i4) }], hlinien: [{ v: 1, txt: "1,0" }] });
  },

  zyklus(el) {
    const Z = D.zyklus, fertig = Z.zyklen.filter(z => z.fertig);
    const hochTage = fertig.map(z => z.hoch_tag), tiefTage = fertig.map(z => z.tief_tag);
    const FAR = ["--s4", "--s1", "--s3", "--s2", "--s7"];
    el.innerHTML = `<p class="erkl">Alle vier Jahre halbiert sich die Belohnung der Miner (<b>Halving</b>). Bisher folgte darauf jedes Mal ein ähnliches Muster: Hoch etwa ${zahl(Math.min(...hochTage))}–${zahl(Math.max(...hochTage))} Tage nach dem Halving, danach ein Bärenmarkt mit Tief nach ${zahl(Math.min(...tiefTage))}–${zahl(Math.max(...tiefTage))} Tagen. Heute ist <b>Tag ${zahl(Z.tag)}</b> nach dem Halving vom ${esc(datum(Z.halving))}.</p>
    <div class="kpis">
      <div class="kpi"><div class="k">Tag im Zyklus</div><div class="v">${zahl(Z.tag)}</div><div class="n">von ca. 1.460</div></div>
      <div class="kpi"><div class="k">Frühere Hochs</div><div class="v">Tag ${zahl(Math.round(hochTage.reduce((a, b) => a + b, 0) / hochTage.length))}</div><div class="n">im Schnitt (${hochTage.map(x => zahl(x)).join(" / ")})</div></div>
      <div class="kpi"><div class="k">Frühere Tiefs</div><div class="v">Tag ${zahl(Math.round(tiefTage.reduce((a, b) => a + b, 0) / tiefTage.length))}</div><div class="n">im Schnitt (${tiefTage.map(x => zahl(x)).join(" / ")})</div></div>
      <div class="kpi"><div class="k">Nächstes Halving</div><div class="v">~${zahl(Z.tage_bis)} Tage</div><div class="n">geschätzt ${esc(datum(Z.naechstes))}</div></div>
    </div>
    <div class="grid">${karte("Zyklen im Vergleich", "Kurs als Vielfaches des Kurses am Halving-Tag · logarithmisch", '<div class="chart" id="ch-z1"></div>', "c12", leg(Z.zyklen.map((z, i) => [z.halving.slice(0, 4) + (z.fertig ? "" : " (läuft)"), FAR[i]])))}</div>
    <div class="grid">
      ${karte("Zyklus-Daten", "", `<div class="tw"><table class="tbl"><thead><tr><th class="l">Halving</th><th>Kurs am Halving</th><th>Hoch</th><th>nach Tagen</th><th>Faktor</th><th>Tief danach</th><th>nach Tagen</th><th>Rückgang</th></tr></thead><tbody>
        ${Z.zyklen.map(z => `<tr${z.fertig ? "" : ' class="hl"'}><td class="l">${esc(datum(z.halving))}${z.fertig ? "" : ' <span class="mute klein">läuft</span>'}</td><td>${kurzUsd(z.start_preis)}</td><td>${kurzUsd(z.hoch_preis)}</td><td>${zahl(z.hoch_tag)}</td><td>${zahl(z.hoch_faktor, 1)}×</td><td>${kurzUsd(z.tief_preis)}</td><td>${zahl(z.tief_tag)}</td><td class="neg">${pct(z.rueckgang)}</td></tr>`).join("")}</tbody></table></div>
        <p class="klein mute" style="margin:10px 0 0">Die Faktoren werden mit jedem Zyklus kleiner – der Markt wird größer und reifer. Ob das Muster weiter gilt, ist offen: Es gibt erst ${fertig.length} abgeschlossene Beispiele.</p>`, "c7")}
      ${karte("Pi-Cycle-Indikator", "111-Tage-Linie ÷ 2 × 350-Tage-Linie · nahe 1 = frühere Zyklus-Hochs", '<div class="chart" id="ch-z2"></div>', "c5")}
    </div>`;
    const alleTage = Array.from(new Set(Z.zyklen.flatMap(z => z.punkte.map(p => p[0])))).sort((a, b) => a - b);
    const serien = Z.zyklen.map((z, i) => { const m = new Map(z.punkte.map(p => [p[0], p[1]])); return { name: z.halving.slice(0, 4), farbe: FAR[i], v: alleTage.map(t => m.get(t) ?? null), breite: z.fertig ? 1.6 : 2.6, fmt: v => zahl(v, 2) + "×" }; });
    chart($("#ch-z1", el), { x: alleTage, log: true, hoehe: 360, fmt: v => zahl(v, v < 1 ? 1 : 0) + "×", xfmt: t => "Tag " + zahl(t), tipx: t => "Tag " + zahl(t) + " nach dem Halving", serien, vlinien: [{ x: Z.tag, txt: "heute" }] });
    const i8 = ab(8);
    chart($("#ch-z2", el), { x: S.t.slice(i8), hoehe: 260, fmt: v => zahl(v, 2), serien: [{ name: "Pi-Cycle", farbe: "--s2", v: S.pi.slice(i8) }], hlinien: [{ v: 1, farbe: "--zss", txt: "1,0" }] });
  },

  stimmung(el) {
    const i = S.t.findIndex((t, j) => ok(S.fng[j]));
    const f = K.fng;
    const txt = f < 25 ? "Extreme Angst" : f < 45 ? "Angst" : f < 55 ? "Neutral" : f < 75 ? "Gier" : "Extreme Gier";
    el.innerHTML = `<p class="erkl">Stimmung ist ein Kontra-Indikator: Wenn alle Angst haben, ist oft viel Schlechtes schon im Kurs. Allein taugt sie aber wenig – das Modell hat dem Fear-&-Greed-Index bisher ${pct((D.indikatoren.find(x => x.k === "fng") || {}).gewicht || 0, 0, false)} Gewicht gegeben, weil er erst seit 2018 existiert und kurzfristig schwankt.</p>
    <div class="kpis">
      <div class="kpi"><div class="k">Fear & Greed heute</div><div class="v">${zahl(f)}</div><div class="n">${txt}</div></div>
      <div class="kpi"><div class="k">Hash Ribbons ${tippI("30- gegen 60-Tage-Schnitt der Hashrate. Unter 1 = Miner schalten ab (Kapitulation); das Ende einer Kapitulation war historisch oft ein gutes Kaufsignal.")}</div><div class="v">${zahl(K.hash_ribbon, 3)}</div><div class="n">${K.hash_ribbon < 1 ? "Miner-Kapitulation läuft" : "Hashrate wächst"}</div></div>
    </div>
    <div class="grid">${karte("Fear & Greed seit 2018", "0 = extreme Angst · 100 = extreme Gier", '<div class="chart" id="ch-s1"></div>', "c12")}</div>
    <div class="grid">${karte("Hash Ribbons", "Unter 1 = Miner-Kapitulation", '<div class="chart" id="ch-s2"></div>', "c12")}</div>`;
    chart($("#ch-s1", el), { x: S.t.slice(i), hoehe: 260, ymin: 0, ymax: 100, fmt: v => zahl(v), serien: [{ name: "Fear & Greed", farbe: "--s4", v: S.fng.slice(i), breite: 1.2 }], hlinien: [{ v: 25, farbe: "--zsb", txt: "Angst" }, { v: 75, farbe: "--zss", txt: "Gier" }] });
    const i4 = ab(4);
    chart($("#ch-s2", el), { x: S.t.slice(i4), hoehe: 220, fmt: v => zahl(v, 2), serien: [{ name: "Hash Ribbons", farbe: "--s1", v: S.hash_ribbon.slice(i4) }], hlinien: [{ v: 1, txt: "1,0" }] });
  },

  gelernt(el) {
    const B = D.backtest, SP = D.sparplan, jahre = Object.keys(D.gewichte).sort();
    const ks = Object.keys(D.merkmale);
    el.innerHTML = `<p class="erkl">Das Modell lernt jedes Jahr neu – aber nur mit Daten, die damals schon bekannt waren. So ist jede Bewertung seit ${esc(datum(D.regeln.lern_start))} ein echter Test: Sie hätte genau so am jeweiligen Tag berechnet werden können.</p>
    <div class="grid">
      ${karte("Sparplan-Test: normal gegen smart", `Jede Woche 100 $ seit ${esc(datum(SP.start))}. Smart: ${Object.entries(D.regeln.sparplan).map(([z, f]) => `${z} ${zahl(f, 1)}×`).join(" · ")}`, `
        <div class="vergl"><div><span>Normaler Sparplan</span><b>${kurzUsd(SP.normal.wert)}</b><small>eingezahlt ${kurzUsd(SP.normal.eingezahlt)} · Ø Kaufpreis ${usd(SP.normal.kaufpreis)}</small></div>
        <div class="besser"><span>Smarter Sparplan</span><b>${kurzUsd(SP.smart.wert)}</b><small>eingezahlt ${kurzUsd(SP.smart.eingezahlt)} · Ø Kaufpreis ${usd(SP.smart.kaufpreis)}</small></div></div>
        <p class="klein" style="margin:12px 0">Der smarte Sparplan hat im Schnitt <b>${pct(SP.smart.kaufpreis / SP.normal.kaufpreis - 1)}</b> günstiger gekauft und aus jedem eingezahlten Dollar <b>${zahl(SP.smart.faktor, 1)}×</b> statt ${zahl(SP.normal.faktor, 1)}× gemacht.</p>
        <div class="chart" id="ch-g2"></div>`, "c6", leg([["normal", "--ink3"], ["smart", "--good"]]))}
      ${karte("Timing-Test: kaufen und verkaufen nach Zone", `Anteil in Bitcoin: ${Object.entries(D.regeln.anteil).map(([z, a]) => `${z} ${pct(a, 0, false)}`).join(" · ")} · ${pct(D.regeln.gebuehr, 1, false)} Gebühr je Umschichtung`, `
        <div class="vergl"><div><span>Nach Zone handeln</span><b>${zahl(B.kz_strategie.faktor, 0)}×</b><small>${pct(B.kz_strategie.cagr, 0)} pro Jahr · größter Rückgang ${pct(B.kz_strategie.max_dd, 0)}</small></div>
        <div><span>Einfach halten</span><b>${zahl(B.kz_halten.faktor, 0)}×</b><small>${pct(B.kz_halten.cagr, 0)} pro Jahr · größter Rückgang ${pct(B.kz_halten.max_dd, 0)}</small></div></div>
        <p class="klein" style="margin:12px 0">Ehrliches Ergebnis: Verkaufen nach dem Modell hat die großen Rückgänge abgefedert, aber <b>weniger Rendite</b> gebracht als einfaches Halten – wer früh verkauft, verpasst oft den letzten, steilsten Teil eines Anstiegs. Am stärksten ist das Modell beim <b>Kaufen in günstigen Phasen</b>.</p>
        <div class="chart" id="ch-g1"></div>`, "c6", leg([["nach Zone", "--s1"], ["halten", "--ink3"]]))}
    </div>
    <div class="card" style="margin-bottom:16px"><div class="ch"><div><h3 class="ct">Gelernte Gewichte je Jahr</h3><div class="cs">Wie viel jeder Indikator in die Bewertung des jeweiligen Jahres einging (höchstens ${pct(D.regeln.max_gewicht, 0, false)})</div></div></div>
      <div class="tw"><table class="tbl hm gew"><thead><tr><th class="l">Indikator</th>${jahre.map(j => `<th>${j}</th>`).join("")}</tr></thead><tbody>
      ${ks.map(k => `<tr><td class="l" style="text-align:left">${esc(D.merkmale[k])}</td>${jahre.map(j => { const w = D.gewichte[j][k] || 0; return `<td style="background:color-mix(in srgb,var(--s1) ${Math.round(w / D.regeln.max_gewicht * 55)}%,transparent)">${w ? zahl(w * 100) : ""}</td>`; }).join("")}</tr>`).join("")}
      </tbody></table></div></div>
    <div class="card"><div class="ch"><div><h3 class="ct">Zonen-Statistik im Detail</h3><div class="cs">Alle Tage seit ${esc(datum(D.regeln.lern_start))}, Werte 12 Monate (bzw. 3 Monate) später</div></div></div>
      <div class="tw"><table class="tbl"><thead><tr><th class="l">Zone</th><th>Tage</th><th>3 Monate</th><th>12 Monate</th><th>im Plus</th><th>bestes Jahr</th><th>schlechtestes Jahr</th><th>Rückgang danach</th></tr></thead><tbody>
      ${D.zonen.map(z => `<tr class="${z.zone === D.zone ? "hl" : ""}"><td class="l">${zTag(z.zone)}</td><td>${zahl(z.tage)}</td><td class="${kl(z.median_3m)}">${pct(z.median_3m)}</td><td class="${kl(z.median_12m)}">${pct(z.median_12m)}</td><td>${pct(z.anteil_plus, 0, false)}</td><td class="pos">${pct(z.bester_12m)}</td><td class="${kl(z.schlechtester_12m)}">${pct(z.schlechtester_12m)}</td><td class="neg">${pct(z.median_rueckgang)}</td></tr>`).join("")}
      </tbody></table></div></div>`;
    chart($("#ch-g1", el), { x: B.t, log: true, hoehe: 240, fmt: v => zahl(v, v < 10 ? 1 : 0) + "×", serien: [{ name: "nach Zone", farbe: "--s1", v: B.strategie, breite: 2 }, { name: "halten", farbe: "--ink3", v: B.halten }] });
    chart($("#ch-g2", el), { x: SP.t, log: true, hoehe: 240, fmt: kurzUsd, serien: [{ name: "smart", farbe: "--good", v: SP.s_wert, breite: 2 }, { name: "normal", farbe: "--ink3", v: SP.n_wert }, { name: "eingezahlt (normal)", farbe: "--ink3", v: SP.n_geld, strich: true, deck: 0.6 }] });
  },

  methode(el) {
    el.innerHTML = `<div class="grid">
      ${karte("So entsteht die Einschätzung", "", `<ol class="gedanken" style="margin-top:6px">
        <li><b>Daten (täglich):</b> Kurs, Marktwert, MVRV, Emission und Hashrate seit 2010 (CoinMetrics), Fear & Greed seit 2018 (alternative.me), Kostenbasis der Kurz- und Langfrist-Halter und SOPR (bitcoin-data.com).</li>
        <li><b>Indikatoren:</b> ${Object.values(D.merkmale).join(", ")}.</li>
        <li><b>Vergleich mit der Geschichte:</b> Jeder Wert wird in ein Perzentil umgerechnet – nur mit Daten bis zum jeweiligen Tag.</li>
        <li><b>Lernen:</b> Zu jedem Jahresbeginn misst das Modell, welche Indikatoren vorher schwache und starke 12-Monats-Phasen angekündigt haben, und gewichtet sie danach (höchstens ${pct(D.regeln.max_gewicht, 0, false)} je Indikator).</li>
        <li><b>Score und Zone:</b> 0–100, daraus ${D.zonen_def.map(([g, n]) => n + " ab " + g).join(", ")}.</li>
      </ol>`, "c6")}
      ${karte("Grenzen", "", `<ul class="gruende warnliste">
        <li>Es gibt erst 3–4 vollständige Zyklen. Ein Modell, das daraus lernt, kann sich auf ein Muster verlassen, das nicht weiter gilt.</li>
        <li>Power Law, Halving-Zyklus und On-Chain-Kennzahlen sind Beobachtungen, keine Naturgesetze. Mit ETFs und großen Firmen im Markt kann sich das Verhalten ändern.</li>
        <li>Die Zonen sind für Monate bis Jahre gedacht. Kurzfristig kann der Kurs auch in „Strong Buy“ noch deutlich fallen.</li>
        <li>Checkonchain und Glassnode bieten weitere Kennzahlen, aber keine freie Schnittstelle. Die wichtigsten (Kostenbasis der Halter, SOPR, MVRV) sind hier über freie Quellen abgedeckt.</li>
        <li>Keine Anlageberatung – die Entscheidung triffst du.</li>
      </ul>`, "c6")}
    </div>
    <div class="card"><h3 class="ct">Protokoll</h3><ul class="liste" style="margin-top:8px">${(D.protokoll || []).length ? D.protokoll.map(p => `<li><span class="mute klein">${esc(zeit(p.zeit))}</span> · ${esc(p.text)}</li>`).join("") : '<li class="mute">Keine Meldungen.</li>'}</ul></div>`;
  },
};

const start = (location.hash || "").slice(1);
zeigeTab(RENDER[start] ? start : "uebersicht");
})();
