# SPDX-License-Identifier: GPL-3.0-or-later
"""Pruebas de ``vislumbra.app`` con sesión, monitores y bandeja falsos: no tocan la pantalla.

Usan una ventana de Tk oculta, objetos del sistema con nombres aleatorios y la carpeta temporal
(nunca el ``%APPDATA%`` real). La cola se procesa a mano con ``_procesar_cola`` (sin ``mainloop``).
"""

import threading
import time
import uuid

import pytest

from vislumbra import app as app_mod
from vislumbra import atajos, teclado
from vislumbra import color, display, perfiles, tray
from vislumbra.app import App
from vislumbra.color import Ajuste
from vislumbra.teclado import Resultado
from vislumbra.perfiles import Configuracion, Perfil

IDENTIDAD = color.rampa_identidad()


def monitores(n=3):
    return [
        display.Monitor(i, rf"\\.\PRUEBA{i}", "Adaptador de pruebas", None, i == 2, id_monitor=f"clave-{i}")
        for i in range(1, n + 1)
    ]


class SesionFalsa:
    def __init__(self, ms):
        self.monitores = list(ms)
        self.pantalla = {m.numero: list(IDENTIDAD) for m in ms}
        self.originales = {m.numero: list(IDENTIDAD) for m in ms}
        self.modificados = []
        self.cerrada = 0
        self.iniciada = False

    def iniciar(self):
        self.iniciada = True

    def cerrar(self):
        self.cerrada += 1
        for n in self.pantalla:
            self.pantalla[n] = list(self.originales[n])

    def originales_modificados(self):
        return self.modificados

    def aplicar_por_monitor(self, rampas):
        for n, r in rampas.items():
            self.pantalla[n] = list(self.originales[n] if r is None else r)
        return []


class ArranqueFalso:
    """«Iniciar con Windows» simulado: estas pruebas nunca tocan la carpeta Inicio real."""

    ErrorArranque = app_mod.arranque.ErrorArranque

    def __init__(self):
        self.activado = False
        self.falla = False
        self.apunta = True

    def esta_activado(self):
        return self.activado

    def apunta_a_algo_que_existe(self):
        return self.apunta

    def activar(self):
        if self.falla:
            raise self.ErrorArranque("no se pudo crear el acceso directo")
        self.activado = True

    def desactivar(self):
        self.activado = False


class GestorFalso:
    """Atajos globales simulados: nunca registran combinaciones de verdad."""

    def __init__(self, al_atajo):
        self.al_atajo = al_atajo
        self.mapa: dict = {}
        self.aplicaciones = 0
        self.fallan: set = set()
        self.parado = False
        self.iniciado = False

    def iniciar(self):
        self.iniciado = True

    def aplicar(self, mapa, espera=2.0):
        self.mapa = dict(mapa)
        self.aplicaciones += 1
        return {k: (Resultado(False, 1409) if k in self.fallan else Resultado(True)) for k in mapa}

    def pausar(self, espera=2.0):
        pass

    def reanudar(self, espera=2.0):
        return {}

    def probar(self, comb, espera=2.0):
        return Resultado(True)

    def parar(self, espera=2.0):
        self.parado = True

    def pulsar(self, clave):
        """Lo que haría el hilo de atajos de Windows al pulsar la combinación."""
        self.al_atajo(clave)


class Entorno:
    """Todo lo que hace falta para probar una ``App``."""

    def __init__(self, ventana, tmp_path, n_monitores=3, conf=None):
        self.ms = monitores(n_monitores)
        self.sesiones: list[SesionFalsa] = []
        self.prefijo = rf"Local\VislumbraPrueba{uuid.uuid4().hex}"
        self.ruta_config = tmp_path / "config.json"
        self.ruta_peticion = tmp_path / "peticion.txt"
        if conf is not None:
            perfiles.guardar_en(conf, self.ruta_config)
        self.ventana = ventana
        self.apps: list[App] = []
        self.arranque = ArranqueFalso()
        self.gestores: list[GestorFalso] = []
        self.procesos: frozenset[str] = frozenset()
        self.ventanas: dict[str, str] = {}

    def crear_sesion(self, ms):
        s = SesionFalsa(ms)
        self.sesiones.append(s)
        return s

    @property
    def sesion(self):
        return self.sesiones[-1]

    def leer(self, m):
        return list(self.sesion.pantalla[m.numero])

    def crear_gestor(self, al_atajo):
        g = GestorFalso(al_atajo)
        self.gestores.append(g)
        return g

    @property
    def gestor(self):
        return self.gestores[-1]

    def nueva(self, ventana=None, oculto=False):
        a = App(
            raiz=ventana or self.ventana, ruta_config=self.ruta_config, ruta_peticion_=self.ruta_peticion,
            listar=lambda: list(self.ms), leer=self.leer, crear_sesion=self.crear_sesion,
            prefijo_sistema=self.prefijo, con_bandeja=False, intervalo_vigilancia=0.05,
            oculto=oculto, arranque=self.arranque, leer_procesos=lambda: self.procesos, leer_ventanas=lambda exes: {k: v for k, v in self.ventanas.items() if k in exes},
            intervalo_procesos=0.05, crear_gestor=self.crear_gestor,
        )
        self.apps.append(a)
        return a

    def cerrar(self):
        for a in self.apps:
            a._parar_todo()


def configuracion():
    c = Configuracion()
    c.guardar(Perfil("Oscuro", Ajuste.uniforme(0.0, 7.5, 1.7)))
    c.guardar(Perfil("Código", Ajuste.uniforme(-20.0, 0.0, 1.0, 6000.0)))
    c.perfil_activo = "Oscuro"
    return c


@pytest.fixture
def entorno(ventana, tmp_path):
    e = Entorno(ventana, tmp_path, conf=configuracion())
    yield e
    e.cerrar()


def esperar(condicion, segundos=3.0):
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if condicion():
            return True
        time.sleep(0.01)
    return False


def procesar(app, hasta=lambda: True, segundos=3.0):
    """Procesa la cola de Tk a mano hasta que se cumpla ``hasta``."""
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        app._procesar_cola()
        if hasta():
            return True
        time.sleep(0.01)
    return False


RAMPA_OSCURO = color.construir_rampa_segura(Ajuste.uniforme(0.0, 7.5, 1.7))


# --- Arranque ------------------------------------------------------------------------------------------------------
def test_al_arrancar_aplica_lo_guardado_y_muestra_el_panel(entorno):
    a = entorno.nueva()
    assert a.iniciar() is True
    assert entorno.sesion.iniciada
    assert esperar(lambda: all(entorno.sesion.pantalla[n] == RAMPA_OSCURO for n in (1, 2, 3)))
    assert a.estado.activo == "Oscuro" and a.panel.visible and a.aplicador.vivo
    assert hasattr(a.raiz, "winfo_exists") and a.panel.var_activo.get() == "Oscuro"


def test_sin_configuracion_todo_empieza_en_normal_y_no_se_escribe_nada(ventana, tmp_path):
    e = Entorno(ventana, tmp_path)
    try:
        a = e.nueva()
        assert a.iniciar() is True
        time.sleep(0.2)
        assert a.estado.activo == "Normal" and all(r is None for r in a.estado.rampas().values())
        assert all(e.sesion.pantalla[n] == IDENTIDAD for n in (1, 2, 3))
    finally:
        e.cerrar()


def test_una_configuracion_danada_se_aparta_y_se_avisa(ventana, tmp_path):
    e = Entorno(ventana, tmp_path)
    e.ruta_config.write_text("esto no es json", encoding="utf-8")
    try:
        a = e.nueva()
        a.iniciar()
        assert a.estado.activo == "Normal" and len(a.avisos_arranque) == 1
        assert "no era válida" in a.panel.lbl_aviso.cget("text")
        assert list(tmp_path.glob("config.dañado-*.json"))
    finally:
        e.cerrar()


def test_un_monitor_con_rampa_original_modificada_se_avisa(entorno):
    original = entorno.nueva()
    original._crear_sesion = lambda ms: _con_modificado(entorno, ms)
    original.iniciar()
    assert "ya tenía una rampa modificada" in original.panel.lbl_aviso.cget("text")


def _con_modificado(entorno, ms):
    s = entorno.crear_sesion(ms)
    s.modificados = [ms[0]]
    return s


def test_sin_monitores_no_arranca_y_no_deja_nada_a_medias(entorno):
    entorno.ms = []
    a = entorno.nueva()
    with pytest.raises(display.MonitorNoEncontrado):
        a.iniciar()
    assert not app_mod.hay_app_abierta(entorno.prefijo)


# --- Instancia única, eventos y peticiones --------------------------------------------------------------------------------
def test_una_segunda_instancia_muestra_el_panel_de_la_primera_y_sale(entorno, ventana):
    a = entorno.nueva()
    a.iniciar()
    a.panel.ocultar()
    assert not a.panel.visible
    segunda = entorno.nueva()
    assert segunda.iniciar() is False  # no crea nada: no hay sesión ni hilos
    assert len(entorno.sesiones) == 1
    assert procesar(a, lambda: a.panel.visible)


def test_hay_app_abierta_mientras_esta_en_marcha_y_deja_de_haberla_al_cerrar(entorno):
    assert not app_mod.hay_app_abierta(entorno.prefijo)
    a = entorno.nueva()
    a.iniciar()
    assert app_mod.hay_app_abierta(entorno.prefijo)
    a._parar_todo()
    assert not app_mod.hay_app_abierta(entorno.prefijo)


def test_reset_desde_la_terminal_desactiva_la_app_y_suelta_la_pantalla(entorno):
    a = entorno.nueva()
    a.iniciar()
    assert esperar(lambda: entorno.sesion.pantalla[1] == RAMPA_OSCURO)
    assert app_mod.pedir_desactivar(entorno.prefijo) is True
    assert procesar(a, lambda: not a.estado.activo_on)
    assert esperar(lambda: all(entorno.sesion.pantalla[n] == IDENTIDAD for n in (1, 2, 3)))
    assert "Desactivado por --reset" in a.panel.lbl_aviso.cget("text") and not a.panel.var_on.get()


def test_pedir_desactivar_sin_app_abierta_devuelve_false(entorno):
    assert app_mod.pedir_desactivar(entorno.prefijo) is False


def test_perfil_siguiente_desde_la_terminal(entorno):
    a = entorno.nueva()
    a.iniciar()
    assert app_mod.pedir_perfil(app_mod.PETICION_SIGUIENTE, entorno.ruta_peticion, entorno.prefijo) is True
    assert procesar(a, lambda: a.estado.activo == "Código")
    assert not entorno.ruta_peticion.exists()  # la petición se borra al leerla
    assert perfiles.cargar(entorno.ruta_config)[0].perfil_activo == "Código"  # y el cambio se guarda
    assert esperar(lambda: entorno.sesion.pantalla[1] == color.construir_rampa_segura(Ajuste.uniforme(-20.0, 0.0, 1.0, 6000.0)))
    assert "Perfil cambiado desde la terminal" in a.panel.lbl_aviso.cget("text")


def test_perfil_por_nombre_desde_la_terminal_y_nombre_inexistente(entorno):
    a = entorno.nueva()
    a.iniciar()
    app_mod.pedir_perfil("perfil:Normal", entorno.ruta_peticion, entorno.prefijo)
    assert procesar(a, lambda: a.estado.activo == "Normal")
    app_mod.pedir_perfil("perfil:NoExiste", entorno.ruta_peticion, entorno.prefijo)
    assert procesar(a, lambda: "no existe" in a.panel.lbl_aviso.cget("text"))
    assert a.estado.activo == "Normal"
    app_mod.pedir_perfil("cualquier cosa", entorno.ruta_peticion, entorno.prefijo)
    assert procesar(a, lambda: "no reconocida" in a.panel.lbl_aviso.cget("text"))


def test_pedir_perfil_sin_app_abierta_no_escribe_nada(entorno):
    assert app_mod.pedir_perfil("siguiente", entorno.ruta_peticion, entorno.prefijo) is False
    assert not entorno.ruta_peticion.exists()


# --- Bandeja ----------------------------------------------------------------------------------------------------------------------
def test_acciones_de_la_bandeja(entorno):
    a = entorno.nueva()
    a.iniciar()
    a._atender_bandeja(tray.SIGUIENTE, None)
    assert a.estado.activo == "Código"
    a._atender_bandeja(tray.PERFIL, "Oscuro")
    assert a.estado.activo == "Oscuro"
    a._atender_bandeja(tray.COMPARAR, None)
    assert a.estado.ab and a._info.ab
    a._atender_bandeja(tray.COMPARAR, None)
    a._atender_bandeja(tray.ALTERNAR_ACTIVO, None)
    assert not a.estado.activo_on and not a._info.activo_on
    a._atender_bandeja(tray.COMPARAR, None)  # desactivado: no hay nada que comparar
    assert not a.estado.ab
    a._atender_bandeja(tray.PERFIL, "NoExiste")
    assert "no existe" in a.panel.lbl_aviso.cget("text")
    a._atender_bandeja(tray.MOSTRAR_OCULTAR, None)
    assert not a.panel.visible
    a._atender_bandeja(tray.MOSTRAR_OCULTAR, None)
    assert a.panel.visible


def test_las_acciones_de_la_bandeja_pasan_por_la_cola(entorno):
    a = entorno.nueva()
    a.iniciar()
    a._accion_de_bandeja(tray.SIGUIENTE, None)  # lo que haría el hilo de pystray
    assert a.estado.activo == "Oscuro"  # aún no se ha procesado
    assert procesar(a, lambda: a.estado.activo == "Código")


def test_la_info_de_la_bandeja_refleja_los_monitores_y_perfiles(entorno):
    a = entorno.nueva()
    a.iniciar()
    assert a._info.grupos == (("Oscuro", (1, 2, 3)),) and a._info.perfiles == ("Normal", "Oscuro", "Código")
    assert tray.texto_emergente(a._info) == "Vislumbra · activo · Oscuro (1, 2, 3)"


# --- Avisos del hilo aplicador --------------------------------------------------------------------------------------------------
def test_avisos_del_aplicador_se_muestran_en_el_panel(entorno):
    a = entorno.nueva()
    a.iniciar()
    a._atender_aviso(Aviso("rechazo", "Windows ha rechazado la rampa.", (1,)))
    assert "Windows no aceptó la rampa: Windows ha rechazado" in a.panel.lbl_aviso.cget("text")
    a._atender_aviso(Aviso("conflicto", "Algo cambia la rampa del monitor 1.", (1,)))
    assert "Algo cambia" in a.panel.lbl_aviso.cget("text")
    a._atender_aviso(Aviso("aplicado", monitores=(1,)))
    a._atender_aviso(Aviso("lectura", "no coincide"))
    assert a.panel.lbl_aviso.cget("text") == "no coincide"


Aviso = app_mod.Aviso


def test_si_otro_programa_cambia_la_rampa_la_app_la_vuelve_a_aplicar(entorno):
    a = entorno.nueva()
    a.iniciar()
    assert esperar(lambda: entorno.sesion.pantalla[1] == RAMPA_OSCURO)
    entorno.sesion.pantalla[1] = list(IDENTIDAD)  # un juego la reinicia
    assert esperar(lambda: entorno.sesion.pantalla[1] == RAMPA_OSCURO)


def test_cambio_en_la_lista_de_monitores_recrea_la_sesion(entorno):
    a = entorno.nueva()
    a.iniciar()
    assert esperar(lambda: entorno.sesion.pantalla[1] == RAMPA_OSCURO)
    primera = entorno.sesion
    entorno.ms = monitores(2)  # se desconectó el tercero
    assert procesar(a, lambda: len(entorno.sesiones) == 2)
    assert primera.cerrada >= 1 and entorno.sesion is not primera and entorno.sesion.iniciada
    assert [m.numero for m in a.estado.monitores] == [1, 2] and a.aplicador.vivo
    assert esperar(lambda: entorno.sesion.pantalla[1] == RAMPA_OSCURO)
    assert "Cambió la lista de monitores" in a.panel.lbl_aviso.cget("text")


def test_si_se_quedan_sin_monitores_la_app_se_pone_en_pausa(entorno):
    a = entorno.nueva()
    a.iniciar()
    entorno.ms = []
    assert procesar(a, lambda: "en pausa" in a.panel.lbl_aviso.cget("text"))


# --- Persistencia y cierre ---------------------------------------------------------------------------------------------------------
def test_persistir_escribe_el_perfil_activo_y_las_asignaciones(entorno):
    a = entorno.nueva()
    a.iniciar()
    a.estado.cambiar_activo("Normal")
    a.estado.fijar_monitor(3, "Código")
    a.persistir()
    c, avisos = perfiles.cargar(entorno.ruta_config)
    assert avisos == [] and c.perfil_activo == "Normal" and c.monitores["clave-3"] == "Código"


def test_persistir_no_escribe_perfiles_sin_guardar(entorno):
    a = entorno.nueva()
    a.iniciar()
    a.panel.deslizadores["gamma"]._pedir(2.0)  # edita «Oscuro» sin guardar
    a.persistir()
    c, _ = perfiles.cargar(entorno.ruta_config)
    assert c.obtener("Oscuro").ajuste.r.gamma == 1.7


def test_un_error_al_guardar_se_muestra_y_no_rompe_la_app(entorno, monkeypatch):
    a = entorno.nueva()
    a.iniciar()

    def falla(*_):
        raise OSError("disco lleno")

    monkeypatch.setattr(perfiles, "guardar_en", falla)
    a.persistir()
    assert "No se pudo guardar" in a.panel.lbl_aviso.cget("text")


def test_salir_restaura_la_pantalla_y_libera_todo(entorno):
    a = entorno.nueva()
    a.iniciar()
    assert esperar(lambda: entorno.sesion.pantalla[1] == RAMPA_OSCURO)
    hilo = a._hilo_eventos
    a.salir()
    s = entorno.sesion
    assert s.cerrada >= 1 and all(s.pantalla[n] == IDENTIDAD for n in (1, 2, 3))
    assert not a.aplicador.vivo and not hilo.is_alive() and not app_mod.hay_app_abierta(entorno.prefijo)
    a._parar_todo()  # idempotente
    nueva = entorno.nueva()
    assert nueva.iniciar() is True  # el mutex quedó libre


def test_salir_con_cambios_sin_guardar_pregunta(entorno):
    a = entorno.nueva()
    a.iniciar()
    a.panel.deslizadores["gamma"]._pedir(2.0)
    a.panel.preguntar_guardar = lambda: None  # Cancelar
    a.salir()
    assert a.aplicador.vivo and app_mod.hay_app_abierta(entorno.prefijo)
    a.panel.preguntar_guardar = lambda: True  # Guardar
    a.salir()
    assert not a.aplicador.vivo
    assert perfiles.cargar(entorno.ruta_config)[0].obtener("Oscuro").ajuste.r.gamma == 2.0


def test_salir_descartando_no_guarda_los_cambios(entorno):
    a = entorno.nueva()
    a.iniciar()
    a.panel.deslizadores["gamma"]._pedir(2.0)
    a.panel.preguntar_guardar = lambda: False  # Descartar
    a.salir()
    assert perfiles.cargar(entorno.ruta_config)[0].obtener("Oscuro").ajuste.r.gamma == 1.7


def test_ctrl_c_o_cierre_de_consola_dentro_de_tk_cierra_sin_preguntar(entorno):
    a = entorno.nueva()
    a.iniciar()
    a.panel.deslizadores["gamma"]._pedir(2.0)
    a._excepcion_tk(KeyboardInterrupt, KeyboardInterrupt(), None)
    assert not a.aplicador.vivo and entorno.sesion.cerrada >= 1
    assert all(entorno.sesion.pantalla[n] == IDENTIDAD for n in (1, 2, 3))


def test_un_error_interno_en_tk_se_muestra_y_la_app_sigue(entorno, capsys):
    a = entorno.nueva()
    a.iniciar()
    a._excepcion_tk(ValueError, ValueError("fallo raro"), None)
    assert "Error interno: fallo raro" in a.panel.lbl_aviso.cget("text") and a.aplicador.vivo
    assert "Error interno" in capsys.readouterr().err


def test_ocultar_el_panel_avisa_solo_la_primera_vez(entorno):
    a = entorno.nueva()
    a.iniciar()
    avisos = []

    class BandejaFalsa:
        def avisar(self, titulo, mensaje):
            avisos.append(titulo)

        def actualizar(self):
            pass

        def detener(self):
            pass

    a.bandeja = BandejaFalsa()
    a.ocultar_panel()
    a.panel.mostrar()
    a.ocultar_panel()
    assert avisos == ["Vislumbra sigue en marcha"] and not a.panel.visible


def test_si_falla_la_restauracion_el_cierre_libera_igualmente_todo(entorno, capsys):
    a = entorno.nueva()
    a.iniciar()

    def falla():
        raise RuntimeError("no se puede")

    entorno.sesion.cerrar = falla
    a._parar_todo()
    assert not a.aplicador.vivo and not app_mod.hay_app_abierta(entorno.prefijo)
    assert "no se pudo restaurar la pantalla" in capsys.readouterr().err


# --- Iniciar con Windows y arranque oculto -----------------------------------------------------------------------------------
def test_con_oculto_la_app_arranca_sin_mostrar_el_panel_pero_aplica_lo_guardado(entorno):
    a = entorno.nueva(oculto=True)
    assert a.iniciar() is True
    assert not a.panel.visible
    assert esperar(lambda: entorno.sesion.pantalla[1] == RAMPA_OSCURO)


def test_con_oculto_una_segunda_instancia_no_muestra_el_panel_de_la_primera(entorno):
    a = entorno.nueva()
    a.iniciar()
    a.panel.ocultar()
    segunda = entorno.nueva(oculto=True)
    assert segunda.iniciar() is False
    time.sleep(0.3)
    a._procesar_cola()
    assert not a.panel.visible


def test_la_bandeja_activa_y_desactiva_el_arranque_con_windows(entorno):
    a = entorno.nueva()
    a.iniciar()
    assert a._info.arranque is False
    a._atender_bandeja(tray.ARRANQUE, None)
    assert entorno.arranque.activado and a._info.arranque is True
    assert "se iniciará con Windows" in a.panel.lbl_aviso.cget("text")
    a._atender_bandeja(tray.ARRANQUE, None)
    assert not entorno.arranque.activado and a._info.arranque is False
    assert "ya no se iniciará" in a.panel.lbl_aviso.cget("text")


def test_si_falla_el_arranque_se_avisa_y_no_cambia_el_estado(entorno):
    a = entorno.nueva()
    a.iniciar()
    entorno.arranque.falla = True
    a._atender_bandeja(tray.ARRANQUE, None)
    assert "no se pudo crear" in a.panel.lbl_aviso.cget("text") and a._info.arranque is False


def test_al_arrancar_se_refleja_el_estado_y_se_avisa_si_el_acceso_esta_roto(entorno):
    entorno.arranque.activado = True
    entorno.arranque.apunta = False
    a = entorno.nueva()
    a.iniciar()
    assert a._info.arranque is True and "ya no existe" in a.panel.lbl_aviso.cget("text")


# --- Perfil automático por programa ----------------------------------------------------------------------------------------
RAMPA_CODIGO = color.construir_rampa_segura(Ajuste.uniforme(-20.0, 0.0, 1.0, 6000.0))


def con_juego(a):
    a.estado.asociar_programa("Juego.exe", "Código")
    a.persistir()  # actualiza los programas vigilados y guarda


def test_al_abrirse_el_programa_asociado_se_activa_su_perfil_y_al_cerrarse_vuelve_el_de_antes(entorno):
    a = entorno.nueva()
    a.iniciar()
    con_juego(a)
    a._procesos_cambiaron(frozenset({"juego.exe"}))
    assert a.estado.activo == "Código" and a._exe_auto == "juego.exe"
    assert esperar(lambda: entorno.sesion.pantalla[1] == RAMPA_CODIGO)
    assert "Perfil automático: juego.exe → «Código»" in a.panel.lbl_aviso.cget("text") and a.panel.var_activo.get() == "Código"
    a._procesos_cambiaron(frozenset())
    assert a.estado.activo == "Oscuro" and a._exe_auto is None
    assert esperar(lambda: entorno.sesion.pantalla[1] == RAMPA_OSCURO)
    assert "vuelve el perfil «Oscuro»" in a.panel.lbl_aviso.cget("text")


def test_el_hilo_detecta_el_programa_solo(entorno):
    a = entorno.nueva()
    a.iniciar()
    con_juego(a)
    entorno.procesos = frozenset({"juego.exe", "chrome.exe"})  # chrome no está asociado: se ignora
    assert procesar(a, lambda: a.estado.activo == "Código")
    entorno.procesos = frozenset({"chrome.exe"})
    assert procesar(a, lambda: a.estado.activo == "Oscuro")


def test_un_programa_que_ya_estaba_abierto_al_arrancar_se_detecta(ventana, tmp_path):
    conf = configuracion()
    conf.asociar("juego.exe", "Código")
    e = Entorno(ventana, tmp_path, conf=conf)
    e.procesos = frozenset({"juego.exe"})
    try:
        a = e.nueva()
        a.iniciar()
        assert procesar(a, lambda: a.estado.activo == "Código")
        assert esperar(lambda: e.sesion.pantalla[1] == RAMPA_CODIGO)
    finally:
        e.cerrar()


def test_el_perfil_automatico_no_se_guarda_como_el_activo(entorno):
    a = entorno.nueva()
    a.iniciar()
    con_juego(a)
    a._procesos_cambiaron(frozenset({"juego.exe"}))
    a.persistir()
    c, _ = perfiles.cargar(entorno.ruta_config)
    assert c.perfil_activo == "Oscuro" and [(x.exe, x.perfil) for x in c.programas] == [("juego.exe", "Código")]


def test_si_el_usuario_cambia_de_perfil_durante_el_juego_se_respeta_al_cerrarlo(entorno):
    a = entorno.nueva()
    a.iniciar()
    con_juego(a)
    a._procesos_cambiaron(frozenset({"juego.exe"}))
    a._atender_bandeja(tray.PERFIL, "Normal")  # a mano
    a._procesos_cambiaron(frozenset())
    assert a.estado.activo == "Normal"


def test_con_activo_apagado_cambia_el_perfil_pero_la_pantalla_sigue_original(entorno):
    a = entorno.nueva()
    a.iniciar()
    con_juego(a)
    a._atender_bandeja(tray.ALTERNAR_ACTIVO, None)
    assert esperar(lambda: entorno.sesion.pantalla[1] == IDENTIDAD)
    a._procesos_cambiaron(frozenset({"juego.exe"}))
    assert a.estado.activo == "Código"
    time.sleep(0.3)
    assert entorno.sesion.pantalla[1] == IDENTIDAD and not a.estado.activo_on


def test_un_programa_sin_asociar_o_con_perfil_borrado_no_cambia_nada(entorno):
    a = entorno.nueva()
    a.iniciar()
    a._procesos_cambiaron(frozenset({"juego.exe"}))  # no hay asociación
    assert a.estado.activo == "Oscuro" and a._exe_auto is None
    con_juego(a)
    a.estado._sustituir_referencias("Código", None)  # el perfil se borra: la asociación desaparece
    a._procesos_cambiaron(frozenset({"juego.exe"}))
    assert a.estado.activo == "Oscuro"


def test_dos_programas_abiertos_mandan_el_ultimo(entorno):
    a = entorno.nueva()
    a.iniciar()
    a.estado.asociar_programa("a.exe", "Código")
    a.estado.asociar_programa("b.exe", "Normal")
    a.persistir()
    a._procesos_cambiaron(frozenset({"a.exe"}))
    assert a.estado.activo == "Código"
    a._procesos_cambiaron(frozenset({"a.exe", "b.exe"}))
    assert a.estado.activo == "Normal"
    a._procesos_cambiaron(frozenset({"a.exe"}))
    assert a.estado.activo == "Código"
    a._procesos_cambiaron(frozenset())
    assert a.estado.activo == "Oscuro"


def test_la_bandeja_abre_el_dialogo_de_programas(entorno):
    a = entorno.nueva(oculto=True)
    a.iniciar()
    llamadas = []
    a.panel.abrir_dialogo_programas = lambda *args: llamadas.append(args)
    a._atender_bandeja(tray.PROGRAMAS, None)
    assert a.panel.visible and len(llamadas) == 1 and llamadas[0][1] is a.estado


def test_cambiar_los_programas_desde_el_dialogo_actualiza_lo_vigilado_y_se_guarda(entorno):
    a = entorno.nueva()
    a.iniciar()
    assert a._vigilados == frozenset()
    a.estado.asociar_programa("juego.exe", "Código")
    a.panel.ctl.persistir()  # lo que llama el diálogo al añadir
    assert a._vigilados == {"juego.exe"}
    assert perfiles.cargar(entorno.ruta_config)[0].programas[0].exe == "juego.exe"


def test_al_cerrar_para_el_hilo_de_procesos(entorno):
    a = entorno.nueva()
    a.iniciar()
    hilo = a._hilo_procesos
    assert hilo.is_alive()
    a._parar_todo()
    assert not hilo.is_alive()


# --- Programas por monitor (alcance «ventana» y «monitor concreto») -----------------------------------------------------------
def monitores_fijos(a):
    """El caso del autor: todos los monitores con perfil fijo."""
    a.estado.fijar_monitor(1, "Código")
    a.estado.fijar_monitor(2, "Oscuro")
    a.estado.fijar_monitor(3, "Normal")
    a.rampas_cambiaron()
    assert esperar(lambda: entorno_pantalla(a)[1] == RAMPA_CODIGO)


def entorno_pantalla(a):
    return a.sesion.pantalla


def test_un_programa_con_alcance_ventana_solo_cambia_el_monitor_donde_esta(entorno):
    a = entorno.nueva()
    a.iniciar()
    monitores_fijos(a)
    a.estado.asociar_programa("juego.exe", "Oscuro", "ventana")
    a.persistir()
    entorno.ventanas = {"juego.exe": r"\\.\PRUEBA3"}
    entorno.procesos = frozenset({"juego.exe"})
    assert procesar(a, lambda: a.estado.perfil_de_monitor(3).nombre == "Oscuro")
    assert esperar(lambda: entorno.sesion.pantalla[3] == RAMPA_OSCURO)
    assert entorno.sesion.pantalla[1] == RAMPA_CODIGO and a.estado.activo == "Oscuro" and not a.estado.automatico
    assert "Perfil automático: juego.exe → «Oscuro» en el monitor 3" in a.panel.lbl_aviso.cget("text")
    entorno.procesos = frozenset()
    assert procesar(a, lambda: a.estado.perfil_de_monitor(3).es_normal)
    assert esperar(lambda: entorno.sesion.pantalla[3] == IDENTIDAD)
    assert "vuelven los perfiles de antes" in a.panel.lbl_aviso.cget("text")


def test_minimizar_no_quita_el_perfil_y_arrastrar_la_ventana_lo_mueve(entorno):
    a = entorno.nueva()
    a.iniciar()
    monitores_fijos(a)
    a.estado.asociar_programa("juego.exe", "Oscuro", "ventana")
    a.persistir()
    a._procesos_cambiaron(frozenset({"juego.exe"}), {"juego.exe": r"\\.\PRUEBA3"})
    assert a.estado.perfil_de_monitor(3).nombre == "Oscuro"
    a._procesos_cambiaron(frozenset({"juego.exe"}), {})  # minimizado o alt-tab: sin ventana visible
    assert a.estado.perfil_de_monitor(3).nombre == "Oscuro"
    a._procesos_cambiaron(frozenset({"juego.exe"}), {"juego.exe": r"\\.\PRUEBA1"})  # lo arrastraron al monitor 1
    assert a.estado.perfil_de_monitor(1).nombre == "Oscuro" and a.estado.perfil_de_monitor(3).es_normal


def test_un_monitor_concreto_se_aplica_aunque_la_ventana_este_en_otro(entorno):
    a = entorno.nueva()
    a.iniciar()
    monitores_fijos(a)
    clave3 = a.estado.monitores[2].clave
    a.estado.asociar_programa("juego.exe", "Oscuro", "monitor:" + clave3)
    a.persistir()
    a._procesos_cambiaron(frozenset({"juego.exe"}), {"juego.exe": r"\\.\PRUEBA1"})
    assert a.estado.perfil_de_monitor(3).nombre == "Oscuro" and a.estado.perfil_de_monitor(1).nombre == "Código"


def test_lo_que_ponen_los_programas_por_monitor_no_se_guarda(entorno):
    a = entorno.nueva()
    a.iniciar()
    monitores_fijos(a)
    a.estado.asociar_programa("juego.exe", "Oscuro", "ventana")
    a.persistir()
    a._procesos_cambiaron(frozenset({"juego.exe"}), {"juego.exe": r"\\.\PRUEBA3"})
    a.persistir()
    c, _ = perfiles.cargar(entorno.ruta_config)
    assert c.monitores[a.estado.monitores[2].clave] == "Normal"  # el fijo del monitor 3, no el del programa
    assert [(x.exe, x.alcance) for x in c.programas] == [("juego.exe", "ventana")]


def test_el_hilo_lee_las_ventanas_solo_de_los_programas_con_alcance_ventana(entorno):
    a = entorno.nueva()
    a.iniciar()
    monitores_fijos(a)
    a.estado.asociar_programa("juego.exe", "Oscuro", "ventana")
    a.estado.asociar_programa("global.exe", "Código", "activo")
    a.persistir()
    assert a._vigilados_ventana == {"juego.exe"} and a._vigilados == {"juego.exe", "global.exe"}
    entorno.ventanas = {"juego.exe": r"\\.\PRUEBA2"}
    entorno.procesos = frozenset({"juego.exe"})
    assert procesar(a, lambda: a.estado.perfil_de_monitor(2).nombre == "Oscuro" and "juego.exe" in a.panel.lbl_aviso.cget("text"))


def test_un_programa_que_cambia_de_monitor_se_detecta_por_el_hilo(entorno):
    a = entorno.nueva()
    a.iniciar()
    monitores_fijos(a)
    a.estado.asociar_programa("juego.exe", "Oscuro", "ventana")
    a.persistir()
    entorno.procesos = frozenset({"juego.exe"})
    entorno.ventanas = {"juego.exe": r"\\.\PRUEBA3"}
    assert procesar(a, lambda: a.estado.perfil_de_monitor(3).nombre == "Oscuro")
    entorno.ventanas = {"juego.exe": r"\\.\PRUEBA1"}
    assert procesar(a, lambda: a.estado.perfil_de_monitor(1).nombre == "Oscuro")


# --- Atajos de teclado globales ------------------------------------------------------------------------------------------------
def pulsar(a, entorno, clave):
    """Un atajo: el hilo de atajos avisa y la interfaz lo atiende."""
    entorno.gestor.pulsar(clave)
    procesar(a)


def test_al_arrancar_se_registran_los_atajos_por_defecto(entorno):
    a = entorno.nueva()
    a.iniciar()
    g = entorno.gestor
    assert g.iniciado and g.aplicaciones == 1
    assert {k: c.texto() for k, c in g.mapa.items()} == {
        ("accion", "siguiente"): "Ctrl+Alt+P", ("accion", "anterior"): "Ctrl+Alt+Shift+P", ("accion", "comparar"): "Ctrl+Alt+B",
        ("accion", "activo"): "Ctrl+Alt+V", ("accion", "panel"): "Ctrl+Alt+Shift+V", ("accion", "emergencia"): "Ctrl+Alt+0",
    }
    assert a.gestor_atajos is g and "en uso" not in a.panel.lbl_aviso.cget("text")


def test_siguiente_y_anterior_perfil(entorno):
    a = entorno.nueva()
    a.iniciar()
    pulsar(a, entorno, ("accion", "siguiente"))
    assert a.estado.activo == "Código"
    assert esperar(lambda: entorno.sesion.pantalla[1] == RAMPA_CODIGO)
    pulsar(a, entorno, ("accion", "anterior"))
    assert a.estado.activo == "Oscuro" and esperar(lambda: entorno.sesion.pantalla[1] == RAMPA_OSCURO)
    pulsar(a, entorno, ("accion", "anterior"))
    assert a.estado.activo == "Normal"
    assert perfiles.cargar(entorno.ruta_config)[0].perfil_activo == "Normal"  # como el menú de la bandeja: se guarda


def test_comparar_activo_y_panel(entorno):
    a = entorno.nueva()
    a.iniciar()
    pulsar(a, entorno, ("accion", "comparar"))
    assert a.estado.ab and esperar(lambda: entorno.sesion.pantalla[1] == IDENTIDAD)
    pulsar(a, entorno, ("accion", "comparar"))
    assert not a.estado.ab and esperar(lambda: entorno.sesion.pantalla[1] == RAMPA_OSCURO)
    pulsar(a, entorno, ("accion", "activo"))
    assert not a.estado.activo_on and esperar(lambda: entorno.sesion.pantalla[1] == IDENTIDAD)
    pulsar(a, entorno, ("accion", "activo"))
    assert a.estado.activo_on
    visible = a.panel.visible
    pulsar(a, entorno, ("accion", "panel"))
    assert a.panel.visible is (not visible)


def test_el_atajo_de_modo_preciso(entorno):
    a = entorno.nueva()
    a.iniciar()
    assert not a.estado.preciso
    pulsar(a, entorno, ("accion", "preciso"))
    assert a.estado.preciso and a.panel.var_preciso.get() and all(d.preciso for d in a.panel.deslizadores.values())
    pulsar(a, entorno, ("accion", "preciso"))
    assert not a.estado.preciso


def test_un_atajo_de_perfil_y_con_activo_apagado_reactiva_la_aplicacion(entorno):
    a = entorno.nueva()
    a.iniciar()
    a.estado.asignar_atajo(("perfil", "Código"), atajos.parsear("Ctrl+Alt+2"))
    a.persistir()
    assert ("perfil", "Código") in entorno.gestor.mapa  # se registró al cambiar los atajos
    pulsar(a, entorno, ("accion", "activo"))
    assert not a.estado.activo_on
    pulsar(a, entorno, ("perfil", "Código"))
    assert a.estado.activo == "Código" and a.estado.activo_on
    assert esperar(lambda: entorno.sesion.pantalla[1] == RAMPA_CODIGO)


def test_un_atajo_de_perfil_cambia_a_normal_tambien(entorno):
    a = entorno.nueva()
    a.iniciar()
    a.estado.asignar_atajo(("perfil", "Normal"), atajos.parsear("Ctrl+Alt+1"))
    a.persistir()
    pulsar(a, entorno, ("perfil", "Normal"))
    assert a.estado.activo == "Normal" and esperar(lambda: entorno.sesion.pantalla[1] == IDENTIDAD)


def test_la_emergencia_suelta_la_pantalla_sin_esperar_a_la_interfaz(entorno):
    a = entorno.nueva()
    a.iniciar()
    assert esperar(lambda: entorno.sesion.pantalla[1] == RAMPA_OSCURO)
    t = threading.Thread(target=entorno.gestor.pulsar, args=(("accion", "emergencia"),))  # desde el hilo de atajos
    t.start()
    t.join(5)
    # La cola de Tk NO se ha procesado todavía: la pantalla ya está suelta.
    assert all(entorno.sesion.pantalla[n] == IDENTIDAD for n in (1, 2, 3))
    assert a.estado.activo_on and a.aplicador.en_emergencia
    procesar(a)
    assert not a.estado.activo_on and not a.aplicador.en_emergencia
    assert "EMERGENCIA" in a.panel.lbl_aviso.cget("text") and a.panel.var_on.get() is False
    time.sleep(0.4)
    assert all(entorno.sesion.pantalla[n] == IDENTIDAD for n in (1, 2, 3))  # y no se reaplica


def test_despues_de_la_emergencia_se_puede_volver_a_activar(entorno):
    a = entorno.nueva()
    a.iniciar()
    entorno.gestor.pulsar(("accion", "emergencia"))
    procesar(a)
    a._atender_bandeja(tray.ALTERNAR_ACTIVO, None)
    assert a.estado.activo_on and esperar(lambda: entorno.sesion.pantalla[1] == RAMPA_OSCURO)


def test_la_emergencia_avisa_siempre_en_la_bandeja_aunque_el_aviso_de_atajos_este_apagado(entorno):
    a = entorno.nueva()
    a.iniciar()
    avisos = []
    a.bandeja = type("B", (), {"avisar": lambda s, t, m: avisos.append(t), "actualizar": lambda s: None, "detener": lambda s: None})()
    assert a.estado.atajos.aviso == "ninguno"
    entorno.gestor.pulsar(("accion", "emergencia"))
    procesar(a)
    assert "Emergencia" in avisos


def test_los_atajos_que_otra_aplicacion_tiene_se_avisan_en_el_panel_y_en_la_bandeja(entorno):
    a = entorno.nueva()
    a.iniciar()
    avisos = []
    a.bandeja = type("B", (), {"avisar": lambda s, t, m: avisos.append((t, m)), "actualizar": lambda s: None, "detener": lambda s: None})()
    entorno.gestor.fallan = {("accion", "siguiente"), ("accion", "emergencia")}
    a._registrar_atajos(forzar=True)
    texto = a.panel.lbl_aviso.cget("text")
    assert "Siguiente perfil (Ctrl+Alt+P)" in texto and "Emergencia" in texto and "otra aplicación" in texto
    assert avisos and avisos[0][0] == "Atajo de emergencia no disponible" and "Ctrl+Alt+0" in avisos[0][1]
    assert not a.resultados_atajos[("accion", "siguiente")].ok and a.resultados_atajos[("accion", "comparar")].ok


def test_un_atajo_en_uso_no_impide_arrancar(ventana, tmp_path):
    e = Entorno(ventana, tmp_path, conf=configuracion())
    try:
        a = e.nueva()
        original = e.crear_gestor

        def con_fallos(al_atajo):
            g = original(al_atajo)
            g.fallan = {("accion", "comparar")}
            return g

        a._crear_gestor = con_fallos
        assert a.iniciar() is True
        assert "Comparar (A/B)" in a.panel.lbl_aviso.cget("text") and a.aplicador.vivo
    finally:
        e.cerrar()


def test_sin_gestor_de_atajos_la_app_sigue_funcionando(ventana, tmp_path):
    e = Entorno(ventana, tmp_path, conf=configuracion())
    try:
        a = e.nueva()

        def mal(al_atajo):
            raise teclado.ErrorTeclado("no arrancó")

        a._crear_gestor = mal
        assert a.iniciar() is True and a.gestor_atajos is None
        assert "no están disponibles" in a.panel.lbl_aviso.cget("text")
        a.persistir()  # sin gestor: no falla
    finally:
        e.cerrar()


def test_el_aviso_de_notificacion_y_de_sonido(entorno, monkeypatch):
    import winsound

    a = entorno.nueva()
    a.iniciar()
    avisos, pitidos = [], []
    a.bandeja = type("B", (), {"avisar": lambda s, t, m: avisos.append((t, m)), "actualizar": lambda s: None, "detener": lambda s: None})()
    monkeypatch.setattr(winsound, "MessageBeep", lambda *x: pitidos.append(x))
    pulsar(a, entorno, ("accion", "siguiente"))
    assert avisos == [] and pitidos == []  # por defecto: ninguno
    a.estado.poner_aviso_atajos("notificacion")
    pulsar(a, entorno, ("accion", "siguiente"))
    assert avisos == [("Siguiente perfil", "Perfil activo: Normal")]
    a.estado.poner_aviso_atajos("sonido")
    pulsar(a, entorno, ("accion", "siguiente"))
    assert len(pitidos) == 1 and len(avisos) == 1


def test_persistir_solo_vuelve_a_registrar_si_cambiaron_los_atajos(entorno):
    a = entorno.nueva()
    a.iniciar()
    g = entorno.gestor
    a.persistir()
    a.persistir()
    assert g.aplicaciones == 1
    a.estado.asignar_atajo(("accion", "preciso"), atajos.parsear("Ctrl+Alt+M"))
    a.persistir()
    assert g.aplicaciones == 2 and ("accion", "preciso") in g.mapa
    a.estado.asignar_atajo(("accion", "preciso"), None)
    a.persistir()
    assert g.aplicaciones == 3 and ("accion", "preciso") not in g.mapa


def test_renombrar_o_borrar_un_perfil_con_atajo_actualiza_lo_registrado(entorno):
    a = entorno.nueva()
    a.iniciar()
    a.estado.asignar_atajo(("perfil", "Oscuro"), atajos.parsear("Ctrl+Alt+2"))
    a.persistir()
    a.estado.cambiar_activo("Oscuro")
    a.estado.mirar(2)
    a.estado.renombrar("Noche")
    a.persistir()
    assert ("perfil", "Noche") in entorno.gestor.mapa and ("perfil", "Oscuro") not in entorno.gestor.mapa
    a.estado.borrar()
    a.persistir()
    assert ("perfil", "Noche") not in entorno.gestor.mapa


def test_los_atajos_se_guardan_en_la_configuracion_y_se_leen_al_arrancar(ventana, tmp_path):
    conf = configuracion()
    conf.atajos.asignar_accion("preciso", atajos.parsear("Ctrl+Alt+M"))
    conf.atajos.asignar_perfil("Código", atajos.parsear("Ctrl+Alt+2"))
    e = Entorno(ventana, tmp_path, conf=conf)
    try:
        a = e.nueva()
        a.iniciar()
        assert ("accion", "preciso") in e.gestor.mapa and ("perfil", "Código") in e.gestor.mapa
    finally:
        e.cerrar()


def test_un_atajo_malo_en_el_archivo_se_avisa_al_arrancar(ventana, tmp_path):
    import json

    e = Entorno(ventana, tmp_path, conf=configuracion())
    datos = json.loads(e.ruta_config.read_text(encoding="utf-8"))
    datos["atajos"]["acciones"]["siguiente"] = "Shift+P"
    e.ruta_config.write_text(json.dumps(datos), encoding="utf-8")
    try:
        a = e.nueva()
        a.iniciar()
        assert len(a.avisos_arranque) == 1 and "Mayús sola" in a.avisos_arranque[0]
        assert ("accion", "siguiente") not in e.gestor.mapa and a.estado.activo == "Oscuro"
    finally:
        e.cerrar()


def test_al_cerrar_se_paran_los_atajos(entorno):
    a = entorno.nueva()
    a.iniciar()
    g = entorno.gestor
    a._parar_todo()
    assert g.parado and a.gestor_atajos is None


def test_la_bandeja_abre_el_dialogo_de_atajos(entorno):
    a = entorno.nueva(oculto=True)
    a.iniciar()
    llamadas = []
    a.panel.abrir_dialogo_atajos = lambda *args: llamadas.append(args)
    a._atender_bandeja(tray.ATAJOS, None)
    assert a.panel.visible and len(llamadas) == 1 and llamadas[0][1] is a.estado and llamadas[0][2] is entorno.gestor
    assert llamadas[0][3] == a.panel.ctl.persistir
