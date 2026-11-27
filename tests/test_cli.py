# SPDX-License-Identifier: GPL-3.0-or-later
"""Pruebas de la orden de terminal. Sustituyen ``display`` por un doble: no tocan la pantalla."""

import pytest

from vislumbra import __main__ as cli
from vislumbra import app as app_mod
from vislumbra import color, display, perfiles
from vislumbra.display import Monitor
from vislumbra.perfiles import Configuracion, Perfil

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


class AppFalsa:
    """La app abierta, simulada: estas pruebas nunca abren la app de verdad ni miran si hay una."""

    abierta = False
    abiertas = 0
    peticiones: list[str] = []
    desactivaciones = 0
    esperas: list[float] = []


def configuracion_de_prueba():
    c = Configuracion()
    c.guardar(Perfil("Oscuro", color.Ajuste.uniforme(0.0, 7.5, 1.7)))
    c.guardar(Perfil("Código", color.Ajuste.uniforme(-20.0, 0.0, 1.0, 6000.0)))
    c.perfil_activo = "Oscuro"
    return c


@pytest.fixture(autouse=True)
def pantalla_falsa(monkeypatch):
    SesionFalsa.creadas, SesionFalsa.sin_coincidir = [], []
    SesionFalsa.modificados, SesionFalsa.fallo = [], None
    AppFalsa.abierta, AppFalsa.abiertas, AppFalsa.desactivaciones = False, 0, 0
    AppFalsa.peticiones, AppFalsa.esperas = [], []
    reiniciados = []
    monkeypatch.setattr(cli, "_hay_app", lambda: AppFalsa.abierta)
    monkeypatch.setattr(cli, "_abrir_app", lambda: setattr(AppFalsa, "abiertas", AppFalsa.abiertas + 1) or 0)
    monkeypatch.setattr(cli, "_dormir", AppFalsa.esperas.append)
    monkeypatch.setattr(app_mod, "pedir_perfil", lambda peticion, *a, **k: AppFalsa.peticiones.append(peticion) or True)
    monkeypatch.setattr(app_mod, "pedir_desactivar", lambda *a, **k: setattr(AppFalsa, "desactivaciones", AppFalsa.desactivaciones + 1) or True)
    monkeypatch.setattr(perfiles, "cargar", lambda *a, **k: (configuracion_de_prueba(), []))  # nunca el %APPDATA% real
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


def test_duration_con_decimales_se_muestra_completa(capsys):
    _, out, _ = ejecutar(capsys, "--gamma", "1.2", "--duration", "0,5")
    assert "Se restaurará en 0,5 s." in out


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
    codigo, _, err = ejecutar(capsys, "--brightness", "-100", "--gamma", "0.5")
    assert codigo == 1
    assert "dejaría la pantalla casi ilegible" in err and "No se ha aplicado nada." in err
    assert SesionFalsa.creadas == []


def test_formas_de_escribir_los_valores_de_argparse(capsys):
    assert ejecutar(capsys, "--simulate", "--gamma=1,4")[0] == 0
    codigo, _, err = ejecutar(capsys, "--simulate", "--gamma", "-1")  # valor, no opción
    assert codigo == 1 and "--gamma -1,0 está fuera del rango" in err
    codigo, _, err = ejecutar(capsys, "--gamma", "1.2", "--monitor", "0")
    assert codigo == 3 and "el monitor 0 no existe" in err and SesionFalsa.creadas == []


def test_ayuda_tiene_prioridad_sobre_un_valor_invalido(capsys):
    codigo, out, _ = ejecutar(capsys, "--help", "--gamma", "7")
    assert codigo == 0 and "Uso:" in out


def test_nan_se_rechaza(capsys):
    codigo, _, err = ejecutar(capsys, "--gamma", "nan")
    assert codigo == 1 and "número finito" in err


# --- Uso incorrecto (código 2) ---------------------------------------------------------------
@pytest.mark.parametrize("argv, texto", [
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


# --- I-5 e I-11b: nada se ignora en silencio ---------------------------------------------------
@pytest.mark.parametrize("argv, texto", [
    (["--simulate", "--gamma", "1.2", "--monitor", "2"], "--simulate no toca ninguna pantalla"),
    (["--list", "--monitor", "2"], "--list no usa --monitor ni --channel"),
    (["--list", "--channel", "r"], "--list no usa --monitor ni --channel"),
    (["--reset", "--channel", "r"], "--reset no usa --channel"),
])
def test_opciones_que_se_ignorarian_dan_error_de_uso(capsys, argv, texto):
    codigo, _, err = ejecutar(capsys, *argv)
    assert codigo == 2 and texto in err


def test_monitor_vacio_es_un_error_y_no_cae_al_principal(capsys, pantalla_falsa):
    codigo, _, err = ejecutar(capsys, "--gamma", "1.2", "--monitor", "")
    assert codigo == 3 and "no es un monitor válido" in err and SesionFalsa.creadas == []
    codigo, _, err = ejecutar(capsys, "--reset", "--monitor", "")
    assert codigo == 3 and pantalla_falsa == []


def test_channel_all_explicito_sigue_funcionando(capsys):
    assert ejecutar(capsys, "--simulate", "--gamma", "1.2", "--channel", "all")[0] == 0


# --- Sin argumentos: abre la app ---------------------------------------------------------------------------------
def test_sin_argumentos_abre_la_app(capsys):
    assert ejecutar(capsys)[0] == 0
    assert AppFalsa.abiertas == 1 and SesionFalsa.creadas == []


def test_con_argumentos_no_abre_la_app(capsys):
    ejecutar(capsys, "--simulate", "--gamma", "1.2")
    assert AppFalsa.abiertas == 0


# --- --perfil ----------------------------------------------------------------------------------------------------------
def test_perfil_sin_la_app_lo_aplica_como_un_ajuste(capsys):
    codigo, out, _ = ejecutar(capsys, "--perfil", "oscuro")
    assert codigo == 0 and "Aplicado al monitor 2 (principal): perfil «Oscuro»." in out
    (sesion,) = SesionFalsa.creadas
    assert sesion.aplicadas[0] == color.construir_rampa_segura(color.Ajuste.uniforme(0.0, 7.5, 1.7))
    assert sesion.cerrada and AppFalsa.peticiones == []


def test_perfil_normal_aplica_la_rampa_neutra(capsys):
    assert ejecutar(capsys, "--perfil", "Normal")[0] == 0
    assert SesionFalsa.creadas[0].aplicadas[0] == color.rampa_identidad()


def test_perfil_siguiente_sin_la_app_sigue_al_activo_de_la_configuracion(capsys):
    _, out, _ = ejecutar(capsys, "--perfil", "siguiente")  # el activo es «Oscuro»: sigue «Código»
    assert "perfil «Código»" in out


def test_perfil_admite_monitor_duration_y_persist_sin_la_app(capsys):
    ejecutar(capsys, "--perfil", "Oscuro", "--monitor", "todos", "--persist")
    assert [m.numero for m in SesionFalsa.creadas[-1].monitores] == [1, 2, 3] and SesionFalsa.creadas[-1].conservada
    assert ejecutar(capsys, "--perfil", "Oscuro", "--duration", "5")[0] == 0


def test_perfil_con_simulate_no_toca_la_pantalla(capsys):
    codigo, out, _ = ejecutar(capsys, "--perfil", "Oscuro", "--simulate")
    assert codigo == 0 and "no se ha tocado la pantalla" in out and SesionFalsa.creadas == []


def test_perfil_inexistente_da_codigo_1_y_lista_los_perfiles(capsys):
    codigo, _, err = ejecutar(capsys, "--perfil", "NoExiste")
    assert codigo == 1 and "no existe" in err and "Perfiles disponibles: Normal, Oscuro, Código." in err
    assert SesionFalsa.creadas == []


def test_perfil_con_la_app_abierta_envia_la_peticion(capsys):
    AppFalsa.abierta = True
    codigo, out, _ = ejecutar(capsys, "--perfil", "código")
    assert codigo == 0 and AppFalsa.peticiones == ["perfil:Código"] and "perfil «Código»" in out
    ejecutar(capsys, "--perfil", "siguiente")
    assert AppFalsa.peticiones[-1] == "siguiente"
    assert SesionFalsa.creadas == []  # no aplica nada por su cuenta


def test_perfil_inexistente_con_la_app_abierta_tambien_da_codigo_1(capsys):
    AppFalsa.abierta = True
    assert ejecutar(capsys, "--perfil", "Nada")[0] == 1 and AppFalsa.peticiones == []


@pytest.mark.parametrize("extra", [["--monitor", "2"], ["--duration", "5"], ["--persist"], ["--simulate"]])
def test_con_la_app_abierta_perfil_no_admite_destino_ni_duracion(capsys, extra):
    AppFalsa.abierta = True
    codigo, _, err = ejecutar(capsys, "--perfil", "Oscuro", *extra)
    assert codigo == 2 and "solo cambia el perfil activo" in err and AppFalsa.peticiones == []


@pytest.mark.parametrize("argv, texto", [
    (["--perfil", "Oscuro", "--gamma", "1.2"], "--perfil no se mezcla con ajustes"),
    (["--perfil", "Oscuro", "--channel", "r"], "--perfil no se mezcla con ajustes"),
    (["--perfil", "Oscuro", "--reset"], "--reset no se mezcla"),
    (["--perfil", "Oscuro", "--list"], "--list no se mezcla"),
    (["--perfil", "  "], "necesita el nombre"),
    (["--perfil"], "se esperaba un valor"),
])
def test_perfil_uso_incorrecto(capsys, argv, texto):
    codigo, _, err = ejecutar(capsys, *argv)
    assert codigo == 2 and texto in err and SesionFalsa.creadas == []


# --- Con la app abierta -------------------------------------------------------------------------------------------------------
def test_con_la_app_abierta_los_ajustes_se_rechazan_con_codigo_3(capsys):
    AppFalsa.abierta = True
    codigo, _, err = ejecutar(capsys, "--gamma", "1.2")
    assert codigo == 3 and "Vislumbra está abierta" in err and SesionFalsa.creadas == []


def test_con_la_app_abierta_list_y_simulate_siguen_funcionando(capsys):
    AppFalsa.abierta = True
    assert ejecutar(capsys, "--list")[0] == 0
    assert ejecutar(capsys, "--simulate", "--gamma", "1.2")[0] == 0


def test_un_valor_invalido_se_avisa_antes_que_la_app_abierta(capsys):
    AppFalsa.abierta = True
    codigo, _, err = ejecutar(capsys, "--gamma", "7")
    assert codigo == 1 and "fuera del rango" in err


def test_reset_con_la_app_abierta_la_desactiva_antes_de_aplicar_la_identidad(capsys, pantalla_falsa):
    AppFalsa.abierta = True
    codigo, out, _ = ejecutar(capsys, "--reset")
    assert codigo == 0 and AppFalsa.desactivaciones == 1 and AppFalsa.esperas == [app_mod.ESPERA_RESET_MS / 1000]
    assert [m.numero for m in pantalla_falsa[0]] == [1, 2, 3] and "se ha desactivado" in out


def test_reset_sin_la_app_no_espera(capsys, pantalla_falsa):
    assert ejecutar(capsys, "--reset")[0] == 0
    assert AppFalsa.desactivaciones == 0 and AppFalsa.esperas == []


def test_la_ayuda_menciona_perfil_y_que_sin_argumentos_abre_la_app(capsys):
    _, out, _ = ejecutar(capsys, "--help")
    assert "--perfil" in out and "Sin argumentos abre la app" in " ".join(out.split())  # la ayuda reparte las líneas
