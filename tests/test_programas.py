# SPDX-License-Identifier: GPL-3.0-or-later
"""Pruebas de ``procesos`` (lectura real, solo lectura) y ``programas`` (lógica pura)."""

import os
import sys

import pytest

from vislumbra import procesos, programas
from vislumbra.programas import Asociacion, ErrorPrograma, SeguimientoProgramas, buscar, normalizar_exe


# --- procesos (solo lee la lista de procesos) ------------------------------------------------------------
def test_la_lista_incluye_este_mismo_proceso():
    nombres = procesos.nombres_en_ejecucion()
    assert os.path.basename(sys.executable).lower() in nombres
    assert all(n == n.lower() for n in nombres) and len(nombres) > 10


def test_la_lista_para_elegir_no_trae_procesos_del_sistema_ni_repetidos():
    lista = procesos.nombres_ordenados()
    assert lista == sorted(set(lista)) and all(n.endswith(".exe") for n in lista)
    assert "svchost.exe" not in lista and "system" not in lista


# --- normalizar_exe --------------------------------------------------------------------------------------------
@pytest.mark.parametrize("texto, esperado", [
    ("juego.exe", "juego.exe"), ("Juego.EXE", "juego.exe"), ("  juego  ", "juego.exe"),
    (r"C:\Juegos\Mi Juego\Juego.exe", "juego.exe"), ('"D:/Games/otro juego.exe"', "otro juego.exe"),
    ("Mi.Juego.exe", "mi.juego.exe"),
])
def test_normalizar_exe_deja_solo_el_nombre_en_minusculas(texto, esperado):
    assert normalizar_exe(texto) == esperado


def test_normalizar_exe_no_deja_pasar_la_carpeta():
    """Privacidad: aunque se pegue una ruta con el usuario, solo se guarda el nombre del programa."""
    assert "\\" not in normalizar_exe(r"C:\Users\alguien\Juegos\juego.exe")
    assert "alguien" not in normalizar_exe(r"C:\Users\alguien\Juegos\juego.exe")


@pytest.mark.parametrize("texto", ["", "   ", ".exe", "juego.bat", "juego.txt", 'a"b.exe', "a|b.exe", "x" * 70 + ".exe", "con\nsalto.exe", "C:\\carpeta\\"])
def test_normalizar_exe_rechaza_lo_que_no_es_un_programa(texto):
    with pytest.raises(ErrorPrograma):
        normalizar_exe(texto)


def test_buscar():
    lista = [Asociacion("a.exe", "Oscuro"), Asociacion("b.exe", "Código")]
    assert buscar(lista, "b.exe").perfil == "Código" and buscar(lista, "c.exe") is None


# --- SeguimientoProgramas ----------------------------------------------------------------------------------------
def test_sin_programas_abiertos_no_manda_ninguno():
    s = SeguimientoProgramas()
    assert s.actualizar([]) is None and s.actualizar({"a.exe"}) == "a.exe" and s.actualizar([]) is None


def test_manda_el_ultimo_que_se_abrio_y_al_cerrarlo_vuelve_el_anterior():
    s = SeguimientoProgramas()
    assert s.actualizar({"a.exe"}) == "a.exe"
    assert s.actualizar({"a.exe", "b.exe"}) == "b.exe"  # se abrió b después
    assert s.actualizar({"a.exe", "b.exe"}) == "b.exe"  # sigue mandando b
    assert s.actualizar({"a.exe"}) == "a.exe"  # se cerró b
    assert s.actualizar(set()) is None


def test_reabrir_un_programa_lo_pone_el_ultimo():
    s = SeguimientoProgramas()
    s.actualizar({"a.exe", "b.exe"})
    s.actualizar({"b.exe"})
    assert s.actualizar({"a.exe", "b.exe"}) == "a.exe"  # a se abrió de nuevo después


def test_varios_a_la_vez_en_el_primer_muestreo_es_estable():
    assert SeguimientoProgramas().actualizar({"b.exe", "a.exe"}) == SeguimientoProgramas().actualizar({"a.exe", "b.exe"})
