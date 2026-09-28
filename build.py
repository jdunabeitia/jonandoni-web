"""
Fabrica la web completa (carpeta public/) a partir de:
  src/pages/...        el contenido de cada página (tu diseño)
  src/site.css         los estilos
  data/publications.json  la lista única de publicaciones
  data/citations.json     las citas de Google Scholar
Uso: python build.py
"""
import hashlib, html, json, os, shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
P = lambda *a: os.path.join(ROOT, *a)
SITE = "https://jonandoni.com"

def load(p):
    return json.load(open(P(p), encoding="utf-8"))

def esc(s):
    return html.escape(str(s or ""), quote=True)

T = {
    "es": {"all": "Todas", "shown": "publicaciones mostradas", "archive": "Todas las publicaciones",
           "pdf": "Descargar PDF", "pdf_no": "PDF pendiente", "src": "Fuente original", "src_no": "DOI no disponible",
           "apa": "Copiar cita APA", "chart": "Citas por año", "total": "total", "upd": "Última actualización",
           "sofar": "en {y} (en curso)"},
    "en": {"all": "All", "shown": "publications shown", "archive": "All publications",
           "pdf": "Download PDF", "pdf_no": "PDF pending", "src": "Original source", "src_no": "DOI unavailable",
           "apa": "Copy APA citation", "chart": "Citations per year", "total": "total", "upd": "Last update",
           "sofar": "in {y} (so far)"},
}


def topic_label(t, lang, i18n):
    return i18n["topics"].get(t, t) if lang == "en" else t

def type_label(t, lang, i18n):
    return i18n["types"].get(t, t) if lang == "en" else t

def search_text(e):
    j = e["journal"].split(" · ")[0]
    return " ".join([e["title"], e["authors"], j, e.get("doi", ""), e["topic"]]).lower()


def card(e, lang, i18n):
    t = T[lang]
    tl, ty = topic_label(e["topic"], lang, i18n), type_label(e["type"], lang, i18n)
    journal = e.get("journal_en") if lang == "en" and e.get("journal_en") else e["journal"]
    cit = e.get("citation_en") if lang == "en" and e.get("citation_en") else e["citation"]
    pdf = (f'<a class="jad-pub-btn jad-pub-btn-primary" href="{esc(e["pdf"])}" rel="noopener" target="_blank">{t["pdf"]}</a>'
           if e.get("pdf") else f'<span class="jad-pub-btn jad-pub-btn-disabled">{t["pdf_no"]}</span>')
    src = (f'<a class="jad-pub-btn" href="{esc(e["source"])}" rel="noopener" target="_blank">{t["src"]}</a>'
           if e.get("source") else f'<span class="jad-pub-btn jad-pub-btn-disabled">{t["src_no"]}</span>')
    return (f'<article class="jad-pub-item" data-pdf="{"yes" if e.get("pdf") else "no"}" data-search="{esc(e.get("search") or search_text(e))}" '
            f'data-topic="{esc(e["topic"])}" data-type="{esc(ty)}" data-year="{e["year"]}">\n'
            f'<div class="jad-pub-meta-top"><span>{e["year"]}</span><span>{esc(tl)}</span><span>{esc(ty)}</span></div>\n'
            f'<h3>{esc(e["title"])}</h3>\n<p class="jad-pub-authors">{esc(e["authors"])}</p>\n'
            f'<p class="jad-pub-journal">{esc(journal)}</p>\n<div class="jad-pub-actions">\n{pdf}\n{src}\n'
            f'<button class="jad-pub-btn jad-copy-citation" data-citation="{esc(cit)}" type="button">{t["apa"]}</button>\n</div>\n</article>')


def filters(pubs, lang, i18n):
    t = T[lang]
    out = [f'<button class="jad-filter-chip is-active" data-filter-topic="all" type="button">{t["all"]} <span>{len(pubs)}</span></button>']
    order = i18n["topics_order"] + sorted({e["topic"] for e in pubs} - set(i18n["topics_order"]))
    for k in order:
        n = sum(1 for e in pubs if e["topic"] == k)
        if n:
            out.append(f'<button class="jad-filter-chip" data-filter-topic="{esc(k)}" type="button">{esc(topic_label(k, lang, i18n))} <span>{n}</span></button>')
    return "".join(out)


def archive(pubs, lang, i18n):
    t = T[lang]
    parts = [f'<div class="jad-pub-archive-head"><h2 class="jad-pub-section-title">{t["archive"]}</h2>'
             f'<span class="jad-pub-counter">{len(pubs)} {t["shown"]}</span></div>']
    for y in sorted({e["year"] for e in pubs}, reverse=True):
        cards = "\n".join(card(e, lang, i18n) for e in pubs if e["year"] == y)
        parts.append(f'<div class="jad-pub-year-group"><h2>{y}</h2><div class="jad-pub-list">\n{cards}\n</div></div>')
    # oculta los años vacíos al filtrar
    parts.append("""<script>
document.addEventListener('input',hideEmpty);document.addEventListener('click',()=>setTimeout(hideEmpty,0));
function hideEmpty(){document.querySelectorAll('.jad-pub-year-group').forEach(g=>{
 g.style.display=[...g.querySelectorAll('.jad-pub-item')].some(i=>i.style.display!=='none')?'':'none';});}
</script>""")
    return "\n".join(parts)


def chart(lang, cites):
    t = T[lang]
    data = json.dumps({k: cites[k] for k in ("updated", "total", "h_index", "years", "citations")})
    return f"""<section class="jad-container jad-cites-section"><div class="jad-cites" id="jadCit" role="img" aria-label="{t['chart']}">
<div class="jad-cites-hd"><h2>{t['chart']}</h2><span><b id="jadTotal"></b> {t['total']} · h-index <b id="jadH"></b></span></div>
<svg id="jadSvg" viewBox="0 0 720 260"></svg>
<div class="jad-cites-ft"><span id="jadUpd"></span><a href="https://scholar.google.com/citations?user=zOf2BvcAAAAJ" target="_blank" rel="noopener">Google Scholar</a></div>
</div></section>
<script>(function(){{
var d={data}, L={json.dumps(lang)}, TXT={json.dumps(t)};
var box=document.getElementById('jadCit'),svg=document.getElementById('jadSvg'),NS='http://www.w3.org/2000/svg';
function el(n,a){{var e=document.createElementNS(NS,n);for(var k in a)e.setAttribute(k,a[k]);return e;}}
var loc=L==='es'?'es-ES':'en-GB';function f(n){{return n.toLocaleString(loc);}}
document.getElementById('jadTotal').textContent=f(d.total);document.getElementById('jadH').textContent=d.h_index;
document.getElementById('jadUpd').textContent=TXT.upd+': '+new Date(d.updated+'T12:00:00').toLocaleDateString(loc,{{day:'numeric',month:'long',year:'numeric'}});
var W=Math.max(300,Math.round(svg.getBoundingClientRect().width||720)),H=W<500?220:260,Lm=8,R=8,T=38,B=28,n=d.years.length,max=Math.max.apply(null,d.citations)*1.08,step=(W-Lm-R)/n,bw=step*.62;
var X=function(i){{return Lm+step*i+step/2}},Y=function(v){{return T+(H-T-B)*(1-v/max)}};
svg.setAttribute('viewBox','0 0 '+W+' '+H);
var defs=el('defs',{{}}),g=el('linearGradient',{{id:'jadGrad',x1:0,y1:0,x2:0,y2:1}});
g.appendChild(el('stop',{{offset:'0','stop-color':'#0f6fa8','stop-opacity':'.35'}}));g.appendChild(el('stop',{{offset:'1','stop-color':'#0f6fa8','stop-opacity':'0'}}));
defs.appendChild(g);svg.appendChild(defs);
for(var k=1;k<=3;k++){{var gy=T+(H-T-B)*k/4;svg.appendChild(el('line',{{x1:Lm,x2:W-R,y1:gy,y2:gy,'class':'grid'}}));}}
var bars=[],pts='',area='M'+X(0)+','+(H-B);
d.citations.forEach(function(v,i){{var r=el('rect',{{'class':'bar',x:X(i)-bw/2,y:Y(v),width:bw,height:(H-B)-Y(v),rx:4}});r.style.transitionDelay=(i*.04)+'s';svg.appendChild(r);bars.push(r);
 pts+=(i?' L':'M')+X(i)+','+Y(v);area+=' L'+X(i)+','+Y(v);
 if(i%(W<500?3:2)===0||i===n-1){{var t=el('text',{{'class':'ax',x:X(i),y:H-8,'text-anchor':'middle'}});t.textContent='\\u2019'+String(d.years[i]).slice(2);svg.appendChild(t);}}}});
area+=' L'+X(n-1)+','+(H-B)+' Z';svg.appendChild(el('path',{{'class':'area',d:area}}));
var line=el('path',{{'class':'line',d:pts}});svg.appendChild(line);var len=line.getTotalLength();line.style.transition='none';line.style.strokeDasharray=len;line.style.strokeDashoffset=len;line.getBoundingClientRect();line.style.transition='';
d.citations.forEach(function(v,i){{var c=el('circle',{{'class':'pt'+(i===n-1?' last':''),cx:X(i),cy:Y(v),r:i===n-1?5:3.5}});c.style.transitionDelay=(.3+i*.07)+'s';svg.appendChild(c);}});
var lv=d.citations[n-1],lx=X(n-1),ly=Y(lv),label=f(lv)+' '+TXT.sofar.replace('{{y}}',d.years[n-1]);
var below=n>1&&Y(d.citations[n-2])<ly,ty=below?ly+12:ly-36,tag=el('g',{{'class':'tag'}}),tw=label.length*7.2+18;
tag.appendChild(el('rect',{{x:lx-tw+10,y:ty,width:tw,height:24,rx:7}}));var tt=el('text',{{x:lx-tw/2+10,y:ty+16.5,'text-anchor':'middle'}});tt.textContent=label;tag.appendChild(tt);svg.appendChild(tag);
function toBars(){{box.classList.remove('s2');box.classList.add('s1');line.style.strokeDashoffset=len;bars.forEach(function(b,i){{b.setAttribute('x',X(i)-bw/2);b.setAttribute('width',bw);}});}}
function toLine(){{box.classList.add('s2');line.style.strokeDashoffset=0;bars.forEach(function(b,i){{b.setAttribute('x',X(i)-1.5);b.setAttribute('width',3);}});}}
var timer=null,vis=false,ph=0;function loop(){{if(!vis){{timer=null;return;}}ph=1-ph;ph?toLine():toBars();timer=setTimeout(loop,ph?4200:3000);}}
if(matchMedia('(prefers-reduced-motion: reduce)').matches){{box.classList.add('s1');toLine();return;}}
new IntersectionObserver(function(e){{vis=e[0].isIntersecting;if(vis&&!timer){{requestAnimationFrame(function(){{box.classList.add('s1');}});timer=setTimeout(loop,2500);}}}},{{threshold:.3}}).observe(box);
}})();</script>"""


def contact_form(lang):
    es = lang == "es"
    L = (["Nombre completo", "Correo electrónico", "Organización", "Motivo", "Mensaje", "Enviar",
          ["Conferencia o curso", "Colaboración científica", "Prensa y medios", "Otra"], "— Selecciona la opción —",
          "¡Gracias! He recibido tu mensaje y te responderé lo antes posible.", "No se ha podido enviar. Escríbeme a info@jonandoni.com.", "Enviando…"]
         if es else
         ["Full name", "Email", "Institution", "Reason", "Message", "Send",
          ["Conference or course", "Scientific collaboration", "Press and media", "Other"], "— Select the option —",
          "Thank you! I have received your message and will reply as soon as possible.", "It could not be sent. Please write to info@jonandoni.com.", "Sending…"])
    opts = "".join(f"<option>{esc(o)}</option>" for o in L[6])
    return f"""<form class="jad-form" id="jadForm" novalidate>
<label>{L[0]} *<input name="nombre" required autocomplete="name"></label>
<label>{L[1]} *<input name="email" type="email" required autocomplete="email"></label>
<label>{L[2]}<input name="organizacion" autocomplete="organization"></label>
<label class="jad-hp" aria-hidden="true">Web<input name="web" tabindex="-1" autocomplete="off"></label>
<label>{L[3]} *<select name="motivo" required><option value="">{L[7]}</option>{opts}</select></label>
<label>{L[4]} *<textarea name="mensaje" rows="6" required></textarea></label>
<input type="hidden" name="idioma" value="{lang}">
<button class="jad-btn jad-btn-blue" type="submit">{L[5]}</button>
<p class="jad-form-msg" role="status"></p>
</form>
<script>(function(){{var f=document.getElementById('jadForm'),m=f.querySelector('.jad-form-msg'),b=f.querySelector('button');
f.addEventListener('submit',function(e){{e.preventDefault();if(!f.reportValidity())return;b.disabled=true;var old=b.textContent;b.textContent={json.dumps(L[10])};
fetch('/api/contacto',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(Object.fromEntries(new FormData(f)))}})
.then(function(r){{if(!r.ok)throw 0;f.reset();m.className='jad-form-msg ok';m.textContent={json.dumps(L[8])};}})
.catch(function(){{m.className='jad-form-msg err';m.textContent={json.dumps(L[9])};}})
.finally(function(){{b.disabled=false;b.textContent=old;}});}});}})();</script>"""


EXTRA_CSS = """
/* ===== Añadidos en la versión Vercel ===== */
body.page{margin:0;background:var(--jad-soft)}
.jad-cites-section{margin-top:28px;margin-bottom:8px}
.jad-cites{background:#fff;border:1px solid var(--jad-border);border-radius:var(--jad-radius);box-shadow:var(--jad-shadow-soft);padding:22px 24px 14px}
.jad-cites-hd{display:flex;justify-content:space-between;align-items:baseline;gap:6px 16px;flex-wrap:wrap}
.jad-cites-hd h2{margin:0;font-size:24px;color:var(--jad-navy)}
.jad-cites-hd span{color:var(--jad-muted);font-size:14px}.jad-cites-hd b{color:var(--jad-navy);font-size:16px}
.jad-cites svg{display:block;width:100%;height:auto;overflow:visible;margin-top:6px}
.jad-cites .grid{stroke:var(--jad-border);stroke-width:1}
.jad-cites .bar{fill:var(--jad-blue);transform-box:fill-box;transform-origin:50% 100%;transform:scaleY(0);transition:transform .7s cubic-bezier(.2,.8,.2,1),opacity .6s,width .6s,x .6s}
.jad-cites.s1 .bar{transform:scaleY(1)}.jad-cites.s2 .bar{opacity:.22}
.jad-cites .area{fill:url(#jadGrad);opacity:0;transition:opacity .4s}.jad-cites.s2 .area{opacity:1;transition:opacity .8s .5s}
.jad-cites .line{fill:none;stroke:var(--jad-navy);stroke-width:2.6;stroke-linecap:round;stroke-linejoin:round;transition:stroke-dashoffset 1.4s ease-in-out}
.jad-cites .pt{fill:#fff;stroke:var(--jad-navy);stroke-width:2;opacity:0;transition:opacity .3s}.jad-cites.s2 .pt{opacity:1}
.jad-cites .pt.last{fill:var(--jad-gold);stroke:#fff}
.jad-cites .tag{opacity:0;transform:translateY(6px);transition:opacity .25s,transform .25s}
.jad-cites.s2 .tag{opacity:1;transform:none;transition:opacity .4s 1.4s,transform .4s 1.4s}
.jad-cites .tag rect{fill:var(--jad-navy)}.jad-cites .tag text{fill:#fff;font-weight:600;font-size:13px;font-family:Inter,system-ui,sans-serif}
.jad-cites .ax{fill:var(--jad-muted);font-size:11px;font-family:Inter,system-ui,sans-serif}
.jad-cites-ft{display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;font-size:13px;color:var(--jad-muted);padding-top:10px}
.jad-cites-ft a{color:var(--jad-blue)!important}
@media (prefers-reduced-motion:reduce){.jad-cites *{transition:none!important}}
.jad-form{display:grid;gap:14px}
.jad-form label{display:grid;gap:6px;font-weight:600;font-size:15px;color:var(--jad-text)}
.jad-form input,.jad-form select,.jad-form textarea{font:inherit;font-weight:400;padding:11px 14px;border:1px solid var(--jad-border);border-radius:var(--jad-radius-sm);background:#fff;color:var(--jad-text);width:100%}
.jad-form input:focus,.jad-form select:focus,.jad-form textarea:focus{outline:2px solid var(--jad-blue);outline-offset:1px}
.jad-form button{justify-self:start;border:0;cursor:pointer}
.jad-form button[disabled]{opacity:.6;cursor:wait}
.jad-hp{position:absolute!important;left:-9999px!important;height:1px;overflow:hidden}
.jad-form-msg{margin:0;font-weight:600}.jad-form-msg.ok{color:#137333}.jad-form-msg.err{color:#b3261e}
"""


def head(path, meta, css_v):
    alt = meta.get("alternate")
    canon = f"{SITE}/{path.replace('index.html', '')}"
    links = f'<link rel="canonical" href="{canon}">'
    if alt:
        es_p, en_p = (path, alt) if meta["lang"] == "es" else (alt, path)
        links += (f'<link rel="alternate" hreflang="es" href="{SITE}/{es_p.replace("index.html", "")}">'
                  f'<link rel="alternate" hreflang="en" href="{SITE}/{en_p.replace("index.html", "")}">')
    img = f"{SITE}/wp-content/uploads/2026/05/jon_andoni_banner.png"
    return f"""<!DOCTYPE html>
<html lang="{meta['lang']}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(meta['title'])}</title>
<meta name="description" content="{esc(meta['description'])}">
{links}
<meta property="og:type" content="website"><meta property="og:title" content="{esc(meta['title'])}">
<meta property="og:description" content="{esc(meta['description'])}"><meta property="og:image" content="{img}">
<meta property="og:url" content="{canon}"><meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/assets/icon-32.png" sizes="32x32"><link rel="icon" href="/assets/icon-192.png" sizes="192x192">
<link rel="apple-touch-icon" href="/assets/icon-180.png">
<link rel="stylesheet" href="/assets/site.css?v={css_v}">
</head>
<body class="page">
"""


def main():
    pubs, i18n, pages = load("data/publications.json"), load("data/i18n.json"), load("src/pages.json")
    cites = load("data/citations.json")
    os.makedirs(P("public/assets"), exist_ok=True)
    os.makedirs(P("public/data"), exist_ok=True)
    css = open(P("src/site.css"), encoding="utf-8").read() + EXTRA_CSS
    open(P("public/assets/site.css"), "w", encoding="utf-8").write(css)
    shutil.copy(P("data/citations.json"), P("public/data/citations.json"))
    v = hashlib.md5(css.encode()).hexdigest()[:8]
    c100 = cites["total"] // 100 * 100
    for path, meta in pages.items():
        lang = meta["lang"]
        body = open(P("src/pages", path), encoding="utf-8").read()
        body = (body.replace("<!--PUBS_FILTERS-->", filters(pubs, lang, i18n))
                    .replace("<!--PUBS_ARCHIVE-->", archive(pubs, lang, i18n))
                    .replace("<!--CITES_CHART-->", chart(lang, cites))
                    .replace("<!--CONTACT_FORM-->", contact_form(lang))
                    .replace("{{PUBS_TOTAL}}", str(len(pubs)))
                    .replace("{{CITES}}", f"{c100:,}".replace(",", "." if lang == "es" else ",")))
        out = P("public", path)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, "w", encoding="utf-8").write(head(path, meta, v) + body + "\n</body>\n</html>\n")
    # mapa del sitio
    urls = "".join(f"<url><loc>{SITE}/{p.replace('index.html', '')}</loc></url>" for p in pages)
    open(P("public/sitemap.xml"), "w").write(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>')
    open(P("public/robots.txt"), "w").write(f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n")
    print(f"Web fabricada: {len(pages)} páginas, {len(pubs)} publicaciones, {cites['total']} citas.")


if __name__ == "__main__":
    main()
