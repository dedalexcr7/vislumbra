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
    assert d.filas() == ["juego.exe  →  Código  ·  monitor donde esté"] and d.lista.get(0) == d.filas()[0]
    assert [(a.exe, a.perfil) for a in estado.programas] == [("juego.exe", "Código")]
    assert d.var_exe.get() == "" and d.lbl_error.cget("text") == "" and cambios == [1]


def test_elegir_un_programa_abierto_rellena_el_campo(dialogo_programas):
    d, *_ = dialogo_programas
    d.combo_abiertos.elegir("juego.exe")  # lo que hace pulsar un valor de la lista
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


# --- Alcance y edición en su sitio ------------------------------------------------------------------------------------------------
def test_el_alcance_por_defecto_es_el_monitor_donde_este_el_programa_y_se_guarda_asi(dialogo_programas):
    d, estado, _ = dialogo_programas
    assert d.var_alcance.get() == dialogos.ETIQUETA_VENTANA and str(d.combo_monitor.cget("state")) == "disabled"
    d.var_exe.set("juego.exe")
    d.var_perfil.set("Oscuro")
    d._anadir()
    assert [(a.exe, a.alcance) for a in estado.programas] == [("juego.exe", "ventana")]


def test_elegir_un_monitor_concreto_activa_su_selector_y_guarda_su_clave(dialogo_programas):
    d, estado, _ = dialogo_programas
    assert list(d.combo_monitor.cget("values")) == ["Monitor 1 · principal", "Monitor 2"]
    d.var_alcance.set(dialogos.ETIQUETA_MONITOR)
    d._alcance_cambiado()
    assert str(d.combo_monitor.cget("state")) == "readonly"
    d.var_monitor.set("Monitor 2")
    d.var_exe.set("juego.exe")
    d.var_perfil.set("Código")
    d._anadir()
    assert estado.programas[0].alcance == "monitor:m-2"
    assert d.filas() == ["juego.exe  →  Código  ·  Monitor 2"]


def test_el_alcance_perfil_activo(dialogo_programas):
    d, estado, _ = dialogo_programas
    d.var_alcance.set(dialogos.ETIQUETA_ACTIVO)
    d.var_exe.set("juego.exe")
    d._anadir()
    assert estado.programas[0].alcance == "activo" and d.filas()[0].endswith("perfil activo")


def test_elegir_una_fila_carga_el_formulario_y_guardar_cambios_la_modifica_sin_borrarla(dialogo_programas):
    d, estado, cambios = dialogo_programas
    estado.asociar_programa("a.exe", "Oscuro", "ventana")
    estado.asociar_programa("b.exe", "Código", "monitor:m-2")
    d._refrescar_lista()
    assert str(d.btn_guardar.cget("state")) == "disabled"  # nada elegido todavía
    d.lista.selection_set(1)
    d._cargar_seleccion()
    assert d.var_exe.get() == "b.exe" and d.var_perfil.get() == "Código"
    assert d.var_alcance.get() == dialogos.ETIQUETA_MONITOR and d.var_monitor.get() == "Monitor 2"
    assert "Cambiar" in d.lbl_forma.cget("text")
    d.var_perfil.set("Oscuro")
    d.var_alcance.set(dialogos.ETIQUETA_ACTIVO)
    d.var_exe.set("B2.exe")  # también se puede cambiar el nombre
    d._guardar_cambios()
    assert [(a.exe, a.perfil, a.alcance) for a in estado.programas] == [("a.exe", "Oscuro", "ventana"), ("b2.exe", "Oscuro", "activo")]
    assert d.lista.size() == 2 and d.var_exe.get() == "" and d.lbl_forma.cget("text") == "Añadir un programa" and cambios == [1]


def test_guardar_cambios_sin_elegir_nada_o_con_un_nombre_repetido_da_error(dialogo_programas):
    d, estado, cambios = dialogo_programas
    d._guardar_cambios()
    assert "Elige primero" in d.lbl_error.cget("text") and cambios == []
    estado.asociar_programa("a.exe", "Oscuro")
    estado.asociar_programa("b.exe", "Oscuro")
    d._refrescar_lista()
    d.lista.selection_set(1)
    d._cargar_seleccion()
    d.var_exe.set("a.exe")
    d._guardar_cambios()
    assert "ya está" in d.lbl_error.cget("text") and [a.exe for a in estado.programas] == ["a.exe", "b.exe"] and cambios == []


def test_un_programa_cuyo_monitor_ya_no_esta_conectado_se_muestra_asi(dialogo_programas):
    d, estado, _ = dialogo_programas
    estado.asociar_programa("a.exe", "Oscuro", "monitor:otro-que-no-esta")
    assert d.filas() == ["a.exe  →  Oscuro  ·  monitor no conectado"]


def test_la_pestana_de_un_monitor_con_programa_muestra_su_nombre():
    from vislumbra.estado import Estado

    est = _estado_de_prueba()
    est.asociar_programa("juego.exe", "Código", "monitor:m-2")
    est.aplicar_programas(["juego.exe"], {})
    assert [(p.numero, p.perfil, p.programa) for p in est.pestanas()] == [(1, "Normal", None), (2, "Código", "juego.exe")]


# --- Diálogo de atajos --------------------------------------------------------------------------------------------------------
from types import SimpleNamespace as _Ev  # noqa: E402

from vislumbra import atajos as _atajos  # noqa: E402
from vislumbra.teclado import Resultado  # noqa: E402


class GestorDeDialogo:
    """Gestor de atajos simulado: cuenta pausas y reanudaciones y decide qué combinaciones están «en uso»."""

    def __init__(self, ocupadas=()):
        self.pausas = self.reanudaciones = 0
        self.ocupadas = set(ocupadas)
        self.probadas = []

    def pausar(self, espera=2.0):
        self.pausas += 1

    def reanudar(self, espera=2.0):
        self.reanudaciones += 1
        return {}

    def probar(self, comb, espera=2.0):
        self.probadas.append(comb.texto())
        return Resultado(False, 1409) if comb.texto() in self.ocupadas else Resultado(True)


@pytest.fixture
def dialogo_atajos(ventana):
    estado = _estado_de_prueba()
    gestor, cambios = GestorDeDialogo(), []
    d = dialogos.DialogoAtajos(ventana, estado, gestor, lambda: cambios.append(1), lambda: {})
    d.confirmar = lambda t, m: True
    mods = []
    d.leer_modificadores = lambda: frozenset(mods)

    def pulsar(vk, *modificadores, keysym=""):
        mods[:] = modificadores
        return d._tecla(_Ev(keycode=vk, keysym=keysym))

    d.pulsar = pulsar
    yield d, estado, gestor, cambios
    d.destroy()


def test_el_dialogo_muestra_las_acciones_y_los_perfiles_con_sus_combinaciones(dialogo_atajos):
    d, estado, _, _ = dialogo_atajos
    assert [k for k in d.filas_ui if k[0] == "accion"] == [("accion", a) for a in _atajos.ACCIONES]
    assert [k[1] for k in d.filas_ui if k[0] == "perfil"] == ["Normal", "Oscuro", "Código"]
    assert d.filas_ui[("accion", "siguiente")]["comb"].cget("text") == "Ctrl+Alt+P"
    assert d.filas_ui[("accion", "anterior")]["comb"].cget("text") == "Ctrl+Alt+Mayús+P"
    assert d.filas_ui[("accion", "preciso")]["comb"].cget("text") == "sin atajo"
    assert d.filas_ui[("perfil", "Código")]["comb"].cget("text") == "sin atajo"
    assert d.filas_ui[("accion", "emergencia")]["quitar"] is None  # la emergencia no se puede quitar
    assert d.var_aviso.get() == "Ninguno"


def test_grabar_una_combinacion_pausa_los_atajos_asigna_y_los_reanuda(dialogo_atajos):
    d, estado, gestor, cambios = dialogo_atajos
    clave = ("accion", "preciso")
    d.grabar(clave)
    assert gestor.pausas == 1 and gestor.reanudaciones == 0
    assert "Pulsa la combinación" in d.filas_ui[clave]["estado"].cget("text")
    assert d.pulsar(0x4D, "Ctrl", "Alt") == "break"  # Ctrl+Alt+M
    assert estado.atajos.acciones["preciso"].texto() == "Ctrl+Alt+M" and d.filas_ui[clave]["comb"].cget("text") == "Ctrl+Alt+M"
    assert gestor.reanudaciones == 1 and gestor.probadas == ["Ctrl+Alt+M"] and cambios == [1]
    assert d.filas_ui[clave]["estado"].cget("text") == "" and d._grabando is None


def test_grabar_un_atajo_de_perfil_incluido_normal(dialogo_atajos):
    d, estado, _, _ = dialogo_atajos
    d.grabar(("perfil", "Normal"))
    d.pulsar(0x31, "Ctrl", "Alt")
    assert estado.atajos.perfiles["Normal"].texto() == "Ctrl+Alt+1"
    d.grabar(("perfil", "Código"))
    d.pulsar(0x70 + 2, "Ctrl", "Alt", "Shift")  # F3
    assert estado.atajos.perfiles["Código"].texto() == "Ctrl+Alt+Shift+F3"


def test_los_modificadores_solos_no_terminan_la_grabacion(dialogo_atajos):
    d, estado, gestor, cambios = dialogo_atajos
    d.grabar(("accion", "preciso"))
    for vk in (0x11, 0x12, 0x10, 0x5B, 0xA2, 0xA4):  # Ctrl, Alt, Mayús, Win…
        assert d.pulsar(vk, "Ctrl") == "break"
    assert d._grabando == ("accion", "preciso") and gestor.reanudaciones == 0 and cambios == []


def test_una_tecla_no_admitida_se_avisa_y_se_sigue_grabando(dialogo_atajos):
    d, estado, gestor, _ = dialogo_atajos
    clave = ("accion", "preciso")
    d.grabar(clave)
    d.pulsar(0x6B, "Ctrl", "Alt")  # «+» del teclado numérico
    assert "no se admite" in d.filas_ui[clave]["estado"].cget("text") and d._grabando == clave
    d.pulsar(0x4D, "Ctrl", "Alt")
    assert estado.atajos.acciones["preciso"].texto() == "Ctrl+Alt+M"


def test_un_atajo_repetido_se_rechaza_con_el_nombre_de_quien_lo_usa_y_se_reanuda(dialogo_atajos):
    d, estado, gestor, cambios = dialogo_atajos
    clave = ("accion", "preciso")
    d.grabar(clave)
    d.pulsar(0x50, "Ctrl", "Alt")  # Ctrl+Alt+P: ya es «Siguiente perfil»
    assert "ya la usa «Siguiente perfil»" in d.filas_ui[clave]["estado"].cget("text")
    assert estado.atajos.acciones["preciso"] is None and gestor.reanudaciones == 1 and cambios == [] and gestor.probadas == []


def test_una_combinacion_ocupada_por_otra_aplicacion_se_rechaza(ventana):
    estado, gestor, cambios = _estado_de_prueba(), GestorDeDialogo(ocupadas={"Ctrl+Alt+L"}), []
    d = dialogos.DialogoAtajos(ventana, estado, gestor, lambda: cambios.append(1), lambda: {})
    d.leer_modificadores = lambda: frozenset({"Ctrl", "Alt"})
    try:
        d.grabar(("accion", "preciso"))
        d._tecla(_Ev(keycode=0x4C, keysym="l"))
        assert "En uso por otra aplicación" in d.filas_ui[("accion", "preciso")]["estado"].cget("text")
        assert estado.atajos.acciones["preciso"] is None and gestor.reanudaciones == 1 and cambios == []
    finally:
        d.destroy()


def test_una_combinacion_no_valida_se_rechaza(dialogo_atajos):
    d, estado, gestor, _ = dialogo_atajos
    d.grabar(("accion", "preciso"))
    d.pulsar(0x4D, "Shift")  # Mayús sola
    assert "Mayús sola" in d.filas_ui[("accion", "preciso")]["estado"].cget("text") and estado.atajos.acciones["preciso"] is None
    d.grabar(("accion", "preciso"))
    d.pulsar(0x4D)  # sin modificador
    assert "Ctrl, Alt o Win" in d.filas_ui[("accion", "preciso")]["estado"].cget("text") and gestor.reanudaciones == 2


def test_se_puede_grabar_f13_a_f24_sin_modificador(dialogo_atajos):
    d, estado, _, _ = dialogo_atajos
    d.grabar(("accion", "preciso"))
    d.pulsar(0x7C)  # F13
    assert estado.atajos.acciones["preciso"].texto() == "F13"


def test_escape_cancela_la_grabacion_sin_cerrar_el_dialogo_y_reanuda(dialogo_atajos):
    d, estado, gestor, cambios = dialogo_atajos
    d.grabar(("accion", "preciso"))
    assert d._escape() == "break" and d._grabando is None
    assert gestor.reanudaciones == 1 and cambios == [] and d.winfo_exists() and d.resultado is None
    assert d.filas_ui[("accion", "preciso")]["estado"].cget("text") == ""


def test_empezar_otra_grabacion_cancela_la_anterior_y_cerrar_reanuda(dialogo_atajos):
    d, _, gestor, _ = dialogo_atajos
    d.grabar(("accion", "preciso"))
    d.grabar(("accion", "comparar"))
    assert d._grabando == ("accion", "comparar") and gestor.pausas == 2 and gestor.reanudaciones == 1
    d._cerrar(None)  # se cierra grabando: los atajos se reanudan
    assert gestor.reanudaciones == 2


def test_sin_gestor_de_atajos_grabar_tambien_funciona(ventana):
    estado, cambios = _estado_de_prueba(), []
    d = dialogos.DialogoAtajos(ventana, estado, None, lambda: cambios.append(1), lambda: {})
    d.leer_modificadores = lambda: frozenset({"Ctrl", "Alt"})
    try:
        d.grabar(("accion", "preciso"))
        d._tecla(_Ev(keycode=0x4D, keysym="m"))
        assert estado.atajos.acciones["preciso"].texto() == "Ctrl+Alt+M" and cambios == [1]
    finally:
        d.destroy()


def test_quitar_un_atajo_y_la_emergencia_no_se_puede_quitar(dialogo_atajos):
    d, estado, _, cambios = dialogo_atajos
    d.quitar(("accion", "comparar"))
    assert estado.atajos.acciones["comparar"] is None and d.filas_ui[("accion", "comparar")]["comb"].cget("text") == "sin atajo" and cambios == [1]
    d.quitar(("accion", "emergencia"))
    assert "no quitar" in d.filas_ui[("accion", "emergencia")]["estado"].cget("text") and estado.atajos.acciones["emergencia"] is not None
    assert cambios == [1]


def test_restaurar_valores_por_defecto_pide_confirmacion_y_no_toca_los_perfiles(dialogo_atajos):
    d, estado, _, cambios = dialogo_atajos
    estado.asignar_atajo(("accion", "siguiente"), _atajos.parsear("Ctrl+Alt+F9"))
    estado.asignar_atajo(("perfil", "Oscuro"), _atajos.parsear("Ctrl+Alt+2"))
    d.confirmar = lambda t, m: False
    d._restaurar()
    assert estado.atajos.acciones["siguiente"].texto() == "Ctrl+Alt+F9" and cambios == []
    d.confirmar = lambda t, m: True
    d._restaurar()
    d.refrescar()
    assert estado.atajos.acciones["siguiente"].texto() == "Ctrl+Alt+P" and estado.atajos.perfiles["Oscuro"].texto() == "Ctrl+Alt+2"
    assert d.filas_ui[("accion", "siguiente")]["comb"].cget("text") == "Ctrl+Alt+P" and cambios == [1]


def test_el_aviso_de_altgr_se_muestra_al_asignar_una_combinacion_que_escribe_un_caracter(dialogo_atajos, monkeypatch):
    from vislumbra import teclado

    d, estado, _, _ = dialogo_atajos
    monkeypatch.setattr(teclado, "caracter_con_altgr", lambda c: "@" if c.tecla == "Q" else None)
    d.grabar(("accion", "preciso"))
    d.pulsar(0x51, "Ctrl", "Alt")  # Ctrl+Alt+Q
    assert "escribe «@» con AltGr" in d.lbl_mensaje.cget("text") and estado.atajos.acciones["preciso"].texto() == "Ctrl+Alt+Q"
    d.grabar(("accion", "preciso"))
    d.pulsar(0x4D, "Ctrl", "Alt")
    assert d.lbl_mensaje.cget("text") == ""


def test_el_aviso_al_usar_un_atajo_se_cambia_y_se_guarda(dialogo_atajos):
    d, estado, _, cambios = dialogo_atajos
    d.var_aviso.set("Sonido")
    d._aviso_cambiado()
    assert estado.atajos.aviso == "sonido" and cambios == [1]
    d.var_aviso.set("Notificación")
    d._aviso_cambiado()
    assert estado.atajos.aviso == "notificacion"


def test_las_combinaciones_en_uso_por_otra_aplicacion_se_marcan_en_la_fila(ventana):
    estado = _estado_de_prueba()
    d = dialogos.DialogoAtajos(ventana, estado, None, lambda: None, lambda: {("accion", "siguiente"): Resultado(False, 1409), ("accion", "comparar"): Resultado(True)})
    try:
        assert "En uso por otra aplicación" in d.filas_ui[("accion", "siguiente")]["estado"].cget("text")
        assert d.filas_ui[("accion", "comparar")]["estado"].cget("text") == ""
    finally:
        d.destroy()


def test_los_perfiles_se_listan_con_sus_atajos_al_abrir(ventana):
    estado = _estado_de_prueba()
    estado.asignar_atajo(("perfil", "Oscuro"), _atajos.parsear("Ctrl+Alt+2"))
    d = dialogos.DialogoAtajos(ventana, estado, None, lambda: None, lambda: {})
    try:
        assert d.filas_ui[("perfil", "Oscuro")]["comb"].cget("text") == "Ctrl+Alt+2"
        assert d.combinacion_de(("perfil", "Código")) is None
    finally:
        d.destroy()
