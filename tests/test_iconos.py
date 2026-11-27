# SPDX-License-Identifier: GPL-3.0-or-later
"""Comprobaciones básicas de los iconos generados por ``herramientas/generar_iconos.py``."""

from pathlib import Path

import pytest
from PIL import Image

RAIZ = Path(__file__).resolve().parents[1]
ICONOS = RAIZ / "assets" / "iconos"
TAMANOS = (16, 24, 32, 48, 64)

pytestmark = pytest.mark.skipif(not ICONOS.exists(), reason="los iconos no se han generado")


@pytest.mark.parametrize("n", TAMANOS)
@pytest.mark.parametrize("prefijo", ["glifo", "glifo-inactivo"])
def test_icono_con_fondo_transparente_y_glifo_visible(prefijo, n):
    im = Image.open(ICONOS / f"{prefijo}-{n}.png").convert("RGBA")
    assert im.size == (n, n)
    assert im.getpixel((0, 0))[3] == 0 and im.getpixel((n - 1, n - 1))[3] == 0  # esquinas transparentes
    visibles = sum(1 for a in im.getchannel("A").tobytes() if a > 40)
    assert visibles > n * n * 0.1  # hay glifo, no una imagen vacía


def test_el_icono_inactivo_es_gris_y_menos_opaco():
    activo = Image.open(ICONOS / "glifo-64.png").convert("RGBA")
    inactivo = Image.open(ICONOS / "glifo-inactivo-64.png").convert("RGBA")
    assert max(inactivo.getchannel("A").tobytes()) < max(activo.getchannel("A").tobytes())
    r, g, b, a = (c.tobytes() for c in inactivo.split())
    assert all(abs(x - y) < 3 and abs(y - z) < 3 for x, y, z, op in zip(r, g, b, a) if op)


def test_el_ico_trae_varios_tamanos():
    ico = RAIZ / "assets" / "vislumbra.ico"
    with Image.open(ico) as im:
        assert {16, 32, 48, 64, 256} <= {s[0] for s in im.info["sizes"]}
