# SPDX-License-Identifier: GPL-3.0-or-later
"""Punto de entrada de los ejecutables (lo usa ``vislumbra.spec``).

PyInstaller necesita un script, y ``vislumbra/__main__.py`` usa importaciones relativas. Este
archivo solo llama a ``main``: ``Vislumbra.exe`` y ``vislumbra-cli.exe`` ejecutan el mismo código.
"""

import sys

from vislumbra.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
