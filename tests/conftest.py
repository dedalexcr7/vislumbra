# SPDX-License-Identifier: GPL-3.0-or-later
"""Configuración común de las pruebas."""


def pytest_addoption(parser):
    parser.addoption(
        "--con-pantalla",
        action="store_true",
        default=False,
        help="Ejecuta también las pruebas que modifican la gamma real de la pantalla.",
    )
