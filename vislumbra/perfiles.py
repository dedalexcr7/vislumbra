# SPDX-License-Identifier: GPL-3.0-or-later
"""Perfiles, perfil activo y asignación por monitor, con guardado atómico en ``%APPDATA%``.

No toca la pantalla. Solo el sistema de archivos, y únicamente en la ruta que se le da
(por defecto ``%APPDATA%\\Vislumbra\\config.json``; las pruebas usan una carpeta temporal).

Reglas:
- «Normal» es fijo: no se guarda, no se edita y no se borra. Un monitor en Normal no se
  toca (se le devuelve su rampa original).
- Cada monitor «sigue al perfil activo» o tiene un perfil fijo. La clave del monitor
  contiene datos del equipo y solo vive en este archivo, fuera del repositorio.
- Nunca se aplica un ajuste leído del disco sin validarlo.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
import time
from dataclasses import dataclass, field, replace
from pathlib import Path

from . import color
from .atajos import Atajos
from .color import Ajuste, AjusteCanal
from .programas import ALCANCE_ACTIVO, Asociacion, ErrorPrograma, normalizar_alcance, normalizar_exe

NORMAL = "Normal"
VERSION = 1
ASIGNACION_ACTIVO = "activo"
ASIGNACION_FIJO = "fijo"
NOMBRE_MAX = 40
NOMBRE_ARCHIVO = "config.json"
SIGUIENTE = "siguiente"  # palabra reservada de ``--perfil siguiente``


class ErrorPerfil(ValueError):
    """Error de perfiles o de configuración; el mensaje va en español."""


class PerfilNoEncontrado(ErrorPerfil):
    pass


@dataclass(frozen=True)
class Perfil:
    nombre: str
    ajuste: Ajuste = field(default_factory=Ajuste)
    vinculado: bool = True  # R, G y B se mueven a la vez

    @property
    def es_normal(self) -> bool:
        return _clave(self.nombre) == _clave(NORMAL)

    def con_ajuste(self, ajuste: Ajuste, vinculado: bool | None = None) -> "Perfil":
        return replace(self, ajuste=ajuste, vinculado=self.vinculado if vinculado is None else vinculado)


PERFIL_NORMAL = Perfil(NORMAL)


def _clave(nombre: str) -> str:
    return nombre.strip().casefold()


# --- Archivo ----------------------------------------------------------------------------------
def carpeta_config() -> Path:
    """``%APPDATA%\\Vislumbra`` (no se crea hasta que se guarda algo)."""
    base = os.environ.get("APPDATA")
    return (Path(base) if base else Path.home() / "AppData" / "Roaming") / "Vislumbra"


def ruta_config() -> Path:
    return carpeta_config() / NOMBRE_ARCHIVO


def _perfil_a_json(p: Perfil) -> dict:
    def canal(c: AjusteCanal) -> dict:
        return {"brillo": c.brillo, "contraste": c.contraste, "gamma": c.gamma}

    a = p.ajuste
    return {
        "nombre": p.nombre,
        "vinculado": p.vinculado,
        "canales": {"r": canal(a.r), "g": canal(a.g), "b": canal(a.b)},
        "temperatura": a.temperatura,
    }


def _numero(valor, que: str) -> float:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor):
        raise ErrorPerfil(f"{que} no es un número válido.")
    return float(valor)


def _perfil_de_json(d) -> Perfil:
    if not isinstance(d, dict):
        raise ErrorPerfil("un perfil no tiene el formato esperado.")
    nombre = d.get("nombre")
    if not isinstance(nombre, str):
        raise ErrorPerfil("un perfil no tiene nombre.")
    vinculado = d.get("vinculado", True)
    if not isinstance(vinculado, bool):
        raise ErrorPerfil(f"«{nombre}»: «vinculado» debe ser verdadero o falso.")
    canales = d.get("canales")
    if not isinstance(canales, dict):
        raise ErrorPerfil(f"«{nombre}»: faltan los canales.")
    leidos = {}
    for letra in "rgb":
        c = canales.get(letra)
        if not isinstance(c, dict):
            raise ErrorPerfil(f"«{nombre}»: falta el canal {letra.upper()}.")
        leidos[letra] = AjusteCanal(
            _numero(c.get("brillo", 0.0), f"«{nombre}»: el brillo"),
            _numero(c.get("contraste", 0.0), f"«{nombre}»: el contraste"),
            _numero(c.get("gamma", 1.0), f"«{nombre}»: la gamma"),
        )
    if vinculado:  # un archivo editado a mano no puede dejar canales distintos en un perfil vinculado
        leidos["g"] = leidos["b"] = leidos["r"]
    temperatura = _numero(d.get("temperatura", color.TEMPERATURA_NEUTRA), f"«{nombre}»: la temperatura")
    return Perfil(nombre, Ajuste(leidos["r"], leidos["g"], leidos["b"], temperatura), vinculado)


@dataclass
class Configuracion:
    """Perfiles del usuario (sin Normal), perfil activo, asignación por monitor y programas asociados."""

    perfiles: list[Perfil] = field(default_factory=list)
    perfil_activo: str = NORMAL
    monitores: dict[str, str | None] = field(default_factory=dict)  # clave -> None (activo) o nombre fijo
    programas: list[Asociacion] = field(default_factory=list)  # programa (.exe) -> perfil que se activa solo
    atajos: Atajos = field(default_factory=Atajos.por_defecto)  # atajos de teclado globales
    avisos_lectura: list[str] = field(default_factory=list, repr=False, compare=False)  # lo que se descartó al leer

    # -- consulta
    def todos(self) -> list[Perfil]:
        return [PERFIL_NORMAL, *self.perfiles]

    def nombres(self) -> list[str]:
        return [p.nombre for p in self.todos()]

    def obtener(self, nombre: str) -> Perfil:
        for p in self.todos():
            if _clave(p.nombre) == _clave(nombre):
                return p
        raise PerfilNoEncontrado(f"el perfil «{nombre}» no existe.")

    def existe(self, nombre: str) -> bool:
        return any(_clave(p.nombre) == _clave(nombre) for p in self.todos())

    def activo(self) -> Perfil:
        return self.obtener(self.perfil_activo)

    def asignacion(self, clave: str) -> str | None:
        """``None`` si el monitor sigue al perfil activo; si no, el nombre de su perfil fijo."""
        fijo = self.monitores.get(clave)
        return fijo if fijo is not None and self.existe(fijo) else None

    def perfil_de_monitor(self, clave: str) -> Perfil:
        fijo = self.asignacion(clave)
        return self.obtener(fijo) if fijo is not None else self.activo()

    def nombre_libre(self) -> str:
        n = 1
        while self.existe(f"Perfil {n}"):
            n += 1
        return f"Perfil {n}"

    def validar_nombre(self, nombre: str, excepto: str | None = None) -> str:
        """Devuelve el nombre limpio o lanza ``ErrorPerfil``."""
        limpio = nombre.strip()
        if not limpio:
            raise ErrorPerfil("el nombre del perfil no puede estar vacío.")
        if len(limpio) > NOMBRE_MAX:
            raise ErrorPerfil(f"el nombre del perfil no puede pasar de {NOMBRE_MAX} caracteres.")
        if any(ord(c) < 32 for c in limpio):
            raise ErrorPerfil("el nombre del perfil no puede llevar caracteres de control.")
        if _clave(limpio) == _clave(NORMAL):
            raise ErrorPerfil(f"«{NORMAL}» es el perfil neutro y no se puede usar ese nombre.")
        if _clave(limpio) == SIGUIENTE:
            raise ErrorPerfil(f"«{limpio}» es una palabra reservada de la orden --perfil.")
        if self.existe(limpio) and (excepto is None or _clave(limpio) != _clave(excepto)):
            raise ErrorPerfil(f"ya existe un perfil llamado «{limpio}».")
        return limpio

    # -- cambios
    def guardar(self, perfil: Perfil) -> Perfil:
        """Crea el perfil o reemplaza el que tiene ese nombre. Normal no se puede guardar."""
        if perfil.es_normal:
            raise ErrorPerfil(f"«{NORMAL}» es fijo y no se puede modificar.")
        existente = next((i for i, p in enumerate(self.perfiles) if _clave(p.nombre) == _clave(perfil.nombre)), None)
        nombre = self.validar_nombre(perfil.nombre, excepto=perfil.nombre if existente is not None else None)
        color.construir_rampa_segura(perfil.ajuste)  # nunca se guarda un ajuste que no se podría aplicar
        nuevo = replace(perfil, nombre=nombre)
        if existente is None:
            self.perfiles.append(nuevo)
        else:
            self.perfiles[existente] = nuevo
        return nuevo

    def renombrar(self, viejo: str, nuevo: str) -> str:
        actual = self.obtener(viejo)
        if actual.es_normal:
            raise ErrorPerfil(f"«{NORMAL}» es fijo y no se puede renombrar.")
        limpio = self.validar_nombre(nuevo, excepto=actual.nombre)
        self.perfiles = [replace(p, nombre=limpio) if p is actual else p for p in self.perfiles]
        if _clave(self.perfil_activo) == _clave(actual.nombre):
            self.perfil_activo = limpio
        self.monitores = {
            k: (limpio if v is not None and _clave(v) == _clave(actual.nombre) else v)
            for k, v in self.monitores.items()
        }
        self.programas = [
            replace(a, perfil=limpio) if _clave(a.perfil) == _clave(actual.nombre) else a for a in self.programas
        ]
        self.atajos.renombrar_perfil(actual.nombre, limpio)
        return limpio

    def borrar(self, nombre: str) -> None:
        """Los monitores fijos a ese perfil pasan a seguir al activo; si era el activo, pasa a Normal."""
        actual = self.obtener(nombre)
        if actual.es_normal:
            raise ErrorPerfil(f"«{NORMAL}» es fijo y no se puede borrar.")
        self.perfiles = [p for p in self.perfiles if p is not actual]
        if _clave(self.perfil_activo) == _clave(actual.nombre):
            self.perfil_activo = NORMAL
        self.monitores = {
            k: (None if v is not None and _clave(v) == _clave(actual.nombre) else v)
            for k, v in self.monitores.items()
        }
        self.programas = [a for a in self.programas if _clave(a.perfil) != _clave(actual.nombre)]
        self.atajos.quitar_perfil(actual.nombre)

    def activar(self, nombre: str) -> Perfil:
        perfil = self.obtener(nombre)
        self.perfil_activo = perfil.nombre
        return perfil

    def siguiente(self) -> Perfil:
        """Activa el perfil que sigue al activo (da la vuelta al llegar al final)."""
        nombres = self.nombres()
        i = next((i for i, n in enumerate(nombres) if _clave(n) == _clave(self.perfil_activo)), -1)
        return self.activar(nombres[(i + 1) % len(nombres)])

    def asociar(self, exe: str, perfil: str, alcance: str = ALCANCE_ACTIVO) -> Asociacion:
        """Asocia un programa a un perfil (reemplaza la asociación anterior de ese programa)."""
        try:
            e = normalizar_exe(exe)
        except ErrorPrograma as err:
            raise ErrorPerfil(str(err)) from None
        nueva = Asociacion(e, self.obtener(perfil).nombre, normalizar_alcance(alcance))
        self.programas = [a for a in self.programas if a.exe != e] + [nueva]
        return nueva

    def desasociar(self, exe: str) -> None:
        try:
            e = normalizar_exe(exe)
        except ErrorPrograma as err:
            raise ErrorPerfil(str(err)) from None
        self.programas = [a for a in self.programas if a.exe != e]

    def asignar(self, clave: str, perfil_fijo: str | None) -> None:
        """``None``: el monitor sigue al perfil activo; si no, queda fijo a ese perfil."""
        if perfil_fijo is None:
            self.monitores[clave] = None
        else:
            self.monitores[clave] = self.obtener(perfil_fijo).nombre

    # -- JSON
    def a_json(self) -> dict:
        return {
            "version": VERSION,
            "perfiles": [_perfil_a_json(p) for p in self.perfiles],
            "perfil_activo": self.perfil_activo,
            "programas": [{"exe": a.exe, "perfil": a.perfil, "alcance": a.alcance} for a in self.programas],
            "atajos": self.atajos.a_json(),
            "monitores": {
                k: ({"asignacion": ASIGNACION_ACTIVO} if v is None
                    else {"asignacion": ASIGNACION_FIJO, "perfil": v})
                for k, v in self.monitores.items()
            },
        }

    @classmethod
    def de_json(cls, datos) -> "Configuracion":
        """Valida todo el contenido; lanza ``ErrorPerfil`` si algo no es válido o no es seguro."""
        if not isinstance(datos, dict):
            raise ErrorPerfil("el archivo no tiene el formato esperado.")
        if datos.get("version") != VERSION:
            raise ErrorPerfil(f"versión de configuración no reconocida ({datos.get('version')!r}).")
        conf = cls()
        lista = datos.get("perfiles", [])
        if not isinstance(lista, list):
            raise ErrorPerfil("la lista de perfiles no tiene el formato esperado.")
        for d in lista:
            perfil = _perfil_de_json(d)
            if conf.existe(perfil.nombre):
                raise ErrorPerfil(f"el perfil «{perfil.nombre}» está repetido.")
            conf.guardar(perfil)  # valida nombre, rangos y que la rampa sea aplicable
        activo = datos.get("perfil_activo", NORMAL)
        conf.perfil_activo = conf.obtener(activo).nombre if isinstance(activo, str) and conf.existe(activo) else NORMAL
        monitores = datos.get("monitores", {})
        if not isinstance(monitores, dict):
            raise ErrorPerfil("la asignación de monitores no tiene el formato esperado.")
        for clave, d in monitores.items():
            if not isinstance(d, dict):
                raise ErrorPerfil("la asignación de un monitor no tiene el formato esperado.")
            fijo = d.get("perfil") if d.get("asignacion") == ASIGNACION_FIJO else None
            # Un perfil fijo que ya no existe se trata como «sigue al activo».
            conf.monitores[str(clave)] = conf.obtener(fijo).nombre if isinstance(fijo, str) and conf.existe(fijo) else None
        lista_programas = datos.get("programas", [])
        if not isinstance(lista_programas, list):
            raise ErrorPerfil("la lista de programas no tiene el formato esperado.")
        for d in lista_programas:
            if not isinstance(d, dict) or not isinstance(d.get("exe"), str) or not isinstance(d.get("perfil"), str):
                raise ErrorPerfil("la asociación de un programa no tiene el formato esperado.")
            try:
                exe = normalizar_exe(d["exe"])
            except ErrorPrograma as err:
                raise ErrorPerfil(str(err)) from None
            # Un perfil que ya no existe o un programa repetido se ignoran (no hacen dañado el archivo).
            if conf.existe(d["perfil"]) and not any(a.exe == exe for a in conf.programas):
                conf.programas.append(Asociacion(exe, conf.obtener(d["perfil"]).nombre, normalizar_alcance(d.get("alcance"))))
        conf.atajos, conf.avisos_lectura = Atajos.de_json(datos.get("atajos"), perfiles=conf.nombres())
        return conf


def guardar_en(conf: Configuracion, ruta: Path | None = None) -> Path:
    """Escribe la configuración de forma atómica: a un temporal y después ``os.replace``."""
    ruta = Path(ruta) if ruta is not None else ruta_config()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(conf.a_json(), ensure_ascii=False, indent=2)
    fd, temporal = tempfile.mkstemp(prefix=ruta.name + ".", suffix=".tmp", dir=ruta.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(texto + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporal, ruta)
    except BaseException:
        try:
            os.unlink(temporal)
        except OSError:
            pass
        raise
    return ruta


def _apartar(ruta: Path) -> Path:
    base = ruta.with_name(f"{ruta.stem}.dañado-{time.strftime('%Y%m%d-%H%M%S')}{ruta.suffix}")
    destino, n = base, 1
    while destino.exists():
        n += 1
        destino = base.with_name(f"{base.stem}-{n}{base.suffix}")
    os.replace(ruta, destino)
    return destino


def cargar(ruta: Path | None = None) -> tuple[Configuracion, list[str]]:
    """Lee la configuración. Devuelve ``(configuración, avisos)``.

    Si no existe, arranca con Normal sin avisos. Si está dañada o tiene valores no
    válidos o peligrosos, se aparta como ``config.dañado-<fecha>.json``, se arranca con
    Normal y se avisa. Nunca lanza por un archivo malo.
    """
    ruta = Path(ruta) if ruta is not None else ruta_config()
    if not ruta.exists():
        return Configuracion(), []
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        conf = Configuracion.de_json(datos)
        return conf, list(conf.avisos_lectura)
    except (ValueError, OSError, color.ErrorColor) as e:  # JSON roto, formato, rangos o rampa peligrosa
        motivo = str(e)
    try:
        destino = _apartar(ruta)
        donde = f"Se guardó una copia como «{destino.name}»."
    except OSError:
        donde = "No se pudo apartar el archivo dañado."
    return Configuracion(), [f"La configuración no era válida ({motivo}). Se arranca con «{NORMAL}». {donde}"]
