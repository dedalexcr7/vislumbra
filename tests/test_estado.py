# SPDX-License-Identifier: GPL-3.0-or-later
"""Pruebas de ``vislumbra.estado`` (modelo del panel, sin Tk ni pantalla)."""

from dataclasses import dataclass

import pytest

from vislumbra import color
from vislumbra.color import Ajuste, AjusteCanal
from vislumbra.estado import SEGUNDOS_CONFIRMACION, Estado
from vislumbra.perfiles import NORMAL, Configuracion, ErrorPerfil, Perfil, PerfilNoEncontrado


@dataclass(frozen=True)
class Mon:
    numero: int
    clave: str
    principal: bool = False


MONS = [Mon(1, "m-1"), Mon(2, "m-2", True), Mon(3, "m-3")]


def configuracion():
    c = Configuracion()
    c.guardar(Perfil("Oscuro", Ajuste.uniforme(0.0, 7.5, 1.7)))
    c.guardar(Perfil("Código", Ajuste.uniforme(-20.0, 0.0, 1.0, 6000.0)))
    return c


@pytest.fixture
def e():
    return Estado(configuracion(), MONS)


def con_oscuro_activo():
    est = Estado(configuracion(), MONS)
    est.cambiar_activo("Oscuro")
    return est


# --- Monitor mirado y perfil editado --------------------------------------------------------------
def test_se_mira_el_monitor_principal_al_empezar(e):
    assert e.mirado == 2 and e.perfil_editado().es_normal


def test_el_perfil_editado_depende_del_monitor_mirado():
    est = con_oscuro_activo()
    est.fijar_monitor(3, "Código")
    est.mirar(1)
    assert est.perfil_editado().nombre == "Oscuro"
    est.mirar(3)
    assert est.perfil_editado().nombre == "Código"
    assert est.valor("brillo") == -20.0 and est.valor("temperatura") == 6000.0
    est.mirar(99)  # monitor inexistente: no cambia
    assert est.mirado == 3


def test_fijo_no_cambia_al_cambiar_el_activo():
    est = con_oscuro_activo()
    est.fijar_monitor(3, "Código")
    est.cambiar_activo("Normal")
    assert est.perfil_de_monitor(1).es_normal and est.perfil_de_monitor(3).nombre == "Código"
    est.fijar_monitor(3, None)
    assert est.perfil_de_monitor(3).es_normal


def test_pestanas_y_resumen():
    est = con_oscuro_activo()
    est.fijar_monitor(3, "Código")
    assert [(p.numero, p.perfil, p.fijo, p.principal) for p in est.pestanas()] == [
        (1, "Oscuro", False, False), (2, "Oscuro", False, True), (3, "Código", True, False)]
    assert est.resumen() == "«Oscuro» en los monitores 1 y 2 · «Código» en el 3"
    est.cambiar_activo("Normal")
    assert est.resumen() == "«Normal» en los monitores 1 y 2 · «Código» en el 3"
    assert Estado(configuracion(), MONS[:1]).resumen() == "«Normal» en el monitor 1"


def test_mover_activo_con_las_flechas_da_la_vuelta(e):
    assert [e.mover_activo(+1) for _ in range(4)] == ["Oscuro", "Código", NORMAL, "Oscuro"]
    assert e.mover_activo(-1) == NORMAL


# --- Rampas por monitor -------------------------------------------------------------------------------
def test_un_monitor_en_normal_no_recibe_rampa(e):
    assert e.rampas() == {1: None, 2: None, 3: None}


def test_editar_un_perfil_cambia_las_rampas_de_todos_los_monitores_que_lo_usan():
    est = con_oscuro_activo()
    est.fijar_monitor(3, "Código")
    antes = est.rampas()
    est.mirar(1)
    est.mover("gamma", 2.0)
    despues = est.rampas()
    assert despues[1] == despues[2] != antes[1]  # el 1 y el 2 usan «Oscuro»
    assert despues[3] == antes[3]  # el 3 tiene su perfil fijo
    assert despues[1] == color.construir_rampa_segura(Ajuste.uniforme(0.0, 7.5, 2.0))


def test_editar_el_perfil_fijo_de_un_monitor_no_toca_a_los_demas():
    est = con_oscuro_activo()
    est.fijar_monitor(3, "Código")
    est.mirar(3)
    antes = est.rampas()
    est.mover("brillo", -30.0)
    despues = est.rampas()
    assert despues[3] != antes[3] and despues[1] == antes[1] and despues[2] == antes[2]


def test_ab_y_activo_devuelven_las_rampas_originales():
    est = con_oscuro_activo()
    assert all(r is not None for r in est.rampas().values())
    assert est.alternar_ab() is True
    assert est.rampas() == {1: None, 2: None, 3: None}
    est.alternar_ab()
    assert all(r is not None for r in est.rampas().values())
    est.poner_activo(False)
    assert est.rampas() == {1: None, 2: None, 3: None}
    est.poner_activo(True)
    assert all(r is not None for r in est.rampas().values())


# --- Editar Normal ----------------------------------------------------------------------------------------
def test_mover_un_deslizador_con_normal_crea_perfil_n_y_lo_asigna(e):
    r = e.mover("gamma", 1.4)
    assert r.perfil_creado == "Perfil 1" and r.valor == 1.4
    assert e.activo == "Perfil 1" and e.perfil_editado().nombre == "Perfil 1"
    assert e.sin_guardar("Perfil 1") and e.nombres()[-1] == "Perfil 1"
    assert all(e.perfil_de_monitor(n).nombre == "Perfil 1" for n in (1, 2, 3))  # seguían al activo
    assert e.conf.nombres() == [NORMAL, "Oscuro", "Código"]  # nada guardado todavía
    assert e.rampas()[1] is not None


def test_si_el_monitor_era_fijo_a_normal_solo_el_pasa_a_perfil_n():
    est = con_oscuro_activo()
    est.fijar_monitor(3, "Normal")
    est.mirar(3)
    est.mover("brillo", 10.0)
    assert est.perfil_de_monitor(3).nombre == "Perfil 1" and est.activo == "Oscuro"
    assert est.asignacion("m-3") == "Perfil 1"


def test_mover_a_neutro_con_normal_no_crea_nada(e):
    r = e.mover("gamma", 1.0)
    assert r.perfil_creado is None and e.perfil_editado().es_normal and not e.sin_guardar()


def test_perfil_n_elige_un_nombre_libre(e):
    e.conf.guardar(Perfil("Perfil 1", Ajuste()))
    assert e.mover("brillo", 5.0).perfil_creado == "Perfil 2"


# --- Sin guardar, guardar, guardar como, descartar ---------------------------------------------------------
def test_los_cambios_quedan_sin_guardar_hasta_guardar():
    est = con_oscuro_activo()
    est.mover("gamma", 2.0)
    assert est.sin_guardar("Oscuro") and est.sin_guardar() and est.nombres_sin_guardar() == ["Oscuro"]
    assert est.conf.obtener("Oscuro").ajuste.r.gamma == 1.7  # lo guardado no cambió
    assert est.guardar() == "Oscuro"
    assert not est.sin_guardar() and est.conf.obtener("Oscuro").ajuste.r.gamma == 2.0


def test_volver_al_valor_guardado_quita_el_sin_guardar():
    est = con_oscuro_activo()
    est.mover("gamma", 2.0)
    est.mover("gamma", 1.7)
    assert not est.sin_guardar()


def test_descartar_devuelve_lo_guardado():
    est = con_oscuro_activo()
    est.mover("gamma", 2.0)
    est.descartar()
    assert not est.sin_guardar() and est.valor("gamma") == 1.7


def test_descartar_un_perfil_nuevo_lo_elimina_y_vuelve_a_normal(e):
    e.mover("gamma", 1.4)
    e.descartar()
    assert e.activo == NORMAL and e.nombres() == [NORMAL, "Oscuro", "Código"] and not e.sin_guardar()


def test_guardar_perfil_nuevo_lo_incorpora_a_la_configuracion(e):
    e.mover("gamma", 1.4)
    e.guardar()
    assert e.conf.existe("Perfil 1") and not e.sin_guardar()
    assert e.conf.obtener("Perfil 1").ajuste.r.gamma == 1.4


def test_guardar_todos_guarda_todos_los_perfiles_con_cambios():
    est = con_oscuro_activo()
    est.mover("gamma", 2.0)
    est.fijar_monitor(3, "Código")
    est.mirar(3)
    est.mover("brillo", -30.0)
    assert sorted(est.nombres_sin_guardar()) == ["Código", "Oscuro"]
    assert sorted(est.guardar_todos()) == ["Código", "Oscuro"]
    assert not est.sin_guardar() and est.conf.obtener("Oscuro").ajuste.r.gamma == 2.0
    assert est.conf.obtener("Código").ajuste.r.brillo == -30.0


def test_guardar_todos_incluye_los_perfiles_nuevos(e):
    e.mover("gamma", 1.4)
    assert e.guardar_todos() == ["Perfil 1"] and e.conf.existe("Perfil 1") and e.conf_persistible().perfil_activo == "Perfil 1"


def test_guardar_como_crea_otro_y_deja_el_original_en_lo_guardado():
    est = con_oscuro_activo()
    est.mover("gamma", 2.0)
    assert est.guardar_como("Variante") == "Variante"
    assert est.conf.obtener("Variante").ajuste.r.gamma == 2.0
    assert est.conf.obtener("Oscuro").ajuste.r.gamma == 1.7 and not est.sin_guardar()
    assert est.activo == "Variante"  # el monitor mirado seguía al activo


def test_guardar_como_desde_un_monitor_fijo_solo_cambia_ese_monitor():
    est = con_oscuro_activo()
    est.fijar_monitor(3, "Código")
    est.mirar(3)
    est.mover("brillo", -30.0)
    est.guardar_como("Código 2")
    assert est.asignacion("m-3") == "Código 2" and est.activo == "Oscuro"
    assert est.conf.obtener("Código").ajuste.r.brillo == -20.0


def test_guardar_como_desde_un_perfil_nuevo_no_deja_el_nuevo(e):
    e.mover("gamma", 1.4)
    e.guardar_como("Mío")
    assert e.nombres() == [NORMAL, "Oscuro", "Código", "Mío"] and e.activo == "Mío" and not e.sin_guardar()


@pytest.mark.parametrize("nombre", ["Oscuro", "oscuro", "", "Normal", "x" * 50])
def test_guardar_como_con_nombre_no_valido(nombre):
    est = con_oscuro_activo()
    est.mover("gamma", 2.0)
    with pytest.raises(ErrorPerfil):
        est.guardar_como(nombre)
    assert est.sin_guardar("Oscuro")


def test_no_se_puede_guardar_renombrar_ni_borrar_normal(e):
    for operacion in (e.guardar, e.borrar, lambda: e.renombrar("X")):
        with pytest.raises(ErrorPerfil, match="fijo"):
            operacion()


def test_renombrar_actualiza_activo_fijos_y_cambios_sin_guardar():
    est = con_oscuro_activo()
    est.fijar_monitor(3, "Oscuro")
    est.mover("gamma", 2.0)
    assert est.renombrar("Noche") == "Noche"
    assert est.activo == "Noche" and est.asignacion("m-3") == "Noche"
    assert est.sin_guardar("Noche") and est.valor("gamma") == 2.0
    assert "Oscuro" not in est.nombres() and est.conf.obtener("Noche").ajuste.r.gamma == 1.7


def test_renombrar_un_perfil_nuevo(e):
    e.mover("gamma", 1.4)
    e.renombrar("Cine")
    assert e.activo == "Cine" and e.sin_guardar("Cine") and e.nombres()[-1] == "Cine"
    with pytest.raises(ErrorPerfil, match="ya existe"):
        e.renombrar("código")


def test_borrar_pasa_los_fijos_a_activo_y_el_activo_a_normal():
    est = con_oscuro_activo()
    est.fijar_monitor(3, "Oscuro")
    assert est.borrar() == "Oscuro"
    assert est.activo == NORMAL and est.asignacion("m-3") is None
    assert est.conf.nombres() == [NORMAL, "Código"]


def test_conf_persistible_no_incluye_lo_que_no_esta_guardado(e):
    e.mover("gamma", 1.4)  # «Perfil 1» activo, sin guardar
    e.fijar_monitor(3, "Código")
    c = e.conf_persistible()
    assert c.perfil_activo == NORMAL and c.nombres() == [NORMAL, "Oscuro", "Código"]
    assert c.monitores["m-3"] == "Código"
    e.guardar()
    assert e.conf_persistible().perfil_activo == "Perfil 1"


# --- Vincular canales ----------------------------------------------------------------------------------------
def test_desvincular_permite_editar_un_canal_y_vincular_usa_el_visible():
    est = con_oscuro_activo()
    assert est.vincular(False) is True and not est.perfil_editado().vinculado
    est.poner_canal("b")
    est.mover("gamma", 1.2)
    a = est.perfil_editado().ajuste
    assert (a.r.gamma, a.g.gamma, a.b.gamma) == (1.7, 1.7, 1.2) and est.canales_distintos()
    assert est.valor("gamma") == 1.2  # canal visible
    est.poner_canal("r")
    assert est.valor("gamma") == 1.7
    est.poner_canal("b")
    assert est.vincular(True) is True
    a = est.perfil_editado().ajuste
    assert a.r == a.g == a.b and a.r.gamma == 1.2 and not est.canales_distintos()


def test_con_canales_vinculados_un_cambio_va_a_los_tres():
    est = con_oscuro_activo()
    est.mover("contraste", 12.0)
    a = est.perfil_editado().ajuste
    assert a.r == a.g == a.b and a.r.contraste == 12.0


def test_la_temperatura_es_global_aunque_los_canales_esten_desvinculados():
    est = con_oscuro_activo()
    est.vincular(False)
    est.poner_canal("g")
    est.mover("temperatura", 5000.0)
    assert est.perfil_editado().ajuste.temperatura == 5000.0 and est.valor("temperatura") == 5000.0


def test_vincular_no_hace_nada_en_normal_ni_si_ya_esta_igual(e):
    assert e.vincular(False) is False and e.perfil_editado().es_normal
    est = con_oscuro_activo()
    assert est.vincular(True) is False


# --- Tope ------------------------------------------------------------------------------------------------------
def test_un_movimiento_invalido_se_detiene_en_el_ultimo_valor_valido():
    est = Estado(configuracion(), MONS)
    est.cambiar_activo("Oscuro")
    est.mover("temperatura", 3300.0)  # 31 652 de desviación: válido, pero casi en el límite de Windows
    r = est.mover("brillo", -45.0)
    assert r.tope and "Windows" in r.tope
    assert -45.0 < r.valor < 0.0
    assert est.valor("brillo") == r.valor
    color.construir_rampa_segura(est.perfil_editado().ajuste)  # lo que quedó se puede aplicar
    # Un paso más allá del valor del tope también se rechaza
    mas = est.mover("brillo", r.valor - 1.0)
    assert mas.valor == pytest.approx(r.valor, abs=0.11)


def test_un_movimiento_valido_no_tiene_tope(e):
    r = e.mover("gamma", 2.5)
    assert r.tope is None and r.valor == 2.5


def test_los_valores_se_limitan_al_rango(e):
    assert e.mover("gamma", 99.0).valor <= 4.0
    assert e.mover("brillo", -5000.0).valor >= -100.0


def test_el_tope_no_crea_un_perfil_si_no_se_pudo_mover(e):
    # Desde Normal, un valor imposible se queda en el neutro y no crea nada.
    e.mover("brillo", 0.0)
    assert not e.sin_guardar() and e.nombres() == [NORMAL, "Oscuro", "Código"]


# --- Ajuste fuerte ------------------------------------------------------------------------------------------------
def test_un_ajuste_fuerte_se_deshace_a_los_10_s_si_no_se_confirma():
    est = con_oscuro_activo()
    est.mover("gamma", 2.5, ahora=0.0)
    assert est.pendiente is None  # 33 %: no es fuerte
    est.mover("gamma", 3.5, ahora=100.0)  # ~43 %
    assert est.pendiente is not None and est.segundos_restantes(104.0) == pytest.approx(6.0)
    assert est.vencer(109.0) is False
    assert est.vencer(100.0 + SEGUNDOS_CONFIRMACION) is True
    assert est.valor("gamma") == 2.5 and est.pendiente is None and "deshizo" in est.aviso


def test_mantener_confirma_el_ajuste_fuerte():
    est = con_oscuro_activo()
    est.mover("gamma", 3.5, ahora=0.0)
    est.mantener()
    assert est.pendiente is None and est.vencer(1000.0) is False and est.valor("gamma") == 3.5


def test_seguir_moviendo_con_ajuste_fuerte_renueva_el_plazo_sin_perder_el_original():
    est = con_oscuro_activo()
    est.mover("gamma", 3.5, ahora=0.0)
    est.mover("gamma", 3.6, ahora=8.0)
    assert est.vencer(12.0) is False
    assert est.vencer(18.0) is True and est.valor("gamma") == 1.7


def test_volver_a_un_valor_suave_cancela_la_confirmacion():
    est = con_oscuro_activo()
    est.mover("gamma", 3.5, ahora=0.0)
    est.mover("gamma", 2.0, ahora=1.0)
    assert est.pendiente is None


def test_ajuste_fuerte_desde_normal_vuelve_al_perfil_neutro_nuevo(e):
    e.mover("gamma", 3.6, ahora=0.0)
    assert e.pendiente is not None
    e.vencer(10.0)
    assert e.valor("gamma") == 1.0


def test_guardar_confirma_el_ajuste_fuerte():
    est = con_oscuro_activo()
    est.mover("gamma", 3.5, ahora=0.0)
    est.guardar()
    assert est.pendiente is None and est.conf.obtener("Oscuro").ajuste.r.gamma == 3.5


# --- Restablecer y deshacer -----------------------------------------------------------------------------------------
def test_restablecer_pone_neutro_y_se_puede_deshacer_durante_10_s():
    est = con_oscuro_activo()
    assert est.restablecer(ahora=0.0) is True
    assert est.valor("gamma") == 1.0 and est.valor("contraste") == 0.0 and est.sin_guardar("Oscuro")
    assert est.puede_deshacer(5.0) and not est.puede_deshacer(10.0)
    assert est.deshacer(5.0) is True
    assert est.valor("gamma") == 1.7 and not est.sin_guardar()
    assert est.deshacer(6.0) is False


def test_deshacer_fuera_de_plazo_no_hace_nada():
    est = con_oscuro_activo()
    est.restablecer(ahora=0.0)
    assert est.deshacer(11.0) is False and est.valor("gamma") == 1.0


def test_restablecer_en_normal_no_hace_nada(e):
    assert e.restablecer() is False


# --- Modo preciso y monitores nuevos -------------------------------------------------------------------------------------
def test_el_modo_preciso_es_un_interruptor_que_no_cambia_los_valores(e):
    e.mover("gamma", 1.7)
    antes = e.valores()
    e.preciso = True
    assert e.valores() == antes and e.preciso


def test_un_monitor_nuevo_sigue_al_perfil_activo():
    est = con_oscuro_activo()
    est.actualizar_monitores(MONS + [Mon(4, "m-4")])
    assert est.perfil_de_monitor(4).nombre == "Oscuro" and est.rampas()[4] is not None
    est.actualizar_monitores([MONS[0]])
    assert est.mirado == 1  # el mirado desapareció


def test_valores_devuelve_los_cuatro_parametros():
    est = con_oscuro_activo()
    assert est.valores() == {"brillo": 0.0, "contraste": 7.5, "gamma": 1.7, "temperatura": 6500.0}


# --- Perfil automático por programa --------------------------------------------------------------------------------
def con_programas():
    est = con_oscuro_activo()
    est.asociar_programa("juego.exe", "Código")
    est.asociar_programa(r"D:\Games\Otro.exe", "Normal")
    return est


def test_asociar_y_quitar_programas():
    est = con_programas()
    assert est.exes_vigilados() == {"juego.exe", "otro.exe"}
    assert est.perfil_de_programa("juego.exe") == "Código" and est.perfil_de_programa("nada.exe") is None
    est.quitar_programa("JUEGO")
    assert est.exes_vigilados() == {"otro.exe"}
    with pytest.raises(ErrorPerfil):
        est.asociar_programa("x.bat", "Oscuro")
    with pytest.raises(PerfilNoEncontrado):
        est.asociar_programa("x.exe", "Nada")


def test_al_abrirse_el_programa_se_activa_su_perfil_y_al_cerrarse_vuelve_el_de_antes():
    est = con_programas()
    assert est.set_automatico("Código") is True and est.activo == "Código" and est.automatico
    assert est.perfil_de_monitor(1).nombre == "Código"
    assert est.set_automatico(None) is True and est.activo == "Oscuro" and not est.automatico
    assert est.set_automatico(None) is False  # sin programa y sin automático: nada


def test_el_perfil_automatico_no_se_guarda_como_el_activo_del_usuario():
    est = con_programas()
    est.set_automatico("Código")
    assert est.conf_persistible().perfil_activo == "Oscuro"  # si el PC se apaga en mitad del juego
    assert [a.exe for a in est.conf_persistible().programas] == ["juego.exe", "otro.exe"]


def test_si_el_usuario_cambia_de_perfil_durante_el_programa_se_respeta_al_cerrarlo():
    est = con_programas()
    est.set_automatico("Código")
    est.cambiar_activo("Normal")  # a mano
    assert est.conf_persistible().perfil_activo == "Normal"
    assert est.set_automatico(None) is False and est.activo == "Normal" and not est.automatico


def test_dos_programas_a_la_vez_el_segundo_manda_y_al_cerrarlo_vuelve_el_primero():
    est = con_programas()
    est.set_automatico("Código")
    est.set_automatico("Normal")  # se abrió otro programa asociado a Normal
    assert est.activo == "Normal"
    est.set_automatico("Código")  # se cerró el segundo: manda el primero otra vez
    assert est.activo == "Código"
    est.set_automatico(None)
    assert est.activo == "Oscuro"  # el de antes de todo


def test_cambio_a_mano_y_luego_otro_programa_toma_la_eleccion_manual_como_la_de_antes():
    est = con_programas()
    est.set_automatico("Código")
    est.cambiar_activo("Oscuro")
    est.set_automatico("Normal")
    est.set_automatico(None)
    assert est.activo == "Oscuro"


def test_con_perfil_inexistente_no_hace_nada():
    est = con_oscuro_activo()
    assert est.set_automatico("NoExiste") is False and not est.automatico and est.activo == "Oscuro"


def test_si_el_perfil_de_antes_se_borro_mientras_tanto_se_vuelve_a_normal():
    est = con_programas()
    est.set_automatico("Código")
    est.cambiar_activo("Oscuro")
    est.borrar()  # se borra «Oscuro» (el de antes) estando editado
    est.cambiar_activo("Código")
    est._auto.aplicado = "Código"
    est.set_automatico(None)
    assert est.activo == "Normal"


def test_renombrar_y_borrar_un_perfil_arregla_los_programas_y_el_automatico():
    est = con_programas()
    est.set_automatico("Código")
    est.mirar(2)
    est.renombrar("Programar")  # «Código» es el que se ve (activo automático)
    assert est.activo == "Programar" and est.perfil_de_programa("juego.exe") == "Programar"
    est.set_automatico(None)
    assert est.activo == "Oscuro"
    est.cambiar_activo("Programar")
    est.borrar()
    assert est.perfil_de_programa("juego.exe") is None and est.exes_vigilados() == {"otro.exe"}


def test_los_programas_con_perfiles_sin_guardar_no_se_persisten(e):
    e.mover("gamma", 1.4)  # «Perfil 1», sin guardar
    e.asociar_programa("juego.exe", "Perfil 1")
    assert e.conf_persistible().programas == []
    e.guardar()
    assert [a.exe for a in e.conf_persistible().programas] == ["juego.exe"]
