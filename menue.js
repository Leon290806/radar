/* Gemeinsames Menü: zwischen Aktien-, Auftrags- und Smart-Money-Radar wechseln (gleiches Passwort, bleibt gemerkt). */
window.radarMenue = function (aktiv, titel) {
  var vor = aktiv === "aktien" ? "" : "../";
  var L = [
    ["aktien", "Aktien-Radar", "Strategie, Portfolio, Insider", vor || "./"],
    ["auftraege", "Auftrags-Radar", "Aufträge finden und bieten", vor + "auftraege/"],
    ["bitcoin", "Bitcoin-Radar", "Langfrist-Bewertung: Power Law, On-Chain, Zyklus", vor + "bitcoin/"],
    ["smart", "Smart-Money-Radar", "Top-Trader beobachten (Papier-Test)", vor + "smart/"]
  ];
  return '<details class="wechsler"><summary title="Radar wechseln"><h1>' + titel + '</h1>' +
    '<svg viewBox="0 0 24 24" fill="none" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg></summary>' +
    '<div class="wliste">' + L.map(function (x) {
      return '<a href="' + x[3] + '" class="' + (x[0] === aktiv ? "aktiv" : "") + '"><b>' + x[1] + '</b><span>' + x[2] + '</span></a>';
    }).join("") + '</div></details>';
};
document.addEventListener("click", function (ev) {
  document.querySelectorAll("details.wechsler[open]").forEach(function (d) { if (!d.contains(ev.target)) d.removeAttribute("open"); });
});
