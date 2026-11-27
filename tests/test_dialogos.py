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


# --- Diálogo de programas asociados a perfiles ----------------------------------------------------------------------------------
def _estado_de_prueba():
    from vislumbra.color import Ajuste
    from vislumbra.estado import Estado
    from vislumbra.perfiles import Configuracion, Perfil

    c = Configuracion()
    c.guardar(Perfil("Oscuro", Ajuste.uniforme(0.0, 7.5, 1.7)))
    c.guardar(Perfil("Código", Ajuste.uniforme(-20.0, 0.0, 1.0, 6000.0)))

    class M:
        def __init__(self, n):
            self.numero, self.clave, self.principal = n, f"m-{n}", n == 1

    return Estado(c, [M(1), M(2)])


@pytest.fixture
def dialogo_programas(ventana):
    estado = _estado_de_prueba()
    cambios = []
    d = dialogos.DialogoProgramas(ventana, estado, lambda: ["chrome.exe", "juego.exe"], lambda: cambios.append(1))
    yield d, estado, cambios
    d.destroy()


def test_el_dialogo_de_programas_empieza_vacio_con_los_abiertos_y_los_perfiles(dialogo_programas):
    d, estado, _ = dialogo_programas
    assert d.filas() == [] and d.lista.size() == 0
    assert list(d.combo_abiertos.cget("values")) == ["chrome.exe", "juego.exe"]
    assert list(d.combo_perfil.cget("values")) == ["Normal", "Oscuro", "Código"] and d.var_perfil.get() == "Normal"


def test_anadir_un_programa_escribiendo_su_nombre_o_una_ruta(dialogo_programas):
    d, estado, cambios = dialogo_programas
    d.var_exe.set(r"C:\Juegos\Mi Juego\Juego.EXE")
    d.var_perfil.set("Código")
    d._anadir()
    assert d.filas() == ["juego.exe  →  Código"] and d.lista.get(0) == "juego.exe  →  Código"
    assert [(a.exe, a.perfil) for a in estado.programas] == [("juego.exe", "Código")]
    assert d.var_exe.get() == "" and d.lbl_error.cget("text") == "" and cambios == [1]


def test_elegir_un_programa_abierto_rellena_el_campo(dialogo_programas):
    d, *_ = dialogo_programas
    d.var_abiertos.set("juego.exe")
    d.combo_abiertos.event_generate("<<ComboboxSelected>>")
    assert d.var_exe.get() == "juego.exe"


@pytest.mark.parametrize("texto, error", [("", "nombre del programa"), ("juego.bat", ".exe"), ("a|b.exe", "no válidos")])
def test_anadir_con_un_nombre_no_valido_muestra_el_error_y_no_guarda(dialogo_programas, texto, error):
    d, estado, cambios = dialogo_programas
    d.var_exe.set(texto)
    d._anadir()
    assert error in d.lbl_error.cget("text") and estado.programas == [] and cambios == []


def test_quitar_el_seleccionado_y_sin_seleccion(dialogo_programas):
    d, estado, cambios = dialogo_programas
    estado.asociar_programa("a.exe", "Oscuro")
    estado.asociar_programa("b.exe", "Código")
    d._refrescar_lista()
    d._quitar()
    assert "Elige primero" in d.lbl_error.cget("text") and len(estado.programas) == 2 and cambios == []
    d.lista.selection_set(0)
    d._quitar()
    assert [a.exe for a in estado.programas] == ["b.exe"] and d.lista.size() == 1 and cambios == [1]


def test_si_no_se_pueden_listar_los_procesos_el_dialogo_sigue_funcionando(ventana):
    def falla():
        raise OSError("sin lista")

    d = dialogos.DialogoProgramas(ventana, _estado_de_prueba(), falla, lambda: None)
    try:
        assert list(d.combo_abiertos.cget("values")) == []
    finally:
        d.destroy()
