# -*- coding: utf-8 -*-
"""Baut das Dashboard: eine einzelne HTML-Datei aus web/app.css, web/app.js und den Daten als JSON."""
import json
import os

BASIS = os.path.dirname(os.path.abspath(__file__))


def _lies(name):
    """Sucht die Datei im Ordner web/ oder direkt neben diesem Skript."""
    for pfad in (os.path.join(BASIS, "web", name), os.path.join(BASIS, name)):
        if os.path.exists(pfad):
            with open(pfad, encoding="utf-8") as f:
                return f.read()
    raise FileNotFoundError(f"{name} fehlt – bitte ins Repository hochladen")


def erstelle(D):
    daten = json.dumps(D, ensure_ascii=False, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex"><meta name="color-scheme" content="light dark">
<title>Radar</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400..800&display=swap" rel="stylesheet">
<style>{_lies("app.css")}</style></head>
<body><main></main>
<script type="application/json" id="daten">{daten}</script>
<script>{_lies("app.js")}</script>
</body></html>"""
