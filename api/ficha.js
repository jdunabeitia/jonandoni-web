// Botones de las fichas: página para confirmar y orden a GitHub para ejecutarla.
const crypto = require("crypto");

const esc = (s) => String(s || "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const token = (n) => crypto.createHmac("sha256", process.env.FICHA_SECRET || "").update(String(n)).digest("hex").slice(0, 8);

function page(res, status, title, body) {
  res.status(status).setHeader("Content-Type", "text/html; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");
  res.end(`<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>${esc(title)}</title><style>
body{margin:0;font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;background:#f4f7fb;color:#142033}
.c{max-width:520px;margin:12vh auto;padding:28px;background:#fff;border-radius:18px;box-shadow:0 10px 30px rgba(6,26,51,.08)}
h1{font-family:Georgia,serif;font-size:24px;color:#061a33;margin:0 0 12px}p{line-height:1.5}
button{font:inherit;font-weight:700;border:0;border-radius:10px;padding:14px 22px;color:#fff;cursor:pointer;width:100%;margin-top:8px}
.ok{background:#1a7f37}.no{background:#b3261e}.s{color:#5c6b7d;font-size:14px}</style></head><body><div class="c">${body}</div></body></html>`);
}

module.exports = async (req, res) => {
  const q = req.method === "POST"
    ? (typeof req.body === "string" ? Object.fromEntries(new URLSearchParams(req.body)) : req.body || {})
    : Object.fromEntries(new URL(req.url, "https://jonandoni.com").searchParams);
  const n = String(q.n || ""), c = String(q.c || ""), a = String(q.a || ""), e = String(q.e || ""), t = String(q.t || "").slice(0, 120);
  if (!/^\d+$/.test(n) || !["publicar", "ignorar"].includes(a) || c.length !== 8 ||
      !crypto.timingSafeEqual(Buffer.from(c), Buffer.from(token(n)))) {
    return page(res, 400, "Enlace no válido", "<h1>Enlace no válido</h1><p>Este botón no es correcto o ha caducado. Responde al correo de la ficha escribiendo <b>publicar</b> o <b>ignorar</b>.</p>");
  }
  const que = a === "publicar" ? `Publicar${e ? ` con la etiqueta <b>${esc(e)}</b>` : ""}` : "Ignorar esta ficha";

  // GET: solo muestra la confirmación (así los antivirus que abren enlaces no publican nada por error)
  if (req.method !== "POST") {
    return page(res, 200, "Confirmar", `<h1>Ficha ${esc(n)}</h1><p>${esc(t)}</p><p>${que}</p>
<form method="post"><input type="hidden" name="n" value="${esc(n)}"><input type="hidden" name="c" value="${esc(c)}">
<input type="hidden" name="a" value="${esc(a)}"><input type="hidden" name="e" value="${esc(e)}"><input type="hidden" name="t" value="${esc(t)}">
<button class="${a === "publicar" ? "ok" : "no"}" type="submit">${a === "publicar" ? "✅ Confirmar y publicar" : "Confirmar: ignorar"}</button></form>
<p class="s">Si necesitas añadir el PDF o corregir datos, no pulses: responde al correo de la ficha.</p>`);
  }

  const r = await fetch("https://api.github.com/repos/jdunabeitia/jonandoni-web/actions/workflows/sistema.yml/dispatches", {
    method: "POST",
    headers: { Authorization: `Bearer ${process.env.GH_DISPATCH_TOKEN}`, Accept: "application/vnd.github+json", "User-Agent": "jonandoni-web" },
    body: JSON.stringify({ ref: "main", inputs: { tarea: "accion", ficha: n, accion: a, etiqueta: e, codigo: c } }),
  });
  if (r.status === 204) {
    return page(res, 200, "Recibido", `<h1>✅ Recibido</h1><p>${que}.</p><p>En 1-2 minutos te llegará la confirmación por correo${a === "publicar" ? " y la web estará actualizada" : ""}.</p><p class="s">Ya puedes cerrar esta página.</p>`);
  }
  const detail = `${r.status} ${(await r.text()).slice(0, 200)}`;
  console.error("GitHub:", detail);
  return page(res, 500, "Error", `<h1>⚠️ No se ha podido enviar</h1><p>No he podido avisar a GitHub (${esc(detail)}). No se ha publicado nada.</p><p>Mientras lo arreglamos, responde al correo de la ficha escribiendo <b>${a}</b>.</p>`);
};
