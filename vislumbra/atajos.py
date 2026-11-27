# SPDX-License-Identifier: GPL-3.0-or-later
"""Atajos de teclado globales: lógica pura (sin Windows ni Tk).

Una **combinación** son modificadores (Ctrl, Alt, Mayús, Win) más una tecla. Se guarda como texto canónico
(``Ctrl+Alt+Shift+P``) y se muestra en español (``Ctrl+Alt+Mayús+P``). ``Atajos`` reúne las combinaciones de las
acciones fijas, las de cada perfil y el aviso al usarlas, con un JSON tolerante: un atajo malo se descarta solo.
"""

from __future__ import annotations

import copy
import unicodedata
from collections.abc import Collection
from dataclasses import dataclass, field

MODIFICADORES = ("Ctrl", "Alt", "Shift", "Win")  # orden canónico
_ALIAS_MOD = {
    "ctrl": "Ctrl", "control": "Ctrl", "alt": "Alt", "shift": "Shift", "mayus": "Shift", "mayusculas": "Shift",
    "win": "Win", "windows": "Win", "meta": "Win", "super": "Win",
}
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN = 0x1, 0x2, 0x4, 0x8
_BANDERAS = {"Alt": MOD_ALT, "Ctrl": MOD_CONTROL, "Shift": MOD_SHIFT, "Win": MOD_WIN}

# Tecla canónica -> código de tecla virtual de Windows
_TECLAS: dict[str, int] = {chr(c): c for c in range(ord("A"), ord("Z") + 1)}
_TECLAS.update({str(d): 0x30 + d for d in range(10)})
_TECLAS.update({f"F{n}": 0x70 + n - 1 for n in range(1, 25)})
_TECLAS.update({
    "Left": 0x25, "Up": 0x26, "Right": 0x27, "Down": 0x28, "Home": 0x24, "End": 0x23, "PageUp": 0x21, "PageDown": 0x22,
    "Insert": 0x2D, "Delete": 0x2E, "Pause": 0x13,
})
_ALIAS_TECLA = {
    "left": "Left", "izquierda": "Left", "up": "Up", "arriba": "Up", "right": "Right", "derecha": "Right", "down": "Down",
    "abajo": "Down", "home": "Home", "inicio": "Home", "end": "End", "fin": "End", "pageup": "PageUp", "pgup": "PageUp",
    "repag": "PageUp", "pagedown": "PageDown", "pgdn": "PageDown", "avpag": "PageDown", "insert": "Insert", "ins": "Insert",
    "delete": "Delete", "del": "Delete", "supr": "Delete", "pause": "Pause", "pausa": "Pause",
    "←": "Left", "↑": "Up", "→": "Right", "↓": "Down",  # como se muestran
}
_MOSTRAR_TECLA = {
    "Left": "←", "Up": "↑", "Right": "→", "Down": "↓", "Home": "Inicio", "End": "Fin", "PageUp": "RePág", "PageDown": "AvPág",
    "Insert": "Ins", "Delete": "Supr", "Pause": "Pausa",
}
_VK_A_TECLA = {vk: nombre for nombre, vk in _TECLAS.items()}
SOLAS_VALIDAS = frozenset({f"F{n}" for n in range(13, 25)} | {"Pause"})  # sin modificador: nadie las usa para escribir

ACCIONES = ("siguiente", "anterior", "comparar", "activo", "panel", "preciso", "emergencia")
ETIQUETAS = {
    "siguiente": "Siguiente perfil", "anterior": "Perfil anterior", "comparar": "Comparar (A/B)", "activo": "Activo sí o no",
    "panel": "Mostrar u ocultar el panel", "preciso": "Modo preciso", "emergencia": "Emergencia: pantalla original",
}
DEFECTOS: dict[str, str | None] = {
    "siguiente": "Ctrl+Alt+P", "anterior": "Ctrl+Alt+Shift+P", "comparar": "Ctrl+Alt+B", "activo": "Ctrl+Alt+V",
    "panel": "Ctrl+Alt+Shift+V", "preciso": None, "emergencia": "Ctrl+Alt+0",
}
AVISOS = ("ninguno", "sonido", "notificacion")
ETIQUETAS_AVISO = {"ninguno": "Ninguno", "sonido": "Sonido", "notificacion": "Notificación"}
ACCION, PERFIL = "accion", "perfil"  # primer elemento de la clave de un atajo: (ACCION, "siguiente") o (PERFIL, "Código")


class ErrorAtajo(ValueError):
    """Combinación o atajo no válido; el mensaje va en español."""


def _plano(texto: str) -> str:
    """Minúsculas y sin acentos, para reconocer «Mayús», «mayus» y «MAYÚS»."""
    return "".join(c for c in unicodedata.normalize("NFD", texto.strip().lower()) if unicodedata.category(c) != "Mn")


@dataclass(frozen=True)
class Combinacion:
    mods: frozenset[str]
    tecla: str

    def __post_init__(self) -> None:
        if self.tecla not in _TECLAS:
            raise ErrorAtajo(f"la tecla «{self.tecla}» no se admite.")
        if not set(self.mods) <= set(MODIFICADORES):
            raise ErrorAtajo("modificador no reconocido.")

    @property
    def vk(self) -> int:
        return _TECLAS[self.tecla]

    @property
    def banderas(self) -> int:
        """Los modificadores como los pide ``RegisterHotKey`` (sin ``MOD_NOREPEAT``)."""
        return sum(_BANDERAS[m] for m in self.mods)

    def texto(self) -> str:
        """Texto canónico para guardar: ``Ctrl+Alt+Shift+P``."""
        return "+".join([m for m in MODIFICADORES if m in self.mods] + [self.tecla])

    def mostrar(self) -> str:
        """Texto para el usuario: ``Ctrl+Alt+Mayús+P``."""
        mods = ["Mayús" if m == "Shift" else m for m in MODIFICADORES if m in self.mods]
        return "+".join(mods + [_MOSTRAR_TECLA.get(self.tecla, self.tecla)])

    def validar(self) -> None:
        """Lanza ``ErrorAtajo`` si no se puede usar como atajo global."""
        if self.mods & {"Ctrl", "Alt", "Win"} or self.tecla in SOLAS_VALIDAS:
            return
        if self.mods == {"Shift"}:
            raise ErrorAtajo("Mayús sola no vale: bloquearía escribir mayúsculas. Añade Ctrl o Alt.")
        raise ErrorAtajo("añade Ctrl, Alt o Win (solo F13 a F24 y Pausa se pueden usar sin modificador).")


def tecla_de_vk(vk: int) -> str | None:
    """Nombre canónico de una tecla a partir de su código virtual de Windows (``None`` si no se admite)."""
    return _VK_A_TECLA.get(vk)


def combinacion(mods: Collection[str], tecla: str) -> Combinacion:
    return Combinacion(frozenset(mods), tecla)


def parsear(texto: str) -> Combinacion:
    """Lee ``Ctrl+Alt+Mayús+P`` en cualquier orden y con mayúsculas o minúsculas; la valida."""
    partes = [p for p in (x.strip() for x in texto.split("+")) if p]
    if len(partes) < 1 or texto.strip().endswith("++"):
        raise ErrorAtajo("la combinación está vacía.")
    *mods_texto, tecla_texto = partes
    mods = set()
    for m in mods_texto:
        canon = _ALIAS_MOD.get(_plano(m))
        if canon is None:
            raise ErrorAtajo(f"«{m}» no es un modificador (Ctrl, Alt, Mayús o Win).")
        mods.add(canon)
    plano = _plano(tecla_texto)
    tecla = _ALIAS_TECLA.get(plano) or (tecla_texto.strip().upper() if tecla_texto.strip().upper() in _TECLAS else None)
    if tecla is None:
        raise ErrorAtajo(f"la tecla «{tecla_texto}» no se admite.")
    c = Combinacion(frozenset(mods), tecla)
    c.validar()
    return c


@dataclass
class Atajos:
    acciones: dict[str, Combinacion | None] = field(default_factory=dict)
    perfiles: dict[str, Combinacion] = field(default_factory=dict)  # nombre del perfil -> combinación
    aviso: str = "ninguno"

    @classmethod
    def por_defecto(cls) -> "Atajos":
        return cls({a: (parsear(t) if t else None) for a, t in DEFECTOS.items()})

    def copia(self) -> "Atajos":
        return copy.deepcopy(self)

    # -- consulta ---------------------------------------------------------------------------------------------------
    def elementos(self) -> list[tuple[tuple[str, str], Combinacion]]:
        """Todos los atajos con combinación: ``((ACCION, 'siguiente'), comb)`` y ``((PERFIL, 'Código'), comb)``."""
        res = [((ACCION, a), c) for a, c in self.acciones.items() if c is not None]
        return res + [((PERFIL, n), c) for n, c in self.perfiles.items()]

    @staticmethod
    def etiqueta(clave: tuple[str, str]) -> str:
        return ETIQUETAS[clave[1]] if clave[0] == ACCION else f"Perfil «{clave[1]}»"

    def uso(self, comb: Combinacion, excepto: tuple[str, str] | None = None) -> str | None:
        """Qué acción o perfil ya usa esa combinación (para avisar de duplicados)."""
        for clave, c in self.elementos():
            if c == comb and clave != excepto:
                return self.etiqueta(clave)
        return None

    # -- cambios -------------------------------------------------------------------------------------------------------
    def _comprobar(self, comb: Combinacion, clave: tuple[str, str]) -> None:
        comb.validar()
        otro = self.uso(comb, excepto=clave)
        if otro is not None:
            raise ErrorAtajo(f"{comb.mostrar()} ya la usa «{otro}».")

    def asignar_accion(self, accion: str, comb: Combinacion | None) -> None:
        if accion not in ACCIONES:
            raise ErrorAtajo(f"la acción «{accion}» no existe.")
        if comb is None:
            if accion == "emergencia":
                raise ErrorAtajo("el atajo de emergencia se puede cambiar, pero no quitar.")
            self.acciones[accion] = None
            return
        self._comprobar(comb, (ACCION, accion))
        self.acciones[accion] = comb

    def asignar_perfil(self, nombre: str, comb: Combinacion | None) -> None:
        if comb is None:
            self.perfiles.pop(nombre, None)
            return
        self._comprobar(comb, (PERFIL, nombre))
        self.perfiles[nombre] = comb

    def renombrar_perfil(self, viejo: str, nuevo: str) -> None:
        if viejo in self.perfiles:
            self.perfiles = {(nuevo if n == viejo else n): c for n, c in self.perfiles.items()}

    def quitar_perfil(self, nombre: str) -> None:
        self.perfiles.pop(nombre, None)

    def restaurar_defectos(self) -> list[str]:
        """Devuelve las acciones a sus valores por defecto (los atajos de perfil no se tocan).

        Si un perfil ya usa esa combinación, esa acción se queda sin atajo y se avisa.
        """
        avisos = []
        usadas = {c for c in self.perfiles.values()}
        nuevas: dict[str, Combinacion | None] = {}
        for accion, texto in DEFECTOS.items():
            c = parsear(texto) if texto else None
            if c is not None and c in usadas:
                avisos.append(f"{c.mostrar()} ya la usa un perfil: «{ETIQUETAS[accion]}» se queda sin atajo.")
                c = None
            nuevas[accion] = c
        self.acciones = nuevas
        return avisos

    # -- JSON ----------------------------------------------------------------------------------------------------------------
    def a_json(self) -> dict:
        return {
            "acciones": {a: (c.texto() if c else None) for a, c in self.acciones.items()},
            "perfiles": {n: c.texto() for n, c in self.perfiles.items()},
            "aviso": self.aviso,
        }

    @classmethod
    def de_json(cls, datos: object, perfiles: Collection[str] | None = None) -> tuple["Atajos", list[str]]:
        """Lee los atajos de forma tolerante. Devuelve ``(atajos, avisos)``.

        Una acción ausente usa su valor por defecto; ``null`` es «sin atajo» a propósito. Un atajo inválido, repetido o
        de una acción desconocida se descarta **solo ese**. Un campo entero ilegible vuelve a los valores por defecto.
        """
        avisos: list[str] = []
        if datos is None:
            return cls.por_defecto(), avisos
        if not isinstance(datos, dict):
            return cls.por_defecto(), ["Los atajos guardados no tenían el formato esperado: se usan los valores por defecto."]
        res = cls()
        acciones = datos.get("acciones", {})
        if not isinstance(acciones, dict):
            acciones, _ = {}, avisos.append("Las acciones de los atajos no tenían el formato esperado.")
        for clave in acciones:
            if clave not in ACCIONES:
                avisos.append(f"Atajo de una acción desconocida («{clave}»): se descarta.")
        usadas: dict[Combinacion, str] = {}

        def leer(clave: tuple[str, str], texto: object) -> Combinacion | None:
            try:
                if not isinstance(texto, str):
                    raise ErrorAtajo("no es un texto.")
                c = parsear(texto)
            except ErrorAtajo as e:
                avisos.append(f"Atajo de «{cls.etiqueta(clave)}» descartado: {e}")
                return None
            if c in usadas:
                avisos.append(f"Atajo de «{cls.etiqueta(clave)}» descartado: {c.mostrar()} ya la usa «{usadas[c]}».")
                return None
            usadas[c] = cls.etiqueta(clave)
            return c

        for accion in ACCIONES:
            if accion not in acciones:
                c = parsear(DEFECTOS[accion]) if DEFECTOS[accion] else None
                if c is not None and c in usadas:  # el valor por defecto choca con otro atajo: sin atajo
                    c = None
                elif c is not None:
                    usadas[c] = cls.etiqueta((ACCION, accion))
                res.acciones[accion] = c
            elif acciones[accion] is None:
                if accion == "emergencia":
                    avisos.append("El atajo de emergencia no se puede quitar: se usa el valor por defecto.")
                    res.acciones[accion] = leer((ACCION, accion), DEFECTOS[accion])
                else:
                    res.acciones[accion] = None
            else:
                c = leer((ACCION, accion), acciones[accion])
                if c is None and accion == "emergencia":
                    c = leer((ACCION, accion), DEFECTOS[accion])
                res.acciones[accion] = c
        lista = datos.get("perfiles", {})
        if not isinstance(lista, dict):
            lista, _ = {}, avisos.append("Los atajos de perfil no tenían el formato esperado.")
        conocidos = None if perfiles is None else {_plano(p): p for p in perfiles}
        for nombre, texto in lista.items():
            if not isinstance(nombre, str):
                continue
            if conocidos is not None:
                if _plano(nombre) not in conocidos:
                    continue  # el perfil ya no existe: se ignora sin avisar
                nombre = conocidos[_plano(nombre)]
            c = leer((PERFIL, nombre), texto)
            if c is not None:
                res.perfiles[nombre] = c
        aviso = datos.get("aviso", "ninguno")
        res.aviso = aviso if aviso in AVISOS else "ninguno"
        return res, avisos
