# jonandoni.com en Vercel

La web se fabrica sola a partir de la lista `data/publications.json`.
Cada vez que cambia algo, Vercel la publica en 1-2 minutos.

## Qué hace sola
- **Días 1 y 15**: actualiza las citas de Scholar, busca novedades en ORCID, revisa errores y te manda un **resumen** (siempre, aunque no haya novedades).
- **Cada novedad o error** te llega por correo como **ficha con botones**. Pulsas uno, adjuntas el PDF si lo tienes y envías.
- **Cada 10 minutos** lee tus respuestas, publica y te confirma por correo.
- Si algo falla, te avisa por correo.

## Carpetas (por si curioseas)
- `data/publications.json`: tus publicaciones (la lista única).
- `src/pages/`: el contenido de cada página. `src/site.css`: el diseño.
- `public/`: la web ya fabricada (no se toca a mano).
- `api/contacto.js`: el formulario de contacto.
