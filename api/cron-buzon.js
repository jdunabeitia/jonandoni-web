// Cada 10 minutos (Vercel Cron) pide a GitHub que lea tus respuestas.
// GitHub, por sí solo, ejecuta sus tareas programadas con horas de retraso; Vercel es puntual.
const nodemailer = require("nodemailer");

module.exports = async (req, res) => {
  const secret = process.env.CRON_SECRET || "";
  const url = new URL(req.url, "https://jonandoni.com");
  const prueba = secret && url.searchParams.get("prueba") === secret;   // para probarlo desde el navegador
  const esCron = /vercel-cron/i.test(req.headers["user-agent"] || "") || req.headers.authorization === `Bearer ${secret}`;
  if (!prueba && !esCron) return res.status(401).json({ ok: false, motivo: "falta la clave" });
  if (!process.env.GH_DISPATCH_TOKEN) {
    console.error("Falta GH_DISPATCH_TOKEN");
    return res.status(500).json({ ok: false, motivo: "Falta la variable GH_DISPATCH_TOKEN en Vercel" });
  }
  const r = await fetch("https://api.github.com/repos/jdunabeitia/jonandoni-web/actions/workflows/sistema.yml/dispatches", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${process.env.GH_DISPATCH_TOKEN}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "jonandoni-web-cron",
    },
    body: JSON.stringify({ ref: "main", inputs: { tarea: "buzon" } }),
  });
  if (r.status === 204) {
    console.log("Buzón lanzado en GitHub");
    return res.status(200).json({ ok: true, mensaje: "GitHub ha recibido la orden: mira la pestaña Actions" });
  }
  const detail = `GitHub respondió ${r.status}: ${(await r.text()).slice(0, 300)}`;
  console.error(detail);
  // Aviso por correo como mucho una vez al día (p. ej. si la llave de GitHub ha caducado)
  const now = new Date();
  if (now.getUTCHours() === 7 && now.getUTCMinutes() < 10 && process.env.GMAIL_USER) {
    try {
      const [u, d] = process.env.GMAIL_USER.split("@");
      await nodemailer.createTransport({ service: "gmail",
        auth: { user: process.env.GMAIL_USER, pass: (process.env.GMAIL_APP_PASSWORD || "").replace(/\s/g, "") } })
        .sendMail({ from: `Web jonandoni.com <${process.env.GMAIL_USER}>`, to: `${u}+jonandoni@${d}`,
          subject: "[jonandoni-web] ⚠️ El buzón automático no funciona",
          text: `No he podido pedir a GitHub que lea tus respuestas.\n${detail}\n\nLo más probable es que la llave GH_DISPATCH_TOKEN haya caducado: crea una nueva y guárdala en Vercel.` });
    } catch (e) { console.error(e); }
  }
  res.status(500).json({ ok: false, detail });
};
