# SPDX-License-Identifier: GPL-3.0-or-later
"""Pruebas de ``vislumbra.panel``.

Las funciones puras no necesitan Tk. Las de humo crean una ventana oculta y se saltan si no
hay Tk o escritorio. Nunca tocan la pantalla (la gamma): usan un controlador falso.
"""

import tkinter as tk
from types import SimpleNamespace

import pytest

from vislumbra import color, escala, panel
from vislumbra.panel import Deslizador, GraficoCurva

IDENTIDAD = color.rampa_identidad()


# --- Funciones puras ------------------------------------------------------------------------------------
def test_x_y_posicion_son_inversas_y_se_limitan():
    for p in (0.0, 0.25, 0.5, 1.0):
        assert panel.x_a_posicion(panel.posicion_a_x(p, 220, 10), 220, 10) == pytest.approx(p)
    assert panel.x_a_posicion(-50, 220, 10) == 0.0 and panel.x_a_posicion(999, 220, 10) == 1.0
    assert 0.0 <= panel.x_a_posicion(5, 1, 10) <= 1.0  # ancho diminuto: no divide por cero


def test_puntos_de_la_curva_neutra_van_por_la_diagonal():
    pts = panel.puntos_curva(IDENTIDAD, 100, 100, 0)
    assert len(pts) == 64 and pts[0] == pytest.approx((0, 99)) and pts[-1] == pytest.approx((99, 0))
    assert all(abs(x - (99 - y)) < 1.0 for x, y in pts)


def test_puntos_de_cada_canal():
    r = color.construir_rampa_segura(color.Ajuste(g=color.AjusteCanal(gamma=2.0)))
    verde = panel.puntos_curva(r, 100, 100, 1)
    rojo = panel.puntos_curva(r, 100, 100, 0)
    assert verde[32][1] < rojo[32][1]  # gamma > 1 sube los medios: «y» menor (arriba)


def test_margen_de_windows_y_canales_iguales():
    assert panel.margen_windows(IDENTIDAD) == (0.0, 50.0)
    usado, limite = panel.margen_windows(color.construir_rampa_segura(color.Ajuste.uniforme(0, 7.5, 1.7)))
    assert 10 < usado < 30 and limite == 50.0  # «19 % de 50 %» en el plan
    assert panel.canales_iguales(IDENTIDAD)
    assert not panel.canales_iguales(color.construir_rampa_segura(color.Ajuste(r=color.AjusteCanal(gamma=1.5))))


# --- Humo con Tk ------------------------------------------------------------------------------------------
@pytest.fixture
def raiz(ventana):
    return ventana


def evento(x=0, state=0, delta=0):
    return SimpleNamespace(x=x, state=state, delta=delta)


def deslizador(raiz, parametro="gamma", valor=1.7, respuesta=None):
    llamadas = []

    def al_cambiar(p, v):
        llamadas.append((p, v))
        return respuesta(v) if respuesta else None

    d = Deslizador(raiz, parametro, al_cambiar)
    d.pista.winfo_width = lambda: 220  # la ventana está oculta: se fija el ancho a mano
    d.poner_valor(valor)
    return d, llamadas


def test_el_campo_muestra_el_valor_con_coma(raiz):
    d, _ = deslizador(raiz)
    assert d.texto.get() == "1,70"
    d.poner_valor(6500.0)  # fuera de rango para gamma: se limita
    assert d.texto.get() == "4,00"
    d.destroy()


def test_rueda_y_mayus(raiz):
    d, llamadas = deslizador(raiz)
    d._al_rueda(evento(delta=120))
    d._al_rueda(evento(delta=-120))
    d._al_rueda(evento(delta=120, state=panel.SHIFT))
    assert [round(v, 2) for _, v in llamadas] == [1.75, 1.7, 1.71]
    d.destroy()


def test_flechas_y_botones(raiz):
    d, llamadas = deslizador(raiz, "temperatura", 6500.0)
    d.pista.event_generate("<Right>")
    d.pista.event_generate("<Left>")
    d._paso(1, False)
    assert [v for _, v in llamadas][-1] == 6600.0
    d.destroy()


def test_escribir_un_numero_con_coma(raiz):
    d, llamadas = deslizador(raiz)
    d.texto.set("1,9")
    d._desde_texto()
    assert llamadas == [("gamma", 1.9)] and d.texto.get() == "1,90"
    d.texto.set("abc")
    d._desde_texto()
    assert len(llamadas) == 1 and d.texto.get() == "1,90"  # no es un número: se queda como estaba
    d.texto.set("99")
    d._desde_texto()
    assert llamadas[-1] == ("gamma", 4.0)  # se limita al rango
    d.destroy()


def test_enter_con_el_mismo_valor_no_llama(raiz):
    d, llamadas = deslizador(raiz)
    d.texto.set("1,7")
    d._desde_texto()
    assert llamadas == []
    d.destroy()


def test_doble_clic_vuelve_al_neutro(raiz):
    d, llamadas = deslizador(raiz)
    d._al_doble_clic(evento())
    assert llamadas[-1] == ("gamma", 1.0) and d.valor == 1.0
    d.destroy()


def test_el_tope_coloca_el_deslizador_en_el_valor_devuelto(raiz):
    d, llamadas = deslizador(raiz, respuesta=lambda v: min(v, 2.2))
    d._pedir(3.5)
    assert llamadas == [("gamma", 3.5)] and d.valor == 2.2 and d.texto.get() == "2,20"
    d.destroy()


def test_arrastrar_y_arrastrar_con_mayus(raiz):
    d, llamadas = deslizador(raiz, valor=1.0)
    d._al_pulsar(evento(x=110))  # centro de la pista: neutro
    assert d.valor == pytest.approx(1.0, abs=0.01)
    d._al_arrastrar(evento(x=210))
    assert d.valor == 4.0
    d._al_soltar(evento())
    d.poner_valor(1.0)
    d._al_pulsar(evento(x=110))
    d._al_arrastrar(evento(x=160, state=panel.SHIFT))  # fija la referencia: sin cambio
    d._al_arrastrar(evento(x=210, state=panel.SHIFT))  # 0,25 de recorrido -> 0,025 de posición
    assert d.valor == pytest.approx(escala.posicion_a_valor("gamma", 0.525), abs=0.01)
    d._al_soltar(evento())
    d.destroy()


def test_modo_preciso_usa_pasos_finos_y_recentra(raiz):
    d, llamadas = deslizador(raiz)
    d.poner_preciso(True)
    d._al_rueda(evento(delta=120))
    assert llamadas[-1] == ("gamma", 1.71)  # paso fino aunque no se pulse Mayús
    # La pista cubre ±0,25 alrededor del valor: el centro del recorrido es el valor actual.
    assert d._posicion() == pytest.approx(0.5)
    d._al_pulsar(evento(x=210))
    d._al_soltar(evento())
    assert d.valor == pytest.approx(1.96, abs=0.01) and d._posicion() == pytest.approx(0.5)  # recentrado
    d.poner_preciso(False)
    assert d._posicion() == pytest.approx(escala.valor_a_posicion("gamma", d.valor))
    d.destroy()


def test_dibujar_no_falla_con_ningun_valor(raiz):
    for nombre, par in escala.PARAMETROS.items():
        d, _ = deslizador(raiz, nombre, par.neutro)
        for v in (par.minimo, par.maximo, par.neutro):
            d.poner_valor(v)
        d.poner_preciso(True)
        d.poner_valor(par.minimo)
        d.destroy()


def test_grafico_dibuja_una_curva_o_tres(raiz):
    g = GraficoCurva(raiz)
    base = len(g.find_all())
    g.dibujar(IDENTIDAD)
    assert len(g.find_all()) == base + 1  # una sola línea: los canales son iguales
    desigual = color.construir_rampa_segura(color.Ajuste(r=color.AjusteCanal(gamma=1.5)))
    g.dibujar(desigual)
    assert len(g.find_all()) == base + 3
    g.dibujar(None)
    assert len(g.find_all()) == base
    g.destroy()


# --- La ventana ------------------------------------------------------------------------------------------------
from dataclasses import dataclass  # noqa: E402

from vislumbra.estado import Estado  # noqa: E402
from vislumbra.panel import Panel  # noqa: E402
from vislumbra.perfiles import Configuracion, Perfil  # noqa: E402


@dataclass(frozen=True)
class Mon:
    numero: int
    clave: str
    principal: bool = False


MONS = [Mon(1, "m-1"), Mon(2, "m-2", True), Mon(3, "m-3")]


class ControladorFalso:
    def __init__(self):
        self.rampas = 0
        self.persistencias = 0
        self.ocultados = 0
        self.salidas = 0

    def rampas_cambiaron(self):
        self.rampas += 1

    def persistir(self):
        self.persistencias += 1

    def ocultar_panel(self):
        self.ocultados += 1

    def salir(self):
        self.salidas += 1


class Reloj:
    t = 1000.0

    def __call__(self):
        return self.t


def configuracion():
    c = Configuracion()
    c.guardar(Perfil("Oscuro", color.Ajuste.uniforme(0.0, 7.5, 1.7)))
    c.guardar(Perfil("Código", color.Ajuste.uniforme(-20.0, 0.0, 1.0, 6000.0)))
    return c


@pytest.fixture
def montaje(ventana):
    estado = Estado(configuracion(), MONS)
    ctl, reloj = ControladorFalso(), Reloj()
    p = Panel(ventana, estado, ctl, reloj)
    p.confirmar = lambda titulo, mensaje: True
    p.preguntar_texto = lambda titulo, mensaje, inicial: None
    p.preguntar_guardar = lambda: None
    return p, estado, ctl, reloj


def con_oscuro(p, estado):
    estado.cambiar_activo("Oscuro")
    p.refrescar()


def visible(widget):
    return widget.winfo_manager() != ""


def evento_con_widget(w):
    return SimpleNamespace(widget=w)


def test_el_panel_se_construye_con_tres_monitores_y_con_uno(montaje):
    p, estado, ctl, _ = montaje
    assert visible(p.marco_pestanas) and len(p.marco_pestanas.winfo_children()) == 3
    assert p.lbl_editando.cget("text") == "Editando «Normal»" and not visible(p.lbl_sin_guardar)
    assert p.var_activo.get() == "Normal" and list(p.combo_activo.cget("values")) == ["Normal", "Oscuro", "Código"]
    estado.actualizar_monitores(MONS[:1])
    p.refrescar()
    assert not visible(p.marco_pestanas)
    assert p.raiz.title() == "Vislumbra"


def test_normal_no_se_edita_y_sus_botones_estan_desactivados(montaje):
    p, *_ = montaje
    assert all(str(b.cget("state")) == "disabled" for b in p.btns.values())
    assert str(p.chk_vincular.cget("state")) == "disabled"


def test_mover_un_deslizador_desde_normal_crea_un_perfil_sin_guardar(montaje):
    p, estado, ctl, _ = montaje
    p.deslizadores["gamma"]._pedir(1.4)
    assert estado.activo == "Perfil 1" and ctl.rampas == 1
    assert p.lbl_editando.cget("text") == "Editando «Perfil 1»" and visible(p.lbl_sin_guardar)
    assert "Perfil 1" in list(p.combo_activo.cget("values")) and p.var_activo.get() == "Perfil 1"
    assert "Normal" in p.lbl_aviso.cget("text") and p.deslizadores["gamma"].texto.get() == "1,40"
    assert str(p.btns["guardar"].cget("state")) == "normal" and str(p.btns["borrar"].cget("state")) == "normal"
    assert "Perfil 1" in p.lbl_resumen.cget("text")


def test_el_campo_numerico_la_rueda_y_el_doble_clic_llegan_al_estado(montaje):
    p, estado, ctl, _ = montaje
    con_oscuro(p, estado)
    d = p.deslizadores["gamma"]
    d.texto.set("2,0")
    d._desde_texto()
    assert estado.valor("gamma") == 2.0
    d._al_rueda(evento(delta=120))
    assert estado.valor("gamma") == 2.05
    d._al_doble_clic(evento())
    assert estado.valor("gamma") == 1.0 and ctl.rampas == 3


def test_el_tope_se_muestra_y_deja_el_deslizador_donde_quedo(montaje):
    p, estado, *_ = montaje
    con_oscuro(p, estado)
    p.deslizadores["temperatura"]._pedir(3300.0)
    p.deslizadores["brillo"]._pedir(-45.0)
    assert "Tope" in p.lbl_aviso.cget("text") and "Windows" in p.lbl_aviso.cget("text")
    assert -45.0 < p.deslizadores["brillo"].valor < 0.0 and p.deslizadores["brillo"].valor == estado.valor("brillo")


def test_cambiar_de_perfil_activo_con_las_flechas_y_el_desplegable(montaje):
    p, estado, ctl, _ = montaje
    p._cambiar_activo(+1)
    assert estado.activo == "Oscuro" and p.deslizadores["gamma"].valor == 1.7 and ctl.persistencias == 1 and ctl.rampas == 1
    p._elegir_activo("Código")
    assert estado.activo == "Código" and p.deslizadores["temperatura"].valor == 6000.0 and ctl.persistencias == 2


def test_las_pestanas_cambian_el_monitor_mirado_y_el_perfil_fijo(montaje):
    p, estado, ctl, _ = montaje
    con_oscuro(p, estado)
    p._mirar(3)
    assert estado.mirado == 3 and p.lbl_monitor.cget("text") == "Monitor 3"
    p.var_asignacion.set("fijo")
    p.var_fijo.set("Código")
    p._asignacion_cambiada()
    assert estado.asignacion("m-3") == "Código" and p.lbl_editando.cget("text") == "Editando «Código»"
    assert "«Código» en el 3" in p.lbl_resumen.cget("text") and ctl.persistencias == 1
    p.var_asignacion.set("activo")
    p._asignacion_cambiada()
    assert estado.asignacion("m-3") is None


def test_guardar_guardar_como_renombrar_y_borrar(montaje):
    p, estado, ctl, _ = montaje
    con_oscuro(p, estado)
    p.deslizadores["gamma"]._pedir(2.0)
    assert visible(p.lbl_sin_guardar)
    p._guardar()
    assert not visible(p.lbl_sin_guardar) and estado.conf.obtener("Oscuro").ajuste.r.gamma == 2.0 and ctl.persistencias == 1
    p.deslizadores["gamma"]._pedir(2.5)
    p.preguntar_texto = lambda t, m, i: "Variante"
    p._guardar_como()
    assert estado.activo == "Variante" and estado.conf.existe("Variante") and estado.conf.obtener("Oscuro").ajuste.r.gamma == 2.0
    p.preguntar_texto = lambda t, m, i: "Noche"
    p._renombrar()
    assert estado.activo == "Noche" and p.lbl_editando.cget("text") == "Editando «Noche»"
    p.confirmar = lambda t, m: False
    p._borrar()
    assert estado.conf.existe("Noche")
    p.confirmar = lambda t, m: True
    p._borrar()
    assert not estado.conf.existe("Noche") and estado.activo == "Normal"


def test_los_nombres_no_validos_se_muestran_como_error(montaje):
    p, estado, ctl, _ = montaje
    con_oscuro(p, estado)
    p.deslizadores["gamma"]._pedir(2.0)
    p.preguntar_texto = lambda t, m, i: "Código"  # ya existe
    p._guardar_como()
    assert "ya existe" in p.lbl_aviso.cget("text").lower() and estado.activo == "Oscuro" and ctl.persistencias == 0
    p.preguntar_texto = lambda t, m, i: None  # cancelar el diálogo
    p._renombrar()
    assert estado.activo == "Oscuro"


def test_vincular_con_canales_distintos_pide_confirmacion(montaje):
    p, estado, *_ = montaje
    con_oscuro(p, estado)
    p.var_vinculado.set(False)
    p._vincular_cambiado()
    assert not estado.perfil_editado().vinculado and all(visible(b) for b in p.btn_canal.values())
    p._elegir_canal("b")
    p.deslizadores["gamma"]._pedir(1.2)
    assert p.deslizadores["gamma"].valor == 1.2 and estado.canales_distintos()
    p.var_vinculado.set(True)
    p.confirmar = lambda t, m: False  # el usuario dice que no
    p._vincular_cambiado()
    assert not estado.perfil_editado().vinculado and not p.var_vinculado.get()
    p.var_vinculado.set(True)
    p.confirmar = lambda t, m: True
    p._vincular_cambiado()
    assert estado.perfil_editado().vinculado and not visible(p.btn_canal["r"])


def test_ab_activo_y_espacio(montaje):
    p, estado, ctl, _ = montaje
    con_oscuro(p, estado)
    p.var_ab.set(True)
    p._alternar_ab()
    assert estado.ab and set(estado.rampas().values()) == {None}
    p._tecla_espacio(evento_con_widget(p.raiz))
    assert not estado.ab
    p._tecla_espacio(evento_con_widget(p.deslizadores["gamma"].campo))  # escribiendo: la barra espaciadora no cuenta
    assert not estado.ab
    p.var_on.set(False)
    p._alternar_activo()
    assert not estado.activo_on and "desactivado" in p.lbl_aviso.cget("text")
    p._alternar_ab()  # con la app desactivada no hay nada que comparar
    assert not estado.ab


def test_ajuste_fuerte_banner_mantener_y_reversion(montaje):
    p, estado, ctl, reloj = montaje
    con_oscuro(p, estado)
    p.deslizadores["gamma"]._pedir(3.5)
    assert visible(p.marco_fuerte) and "10 s" in p.lbl_fuerte.cget("text")
    reloj.t += 4
    p._tick()
    assert "6 s" in p.lbl_fuerte.cget("text")
    p._mantener()
    assert not visible(p.marco_fuerte) and estado.valor("gamma") == 3.5
    p.deslizadores["gamma"]._pedir(1.7)
    p.deslizadores["gamma"]._pedir(3.6)
    reloj.t += 11
    antes = ctl.rampas
    p._tick()
    assert estado.valor("gamma") == 1.7 and not visible(p.marco_fuerte) and ctl.rampas == antes + 1
    assert "deshizo" in p.lbl_aviso.cget("text")


def test_restablecer_y_deshacer(montaje):
    p, estado, ctl, reloj = montaje
    con_oscuro(p, estado)
    p._restablecer()
    assert estado.valor("gamma") == 1.0 and visible(p.btn_deshacer)
    p._deshacer()
    assert estado.valor("gamma") == 1.7 and not visible(p.btn_deshacer)
    p._restablecer()
    reloj.t += 11
    p._tick()
    assert not visible(p.btn_deshacer)


def test_modo_preciso_llega_a_los_deslizadores(montaje):
    p, estado, *_ = montaje
    p.var_preciso.set(True)
    p._preciso_cambiado()
    assert estado.preciso and all(d.preciso for d in p.deslizadores.values())
    p.refrescar()
    assert all(d.preciso for d in p.deslizadores.values())


def test_los_mensajes_caducan(montaje):
    p, _, _, reloj = montaje
    p.mensaje("hola", segundos=5)
    assert p.lbl_aviso.cget("text") == "hola"
    reloj.t += 6
    p._tick()
    assert p.lbl_aviso.cget("text") == ""


def test_confirmar_salida(montaje):
    p, estado, ctl, _ = montaje
    assert p.confirmar_salida() is True  # nada sin guardar: no pregunta
    con_oscuro(p, estado)
    p.deslizadores["gamma"]._pedir(2.0)
    p.preguntar_guardar = lambda: None  # Cancelar
    assert p.confirmar_salida() is False and estado.sin_guardar()
    p.preguntar_guardar = lambda: True  # Guardar
    assert p.confirmar_salida() is True and not estado.sin_guardar() and ctl.persistencias == 1
    assert estado.conf.obtener("Oscuro").ajuste.r.gamma == 2.0
    p.deslizadores["gamma"]._pedir(3.0)
    p.preguntar_guardar = lambda: False  # Descartar
    assert p.confirmar_salida() is True and not estado.sin_guardar() and estado.conf.obtener("Oscuro").ajuste.r.gamma == 2.0


def test_ocultar_mostrar_y_cerrar_con_la_x(montaje):
    p, _, ctl, _ = montaje
    p.mostrar()
    assert p.visible
    p.ocultar()
    assert not p.visible
    p.raiz.tk.call(p.raiz.protocol("WM_DELETE_WINDOW"))  # lo que hace la ✕
    assert ctl.ocultados == 1


def test_la_curva_y_el_margen_se_actualizan(montaje):
    p, estado, *_ = montaje
    con_oscuro(p, estado)
    antes = p.lbl_margen.cget("text")
    assert "Margen de Windows" in antes and "de 50 %" in antes
    p.deslizadores["gamma"]._pedir(3.0)
    assert p.lbl_margen.cget("text") != antes
