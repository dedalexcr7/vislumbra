# SPDX-License-Identifier: GPL-3.0-or-later
"""Pruebas de ``vislumbra.dialogos``: se crean ocultos y se «pulsan» por código (no bloquean ni tocan la pantalla)."""

import pytest

from vislumbra import dialogos
from vislumbra.dialogos import ACEPTAR, Dialogo


@pytest.fixture
def raiz(ventana):
    return ventana


def con_texto(raiz, inicial="Perfil 2"):
    return Dialogo(raiz, "Guardar como", "Nombre:", [("Aceptar", ACEPTAR, "activo"), ("Cancelar", None, "normal")], campo=inicial)


def test_aceptar_devuelve_el_texto_escrito(raiz):
    d = con_texto(raiz)
    d._var.set("Noche")
    d.botones[0].invocar()
    assert d.resultado == "Noche" and not d.winfo_exists()


def test_cancelar_escape_y_la_x_devuelven_el_valor_de_cancelar(raiz):
    for cerrar in (lambda d: d.botones[1].invocar(), lambda d: d.event_generate("<Escape>"), lambda d: d._cerrar(d._cancelar)):
        d = con_texto(raiz)
        d.deiconify() if False else None
        d.update()
        cerrar(d)
        raiz.update()
        assert d.resultado is None


def test_confirmar_y_guardar_tienen_tres_o_dos_botones(raiz):
    d = Dialogo(raiz, "Borrar", "¿Seguro?", [("Sí", True, "activo"), ("No", False, "normal")], cancelar=False)
    assert [b.cget("text") for b in d.botones] == ["Sí", "No"]
    d.botones[0].invocar()
    assert d.resultado is True
    d = Dialogo(raiz, "Borrar", "¿Seguro?", [("Sí", True, "activo"), ("No", False, "normal")], cancelar=False)
    d._cerrar(d._cancelar)
    assert d.resultado is False
    g = Dialogo(
        raiz, "Cambios", "x", [("Guardar", True, "activo"), ("Descartar", False, "normal"), ("Cancelar", None, "normal")], cancelar=None,
    )
    assert [b.cget("text") for b in g.botones] == ["Guardar", "Descartar", "Cancelar"]
    g.botones[1].invocar()
    assert g.resultado is False


def test_el_panel_usa_los_dialogos_oscuros_por_defecto():
    from vislumbra import panel

    assert panel.dialogos is dialogos
