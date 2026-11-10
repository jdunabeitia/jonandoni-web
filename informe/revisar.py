"""Informe: trabajos de ORCID/Crossref 2025-2026 frente a la lista de la web (solo lectura, no envía correos)."""
import json, sys
sys.path.insert(0, ".")
import os
os.environ.setdefault("FICHA_SECRET", "x"); os.environ.setdefault("GMAIL_USER", "x@x.com")
import sistema as S
import requests
pubs = S.load(S.PUBS, [])
out = {"orcid": [], "crossref": [], "prensa": [], "sin_doi_2026": []}
dois = {S.normdoi(e.get("doi", "")).lower() for e in pubs if e.get("doi")}
def en_web(t, d):
    return (d and d.lower() in dois) or any(S.similar(t, e["title"]) > .9 for e in pubs)
for w in S.orcid_works():
    if w["year"] >= 2025:
        out["orcid"].append(dict(w, en_web=en_web(w["title"], w["doi"])))
r = requests.get("https://api.crossref.org/works", headers=S.UA, timeout=60, params={
    "query.author": "Jon Andoni Duñabeitia", "filter": "from-pub-date:2025-06-01", "rows": 100, "select": "DOI,title,author,container-title,issued,type,volume,issue,page,article-number"})
for it in r.json()["message"]["items"]:
    if not any("dunabeitia" in S.norm(a.get("family", "")) for a in it.get("author", [])):
        continue
    t = (it.get("title") or [""])[0]
    e = S.from_crossref(it)
    out["crossref"].append(dict(title=t, doi=it["DOI"], year=e["year"], journal=e["journal"], type=it.get("type"), en_web=en_web(t, it["DOI"])))
for e in pubs:
    if e["year"] >= 2025 and ("prensa" in e["journal"].lower() or not e.get("doi")):
        out["prensa"].append({k: e.get(k) for k in ("year", "title", "journal", "doi", "pdf")})
    if e["year"] >= 2025 and not e.get("pdf"):
        out["sin_doi_2026"].append({k: e.get(k) for k in ("year", "title", "doi")})
for e in out["prensa"]:
    try:
        r = requests.get("https://api.crossref.org/works", headers=S.UA, timeout=30, params={"query.bibliographic": e["title"], "rows": 3})
        for it in r.json()["message"]["items"]:
            if S.similar((it.get("title") or [""])[0], e["title"]) > .9:
                e["crossref_ahora"] = S.from_crossref(it)["journal"]; break
    except Exception as ex:
        e["error"] = str(ex)
json.dump(out, open("informe/resultado.json", "w"), ensure_ascii=False, indent=1)
print("ok")
