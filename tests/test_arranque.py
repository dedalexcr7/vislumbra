# SPDX-License-Identifier: GPL-3.0-or-later
"""Pruebas de ``vislumbra.arranque``. Siempre en una carpeta temporal: nunca tocan la carpeta Inicio real."""

import sys
from pathlib import Path

import pytest

from vislumbra import arranque


def test_la_carpeta_por_defecto_es_la_de_inicio_del_usuario(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    c = arranque.carpeta_inicio()
    assert c == tmp_path / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    assert arranque.ruta_acceso() == c / "Vislumbra.lnk"
    assert not c.exists()  # consultar no crea nada


def test_sin_acceso_directo_no_esta_activado(tmp_path):
    assert arranque.esta_activado(tmp_path) is False
    assert arranque.leer_destino(tmp_path) is None
    assert arranque.apunta_a_algo_que_existe(tmp_path) is False
    arranque.desactivar(tmp_path)  # borrar lo que no existe no falla


def test_activar_crea_el_acceso_directo_con_el_destino_y_desactivar_lo_borra(tmp_path):
    carpeta = tmp_path / "Inicio" / "Startup"  # no existe: se crea
    destino = (sys.executable, "-m vislumbra --oculto", str(tmp_path))
    ruta = arranque.activar(carpeta, destino)
    assert ruta == carpeta / "Vislumbra.lnk" and arranque.esta_activado(carpeta)
    programa, argumentos, trabajo = arranque.leer_destino(carpeta)
    assert Path(programa) == Path(sys.executable) and argumentos == "-m vislumbra --oculto"
    assert Path(trabajo) == tmp_path
    assert arranque.apunta_a_algo_que_existe(carpeta)
    arranque.desactivar(carpeta)
    assert not arranque.esta_activado(carpeta) and list(carpeta.iterdir()) == []


def test_activar_dos_veces_reemplaza_el_acceso(tmp_path):
    arranque.activar(tmp_path, (sys.executable, "uno", str(tmp_path)))
    arranque.activar(tmp_path, (sys.executable, "dos", str(tmp_path)))
    assert arranque.leer_destino(tmp_path)[1] == "dos" and len(list(tmp_path.iterdir())) == 1


def test_un_acceso_que_apunta_a_un_programa_que_ya_no_existe_se_detecta(tmp_path):
    arranque.activar(tmp_path, (str(tmp_path / "no_existe.exe"), "", str(tmp_path)))
    assert arranque.esta_activado(tmp_path) and not arranque.apunta_a_algo_que_existe(tmp_path)


def test_rutas_con_espacios_y_acentos(tmp_path):
    carpeta = tmp_path / "Menú Inicio ñ"
    trabajo = tmp_path / "Mi proyecto"
    trabajo.mkdir()
    arranque.activar(carpeta, (sys.executable, "-m vislumbra --oculto", str(trabajo)))
    assert Path(arranque.leer_destino(carpeta)[2]) == trabajo


def test_si_powershell_falla_se_explica_y_no_queda_nada(tmp_path, monkeypatch):
    def falla(*a, **k):
        raise FileNotFoundError("powershell")

    monkeypatch.setattr(arranque.subprocess, "run", falla)
    with pytest.raises(arranque.ErrorArranque, match="PowerShell"):
        arranque.activar(tmp_path, (sys.executable, "", str(tmp_path)))
    assert not arranque.esta_activado(tmp_path)


def test_el_destino_por_defecto_es_pythonw_del_entorno_con_oculto():
    programa, argumentos, trabajo = arranque.destino_por_defecto()
    assert argumentos == "-m vislumbra --oculto" and Path(trabajo, "vislumbra", "__main__.py").exists()
    assert Path(programa).name.lower() in ("pythonw.exe", "python.exe")


def test_empaquetada_como_exe_lanza_el_propio_ejecutable(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    programa, argumentos, trabajo = arranque.destino_por_defecto()
    assert Path(programa) == Path(sys.executable) and argumentos == "--oculto"
