# SPDX-License-Identifier: GPL-3.0-or-later
"""Orden de terminal: ``python -m vislumbra``.

Códigos de salida: 0 correcto; 1 valor inválido o rampa ilegible; 2 uso
incorrecto; 3 error de Windows o de monitor; 130 Ctrl+C fuera de la espera.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
import time

from . import __version__, color, display

OK, ERROR_VALOR, ERROR_USO, ERROR_PANTALLA = 0, 1, 2, 3
INTERRUMPIDO = 130  # Ctrl+C fuera de la espera

_OPCION_POR_NOMBRE = {
    "brillo": "--brightness",
    "contraste": "--contrast",
    "gamma": "--gamma",
    "temperatura": "--temp",
}
_NUMERO_SUELTO = re.compile(r"^[-−]\d+([.,]\d+)?$")
_TRADUCCIONES = (
    ("expected one argument", "se esperaba un valor"),
    ("unrecognized arguments:", "argumentos no reconocidos:"),
    ("ignored explicit argument", "no admite un valor explícito"),
)


def _fmt(x: float, decimales: int = 2) -> str:
    return f"{x:.{decimales}f}".replace(".", ",")


class _Formato(argparse.HelpFormatter):
    def add_usage(self, usage, actions, groups, prefix=None):
        super().add_usage(usage, actions, groups, "Uso: " if prefix is None else prefix)


class _Parser(argparse.ArgumentParser):
    def error(self, message: str):  # los textos por defecto de argparse salen en inglés
        for ingles, español in _TRADUCCIONES:
            message = message.replace(ingles, español)
        message = re.sub(r"^argument ", "argumento ", message)
        self.exit(ERROR_USO, f"Error: {message}\nUsa --help para ver las opciones.\n")


def _decimal(texto: str) -> float:
    try:
        return float(texto.replace(",", "."))
    except ValueError:
        raise argparse.ArgumentTypeError(f"«{texto}» no es un número.") from None


def _segundos(texto: str) -> float:
    valor = _decimal(texto)
    if not (valor > 0 and math.isfinite(valor)):
        raise argparse.ArgumentTypeError("la duración debe ser un número finito mayor que 0.")
    return valor


def _canal(texto: str) -> str:
    t = texto.strip().lower()
    if t not in ("all", "r", "g", "b"):
        raise argparse.ArgumentTypeError(f"«{texto}» no es un canal válido (all, r, g o b).")
    return t


def _crear_parser() -> argparse.ArgumentParser:
    p = _Parser(
        prog="python -m vislumbra",
        description="Vislumbra: brillo, contraste, gamma y temperatura de color de la pantalla.",
        add_help=False,
        allow_abbrev=False,
        formatter_class=_Formato,
    )
    aj = p.add_argument_group("Ajustes (decimales con punto o con coma)")
    aj.add_argument("--gamma", type=_decimal, metavar="G",
                    help=f"gamma, de {_fmt(color.GAMMA_MIN, 1)} a {_fmt(color.GAMMA_MAX, 1)} (1 = neutro)")
    aj.add_argument("--brightness", type=_decimal, metavar="B",
                    help=f"brillo, de {color.BRILLO_MIN:.0f} a {color.BRILLO_MAX:.0f} (0 = neutro)")
    aj.add_argument("--contrast", type=_decimal, metavar="C",
                    help=f"contraste, de {color.CONTRASTE_MIN:.0f} a {color.CONTRASTE_MAX:.0f} (0 = neutro)")
    aj.add_argument("--temp", type=_decimal, metavar="K",
                    help=f"temperatura en kelvin, de {color.TEMPERATURA_MIN:.0f} a "
                         f"{color.TEMPERATURA_MAX:.0f} (6500 = neutro)")
    aj.add_argument("--channel", type=_canal, default=None, metavar="all|r|g|b",
                    help="canal al que se aplican brillo, contraste y gamma (por defecto, all)")
    de = p.add_argument_group("Destino y duración")
    de.add_argument("--monitor", metavar="principal|todos|N", default=None,
                    help="monitor afectado (por defecto, el principal; con --reset, todos)")
    de.add_argument("--duration", type=_segundos, metavar="S",
                    help="aplica, espera S segundos y restaura solo")
    de.add_argument("--persist", action="store_true",
                    help="aplica y termina sin restaurar (usa --reset para deshacerlo)")
    ac = p.add_argument_group("Otras acciones")
    ac.add_argument("--list", action="store_true", help="muestra los monitores activos")
    ac.add_argument("--simulate", action="store_true",
                    help="calcula y muestra la rampa sin tocar la pantalla")
    ac.add_argument("--reset", action="store_true",
                    help="aplica la rampa neutra (identidad) y termina")
    ac.add_argument("-h", "--help", action="help", help="muestra esta ayuda y sale")
    ac.add_argument("--version", action="version", version=f"Vislumbra {__version__}",
                    help="muestra la versión y sale")
    return p


def _normalizar(argv: list[str]) -> list[str]:
    """Permite «-0,5» y el signo menos tipográfico como números negativos."""
    return [
        a.replace("−", "-").replace(",", ".") if _NUMERO_SUELTO.match(a) else a
        for a in argv
    ]


def _con_opcion(mensaje: str) -> str:
    """Cambia «gamma 7,0 está…» por «--gamma 7,0 está…»."""
    primera, _, resto = mensaje.partition(" ")
    return f"{_OPCION_POR_NOMBRE[primera]} {resto}" if primera in _OPCION_POR_NOMBRE else mensaje


def _error(mensaje: str, codigo: int) -> int:
    print(f"Error: {mensaje}", file=sys.stderr)
    return codigo


def _construir_ajuste(a: argparse.Namespace) -> color.Ajuste:
    brillo, contraste, gamma = a.brightness or 0.0, a.contrast or 0.0, (
        1.0 if a.gamma is None else a.gamma
    )
    if a.channel == "all":
        temp = color.TEMPERATURA_NEUTRA if a.temp is None else a.temp
        return color.Ajuste.uniforme(brillo, contraste, gamma, temp)
    canal = color.AjusteCanal(brillo, contraste, gamma)
    return color.Ajuste(**{a.channel: canal})


def _descripcion(a: argparse.Namespace) -> str:
    partes = []
    if a.gamma is not None:
        partes.append(f"gamma {_fmt(a.gamma)}")
    if a.brightness is not None:
        partes.append(f"brillo {_fmt(a.brightness, 1)}")
    if a.contrast is not None:
        partes.append(f"contraste {_fmt(a.contrast, 1)}")
    if a.temp is not None:
        partes.append(f"temperatura {_fmt(a.temp, 0)} K")
    texto = ", ".join(partes)
    return texto + (f" (solo canal {a.channel.upper()})" if a.channel != "all" else "")


def _destino(monitores: list[display.Monitor]) -> str:
    if len(monitores) == 1:
        m = monitores[0]
        return f"al monitor {m.numero}" + (" (principal)" if m.principal else "")
    return "a los monitores " + ", ".join(str(m.numero) for m in monitores)


def _comprobar_uso(a: argparse.Namespace) -> str | None:
    hay_ajuste = any(v is not None for v in (a.gamma, a.brightness, a.contrast, a.temp))
    if a.reset and (hay_ajuste or a.simulate or a.duration or a.persist or a.list):
        return "--reset no se mezcla con ajustes ni con otras acciones."
    if a.list and (hay_ajuste or a.simulate or a.duration or a.persist):
        return "--list no se mezcla con ajustes ni con otras acciones."
    if a.duration and a.persist:
        return "--duration y --persist son excluyentes."
    if a.simulate and (a.duration or a.persist):
        return "--simulate no se combina con --duration ni --persist."
    if a.temp is not None and a.channel not in (None, "all"):
        return "--temp no se puede usar con --channel r, g o b."
    if a.simulate and a.monitor is not None:
        return "--simulate no toca ninguna pantalla y no usa --monitor."
    if a.list and (a.monitor is not None or a.channel is not None):
        return "--list no usa --monitor ni --channel."
    if a.reset and a.channel is not None:
        return "--reset no usa --channel."
    if not (hay_ajuste or a.list or a.reset):
        return ("indica al menos un ajuste (--gamma, --brightness, --contrast o --temp), "
                "--list o --reset.")
    return None


def _listar() -> int:
    monitores = display.listar_monitores()
    if not monitores:
        return _error("no se ha encontrado ningún monitor activo.", ERROR_PANTALLA)
    for m in monitores:
        marca = " (principal)" if m.principal else ""
        print(f"{m.numero}. {m.nombre or m.adaptador}{marca}  [{m.dispositivo}]")
    return OK


def _simular(rampa: color.Rampa) -> int:
    print("Simulación (no se ha tocado la pantalla). Valores de 16 bits:")
    puntos = (0, 64, 128, 192, 255)
    for n, letra in enumerate("RGB"):
        canal = rampa[n * color.PUNTOS:(n + 1) * color.PUNTOS]
        print(f"  {letra}: " + "  ".join(f"[{i}]={canal[i]}" for i in puntos))
    print("El ajuste es válido.")
    return OK


def _reiniciar(a: argparse.Namespace) -> int:
    monitores = display.elegir_monitores("todos" if a.monitor is None else a.monitor, display.listar_monitores())
    display.restaurar_identidad(monitores)
    print(f"Rampa neutra aplicada {_destino(monitores)}.")
    print("Nota: --reset aplica siempre la identidad; no puede conocer una rampa "
          "original distinta (por ejemplo, un perfil de color).")
    return OK


def _esperar(segundos: float | None) -> None:
    """Espera ``segundos`` (o hasta Ctrl+C si es ``None``); en bucle corto para poder interrumpirse."""
    fin = None if segundos is None else time.monotonic() + segundos
    while fin is None or time.monotonic() < fin:
        time.sleep(0.2)


def _aplicar(a: argparse.Namespace, rampa: color.Rampa) -> int:
    monitores = display.elegir_monitores("principal" if a.monitor is None else a.monitor, display.listar_monitores())
    descripcion, destino = _descripcion(a), _destino(monitores)
    with display.SesionGamma(monitores) as sesion:
        for m in sesion.originales_modificados():
            print(f"Aviso: el monitor {m.numero} ya tenía una rampa modificada (otra herramienta "
                  "o un perfil de color); al salir se restaurará esa.", file=sys.stderr)
        for m in sesion.aplicar(rampa):
            print(f"Aviso: el monitor {m.numero} aceptó la rampa, pero la lectura posterior no "
                  "coincide; el controlador puede estar limitándola.", file=sys.stderr)
        if a.persist:
            sesion.conservar()
            print(f"Aplicado {destino}: {descripcion}.")
            print("Aviso: la rampa se queda aplicada al terminar. Usa --reset para volver a la normal.")
            return OK
        pista = (f"Se restaurará en {f'{a.duration:g}'.replace('.', ',')} s."
                 if a.duration else "Pulsa Ctrl+C para restaurar.")
        print(f"Aplicado {destino}: {descripcion}. {pista}", flush=True)
        try:
            _esperar(a.duration)
        except KeyboardInterrupt:
            pass
    print("Pantalla restaurada.")
    return OK


def main(argv: list[str] | None = None) -> int:
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(errors="replace")
    argumentos = _normalizar(list(sys.argv[1:] if argv is None else argv))
    try:
        a = _crear_parser().parse_args(argumentos)
    except SystemExit as salida:  # error de uso, --help o --version
        return salida.code if isinstance(salida.code, int) else OK
    problema = _comprobar_uso(a)
    if problema:
        return _error(problema, ERROR_USO)
    a.channel = a.channel or "all"
    try:
        if a.list:
            return _listar()
        if a.reset:
            return _reiniciar(a)
        rampa = color.construir_rampa_segura(_construir_ajuste(a))
        if a.simulate:
            return _simular(rampa)
        return _aplicar(a, rampa)
    except color.RampaIlegible as e:
        return _error(f"{e} No se ha aplicado nada.", ERROR_VALOR)
    except color.ErrorColor as e:
        return _error(_con_opcion(str(e)), ERROR_VALOR)
    except display.ErrorPantalla as e:
        return _error(str(e), ERROR_PANTALLA)
    except KeyboardInterrupt:  # Ctrl+C fuera de la espera; la sesión ya restauró al salir
        print("Interrumpido. Pantalla restaurada.", file=sys.stderr)
        return INTERRUMPIDO


if __name__ == "__main__":
    sys.exit(main())
