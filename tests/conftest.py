# SPDX-License-Identifier: GPL-3.0-or-later
"""Configuración común de las pruebas.

Las pruebas marcadas con ``pantalla`` modifican la gamma real y solo se ejecutan con
``--con-pantalla``. En ese caso hay dos redes de seguridad que devuelven la rampa
original de cada monitor: una por sesión de pytest y otra por prueba.
"""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--con-pantalla",
        action="store_true",
        default=False,
        help="Ejecuta también las pruebas que modifican la gamma real de la pantalla.",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "pantalla: modifica la gamma real de la pantalla (solo con --con-pantalla)"
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--con-pantalla"):
        return
    salto = pytest.mark.skip(reason="requiere --con-pantalla")
    for item in items:
        if "pantalla" in item.keywords:
            item.add_marker(salto)


def _guardar_rampas(monitores):
    from vislumbra import display

    return {m.numero: display.leer_rampa(m) for m in monitores}


def _devolver_rampas(monitores, guardadas, donde):
    """Restaura las rampas guardadas y comprueba la lectura; si no coincide, lo dice."""
    from vislumbra import display

    for m in monitores:
        try:
            display._escribir(m, guardadas[m.numero])
            if display.leer_rampa(m) != guardadas[m.numero]:
                print(f"\nAVISO ({donde}): la rampa del monitor {m.numero} no coincide con "
                      "la guardada. Ejecuta --reset.")
        except Exception as e:  # nunca ocultar un fallo al restaurar, pero seguir con el resto
            print(f"\nAVISO ({donde}): no se pudo restaurar el monitor {m.numero}: {e}. "
                  "Ejecuta --reset.")


@pytest.fixture
def monitores_reales():
    """Monitores activos reales; se salta la prueba si no hay ninguno."""
    from vislumbra import display

    try:
        monitores = display.listar_monitores()
    except Exception as e:
        pytest.skip(f"no hay monitores activos ({e})")
    if not monitores:
        pytest.skip("no hay monitores activos")
    return monitores


@pytest.fixture(scope="session", autouse=True)
def _red_de_seguridad_de_sesion(request):
    """Con ``--con-pantalla``, devuelve las rampas del inicio al terminar la sesión."""
    if not request.config.getoption("--con-pantalla"):
        yield
        return
    from vislumbra import display

    try:
        monitores = display.listar_monitores()
        guardadas = _guardar_rampas(monitores)
    except Exception as e:
        print(f"\nAVISO: no se pudieron guardar las rampas iniciales: {e}")
        yield
        return
    try:
        yield
    finally:
        _devolver_rampas(monitores, guardadas, "fin de la sesión")


@pytest.fixture
def rampas_guardadas(request, monitores_reales):
    """Guarda las rampas antes de la prueba y las devuelve al acabar, aunque falle.

    Solo actúa con ``--con-pantalla``; sin esa opción las pruebas que la usan se saltan.
    """
    if not request.config.getoption("--con-pantalla"):
        pytest.skip("requiere --con-pantalla")
    guardadas = _guardar_rampas(monitores_reales)
    request.addfinalizer(lambda: _devolver_rampas(monitores_reales, guardadas, request.node.name))
    return guardadas


@pytest.fixture(scope="session")
def raiz_tk():
    """Una única raíz de Tk para toda la sesión de pruebas.

    Crear y destruir varias raíces ``Tk()`` en el mismo proceso falla de forma intermitente en
    Windows («Can't find a usable tk.tcl»). Las pruebas de la interfaz usan un ``Toplevel`` de esta.
    """
    import tkinter as tk

    try:
        raiz = tk.Tk()
    except tk.TclError as e:  # sin Tk o sin escritorio
        pytest.skip(f"no hay Tk: {e}")
    raiz.withdraw()
    yield raiz
    try:
        raiz.destroy()
    except tk.TclError:
        pass


@pytest.fixture
def ventana(raiz_tk):
    """Ventana oculta (``Toplevel``) para una prueba; se destruye al acabar."""
    import tkinter as tk

    v = tk.Toplevel(raiz_tk)
    v.withdraw()
    yield v
    v.destroy()
