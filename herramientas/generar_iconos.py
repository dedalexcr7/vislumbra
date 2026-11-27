# SPDX-License-Identifier: GPL-3.0-or-later
"""Genera los iconos de la bandeja a partir del logo maestro (``assets/logo.png``).

Uso (desde la raíz del proyecto, con el entorno virtual activo)::

    python herramientas/generar_iconos.py

Recorta solo el glifo (sin la loseta oscura), pasa el fondo a transparente y escribe:

- ``assets/iconos/glifo-<N>.png`` y ``glifo-inactivo-<N>.png`` (16, 24, 32, 48 y 64 px);
- ``assets/vislumbra.ico`` con varios tamaños (para el ``.exe`` de la fase 6).

No redibuja el logo: solo lo recorta y lo reduce. Requiere ``Pillow``.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageFilter

RAIZ = Path(__file__).resolve().parents[1]
LOGO = RAIZ / "assets" / "logo.png"
SALIDA = RAIZ / "assets" / "iconos"
ICO = RAIZ / "assets" / "vislumbra.ico"
TAMANOS = (16, 24, 32, 48, 64)
MAESTRO = 256
UMBRAL_BORDE = 80  # luminosidad a partir de la cual un píxel cuenta como glifo al buscar el recorte
ALFA_DESDE, ALFA_HASTA = 55, 100  # rampa de luminosidad -> opacidad (el fondo oscuro queda transparente)
MARGEN = 0.06  # margen transparente alrededor del glifo, en proporción


def _luminosidad(img: Image.Image) -> Image.Image:
    return img.convert("L")


def recortar_glifo(logo: Image.Image) -> Image.Image:
    """Caja cuadrada alrededor del glifo, buscada por luminosidad (ignora motas aisladas)."""
    luz = _luminosidad(logo).filter(ImageFilter.MedianFilter(7))
    caja = luz.point(lambda v: 255 if v > UMBRAL_BORDE else 0).getbbox()
    if caja is None:
        raise SystemExit("No se encontró el glifo en el logo.")
    izq, arriba, der, abajo = caja
    lado = max(der - izq, abajo - arriba)
    lado = int(lado * (1 + 2 * MARGEN))
    cx, cy = (izq + der) // 2, (arriba + abajo) // 2
    return logo.crop((cx - lado // 2, cy - lado // 2, cx - lado // 2 + lado, cy - lado // 2 + lado))


def a_transparente(recorte: Image.Image) -> Image.Image:
    """El fondo oscuro pasa a transparente; el color de los bordes se toma del glifo vecino."""
    rgb = recorte.convert("RGB")
    ancho = ALFA_HASTA - ALFA_DESDE
    alfa = _luminosidad(rgb).point(lambda v: max(0, min(255, round((v - ALFA_DESDE) * 255 / ancho))))
    # Sin esto, los bordes suavizados quedarían con un halo oscuro sobre fondos claros.
    color = rgb.filter(ImageFilter.MaxFilter(7))
    color.putalpha(alfa)
    return color


def variante_inactiva(img: Image.Image) -> Image.Image:
    gris = img.convert("LA")
    gris = Image.merge("LA", (gris.getchannel("L"), gris.getchannel("A").point(lambda v: round(v * 0.45))))
    return gris.convert("RGBA")


def generar() -> None:
    if not LOGO.exists():
        raise SystemExit(f"Falta el logo maestro: {LOGO}")
    logo = Image.open(LOGO)
    maestro = a_transparente(recortar_glifo(logo)).resize((MAESTRO, MAESTRO), Image.LANCZOS)
    inactivo = variante_inactiva(maestro)
    SALIDA.mkdir(parents=True, exist_ok=True)
    for n in TAMANOS:
        maestro.resize((n, n), Image.LANCZOS).save(SALIDA / f"glifo-{n}.png")
        inactivo.resize((n, n), Image.LANCZOS).save(SALIDA / f"glifo-inactivo-{n}.png")
    maestro.save(ICO, sizes=[(n, n) for n in (*TAMANOS, MAESTRO)])
    print(f"Iconos escritos en {SALIDA.relative_to(RAIZ)} y {ICO.relative_to(RAIZ)}")


if __name__ == "__main__":
    sys.exit(generar())
