"""
Sistema automático de jonandoni.com (versión Vercel)

  python sistema.py prueba      -> te envía una ficha de prueba (no cambia la web)
  python sistema.py quincenal   -> citas + novedades de ORCID + errores + resumen (días 1 y 15)
  python sistema.py buzon       -> lee tus respuestas por correo (cada 10 minutos)
  python sistema.py aviso_error -> te avisa por correo si una tarea falla

Publicar = añadir a data/publications.json, guardar el PDF en public/ y fabricar la web (build.py).
Al guardarse los cambios en GitHub, Vercel publica la web sola en 1-2 minutos.
"""
import datetime, difflib, email, hashlib, hmac, imaplib, json, os, re, smtplib, subprocess, sys, traceback
import unicodedata, urllib.parse
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import make_msgid, parseaddr
import requests
from bs4 import BeautifulSoup

CFG = json.load(open("config.json", encoding="utf-8"))
PUBS, I18N, CIT = "data/publications.json", "data/i18n.json", "data/citations.json"
IGN, FICHAS, PROC = "data/ignored.json", "data/fichas.json", "data/procesados.json"
TODAY = datetime.date.today()
UA = {"User-Agent": "jonandoni-web/2.0 (+https://jonandoni.com)"}
HDR = "X-Jonandoni-Sistema"
MARK = "✂ Escribe tu respuesta encima de esta línea ✂"


# ---------------------------------------------------------------- utilidades
def load(p, d=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except FileNotFoundError:
        return d

def save(p, o):
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    json.dump(o, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

def ws(s):
    return re.sub(r"\s+", " ", (s or "").replace("\xa0", " ")).strip()

def norm(s):
    s = unicodedata.normalize("NFKD", ws(s).lower())
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in s if not unicodedata.combining(c))).strip()

def slug(s):
    return norm(s).replace(" ", "-")

def normdoi(d):
    d = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", ws(d), flags=re.I)
    return d.rstrip(".")

def similar(a, b):
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()

def esc(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def log(*a):
    print(*a, flush=True)

def topics():
    return load(I18N, {}).get("topics_order", []) or sorted({e["topic"] for e in load(PUBS, [])})

def build():
    subprocess.run([sys.executable, "build.py"], check=True)


# ---------------------------------------------------------------- fuentes externas
def crossref(doi):
    r = requests.get("https://api.crossref.org/works/" + urllib.parse.quote(doi), headers=UA, timeout=30)
    return r.json()["message"] if r.ok else None

def initials(given):
    return " ".join(p[0].upper() + "." for p in re.split(r"[\s\-]+", given or "") if p)

def apa(e):
    au = e["authors"].replace("; ", ", ")
    seg = [x for x in e["journal"].split(" · ") if not x.startswith("DOI") and not re.fullmatch(r"\d{4}", x)]
    j = seg[0] if seg else ""
    rest = ", ".join(x for x in seg[1:] if "prensa" not in x.lower())
    s = f"{au} ({e['year']}). {e['title']}. {j}" + (f", {rest}" if rest else "")
    return s + (f". https://doi.org/{e['doi']}" if e.get("doi") else ".")

def from_crossref(m):
    au = [f"{a.get('family', '')}, {initials(a.get('given', ''))}".strip(", ") for a in m.get("author", [])]
    authors = "; ".join(au[:10]) + ("; et al." if len(au) > 10 else "")
    title = ws(re.sub(r"<[^>]+>", "", (m.get("title") or [""])[0]))
    journal = (m.get("container-title") or [""])[0]
    dp = (m.get("issued") or m.get("published") or {}).get("date-parts", [[TODAY.year]])
    year = dp[0][0] or TODAY.year
    vol, iss = m.get("volume", ""), m.get("issue", "")
    vi = f"{vol}({iss})" if vol and iss else vol
    pages = m.get("page") or m.get("article-number") or ""
    doi = normdoi(m.get("DOI", ""))
    line = " · ".join(x for x in [journal, str(year), ", ".join(x for x in [vi, pages] if x), f"DOI: {doi}" if doi else ""] if x)
    t = m.get("type", "")
    typ = "Capítulo / libro" if t.startswith("book") else ("Conferencia" if "proceedings" in t else "Artículo")
    if re.search(r"\breview\b", title, re.I) and typ == "Artículo":
        typ = "Review"
    e = {"year": year, "topic": "", "type": typ, "title": title, "authors": authors, "journal": line,
         "journal_en": line, "doi": doi, "pdf": "", "source": f"https://doi.org/{doi}" if doi else ""}
    e["citation"] = apa(e)
    return e

def orcid_works():
    r = requests.get(f"https://pub.orcid.org/v3.0/{CFG['orcid']}/works", headers={**UA, "Accept": "application/json"}, timeout=30)
    r.raise_for_status()
    out = []
    for g in r.json().get("group", []):
        s = g["work-summary"][0]
        ids = (s.get("external-ids") or {}).get("external-id") or []
        doi = next((normdoi(i["external-id-value"]) for i in ids if i.get("external-id-type") == "doi"), "")
        year = int(((s.get("publication-date") or {}).get("year") or {}).get("value") or 0)
        out.append({"title": s["title"]["title"]["value"], "doi": doi, "year": year})
    return out


# ---------------------------------------------------------------- revisión de errores
def entry_key(e):
    return f"{e['year']}-{slug(e['title'])[:60]}"

def local_file(url):
    u = re.sub(r"^https?://(www\.)?jonandoni\.com", "", url or "")
    return "public" + urllib.parse.unquote(u) if u.startswith("/") else None

def find_errors(entries):
    out, seen = [], {}
    for e in entries:
        k = entry_key(e)
        if e.get("source"):
            host = urllib.parse.urlparse(e["source"]).netloc
            if not host or ".." in host or "." not in host.strip("."):
                out.append((f"corr:{k}:fuente", "Enlace roto", f"El enlace «Fuente original» está mal formado:\n{e['source']}",
                            dict(e, source=f"https://doi.org/{e['doi']}" if e.get("doi") else "")))
        if e.get("pdf"):
            fn = e["pdf"].lower().rsplit("/", 1)[-1]
            if not fn.endswith(".pdf"):
                out.append((f"corr:{k}:nopdf", "No es un PDF", f"El archivo vinculado no es un PDF:\n{e['pdf']}\n\nAdjunta el PDF correcto al responder.", dict(e)))
            lf = local_file(e["pdf"])
            if lf and not os.path.exists(lf):
                out.append((f"corr:{k}:pdfcaido", "PDF no encontrado", f"No encuentro el archivo del PDF:\n{e['pdf']}\n\nAdjunta el PDF al responder.", dict(e)))
            code = re.search(r"(s\d{5}-\d{3}-\d{5}-[0-9x])", fn)
            if code and e.get("doi") and code.group(1) not in e["doi"].lower():
                out.append((f"corr:{k}:pdfotro", "PDF de otro artículo",
                            f"El nombre del PDF ({fn}) no corresponde con el DOI {e['doi']}. Puede ser el PDF de otro trabajo.\n\nAdjunta el PDF correcto al responder.", dict(e)))
        key = normdoi(e.get("doi", "")).lower() or norm(e["title"])
        if key in seen:
            out.append((f"corr:{k}:duplicado", "Posible duplicado",
                        f"Parece la misma publicación que «{seen[key]['title']}» ({seen[key]['year']}). Pulsa Ignorar si no lo es.", dict(e)))
        seen[key] = e
    for e in entries:   # en prensa o sin DOI: ¿ya está publicado?
        if e.get("doi") and "prensa" not in e["journal"].lower():
            continue
        try:
            r = requests.get("https://api.crossref.org/works", headers=UA, timeout=30, params={
                "query.bibliographic": e["title"], "query.author": CFG["author_surname"], "rows": 3})
            for it in r.json()["message"]["items"]:
                if it.get("DOI") and similar((it.get("title") or [""])[0], e["title"]) > .92 and normdoi(it["DOI"]).lower() != normdoi(e.get("doi", "")).lower():
                    n = from_crossref(it)
                    n.update(topic=e["topic"], type=e["type"], pdf=e["pdf"])
                    out.append((f"corr:{entry_key(e)}:publicado", "Ya publicado",
                                "Tenías este trabajo en prensa o sin DOI, y ya aparece publicado. Te propongo actualizarlo.", n))
                    break
        except Exception:
            pass
    return out


# ---------------------------------------------------------------- correo
def gmail_user():
    return os.environ["GMAIL_USER"].strip()

def buzon():
    u, d = gmail_user().split("@")
    return f"{u}+{CFG.get('alias', 'jonandoni')}@{d}"

def token(n):
    return hmac.new(os.environ["FICHA_SECRET"].encode(), str(n).encode(), hashlib.sha256).hexdigest()[:8]

def send(subject, html, text):
    m = EmailMessage()
    m["From"] = f"Web jonandoni.com <{gmail_user()}>"
    m["To"] = buzon()
    cc = [x for x in CFG.get("copia_a", []) if x]
    if cc:
        m["Cc"] = ", ".join(cc)
    m["Subject"] = subject
    m["Message-ID"] = make_msgid(domain="jonandoni.com")
    m[HDR] = "1"
    m.set_content(text)
    m.add_alternative(html, subtype="html")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as s:
        s.login(gmail_user(), os.environ["GMAIL_APP_PASSWORD"].replace(" ", ""))
        s.send_message(m)
    log("Correo enviado:", subject)

def btn(label, subject, body, color="#0f6fa8"):
    href = "mailto:" + buzon() + "?subject=" + urllib.parse.quote(subject) + "&body=" + urllib.parse.quote(body)
    return (f'<a href="{href}" style="display:inline-block;margin:4px 6px 4px 0;padding:10px 14px;border-radius:8px;'
            f'background:{color};color:#fff;text-decoration:none;font-weight:600;font-size:14px">{esc(label)}</a>')

def ficha_rows(e):
    rows = [("Etiqueta", e.get("topic") or "— (elígela abajo)"), ("Tipo", e.get("type")), ("Año", e.get("year")),
            ("Título", e.get("title")), ("Autores", e.get("authors")), ("Revista", e.get("journal")),
            ("DOI", e.get("doi")), ("Fuente", e.get("source")), ("PDF", e.get("pdf") or "— (adjúntalo al responder)")]
    return "".join(f'<tr><td style="padding:4px 10px 4px 0;color:#5c6b7d;vertical-align:top;white-space:nowrap">{k}</td>'
                   f'<td style="padding:4px 0">{esc(v)}</td></tr>' for k, v in rows)

def edit_body(e):
    return ("publicar\n\n"
            f"etiqueta: {e.get('topic', '')}\ntipo: {e.get('type', '')}\naño: {e.get('year', '')}\n"
            f"título: {e.get('title', '')}\nautores: {e.get('authors', '')}\nrevista: {e.get('journal', '')}\n"
            f"revista_en: {e.get('journal_en', '')}\ndoi: {e.get('doi', '')}\nfuente: {e.get('source', '')}\n\n"
            "(Corrige las líneas que haga falta y, si tienes el PDF, adjúntalo antes de enviar)\n")

def mail_ficha(f):
    e, n = f["entry"], f["n"]
    subj = f"[jonandoni-web] Ficha {n} · {token(n)} · {f['title']}"
    re_subj = "Re: " + subj
    if f["kind"] in ("nueva", "prueba") and not e.get("topic"):
        buttons = "<p style='margin:14px 0 4px'><b>Publicar con la etiqueta:</b></p>" + "".join(
            btn(t, re_subj, f"publicar\netiqueta: {t}\n\n(Si tienes el PDF, adjúntalo a este correo antes de enviarlo)\n") for t in topics())
    elif f["kind"] == "info":
        buttons = ""
    else:
        buttons = btn("✅ Aplicar", re_subj, "publicar\n\n(Si hace falta el PDF correcto, adjúntalo antes de enviar)\n", "#1a7f37")
    if f["kind"] != "info":
        buttons += btn("✏️ Corregir datos…", re_subj, edit_body(e), "#5c6b7d")
    buttons += btn("Ignorar", re_subj, "ignorar\n", "#b3261e")
    table = f"<table style='border-collapse:collapse;font-size:14px;margin:6px 0 10px'>{ficha_rows(e)}</table>" if e else ""
    html = f"""<div style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;font-size:15px;color:#142033;max-width:640px">
<p style="font-size:13px;color:#5c6b7d;margin:0 0 6px">Web jonandoni.com · Ficha {n}</p>
<h2 style="font-size:19px;margin:0 0 10px;font-family:Georgia,serif;color:#061a33">{esc(f['heading'])}</h2>
<p style="margin:0 0 12px">{f['why']}</p>{table}{buttons}
<p style="font-size:13px;color:#5c6b7d;margin-top:14px">Cada botón abre una respuesta ya escrita: <b>adjunta el PDF si lo tienes y pulsa Enviar</b>. También puedes responder a este correo escribiendo <i>publicar</i> (y la etiqueta) o <i>ignorar</i>. En unos 10 minutos recibirás la confirmación. Nada se publica sin tu respuesta.</p>
<p style="font-size:12px;color:#8c959f;border-top:1px solid #d0d7de;padding-top:8px;margin-top:18px">{MARK}</p></div>"""
    text = (f"{f['heading']}\n\n{re.sub('<[^>]+>', '', f['why'])}\n\n" + edit_body(e).replace("publicar\n\n", "") +
            "\nResponde con 'publicar' (y la etiqueta, si falta) o 'ignorar'. Adjunta el PDF si lo tienes.\n\n" + MARK)
    send(subj, html, text)

def new_ficha(kind, key, heading, why, entry, title=None):
    fs = load(FICHAS, {"next": 1, "items": {}})
    if any(x["key"] == key and x["status"] == "abierta" for x in fs["items"].values()):
        return None
    n = fs["next"]; fs["next"] += 1
    icon = {"nueva": "🆕 ", "correccion": "🛠 ", "prueba": "🧪 ", "info": "ℹ️ "}.get(kind, "")
    f = {"n": n, "kind": kind, "key": key, "heading": heading, "why": why, "entry": entry,
         "title": icon + (title or entry.get("title") or heading)[:70], "status": "abierta", "created": TODAY.isoformat()}
    fs["items"][str(n)] = f
    save(FICHAS, fs)
    mail_ficha(f)
    return f

def open_keys():
    return {x["key"] for x in load(FICHAS, {"items": {}})["items"].values() if x["status"] == "abierta"}

def close_ficha(n, status):
    fs = load(FICHAS)
    fs["items"][str(n)].update(status=status, closed=TODAY.isoformat())
    save(FICHAS, fs)

def confirm(f, ok, detail):
    lines = detail.splitlines()
    subj = f"[jonandoni-web] {'✅' if ok else '⚠️'} Ficha {f['n']}: {f['title']}"
    html = (f'<div style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;font-size:15px;max-width:640px">'
            f'<p style="font-size:17px;color:{"#1a7f37" if ok else "#9a6700"};font-weight:600">{esc(lines[0])}</p>'
            + (f'<p style="white-space:pre-wrap;font-size:14px">{esc(chr(10).join(lines[1:]))}</p>' if len(lines) > 1 else "") +
            f'<p><a href="https://jonandoni.com/publicaciones-cientificas/">Ver publicaciones (ES)</a> · '
            f'<a href="https://jonandoni.com/en/publications/">(EN)</a> · la web se actualiza en 1-2 minutos.</p></div>')
    send(subj, html, detail)


# ---------------------------------------------------------------- leer tus respuestas
FIELDS = {"etiqueta": "topic", "tipo": "type", "ano": "year", "titulo": "title", "autores": "authors",
          "revista": "journal", "revista en": "journal_en", "doi": "doi", "fuente": "source"}
CUT = re.compile(r"^\s*(>|✂|-{2,}\s*(Original|Mensaje original)|_{5,}|(On|El) .{5,200}(wrote|escribió)\s*:|(From|De|Enviado el|Sent):\s)", re.I)

def parse_fields(text):
    out = {}
    for line in (text or "").splitlines():
        m = re.match(r"^\s*([^:\n]{2,20}):\s?(.*)$", line)
        if m and norm(m.group(1)) in FIELDS:
            out[FIELDS[norm(m.group(1))]] = ws(m.group(2))
    return out

def own_part(text):
    out = []
    for line in text.replace("\r", "").split("\n"):
        if CUT.match(line):
            break
        out.append(line)
    return "\n".join(out)

def match_topic(v):
    i18n, ts = load(I18N, {}), topics()
    en = {norm(i18n.get("topics", {}).get(t, t)): t for t in ts}
    for t in ts:
        if norm(v) == norm(t):
            return t
    if norm(v) in en:
        return en[norm(v)]
    cand = [t for t in ts if norm(v) and norm(t).startswith(norm(v))]
    return cand[0] if len(cand) == 1 else None

def decode(s):
    return str(make_header(decode_header(s or "")))

def body_text(msg):
    plain = html = None
    for p in msg.walk():
        if p.get_content_maintype() == "multipart" or p.get_filename():
            continue
        if p.get_content_type() == "text/plain" and plain is None:
            plain = p.get_payload(decode=True).decode(p.get_content_charset() or "utf-8", "replace")
        elif p.get_content_type() == "text/html" and html is None:
            html = p.get_payload(decode=True).decode(p.get_content_charset() or "utf-8", "replace")
    if plain is None and html:
        plain = BeautifulSoup(html, "html.parser").get_text("\n")
    return plain or ""

def pdfs_of(msg):
    out = []
    for p in msg.walk():
        if p.get_content_maintype() == "multipart":
            continue
        name, data = decode(p.get_filename() or ""), p.get_payload(decode=True)
        if data and data[:4] == b"%PDF":
            out.append((name or "documento.pdf", data))
    return out

def all_mail(im):
    for b in im.list()[1] or []:
        line = b.decode(errors="replace")
        if "\\All" in line:
            return line.split(' "/" ')[-1]
    return "INBOX"

def cmd_buzon():
    proc = load(PROC, [])
    im = imaplib.IMAP4_SSL("imap.gmail.com")
    im.login(gmail_user(), os.environ["GMAIL_APP_PASSWORD"].replace(" ", ""))
    im.select(all_mail(im), readonly=True)
    typ, data = im.search(None, "X-GM-RAW", '"subject:(jonandoni-web Ficha) newer_than:30d"')
    allowed = [a.lower() for a in CFG.get("remitentes_permitidos", []) if a] + [gmail_user().lower()]
    for i in (data[0].split() if data and data[0] else []):
        msg = email.message_from_bytes(im.fetch(i, "(RFC822)")[1][0][1])
        mid = msg.get("Message-ID", "") or f"id-{i.decode()}"
        if mid in proc or msg.get(HDR):
            continue
        proc.append(mid); save(PROC, proc[-800:])
        handle_reply(decode(msg.get("Subject")), parseaddr(msg.get("From", ""))[1].lower(), body_text(msg), pdfs_of(msg), allowed)
    im.logout()

def handle_reply(subject, sender, text, pdfs, allowed):
    m = re.search(r"Ficha (\d+) · ([0-9a-f]{8})", subject)
    if not m:
        return
    n = int(m.group(1))
    if not hmac.compare_digest(m.group(2), token(n)):
        log("Código de ficha incorrecto; se ignora:", subject); return
    if allowed and sender not in allowed:
        log("Remitente no autorizado:", sender); return
    f = load(FICHAS, {"items": {}})["items"].get(str(n))
    if not f:
        return
    if f["status"] != "abierta":
        confirm(f, False, f"Esta ficha ya estaba cerrada ({f['status']}). No he hecho nada."); return
    mine = own_part(text)
    words = set(norm(mine).split())
    try:
        if "ignorar" in words:
            ign = load(IGN, {}); ign[f["key"]] = TODAY.isoformat(); save(IGN, ign)
            close_ficha(n, "ignorada")
            confirm(f, True, "De acuerdo, no volveré a preguntarte por esto.")
        elif words & {"publicar", "aplicar"}:
            ok, detail = apply_ficha(f, parse_fields(mine), mine, pdfs)
            if ok:
                close_ficha(n, "publicada")
            confirm(f, ok, detail)
        else:
            confirm(f, False, "No he encontrado la palabra «publicar» ni «ignorar» en tu respuesta.\nVuelve a pulsar uno de los botones del correo de la ficha.")
    except Exception:
        confirm(f, False, "Ha habido un error al procesar tu respuesta. No se ha publicado nada.\n" + traceback.format_exc()[-1200:])
        raise

def apply_ficha(f, fields, raw, pdfs):
    entries = load(PUBS, [])
    e = dict(f["entry"]); e.update({k: v for k, v in fields.items() if v})
    if not fields.get("topic"):   # respuesta libre: "publicar salud cognitiva"
        hit = next((t for t in sorted(topics(), key=len, reverse=True) if f" {norm(t)} " in f" {norm(raw)} "), None)
        if hit:
            e["topic"] = hit
    topic = match_topic(e.get("topic", ""))
    if not topic:
        return False, (f"Falta la etiqueta o no la reconozco («{e.get('topic', '')}»). No he publicado nada.\n"
                       "Vuelve al correo de la ficha y pulsa el botón de la etiqueta que quieras.")
    e["topic"] = topic
    e["year"] = int(re.sub(r"\D", "", str(e.get("year", ""))) or TODAY.year)
    e["doi"] = normdoi(e.get("doi", ""))
    if e["doi"] and not e.get("source"):
        e["source"] = f"https://doi.org/{e['doi']}"
    e["journal_en"] = (fields.get("journal_en") or e.get("journal_en") or e["journal"]).replace("En prensa", "In press")
    if f["kind"] == "prueba":
        pdf = f"PDF recibido: {pdfs[0][0]} ({len(pdfs[0][1]) // 1024} KB)" if pdfs else "Sin PDF adjunto"
        return True, (f"¡La prueba ha funcionado! Tu respuesta ha llegado y el sistema la ha entendido.\n"
                      f"Etiqueta elegida: {topic}\n{pdf}\n(Es una prueba: no se ha cambiado nada en la web.)")
    note = ""
    if pdfs:
        fam = slug(e["authors"].split(",")[0]) or "articulo"
        words = [w for w in slug(e["title"]).split("-") if len(w) > 3][:6]
        rel = f"/wp-content/uploads/{TODAY:%Y/%m}/{fam}-{e['year']}-{'-'.join(words)}.pdf"
        os.makedirs(os.path.dirname("public" + rel), exist_ok=True)
        open("public" + rel, "wb").write(pdfs[-1][1])
        e["pdf"] = rel
        note = "PDF guardado y vinculado."
    elif not e.get("pdf"):
        note = "Sin PDF: aparece como «PDF pendiente»."
    e["citation"] = apa(e) if fields or f["kind"] == "nueva" or not e.get("citation") else e["citation"]
    if fields:
        e.pop("citation_en", None)
    e.pop("search", None)
    if f["kind"] == "nueva":
        pos = next((i for i, x in enumerate(entries) if x["year"] <= e["year"]), len(entries))
        entries.insert(pos, e)
    else:
        k = f["key"].split(":")[1]
        i = next((i for i, x in enumerate(entries) if entry_key(x) == k), None)
        if i is None:
            return False, "No he encontrado esta publicación en la lista (¿ya se corrigió?). No he hecho nada."
        entries[i] = e
        entries.sort(key=lambda x: -x["year"])   # por si cambió el año (mantiene el orden dentro de cada año)
    save(PUBS, entries)
    build()
    ign = load(IGN, {}); ign[f["key"]] = TODAY.isoformat(); save(IGN, ign)
    return True, f"Publicado en español e inglés. {note}\nLa web tiene ahora {len(entries)} publicaciones."


# ---------------------------------------------------------------- comandos
def cmd_quincenal():
    subprocess.run([sys.executable, "update_citations.py"])
    build()   # recalcula contadores de citas
    entries, cit = load(PUBS, []), load(CIT, {})
    lines = [f"Citas en Google Scholar: {cit.get('total', '?')} (datos del {cit.get('updated', '?')})",
             f"Publicaciones en la web: {len(entries)}"]
    keys, ign, budget, made = open_keys(), load(IGN, {}), CFG.get("max_fichas_por_revision", 10), []
    dois = {normdoi(e["doi"]).lower() for e in entries if e.get("doi")}
    extra = []
    try:
        works = orcid_works()
    except Exception as ex:
        works = []
        lines.append(f"⚠️ No he podido leer ORCID esta vez ({ex}). Lo reintentaré en la próxima revisión.")
    for w in works:
        if (w["doi"] and w["doi"].lower() in dois) or any(norm(w["title"]) == norm(e["title"]) for e in entries):
            continue
        prensa = next((e for e in entries if (not e.get("doi") or "prensa" in e["journal"].lower()) and similar(e["title"], w["title"]) > .9), None)
        k = f"corr:{entry_key(prensa)}:publicado" if prensa else f"nueva:{(w['doi'] or slug(w['title'])[:60]).lower()}"
        if k in keys or k in ign:
            continue
        if w["year"] and w["year"] < TODAY.year - 1 and not prensa:
            extra.append(w); continue
        if len(made) >= budget:
            break
        m = crossref(w["doi"]) if w["doi"] else None
        e = from_crossref(m) if m else {"year": w["year"] or TODAY.year, "topic": "", "type": "Artículo", "title": w["title"],
                                       "authors": "", "journal": "", "journal_en": "", "doi": w["doi"], "pdf": "", "source": "", "citation": ""}
        if prensa:
            e.update(topic=prensa["topic"], type=prensa["type"], pdf=prensa["pdf"])
            f = new_ficha("correccion", k, "Ya publicado: actualiza la ficha",
                          "Tenías este trabajo <b>en prensa</b> y ya aparece publicado. Te propongo actualizarlo así:", e)
        else:
            f = new_ficha("nueva", k, "Nueva publicación en tu ORCID", "He encontrado esta publicación y aún no está en tu web.", e)
        if f:
            made.append(f)
    if extra and "orcid-antiguas" not in keys and "orcid-antiguas" not in ign:
        lst = "<br>".join(esc(f"· {w['title']} ({w['year']}) {w['doi']}") for w in extra[:60])
        new_ficha("info", "orcid-antiguas", f"{len(extra)} trabajos antiguos de ORCID no están en tu web",
                  "No los he convertido en fichas para no llenarte de avisos. Si quieres alguno, dímelo.<br><br>" + lst, {}, "Trabajos antiguos de ORCID")
    for k, title, why, e in find_errors(entries):
        if len(made) >= budget:
            break
        if k in keys or k in ign:
            continue
        f = new_ficha("correccion", k, f"Corrección: {title}", esc(why).replace("\n", "<br>") + "<br><br>Corrección propuesta:", e)
        if f:
            made.append(f)
    pend = [x for x in load(FICHAS, {"items": {}})["items"].values() if x["status"] == "abierta" and x not in made]
    lines.append(f"Fichas nuevas hoy: {len(made)}")
    if pend:
        lines.append(f"Fichas pendientes de tu respuesta: {len(pend)}")
        lines += [f"· Ficha {x['n']}: {x['title']}" for x in pend[:15]]
    html = ('<div style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;font-size:15px;max-width:640px">'
            '<h2 style="font-size:19px;font-family:Georgia,serif;color:#061a33">Revisión quincenal de tu web</h2>' +
            "".join(f"<p style='margin:4px 0'>{esc(l)}</p>" for l in lines) +
            "<p style='font-size:13px;color:#5c6b7d;margin-top:14px'>Este resumen te llega siempre, haya novedades o no: si un día 1 o 15 no lo recibes, algo falla.</p></div>")
    send(f"[jonandoni-web] Revisión quincenal {TODAY:%d/%m/%Y}", html, "\n".join(lines))

def cmd_prueba():
    e = {"topic": "", "type": "Artículo", "year": 2026,
         "title": "Hearing once, reading twice: How dual subtitles shape visual attention in bilingual viewing",
         "authors": "Romero-Ortells, I.; Perea, M.; Duñabeitia, J.A.", "journal": "Bilingualism · 2026 · DOI: 10.1017/S1366728926100984",
         "journal_en": "Bilingualism · 2026 · DOI: 10.1017/S1366728926100984", "doi": "10.1017/S1366728926100984", "pdf": "", "source": ""}
    new_ficha("prueba", f"prueba:{datetime.datetime.now().isoformat()}", "PRUEBA: así te llegarán las fichas",
              "Esto es una <b>prueba</b>. Pulsa el botón de cualquier etiqueta, adjunta un PDF cualquiera y envía. "
              "En unos 10 minutos te llegará una confirmación. <b>No se cambiará nada en la web.</b>", e)

def cmd_aviso_error():
    run = f"https://github.com/{os.environ.get('GITHUB_REPOSITORY', '')}/actions/runs/{os.environ.get('GITHUB_RUN_ID', '')}"
    send("[jonandoni-web] ⚠️ El sistema ha tenido un error",
         f'<p>Una tarea automática ha fallado. No se ha publicado nada a medias.</p><p><a href="{run}">Ver el detalle</a> (o reenvíame este correo y lo reviso).</p>',
         f"Una tarea automática ha fallado. Detalle: {run}")


if __name__ == "__main__":
    {"prueba": cmd_prueba, "quincenal": cmd_quincenal, "buzon": cmd_buzon, "aviso_error": cmd_aviso_error}[sys.argv[1]]()
