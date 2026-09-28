# Lee tu perfil de Google Scholar y guarda las citas por año en data/citations.json
import json, re, sys, datetime, urllib.request

USER = "zOf2BvcAAAAJ"
URL = f"https://scholar.google.com/citations?user={USER}&hl=en"
OUT = "data/citations.json"

req = urllib.request.Request(URL, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
})
try:
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
except Exception as e:
    print("No se pudo leer Scholar; se mantienen los datos anteriores:", e)
    sys.exit(0)

years = [int(y) for y in re.findall(r'class="gsc_g_t"[^>]*>(\d{4})<', html)]
# Cada barra lleva su posición (z-index) para cuadrar años sin citas
bars = re.findall(r'class="gsc_g_a"[^>]*z-index:\s*(\d+)[^>]*>\s*<span class="gsc_g_al">(\d+)<', html)
stats = [int(x) for x in re.findall(r'class="gsc_rsb_std">(\d+)<', html)]

if not years or len(stats) < 5:
    print("Scholar no devolvió datos válidos (quizá un captcha); se mantienen los anteriores.")
    sys.exit(0)

n = len(years)
counts = [0] * n
if bars:
    for z, v in bars:
        i = n - int(z)          # z-index 1 = último año
        if 0 <= i < n:
            counts[i] = int(v)
else:
    # Plan B: sin posiciones, se asignan los valores a los últimos años
    vals = [int(v) for v in re.findall(r'class="gsc_g_al">(\d+)<', html)]
    counts[n - len(vals):] = vals

data = {
    "updated": datetime.date.today().isoformat(),
    "total": stats[0],
    "h_index": stats[2],
    "i10_index": stats[4],
    "years": years,
    "citations": counts,
}
with open(OUT, "w") as f:
    json.dump(data, f, indent=2)
print("Actualizado:", data)
