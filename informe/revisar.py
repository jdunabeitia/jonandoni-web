"""Informe 2: datos completos de Crossref para DOIs candidatos (solo lectura)."""
import json, sys, os
sys.path.insert(0, ".")
os.environ.setdefault("FICHA_SECRET", "x"); os.environ.setdefault("GMAIL_USER", "x@x.com")
import sistema as S
DOIS = ["10.3389/fnagi.2026.1916339", "10.3389/fpsyg.2026.1921905", "10.1016/j.yebeh.2026.111176",
        "10.5114/biolsport.2026.154946", "10.35462/flv140.7", "10.1037/tmb0000216",
        "10.1007/s44202-026-00679-7"]
out = {}
for d in DOIS:
    m = S.crossref(d)
    if m:
        e = S.from_crossref(m)
        e["autores_completos"] = [f"{a.get('family','')}, {a.get('given','')} | {', '.join(x.get('name','') for x in a.get('affiliation', []))}" for a in m.get("author", [])]
        out[d] = e
import requests
r = requests.get("https://api.crossref.org/works", headers=S.UA, timeout=30, params={"query.bibliographic": "Visual Attention in Bilingual Instructional Videos Audiovisual Congruency", "rows": 3})
for it in r.json()["message"]["items"]:
    if "bilingual instructional" in S.norm((it.get("title") or [""])[0]):
        out[it["DOI"]] = S.from_crossref(it); break
json.dump(out, open("informe/resultado.json", "w"), ensure_ascii=False, indent=1)
