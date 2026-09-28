// Formulario de contacto: envía el mensaje a tu correo usando tu Gmail.
const nodemailer = require("nodemailer");

const clean = (s, n = 5000) => String(s || "").replace(/\r/g, "").trim().slice(0, n);

module.exports = async (req, res) => {
  if (req.method !== "POST") return res.status(405).json({ ok: false });
  const b = typeof req.body === "string" ? JSON.parse(req.body || "{}") : (req.body || {});
  if (b.web) return res.status(200).json({ ok: true }); // trampa para robots
  const nombre = clean(b.nombre, 200), email = clean(b.email, 200), org = clean(b.organizacion, 200);
  const motivo = clean(b.motivo, 100), mensaje = clean(b.mensaje), idioma = clean(b.idioma, 5);
  if (!nombre || !mensaje || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return res.status(400).json({ ok: false });
  try {
    const t = nodemailer.createTransport({ service: "gmail",
      auth: { user: process.env.GMAIL_USER, pass: (process.env.GMAIL_APP_PASSWORD || "").replace(/\s/g, "") } });
    await t.sendMail({
      from: `Web jonandoni.com <${process.env.GMAIL_USER}>`,
      to: process.env.CONTACT_TO || "info@jonandoni.com",
      replyTo: `${nombre} <${email}>`,
      subject: `[Contacto web] ${motivo || "Mensaje"} · ${nombre}`,
      text: `Nombre: ${nombre}\nCorreo: ${email}\nOrganización: ${org || "-"}\nMotivo: ${motivo || "-"}\nIdioma: ${idioma}\n\n${mensaje}\n\n(Responde a este correo para contestar directamente a ${nombre}.)`,
    });
    res.status(200).json({ ok: true });
  } catch (e) {
    console.error(e);
    res.status(500).json({ ok: false });
  }
};
