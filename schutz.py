# -*- coding: utf-8 -*-
"""
Passwortschutz: Journal und Dashboard werden mit AES-256-GCM verschlüsselt
(Schlüssel aus dem Passwort per PBKDF2-SHA256, 250.000 Runden).
Im öffentlichen Repository liegt so nur Kauderwelsch; ohne Passwort sieht niemand etwas.
"""
import base64
import json
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

RUNDEN = 250_000


def _schluessel(passwort, salz):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salz, iterations=RUNDEN)
    return kdf.derive(passwort.encode("utf-8"))


def verschluesseln(daten: bytes, passwort: str) -> str:
    salz, nonce = os.urandom(16), os.urandom(12)
    ct = AESGCM(_schluessel(passwort, salz)).encrypt(nonce, daten, None)
    return base64.b64encode(salz + nonce + ct).decode("ascii")


def entschluesseln(text: str, passwort: str) -> bytes:
    roh = base64.b64decode(text)
    salz, nonce, ct = roh[:16], roh[16:28], roh[28:]
    return AESGCM(_schluessel(passwort, salz)).decrypt(nonce, ct, None)


def journal_laden(pfad_enc, passwort):
    with open(pfad_enc, encoding="ascii") as f:
        return json.loads(entschluesseln(f.read().strip(), passwort).decode("utf-8"))


def journal_speichern(dep, pfad_enc, passwort):
    os.makedirs(os.path.dirname(pfad_enc), exist_ok=True)
    daten = json.dumps(dep, ensure_ascii=False, default=float).encode("utf-8")
    tmp = pfad_enc + ".tmp"
    with open(tmp, "w", encoding="ascii") as f:
        f.write(verschluesseln(daten, passwort))
    os.replace(tmp, pfad_enc)


def dashboard_sperren(html: str, passwort: str) -> str:
    """Packt das fertige Dashboard in eine Seite mit Passwortabfrage (Entschlüsselung im Browser)."""
    blob = verschluesseln(html.encode("utf-8"), passwort)
    return """<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="robots" content="noindex">
<title>Radar</title><style>
:root{--bg:#f4f4f1;--card:#fcfcfb;--ink:#0b0b0b;--ink3:#8a8984;--line:#e6e5e0;--s1:#2a78d6;--bad:#c93333}
@media (prefers-color-scheme:dark){:root{--bg:#111110;--card:#1a1a19;--ink:#f0efec;--ink3:#8f8e86;--line:#2c2c2a;--s1:#3987e5;--bad:#ec6b6b}}
*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;background:var(--bg);color:var(--ink);
font:16px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,system-ui,sans-serif;padding:16px}
form{width:100%;max-width:340px;background:var(--card);border:1px solid var(--line);border-radius:16px;padding:22px}
h1{font-size:22px;margin:0 0 4px}p{margin:0 0 16px;color:var(--ink3);font-size:14px}
input[type=password]{width:100%;font:inherit;padding:12px 14px;border-radius:10px;border:1px solid var(--line);background:var(--bg);color:var(--ink)}
label{display:flex;gap:8px;align-items:center;font-size:14px;color:var(--ink3);margin:12px 0 16px}
button{width:100%;font:inherit;font-weight:600;padding:12px;border:0;border-radius:10px;background:var(--s1);color:#fff;cursor:pointer}
#f{color:var(--bad);font-size:14px;min-height:20px;margin-top:10px}
</style></head><body>
<form id="form"><h1>Radar</h1><p>Privat. Bitte Passwort eingeben.</p>
<input id="pw" type="password" autocomplete="current-password" placeholder="Passwort" required>
<label><input id="merk" type="checkbox" checked> Auf diesem Gerät merken</label>
<button type="submit">Öffnen</button><div id="f"></div></form>
<script>
const B="__BLOB__",R=__RUNDEN__;
const b64=s=>Uint8Array.from(atob(s),c=>c.charCodeAt(0));
async function oeffne(pw){
  const roh=b64(B),salz=roh.slice(0,16),iv=roh.slice(16,28),ct=roh.slice(28);
  const basis=await crypto.subtle.importKey("raw",new TextEncoder().encode(pw),"PBKDF2",false,["deriveKey"]);
  const key=await crypto.subtle.deriveKey({name:"PBKDF2",salt:salz,iterations:R,hash:"SHA-256"},basis,{name:"AES-GCM",length:256},false,["decrypt"]);
  const klar=await crypto.subtle.decrypt({name:"AES-GCM",iv},key,ct);
  return new TextDecoder().decode(klar);
}
async function los(pw,merken){
  try{const html=await oeffne(pw);
    if(merken){try{localStorage.setItem("radar_pw",pw)}catch(e){}}
    document.open();document.write(html);document.close();
  }catch(e){document.getElementById("f").textContent="Falsches Passwort.";try{localStorage.removeItem("radar_pw")}catch(_){}}
}
document.getElementById("form").addEventListener("submit",ev=>{ev.preventDefault();
  los(document.getElementById("pw").value,document.getElementById("merk").checked)});
let g=null;try{g=localStorage.getItem("radar_pw")}catch(e){}
if(g)los(g,true);
</script></body></html>""".replace("__BLOB__", blob).replace("__RUNDEN__", str(RUNDEN))
