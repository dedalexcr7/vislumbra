# SPDX-License-Identifier: GPL-3.0-or-later
"""Pruebas de ``vislumbra.tray``: solo las funciones puras y la construcción (sin mostrar el icono)."""

import pytest

from vislumbra import tray
from vislumbra.tray import Bandeja, InfoBandeja, ItemMenu

INFO = InfoBandeja(
    activo_on=True, perfil_activo="Oscuro", perfiles=("Normal", "Oscuro", "Código"), ab=False,
    grupos=(("Oscuro", (1, 2)), ("Código", (3,))),
)


def textos(menu):
    return [i.texto for i in menu if not i.separador]


def test_el_menu_tiene_las_entradas_del_plan():
    menu = tray.construir_menu(INFO)
    assert textos(menu) == [
        "Mostrar panel", "Activo", "Perfil activo", "Normal", "Oscuro", "Código", "Siguiente perfil", "Comparar (A/B)",
        "Salir (restaura la pantalla)",
    ]
    assert sum(i.separador for i in menu) == 2


def test_el_clic_izquierdo_es_mostrar_u_ocultar_y_solo_hay_un_predeterminado():
    menu = tray.construir_menu(INFO)
    assert [i.accion for i in menu if i.predeterminado] == [tray.MOSTRAR_OCULTAR]


def test_activo_y_ab_reflejan_el_estado():
    por_texto = {i.texto: i for i in tray.construir_menu(INFO)}
    assert por_texto["Activo"].marcado is True and por_texto["Comparar (A/B)"].marcado is False
    apagado = InfoBandeja(activo_on=False, ab=True, perfiles=("Normal",))
    por_texto = {i.texto: i for i in tray.construir_menu(apagado)}
    assert por_texto["Activo"].marcado is False and por_texto["Comparar (A/B)"].marcado is True


def test_la_lista_de_perfiles_es_plana_bajo_una_cabecera_gris():
    menu = tray.construir_menu(INFO)
    i = next(n for n, it in enumerate(menu) if it.texto == "Perfil activo")
    assert menu[i].habilitado is False and menu[i].accion is None and menu[i].hijos is None
    perfiles = menu[i + 1:i + 4]
    assert [h.texto for h in perfiles] == ["Normal", "Oscuro", "Código"]
    assert [h.marcado for h in perfiles] == [False, True, False]
    assert all(h.accion == tray.PERFIL and h.argumento == h.texto for h in perfiles)
    assert all(it.hijos is None for it in menu)  # sin submenús


def test_un_nombre_de_perfil_raro_se_envia_tal_cual():
    info = InfoBandeja(perfiles=("Normal", "Mi «perfil» & más"), perfil_activo="Normal")
    perfil = next(i for i in tray.construir_menu(info) if i.texto == "Mi «perfil» & más")
    assert perfil.argumento == "Mi «perfil» & más"


def test_texto_emergente_como_en_el_plan():
    assert tray.texto_emergente(INFO) == "Vislumbra · activo · Oscuro (1, 2) · Código (3)"
    assert tray.texto_emergente(InfoBandeja(activo_on=False)) == "Vislumbra · desactivado"
    assert tray.texto_emergente(InfoBandeja(ab=True, grupos=(("Normal", (1,)),))) == "Vislumbra · A/B: pantalla original · Normal (1)"


def test_texto_emergente_largo_se_recorta():
    info = InfoBandeja(grupos=tuple((f"Perfil con un nombre bastante largo {n}", (n,)) for n in range(1, 9)))
    texto = tray.texto_emergente(info)
    assert len(texto) <= tray.LIMITE_TEXTO_EMERGENTE and texto.endswith("…")


def test_cargar_icono_activo_e_inactivo():
    a, i = tray.cargar_icono(True), tray.cargar_icono(False)
    assert a.size == i.size == (64, 64) and a.mode == i.mode == "RGBA"
    assert a.tobytes() != i.tobytes()


def test_si_faltan_los_iconos_hay_uno_de_respaldo(monkeypatch, tmp_path):
    monkeypatch.setattr(tray, "ICONOS", tmp_path)
    assert tray.cargar_icono(True).size == (64, 64)


def test_la_bandeja_traduce_el_menu_y_envia_las_acciones():
    recibidas = []
    b = Bandeja(lambda accion, arg: recibidas.append((accion, arg)), lambda: INFO)
    items = [b._convertir(i) for i in tray.construir_menu(INFO)]
    assert len(items) == 11
    por_texto = {getattr(i, "text", None): i for i in items}
    por_texto["Siguiente perfil"](b.icono)  # un MenuItem se invoca con el icono
    por_texto["Activo"](b.icono)
    assert recibidas == [(tray.SIGUIENTE, None), (tray.ALTERNAR_ACTIVO, None)]
    assert por_texto["Perfil activo"].enabled is False  # cabecera de sección, no se puede pulsar
    por_texto["Código"](b.icono)
    assert recibidas[-1] == (tray.PERFIL, "Código")
    assert b.icono.title == "Vislumbra · activo · Oscuro (1, 2) · Código (3)"


def test_detener_y_avisar_sin_haber_iniciado_no_fallan():
    b = Bandeja(lambda *a: None, lambda: INFO)
    b.avisar("Título", "Mensaje")
    b.detener()
