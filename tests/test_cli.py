# SPDX-License-Identifier: GPL-3.0-or-later
"""Pruebas de la orden de terminal. Sustituyen ``display`` por un doble: no tocan la pantalla."""

import pytest

from vislumbra import __main__ as cli
from vislumbra import display
from vislumbra.display import Monitor

MONITORES = [
    Monitor(1, r"\\.\DISPLAY1", "Adaptador A", None, False),
    Monitor(2, r"\\.\DISPLAY2", "Adaptador B", "Monitor de pruebas", True),
    Monitor(3, r"\\.\DISPLAY3", "Adaptador B", None, False),
]


class SesionFalsa:
    creadas: list["SesionFalsa"] = []
    sin_coincidir: list[Monitor] = []
    modificados: list[Monitor] = []
    fallo: Exception | None = None

    def __init__(self, monitores):
        self.monitores, self.aplicadas = monitores, []
        self.conservada = self.cerrada = False
        SesionFalsa.creadas.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.cerrada = True

    def originales_modificados(self):
        return SesionFalsa.modificados

    def aplicar(self, rampa):
        if SesionFalsa.fallo:
            raise SesionFalsa.fallo
        self.aplicadas.append(rampa)
        return SesionFalsa.sin_coincidir

    def conservar(self):
        self.conservada = True


@pytest.fixture(autouse=True)
def pantalla_falsa(monkeypatch):
    SesionFalsa.creadas, SesionFalsa.sin_coincidir = [], []
    SesionFalsa.modificados, SesionFalsa.fallo = [], None
    reiniciados = []
    monkeypatch.setattr(display, "listar_monitores", lambda: list(MONITORES))
    monkeypatch.setattr(display, "SesionGamma", SesionFalsa)
    monkeypatch.setattr(display, "restaurar_identidad", lambda ms: reiniciados.append(ms))
    monkeypatch.setattr(cli, "_esperar", lambda segundos: None)
    return reiniciados


def ejecutar(capsys, *argv):
    codigo = cli.main(list(argv))
    salida = capsys.readouterr()
    return codigo, salida.out, salida.err


# --- --list y --simulate --------------------------------------------------------
def test_list_muestra_los_monitores_y_marca_el_principal(capsys):
    codigo, out, _ = ejecutar(capsys, "--list")
    assert codigo == 0
    assert out.count("\n") == 3
    assert "2. Monitor de pruebas (principal)" in out
    assert "1. Adaptador A" in out


def test_list_sin_monitores_da_error_de_pantalla(capsys, monkeypatch):
    monkeypatch.setattr(display, "listar_monitores", lambda: [])
    codigo, _, err = ejecutar(capsys, "--list")
    assert codigo == 3 and "ningún monitor" in err


def test_simulate_no_toca_la_pantalla_y_muestra_valores(capsys):
    codigo, out, _ = ejecutar(capsys, "--simulate", "--gamma", "1.4")
    assert codigo == 0
    assert "no se ha tocado la pantalla" in out
    assert "[255]=65535" in out and "[0]=0" in out
    assert SesionFalsa.creadas == []


# --- Aplicar ------------------------------------------------------------------------
def test_gamma_se_aplica_al_monitor_principal_y_restaura(capsys):
    codigo, out, _ = ejecutar(capsys, "--gamma", "1,4")
    assert codigo == 0
    (sesion,) = SesionFalsa.creadas
    assert [m.numero for m in sesion.monitores] == [2]
    assert len(sesion.aplicadas) == 1 and len(sesion.aplicadas[0]) == 768
    assert sesion.cerrada and not sesion.conservada
    assert "Aplicado al monitor 2 (principal): gamma 1,40. Pulsa Ctrl+C para restaurar." in out
    assert "Pantalla restaurada." in out


def test_monitor_todos_y_monitor_numero(capsys):
    ejecutar(capsys, "--gamma", "1.2", "--monitor", "todos")
    assert [m.numero for m in SesionFalsa.creadas[-1].monitores] == [1, 2, 3]
    ejecutar(capsys, "--gamma", "1.2", "--monitor", "3")
    assert [m.numero for m in SesionFalsa.creadas[-1].monitores] == [3]


def test_monitor_inexistente(capsys):
    codigo, _, err = ejecutar(capsys, "--gamma", "1.2", "--monitor", "5")
    assert codigo == 3
    assert "Error: el monitor 5 no existe. Usa --list para ver los disponibles." in err


def test_duration_espera_y_restaura(capsys, monkeypatch):
    esperas = []
    monkeypatch.setattr(cli, "_esperar", esperas.append)
    codigo, out, _ = ejecutar(capsys, "--gamma", "1.2", "--duration", "5")
    assert codigo == 0 and esperas == [5.0]
    assert "Se restaurará en 5 s." in out


def test_persist_conserva_y_avisa(capsys):
    codigo, out, _ = ejecutar(capsys, "--gamma", "1.2", "--persist")
    assert codigo == 0
    assert SesionFalsa.creadas[0].conservada
    assert "--reset" in out


def test_ctrl_c_restaura_y_termina_bien(capsys, monkeypatch):
    def interrumpir(_):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "_esperar", interrumpir)
    codigo, out, _ = ejecutar(capsys, "--gamma", "1.2")
    assert codigo == 0 and SesionFalsa.creadas[0].cerrada
    assert "Pantalla restaurada." in out


def test_ctrl_c_durante_la_aplicacion_da_mensaje_en_español_y_codigo_130(capsys):
    SesionFalsa.fallo = KeyboardInterrupt()  # llega dentro de sesion.aplicar, fuera de _esperar
    codigo, out, err = ejecutar(capsys, "--gamma", "1.2")
    assert codigo == 130
    assert "Interrumpido. Pantalla restaurada." in err
    assert "Traceback" not in err and SesionFalsa.creadas[0].cerrada


def test_avisos_de_lectura_y_de_rampa_original_modificada(capsys):
    SesionFalsa.sin_coincidir = [MONITORES[1]]
    SesionFalsa.modificados = [MONITORES[0]]
    _, _, err = ejecutar(capsys, "--gamma", "1.2")
    assert "el monitor 2 aceptó la rampa, pero la lectura posterior no coincide" in err
    assert "el monitor 1 ya tenía una rampa modificada" in err


def test_canal_individual_deja_los_otros_neutros(capsys):
    ejecutar(capsys, "--gamma", "2", "--channel", "r")
    rampa = SesionFalsa.creadas[0].aplicadas[0]
    assert rampa[:256] != rampa[256:512] and rampa[256:512] == rampa[512:]
    assert rampa[256:512] == [i * 257 for i in range(256)]


def test_numeros_con_coma_negativos_y_signo_tipografico(capsys):
    codigo, out, _ = ejecutar(capsys, "--simulate", "--brightness", "-0,5", "--contrast", "\u22123")
    assert codigo == 0
    assert ejecutar(capsys, "--simulate", "--brightness=-40")[0] == 0


def test_error_de_windows_al_aplicar_da_codigo_3(capsys):
    SesionFalsa.fallo = display.RampaRechazada(
        "Windows ha rechazado la rampa en el monitor 2. Prueba con valores más suaves."
    )
    codigo, _, err = ejecutar(capsys, "--gamma", "1.2")
    assert codigo == 3
    assert "Error: Windows ha rechazado la rampa en el monitor 2. Prueba con valores más suaves." in err


# --- --reset -----------------------------------------------------------------------------
def test_reset_actua_sobre_todos_por_defecto(capsys, pantalla_falsa):
    codigo, out, _ = ejecutar(capsys, "--reset")
    assert codigo == 0
    assert [m.numero for m in pantalla_falsa[0]] == [1, 2, 3]
    assert "identidad" in out


def test_reset_con_monitor(capsys, pantalla_falsa):
    ejecutar(capsys, "--reset", "--monitor", "2")
    assert [m.numero for m in pantalla_falsa[0]] == [2]


# --- Errores de valor (código 1) -----------------------------------------------------------
def test_valor_fuera_de_rango_usa_el_nombre_de_la_opcion(capsys):
    codigo, _, err = ejecutar(capsys, "--gamma", "7")
    assert codigo == 1
    assert "Error: --gamma 7,0 está fuera del rango permitido (0,5 a 4,0)." in err
    assert SesionFalsa.creadas == []


def test_ajuste_ilegible_se_rechaza_sin_aplicar(capsys):
    codigo, _, err = ejecutar(capsys, "--brightness", "125", "--contrast", "-82")
    assert codigo == 1
    assert "dejaría la pantalla casi ilegible" in err and "No se ha aplicado nada." in err
    assert SesionFalsa.creadas == []


def test_nan_se_rechaza(capsys):
    codigo, _, err = ejecutar(capsys, "--gamma", "nan")
    assert codigo == 1 and "número finito" in err


# --- Uso incorrecto (código 2) ---------------------------------------------------------------
@pytest.mark.parametrize("argv, texto", [
    ([], "indica al menos un ajuste"),
    (["--monitor", "2"], "indica al menos un ajuste"),
    (["--reset", "--gamma", "1.2"], "--reset no se mezcla"),
    (["--list", "--gamma", "1.2"], "--list no se mezcla"),
    (["--gamma", "1.2", "--duration", "5", "--persist"], "excluyentes"),
    (["--simulate", "--gamma", "1.2", "--persist"], "--simulate no se combina"),
    (["--temp", "4000", "--channel", "r"], "--temp no se puede usar con --channel"),
    (["--gamma"], "se esperaba un valor"),
    (["--gamma", "abc"], "«abc» no es un número"),
    (["--gamma", "1.2", "--channel", "x"], "no es un canal válido"),
    (["--gamma", "1.2", "--duration", "0"], "mayor que 0"),
    (["--gamma", "1.2", "--duration", "inf"], "número finito"),
    (["--gamma", "1.2", "--duration", "nan"], "número finito"),
    (["--gamma", "1.2", "--rara"], "argumentos no reconocidos"),
    (["--gam", "1.2"], "argumentos no reconocidos"),
])
def test_uso_incorrecto_da_codigo_2_y_mensaje_en_español(capsys, argv, texto):
    codigo, _, err = ejecutar(capsys, *argv)
    assert codigo == 2
    assert texto in err and err.startswith("Error:")
    assert SesionFalsa.creadas == []


def test_ayuda_en_español(capsys):
    codigo, out, _ = ejecutar(capsys, "--help")
    assert codigo == 0
    assert "Uso:" in out and "usage" not in out.lower()
    assert "Ajustes" in out and "options:" not in out


def test_version(capsys):
    codigo, out, _ = ejecutar(capsys, "--version")
    assert codigo == 0 and out.startswith("Vislumbra ")
