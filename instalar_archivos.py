"""Copia (una sola vez) los PDF e imágenes de la copia de tu web a la web nueva."""
import os, re, shutil, glob
SRC = "sitio-actual"
n = 0
for f in glob.glob(f"{SRC}/jonandoni.com/wp-content/uploads/**/*", recursive=True):
    if os.path.isfile(f):
        dst = "public/" + f.split("jonandoni.com/", 1)[1]
        os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy(f, dst); n += 1
for f in glob.glob(f"{SRC}/i0.wp.com/jonandoni.com/wp-content/uploads/**/*", recursive=True):
    if os.path.isfile(f):
        rel = f.split("jonandoni.com/", 1)[1]
        m = re.search(r"\?fit=(\d+),", rel)
        if m:
            os.makedirs("public/assets", exist_ok=True)
            shutil.copy(f, f"public/assets/icon-{m.group(1)}.png"); n += 1
            continue
        dst = "public/" + rel.split("?")[0]
        os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy(f, dst); n += 1
print("Archivos copiados:", n)
