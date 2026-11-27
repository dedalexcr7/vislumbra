# SPDX-License-Identifier: GPL-3.0-or-later
"""Pruebas del registro de errores sin consola. Todo va a carpetas temporales, nunca a ``%APPDATA%`` real."""

import io
import sys

import pytest

from vislumbra import __main__ as cli
from vislumbra import bitacora


@pytest.fixture
def sin_consola(monkeypatch, tmp_path):
    """%APPDATA% apunta a una carpeta temporal; devuelve la ruta del registro y una función que quita stdout y stderr.

    Quitarlos tiene que hacerse dentro del test: pytest reactiva su captura justo antes y pisaría los ``None``.
    """
    monkeypatch.setenv("APPDATA", str(tmp_path))

    def quitar_flujos():
        monkeypatch.setattr(sys, "stdout", None)
        monkeypatch.setattr(sys, "stderr", None)

    return tmp_path / "Vislumbra" / bitacora.NOMBRE_REGISTRO, quitar_flujos


def test_con_consola_no_hace_nada(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    antes = (sys.stdout, sys.stderr)
    assert bitacora.asegurar_salida("0.0", tmp_path) is None
    assert (sys.stdout, sys.stderr) == antes


def test_sustituye_solo_el_flujo_ausente(monkeypatch, tmp_path):
    visible = io.StringIO()
    monkeypatch.setattr(sys, "stdout", visible)
    monkeypatch.setattr(sys, "stderr", None)
    assert bitacora.asegurar_salida("0.0", tmp_path) == tmp_path / bitacora.NOMBRE_REGISTRO
    assert sys.stdout is visible
    assert isinstance(sys.stderr, bitacora.SalidaARegistro)


def test_no_crea_el_archivo_hasta_escribir(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    ruta = bitacora.asegurar_salida("0.0", tmp_path / "carpeta")
    assert not ruta.exists() and not ruta.parent.exists()
    print("hola")
    assert ruta.read_text(encoding="utf-8").endswith("hola\n")


def test_la_marca_de_inicio_se_escribe_una_vez(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    ruta = bitacora.asegurar_salida("1.2.3", tmp_path)
    print("uno")
    print("dos", file=sys.stderr)
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    assert lineas[0].startswith("--- Vislumbra 1.2.3 · ")
    assert lineas[1:] == ["uno", "dos"]


def test_recorta_lo_antiguo_al_superar_el_tope(tmp_path):
    ruta = tmp_path / bitacora.NOMBRE_REGISTRO
    ruta.write_text("".join(f"línea {i:04d}\n" for i in range(1000)), encoding="utf-8")
    tamano = ruta.stat().st_size
    salida = bitacora.SalidaARegistro(ruta, "0.0", tope=tamano // 2)
    salida.write("nueva\n")
    texto = ruta.read_text(encoding="utf-8")
    assert "línea 0999" in texto and "línea 0000" not in texto
    assert texto.endswith("nueva\n")
    assert ruta.stat().st_size < tamano
    assert all(l.startswith(("línea", "---", "nueva")) for l in texto.splitlines())  # sin líneas cortadas


def test_si_no_se_puede_escribir_se_descarta_sin_romper(tmp_path):
    bloqueada = tmp_path / "es-un-archivo"
    bloqueada.write_text("x", encoding="utf-8")
    salida = bitacora.SalidaARegistro(bloqueada / bitacora.NOMBRE_REGISTRO, "0.0")  # su «carpeta» es un archivo
    assert salida.write("texto") == 5
    assert salida.write("más") == 3


# --- La orden de terminal sin consola: lo que fallaba con argparse -------------------------------------------
@pytest.mark.parametrize("argv, codigo, texto", [
    (["--version"], 0, "Vislumbra "),
    (["--help"], 0, "Uso: "),
    (["--nada"], 2, "argumentos no reconocidos"),
    (["--gamma", "99"], 1, "fuera del rango"),
])
def test_sin_consola_argparse_y_errores_no_revientan(sin_consola, argv, codigo, texto):
    ruta, quitar_flujos = sin_consola
    quitar_flujos()
    assert cli.main(argv) == codigo
    assert texto in ruta.read_text(encoding="utf-8")


def test_con_consola_no_se_crea_registro(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert cli.main(["--version"]) == 0
    assert "Vislumbra " in capsys.readouterr().out
    assert not (tmp_path / "Vislumbra").exists()
