(function () {
"use strict";
const D = JSON.parse(document.getElementById("daten").textContent);
const $ = (s, el) => (el || document).querySelector(s);
const $$ = (s, el) => Array.from((el || document).querySelectorAll(s));
const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const ok = x => x !== null && x !== undefined && isFinite(x);
const zahl = (x, nk = 0) => ok(x) ? Number(x).toLocaleString("de-DE", { minimumFractionDigits: nk, maximumFractionDigits: nk }) : "–";
const eur = (x, nk = 0) => ok(x) ? zahl(x, nk) + " €" : "–";
const pct = (x, nk = 0) => ok(x) ? zahl(x * 100, nk) + " %" : "–";
const zeit = iso => { if (!iso) return "–"; const d = new Date(iso); return d.toLocaleString("de-DE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }); };
const tag = iso => { if (!iso) return ""; const d = new Date(iso); return d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" }); };
const tippI = txt => `<span class="tipp" tabindex="0" data-tipp="${esc(txt)}">?</span>`;
const ART = { freelance: "Freelance", bounty: "Bounty", wettbewerb: "Wettbewerb", gesuch: "Gesuch", ausschreibung: "Ausschreibung" };
/* Hell/Dunkel: gleiche Einstellung wie im Aktien-Radar (radar_thema) */
try { const t = JSON.parse(localStorage.getItem("radar_thema") || "null"); if (t) document.documentElement.dataset.theme = t; } catch (e) { }
const NACH_ID = {}; D.eintraege.forEach(e => NACH_ID[e.id] = e);
const TOP = D.top.map(i => NACH_ID[i]).filter(Boolean);

function toast(t) { let el = $(".toast"); if (!el) { el = document.createElement("div"); el.className = "toast"; document.body.appendChild(el); }
  el.textContent = t; el.classList.add("an"); clearTimeout(el._t); el._t = setTimeout(() => el.classList.remove("an"), 1800); }

/* ---------- Feedback über GitHub-Issues ---------- */
function issueUrl(e, aktion, betrag) {
  const titel = `[Auftrag] ${aktion}: ${e.titel.slice(0, 60)}`;
  const body = `id: ${e.id}\naktion: ${aktion}\n` + (betrag ? `betrag: ${betrag}\n` : "") +
    `\n(Vom Auftrags-Radar erzeugt. Einfach auf „Submit new issue“ tippen – der nächste Lauf übernimmt und schließt das Issue.)`;
  return `https://github.com/${D.repo}/issues/new?title=${encodeURIComponent(titel)}&body=${encodeURIComponent(body)}`;
}
function feedbackKnoepfe(e) {
  return `<div class="aktionen">
    <a class="knopf haupt" href="${esc(e.url)}" target="_blank" rel="noopener">Zum Auftrag ↗</a>
    <button class="knopf" data-fb="beworben" data-id="${esc(e.id)}">Beworben</button>
    <button class="knopf gut" data-fb="gewonnen" data-id="${esc(e.id)}">Gewonnen</button>
    <button class="knopf schlecht" data-fb="verloren" data-id="${esc(e.id)}">Verloren</button>
    <button class="knopf" data-fb="uninteressant" data-id="${esc(e.id)}">Nicht interessant</button>
    ${e.art === "freelance" ? `<button class="knopf" data-fb="gesperrt" data-id="${esc(e.id)}" title="Du darfst auf diesen Auftrag nicht bieten (z. B. nur Preferred Freelancer). Der Radar lernt daraus.">Für mich gesperrt</button>` : ""}
  </div>`;
}
document.addEventListener("click", ev => {
  const b = ev.target.closest("[data-fb]");
  if (b) {
    const e = NACH_ID[b.dataset.id]; const a = b.dataset.fb; let betrag = null;
    if (a === "pruefen") toast("GitHub öffnet sich – „Submit new issue“ tippen, Ergebnis in ca. 3 Minuten");
    if (a === "gewonnen") { betrag = prompt("Betrag in Euro (leer lassen, wenn er nicht öffentlich sichtbar sein soll):", e.ki && e.ki.preis_vorschlag_eur ? Math.round(e.ki.preis_vorschlag_eur) : ""); if (betrag === null) return; }
    window.open(issueUrl(e, a, betrag), "_blank", "noopener"); return;
  }
  const k = ev.target.closest("[data-kopie]");
  if (k) { const t = NACH_ID[k.dataset.kopie]; const txt = t && t.ki ? t.ki.bewerbung : "";
    (navigator.clipboard ? navigator.clipboard.writeText(txt) : Promise.reject()).then(() => toast("Text kopiert"), () => toast("Kopieren nicht möglich")); return; }
  const z = ev.target.closest("tr[data-id]");
  if (z && !ev.target.closest("a,button")) oeffne(NACH_ID[z.dataset.id]);
  if (ev.target.closest(".schliessen") || ev.target.classList.contains("modal")) $(".modal").classList.remove("offen");
});

/* ---------- Bausteine ---------- */
function badgeArt(e) { const kl = e.art === "bounty" ? "b-warn" : e.art === "wettbewerb" ? "b-neutral" : "b-kauf"; return `<span class="badge ${kl}">${ART[e.art] || e.art}</span>`; }
function fbTag(e) { return e.feedback ? `<span class="fb ${esc(e.feedback)}">${esc(e.feedback)}</span>` : ""; }
function bewerbung(e) {
  if (e.ki && e.ki.bewerbung) return `<div class="bew"><button class="knopf kopie" data-kopie="${esc(e.id)}">Kopieren</button>${esc(e.ki.bewerbung)}</div>`;
  if (!D.ki.aktiv) return `<div class="box warn" style="margin-top:10px">Für Bewerbungstexte den Schlüssel ANTHROPIC_API_KEY als GitHub-Secret hinterlegen.</div>`;
  return `<div class="box warn" style="margin-top:10px;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap">
    <span>Noch keine KI-Bewertung.</span><button class="knopf haupt" data-fb="pruefen" data-id="${esc(e.id)}">Mit KI prüfen</button></div>`;
}
function gebotBox(e) {
  const g = e.gebot; if (!g) return "";
  return `<div class="zahlen" style="margin-bottom:10px;border-color:color-mix(in srgb,var(--good) 40%,var(--line2))">
    <div class="lbl">Dein Gebot ${tippI(g.rabatt ? "Etwa 30 % unter dem Durchschnittsgebot, solange du weniger als 3 gewonnene Aufträge hast – so kommst du an die ersten Bewertungen." : "Knapp unter dem Durchschnittsgebot.")}</div>
    <div class="ew">${zahl(g.betrag_usd)} $ <span style="font-size:14px;font-weight:600;color:var(--ink3)">${esc(g.einheit)}</span></div>
    ${g.tage ? `<div class="zr"><span>Lieferzeit</span><span>${g.tage} ${g.tage === 1 ? "Tag" : "Tage"}</span></div>` : ""}
    <div class="zr"><span>Bei dir an (nach Gebühr)</span><span>${zahl(g.netto_usd)} $</span></div></div>`;
}
function zahlenBox(e) {
  return `<div>` + gebotBox(e) + `<div class="zahlen"><div class="lbl">Erwarteter Wert ${tippI("Wert nach Gebühren × Gewinnchance × Machbarkeit × gelernter Interesse-Faktor. Das ist der Durchschnitt, den eine Bewerbung bringt.")}</div>
    <div class="ew">${eur(e.ew_eur)}</div>
    <div class="zr"><span>Wert bei Zuschlag</span><span>${eur(e.wert_eur)}</span></div>
    <div class="zr"><span>Gewinnchance</span><span>${pct(e.chance, 1)}</span></div>
    <div class="zr"><span>Machbar durch Claude</span><span>${pct(e.machbar)}</span></div>
    <div class="zr"><span>€ pro Leon-Stunde ${tippI("Erwarteter Wert geteilt durch deine erwartete Zeit: Bewerben plus (mit der Gewinnchance gewichtet) Abstimmung und Abliefern.")}</span><span>${eur(e.eur_pro_std)}</span></div>
    <div class="zr"><span>Deine Zeit (Ø)</span><span>${zahl(e.leon_min)} Min.</span></div>
    <div class="zr"><span>Konkurrenz</span><span>${e.art === "ausschreibung" ? "unbekannt" : zahl(e.gebote) + " " + (e.art === "bounty" ? "Kommentare" : e.art === "wettbewerb" ? "Teilnehmer" : "Gebote")}</span></div>
  </div></div>`;
}
function metaZeile(e) {
  const t = [badgeArt(e), `<span>${esc(e.quelle)}</span>`, `<span>${esc(e.kat_name)}</span>`];
  if (ok(e.alter_tage)) t.push(`<span>vor ${e.alter_tage < 1 ? Math.max(1, Math.round(e.alter_tage * 24)) + " Std." : zahl(e.alter_tage) + " T."}</span>`);
  if (e.art === "bounty" && e.ki_regel && e.ki_regel !== "unbekannt") t.push(`<span>KI-Regel: ${esc(e.ki_regel)}</span>`);
  if (e.frist) t.push(`<span>Frist: ${esc(String(e.frist).slice(0, 40))}</span>`);
  if (e.kunde && e.kunde.seit) t.push(`<span>Kunde: ${e.kunde.bewertungen ? zahl(e.kunde.sterne, 1) + "★ · " + e.kunde.bewertungen + " Bew." : "neu, keine Bewertungen"}${e.kunde.zahlung_ok ? " · Zahlung verifiziert" : ""}</span>`);
  t.push(fbTag(e));
  return `<div class="meta">${t.join("")}</div>`;
}

/* ---------- Mini-Charts ---------- */
function liniePlot(host, x, reihen, fmt, hoehe = 220) {
  const W = host.clientWidth || 600, H = hoehe, pl = 4, pr = 56, pt = 12, pb = 24, n = x.length;
  if (n < 2) { host.innerHTML = '<div class="leer">Noch zu wenige Läufe für eine Kurve.</div>'; return; }
  const alle = reihen.flatMap(r => r.v).filter(ok); let lo = 0, hi = Math.max(1, ...alle); hi *= 1.1;
  const X = i => pl + (W - pl - pr) * i / (n - 1), Y = v => pt + (H - pt - pb) * (1 - (v - lo) / (hi - lo));
  const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  let g = "";
  for (let k = 0; k <= 3; k++) { const v = lo + (hi - lo) * k / 3; g += `<line x1="${pl}" x2="${W - pr}" y1="${Y(v)}" y2="${Y(v)}" stroke="${css("--line2")}"/><text x="${W - pr + 8}" y="${Y(v) + 4}" font-size="11" fill="${css("--ink3")}">${esc(fmt(v))}</text>`; }
  [0, Math.floor((n - 1) / 2), n - 1].forEach((i, k) => g += `<text x="${X(i)}" y="${H - 6}" font-size="11" fill="${css("--ink3")}" text-anchor="${k === 0 ? "start" : k === 2 ? "end" : "middle"}">${esc(tag(x[i]))}</text>`);
  reihen.forEach(r => {
    const pts = r.v.map((v, i) => ok(v) ? `${X(i)},${Y(v)}` : null).filter(Boolean).join(" ");
    if (r.flaeche) g += `<polygon points="${X(0)},${Y(0)} ${pts} ${X(n - 1)},${Y(0)}" fill="${css(r.farbe)}" opacity=".12"/>`;
    g += `<polyline points="${pts}" fill="none" stroke="${css(r.farbe)}" stroke-width="2" stroke-linejoin="round"/>`;
  });
  host.innerHTML = `<div class="chart"><svg width="${W}" height="${H}">${g}<line class="hv" y1="${pt}" y2="${H - pb}" stroke="${css("--ink3")}" stroke-dasharray="3 3" style="display:none"/></svg><div class="tip"></div></div>`;
  const svg = $("svg", host), tip = $(".tip", host), hv = $(".hv", host);
  svg.addEventListener("mousemove", ev => {
    const r = svg.getBoundingClientRect(), i = Math.max(0, Math.min(n - 1, Math.round((ev.clientX - r.left - pl) / (W - pl - pr) * (n - 1))));
    hv.setAttribute("x1", X(i)); hv.setAttribute("x2", X(i)); hv.style.display = "";
    tip.innerHTML = `<div class="tk">${esc(zeit(x[i]))}</div>` + reihen.map(s => `<div class="tz"><span><i style="background:var(${s.farbe})"></i>${esc(s.name)}</span><b>${esc(fmt(s.v[i]))}</b></div>`).join("");
    tip.style.display = "block"; tip.style.left = Math.min(X(i) + 12, W - 170) + "px"; tip.style.top = "8px";
  });
  svg.addEventListener("mouseleave", () => { tip.style.display = "none"; hv.style.display = "none"; });
}
function spark(werte, farbe = "--s1") {
  const W = 120, H = 26, n = werte.length; if (n < 2) return '<span class="mute">–</span>';
  const hi = Math.max(1, ...werte); const pts = werte.map((v, i) => `${(W * i / (n - 1)).toFixed(1)},${(H - 2 - (H - 4) * v / hi).toFixed(1)}`).join(" ");
  return `<svg class="spark" width="${W}" height="${H}"><polyline points="${pts}" fill="none" stroke="var(${farbe})" stroke-width="1.6"/></svg>`;
}

/* ---------- Kopf ---------- */
const L = D.laeufe[D.laeufe.length - 1] || {};
const empf = D.eintraege.filter(e => e.empfehlbar);
const tabs = [["uebersicht", "Übersicht", TOP.length], ["alle", "Alle Aufträge", empf.length], ["quellen", "Quellen", Object.keys(D.quellen).length],
  ["lernen", "Lernen", null], ["ergebnisse", "Ergebnisse", D.feedback.length || null]];
document.body.innerHTML = `
<header class="kopf"><div class="in">
  <div class="zeile1">
    <div class="marke"><div class="logo"><svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round"><path d="M4 17l5-5 4 4 7-8"/><path d="M15 8h5v5"/></svg></div>
      <div><h1>Auftrags-Radar</h1><div class="stand">Stand ${esc(zeit(D.stand))}<span class="lang"> · scannt ${Object.values(D.quellen).filter(q => q.status !== "pausiert").length} Quellen alle 3 Stunden</span></div></div></div>
    <div class="rechts"><a class="pill" href="../">← Aktien-Radar</a>
      <a class="pill" href="https://github.com/${esc(D.repo)}/actions/workflows/auftraege.yml" target="_blank" rel="noopener" title="Öffnet GitHub: dort „Run workflow“ tippen. Manuelle Läufe prüfen auch nach dem Tageskontingent bis zu 8 Aufträge mit KI.">↻ Jetzt scannen</a>
      <button class="ikon" id="thema" aria-label="Hell/Dunkel"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg></button>
      <span class="pill" title="Automatisch höchstens ${D.ki.max} Prüfungen pro Tag, mit manuellen Prüfungen höchstens ${D.ki.hart}. Zähler beginnt um 0 Uhr."><i style="background:var(${D.ki.aktiv ? "--good" : "--warn"})"></i>KI ${D.ki.aktiv ? D.ki.heute + "/" + D.ki.max + " heute" : "aus"}</span></div>
  </div>
  <nav class="tabs">${tabs.map(([k, t, z], i) => `<button data-tab="${k}" class="${i === 0 ? "aktiv" : ""}">${t}${z ? `<span class="zahl">${z}</span>` : ""}</button>`).join("")}</nav>
</div></header>
<main>${tabs.map(([k], i) => `<section class="tab${i === 0 ? " aktiv" : ""}" id="t-${k}"></section>`).join("")}</main>
<div class="modal"><div class="blatt"><div class="blatt-kopf"><div id="m-kopf"></div><button class="schliessen">×</button></div><div class="blatt-inhalt" id="m-inhalt"></div></div></div>`;
$("#thema").addEventListener("click", () => {
  const dunkel = document.documentElement.dataset.theme ? document.documentElement.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.dataset.theme = dunkel ? "light" : "dark";
  try { localStorage.setItem("radar_thema", JSON.stringify(document.documentElement.dataset.theme)); } catch (e) { }
  zeichneCharts();
});
$$("nav.tabs button").forEach(b => b.addEventListener("click", () => {
  $$("nav.tabs button").forEach(x => x.classList.toggle("aktiv", x === b));
  $$("section.tab").forEach(s => s.classList.toggle("aktiv", s.id === "t-" + b.dataset.tab));
  try { localStorage.setItem("auftrag_tab", b.dataset.tab); } catch (e) { }
  zeichneCharts();
}));

/* ---------- Monatsziel ---------- */
function monatsziel() {
  const a = D.annahmen, jetzt = new Date(), ym = jetzt.toISOString().slice(0, 7);
  const umsatz = D.feedback.filter(f => f.aktion === "gewonnen" && (f.zeit || "").slice(0, 7) === ym)
    .reduce((s, f) => s + (f.betrag || (NACH_ID[f.id] || {}).wert_eur || 0), 0);
  const netto = umsatz * a.netto_faktor, rest = Math.max(0, a.ziel_netto - netto);
  const basis = empf.slice().sort((x, y) => (y.rang || 0) - (x.rang || 0)).slice(0, 20);
  const ewProGebot = basis.length ? basis.reduce((s, e) => s + e.ew_eur, 0) / basis.length : 0;
  const gebote = ewProGebot > 0 ? Math.ceil((rest / a.netto_faktor) / ewProGebot) : null;
  const tage = new Date(jetzt.getFullYear(), jetzt.getMonth() + 1, 0).getDate() - jetzt.getDate() + 1;
  return { netto, umsatz, rest, gebote, tage, anteil: Math.min(1, netto / a.ziel_netto) };
}

/* ---------- Mein freelancer.com-Konto ---------- */
function kontoKarte() {
  const K = D.konto || {};
  if (!K.verbunden) return `<div class="box" style="margin-bottom:16px"><b>Konto noch nicht verbunden.</b> Mit dem Secret <b>FREELANCER_TOKEN</b> erkennt das Radar deine Gebote, Zuschläge und Absagen automatisch und schickt dir eine Push-Nachricht, wenn ein Kunde schreibt.</div>`;
  const Z = { offen: ["Läuft", "b-neutral"], gewonnen: ["Gewonnen 🎉", "b-kauf"], verloren: ["Nicht bekommen", "b-warn"], "zurückgezogen": ["Zurückgezogen", "b-neutral"] };
  const g = K.gebote || [];
  return `<div class="card" style="margin-bottom:16px"><div class="ch"><div><h3 class="ct">Mein freelancer.com-Konto${K.name ? " · " + esc(K.name) : ""}</h3>
      <div class="cs">${K.verifiziert ? "✅ verifiziert" : "⏳ Verifizierung noch nicht bestätigt"} · Abgleich ${zeit(K.abgleich)} (alle 30 Min.) ${tippI("Gebote, Zuschläge und Absagen werden automatisch übernommen – du musst „Beworben“, „Gewonnen“ und „Verloren“ nicht mehr drücken. Neue Kunden-Nachrichten kommen als Push aufs Handy.")}</div></div></div>
    ${K.fehler ? `<div class="box warn" style="margin-bottom:10px">Verbindung: ${esc(K.fehler)}</div>` : ""}
    ${g.length ? `<table class="tbl"><thead><tr><th class="l">Auftrag</th><th>Gebot</th><th>Abgegeben</th><th>Status</th></tr></thead><tbody>${g.map(x => `<tr>
      <td class="l"><a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.titel)}</a></td>
      <td>${zahl(x.betrag)} ${esc(x.waehrung)}${x.tage ? ` · ${x.tage} T.` : ""}</td><td>${tag(x.zeit)}</td>
      <td><span class="badge ${(Z[x.zustand] || ["", "b-neutral"])[1]}">${(Z[x.zustand] || [esc(x.zustand)])[0]}</span></td></tr>`).join("")}</tbody></table>`
      : `<p class="mute">Noch keine Gebote gefunden.</p>`}</div>`;
}

/* ---------- Übersicht ---------- */
function uebersicht() {
  const gewonnen = D.ergebnis.umsatz || 0;
  const kp = [
    ["Erwarteter Wert Top 5", eur(TOP.reduce((s, e) => s + e.ew_eur, 0)), "Ø-Ertrag, wenn du dich auf alle 5 bewirbst"],
    ["Empfehlbare Aufträge", zahl(empf.length), "machbar, frisch, seriös, noch nicht bearbeitet"],
    ["Neu im letzten Lauf", zahl(L.neu), `${zahl(Object.values(L.quellen || {}).reduce((s, q) => s + q.n, 0))} Einträge geprüft`],
    ["Bester €/Leon-Std.", eur(Math.max(0, ...empf.map(e => e.eur_pro_std))), "unter allen empfehlbaren"],
    ["Gewonnen bisher", eur(gewonnen), `${D.ergebnis.gewonnen} von ${D.ergebnis.beworben} Bewerbungen`],
  ];
  const Z = monatsziel();
  let h = `<div class="card" style="margin-bottom:16px"><div class="ch"><div><h3 class="ct">Monatsziel: ${eur(D.annahmen.ziel_netto)} netto</h3>
      <div class="cs">Gewonnen diesen Monat ${eur(Z.umsatz)} Umsatz ≈ ${eur(Z.netto)} netto ${tippI("Netto grob geschätzt: Umsatz × " + zahl(D.annahmen.netto_faktor * 100) + " % (nach ca. 10 % Plattformgebühr und ca. 20 % Steuern). Zählt Aufträge, die du mit „Gewonnen“ meldest.")} · noch ${Z.tage} Tage</div></div>
      <div style="text-align:right"><div class="lbl">Noch nötig</div><div style="font-size:22px;font-weight:750">${eur(Z.rest)}</div></div></div>
    <div style="height:10px;border-radius:5px;background:var(--chip);overflow:hidden"><i style="display:block;height:100%;width:${Math.round(Z.anteil * 100)}%;background:var(--good)"></i></div>
    <p class="fuss" style="margin-top:10px">${Z.rest <= 0 ? "Ziel erreicht – stark!" : Z.gebote ? `Bei den aktuellen Empfehlungen brauchst du dafür rechnerisch noch etwa <b>${Z.gebote} Gebote</b> (Ø-Ertrag pro Gebot ${eur(Z.netto >= 0 ? (Z.rest / D.annahmen.netto_faktor) / Z.gebote : 0)}). Mit Bewertungen steigt die Gewinnchance und die Zahl sinkt.` : "Noch keine Empfehlungen für eine Schätzung."}</p></div>`;
  h += kontoKarte();
  h += `<div class="kpis">${kp.map(([k, v, n]) => `<div class="kpi"><div class="k">${k}</div><div class="v">${v}</div><div class="n">${esc(n)}</div></div>`).join("")}</div>`;
  if (!D.ki.aktiv) h += `<div class="box warn" style="margin-bottom:16px">KI-Bewertung ist aus. Hinterlege das GitHub-Secret <b>ANTHROPIC_API_KEY</b>, dann bekommst du Lösungsweg, Risiko und fertige Bewerbungstexte.</div>`;
  h += `<div class="ch"><div><h2 class="ct" style="font-size:18px">Top 5 Empfehlungen</h2><div class="cs">Mischung aus Wert und echter Chance: Unter ${pct(D.annahmen.top_volle_chance)} Gewinnchance wird der erwartete Wert anteilig abgewertet, unter ${pct(D.annahmen.top_min_chance)} oder mit mehr als ${D.annahmen.top_max_gebote} Geboten fliegt ein Auftrag raus. Bewirb dich, kopiere den Auftrag in den Claude-Chat, Claude löst ihn.</div></div></div>`;
  h += TOP.length ? `<div class="top-liste">${TOP.map((e, i) => `<div class="card top-karte">
      <div class="rang">${i + 1}</div>
      <div>${metaZeile(e)}<h3><a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.titel)}</a></h3>
        ${e.ki && e.ki.loesung ? `<div><b>Lösung:</b> <span class="ink2">${esc(e.ki.loesung)}</span></div>` : `<div class="ink2 klein">${esc((e.text || "").slice(0, 220))}…</div>`}
        ${e.ki && e.ki.risiko ? `<div class="klein" style="margin-top:4px"><b>Risiko:</b> <span class="ink2">${esc(e.ki.risiko)}</span></div>` : ""}
        ${bewerbung(e)}${feedbackKnoepfe(e)}</div>
      ${zahlenBox(e)}</div>`).join("")}</div>`
    : `<div class="card"><div class="ruhe">Gerade nichts Lohnendes</div><p class="erkl">Kein Auftrag erfüllt im Moment alle Bedingungen (machbar, frisch, seriös, genug Wert). Der Radar schaut in 3 Stunden wieder.</p></div>`;
  h += `<div class="grid" style="margin-top:16px"><div class="card c12"><div class="ch"><div><h3 class="ct">Verlauf</h3><div class="cs">Erwarteter Wert der Top 5 und Zahl empfehlbarer Aufträge je Lauf</div></div></div><div id="ch-verlauf"></div></div></div>`;
  $("#t-uebersicht").innerHTML = h;
}

/* ---------- Alle Aufträge ---------- */
const F = { art: "alle", quelle: "alle", kat: "alle", q: "", nurEmpf: true, sort: "rang", ab: false };
function alle() {
  const quellen = [...new Set(D.eintraege.map(e => e.quelle))].sort(), kats = [...new Set(D.eintraege.map(e => e.kat_name))].sort();
  $("#t-alle").innerHTML = `<div class="card"><div class="steuer">
      <div class="chips" id="f-art">${["alle", "freelance", "bounty", "wettbewerb", "gesuch", "ausschreibung"].map(a => `<span class="chip${F.art === a ? " an" : ""}" data-v="${a}">${a === "alle" ? "Alle" : ART[a]}</span>`).join("")}</div>
      <div class="chips"><select class="feld" id="f-quelle"><option value="alle">Alle Quellen</option>${quellen.map(q => `<option>${esc(q)}</option>`).join("")}</select>
      <select class="feld" id="f-kat"><option value="alle">Alle Kategorien</option>${kats.map(q => `<option>${esc(q)}</option>`).join("")}</select>
      <input class="feld" id="f-q" placeholder="Suchen …"><label class="chip"><input type="checkbox" id="f-empf" checked> nur empfehlbar</label></div></div>
    <div class="tw"><table class="tbl karten"><thead><tr>
      <th class="l">Auftrag</th><th class="sort" data-s="rang">Rang ${tippI("Erwarteter Wert, bei weniger als 10 % Chance anteilig abgewertet. Danach sind die Top 5 sortiert.")}</th><th class="sort" data-s="ew_eur">Erw. Wert</th><th class="sort" data-s="wert_eur">Wert</th><th class="sort" data-s="chance">Chance</th>
      <th class="sort" data-s="machbar">Machbar</th><th class="sort" data-s="eur_pro_std">€/Std.</th><th class="sort" data-s="gebote">Konk.</th><th class="sort" data-s="alter_tage">Alter</th></tr></thead>
      <tbody id="f-body"></tbody></table></div><div class="fuss" id="f-fuss"></div></div>`;
  const neu = () => {
    let l = D.eintraege.filter(e => (F.art === "alle" || e.art === F.art) && (F.quelle === "alle" || e.quelle === F.quelle) &&
      (F.kat === "alle" || e.kat_name === F.kat) && (!F.nurEmpf || e.empfehlbar) &&
      (!F.q || (e.titel + " " + (e.text || "")).toLowerCase().includes(F.q)));
    const s = F.sort, rich = s === "alter_tage" || s === "gebote" ? 1 : -1;
    l.sort((a, b) => ((a[s] ?? 1e9) - (b[s] ?? 1e9)) * rich);
    $("#f-body").innerHTML = l.slice(0, 400).map(e => `<tr class="klick" data-id="${esc(e.id)}">
      <td class="l titelzelle"><div class="tick">${esc(e.titel)}</div><div class="meta">${badgeArt(e)}<span>${esc(e.quelle)}</span><span>${esc(e.kat_name)}</span>${fbTag(e)}${e.aussortiert ? `<span class="neg">${esc((e.gruende || [])[0] || "aussortiert")}</span>` : ""}</div></td>
      <td class="m-r"><b>${zahl(e.rang, 1)}</b></td><td class="m-aus">${eur(e.ew_eur)}</td><td class="m-aus">${eur(e.wert_eur)}</td><td class="m-aus">${pct(e.chance, 1)}</td>
      <td class="m-aus">${pct(e.machbar)}<span class="balken"><i style="width:${Math.round(e.machbar * 100)}%"></i></span></td>
      <td class="m-aus">${eur(e.eur_pro_std)}</td><td class="m-aus">${zahl(e.gebote)}</td><td class="m-aus">${ok(e.alter_tage) ? zahl(e.alter_tage, e.alter_tage < 2 ? 1 : 0) + " T." : "–"}</td></tr>`).join("") ||
      `<tr><td colspan="9" class="leer">Keine Treffer mit diesen Filtern.</td></tr>`;
    $("#f-fuss").textContent = `${l.length} von ${D.eintraege.length} Einträgen (letzte 30 Tage). Klick auf eine Zeile öffnet Details.`;
  };
  $$("#f-art .chip").forEach(c => c.addEventListener("click", () => { F.art = c.dataset.v; $$("#f-art .chip").forEach(x => x.classList.toggle("an", x === c)); neu(); }));
  $("#f-quelle").addEventListener("change", ev => { F.quelle = ev.target.value; neu(); });
  $("#f-kat").addEventListener("change", ev => { F.kat = ev.target.value; neu(); });
  $("#f-q").addEventListener("input", ev => { F.q = ev.target.value.toLowerCase(); neu(); });
  $("#f-empf").addEventListener("change", ev => { F.nurEmpf = ev.target.checked; neu(); });
  $$("#t-alle th.sort").forEach(th => th.addEventListener("click", () => { F.sort = th.dataset.s; neu(); }));
  neu();
}
function oeffne(e) {
  if (!e) return;
  $("#m-kopf").innerHTML = `${metaZeile(e)}<div class="gross-tick" style="font-size:22px">${esc(e.titel)}</div>`;
  $("#m-inhalt").innerHTML = `<div class="held"><div>
      ${e.ki && e.ki.loesung ? `<p><b>Lösung:</b> ${esc(e.ki.loesung)}</p>` : ""}
      ${e.ki && e.ki.risiko ? `<p><b>Risiko:</b> ${esc(e.ki.risiko)}</p>` : ""}
      ${e.gruende && e.gruende.length ? `<div class="box fehler">${esc(e.gruende.join(" · "))}</div>` : ""}
      ${e.schwer && e.schwer.length ? `<p class="mute klein">Schwierig für KI: ${esc(e.schwer.join(", "))}</p>` : ""}
      <div class="lbl" style="margin-top:12px">Beschreibung (gekürzt)</div><p class="ink2">${esc(e.text)}</p>
      ${e.tags && e.tags.length ? `<div class="chips">${e.tags.map(t => `<span class="mtag">${esc(t)}</span>`).join("")}</div>` : ""}
      ${bewerbung(e)}${feedbackKnoepfe(e)}</div>${zahlenBox(e)}</div>`;
  $(".modal").classList.add("offen");
}

/* ---------- Quellen ---------- */
function quellenTab() {
  const zeilen = Object.entries(D.quellen).map(([n, q]) => {
    const l = q.laeufe || [], letzt = l[l.length - 1] || {}, schnitt = l.length ? l.reduce((s, x) => s + x.empfehlbar, 0) / l.length : 0;
    const fehler = ((L.quellen || {})[n] || {}).fehler || [];
    return `<tr><td class="l"><b>${esc(n)}</b>${fehler.length ? `<div class="klein neg" style="white-space:normal">${esc(fehler.slice(0, 2).join(" · "))}</div>` : ""}</td>
      <td><span class="status ${esc(q.status)}">${esc(q.status)}</span></td><td>${zahl(letzt.n)}</td><td>${zahl(letzt.empfehlbar)}</td><td>${zahl(schnitt, 1)}</td>
      <td>${spark(l.map(x => x.n), "--s1")}</td><td>${spark(l.map(x => x.empfehlbar), "--s3")}</td></tr>`;
  }).join("");
  $("#t-quellen").innerHTML = `<div class="card"><div class="ch"><div><h3 class="ct">Quellen</h3><div class="cs">Neue Quellen laufen zuerst im Test. Nach 5 Läufen mit genug brauchbaren Treffern werden sie aktiv, nach 10 schwachen Läufen pausiert.</div></div></div>
    <div class="tw"><table class="tbl"><thead><tr><th class="l">Quelle</th><th>Status</th><th>Letzter Lauf</th><th>Davon brauchbar</th><th>Ø brauchbar/Lauf</th><th>Einträge</th><th>Brauchbar</th></tr></thead><tbody>${zeilen}</tbody></table></div>
    <p class="fuss">Es werden nur offizielle Schnittstellen und öffentliche Feeds gelesen; bei Seiten ohne API wird robots.txt geprüft. Der Radar loggt sich nirgends ein, bewirbt sich nicht und kontaktiert niemanden.
    Optional: Mit den Secrets KAGGLE_USERNAME und KAGGLE_KEY kommen Kaggle-Wettbewerbe dazu.</p></div>`;
}

/* ---------- Lernen ---------- */
function lernenTab() {
  const g = D.gelernt || {}, sb = D.suchbegriffe || {}, a = D.annahmen;
  const fakt = (obj, name) => Object.keys(obj || {}).length ? Object.entries(obj).map(([k, v]) => `<tr><td class="l">${esc(name)}</td><td class="l">${esc(k)}</td><td class="${v >= 1 ? "pos" : "neg"}">× ${zahl(v, 2)}</td></tr>`).join("") : "";
  const faktoren = fakt(g.quelle_mult, "Gewinnchance") + fakt(g.wert_mult, "Wert-Schätzung") + fakt(g.kat_mult, "Interesse");
  const st = sb.stat || {};
  const sbTag = (q, aus) => { const s = st[q] || {}; return `<span class="sb${aus ? " aus" : ""}">${esc(q)}${s.laeufe ? `<b>${s.gut || 0}</b>` : ""}</span>`; };
  $("#t-lernen").innerHTML = `<div class="grid">
    <div class="card c7"><div class="ch"><div><h3 class="ct">Was der Radar gelernt hat</h3><div class="cs">Jede Anpassung mit Begründung, neueste zuerst</div></div></div>
      ${D.protokoll.length ? `<ol class="gedanken">${D.protokoll.slice(0, 40).map(p => `<li><div class="klein mute">${esc(zeit(p.zeit))}</div>${esc(p.text)}</li>`).join("")}</ol>` : '<div class="leer">Noch nichts.</div>'}</div>
    <div class="card c5"><div class="ch"><div><h3 class="ct">So lernt er</h3></div></div><ol class="gedanken">
      <li><b>Deine Rückmeldungen:</b> Beworben, Gewonnen, Verloren, Nicht interessant. Daraus werden Gewinnchance je Quelle, Interesse je Kategorie und Treffsicherheit der Wert-Schätzung angepasst (vorsichtig, wenige Ergebnisse zählen wenig).</li>
      <li><b>Quellen-Test:</b> Neue Quellen werden beobachtet und nach ihrer Ausbeute befördert oder pausiert.</li>
      <li><b>Suchbegriffe:</b> Jeder Lauf testet 2 neue Begriffe. Was Brauchbares findet, bleibt; was nichts bringt, fliegt raus.</li>
      <li><b>KI-Prüfung:</b> Die aussichtsreichsten neuen Aufträge prüft Claude auf Machbarkeit und Seriosität und schreibt den Bewerbungstext.</li></ol>
      <div class="lbl" style="margin-top:6px">Gelernte Faktoren</div>
      ${faktoren ? `<table class="tbl"><tbody>${faktoren}</tbody></table>` : '<p class="mute klein">Noch keine. Sobald du ein paar Rückmeldungen gibst, erscheinen hier die Anpassungen.</p>'}</div></div>
  <div class="grid"><div class="card c12"><div class="ch"><div><h3 class="ct">Suchbegriffe freelancer.com</h3><div class="cs">Zahl = brauchbare Treffer bisher</div></div></div>
    <div class="lbl">Aktiv</div><div class="sb-liste" style="margin:6px 0 12px">${(sb.aktiv || []).map(q => sbTag(q)).join("")}</div>
    <div class="lbl">Im Test / Warteschlange</div><div class="sb-liste" style="margin:6px 0 12px">${(sb.kandidaten || []).map(q => sbTag(q)).join("")}</div>
    <div class="lbl">Ausgemustert</div><div class="sb-liste" style="margin-top:6px">${(sb.ausgemustert || []).map(q => sbTag(q, true)).join("") || '<span class="mute klein">keine</span>'}</div></div></div>
  <div class="grid"><div class="card c12"><div class="ch"><div><h3 class="ct">Startannahmen</h3><div class="cs">Werden durch Rückmeldungen überschrieben. Umrechnung ${zahl(a.usd_eur, 2)} € je $ (nur grob, zum Sortieren).</div></div></div>
    <div class="zwei"><table class="tbl"><thead><tr><th class="l">Art</th><th>Gewinnchance (0 Konkurrenz)</th><th>Bewerben</th><th>Abliefern</th><th>frisch bis</th></tr></thead><tbody>
      ${Object.keys(a.gewinn_basis).map(k => `<tr><td class="l">${ART[k]}</td><td>${pct(a.gewinn_basis[k])}</td><td>${a.leon_min[k][0]} Min.</td><td>${a.leon_min[k][1]} Min.</td><td>${a.frisch_tage[k]} T.</td></tr>`).join("")}</tbody></table>
    <table class="tbl"><thead><tr><th class="l">Kategorie</th><th>Machbar durch Claude</th></tr></thead><tbody>
      ${Object.values(a.kategorien).sort((x, y) => y.machbar - x.machbar).map(k => `<tr><td class="l">${esc(k.name)}</td><td>${pct(k.machbar)}<span class="balken"><i style="width:${k.machbar * 100}%"></i></span></td></tr>`).join("")}</tbody></table></div></div></div>`;
}

/* ---------- Ergebnisse ---------- */
function ergebnisseTab() {
  const r = D.ergebnis, quote = r.gewonnen + r.verloren ? r.gewonnen / (r.gewonnen + r.verloren) : null;
  const kp = [["Bewerbungen", zahl(r.beworben)], ["Gewonnen", zahl(r.gewonnen)], ["Verloren", zahl(r.verloren)], ["Gewinnquote", pct(quote)], ["Umsatz (gemeldet)", eur(r.umsatz)]];
  const stat = (D.gelernt || {}).stat_kat || {};
  $("#t-ergebnisse").innerHTML = `<div class="kpis">${kp.map(([k, v]) => `<div class="kpi"><div class="k">${k}</div><div class="v">${v}</div></div>`).join("")}</div>
    <div class="grid"><div class="card c7"><div class="ch"><h3 class="ct">Deine Rückmeldungen</h3></div>
      ${D.feedback.length ? `<div class="tw"><table class="tbl"><thead><tr><th class="l">Datum</th><th class="l">Auftrag</th><th>Status</th><th>Betrag</th></tr></thead><tbody>
        ${D.feedback.map(f => { const e = NACH_ID[f.id]; return `<tr${e ? ` class="klick" data-id="${esc(f.id)}"` : ""}><td class="l">${esc(tag(f.zeit))}</td><td class="l titelzelle">${esc(e ? e.titel : f.id)}</td><td><span class="fb ${esc(f.aktion)}">${esc(f.aktion)}</span></td><td>${f.betrag ? eur(f.betrag) : "–"}</td></tr>`; }).join("")}</tbody></table></div>`
        : '<p class="erkl">Noch keine Rückmeldungen. Tippe bei einem Auftrag auf „Beworben“ oder „Gewonnen“. Es öffnet sich GitHub mit einem fertigen Eintrag, du tippst nur auf „Submit“. Der nächste Lauf übernimmt ihn und lernt daraus.</p>'}</div>
    <div class="card c5"><div class="ch"><h3 class="ct">Nach Kategorie</h3></div>
      ${Object.keys(stat).length ? `<table class="tbl"><thead><tr><th class="l">Kategorie</th><th>Bew.</th><th>Gew.</th><th>Umsatz</th></tr></thead><tbody>${Object.entries(stat).map(([k, s]) => `<tr><td class="l">${esc((D.annahmen.kategorien[k] || {}).name || k)}</td><td>${s.beworben}</td><td>${s.gewonnen}</td><td>${eur(s.umsatz)}</td></tr>`).join("")}</tbody></table>` : '<p class="mute">Noch keine Daten.</p>'}
      <p class="fuss">Hinweis: Das Repository ist öffentlich. Rückmeldungen als GitHub-Issue sind für andere sichtbar. Beträge deshalb nur eintragen, wenn das für dich in Ordnung ist.</p></div></div>`;
}

function zeichneCharts() {
  const host = $("#ch-verlauf"); if (!host || !host.offsetParent) return;
  liniePlot(host, D.laeufe.map(l => l.zeit), [
    { name: "Erw. Wert Top 5 (€)", v: D.laeufe.map(l => l.top_ew || 0), farbe: "--s1", flaeche: true },
    { name: "Empfehlbare", v: D.laeufe.map(l => l.empfehlbar || 0), farbe: "--s3" }], v => zahl(v));
}
uebersicht(); alle(); quellenTab(); lernenTab(); ergebnisseTab();
let start = null; try { start = localStorage.getItem("auftrag_tab"); } catch (e) { }
if (start && $(`nav.tabs button[data-tab="${start}"]`)) $(`nav.tabs button[data-tab="${start}"]`).click(); else zeichneCharts();
window.addEventListener("resize", () => { clearTimeout(window._rz); window._rz = setTimeout(zeichneCharts, 150); });
})();
