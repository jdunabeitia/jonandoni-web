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
    d = json.load(open(P(p), encoding="utf-8"))
    if p.endswith("publications.json"):   # quita restos de códigos HTML (p. ej. &#x27;)
        for e in d:
            for k, v in e.items():
                if isinstance(v, str):
                    e[k] = html.unescape(v)
    return d

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
          ["Conferencia", "Formación", "Colaboración científica", "Prensa y medios", "Otra"], "— Selecciona la opción —",
          "¡Gracias! He recibido tu mensaje y te responderé lo antes posible.", "No se ha podido enviar. Escríbeme a info@jonandoni.com.", "Enviando…"]
         if es else
         ["Full name", "Email", "Institution", "Reason", "Message", "Send",
          ["Talk", "Training", "Scientific collaboration", "Press and media", "Other"], "— Select the option —",
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


TR = {
    "es": {"for": "Para", "contents": "Contenidos", "ask": "Solicitar conferencia o formación →", "home_k": "Conferencias y formación",
           "home_h": "Conferencias y formación basadas en evidencia para escuelas, organizaciones y familias.",
           "home_p": "Conferencias para congresos y eventos, cursos breves desde 2 horas y formaciones multisesión de varios días, presenciales en Bilbao y Madrid o en línea.",
           "home_cta": "Ver conferencias y formación →", "fmt": [("🎙️", "Conferencias", "Congresos, jornadas y eventos"), ("📍", "Presencial o en línea", "Formación en Bilbao, Madrid o en línea"),
           ("⏱️", "Cursos breves", "Desde 2 horas"), ("📅", "Multisesión", "Formaciones de varios días")], "aud": "Dirigido a"},
    "en": {"for": "For", "contents": "Contents", "ask": "Request a talk or training →", "home_k": "Talks & training",
           "home_h": "Evidence-based talks and training for schools, organisations and families.",
           "home_p": "Talks for conferences and events, short courses from 2 hours and multi-session programmes over several days, in person in Bilbao and Madrid or online.",
           "home_cta": "See talks and training →", "fmt": [("🎙️", "Talks", "Conferences, seminars and events"), ("📍", "In person or online", "Training in Bilbao, Madrid or online"),
           ("⏱️", "Short courses", "From 2 hours"), ("📅", "Multi-session", "Programmes over several days")], "aud": "Aimed at"},
}

def training_formats(lang, F):
    t = TR[lang]
    cards = "".join(f'<div class="jad-tr-fmt"><span>{i}</span><b>{esc(a)}</b><small>{esc(b)}</small></div>' for i, a, b in t["fmt"])
    aud = "".join(f"<span>{esc(x)}</span>" for x in F["audiences"][lang])
    return f'<div class="jad-tr-fmts">{cards}</div><div class="jad-tr-aud"><b>{t["aud"]}:</b> {aud}</div>'

def training_catalog(lang, F):
    t, out = TR[lang], []
    for c in F["courses"]:
        d, cid = c[lang], c["id"] if lang == "es" else c["id_en"]
        mods = "".join(f"<li>{esc(m)}</li>" for m in d["modules"])
        aud = "".join(f"<span>{esc(F['audiences'][lang][i])}</span>" for i in c["audience"])
        out.append(f'''<article class="jad-tr-card" id="{cid}">
<div class="jad-tr-head"><div class="jad-card-icon">{c["icon"]}</div><h3>{esc(d["title"])}</h3></div>
<p>{esc(d["lead"])}</p>
<div class="jad-tr-label">{t["contents"]}</div><ul>{mods}</ul>
<div class="jad-tr-tags"><b>{t["for"]}:</b> {aud}</div>
<a class="jad-tr-ask" href="#solicitud" data-curso="{esc(d["title"])}">{t["ask"]}</a>
</article>''')
    return '<div class="jad-tr-grid">' + "\n".join(out) + """</div>
<script>document.querySelectorAll('.jad-tr-ask').forEach(function(a){a.addEventListener('click',function(){
var s=document.querySelector("#jadForm select[name=formacion]");if(s)s.value=a.dataset.curso;});});</script>"""

def training_home(lang, F):
    t, url = TR[lang], ("/conferencias-formacion/" if lang == "es" else "/en/talks-training/")
    tiles = "".join(f'<a class="jad-tr-tile" href="{url}#{c["id"] if lang == "es" else c["id_en"]}"><span>{c["icon"]}</span>{esc(c[lang]["title"])}</a>' for c in F["courses"])
    aud = "".join(f"<span>{esc(x)}</span>" for x in F["audiences"][lang])
    return f'''<section class="jad-container jad-tr-home">
<div class="jad-tr-home-box">
<div class="jad-tr-home-copy"><div class="jad-small-kicker">{t["home_k"]}</div><h2>{t["home_h"]}</h2><p>{t["home_p"]}</p>
<div class="jad-tr-aud">{aud}</div>
<a class="jad-btn jad-btn-gold" href="{url}">{t["home_cta"]}</a></div>
<div class="jad-tr-tiles">{tiles}</div>
</div></section>'''

def training_form(lang, F):
    es = lang == "es"
    L = dict(n="Nombre completo" if es else "Full name", e="Correo electrónico" if es else "Email",
             o="Organización o centro" if es else "Organisation or school", ty="Tipo de entidad" if es else "Type of organisation",
             f="Tema de interés" if es else "Topic of interest", m="Modalidad" if es else "Mode",
             d="¿Qué necesitas?" if es else "What do you need?", a="Nº aproximado de asistentes" if es else "Approx. number of participants",
             fe="Fechas aproximadas" if es else "Approximate dates", msg="Objetivos y detalles" if es else "Goals and details",
             send="Enviar solicitud" if es else "Send request", sel="— Selecciona —" if es else "— Select —",
             ok="¡Gracias! He recibido tu solicitud y te responderé con una propuesta lo antes posible." if es else "Thank you! I have received your request and will reply with a proposal as soon as possible.",
             err="No se ha podido enviar. Escríbeme a info@jonandoni.com." if es else "It could not be sent. Please write to info@jonandoni.com.",
             wait="Enviando…" if es else "Sending…", ph="Por ejemplo: jornada para 200 docentes, o curso para un claustro de primaria interesado en la detección temprana…" if es else "For example: keynote for 200 teachers, or a course for primary school staff interested in early detection…")
    ent = F["audiences"][lang] + (["Universidad o centro de investigación", "Institución pública", "Fundación", "Organizador de congreso o evento", "Otra"] if es else
                                  ["University or research centre", "Public institution", "Foundation", "Conference or event organiser", "Other"])
    cur = [c[lang]["title"] for c in F["courses"]] + (["Varias / programa a medida"] if es else ["Several / tailor-made programme"])
    mod = ["Presencial en Bilbao", "Presencial en Madrid", "Presencial en otra ciudad", "En línea", "Por definir"] if es else ["In person in Bilbao", "In person in Madrid", "In person elsewhere", "Online", "To be decided"]
    dur = ["Conferencia o charla", "Curso breve (desde 2 horas)", "Formación multisesión (varios días)", "Por definir"] if es else ["Talk or keynote", "Short course (from 2 hours)", "Multi-session programme (several days)", "To be decided"]
    o = lambda xs: "".join(f"<option>{esc(x)}</option>" for x in xs)
    return f"""<form class="jad-form" id="jadForm" novalidate>
<label>{L["n"]} *<input name="nombre" required autocomplete="name"></label>
<label>{L["e"]} *<input name="email" type="email" required autocomplete="email"></label>
<div class="jad-form-row"><label>{L["o"]}<input name="organizacion" autocomplete="organization"></label>
<label>{L["ty"]} *<select name="entidad" required><option value="">{L["sel"]}</option>{o(ent)}</select></label></div>
<label>{L["f"]} *<select name="formacion" required><option value="">{L["sel"]}</option>{o(cur)}</select></label>
<div class="jad-form-row"><label>{L["m"]} *<select name="modalidad" required><option value="">{L["sel"]}</option>{o(mod)}</select></label>
<label>{L["d"]} *<select name="duracion" required><option value="">{L["sel"]}</option>{o(dur)}</select></label></div>
<div class="jad-form-row"><label>{L["a"]}<input name="asistentes" inputmode="numeric"></label>
<label>{L["fe"]}<input name="fechas"></label></div>
<label class="jad-hp" aria-hidden="true">Web<input name="web" tabindex="-1" autocomplete="off"></label>
<label>{L["msg"]} *<textarea name="mensaje" rows="5" required placeholder="{esc(L["ph"])}"></textarea></label>
<input type="hidden" name="motivo" value="{"Conferencia o formación" if es else "Talk or training"}"><input type="hidden" name="idioma" value="{lang}">
<button class="jad-btn jad-btn-gold" type="submit">{L["send"]}</button>
<p class="jad-form-msg" role="status"></p>
</form>
<script>(function(){{var f=document.getElementById('jadForm'),m=f.querySelector('.jad-form-msg'),b=f.querySelector('button');
f.addEventListener('submit',function(e){{e.preventDefault();if(!f.reportValidity())return;b.disabled=true;var old=b.textContent;b.textContent={json.dumps(L["wait"])};
fetch('/api/contacto',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(Object.fromEntries(new FormData(f)))}})
.then(function(r){{if(!r.ok)throw 0;f.reset();m.className='jad-form-msg ok';m.textContent={json.dumps(L["ok"])};}})
.catch(function(){{m.className='jad-form-msg err';m.textContent={json.dumps(L["err"])};}})
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
.jad-form-row{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media (max-width:640px){.jad-form-row{grid-template-columns:1fr}}
/* ===== Formación ===== */
.jad-training-main>section:first-child{margin-top:40px}
.jad-training-main .jad-section-title{margin-bottom:18px}
.jad-tr-fmts{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:0 0 14px}
.jad-tr-fmt{background:#fff;border:1px solid var(--jad-border);border-radius:var(--jad-radius-sm);padding:14px 16px;display:grid;gap:2px;box-shadow:var(--jad-shadow-soft)}
.jad-tr-fmt span{font-size:22px}.jad-tr-fmt b{color:var(--jad-navy);font-size:16px}.jad-tr-fmt small{color:var(--jad-muted);font-size:13px}
.jad-tr-aud{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0 0 26px;color:var(--jad-muted);font-size:14px}
.jad-tr-aud span,.jad-tr-tags span{background:rgba(15,111,168,.08);color:var(--jad-blue);border-radius:999px;padding:5px 11px;font-weight:600;font-size:13px}
.jad-tr-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:18px}
.jad-tr-card{background:#fff;border:1px solid var(--jad-border);border-radius:var(--jad-radius);padding:24px;box-shadow:var(--jad-shadow-soft);display:flex;flex-direction:column;gap:10px;scroll-margin-top:90px}
.jad-tr-card:last-child:nth-child(odd){grid-column:1/-1}
.jad-tr-head{display:flex;align-items:center;gap:12px}.jad-tr-head .jad-card-icon{margin:0}
.jad-tr-card h3{margin:0;font-size:24px;color:var(--jad-navy)}
.jad-tr-card p{margin:0;color:var(--jad-text);line-height:1.55}
.jad-tr-label{font-size:12px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--jad-gold);margin-top:4px}
.jad-tr-card ul{margin:0;padding-left:18px;color:var(--jad-muted);line-height:1.55;font-size:15px}
.jad-tr-tags{display:flex;flex-wrap:wrap;gap:6px;align-items:center;font-size:13px;color:var(--jad-muted);margin-top:auto;padding-top:6px}
.jad-tr-ask{font-weight:700;color:var(--jad-blue)!important;text-decoration:none}
.jad-tr-exp{margin-top:40px;margin-bottom:10px}
.jad-tr-exp-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.jad-tr-exp-card{background:linear-gradient(135deg,var(--jad-navy),#0b3557);color:#fff;border-radius:var(--jad-radius);padding:26px;display:flex;flex-direction:column;gap:12px;box-shadow:var(--jad-shadow)}
.jad-tr-exp-card h3{margin:0;color:#fff;font-size:24px}.jad-tr-exp-card p{margin:0;color:rgba(255,255,255,.85);line-height:1.55}
.jad-tr-exp-card .jad-card-icon{background:var(--jad-gold)}
.jad-tr-exp-card .jad-tr-tags span{background:rgba(255,255,255,.12);color:#fff}
@media (max-width:860px){.jad-tr-exp-grid{grid-template-columns:1fr}}
.jad-training-main>section.jad-tr-exp+section{margin-top:44px}
.jad-tr-home{margin-top:34px;margin-bottom:34px}
.jad-tr-home-box{background:linear-gradient(135deg,var(--jad-navy),#0b3557);color:#fff;border-radius:var(--jad-radius);padding:32px;display:grid;grid-template-columns:1.1fr 1fr;gap:28px;align-items:center;box-shadow:var(--jad-shadow)}
.jad-tr-home-box h2{color:#fff;margin:6px 0 10px;font-size:30px;line-height:1.15}
.jad-tr-home-box p{color:rgba(255,255,255,.82);margin:0 0 14px;line-height:1.55}
.jad-tr-home-box .jad-tr-aud{margin-bottom:18px}.jad-tr-home-box .jad-tr-aud span{background:rgba(255,255,255,.12);color:#fff}
.jad-tr-tiles{display:grid;gap:10px}
.jad-tr-tile{display:flex;align-items:center;gap:12px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.16);border-radius:var(--jad-radius-sm);padding:13px 16px;color:#fff!important;text-decoration:none;font-weight:700;transition:background .2s}
.jad-tr-tile:hover{background:rgba(255,255,255,.16)}.jad-tr-tile span{font-size:20px}
@media (max-width:860px){.jad-tr-fmts{grid-template-columns:repeat(2,1fr)}.jad-tr-grid,.jad-tr-home-box{grid-template-columns:1fr}.jad-tr-home-box{padding:24px}.jad-tr-home-box h2{font-size:24px}}
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
    F = load("src/formaciones.json")
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
                    .replace("<!--TRAINING_FORMATS-->", training_formats(lang, F))
                    .replace("<!--TRAINING_CATALOG-->", training_catalog(lang, F))
                    .replace("<!--TRAINING_HOME-->", training_home(lang, F))
                    .replace("<!--TRAINING_FORM-->", training_form(lang, F))
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
