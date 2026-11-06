(function () {
"use strict";
const D = JSON.parse(document.getElementById("daten").textContent);
const P = D.par;

/* ============================== Helfer ============================== */
const $ = (s, el) => (el || document).querySelector(s);
const $$ = (s, el) => Array.from((el || document).querySelectorAll(s));
const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const ok = x => x !== null && x !== undefined && isFinite(x);
const zahl = (x, nk = 2) => ok(x) ? Number(x).toLocaleString("de-DE", { minimumFractionDigits: nk, maximumFractionDigits: nk }) : "–";
const pct = (x, nk = 1, vz = true) => ok(x) ? (vz && x > 0 ? "+" : "") + (x * 100).toLocaleString("de-DE", { minimumFractionDigits: nk, maximumFractionDigits: nk }) + " %" : "–";
const kl = x => !ok(x) || Math.abs(x) < 1e-9 ? "" : (x > 0 ? "pos" : "neg");
const sym = cur => cur === "EUR" ? "€" : "$";
const dat = (iso, jahr) => { if (!iso) return "–"; const [y, m, d] = iso.split("-"); return jahr ? `${d}.${m}.${y}` : `${d}.${m}.`; };
const datKurz = iso => { if (!iso) return ""; const [y, m, d] = iso.split("-"); return `${d}.${m}.${y.slice(2)}`; };
const geld = (w, cur) => !ok(w) ? "–" : (w >= 1e9 ? zahl(w / 1e9, 2) + " Mrd. " : w >= 1e6 ? zahl(w / 1e6, 2) + " Mio. " : zahl(w / 1e3, 0) + " Tsd. ") + sym(cur);
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const typTag = t => `<span class="mtag ${t === "52W-Hoch" ? "W52" : esc(t)}">${esc(t)}</span>`;
const tlink = (t, extra) => `<span class="tlink" data-ticker="${esc(t)}"${extra ? ` data-trade="${extra}"` : ""}>${esc(t)}</span>`;
const tippI = txt => `<span class="tipp" tabindex="0" data-tipp="${esc(txt)}">?</span>`;
const KOMP = [
  { k: "M", name: "Momentum", farbe: "--s1", gew: "GEWICHT_MOMENTUM" },
  { k: "P", name: "Kurssprung (Zahlen)", farbe: "--s2", gew: "GEWICHT_PEAD" },
  { k: "I", name: "Insider", farbe: "--s3", gew: "GEWICHT_INSIDER" },
  { k: "H", name: "52W-Hoch", farbe: "--s4", gew: "GEWICHT_HOCH" },
];
const SERIEN_FARBEN = ["--s2", "--s3", "--s4", "--s5", "--s7"];
const TRADES = D.trades;
const tradeById = {}; TRADES.forEach(t => tradeById[t.id] = t);
const merke = (k, v) => { try { localStorage.setItem("radar_" + k, JSON.stringify(v)); } catch (e) { } };
const lies = (k, d) => { try { const v = localStorage.getItem("radar_" + k); return v ? JSON.parse(v) : d; } catch (e) { return d; } };

/* ============================== Charts ============================== */
const charts = [];
function nice(lo, hi, n) {
  const r = hi - lo || Math.abs(hi) || 1, roh = r / n, p = Math.pow(10, Math.floor(Math.log10(roh)));
  const s = [1, 2, 2.5, 5, 10].map(x => x * p).find(x => r / x <= n) || 10 * p;
  const a = Math.ceil(lo / s) * s, out = [];
  for (let v = a; v <= hi + 1e-9; v += s) out.push(+v.toFixed(10));
  return out;
}
function datTicks(x, w) {
  const n = Math.max(2, Math.min(7, Math.floor(w / 110))), out = [];
  for (let k = 0; k < n; k++) out.push(Math.round(k * (x.length - 1) / (n - 1)));
  return out;
}
/* Linien-Chart. cfg: x[], series[{name,farbe,v[],breite,strich,flaeche,fmt}], marker[{i,v,form,farbe,txt}],
   hlinien[{v,farbe,strich,txt}], vlinien[{i,txt}], yfmt, hoehe, nullLinie */
function linie(host, cfg) {
  const zeichne = () => {
    const W = host.clientWidth || 600, H = cfg.hoehe || 300;
    const pl = 6, pr = cfg.pr || 58, pt = 14, pb = 26;
    const x = cfg.x, n = x.length;
    if (!n) { host.innerHTML = '<div class="leer">Keine Daten</div>'; return; }
    const sicht = cfg.series.filter(s => !s.aus);
    let werte = [];
    sicht.forEach(s => s.v.forEach(v => { if (ok(v)) werte.push(v); }));
    (cfg.hlinien || []).forEach(h => werte.push(h.v));
    if (!werte.length) werte = [0, 1];
    let lo = Math.min(...werte), hi = Math.max(...werte);
    if (cfg.nullLinie) { lo = Math.min(lo, 0); hi = Math.max(hi, 0); }
    const pad = (hi - lo) * 0.06 || Math.abs(hi) * 0.05 || 1; lo -= pad; hi += pad;
    const X = i => pl + (W - pl - pr) * (n === 1 ? 0.5 : i / (n - 1));
    const Y = v => pt + (H - pt - pb) * (1 - (v - lo) / (hi - lo));
    const yfmt = cfg.yfmt || (v => zahl(v, Math.abs(hi - lo) < 10 ? 2 : 0));
    const lc = css("--line2"), i3 = css("--ink3");
    let g = "";
    nice(lo, hi, Math.max(3, Math.floor(H / 60))).forEach(v => {
      g += `<line x1="${pl}" x2="${W - pr}" y1="${Y(v)}" y2="${Y(v)}" stroke="${lc}"/><text x="${W - pr + 8}" y="${Y(v) + 4}" font-size="11" fill="${i3}">${esc(yfmt(v))}</text>`;
    });
    if (cfg.nullLinie && lo < 0 && hi > 0) g += `<line x1="${pl}" x2="${W - pr}" y1="${Y(0)}" y2="${Y(0)}" stroke="${css("--ink3")}" stroke-width="1"/>`;
    datTicks(x, W - pr).forEach((i, k, arr) => {
      const anker = k === 0 ? "start" : k === arr.length - 1 ? "end" : "middle";
      g += `<text x="${X(i)}" y="${H - 6}" font-size="11" fill="${i3}" text-anchor="${anker}">${esc(datKurz(x[i]))}</text>`;
    });
    (cfg.vlinien || []).forEach(v => {
      if (v.i < 0 || v.i >= n) return;
      g += `<line x1="${X(v.i)}" x2="${X(v.i)}" y1="${pt}" y2="${H - pb}" stroke="${i3}" stroke-dasharray="3 4"/>` +
        (v.txt ? `<text x="${X(v.i) + 5}" y="${pt + 9}" font-size="11" fill="${i3}">${esc(v.txt)}</text>` : "");
    });
    sicht.slice().reverse().forEach(s => {
      let d = "", neu = true;
      s.v.forEach((v, i) => { if (!ok(v)) { neu = true; return; } d += (neu ? "M" : "L") + X(i).toFixed(1) + " " + Y(v).toFixed(1); neu = false; });
      const f = css(s.farbe);
      if (s.flaeche) {
        const basis = Y(s.flaecheBasis != null ? s.flaecheBasis : lo);
        const i0 = s.v.findIndex(ok), i1 = s.v.length - 1 - s.v.slice().reverse().findIndex(ok);
        g += `<path d="${d} L${X(i1)} ${basis} L${X(i0)} ${basis} Z" fill="${f}" opacity="${s.flaecheOpa || 0.12}"/>`;
      }
      g += `<path d="${d}" fill="none" stroke="${f}" stroke-width="${s.breite || 2}" ${s.strich ? `stroke-dasharray="${s.strich}"` : ""} stroke-linejoin="round" stroke-linecap="round"/>`;
    });
    (cfg.hlinien || []).forEach(h => {
      const f = css(h.farbe);
      g += `<line x1="${pl}" x2="${W - pr}" y1="${Y(h.v)}" y2="${Y(h.v)}" stroke="${f}" stroke-width="1.5" stroke-dasharray="${h.strich || "6 5"}"/>` +
        `<rect x="${W - pr + 2}" y="${Y(h.v) - 9}" width="${pr - 2}" height="18" rx="4" fill="${f}"/>` +
        `<text x="${W - pr + 6}" y="${Y(h.v) + 4}" font-size="11" font-weight="600" fill="#fff">${esc(yfmt(h.v))}</text>` +
        (h.txt ? `<text x="${pl + 4}" y="${Y(h.v) - 6}" font-size="11" font-weight="600" fill="${f}">${esc(h.txt)}</text>` : "");
    });
    (cfg.marker || []).forEach(m => {
      if (m.i < 0 || m.i >= n || !ok(m.v)) return;
      const cx = X(m.i), cy = Y(m.v), f = css(m.farbe), r = m.r || 5, rand = css("--card");
      if (m.form === "auf") g += `<path d="M${cx} ${cy - r - 9} l${r + 1} ${r + 4} h${-2 * r - 2} z" fill="${f}" stroke="${rand}" stroke-width="1.5"/>`;
      else if (m.form === "ab") g += `<path d="M${cx} ${cy + r + 9} l${r + 1} ${-r - 4} h${-2 * r - 2} z" fill="${f}" stroke="${rand}" stroke-width="1.5"/>`;
      else if (m.form === "raute") g += `<path d="M${cx} ${cy - r - 1} l${r + 1} ${r + 1} l${-r - 1} ${r + 1} l${-r - 1} ${-r - 1} z" fill="${f}" stroke="${rand}" stroke-width="1.5"/>`;
      else g += `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${f}" stroke="${rand}" stroke-width="2"/>`;
    });
    g += `<line class="kx" y1="${pt}" y2="${H - pb}" stroke="${i3}" stroke-width="1" visibility="hidden"/>`;
    sicht.forEach((s, k) => g += `<circle class="kp kp${k}" r="4" fill="${css(s.farbe)}" stroke="${css("--card")}" stroke-width="2" visibility="hidden"/>`);
    host.innerHTML = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(cfg.label || "Chart")}">${g}<rect class="fang" x="0" y="0" width="${W - pr}" height="${H}" fill="transparent"/></svg><div class="tip"></div>`;
    const svg = host.querySelector("svg"), tip = host.querySelector(".tip"), kx = svg.querySelector(".kx");
    const markerBei = {}; (cfg.marker || []).forEach(m => { if (m.txt) (markerBei[m.i] = markerBei[m.i] || []).push(m); });
    const an = ev => {
      const r = svg.getBoundingClientRect();
      let i = Math.round((ev.clientX - r.left - pl) / (W - pl - pr) * (n - 1));
      i = Math.max(0, Math.min(n - 1, i));
      // Marker in der Nähe bevorzugen
      for (const dd of [0, -1, 1, -2, 2]) if (markerBei[i + dd]) { i = i + dd; break; }
      kx.setAttribute("x1", X(i)); kx.setAttribute("x2", X(i)); kx.setAttribute("visibility", "visible");
      let h = `<div class="tk">${esc(dat(x[i], true))}</div>`;
      sicht.forEach((s, k) => {
        const c = svg.querySelector(".kp" + k), v = s.v[i];
        if (!ok(v)) { c.setAttribute("visibility", "hidden"); return; }
        c.setAttribute("cx", X(i)); c.setAttribute("cy", Y(v)); c.setAttribute("visibility", "visible");
        h += `<div class="tz"><span><i style="background:${css(s.farbe)}"></i>${esc(s.name)}</span><b>${esc((s.fmt || cfg.tipfmt || yfmt)(v))}</b></div>`;
      });
      (markerBei[i] || []).forEach(m => h += `<div class="te">${esc(m.txt)}</div>`);
      tip.innerHTML = h; tip.style.display = "block";
      const tw = tip.offsetWidth, px = X(i);
      tip.style.left = (px + 14 + tw > W - pr ? px - tw - 14 : px + 14) + "px";
      tip.style.top = "6px";
    };
    const weg = () => { tip.style.display = "none"; kx.setAttribute("visibility", "hidden"); $$(".kp", svg).forEach(c => c.setAttribute("visibility", "hidden")); };
    svg.addEventListener("pointermove", an); svg.addEventListener("pointerdown", an); svg.addEventListener("pointerleave", weg);
  };
  host.classList.add("chart");
  host._zeichne = zeichne;
  if (!charts.includes(host)) charts.push(host);
  zeichne();
}
function donut(host, teile, mitte, unter) {
  const zeichne = () => {
    const S = Math.min(host.clientWidth || 240, 240), R = S / 2, r = R * 0.64, sum = teile.reduce((a, b) => a + b.w, 0) || 1;
    let a0 = -Math.PI / 2, g = "";
    const luecke = teile.length > 1 ? 0.012 : 0;
    teile.forEach((t, k) => {
      const a1 = a0 + 2 * Math.PI * t.w / sum, s = a0 + luecke, e = Math.max(s + 0.001, a1 - luecke), gr = e - s > Math.PI ? 1 : 0;
      const p = (rad, w) => `${R + rad * Math.cos(w)} ${R + rad * Math.sin(w)}`;
      g += `<path data-k="${k}" d="M${p(R, s)} A${R} ${R} 0 ${gr} 1 ${p(R, e)} L${p(r, e)} A${r} ${r} 0 ${gr} 0 ${p(r, s)} Z" fill="${css(t.farbe)}"/>`;
      a0 = a1;
    });
    host.innerHTML = `<svg width="${S}" height="${S}" viewBox="0 0 ${S} ${S}" style="display:block;margin:0 auto">${g}
      <text x="${R}" y="${R - 2}" text-anchor="middle" font-size="22" font-weight="700" fill="${css("--ink")}">${esc(mitte || "")}</text>
      <text x="${R}" y="${R + 18}" text-anchor="middle" font-size="12" fill="${css("--ink3")}">${esc(unter || "")}</text></svg><div class="tip"></div>`;
    const tip = host.querySelector(".tip");
    $$("path", host).forEach(p => {
      p.addEventListener("pointerenter", ev => { const t = teile[+p.dataset.k]; tip.innerHTML = `<div class="tz"><span><i style="background:${css(t.farbe)}"></i>${esc(t.name)}</span><b>${pct(t.w / sum, 1, false)}</b></div>`; tip.style.display = "block"; tip.style.left = "8px"; tip.style.top = "8px"; });
      p.addEventListener("pointerleave", () => tip.style.display = "none");
    });
  };
  host.classList.add("chart"); host._zeichne = zeichne; if (!charts.includes(host)) charts.push(host); zeichne();
}
function saeulen(host, werte, cfg) {
  /* werte: [{v, label, farbe, txt}] */
  const zeichne = () => {
    const W = host.clientWidth || 500, H = cfg.hoehe || 200, pl = 6, pr = 50, pt = 10, pb = 24, n = werte.length;
    if (!n) { host.innerHTML = '<div class="leer">Keine Daten</div>'; return; }
    let lo = Math.min(0, ...werte.map(w => w.v)), hi = Math.max(0, ...werte.map(w => w.v));
    if (hi === lo) hi = lo + 1;
    const Y = v => pt + (H - pt - pb) * (1 - (v - lo) / (hi - lo));
    const bw = (W - pl - pr) / n, gap = Math.min(2, bw * 0.2);
    let g = "";
    nice(lo, hi, 4).forEach(v => g += `<line x1="${pl}" x2="${W - pr}" y1="${Y(v)}" y2="${Y(v)}" stroke="${css("--line2")}"/><text x="${W - pr + 8}" y="${Y(v) + 4}" font-size="11" fill="${css("--ink3")}">${esc((cfg.yfmt || (v => zahl(v, 0)))(v))}</text>`);
    werte.forEach((w, i) => {
      const y0 = Y(Math.max(0, w.v)), y1 = Y(Math.min(0, w.v)), h = Math.max(1, y1 - y0);
      g += `<rect data-i="${i}" x="${pl + i * bw + gap / 2}" y="${y0}" width="${Math.max(1, bw - gap)}" height="${h}" rx="${Math.min(3, bw / 3)}" fill="${css(w.farbe)}"/>`;
    });
    g += `<line x1="${pl}" x2="${W - pr}" y1="${Y(0)}" y2="${Y(0)}" stroke="${css("--ink3")}"/>`;
    const labels = cfg.labels || [];
    labels.forEach(l => g += `<text x="${pl + l.i * bw + bw / 2}" y="${H - 6}" font-size="11" fill="${css("--ink3")}" text-anchor="middle">${esc(l.t)}</text>`);
    host.innerHTML = `<svg width="${W}" height="${H}">${g}<rect class="fang" x="0" y="0" width="${W - pr}" height="${H}" fill="transparent"/></svg><div class="tip"></div>`;
    const svg = host.querySelector("svg"), tip = host.querySelector(".tip");
    svg.addEventListener("pointermove", ev => {
      const r = svg.getBoundingClientRect(); const i = Math.floor((ev.clientX - r.left - pl) / bw);
      if (i < 0 || i >= n) { tip.style.display = "none"; return; }
      tip.innerHTML = werte[i].txt; tip.style.display = "block";
      const px = pl + i * bw; tip.style.left = Math.min(px + 12, W - tip.offsetWidth - 4) + "px"; tip.style.top = "4px";
    });
    svg.addEventListener("pointerleave", () => tip.style.display = "none");
  };
  host.classList.add("chart"); host._zeichne = zeichne; if (!charts.includes(host)) charts.push(host); zeichne();
}
function streu(host, punkte, cfg) {
  /* punkte: [{x,y,farbe,r,txt}] */
  const zeichne = () => {
    const W = host.clientWidth || 500, H = cfg.hoehe || 300, pl = 48, pr = 12, pt = 12, pb = 36;
    if (!punkte.length) { host.innerHTML = '<div class="leer">Noch keine Daten</div>'; return; }
    const xs = punkte.map(p => p.x), ys = punkte.map(p => p.y);
    let x0 = Math.min(...xs, 0), x1 = Math.max(...xs, 0), y0 = Math.min(...ys, 0), y1 = Math.max(...ys, 0);
    const px = (x1 - x0) * 0.08 || 0.05, py = (y1 - y0) * 0.08 || 0.05; x0 -= px; x1 += px; y0 -= py; y1 += py;
    const X = v => pl + (W - pl - pr) * (v - x0) / (x1 - x0), Y = v => pt + (H - pt - pb) * (1 - (v - y0) / (y1 - y0));
    let g = "";
    nice(y0, y1, 4).forEach(v => g += `<line x1="${pl}" x2="${W - pr}" y1="${Y(v)}" y2="${Y(v)}" stroke="${css("--line2")}"/><text x="${pl - 6}" y="${Y(v) + 4}" font-size="11" text-anchor="end" fill="${css("--ink3")}">${esc(pct(v, 0))}</text>`);
    nice(x0, x1, 5).forEach(v => g += `<text x="${X(v)}" y="${H - 18}" font-size="11" text-anchor="middle" fill="${css("--ink3")}">${esc(pct(v, 0))}</text>`);
    g += `<line x1="${X(0)}" x2="${X(0)}" y1="${pt}" y2="${H - pb}" stroke="${css("--ink3")}" stroke-dasharray="3 3"/><line x1="${pl}" x2="${W - pr}" y1="${Y(0)}" y2="${Y(0)}" stroke="${css("--ink3")}" stroke-dasharray="3 3"/>`;
    g += `<text x="${(W + pl) / 2}" y="${H - 2}" font-size="11.5" text-anchor="middle" fill="${css("--ink2")}">${esc(cfg.xlabel || "")}</text>`;
    g += `<text x="12" y="${(H - pb) / 2}" font-size="11.5" text-anchor="middle" fill="${css("--ink2")}" transform="rotate(-90 12 ${(H - pb) / 2})">${esc(cfg.ylabel || "")}</text>`;
    punkte.slice().sort((a, b) => (a.r || 4) - (b.r || 4)).forEach((p, k) => g += `<circle data-k="${punkte.indexOf(p)}" cx="${X(p.x)}" cy="${Y(p.y)}" r="${p.r || 4}" fill="${css(p.farbe || "--ink3")}" fill-opacity="${p.r > 5 ? 1 : 0.55}" stroke="${css("--card")}" stroke-width="${p.r > 5 ? 2 : 1}"/>`);
    host.innerHTML = `<svg width="${W}" height="${H}">${g}</svg><div class="tip"></div>`;
    const tip = host.querySelector(".tip");
    $$("circle", host).forEach(c => {
      c.addEventListener("pointerenter", () => { const p = punkte[+c.dataset.k]; tip.innerHTML = p.txt; tip.style.display = "block"; tip.style.left = Math.min(+c.getAttribute("cx") + 10, W - 230) + "px"; tip.style.top = Math.max(+c.getAttribute("cy") - 40, 0) + "px"; });
      c.addEventListener("pointerleave", () => tip.style.display = "none");
    });
  };
  host.classList.add("chart"); host._zeichne = zeichne; if (!charts.includes(host)) charts.push(host); zeichne();
}
let rz; window.addEventListener("resize", () => { clearTimeout(rz); rz = setTimeout(() => charts.forEach(c => c.offsetParent && c._zeichne()), 120); });
function neuZeichnen() { charts.forEach(c => c.offsetParent && c._zeichne()); }

/* Score-Balken */
function scoreBar(komp, schwelle) {
  let h = "";
  KOMP.forEach(k => { const v = 100 * P[k.gew] * (komp[k.k] || 0); if (v > 0.5) h += `<i style="width:${Math.min(v, 100)}%;background:var(${k.farbe})"></i>`; });
  return `<div class="sbar">${h}${schwelle ? `<span class="schw" style="left:${schwelle}%"></span>` : ""}</div>`;
}
const scoreLegende = () => `<div class="legende">${KOMP.map(k => `<span><i style="background:var(${k.farbe})"></i>${k.name} (max. ${Math.round(100 * P[k.gew])})</span>`).join("")}</div>`;

/* Performance-Chart mit Vergleichsindizes und Zeitraum */
const BEREICHE = [["1M", 21], ["3M", 63], ["6M", 126], ["YTD", "ytd"], ["1J", 252], ["Alle", 0]];
function perfChart(host, opts) {
  const ausgew = new Set(lies("bench", D.bench.map(b => b.name)));
  let bereich = lies("bereich", "Alle"), mitKern = !!opts.kern;
  const wrap = document.createElement("div");
  host.appendChild(wrap);
  const steuer = document.createElement("div"); steuer.className = "steuer";
  const chips = document.createElement("div"); chips.className = "chips";
  const seg = document.createElement("div"); seg.className = "seg";
  steuer.append(chips, seg); wrap.appendChild(steuer);
  const ch = document.createElement("div"); wrap.appendChild(ch);
  const unter = document.createElement("div"); unter.className = "cs"; unter.style.marginTop = "8px"; wrap.appendChild(unter);
  const zeichneSteuer = () => {
    chips.innerHTML = `<span class="chip serie"><i class="dot" style="background:var(--s1)"></i>Radar</span>` +
      D.bench.map((b, k) => `<span class="chip serie ${ausgew.has(b.name) ? "" : "aus"}" data-b="${esc(b.name)}"><i class="dot" style="background:var(${SERIEN_FARBEN[k % 5]})"></i>${esc(b.name)}</span>`).join("") +
      (opts.kern ? `<span class="chip serie ${mitKern ? "" : "aus"}" data-b="__kern"><i class="dot" style="background:var(--s6)"></i>Nur Kern</span>` : "");
    seg.innerHTML = BEREICHE.map(([n]) => `<button class="${n === bereich ? "an" : ""}" data-r="${n}">${n}</button>`).join("");
  };
  steuer.addEventListener("click", ev => {
    const b = ev.target.closest("[data-b]"), r = ev.target.closest("[data-r]");
    if (b) { const n = b.dataset.b; if (n === "__kern") mitKern = !mitKern; else { ausgew.has(n) ? ausgew.delete(n) : ausgew.add(n); merke("bench", [...ausgew]); } }
    if (r) { bereich = r.dataset.r; merke("bereich", bereich); }
    if (b || r) { zeichneSteuer(); male(); }
  });
  const male = () => {
    const n = D.dates.length; let a = 0;
    const def = BEREICHE.find(b => b[0] === bereich)[1];
    if (def === "ytd") { const j = D.dates[n - 1].slice(0, 4); a = Math.max(0, D.dates.findIndex(d => d.slice(0, 4) === j) - 1); }
    else if (def) a = Math.max(0, n - 1 - def);
    const rebase = arr => { const s = arr.slice(a); const b0 = s.find(ok); return s.map(v => ok(v) && b0 ? v / b0 - 1 : null); };
    const series = [{ name: "Radar", farbe: "--s1", v: rebase(D.eq), breite: 2.4 }];
    D.bench.forEach((b, k) => series.push({ name: b.name, farbe: SERIEN_FARBEN[k % 5], v: rebase(b.v), aus: !ausgew.has(b.name), breite: 1.6 }));
    if (opts.kern) series.push({ name: "Nur Kern", farbe: "--s6", v: rebase(D.kern), aus: !mitKern, breite: 1.4, strich: "5 4" });
    series[0].flaeche = true; series[0].flaecheBasis = 0; series[0].flaecheOpa = 0.08;
    linie(ch, { x: D.dates.slice(a), series, yfmt: v => pct(v, 0), tipfmt: v => pct(v, 1), hoehe: opts.hoehe || 340, nullLinie: true,
      vlinien: D.live_idx > a ? [{ i: D.live_idx - a, txt: "Live" }] : [], label: "Wertentwicklung" });
    const r = series[0].v[series[0].v.length - 1];
    const vergl = series.slice(1).filter(s => !s.aus).map(s => ({ n: s.name, v: s.v[s.v.length - 1] })).filter(s => ok(s.v));
    unter.innerHTML = `Zeitraum ${bereich}: Radar <b class="${kl(r)}">${pct(r)}</b>` + vergl.map(s => ` · ${esc(s.n)} <b class="${kl(s.v)}">${pct(s.v)}</b>`).join("") +
      (D.live_idx > 0 ? ` · links der gestrichelten Linie: Rückblick mit denselben Regeln` : "");
  };
  zeichneSteuer(); male();
}

/* ============================== Kopf & Tabs ============================== */
const TABS = [["uebersicht", "Übersicht"], ["portfolio", "Portfolio"], ["verlauf", "Verlauf"], ["insider", "Insider"], ["scanner", "Scanner"], ["statistik", "Statistik"], ["lernen", "Lernen"]];
const M = D.meta;
const sp = D.markt.find(m => m.name === "S&P 500");
document.body.insertAdjacentHTML("afterbegin", `
<header class="kopf"><div class="in">
  <div class="zeile1">
    <div class="marke"><div class="logo"><svg viewBox="0 0 24 24" fill="none" stroke="${css("--card")}" stroke-width="2.4" stroke-linecap="round"><path d="M3 17l5-6 4 3 7-9"/></svg></div>
      <div><h1>Radar</h1><div class="stand">Kursstand ${dat(M.stand, true)}<span class="lang"> · aktualisiert ${esc(M.erstellt)} · ${M.universum} Aktien</span></div></div></div>
    <div class="rechts">
      <button class="pill" id="markt-pill" title="Was bedeutet das?"><i style="background:var(${M.regime ? "--good" : "--bad"})"></i>Markt: ${M.regime ? "Aufwärtstrend" : "Abwärtstrend"}</button>
      <button class="ikon" id="thema" aria-label="Hell/Dunkel"><svg viewBox="0 0 24 24" fill="none" stroke-width="2"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg></button>
    </div>
  </div>
  <nav class="tabs">${TABS.map(([id, n]) => `<button data-t="${id}">${n}${id === "portfolio" ? `<span class="zahl">${TRADES.filter(t => t.status === "offen").length}</span>` : ""}${id === "insider" && D.insider.cluster.length ? `<span class="zahl">${D.insider.cluster.length}</span>` : ""}</button>`).join("")}</nav>
</div></header>`);
const main = $("main");
if (M.demo) main.insertAdjacentHTML("afterbegin", '<div class="demo">Demo mit erfundenen Daten – nicht danach handeln.</div>');
TABS.forEach(([id]) => main.insertAdjacentHTML("beforeend", `<section class="tab" id="${id}"></section>`));
const gerendert = {};
const RENDER = {};
function zeige(id) {
  if (!RENDER[id]) id = "uebersicht";
  $$("nav.tabs button").forEach(b => b.classList.toggle("aktiv", b.dataset.t === id));
  $$("section.tab").forEach(s => s.classList.toggle("aktiv", s.id === id));
  if (!gerendert[id]) { RENDER[id]($("#" + id)); gerendert[id] = true; } else neuZeichnen();
  try { history.replaceState(null, "", "#" + id); } catch (e) { }
}
$("nav.tabs").addEventListener("click", ev => { const b = ev.target.closest("button"); if (b) { zeige(b.dataset.t); window.scrollTo({ top: 0 }); } });
$("#thema").addEventListener("click", () => {
  const dunkel = document.documentElement.dataset.theme ? document.documentElement.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.dataset.theme = dunkel ? "light" : "dark"; merke("thema", document.documentElement.dataset.theme);
  $(".logo svg").setAttribute("stroke", css("--card")); neuZeichnen();
});
const gespThema = lies("thema", null); if (gespThema) { document.documentElement.dataset.theme = gespThema; $(".logo svg").setAttribute("stroke", css("--card")); }
$("#markt-pill").addEventListener("click", () => { zeige("uebersicht"); const m = $("#markt-karte"); if (m) m.scrollIntoView({ behavior: "smooth", block: "center" }); });

/* ============================== Übersicht ============================== */
function marktKarte() {
  return `<div class="card c4" id="markt-karte"><div class="ch"><div><h3 class="ct">Marktlage</h3><div class="cs">Index über/unter seiner 200-Tage-Linie</div></div></div>
  ${D.markt.map(m => `<div class="markt-z"><span><i class="ampel" style="background:var(${m.auf ? "--good" : "--bad"})"></i><b>${esc(m.name)}</b></span>
    <span class="${kl(m.abst)}">${pct(m.abst)}</span><span class="mute klein">1M ${pct(m.m1)}</span></div>`).join("")}
  <p class="cs" style="margin:12px 0 0">Aufwärtstrend = Index über seinem Durchschnitt der letzten 200 Handelstage (200-Tage-Linie) – ein klassischer Filter für den <b>langfristigen</b> Trend, kein Tagestrend. Maßgeblich ist der S&amp;P 500: Er liegt aktuell ${sp ? `${pct(Math.abs(sp.abst), 1, false)} ${sp.auf ? "über" : "unter"}` : ""} seiner 200-Tage-Linie.
  ${M.regime ? `Folge: Kauf-Schwelle ${P.SCHWELLE}, freies Geld liegt im S&amp;P-500-ETF.` : `Folge: höhere Kauf-Schwelle (${P.SCHWELLE_RISK_OFF}), freies Geld liegt im Geldmarkt.`}</p></div>`;
}
function heldKarte() {
  const kauf = D.aktionen.find(a => a.typ === "kaufen");
  if (kauf) {
    const t = tradeById[kauf.id], s = sym(t.cur), det = D.tick[t.ticker];
    return `<div class="card c8"><div class="held"><div>
      <span class="badge b-kauf">Kaufsignal</span>
      <div class="gross-tick">${tlink(t.ticker, t.id)}</div><div class="mute">${esc(t.firma)}</div>
      <div class="gross-zahl">${pct(t.gewicht, 0, false)} des Portfolios</div>
      ${M.zeige_euro ? `<div class="mute">≈ ${zahl(kauf.eur, 0)} € ${kauf.stueck > 0 ? `· ca. ${kauf.stueck} Stück` : "· Bruchstücke nutzen"}</div>` : ""}
      <ul class="schritte"><li><span>Kaufen</span><span>morgen zur Eröffnung, Limit ${zahl(t.limit)} ${s}</span></li>
        <li><span>Stopp-Order danach</span><span>ca. ${zahl(t.stopp_hinweis)} ${s}</span></li>
        ${t.ziel_hinweis ? `<li><span>Gewinnziel (Limit-Verkauf)</span><span>ca. ${zahl(t.ziel_hinweis)} ${s} (${pct(t.ziel_hinweis / t.signal_kurs - 1, 1)})</span></li>` : ""}
        <li><span>Plan</span><span>bis ${t.parameter.HALTEDAUER} Handelstage${t.ziel_hinweis ? "" : ", Stopp wird nachgezogen"}</span></li></ul>
    </div><div>
      <div class="lbl" style="margin-bottom:8px">Überzeugung ${Math.round(t.score)} / 100</div>${scoreBar(t.komp, t.parameter.SCHWELLE)}
      <ul class="gruende">${t.gruende.map(g => `<li>${esc(g)}</li>`).join("")}</ul>
      ${det ? `<div id="held-chart" style="margin-top:10px"></div>` : ""}
    </div></div></div>`;
  }
  const k = D.scanner[0];
  return `<div class="card c8"><span class="badge b-neutral">Heute</span><p class="ruhe">Nichts Neues kaufen</p>
    <div class="ink2">${P.PEAD_AKTIV === false && P.INSIDER_TRIGGER === false && !P.MOMENTUM_TRIGGER && !P.HOCH_TRIGGER && !P.UMKEHR_TRIGGER && !P.NEG_KAUF_TRIGGER ? "Das Forschungslabor findet in den echten Daten zurzeit keinen belegten Vorteil. Deshalb kauft der Radar keine Einzelaktien – das Geld bleibt im ETF (Details im Reiter Lernen)." : `Kein Signal ist stark genug. Freies Geld bleibt im ${M.regime ? "S&amp;P-500-ETF" : "Geldmarkt"}.`}</div>
    ${k ? `<div style="margin-top:18px"><div class="lbl" style="margin-bottom:8px">Stärkster Kandidat</div>
      <div style="display:flex;justify-content:space-between;gap:12px;align-items:baseline"><span>${tlink(k.t)} <span class="mute">${esc(k.f)}</span></span><b>${Math.round(k.sc)}</b></div>
      <div style="margin:8px 0">${scoreBar(k.komp, M.schwelle)}</div><div class="cs">${esc(k.status)}</div></div>` : ""}</div>`;
}
RENDER.uebersicht = el => {
  const st = D.stats, r = st.radar || {}, tk = st.trades || {};
  const bestB = Object.entries(st.bench).map(([n, b]) => ({ n, v: b.gesamt })).filter(b => ok(b.v)).sort((a, b) => b.v - a.v)[0];
  const offen = TRADES.filter(t => t.status === "offen");
  el.innerHTML = `<div class="grid">${heldKarte()}${marktKarte()}</div>
  <div class="kpis">
    <div class="kpi"><div class="k">Radar seit ${datKurz(M.start)}</div><div class="v ${kl(r.gesamt)}">${pct(r.gesamt)}</div><div class="n">${pct(r.cagr)} pro Jahr</div></div>
    ${bestB ? `<div class="kpi"><div class="k">vs. ${esc(bestB.n)} (bester Index)</div><div class="v ${kl(r.gesamt - bestB.v)}">${pct(r.gesamt - bestB.v)}</div><div class="n">${esc(bestB.n)}: ${pct(bestB.v)}</div></div>` : ""}
    <div class="kpi"><div class="k">Sharpe ${tippI("Rendite pro Einheit Schwankung (über Geldmarktzins). Über 1 gilt als gut, über 2 als sehr gut.")}</div><div class="v">${zahl(r.sharpe)}</div><div class="n">Sortino ${zahl(r.sortino)}</div></div>
    <div class="kpi"><div class="k">Max. Rückgang</div><div class="v neg">${pct(r.maxdd)}</div><div class="n">längste Erholung ${r.dd_dauer || 0} Tage</div></div>
    <div class="kpi"><div class="k">Trefferquote</div><div class="v">${pct(tk.trefferquote, 0, false)}</div><div class="n">${tk.anzahl || 0} Trades · PF ${zahl(tk.profit_factor)}</div></div>
    <div class="kpi"><div class="k">Einzelaktien</div><div class="v">${pct(1 - D.kern_w, 0, false)}</div><div class="n">${offen.length} Position${offen.length === 1 ? "" : "en"} · Rest ${M.regime ? "ETF" : "Geldmarkt"}</div></div>
  </div>
  <div class="grid"><div class="card c12"><div class="ch"><div><h3 class="ct">Wertentwicklung</h3><div class="cs">Radar gegen Indizes – Indizes an- und ausschalten, Zeitraum wählen</div></div></div><div id="ue-perf"></div></div></div>
  <div class="grid">
    <div class="card c6"><div class="ch"><h3 class="ct">Aufgaben</h3></div>${aufgaben()}</div>
    <div class="card c6"><div class="ch"><div><h3 class="ct">Top-Kandidaten</h3><div class="cs">Schwelle heute ${M.schwelle} – Details im Scanner</div></div><button class="chip" data-geh="scanner">Scanner ›</button></div>
      ${D.scanner.slice(0, 6).map(k => `<div style="padding:9px 0;border-top:1px solid var(--line2)"><div style="display:flex;justify-content:space-between;gap:10px;margin-bottom:6px"><span>${tlink(k.t)} <span class="mute klein">${esc(k.f)}</span></span><b>${Math.round(k.sc)}</b></div>${scoreBar(k.komp, M.schwelle)}</div>`).join("") || '<div class="leer">Keine Kandidaten</div>'}
    </div>
  </div>
  ${D.oddlot && D.oddlot.length ? `<div class="grid"><div class="card c12"><div class="ch"><div><h3 class="ct">Sonderchancen · Odd-Lot-Angebote</h3><div class="cs">US-Rückkäufe mit Vorrang für Aktionäre unter 100 Aktien – separat vom Portfolio prüfen</div></div></div>
    <div class="tw"><table class="tbl"><thead><tr><th class="l">Firma</th><th class="l">Ticker</th><th>Meldung</th><th>Dokument</th></tr></thead><tbody>
    ${D.oddlot.slice(0, 8).map(o => `<tr><td class="l">${esc(o.firma)}</td><td class="l">${esc(o.ticker.join(", ") || "–")}</td><td>${dat(o.datum, true)}</td><td><a href="${esc(o.link)}" target="_blank" rel="noopener">SEC ›</a></td></tr>`).join("")}</tbody></table></div></div></div>` : ""}
  ${D.hinweise && D.hinweise.length ? `<div class="grid"><div class="card c12"><h3 class="ct" style="margin-bottom:8px">Hinweise</h3>${D.hinweise.map(h => `<div class="cs">• ${esc(h)}</div>`).join("")}</div></div>` : ""}
  ${fuss()}`;
  perfChart($("#ue-perf"), { hoehe: 360 });
  const kauf = D.aktionen.find(a => a.typ === "kaufen");
  if (kauf && $("#held-chart")) tickerChart($("#held-chart"), tradeById[kauf.id].ticker, { tage: 90, hoehe: 200, trade: tradeById[kauf.id], kompakt: true });
};
function aufgaben() {
  const z = [];
  D.aktionen.forEach(a => {
    const t = tradeById[a.id], s = sym(t.cur);
    if (a.typ === "kaufen") z.push(`<li class="aufgabe"><span class="badge b-kauf">Kaufen</span><span>${tlink(t.ticker, t.id)} – ${pct(t.gewicht, 0, false)} des Portfolios zur Eröffnung, Limit ${zahl(t.limit)} ${s}</span></li>`);
    if (a.typ === "verkaufen") z.push(`<li class="aufgabe"><span class="badge b-verk">Verkaufen</span><span>${tlink(t.ticker, t.id)} zur Eröffnung – ${esc(a.text)}</span></li>`);
    if (a.typ === "gestoppt") z.push(`<li class="aufgabe"><span class="badge b-verk">Ausgestoppt</span><span>${tlink(t.ticker, t.id)} bei ca. ${zahl(t.ausstieg_kurs)} ${s} (${pct(t.ergebnis)}). Falls deine Stopp-Order nicht lief: morgen verkaufen.</span></li>`);
    if (a.typ === "stopp") z.push(`<li class="aufgabe"><span class="badge b-neutral">Stopp hoch</span><span>${tlink(t.ticker, t.id)} Stopp auf ${zahl(t.stopp)} ${s} anheben</span></li>`);
  });
  return z.length ? `<ul class="liste">${z.join("")}</ul>` : '<div class="leer">Heute nichts zu tun. Nichts tun ist auch eine Entscheidung.</div>';
}
function fuss() {
  return `<div class="fuss">Regeln: Kauf ab Score ${P.SCHWELLE} (bei Abwärtstrend ${P.SCHWELLE_RISK_OFF}), max. ${P.MAX_NEU_PRO_TAG} neue Empfehlung pro Tag und ${P.MAX_POSITIONEN} Positionen,
  Größe ${Math.round(P.GEWICHT_MIN * 100)}–${Math.round(P.GEWICHT_MAX * 100)} % je nach Score, max. ${Math.round(P.MAX_VERLUST_PRO_TRADE * 100)} % Portfolio-Verlust pro Trade bis zum Stopp.
  Freies Geld liegt im S&amp;P-500-ETF (bei Abwärtstrend im Geldmarkt). Musterdepot inkl. ${pct(P.KOSTEN, 1, false)} Kosten je Order, ohne Steuern und Dividenden; Indizes als Kursindex.
  Der Rückblick nutzt heutige Indexmitglieder und ist daher geschönt. Daten: Yahoo Finance, SEC EDGAR, BaFin. Kein Anlagerat.</div>`;
}
document.addEventListener("click", ev => { const g = ev.target.closest("[data-geh]"); if (g) { zeige(g.dataset.geh); window.scrollTo({ top: 0 }); } });

/* ============================== Ticker-Chart (Kurs mit Ereignissen) ============================== */
function tickerChart(host, t, o) {
  const d = D.tick[t]; if (!d) { host.innerHTML = '<div class="leer">Kein Kursverlauf verfügbar</div>'; return; }
  const n = d.c.length, a = Math.max(0, n - (o.tage || n));
  const x = D.tdates.slice(D.tdates.length - n).slice(a);
  const c = d.c.slice(a);
  const series = [{ name: "Kurs", farbe: "--ink", v: c, breite: 1.8, fmt: v => zahl(v) + " " + sym(d.cur) }];
  if (!o.kompakt) series.push({ name: "200-Tage-Linie", farbe: "--ink3", v: d.sma.slice(a), breite: 1.2, strich: "4 4", fmt: v => zahl(v) + " " + sym(d.cur) });
  const marker = [], hlinien = [];
  const im = i => i - a;
  if (!o.nurTrade) {
    d.ev.forEach(e => {
      const i = im(e.i); if (i < 0) return;
      if (e.typ === "sprung") marker.push({ i, v: c[i], form: "punkt", farbe: "--s2", txt: e.txt, r: 5 });
      if (e.typ === "neg") marker.push({ i, v: c[i], form: "punkt", farbe: "--bad", txt: e.txt, r: 5 });
      if (e.typ === "hoch") marker.push({ i, v: c[i], form: "raute", farbe: "--s4", txt: e.txt, r: 5 });
    });
    d.ins.forEach(e => {
      const i = im(e.i); if (i < 0 || !ok(c[i])) return;
      marker.push({ i, v: c[i], form: e.typ === "Kauf" ? "auf" : "ab", farbe: e.typ === "Kauf" ? "--s3" : "--s5", r: 4,
        txt: `Insider-${e.typ}: ${e.n} (${e.k}) ${geld(e.w, e.cur)}${e.plan ? " · Sparplan" : ""}` });
    });
  }
  const tr = o.trade;
  (tr ? [tr] : d.trades.map(x => tradeById[x.id])).forEach(t2 => {
    if (!t2 || !t2.einstieg_datum) return;
    const iE = x.indexOf(t2.einstieg_datum);
    if (iE >= 0) marker.push({ i: iE, v: t2.einstieg_kurs, form: "punkt", farbe: "--good", r: 6, txt: `Radar-Kauf zu ${zahl(t2.einstieg_kurs)} ${sym(d.cur)}` });
    if (t2.status === "geschlossen") {
      const iA = x.indexOf(t2.ausstieg_datum);
      if (iA >= 0) marker.push({ i: iA, v: t2.ausstieg_kurs, form: "punkt", farbe: t2.ergebnis > 0 ? "--good" : "--bad", r: 6, txt: `Radar-Verkauf zu ${zahl(t2.ausstieg_kurs)} ${sym(d.cur)} (${pct(t2.ergebnis)}) – ${t2.ausstieg_grund}` });
    }
  });
  if (tr && tr.einstieg_datum && tr.status !== "verpasst") {
    hlinien.push({ v: tr.einstieg_kurs, farbe: "--good", txt: "Einstieg", strich: "6 5" });
    if (tr.status === "offen") hlinien.push({ v: tr.stopp, farbe: "--bad", txt: "Stopp", strich: "4 4" });
    if (tr.status === "offen" && tr.ziel) hlinien.push({ v: tr.ziel, farbe: "--s1", txt: "Ziel", strich: "2 4" });
  } else if (tr && tr.status === "geplant") {
    hlinien.push({ v: tr.limit, farbe: "--good", txt: "Limit", strich: "6 5" });
    hlinien.push({ v: tr.stopp_hinweis, farbe: "--bad", txt: "Stopp", strich: "4 4" });
  }
  linie(host, { x, series, marker, hlinien, hoehe: o.hoehe || 320, yfmt: v => zahl(v, v >= 100 ? 0 : 2), label: `Kursverlauf ${t}` });
}

/* ============================== Ticker-Detail (Modal) ============================== */
document.body.insertAdjacentHTML("beforeend", `<div class="modal" id="modal"><div class="blatt"><div class="blatt-kopf"><div id="m-kopf"></div><button class="schliessen" aria-label="Schließen">×</button></div><div class="blatt-inhalt" id="m-inhalt"></div></div></div>`);
const modal = $("#modal");
const schliessen = () => { modal.classList.remove("offen"); document.body.style.overflow = ""; };
modal.addEventListener("click", ev => { if (ev.target === modal || ev.target.closest(".schliessen")) schliessen(); });
document.addEventListener("keydown", ev => { if (ev.key === "Escape") schliessen(); });
document.addEventListener("click", ev => {
  const l = ev.target.closest("[data-ticker]"); if (!l) return;
  ev.preventDefault(); detail(l.dataset.ticker, l.dataset.trade ? +l.dataset.trade : null);
});
const KOMP_TEXT = {
  M: "Wie stark die Aktie in den letzten 6–12 Monaten im Vergleich zu allen anderen lief (risikobereinigt, nur im Aufwärtstrend).",
  P: "Positiver Kurssprung mit hohem Volumen (meist nach Quartalszahlen), dessen Niveau gehalten wird. Solche Aktien laufen oft wochenlang weiter (Post-Earnings-Drift).",
  I: "Mehrere Vorstände/Direktoren kaufen mit eigenem Geld. Sparpläne (10b5-1) zählen nicht. Am stärksten bei Clustern und CEO/CFO.",
  H: "Ausbruch auf ein neues 52-Wochen-Hoch mit erhöhtem Volumen – Anleger verankern sich am alten Hoch, ein Ausbruch setzt sich oft fort.",
};
function detail(t, tradeId) {
  const d = D.tick[t], tr = tradeId ? tradeById[tradeId] : null;
  modal.classList.add("offen"); document.body.style.overflow = "hidden";
  $("#modal .blatt").scrollTop = 0; modal.scrollTop = 0;
  if (!d) {
    $("#m-kopf").innerHTML = `<div class="gross-tick" style="margin:0">${esc(t)}</div>`;
    $("#m-inhalt").innerHTML = `<div class="leer">Für diese Aktie liegen keine Detaildaten vor.</div>`; return;
  }
  const f = d.fakten, s = sym(d.cur);
  $("#m-kopf").innerHTML = `<div style="display:flex;gap:14px;align-items:baseline;flex-wrap:wrap"><span class="gross-tick" style="margin:0">${esc(t)}</span>
    <span style="font-size:20px;font-weight:650">${zahl(f.kurs)} ${s}</span><span class="${kl(f.d1)}" style="font-weight:600">${pct(f.d1)}</span></div>
    <div class="mute">${esc(d.f)} · Score heute <b style="color:var(--ink)">${ok(d.sc) ? Math.round(d.sc) : "–"}</b></div>`;
  const komp = KOMP.map(k => { const v = 100 * P[k.gew] * (d.komp[k.k] || 0), max = 100 * P[k.gew];
    return `<div class="komp"><b>${k.name}</b><div class="bahn"><i style="width:${max ? v / max * 100 : 0}%;background:var(${k.farbe})"></i></div><span style="text-align:right;font-weight:650">${Math.round(v)}<span class="mute">/${Math.round(max)}</span></span><div class="erk">${KOMP_TEXT[k.k]}</div></div>`; }).join("");
  const sprung = d.sprung ? `Letzter Kurssprung am ${dat(d.sprung.d)}: ${pct(d.sprung.plus)} bei ${zahl(d.sprung.vf, 1)}× Volumen, vor ${d.sprung.tage} Handelstagen.` : "Kein aktueller positiver Kurssprung.";
  const insSig = d.ins_sig ? `Insider-Anomalie ${d.ins_sig.a ?? "–"}/100: ${d.ins_sig.n} Insider kauften zuletzt für ${geld(d.ins_sig.w, d.cur)} (${d.ins_sig.kat.join(", ")})${(d.ins_sig.g || []).length ? " – " + d.ins_sig.g.join(", ") : ""}.` : "Kein auffälliger Insider-Kauf (normale Käufe zählen nicht).";
  const radarT = d.trades.map(x => tradeById[x.id]).filter(Boolean);
  $("#m-inhalt").innerHTML = `
  ${tr ? tradeBox(tr) : ""}
  <div class="grid">
    <div class="card c8"><div class="ch"><div><h3 class="ct">Kursverlauf mit Ereignissen</h3><div class="cs">Antippen/Überfahren für Details</div></div><div class="seg" id="m-ber">${[["3M", 63], ["6M", 126], ["1J", 0]].map(([n, v], k) => `<button data-v="${v}" class="${k === 2 ? "an" : ""}">${n}</button>`).join("")}</div></div>
      <div id="m-chart"></div>
      <div class="legende" style="margin-top:10px"><span><i style="background:var(--good);border-radius:50%"></i>Radar Kauf/Verkauf</span><span><i style="background:var(--s2);border-radius:50%"></i>Kurssprung</span><span><i style="background:var(--bad);border-radius:50%"></i>Kursrutsch</span><span><i style="background:var(--s3)"></i>Insider-Kauf ▲</span><span><i style="background:var(--s5)"></i>Insider-Verkauf ▼</span><span><i style="background:var(--s4);transform:rotate(45deg)"></i>52W-Hoch</span></div></div>
    <div class="card c4"><h3 class="ct" style="margin-bottom:6px">Warum dieser Score?</h3>
      ${d.status ? `<div class="box ${d.status.startsWith("KAUF") ? "ok" : "warn"}" style="margin:8px 0 6px">${esc(d.status)}</div>` : ""}
      ${f.neg_sperre ? `<div class="box fehler" style="margin:6px 0">Kürzlicher Kursrutsch mit Volumen – Käufe 20 Tage gesperrt.</div>` : ""}
      ${komp}</div>
  </div>
  <div class="grid">
    <div class="card c6"><h3 class="ct" style="margin-bottom:12px">Kennzahlen</h3><div class="fakten">
      <div><span>1 Monat</span><b class="${kl(f.m1)}">${pct(f.m1)}</b></div><div><span>6 Monate</span><b class="${kl(f.m6)}">${pct(f.m6)}</b></div>
      <div><span>12 Monate</span><b class="${kl(f.m12)}">${pct(f.m12)}</b></div><div><span>Momentum-Rang</span><b>${ok(f.rang) && f.rang > 0 ? "besser als " + Math.round(f.rang * 100) + " %" : "kein Aufwärtstrend"}</b></div>
      <div><span>Schwankung p.a.</span><b>${pct(f.vola, 0, false)}</b></div><div><span>Abstand 200-Tage-Linie</span><b class="${kl(f.dist200)}">${pct(f.dist200)}</b></div>
      <div><span>vom 52W-Hoch</span><b>${pct(f.vom_hoch)}</b></div><div><span>Ø Tagesumsatz</span><b>${geld(f.umsatz, d.cur)}</b></div></div>
      <p class="cs" style="margin:14px 0 0">${esc(sprung)} ${esc(insSig)}</p></div>
    <div class="card c6"><h3 class="ct" style="margin-bottom:6px">Score-Verlauf</h3><div class="cs">Schwarzer Strich = Kauf-Schwelle</div><div id="m-score"></div></div>
  </div>
  <div class="grid"><div class="card c12"><div class="ch"><h3 class="ct">Insider-Transaktionen</h3><span class="cs">${d.ins.length} im letzten Jahr</span></div>
    ${d.ins.length ? `<div class="tw"><table class="tbl"><thead><tr><th class="l">Datum</th><th class="l">Insider</th><th class="l">Rolle</th><th class="l">Art</th><th>Wert</th><th>Preis</th><th>seitdem</th></tr></thead><tbody>
    ${d.ins.map(e => `<tr><td class="l">${dat(e.d, true)}</td><td class="l">${esc(e.n)}</td><td class="l">${esc(e.k)} <span class="mute klein">${esc(e.r)}</span></td><td class="l"><span class="badge ${e.typ === "Kauf" ? "b-kauf" : "b-verk"}">${e.typ}</span>${e.plan ? ' <span class="mute klein">Sparplan</span>' : ""}</td><td>${geld(e.w, e.cur)}</td><td>${zahl(e.p)}</td><td class="${kl(f.kurs / e.p - 1)}">${pct(f.kurs / e.p - 1)}</td></tr>`).join("")}</tbody></table></div>` : '<div class="leer">Keine gemeldeten Insider-Transaktionen</div>'}</div></div>
  ${radarT.length ? `<div class="grid"><div class="card c12"><h3 class="ct" style="margin-bottom:10px">Radar-Historie mit ${esc(t)}</h3>${verlaufTabelle(radarT, false)}</div></div>` : ""}`;
  const chartEl = $("#m-chart");
  const zeichneK = tage => tickerChart(chartEl, t, { tage, hoehe: 340, trade: tr });
  zeichneK(0);
  $("#m-ber").addEventListener("click", ev => { const b = ev.target.closest("button"); if (!b) return; $$("#m-ber button").forEach(x => x.classList.toggle("an", x === b)); zeichneK(+b.dataset.v); });
  const sx = D.tdates.slice(D.tdates.length - d.score.length);
  linie($("#m-score"), { x: sx, series: [{ name: "Score", farbe: "--s1", v: d.score, flaeche: true, flaecheBasis: 0 }], hlinien: [{ v: M.schwelle, farbe: "--ink", strich: "2 3" }], hoehe: 200, yfmt: v => zahl(v, 0), nullLinie: true });
}
function tradeBox(t) {
  const s = sym(t.cur);
  const erg = t.status === "geschlossen" ? t.ergebnis : t.status === "offen" ? t.kurs / t.einstieg_kurs - 1 : null;
  return `<div class="card" style="margin-bottom:16px"><div class="ch"><div><h3 class="ct">Empfehlung vom ${dat(t.signal_datum, true)} ${t.modus === "Live" ? '<span class="mtag live">Live</span>' : '<span class="mtag">Rückblick</span>'}</h3>
    <div class="cs">${t.typen.map(typTag).join("")}</div></div><div style="text-align:right"><div class="${kl(erg)}" style="font-size:24px;font-weight:700">${pct(erg)}</div><div class="cs">${esc(t.status === "geschlossen" ? t.ausstieg_grund : t.status === "offen" ? "läuft · Tag " + t.tage : t.status === "geplant" ? "Kauf zur nächsten Eröffnung" : t.ausstieg_grund || "")}</div></div></div>
    <div class="fakten"><div><span>Score</span><b>${Math.round(t.score)}</b></div><div><span>Gewicht</span><b>${pct(t.gewicht, 0, false)}</b></div>
    <div><span>Einstieg</span><b>${t.einstieg_datum ? dat(t.einstieg_datum) + " · " + zahl(t.einstieg_kurs) + " " + s : "–"}</b></div>
    <div><span>Ausstieg</span><b>${t.ausstieg_kurs ? dat(t.ausstieg_datum) + " · " + zahl(t.ausstieg_kurs) + " " + s : "–"}</b></div>
    ${t.status === "offen" ? `<div><span>Stopp</span><b>${zahl(t.stopp)} ${s}</b></div>` : ""}
    ${ok(t.markt) ? `<div><span>S&amp;P 500 gleiche Zeit</span><b class="${kl(t.markt)}">${pct(t.markt)}</b></div><div><span>Mehrrendite</span><b class="${kl(t.ueber_markt)}">${pct(t.ueber_markt)}</b></div>` : ""}</div>
    <ul class="gruende">${t.gruende.map(g => `<li>${esc(g)}</li>`).join("")}</ul></div>`;
}

/* ============================== Portfolio ============================== */
RENDER.portfolio = el => {
  const offen = TRADES.filter(t => t.status === "offen").sort((a, b) => b.anteil - a.anteil);
  const geplant = TRADES.filter(t => t.status === "geplant");
  const farben = ["--s1", "--s2", "--s3", "--s4", "--s5", "--s7"];
  const teile = offen.map((t, k) => ({ name: t.ticker, w: t.anteil, farbe: farben[k % 6] }));
  teile.push({ name: M.regime ? "S&P-500-ETF (Kern)" : "Geldmarkt (Kern)", w: D.kern_w, farbe: "--chip" });
  const gv = offen.reduce((a, t) => a + t.anteil * t.lauf / (1 + t.lauf), 0);
  el.innerHTML = `<div class="grid">
    <div class="card c4"><div class="ch"><div><h3 class="ct">Aufteilung</h3><div class="cs">Anteil am Strategie-Portfolio</div></div></div><div id="pf-donut"></div>
      <div class="legende" style="margin-top:14px;justify-content:center">${teile.map(t => `<span><i style="background:var(${t.farbe});${t.farbe === "--chip" ? "outline:1px solid var(--line)" : ""}"></i>${esc(t.name)} ${pct(t.w, 0, false)}</span>`).join("")}</div></div>
    <div class="card c8"><div class="ch"><div><h3 class="ct">Positionen</h3><div class="cs">${offen.length} offen${geplant.length ? ` · ${geplant.length} Kauf morgen` : ""} · unrealisiert ${pct(gv, 2)} vom Portfolio</div></div></div>
      ${offen.length || geplant.length ? `<div class="tw"><table class="tbl"><thead><tr><th class="l">Aktie</th><th>Anteil</th><th>Einstieg</th><th>Kurs</th><th>G/V</th><th>Stopp</th><th>bis Stopp</th><th>Tag</th></tr></thead><tbody>
      ${offen.map(t => `<tr class="klick" data-ticker="${esc(t.ticker)}" data-trade="${t.id}"><td class="l"><div class="tick">${esc(t.ticker)}</div><div class="firma">${esc(t.firma)}</div></td><td>${pct(t.anteil, 1, false)}</td><td>${zahl(t.einstieg_kurs)}</td><td>${zahl(t.kurs)}</td><td class="${kl(t.lauf)}"><b>${pct(t.lauf)}</b></td><td>${zahl(t.stopp)}</td><td class="neg">${pct(t.stopp / t.kurs - 1)}</td><td>${t.tage}/${t.parameter.HALTEDAUER}</td></tr>`).join("")}
      ${geplant.map(t => `<tr class="klick" data-ticker="${esc(t.ticker)}" data-trade="${t.id}"><td class="l"><div class="tick">${esc(t.ticker)} <span class="badge b-kauf">Kauf morgen</span></div><div class="firma">${esc(t.firma)}</div></td><td>${pct(t.gewicht, 0, false)}</td><td>Limit ${zahl(t.limit)}</td><td>${zahl(t.signal_kurs)}</td><td>–</td><td>${zahl(t.stopp_hinweis)}</td><td></td><td>0</td></tr>`).join("")}
      </tbody></table></div>` : `<div class="leer">Keine Einzelaktien – alles im ${M.regime ? "S&amp;P-500-ETF" : "Geldmarkt"}.</div>`}</div>
  </div>
  <div class="grid">${offen.concat(geplant).map(t => posKarte(t)).join("")}</div>${fuss()}`;
  donut($("#pf-donut"), teile, pct(1 - D.kern_w, 0, false), "in Einzelaktien");
  offen.concat(geplant).forEach(t => { const h = $(`#pos-${t.id}`); if (h) tickerChart(h, t.ticker, { tage: Math.max(60, (t.tage || 0) + 40), hoehe: 280, trade: t, kompakt: true }); });
};
function posKarte(t) {
  const s = sym(t.cur), offen = t.status === "offen", r = offen ? t.lauf : null;
  return `<div class="card c6"><div class="pos-kopf"><div><div class="gross">${tlink(t.ticker, t.id)}</div><div class="mute">${esc(t.firma)}</div></div>
    <div style="text-align:right"><div class="gross ${kl(r)}">${offen ? pct(r) : '<span class="badge b-kauf">Kauf morgen</span>'}</div><div class="cs">${offen ? `${pct(t.anteil, 1, false)} · Tag ${t.tage} von ${t.parameter.HALTEDAUER}` : `${pct(t.gewicht, 0, false)} geplant`}</div></div></div>
    <div id="pos-${t.id}" style="margin-top:12px"></div>
    <div class="legende" style="margin:8px 0 12px"><span><i style="background:var(--good);border-radius:50%"></i>Einstieg</span><span><i style="background:var(--bad)"></i>Stopp (gestrichelt)</span><span><i style="background:var(--s3)"></i>Insider</span><span><i style="background:var(--s2);border-radius:50%"></i>Kurssprung</span></div>
    ${offen ? `<div class="fort"><i style="width:${Math.min(100, t.tage / t.parameter.HALTEDAUER * 100)}%"></i></div>` : ""}
    <div class="fakten" style="margin-top:14px">
      <div><span>${offen ? "Einstieg" : "Limit"}</span><b>${offen ? dat(t.einstieg_datum) + " · " + zahl(t.einstieg_kurs) : zahl(t.limit)} ${s}</b></div>
      <div><span>Aktuell</span><b>${zahl(offen ? t.kurs : t.signal_kurs)} ${s}</b></div>
      <div><span>Stopp</span><b>${zahl(offen ? t.stopp : t.stopp_hinweis)} ${s}</b></div>
      <div><span>Abstand zum Stopp</span><b class="neg">${pct((offen ? t.stopp / t.kurs : t.stopp_hinweis / t.signal_kurs) - 1)}</b></div>
      ${(offen ? t.ziel : t.ziel_hinweis) ? `<div><span>Gewinnziel</span><b>${zahl(offen ? t.ziel : t.ziel_hinweis)} ${s}</b></div><div><span>Abstand zum Ziel</span><b class="pos">${pct((offen ? t.ziel / t.kurs : t.ziel_hinweis / t.signal_kurs) - 1)}</b></div>` : ""}
      ${offen ? `<div><span>Höchster Kurs</span><b>${zahl(t.hoechst)} ${s}</b></div><div><span>Gesichert</span><b class="${kl(t.stopp / t.einstieg_kurs - 1)}">${pct(t.stopp / t.einstieg_kurs - 1)}</b></div>` : ""}
    </div>
    <ul class="gruende">${t.gruende.map(g => `<li>${esc(g)}</li>`).join("")}</ul></div>`;
}

/* ============================== Verlauf ============================== */
function ergebnisVon(t) { return t.status === "geschlossen" ? t.ergebnis : t.status === "offen" ? t.kurs / t.einstieg_kurs - 1 : null; }
function verlaufTabelle(liste, karten) {
  const maxA = Math.max(0.05, ...liste.map(t => Math.abs(ergebnisVon(t) || 0)));
  return `<div class="tw"><table class="tbl ${karten ? "karten" : ""}"><thead><tr><th class="l">Aktie</th><th class="l">Signal</th><th class="l">Auslöser</th><th>Gewicht</th><th>Einstieg</th><th>Ausstieg</th><th>Tage</th><th>Ergebnis</th><th>vs. S&amp;P</th><th class="l">Status</th></tr></thead><tbody>
  ${liste.map(t => { const e = ergebnisVon(t), tage = t.status === "offen" ? t.tage : t.ausstieg_datum && t.einstieg_datum ? Math.round((new Date(t.ausstieg_datum) - new Date(t.einstieg_datum)) / 864e5 * 5 / 7) : null;
    const status = t.status === "geschlossen" ? t.ausstieg_grund : t.status === "offen" ? "läuft" : t.status === "geplant" ? "Kauf morgen" : "ausgelassen";
    return `<tr class="klick" data-ticker="${esc(t.ticker)}" data-trade="${t.id}"><td class="l"><div class="tick">${esc(t.ticker)} ${t.modus === "Live" ? '<span class="mtag live">Live</span>' : ""}</div><div class="firma">${esc(t.firma)}</div></td>
    <td class="l m-aus">${dat(t.signal_datum, true)}</td><td class="l m-aus">${t.typen.filter(x => x !== "Momentum").map(typTag).join("") || typTag("Momentum")}</td><td class="m-aus">${pct(t.gewicht, 0, false)}</td>
    <td class="m-aus">${t.einstieg_kurs ? zahl(t.einstieg_kurs) : "–"}</td><td class="m-aus">${t.ausstieg_kurs ? zahl(t.ausstieg_kurs) : "–"}</td><td class="m-aus">${tage ?? "–"}</td>
    <td class="m-r"><span class="ergbar">${ok(e) ? `<b style="width:${Math.round(Math.abs(e) / maxA * 48)}px;background:var(${e > 0 ? "--good" : "--bad"})"></b>` : ""}<span class="${kl(e)}" style="font-weight:650;min-width:62px;display:inline-block">${pct(e)}</span></span></td>
    <td class="m-aus ${kl(t.ueber_markt)}">${pct(t.ueber_markt)}</td><td class="l mute">${esc(status)}${!karten ? "" : ` · ${dat(t.signal_datum)}`}</td></tr>`; }).join("")}
  </tbody></table></div>`;
}
RENDER.verlauf = el => {
  const tk = D.stats.trades || {};
  el.innerHTML = `<div class="kpis">
    <div class="kpi"><div class="k">Empfehlungen</div><div class="v">${TRADES.length}</div><div class="n">${TRADES.filter(t => t.modus === "Live").length} live · ${TRADES.filter(t => t.modus !== "Live").length} Rückblick</div></div>
    <div class="kpi"><div class="k">Trefferquote</div><div class="v">${pct(tk.trefferquote, 0, false)}</div><div class="n">${tk.gewinner || 0} Gewinner · ${tk.verlierer || 0} Verlierer</div></div>
    <div class="kpi"><div class="k">Profit Factor ${tippI("Summe aller Gewinne geteilt durch Summe aller Verluste. Über 1 = profitabel, über 1,5 = gut.")}</div><div class="v">${zahl(tk.profit_factor)}</div><div class="n">Payoff ${zahl(tk.payoff)}</div></div>
    <div class="kpi"><div class="k">Ø Ergebnis je Trade</div><div class="v ${kl(tk.erwartung)}">${pct(tk.erwartung)}</div><div class="n">Ø Gewinn ${pct(tk.avg_gewinn)} · Ø Verlust ${pct(tk.avg_verlust)}</div></div>
    <div class="kpi"><div class="k">Schlägt den S&amp;P 500</div><div class="v">${pct(tk.schlag_markt, 0, false)}</div><div class="n">Ø Mehrrendite ${pct(tk.ueber_markt)}</div></div>
  </div>
  <div class="grid"><div class="card c12"><div class="ch"><div><h3 class="ct">Ergebnis je Empfehlung</h3><div class="cs">Jede Säule ein abgeschlossener Trade, zeitlich sortiert</div></div></div><div id="vl-saeulen"></div></div></div>
  <div class="grid"><div class="card c12">
    <div class="steuer"><div class="chips" id="vl-filter">${[["alle", "Alle"], ["live", "Live"], ["rueck", "Rückblick"], ["offen", "Offen"], ["gew", "Gewinner"], ["verl", "Verlierer"]].map(([f, n], k) => `<span class="chip ${k ? "" : "an"}" data-f="${f}">${n}</span>`).join("")}</div>
    <div style="display:flex;gap:8px;flex-wrap:wrap"><select class="feld" id="vl-typ"><option value="">Alle Auslöser</option><option>Zahlen</option><option>Insider</option><option>Momentum</option><option>Umkehr</option><option>Rücksetzer</option><option>52W-Hoch</option></select>
      <select class="feld" id="vl-sort"><option value="neu">Neueste zuerst</option><option value="best">Bestes Ergebnis</option><option value="schlecht">Schlechtestes Ergebnis</option><option value="score">Höchster Score</option></select>
      <input class="feld" id="vl-suche" placeholder="Ticker suchen …"></div></div>
    <div id="vl-tabelle"></div></div></div>${fuss()}`;
  const gz = TRADES.filter(t => t.status === "geschlossen").sort((a, b) => a.ausstieg_datum < b.ausstieg_datum ? -1 : 1);
  saeulen($("#vl-saeulen"), gz.map(t => ({ v: t.ergebnis * 100, farbe: t.ergebnis > 0 ? "--good" : "--bad",
    txt: `<div class="tk">${esc(t.ticker)} · ${dat(t.ausstieg_datum, true)}</div><div class="tz"><span>Ergebnis</span><b class="${kl(t.ergebnis)}">${pct(t.ergebnis)}</b></div><div class="tz"><span>Grund</span><b>${esc(t.ausstieg_grund)}</b></div>` })),
    { hoehe: 180, yfmt: v => zahl(v, 0) + " %", labels: gz.length ? [{ i: 0, t: datKurz(gz[0].ausstieg_datum) }, { i: gz.length - 1, t: datKurz(gz[gz.length - 1].ausstieg_datum) }] : [] });
  let f = "alle";
  const male = () => {
    const typ = $("#vl-typ").value, q = $("#vl-suche").value.trim().toUpperCase(), so = $("#vl-sort").value;
    let l = TRADES.filter(t => {
      const e = ergebnisVon(t);
      if (f === "live" && t.modus !== "Live") return false; if (f === "rueck" && t.modus === "Live") return false;
      if (f === "offen" && !["offen", "geplant"].includes(t.status)) return false;
      if (f === "gew" && !(e > 0)) return false; if (f === "verl" && !(e <= 0 && ok(e))) return false;
      if (typ && !t.typen.includes(typ)) return false; if (q && !t.ticker.includes(q)) return false; return true;
    });
    if (so === "best") l.sort((a, b) => (ergebnisVon(b) ?? -9) - (ergebnisVon(a) ?? -9));
    if (so === "schlecht") l.sort((a, b) => (ergebnisVon(a) ?? 9) - (ergebnisVon(b) ?? 9));
    if (so === "score") l.sort((a, b) => b.score - a.score);
    $("#vl-tabelle").innerHTML = l.length ? verlaufTabelle(l, true) : '<div class="leer">Keine Empfehlungen für diesen Filter</div>';
  };
  $("#vl-filter").addEventListener("click", ev => { const c = ev.target.closest(".chip"); if (!c) return; f = c.dataset.f; $$("#vl-filter .chip").forEach(x => x.classList.toggle("an", x === c)); male(); });
  ["#vl-typ", "#vl-sort"].forEach(s => $(s).addEventListener("change", male)); $("#vl-suche").addEventListener("input", male);
  male();
};

/* ============================== Insider ============================== */
function ring(v) {
  const r = 26, u = 2 * Math.PI * r, f = v >= 70 ? "--good" : v >= 45 ? "--s4" : "--ink3";
  return `<svg class="ring" viewBox="0 0 64 64"><circle cx="32" cy="32" r="${r}" fill="none" stroke="var(--chip)" stroke-width="7"/><circle cx="32" cy="32" r="${r}" fill="none" stroke="var(${f})" stroke-width="7" stroke-linecap="round" stroke-dasharray="${u * v / 100} ${u}" transform="rotate(-90 32 32)"/><text x="32" y="37" text-anchor="middle" font-size="16" font-weight="700" fill="var(--ink)">${Math.round(v)}</text></svg>`;
}
RENDER.insider = el => {
  const I = D.insider, st = I.status || {};
  const stBox = st.ok ? `<div class="box ok">${st.anzahl} Insider-Transaktionen geladen (${dat(st.von, true)} – ${dat(st.bis, true)}).
      <details style="margin-top:6px"><summary style="cursor:pointer">Quellen</summary>${(st.quellen || []).map(q => `<div class="klein">• ${esc(q)}</div>`).join("")}${(st.luecken || []).map(q => `<div class="klein" style="color:var(--warn)">• Lücke: ${esc(q)}</div>`).join("")}</details></div>`
    : `<div class="box fehler"><b>Insider-Daten wurden nicht geladen.</b>${(st.fehler || []).map(f => `<div class="klein">• ${esc(f)}</div>`).join("")}<div class="klein" style="margin-top:6px">Tipp: In GitHub unter Settings → Secrets das Secret SEC_USER_AGENT prüfen (Format: Vorname Nachname email@domain.de, ohne Umlaute).</div></div>`;
  const fehlerExtra = st.ok && (st.fehler || []).length ? `<div class="box warn" style="margin-top:8px">${st.fehler.map(f => `<div class="klein">• ${esc(f)}</div>`).join("")}</div>` : "";
  const h = I.cluster[0];
  el.innerHTML = `<div class="grid"><div class="card c12"><div class="ch"><div><h3 class="ct">Insider-Radar</h3><div class="cs">USA: SEC Form 4 · Deutschland: BaFin Directors' Dealings (Art. 19 MAR)</div></div></div>
    <p class="erkl">Vorstände und Aufsichtsräte müssen eigene Käufe und Verkäufe melden. Die meisten Käufe sind <b>normal</b> und sagen wenig. Der Radar bewertet deshalb jeden Kauf mit einer <b>Auffälligkeit von 0–100</b> und nutzt nur echte Anomalien ab ${I.grenze || 50} Punkten. Punkte gibt es für: mehrere Insider gleichzeitig (bis 25), die Rolle – CEO/CFO am meisten, Fonds/Großaktionäre am wenigsten (bis 15), den Kauf <b>im Verhältnis zum eigenen Bestand</b> (bis 25), die Größe (bis 15), den ersten Kauf seit über einem Jahr (10, Routinekäufe wie im Vorjahr geben Abzug) und Käufe nach deutlichem Kursrückgang (10). Beispiel: Ein CEO kauft für 50 Tsd. $, besitzt aber schon 50 Mio. $ – das sind +0,1 % auf seinen Bestand und bleibt „normal“. Verkäufe und Sparpläne (10b5-1) zählen nie.</p>${stBox}${fehlerExtra}</div></div>
  ${h ? `<div class="grid"><div class="card c12 ins-held"><div class="held"><div>
      <span class="badge b-kauf">Auffälligste Insider-Aktivität</span>
      <div class="gross-tick">${tlink(h.t)}</div><div class="mute">${esc(h.f)} · ${esc(h.land)}</div>
      <div class="staerke" style="margin-top:16px">${ring(h.staerke)}<div><b>Auffälligkeit ${Math.round(h.staerke)} / 100 · ${esc(h.label)}</b><div class="cs">${h.gruende && h.gruende.length ? esc(h.gruende.join(" · ")) : "keine besonderen Merkmale"}</div></div></div>
      <div class="fakten" style="margin-top:16px"><div><span>Insider</span><b>${h.n}</b></div><div><span>Summe</span><b>${geld(h.w, h.cur)}</b></div>
        <div><span>Rollen</span><b>${esc(h.kat.join(", "))}</b></div><div><span>Ø Kaufpreis</span><b>${zahl(h.avg)} ${sym(h.cur)}</b></div>
        <div><span>Kurs jetzt</span><b>${zahl(h.kurs)} ${sym(h.cur)}</b></div><div><span>seit Kauf</span><b class="${kl(h.seit)}">${pct(h.seit)}</b></div>
        <div><span>Letzte Meldung</span><b>${dat(h.letzte, true)}</b></div><div><span>Radar-Score</span><b>${ok(h.score) ? Math.round(h.score) : "–"}</b></div></div>
      <div class="cs" style="margin-top:12px">${esc(h.namen.join(" · "))}</div>
    </div><div id="ins-held-chart"></div></div></div></div>
    <div class="grid">${I.cluster.slice(1, 7).map(c => `<div class="card c4 mini-karte" data-ticker="${esc(c.t)}"><div style="display:flex;justify-content:space-between;gap:10px">
      <div><div class="tick" style="font-size:18px">${esc(c.t)}</div><div class="firma">${esc(c.f)}</div></div>${ring(c.staerke).replace('class="ring"', 'class="ring" style="width:48px;height:48px"')}</div>
      <div class="fakten" style="margin-top:10px;grid-template-columns:1fr 1fr"><div><span>Insider</span><b>${c.n} · ${esc(c.kat.join(", "))}</b></div><div><span>Summe</span><b>${geld(c.w, c.cur)}</b></div>
      <div><span>seit Kauf</span><b class="${kl(c.seit)}">${pct(c.seit)}</b></div><div><span>Letzte</span><b>${dat(c.letzte)}</b></div></div>
      <div class="klein mute" style="margin-top:10px">${c.gruende && c.gruende.length ? esc(c.gruende.slice(0, 3).join(" · ")) : esc(c.label)}</div></div>`).join("")}</div>` : ""}
  ${h && h.staerke < (I.grenze || 50) ? `<div class="grid"><div class="card c12"><div class="box warn">Zurzeit keine echte Insider-Anomalie: Selbst die auffälligste Aktivität liegt unter ${I.grenze || 50} Punkten. Das ist normal – starke Signale gibt es nur ein paar Mal im Monat.</div></div></div>` : ""}
  <div class="grid"><div class="card c12"><div class="ch"><div><h3 class="ct">Alle Transaktionen</h3><div class="cs">Käufe ab 10 Tsd., Verkäufe ab 250 Tsd. · Spalte „Auffällig“: Bewertung je Einzelkauf · antippen für Details</div></div><span class="cs" id="ins-anz"></span></div>
    <div class="steuer" style="align-items:flex-start"><div style="display:flex;flex-direction:column;gap:8px">
      <div class="chips" id="ins-typ">${[["", "Alle"], ["Kauf", "Käufe"], ["Verkauf", "Verkäufe"]].map(([v, n], k) => `<span class="chip ${k === 1 ? "an" : ""}" data-v="${v}">${n}</span>`).join("")}</div>
      <div class="chips" id="ins-rolle">${["CEO", "CFO", "Vorstand", "Direktor", "10%-Eigner", "Sonstige"].map(r => `<span class="chip" data-v="${r}">${r}</span>`).join("")}</div></div>
      <div style="display:flex;gap:8px;flex-wrap:wrap"><select class="feld" id="ins-land"><option value="">Alle Länder</option><option value="USA">USA</option><option value="DE">Deutschland</option></select>
        <select class="feld" id="ins-min"><option value="0">Jeder Betrag</option><option value="100000">ab 100 Tsd.</option><option value="1000000">ab 1 Mio.</option><option value="10000000">ab 10 Mio.</option></select>
        <label class="chip" style="cursor:pointer"><input type="checkbox" id="ins-plan" checked style="margin:0"> Sparpläne ausblenden</label>
        <label class="chip" style="cursor:pointer"><input type="checkbox" id="ins-auff" style="margin:0"> nur auffällige (ab ${I.grenze || 50})</label>
        <input class="feld" id="ins-suche" placeholder="Ticker oder Name …"></div></div>
    <div id="ins-tabelle"></div></div></div>${fuss()}`;
  if (h) tickerChart($("#ins-held-chart"), h.t, { tage: 126, hoehe: 300 });
  let typ = "Kauf"; const rollen = new Set(); let sortK = "d", sortAuf = false, limit = 100;
  const male = () => {
    const land = $("#ins-land").value, min = +$("#ins-min").value, plan = $("#ins-plan").checked, auff = $("#ins-auff").checked, q = $("#ins-suche").value.trim().toUpperCase();
    let l = I.feed.filter(x => (!typ || x.typ === typ) && (!rollen.size || rollen.has(x.k)) && (!land || x.land === land) && x.w >= min && !(plan && x.plan)
      && (!auff || (x.a ?? 0) >= (I.grenze || 50))
      && (!q || x.t.includes(q) || x.n.toUpperCase().includes(q) || x.f.toUpperCase().includes(q)));
    l.sort((a, b) => { const va = a[sortK], vb = b[sortK]; const r = va == null ? 1 : vb == null ? -1 : va < vb ? -1 : va > vb ? 1 : 0; return sortAuf ? r : -r; });
    $("#ins-anz").textContent = `${l.length} Transaktionen · Summe ${geld(l.reduce((a, b) => a + (b.cur === "USD" ? b.w : b.w * (M.eurusd || 1)), 0), "USD")}`;
    const th = (k, n, c) => `<th class="sort ${c || ""}" data-k="${k}">${n}${sortK === k ? (sortAuf ? " ↑" : " ↓") : ""}</th>`;
    $("#ins-tabelle").innerHTML = l.length ? `<div class="tw"><table class="tbl"><thead><tr>${th("d", "Meldung", "l")}${th("t", "Aktie", "l")}${th("n", "Insider", "l")}${th("k", "Rolle", "l")}<th class="l">Art</th>${th("w", "Wert")}${th("a", "Auffällig")}${th("p", "Preis")}${th("seit", "seitdem")}${th("score", "Score")}<th>Land</th></tr></thead><tbody>
      ${l.slice(0, limit).map(x => `<tr class="klick" data-ticker="${esc(x.t)}"><td class="l">${dat(x.d, true)}</td><td class="l"><div class="tick">${esc(x.t)}</div><div class="firma">${esc(x.f)}</div></td><td class="l">${esc(x.n)}</td><td class="l">${esc(x.k)}<div class="firma">${esc(x.r)}</div></td>
      <td class="l"><span class="badge ${x.typ === "Kauf" ? "b-kauf" : "b-verk"}">${x.typ}</span>${x.plan ? ' <span class="mute klein">Plan</span>' : ""}</td><td><b>${geld(x.w, x.cur)}</b></td><td title="${esc((x.ag || []).join(" · "))}">${ok(x.a) ? `<span class="badge ${x.a >= 70 ? "b-kauf" : x.a >= (I.grenze || 50) ? "b-warn" : "b-neutral"}">${Math.round(x.a)} ${x.a >= 70 ? "stark" : x.a >= (I.grenze || 50) ? "auffällig" : "normal"}</span>` : '<span class="mute">–</span>'}</td><td>${zahl(x.p)}</td><td class="${kl(x.seit)}">${pct(x.seit)}</td><td>${ok(x.score) ? Math.round(x.score) : "–"}</td><td>${esc(x.land)}</td></tr>`).join("")}
      </tbody></table></div>${l.length > limit ? `<button class="mehr" id="ins-mehr">Weitere ${Math.min(100, l.length - limit)} anzeigen</button>` : ""}` : '<div class="leer">Keine Transaktionen für diesen Filter</div>';
    const mb = $("#ins-mehr"); if (mb) mb.addEventListener("click", () => { limit += 100; male(); });
    $$("#ins-tabelle th.sort").forEach(t => t.addEventListener("click", () => { if (sortK === t.dataset.k) sortAuf = !sortAuf; else { sortK = t.dataset.k; sortAuf = false; } male(); }));
  };
  $("#ins-typ").addEventListener("click", ev => { const c = ev.target.closest(".chip"); if (!c) return; typ = c.dataset.v; $$("#ins-typ .chip").forEach(x => x.classList.toggle("an", x === c)); limit = 100; male(); });
  $("#ins-rolle").addEventListener("click", ev => { const c = ev.target.closest(".chip"); if (!c) return; rollen.has(c.dataset.v) ? rollen.delete(c.dataset.v) : rollen.add(c.dataset.v); c.classList.toggle("an"); limit = 100; male(); });
  ["#ins-land", "#ins-min", "#ins-plan", "#ins-auff"].forEach(s => $(s).addEventListener("change", () => { limit = 100; male(); }));
  $("#ins-suche").addEventListener("input", () => { limit = 100; male(); });
  male();
};

/* ============================== Scanner ============================== */
RENDER.scanner = el => {
  el.innerHTML = `<div class="grid"><div class="card c12"><div class="ch"><div><h3 class="ct">Scanner · stärkste Aktien heute</h3>
    <div class="cs">${M.universum} Aktien geprüft · Kauf-Schwelle heute ${M.schwelle} (${M.regime ? "Markt im Aufwärtstrend" : "Markt im Abwärtstrend – höhere Hürde"})</div></div></div>
    <p class="erkl">Der Score (0–100) setzt sich aus vier Bausteinen zusammen. Momentum und 52W-Hoch zusammen erreichen höchstens ${Math.round(100 * (P.GEWICHT_MOMENTUM + P.GEWICHT_HOCH))} Punkte – für einen Kauf braucht es immer einen Auslöser: einen <b>positiven</b> Kurssprung nach Zahlen oder Insider-Käufe. Ein <b>negativer</b> Kurssprung ist ein Warnsignal: Die Aktie wird gesperrt bzw. verkauft. Die Spalte „Status“ erklärt, warum eine Aktie über der Schwelle (noch) nicht gekauft wird.</p>
    ${scoreLegende()}
    <div class="steuer" style="margin-top:14px"><div class="chips" id="sc-f">${[["", "Alle"], ["ueber", "Über Schwelle"], ["P", "mit Kurssprung"], ["I", "mit Insider"], ["H", "mit 52W-Hoch"]].map(([v, n], k) => `<span class="chip ${k ? "" : "an"}" data-v="${v}">${n}</span>`).join("")}</div></div>
    <div id="sc-tab"></div></div></div>${fuss()}`;
  let f = "";
  const male = () => {
    const l = D.scanner.filter(k => !f || (f === "ueber" ? k.sc >= M.schwelle : (k.komp[f] || 0) > 0));
    $("#sc-tab").innerHTML = `<div class="tw"><table class="tbl"><thead><tr><th class="l">#</th><th class="l">Aktie</th><th class="l" style="min-width:220px">Score</th><th></th><th>Kurs</th><th>1M</th><th>12M</th><th class="l">Status</th></tr></thead><tbody>
      ${l.map(k => `<tr class="klick ${k.kauf ? "hl" : ""}" data-ticker="${esc(k.t)}"><td class="l mute">${D.scanner.indexOf(k) + 1}</td><td class="l"><div class="tick">${esc(k.t)}</div><div class="firma">${esc(k.f)}</div></td>
      <td class="l">${scoreBar(k.komp, M.schwelle)}<div class="klein mute" style="margin-top:5px">${KOMP.filter(x => (k.komp[x.k] || 0) > 0).map(x => `${x.name.split(" ")[0]} ${Math.round(100 * P[x.gew] * k.komp[x.k])}`).join(" · ")}</div></td>
      <td><b style="font-size:16px">${Math.round(k.sc)}</b></td><td>${zahl(k.kurs)}</td><td class="${kl(k.m1)}">${pct(k.m1, 0)}</td><td class="${kl(k.m12)}">${pct(k.m12, 0)}</td>
      <td class="l wrap ${k.kauf ? "pos" : "mute"}" style="max-width:320px">${esc(k.status)}</td></tr>`).join("") || '<tr><td colspan="8" class="leer">Keine Aktien</td></tr>'}
      </tbody></table></div>`;
  };
  $("#sc-f").addEventListener("click", ev => { const c = ev.target.closest(".chip"); if (!c) return; f = c.dataset.v; $$("#sc-f .chip").forEach(x => x.classList.toggle("an", x === c)); male(); });
  male();
};

/* ============================== Statistik ============================== */
function belastbarkeit(tk) {
  if (!tk || !tk.anzahl) return "";
  const n = tk.anzahl, t = tk.t_wert, lo = tk.ki_unten, hi = tk.ki_oben;
  let urteil, klasse;
  if (n < 30) { urteil = `Erst ${n} abgeschlossene Trades – dafür lässt sich noch nichts sicher sagen.`; klasse = "warn"; }
  else if (ok(lo) && lo > 0) { urteil = "Der Vorteil ist statistisch belastbar: Auch im ungünstigen Fall bleibt der Durchschnitt über 0."; klasse = "ok"; }
  else if (ok(hi) && hi < 0) { urteil = "Die Regeln verlieren belastbar Geld – hier muss sich etwas ändern."; klasse = "fehler"; }
  else { urteil = "Noch nicht von Zufall zu unterscheiden: Der wahre Durchschnitt kann über oder unter 0 liegen. Erst mit mehr Trades wird es klar."; klasse = "warn"; }
  return `<div class="grid"><div class="card c12"><div class="ch"><div><h3 class="ct">Ist das Können oder Zufall?</h3><div class="cs">${n} Trades · Ø ${pct(tk.erwartung, 2)} je Trade · 95-%-Bereich ${ok(lo) ? `${pct(lo, 1)} bis ${pct(hi, 1)}` : "–"} · t-Wert ${ok(t) ? zahl(t) : "–"}${ok(tk.t_ueber) ? ` · gegenüber S&amp;P 500: ${pct(tk.ueber_markt, 1)} (95 %: ${pct(tk.ki_u_unten, 1)} bis ${pct(tk.ki_u_oben, 1)})` : ""}</div></div></div>
    <div class="box ${klasse}">${urteil} Faustregel: Ab etwa 100 Trades und einem t-Wert über 2 kann man einem Vorteil trauen.</div></div></div>`;
}
RENDER.statistik = el => {
  const st = D.stats, r = st.radar || {}, tk = st.trades || {}, namen = Object.keys(st.bench);
  const spalten = [["Radar", r]].concat(namen.map(n => [n, st.bench[n]])).concat([["Nur Kern", st.kern || {}]]);
  const zeilen = [
    ["Gesamtrendite", "gesamt", "p", 1], ["Rendite p.a. (CAGR)", "cagr", "p", 1], ["Schwankung p.a.", "vola", "p", -1],
    ["Sharpe Ratio", "sharpe", "z", 1, "Überrendite je Schwankung. >1 gut, >2 sehr gut."], ["Sortino Ratio", "sortino", "z", 1, "Wie Sharpe, zählt aber nur Schwankung nach unten."],
    ["Calmar Ratio", "calmar", "z", 1, "Rendite p.a. geteilt durch maximalen Rückgang."], ["Omega Ratio", "omega", "z", 1, "Summe aller Gewinntage geteilt durch Summe aller Verlusttage. >1 = mehr Gewinn als Verlust."],
    ["Max. Rückgang", "maxdd", "p", 1], ["Längste Erholung (Tage)", "dd_dauer", "n", -1], ["Ulcer Index", "ulcer", "p0", -1, "Tiefe und Dauer der Rückgänge kombiniert – je kleiner, desto ruhiger."],
    ["Positive Monate", "pos_monate", "p0", 1], ["Bester Monat", "bester_monat", "p", 1], ["Schlechtester Monat", "schlechtester_monat", "p", 1],
  ];
  const fz = (v, t) => t === "p" ? pct(v) : t === "p0" ? pct(v, 0, false) : t === "n" ? (v ?? "–") : zahl(v);
  el.innerHTML = `<div class="kpis">
    <div class="kpi"><div class="k">Netto-Rendite</div><div class="v ${kl(r.gesamt)}">${pct(r.gesamt)}</div><div class="n">${pct(r.cagr)} p.a.</div></div>
    <div class="kpi"><div class="k">Max. Rückgang</div><div class="v neg">${pct(r.maxdd)}</div><div class="n">${r.dd_dauer || 0} Tage bis neues Hoch</div></div>
    <div class="kpi"><div class="k">Profit Factor</div><div class="v">${zahl(tk.profit_factor)}</div><div class="n">${tk.anzahl || 0} Trades</div></div>
    <div class="kpi"><div class="k">Trefferquote</div><div class="v">${pct(tk.trefferquote, 1, false)}</div><div class="n">${tk.gewinner || 0}/${tk.anzahl || 0}</div></div>
    <div class="kpi"><div class="k">Sharpe</div><div class="v">${zahl(r.sharpe)}</div><div class="n">Sortino ${zahl(r.sortino)}</div></div>
    <div class="kpi"><div class="k">Omega</div><div class="v">${zahl(r.omega)}</div><div class="n">Calmar ${zahl(r.calmar)}</div></div>
  </div>
  <div class="grid"><div class="card c12"><div class="ch"><div><h3 class="ct">Wertentwicklung</h3><div class="cs">Indizes an-/ausschalten · „Nur Kern“ = S&amp;P 500 mit Trendfilter, ohne Einzelaktien</div></div></div><div id="st-perf"></div></div></div>
  <div class="grid"><div class="card c12"><div class="ch"><div><h3 class="ct">Rückgänge (Drawdown)</h3><div class="cs">Abstand zum bisherigen Höchststand</div></div></div><div id="st-dd"></div></div></div>
  <div class="grid"><div class="card c12"><div class="ch"><div><h3 class="ct">Vergleich</h3><div class="cs">Gleicher Zeitraum · bester Wert je Zeile hervorgehoben</div></div></div>
    <div class="tw"><table class="tbl"><thead><tr><th class="l">Kennzahl</th>${spalten.map(([n]) => `<th>${esc(n)}</th>`).join("")}</tr></thead><tbody>
    ${zeilen.map(([name, k, t, richtung, tip]) => { const vs = spalten.map(([, s]) => s[k]); const gueltig = vs.filter(ok); const best = gueltig.length ? (richtung > 0 ? Math.max(...gueltig) : Math.min(...gueltig)) : null;
      return `<tr><td class="l">${esc(name)} ${tip ? tippI(tip) : ""}</td>${vs.map(v => `<td class="${ok(v) && v === best ? "pos" : ""}" style="${ok(v) && v === best ? "font-weight:700" : ""}">${fz(v, t)}</td>`).join("")}</tr>`; }).join("")}
    </tbody></table></div></div></div>
  ${belastbarkeit(tk)}
  <div class="grid">
    <div class="card c6"><h3 class="ct" style="margin-bottom:12px">Trade-Analyse</h3><div class="tw"><table class="tbl"><tbody>
      ${[["Abgeschlossene Trades", tk.anzahl], ["Gewinner / Verlierer", `${tk.gewinner || 0} / ${tk.verlierer || 0}`], ["Trefferquote", pct(tk.trefferquote, 1, false)],
        ["Profit Factor", zahl(tk.profit_factor)], ["Erwartungswert je Trade", `<span class="${kl(tk.erwartung)}">${pct(tk.erwartung, 2)}</span>`],
        [`Erwartungswert, 95-%-Bereich ${tippI("So weit kann der wahre Durchschnitt allein durch Zufall daneben liegen. Liegt der Bereich komplett über 0, ist der Vorteil belastbar.")}`, ok(tk.ki_unten) ? `${pct(tk.ki_unten, 1)} bis ${pct(tk.ki_oben, 1)}` : "–"],
        [`t-Wert ${tippI("Durchschnitt geteilt durch seine Unsicherheit. Erst ab etwa 2 spricht wenig für Zufall.")}`, ok(tk.t_wert) ? zahl(tk.t_wert) : "–"],
        ["Ø Gewinn / Ø Verlust", `${pct(tk.avg_gewinn)} / ${pct(tk.avg_verlust)}`], ["Payoff (Ø Gewinn ÷ Ø Verlust)", zahl(tk.payoff)],
        ["Größter Gewinn / Verlust", `${pct(tk.groesster_gewinn)} / ${pct(tk.groesster_verlust)}`], ["Längste Gewinn- / Verlustserie", `${tk.serie_gewinn || 0} / ${tk.serie_verlust || 0}`],
        ["Ø Haltedauer (Handelstage)", `${zahl(tk.haltedauer, 0)} · Gewinner ${zahl(tk.haltedauer_gewinner, 0)} · Verlierer ${zahl(tk.haltedauer_verlierer, 0)}`],
        ["Netto-Ergebnis (Portfolio-%)", `<span class="${kl(tk.netto_pnl)}">${zahl(tk.netto_pnl, 2)} %</span>`], ["Ø Mehrrendite vs. S&P 500", `<span class="${kl(tk.ueber_markt)}">${pct(tk.ueber_markt)}</span>`]]
        .map(([a, b]) => `<tr><td class="l ink2">${a}</td><td><b>${b ?? "–"}</b></td></tr>`).join("")}</tbody></table></div></div>
    <div class="card c6"><div class="ch"><h3 class="ct">Verteilung der Trade-Ergebnisse</h3><div class="legende"><span><i style="background:var(--good)"></i>Gewinner</span><span><i style="background:var(--bad)"></i>Verlierer</span></div></div>
      <div id="st-hist"></div><div style="display:grid;grid-template-columns:150px 1fr;gap:16px;align-items:center;margin-top:12px"><div id="st-donut"></div>
      <div class="cs">Ø Gewinn <b class="pos">${pct(tk.avg_gewinn)}</b> · Ø Verlust <b class="neg">${pct(tk.avg_verlust)}</b><br>Ausstiege: ${Object.entries(tk.ausstiege || {}).map(([k, v]) => `${esc(k)} ${v}`).join(" · ")}</div></div></div>
  </div>
  <div class="grid">
    <div class="card c6"><div class="ch"><div><h3 class="ct">Risiko gegenüber Index</h3><div class="cs">Alpha, Beta & Co.</div></div><select class="feld" id="st-rel">${namen.map(n => `<option>${esc(n)}</option>`).join("")}</select></div><div id="st-reltab"></div></div>
    <div class="card c6"><h3 class="ct" style="margin-bottom:12px">Nach Auslöser</h3><div id="st-ausl"></div></div>
  </div>
  <div class="grid"><div class="card c12"><div class="ch"><div><h3 class="ct">Monatsrenditen</h3><div class="cs">Radar-Portfolio</div></div></div><div class="tw" id="st-monate"></div></div></div>${fuss()}`;
  perfChart($("#st-perf"), { hoehe: 380, kern: true });
  const ddS = [{ name: "Radar", farbe: "--bad", v: D.dd, flaeche: true, flaecheBasis: 0, flaecheOpa: 0.18, fmt: v => pct(v) }];
  if (D.bench[0]) { let mx = -1e9; ddS.push({ name: D.bench[0].name, farbe: "--ink3", breite: 1.3, strich: "4 4", fmt: v => pct(v), v: D.bench[0].v.map(v => { if (!ok(v)) return null; mx = Math.max(mx, v); return v / mx - 1; }) }); }
  linie($("#st-dd"), { x: D.dates, series: ddS, hoehe: 200, yfmt: v => pct(v, 0), nullLinie: true });
  const vt = tk.verteilung || [];
  if (vt.length) {
    const lo = Math.floor(Math.min(...vt) * 50) / 50, hi = Math.ceil(Math.max(...vt) * 50) / 50, bins = [];
    for (let b = lo; b < hi - 1e-9; b += 0.02) bins.push({ a: b, n: vt.filter(v => v >= b && v < b + 0.02 + (b + 0.02 >= hi - 1e-9 ? 1e-9 : 0)).length });
    saeulen($("#st-hist"), bins.map(b => ({ v: b.n, farbe: b.a + 0.01 > 0 ? "--good" : "--bad", txt: `<div class="tk">${pct(b.a, 0)} bis ${pct(b.a + 0.02, 0)}</div><div class="tz"><span>Trades</span><b>${b.n}</b></div>` })),
      { hoehe: 170, labels: [{ i: 0, t: pct(lo, 0) }, { i: bins.length - 1, t: pct(hi, 0) }] });
    donut($("#st-donut"), [{ name: "Gewinner", w: tk.gewinner, farbe: "--good" }, { name: "Verlierer", w: tk.verlierer, farbe: "--bad" }], String(tk.anzahl), "Trades");
  } else $("#st-hist").innerHTML = '<div class="leer">Noch keine abgeschlossenen Trades</div>';
  const rel = () => { const x = st.relativ[$("#st-rel").value] || {};
    $("#st-reltab").innerHTML = `<div class="tw"><table class="tbl"><tbody>${[["Alpha p.a.", pct(x.alpha), "Rendite, die nicht durch die Marktbewegung erklärt wird."], ["Beta", zahl(x.beta), "1 = bewegt sich wie der Index, <1 = ruhiger."],
      ["Korrelation", zahl(x.korrelation), "1 = läuft genau wie der Index."], ["Tracking Error", pct(x.tracking_error), "Wie stark der Radar vom Index abweicht (p.a.)."],
      ["Information Ratio", zahl(x.info_ratio), "Mehrrendite je Abweichung. >0,5 gilt als gut."], ["Up-Capture", pct(x.up_capture, 0, false), "Anteil der Index-Gewinntage, den der Radar mitnimmt."],
      ["Down-Capture", pct(x.down_capture, 0, false), "Anteil der Index-Verlusttage, den der Radar mitmacht – kleiner ist besser."]]
      .map(([a, b, t]) => `<tr><td class="l ink2">${a} ${tippI(t)}</td><td><b>${b}</b></td></tr>`).join("")}</tbody></table></div>`; };
  if (namen.length) { $("#st-rel").addEventListener("change", rel); rel(); }
  const gz = TRADES.filter(t => t.status === "geschlossen"), grp = {};
  gz.forEach(t => { const k = t.typen.filter(x => x !== "Momentum").join(" + ") || "nur Momentum"; (grp[k] = grp[k] || []).push(t); });
  const mean = a => a.reduce((x, y) => x + y, 0) / (a.length || 1);
  $("#st-ausl").innerHTML = Object.keys(grp).length ? `<div class="tw"><table class="tbl"><thead><tr><th class="l">Auslöser</th><th>Trades</th><th>Treffer</th><th>Ø Ergebnis</th><th>Ø vs. S&amp;P</th></tr></thead><tbody>
    ${Object.entries(grp).sort((a, b) => b[1].length - a[1].length).map(([k, v]) => { const e = mean(v.map(t => t.ergebnis)), u = mean(v.map(t => t.ueber_markt || 0));
      return `<tr><td class="l">${k.split(" + ").map(typTag).join("")}</td><td>${v.length}</td><td>${pct(mean(v.map(t => t.ergebnis > 0 ? 1 : 0)), 0, false)}</td><td class="${kl(e)}">${pct(e)}</td><td class="${kl(u)}">${pct(u)}</td></tr>`; }).join("")}</tbody></table></div>` : '<div class="leer">Noch keine Daten</div>';
  const MN = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"];
  const farbe = v => !ok(v) ? "transparent" : `color-mix(in srgb, var(${v > 0 ? "--good" : "--bad"}) ${Math.min(70, 12 + Math.abs(v) * 600)}%, transparent)`;
  $("#st-monate").innerHTML = `<table class="tbl hm"><thead><tr><th class="l">Jahr</th>${MN.map(m => `<th>${m}</th>`).join("")}<th>Jahr</th></tr></thead><tbody>
    ${(st.monate || []).map(j => `<tr><td class="l"><b>${j.jahr}</b></td>${j.monate.map(v => `<td style="background:${farbe(v)}">${ok(v) ? pct(v, 1).replace(" %", "") : ""}</td>`).join("")}<td style="background:${farbe(j.jahr_r)};font-weight:700">${pct(j.jahr_r, 1)}</td></tr>`).join("")}</tbody></table>`;
};

/* ============================== Lernen ============================== */
function forschungKarte() {
  const F = D.forschung;
  if (!F) return `<div class="grid"><div class="card c12"><h3 class="ct">Forschungslabor</h3><div class="leer">Läuft beim nächsten Tageslauf.</div></div></div>`;
  if (F.fehler) return `<div class="grid"><div class="card c12"><h3 class="ct">Forschungslabor</h3><div class="box warn">${esc(F.fehler)}</div></div></div>`;
  const badge = u => { const s = (u || {}).stufe || "–"; const c = /belegt/.test(s) ? "b-kauf" : s === "schwach" ? "b-warn" : "b-neutral"; return `<span class="badge ${c}">${esc(s)}</span>`; };
  const z = st => st && ok(st.avg) ? `<span class="${kl(st.avg)}">${pct(st.avg, 2)}</span><div class="klein mute">t ${zahl(st.t, 1)} · ${st.n}×</div>` : '<span class="mute">–</span>';
  const k = v => v ? `${pct(v.cagr, 1)}<div class="klein mute">DD ${pct(v.maxdd, 0)} · Sharpe ${zahl(v.sharpe)}</div>` : "–";
  const studie = (F.studie || []).slice().sort((a, b) => ((b.urteil || {}).t || -9) - ((a.urteil || {}).t || -9));
  return `<div class="grid"><div class="card c12"><div class="ch"><div><h3 class="ct">Forschungslabor · Welche Effekte wirken mit echten Daten?</h3>
      <div class="cs">Alle Ereignisse ${datKurz(F.von)} – ${datKurz(F.bis)} · Lernteil bis ${datKurz(F.grenze)}, danach Testteil mit Daten, die bei der Wahl unbekannt waren · Stand ${dat(F.datum, true)} · ${zahl(F.dauer_s, 0)} s</div></div></div>
    <p class="erkl">Gemessen wird die Rendite ab der nächsten Eröffnung, <b>abzüglich des Durchschnitts aller Aktien</b> am selben Tag – also das, was das Signal wirklich mehr bringt. t-Wert ab 2 = kaum Zufall. Die Spalte „vs. S&amp;P 500“ zeigt, ob das auch gegen den Index reicht (Testteil, 20 Tage).</p>
    <ol class="gedanken">${(F.gedanken || []).map(g => `<li>${esc(g)}</li>`).join("")}</ol>
    <div class="tw" style="margin-top:14px"><table class="tbl"><thead><tr><th class="l">Signal</th><th>Ereignisse</th><th>20 Tage · Lernteil</th><th>20 Tage · Test</th><th>60 Tage · Lernteil</th><th>60 Tage · Test</th><th>vs. S&amp;P 500</th><th class="l">Urteil</th></tr></thead><tbody>
    ${studie.map(e => `<tr><td class="l wrap" style="max-width:280px"><b>${esc(e.name)}</b></td><td>${e.n}</td><td>${z(e.h20.lern)}</td><td>${z(e.h20.test)}</td><td>${z(e.h60.lern)}</td><td>${z(e.h60.test)}</td><td>${z(e.h20.spy_test)}</td><td class="l">${badge(e.urteil)}</td></tr>`).join("")}
    </tbody></table></div></div></div>
  <div class="grid"><div class="card c12"><div class="ch"><div><h3 class="ct">Portfolio-Aufbau · ${(F.varianten || []).length} Varianten über die ganze Historie</h3><div class="cs">Auslöser-Mischung × Ausstieg (Trend oder schnelle Gewinnmitnahme) × Anzahl Aktien · gewählt nur nach dem Lernteil · die 20 besten</div></div></div>
    <div class="tw"><table class="tbl"><thead><tr><th class="l">Variante</th><th>Lernteil p.a.</th><th>Treffer Lern</th><th>Testteil p.a.</th><th>Treffer Test</th><th>Ø Gewinn / Ø Verlust (Test)</th><th>Trades</th></tr></thead><tbody>
    ${F.bench ? `<tr><td class="l mute">S&amp;P 500 (zum Vergleich)</td><td>${k(F.bench.lern)}</td><td></td><td>${k(F.bench.test)}</td><td></td><td></td><td></td></tr>` : ""}
    ${(F.varianten || []).slice().sort((a, b) => (b.name === F.bester) - (a.name === F.bester) || ((b.lern || {}).ziel ?? -9) - ((a.lern || {}).ziel ?? -9)).slice(0, 20).map(v => `<tr class="${v.name === F.bester ? "hl" : ""}"><td class="l wrap" style="max-width:420px">${v.name === F.bester ? '<span class="badge b-kauf">gewählt</span> ' : ""}${esc(v.name)}</td><td>${k(v.lern)}</td><td>${pct(v.quote_lern, 0, false)}</td><td>${k(v.test)}</td><td>${pct(v.quote_test, 0, false)}</td><td>${v.gv_test ? `<span class="pos">${pct(v.gv_test[0], 1)}</span> / <span class="neg">${pct(v.gv_test[1], 1)}</span>` : "–"}</td><td>${v.trades}</td></tr>`).join("")}
    </tbody></table></div></div></div>`;
}
RENDER.lernen = el => {
  const L = D.lernen || {};
  const fl = P.FILTER || [];
  const naechste = L.datum ? `etwa ${P.LERN_INTERVALL} Handelstage nach dem ${dat(L.datum, true)}` : "beim nächsten Lauf";
  el.innerHTML = forschungKarte() + `<div class="grid">
    <div class="card c8"><div class="ch"><div><h3 class="ct">Was der Radar gerade denkt</h3><div class="cs">${L.datum ? `Letzte Prüfung ${dat(L.datum, true)} · ${L.varianten} Varianten in ${zahl(L.dauer_s, 0)} s · Zeitraum ${datKurz(L.fenster[0])} – ${datKurz(L.fenster[1])}` : "Noch keine Prüfung"}</div></div>
      ${L.datum ? `<span class="badge ${L.gewechselt ? "b-kauf" : "b-neutral"}">${L.gewechselt ? "Regeln angepasst" : "Regeln bestätigt"}</span>` : ""}</div>
      ${(L.gedanken || []).length ? `<ol class="gedanken">${L.gedanken.map(g => `<li>${esc(g)}</li>`).join("")}</ol>` : '<div class="leer">Die erste Prüfung läuft beim nächsten Tageslauf.</div>'}</div>
    <div class="card c4"><h3 class="ct" style="margin-bottom:12px">Aktuelle Regeln</h3><div class="fakten" style="grid-template-columns:1fr 1fr">
      <div><span>Kauf-Schwelle</span><b>${P.SCHWELLE}</b></div><div><span>bei Abwärtstrend</span><b>${P.SCHWELLE_RISK_OFF}</b></div>
      <div><span>Max. Haltedauer</span><b>${P.HALTEDAUER} Tage</b></div><div><span>Nachzieh-Stopp</span><b>${zahl(P.STOPP_ATR_NACHZIEH, 1)} × ATR</b></div>
      <div><span>Positionen</span><b>max. ${P.MAX_POSITIONEN} · ${pct(P.GEWICHT_MIN, 0, false)}–${pct(P.GEWICHT_MAX, 0, false)}</b></div><div><span>Anfangs-Stopp</span><b>${zahl(P.STOPP_ATR_START, 1)} × ATR</b></div>
      <div><span>Auslöser Zahlen</span><b>${P.PEAD_AKTIV === false ? "aus" : (P.PEAD_GROESSEN || [0, 1, 2]).map(g => ["klein", "mittel", "groß"][g]).join(", ") + (P.PEAD_STARKER_SCHLUSS ? " · starker Schluss" : "")}</b></div>
      <div><span>Auslöser Insider</span><b>${P.INSIDER_TRIGGER === false ? "aus" : "ab " + P.INSIDER_MIN_AUFFAELLIG + " Punkten"}</b></div>
      <div><span>Auslöser Momentum</span><b>${P.MOMENTUM_TRIGGER ? "an (Top 10 %)" : "aus"}</b></div><div><span>Auslöser 52W-Hoch</span><b>${P.HOCH_TRIGGER ? "an" : "aus"}</b></div>
      <div><span>Auslöser Umkehr</span><b>${P.UMKEHR_TRIGGER ? "an" : "aus"}</b></div><div><span>Kauf nach Kursrutsch</span><b>${P.NEG_KAUF_TRIGGER ? "an" : "aus"}</b></div>
      <div><span>Notverkauf bei Kursrutsch</span><b>${P.EXIT_NEG_SPRUNG === false ? "aus (nicht belegt)" : "an"}</b></div>
      ${KOMP.map(k => `<div><span>Gewicht ${k.name}</span><b>${Math.round(100 * P[k.gew])}</b></div>`).join("")}</div>
      <div class="lbl" style="margin:16px 0 8px">Gelernte Filter</div>${fl.length ? fl.map(f => `<div class="box ok" style="margin-bottom:6px">${esc(f.text)}</div>`).join("") : '<div class="cs">Keine – bisher hat kein Filter in beiden Zeiträumen überzeugt.</div>'}
      <div class="cs" style="margin-top:14px">Nächste Prüfung ${esc(naechste)}.</div></div>
  </div>
  <div class="grid">
    <div class="card c6"><div class="ch"><div><h3 class="ct">Alle getesteten Varianten</h3><div class="cs">Jeder Punkt eine Einstellung · rechts oben = gut in beiden Zeiträumen</div></div></div><div id="ln-streu"></div>
      <div class="legende" style="margin-top:8px"><span><i style="background:var(--ink3);border-radius:50%"></i>Variante</span><span><i style="background:var(--s1);border-radius:50%"></i>aktuell</span><span><i style="background:var(--s2);border-radius:50%"></i>beste</span></div></div>
    <div class="card c6"><h3 class="ct" style="margin-bottom:4px">Robusteste Varianten</h3><div class="cs" style="margin-bottom:10px">„Nachbarn“ = Ø der leicht veränderten Einstellungen – schützt vor Zufallstreffern</div>
      <div class="tw"><table class="tbl"><thead><tr><th class="l">Variante</th><th>Lernteil</th><th>Nachbarn</th><th>Prüfteil</th><th>Trades</th></tr></thead><tbody>
      ${L.aktuell ? `<tr class="hl"><td class="l"><b>aktuell</b></td><td>${pct(L.aktuell.lern)}</td><td>–</td><td>${pct(L.aktuell.pruef)}</td><td>${L.aktuell.trades}</td></tr>` : ""}
      ${(L.top || []).slice(0, 8).map(z => `<tr><td class="l">${esc(z.name)}</td><td class="${kl(z.lern)}">${pct(z.lern)}</td><td class="${kl(z.robust)}">${pct(z.robust)}</td><td class="${kl(z.pruef)}">${pct(z.pruef)}</td><td>${z.trades}</td></tr>`).join("")}</tbody></table></div>
      <div class="cs" style="margin-top:8px">Werte = Rendite minus halber maximaler Rückgang (bestraft riskante Varianten).</div></div>
  </div>
  <div class="grid">
    <div class="card c6"><h3 class="ct" style="margin-bottom:4px">Fehleranalyse</h3><div class="cs" style="margin-bottom:10px">Ø Ergebnis der Trades nach Merkmal beim Kauf (${L.analyse ? L.analyse.n : 0} Trades) – rote Bereiche sind Kandidaten für Filter</div>
      ${L.analyse && L.analyse.muster && L.analyse.muster.length ? (() => { const mx = Math.max(0.02, ...L.analyse.muster.map(m => Math.abs(m.avg)));
        return `<div class="tw"><table class="tbl"><thead><tr><th class="l">Merkmal</th><th class="l">Bereich</th><th>Trades</th><th>Treffer</th><th style="min-width:160px">Ø Ergebnis</th></tr></thead><tbody>
        ${L.analyse.muster.map(m => `<tr><td class="l">${esc(m.merkmal)}</td><td class="l mute">${esc(m.bereich)}</td><td>${m.n}</td><td>${pct(m.quote, 0, false)}</td><td><span class="ergbar"><b style="width:${Math.round(Math.abs(m.avg) / mx * 60)}px;background:var(${m.avg > 0 ? "--good" : "--bad"})"></b><span class="${kl(m.avg)}" style="min-width:56px;display:inline-block">${pct(m.avg)}</span></span></td></tr>`).join("")}</tbody></table></div>`; })() : '<div class="leer">Zu wenige Trades für eine Analyse</div>'}</div>
    <div class="card c6"><h3 class="ct" style="margin-bottom:4px">Getestete Filter</h3><div class="cs" style="margin-bottom:10px">Jede Filter-Idee auf den besten Varianten simuliert – übernommen nur, wenn beide Zeiträume besser werden</div>
      ${(L.filter_tests || []).length ? `<div class="tw"><table class="tbl"><thead><tr><th class="l">Filter</th><th class="l">auf</th><th>Δ Lernteil</th><th>Δ Prüfteil</th></tr></thead><tbody>
      ${L.filter_tests.map(z => `<tr><td class="l wrap">${esc(z.filter)}</td><td class="l mute klein">${esc(z.basis)}</td><td class="${kl(z.verbesserung_lern)}">${pct(z.verbesserung_lern)}</td><td class="${kl(z.verbesserung_pruef)}">${pct(z.verbesserung_pruef)}</td></tr>`).join("")}</tbody></table></div>` : '<div class="leer">Noch keine Filter-Tests</div>'}</div>
  </div>
  <div class="grid"><div class="card c12"><div class="ch"><div><h3 class="ct">Größte Verluste – was ist schiefgelaufen?</h3><div class="cs">Automatische Diagnose je Verlust-Trade</div></div></div>
    ${(L.verluste || []).length ? `<div class="grid" style="margin:0">${L.verluste.map(v => `<div class="card c4 mini-karte" data-ticker="${esc(v.ticker)}" data-trade="${v.id}" style="background:var(--card2)">
      <div style="display:flex;justify-content:space-between"><div><span class="tick" style="font-size:17px">${esc(v.ticker)}</span> <span class="mute klein">${dat(v.datum, true)}</span></div><b class="neg" style="font-size:17px">${pct(v.ergebnis)}</b></div>
      <div class="cs" style="margin:4px 0 8px">${v.typen.map(typTag).join("")} · ${esc(v.grund)}${v.tage != null ? ` nach ${v.tage} Tagen` : ""}</div>
      <ul class="liste">${v.ursachen.map(u => `<li class="klein ink2" style="padding:6px 0">${esc(u)}</li>`).join("")}</ul></div>`).join("")}</div>` : '<div class="leer">Keine Verlust-Trades</div>'}</div></div>
  <div class="grid"><div class="card c12"><h3 class="ct" style="margin-bottom:10px">Protokoll</h3>
    ${(L.historie || []).length ? `<ul class="liste">${L.historie.slice().reverse().map(h => `<li style="display:flex;gap:14px"><b style="min-width:92px">${dat(h.datum, true)}</b><span>${h.nach ? `<b>Wechsel zu „${esc(h.nach)}“</b> – ` : ""}${esc(h.grund)}</span></li>`).join("")}</ul>` : '<div class="leer">Noch keine Einträge</div>'}
    <p class="cs" style="margin-top:12px">So lernt der Radar: Fehleranalyse der Verlierer → ${L.grund_varianten || "~180"} Grundvarianten (Gewichtung × Schwelle × Haltedauer × Stopp) → Robustheits-Check über Nachbarvarianten → Filter-Tests → Bestätigung im späteren Prüfzeitraum. Neue Regeln gelten nur für künftige Empfehlungen; vergangene Empfehlungen werden nie verändert.</p></div></div>${fuss()}`;
  const pk = (L.punkte || []).map(p => ({ x: p.lern, y: p.pruef, farbe: "--ink3", r: 3.5, txt: `<div class="tk">${esc(p.name)}</div><div class="tz"><span>Lernteil</span><b>${pct(p.lern)}</b></div><div class="tz"><span>Prüfteil</span><b>${pct(p.pruef)}</b></div>` }));
  if (L.aktuell) pk.push({ x: L.aktuell.lern, y: L.aktuell.pruef, farbe: "--s1", r: 7, txt: `<div class="tk">aktuell</div><div class="tz"><span>Lernteil</span><b>${pct(L.aktuell.lern)}</b></div><div class="tz"><span>Prüfteil</span><b>${pct(L.aktuell.pruef)}</b></div>` });
  if (L.bester && L.bester.name !== "aktuell") pk.push({ x: L.bester.lern, y: L.bester.pruef, farbe: "--s2", r: 7, txt: `<div class="tk">${esc(L.bester.name)}</div><div class="tz"><span>Lernteil</span><b>${pct(L.bester.lern)}</b></div><div class="tz"><span>Prüfteil</span><b>${pct(L.bester.pruef)}</b></div>` });
  streu($("#ln-streu"), pk, { hoehe: 320, xlabel: "Lernteil (ältere 2/3)", ylabel: "Prüfteil (neueres 1/3)" });
};

/* ============================== Start ============================== */
const start = (location.hash || "#uebersicht").slice(1);
zeige(TABS.some(t => t[0] === start) ? start : "uebersicht");
window.addEventListener("hashchange", () => { const h = location.hash.slice(1); if (TABS.some(t => t[0] === h) && !$(`#${h}.aktiv`)) zeige(h); });
})();
