# SPDX-License-Identifier: GPL-3.0-or-later
"""Modelo del panel, sin Tk ni pantalla: qué se edita, qué rampa va a cada monitor.

``Estado`` guarda lo que el usuario ve y toca: el monitor que mira, el perfil que edita
(el que usa ese monitor), los cambios sin guardar, el tope de los deslizadores, el
«ajuste fuerte», A/B, «Activo» y el modo preciso. La interfaz lee de aquí y el aplicador
recibe de aquí ``rampas()``.

Reglas (``docs/plan-fase-2.md`` §2 y §4):
- Un cambio se aplica en vivo a **todos** los monitores que usan ese perfil.
- «Normal» no se edita: mover un deslizador crea «Perfil N» (sin guardar) y lo asigna
  en lugar de Normal. Un monitor en Normal no recibe rampa (se le devuelve la original).
- Si un movimiento daría una rampa que el validador rechaza, el valor se queda en el
  último válido (por bisección) y se explica el motivo.
- Los tiempos (10 s) se pasan como parámetro ``ahora`` (reloj monótono), para probarlos.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol

from . import color, escala
from .color import Ajuste, ErrorColor, Rampa
from .perfiles import NORMAL, Configuracion, ErrorPerfil, Perfil, PerfilNoEncontrado, _clave

SEGUNDOS_CONFIRMACION = 10.0
UMBRAL_FUERTE = 0.40 * color.MAXIMO  # desviación de la identidad a partir de la cual el ajuste es «fuerte»
PARAMETROS_CANAL = ("brillo", "contraste", "gamma")
BISECCIONES = 24


class MonitorLike(Protocol):
    numero: int
    clave: str
    principal: bool


@dataclass(frozen=True)
class ResultadoMover:
    valor: float  # el valor que quedó (puede ser menor que el pedido si hubo tope)
    tope: str | None = None  # motivo, si el deslizador se detuvo
    perfil_creado: str | None = None  # «Perfil N», si se estaba editando Normal


@dataclass
class _Pendiente:
    clave: str  # perfil afectado
    antes: Perfil
    limite: float


@dataclass(frozen=True)
class Pestana:
    numero: int
    principal: bool
    perfil: str
    fijo: bool


class Estado:
    def __init__(self, conf: Configuracion, monitores: list[MonitorLike]):
        self.conf = conf  # lo guardado en disco (perfiles); no cambia hasta guardar
        self.monitores = list(monitores)
        self.activo: str = conf.perfil_activo
        self._fijos: dict[str, str | None] = dict(conf.monitores)
        self._trabajo: dict[str, Perfil] = {}  # copias con cambios sin guardar, por nombre
        self._nuevos: list[str] = []  # claves de perfiles creados y aún sin guardar (en orden)
        self.mirado: int = self._monitor_inicial()
        self.canal = "r"
        self.activo_on = True
        self.ab = False  # A/B: ver la pantalla normal un momento
        self.preciso = False
        self.pendiente: _Pendiente | None = None  # ajuste fuerte esperando confirmación
        self._deshacer: tuple[str, Perfil, float] | None = None  # «Restablecer» reversible
        self.aviso: str | None = None

    # -- monitores -------------------------------------------------------------------------
    def _monitor_inicial(self) -> int:
        if not self.monitores:
            return 0
        return next((m.numero for m in self.monitores if m.principal), self.monitores[0].numero)

    def _monitor(self, numero: int) -> MonitorLike:
        return next(m for m in self.monitores if m.numero == numero)

    def mirar(self, numero: int) -> None:
        if any(m.numero == numero for m in self.monitores):
            self.mirado = numero

    def actualizar_monitores(self, monitores: list[MonitorLike]) -> None:
        """Cambió la lista de monitores: lo asignado se conserva por clave; los nuevos siguen al activo."""
        self.monitores = list(monitores)
        if not any(m.numero == self.mirado for m in self.monitores):
            self.mirado = self._monitor_inicial()

    # -- perfiles ---------------------------------------------------------------------------
    def _existe(self, nombre: str) -> bool:
        return self.conf.existe(nombre) or _clave(nombre) in self._nuevos

    def _perfil(self, nombre: str) -> Perfil:
        k = _clave(nombre)
        if k in self._trabajo:
            return self._trabajo[k]
        return self.conf.obtener(nombre)

    def _guardado(self, nombre: str) -> Perfil | None:
        return self.conf.obtener(nombre) if self.conf.existe(nombre) else None

    def nombres(self) -> list[str]:
        return self.conf.nombres() + [self._trabajo[k].nombre for k in self._nuevos]

    def asignacion(self, clave: str) -> str | None:
        fijo = self._fijos.get(clave)
        return fijo if fijo is not None and self._existe(fijo) else None

    def perfil_de_monitor(self, numero: int) -> Perfil:
        fijo = self.asignacion(self._monitor(numero).clave)
        return self._perfil(fijo if fijo is not None else self.activo)

    def perfil_editado(self) -> Perfil:
        return self.perfil_de_monitor(self.mirado)

    def pestanas(self) -> list[Pestana]:
        return [
            Pestana(m.numero, m.principal, self.perfil_de_monitor(m.numero).nombre,
                    self.asignacion(m.clave) is not None)
            for m in self.monitores
        ]

    def resumen(self) -> str:
        """«Oscuro» en los monitores 1 y 2 · «Código» en el 3"""
        grupos: dict[str, list[int]] = {}
        for m in self.monitores:
            grupos.setdefault(self.perfil_de_monitor(m.numero).nombre, []).append(m.numero)
        partes = []
        for i, (nombre, nums) in enumerate(grupos.items()):
            if len(nums) == 1:
                donde = f"el monitor {nums[0]}" if i == 0 else f"el {nums[0]}"
            else:
                lista = ", ".join(map(str, nums[:-1])) + f" y {nums[-1]}"
                donde = f"los monitores {lista}" if i == 0 else f"los {lista}"
            partes.append(f"«{nombre}» en {donde}")
        return " · ".join(partes)

    def cambiar_activo(self, nombre: str) -> None:
        if not self._existe(nombre):
            raise PerfilNoEncontrado(f"el perfil «{nombre}» no existe.")
        self.activo = self._perfil(nombre).nombre

    def mover_activo(self, delta: int) -> str:
        """‹ y ›: el perfil activo anterior (−1) o siguiente (+1), con vuelta."""
        nombres = self.nombres()
        i = next((i for i, n in enumerate(nombres) if _clave(n) == _clave(self.activo)), 0)
        self.activo = nombres[(i + delta) % len(nombres)]
        return self.activo

    def fijar_monitor(self, numero: int, nombre: str | None) -> None:
        """``None``: el monitor sigue al perfil activo; si no, queda fijo a ``nombre``."""
        if nombre is not None and not self._existe(nombre):
            raise PerfilNoEncontrado(f"el perfil «{nombre}» no existe.")
        self._fijos[self._monitor(numero).clave] = None if nombre is None else self._perfil(nombre).nombre

    # -- sin guardar --------------------------------------------------------------------------
    def sin_guardar(self, nombre: str | None = None) -> bool:
        if nombre is None:
            return bool(self._trabajo)
        return _clave(nombre) in self._trabajo

    def nombres_sin_guardar(self) -> list[str]:
        return [p.nombre for p in self._trabajo.values()]

    def _poner(self, nombre: str, perfil: Perfil) -> None:
        """Deja ``perfil`` como la versión de trabajo; si coincide con lo guardado, no hay cambios."""
        k = _clave(nombre)
        guardado = self._guardado(nombre)
        if k not in self._nuevos and guardado is not None and perfil == guardado:
            self._trabajo.pop(k, None)
        else:
            self._trabajo[k] = perfil

    def _nombre_libre(self) -> str:
        n = 1
        while self._existe(f"Perfil {n}"):
            n += 1
        return f"Perfil {n}"

    def _validar_nombre(self, nombre: str, excepto: str | None = None) -> str:
        limpio = self.conf.validar_nombre(nombre, excepto=excepto)
        if _clave(limpio) in self._nuevos and (excepto is None or _clave(limpio) != _clave(excepto)):
            raise ErrorPerfil(f"ya existe un perfil llamado «{limpio}».")
        return limpio

    def _reasignar_editado(self, nuevo: str, era_fijo: bool | None = None) -> None:
        """Hace que el monitor mirado use ``nuevo``: cambia el activo si lo seguía, o su perfil fijo."""
        clave = self._monitor(self.mirado).clave
        if era_fijo is None:
            era_fijo = self.asignacion(clave) is not None
        if era_fijo:
            self._fijos[clave] = nuevo
        else:
            self.activo = nuevo

    def _sustituir_referencias(self, viejo: str, nuevo: str | None) -> None:
        """Cambia ``viejo`` por ``nuevo`` en el activo y en los monitores fijos (``None``: Normal / activo)."""
        if _clave(self.activo) == _clave(viejo):
            self.activo = nuevo or NORMAL
        for k, v in list(self._fijos.items()):
            if v is not None and _clave(v) == _clave(viejo):
                self._fijos[k] = nuevo

    # -- editar -----------------------------------------------------------------------------------
    def valor(self, parametro: str) -> float:
        """Valor que muestra el deslizador: el del canal visible si no están vinculados."""
        p = self.perfil_editado()
        if parametro == "temperatura":
            return p.ajuste.temperatura
        c = getattr(p.ajuste, "r" if p.vinculado else self.canal)
        return getattr(c, parametro)

    def valores(self) -> dict[str, float]:
        return {n: self.valor(n) for n in escala.PARAMETROS}

    @staticmethod
    def _con_valor(p: Perfil, parametro: str, valor: float, canal: str) -> Perfil:
        a = p.ajuste
        if parametro == "temperatura":
            return p.con_ajuste(replace(a, temperatura=valor))
        letras = ("r", "g", "b") if p.vinculado else (canal,)
        cambios = {l: replace(getattr(a, l), **{parametro: valor}) for l in letras}
        return p.con_ajuste(replace(a, **cambios))

    @staticmethod
    def _motivo(p: Perfil) -> str | None:
        """``None`` si el perfil se podría aplicar; si no, el motivo en español."""
        try:
            color.construir_rampa_segura(p.ajuste)
        except ErrorColor as e:
            return str(e)
        return None

    def mover(self, parametro: str, valor: float, ahora: float = 0.0) -> ResultadoMover:
        """Pone ``parametro`` a ``valor`` en el perfil editado, con tope si la rampa no sería válida."""
        par = escala.PARAMETROS[parametro]
        valor = escala.limitar(parametro, valor)
        base = self.perfil_editado()
        creado = None
        if base.es_normal:  # Normal no se edita: se trabaja sobre un «Perfil N» nuevo
            creado = self._nombre_libre()
            antes = Perfil(creado, Ajuste())
            base, actual = Perfil(creado, Ajuste()), par.neutro
        else:
            antes, actual = base, self.valor(parametro)
        canal = self.canal
        candidato = self._con_valor(base, parametro, valor, canal)
        motivo = self._motivo(candidato)
        if motivo is not None:  # tope: último valor válido entre el actual y el pedido
            bueno, malo = actual, valor
            for _ in range(BISECCIONES):
                medio = (bueno + malo) / 2.0
                if self._motivo(self._con_valor(base, parametro, medio, canal)) is None:
                    bueno = medio
                else:
                    malo = medio
            valor = escala.redondear(parametro, bueno)
            if self._motivo(self._con_valor(base, parametro, valor, canal)) is not None:
                valor = actual  # el redondeo cayó al otro lado del límite
        else:
            valor = escala.redondear(parametro, valor)
        candidato = self._con_valor(base, parametro, valor, canal)
        if creado is not None:
            if valor == escala.redondear(parametro, par.neutro):
                return ResultadoMover(valor, motivo)  # no cambió nada: no se crea el perfil
            self._nuevos.append(_clave(creado))
            self._reasignar_editado(creado)
        self._poner(candidato.nombre, candidato)
        self._vigilar_fuerte(candidato, antes, ahora)
        return ResultadoMover(valor, motivo, creado)

    def _vigilar_fuerte(self, nuevo: Perfil, antes: Perfil, ahora: float) -> None:
        k = _clave(nuevo.nombre)
        if color.desviacion(color.construir_rampa(nuevo.ajuste)) > UMBRAL_FUERTE:
            if self.pendiente is None or self.pendiente.clave != k:
                self.pendiente = _Pendiente(k, antes, ahora + SEGUNDOS_CONFIRMACION)
            else:
                self.pendiente.limite = ahora + SEGUNDOS_CONFIRMACION
        elif self.pendiente is not None and self.pendiente.clave == k:
            self.pendiente = None

    def mantener(self) -> None:
        """Confirma el ajuste fuerte: ya no se deshace solo."""
        self.pendiente = None

    def segundos_restantes(self, ahora: float) -> float | None:
        return None if self.pendiente is None else max(0.0, self.pendiente.limite - ahora)

    def vencer(self, ahora: float) -> bool:
        """Deshace el ajuste fuerte si pasaron los 10 s sin confirmar. ``True`` si cambió algo."""
        if self.pendiente is None or ahora < self.pendiente.limite:
            return False
        p = self.pendiente
        self.pendiente = None
        self._poner(p.antes.nombre, p.antes)
        self.aviso = "Se deshizo el ajuste fuerte porque no se confirmó."
        return True

    def poner_canal(self, letra: str) -> None:
        if letra in ("r", "g", "b"):
            self.canal = letra

    def canales_distintos(self) -> bool:
        a = self.perfil_editado().ajuste
        return not (a.r == a.g == a.b)

    def vincular(self, si: bool) -> bool:
        """Vincula o desvincula R, G y B. Al vincular se usan los valores del canal visible."""
        p = self.perfil_editado()
        if p.es_normal or p.vinculado == si:
            return False
        a = p.ajuste
        if si:
            c = getattr(a, self.canal)
            a = replace(a, r=c, g=c, b=c)
        nuevo = p.con_ajuste(a, vinculado=si)
        self._poner(nuevo.nombre, nuevo)
        return True

    def restablecer(self, ahora: float = 0.0) -> bool:
        """Pone el perfil editado en neutro (sin guardar). Se puede deshacer durante 10 s."""
        p = self.perfil_editado()
        if p.es_normal:
            return False
        self._deshacer = (_clave(p.nombre), p, ahora + SEGUNDOS_CONFIRMACION)
        self._poner(p.nombre, Perfil(p.nombre, Ajuste(), vinculado=True))
        if self.pendiente is not None and self.pendiente.clave == _clave(p.nombre):
            self.pendiente = None
        return True

    def puede_deshacer(self, ahora: float) -> bool:
        return self._deshacer is not None and ahora < self._deshacer[2]

    def deshacer(self, ahora: float) -> bool:
        if not self.puede_deshacer(ahora):
            self._deshacer = None
            return False
        _, perfil, _ = self._deshacer
        self._deshacer = None
        self._poner(perfil.nombre, perfil)
        return True

    # -- guardar, renombrar, borrar ---------------------------------------------------------------
    def guardar(self) -> str:
        """Guarda el perfil editado (en memoria de ``conf``; la app escribe el archivo)."""
        p = self.perfil_editado()
        if p.es_normal:
            raise ErrorPerfil(f"«{NORMAL}» es fijo y no se puede guardar.")
        k = _clave(p.nombre)
        self.conf.guardar(p)
        self._trabajo.pop(k, None)
        if k in self._nuevos:
            self._nuevos.remove(k)
        if self.pendiente is not None and self.pendiente.clave == k:
            self.pendiente = None
        return p.nombre

    def guardar_todos(self) -> list[str]:
        """Guarda todos los perfiles con cambios (al salir con la opción «Guardar»)."""
        nombres = []
        for k, perfil in list(self._trabajo.items()):
            self.conf.guardar(perfil)
            nombres.append(perfil.nombre)
            self._trabajo.pop(k, None)
            if k in self._nuevos:
                self._nuevos.remove(k)
        self.pendiente = None
        return nombres

    def guardar_como(self, nombre: str) -> str:
        """Crea otro perfil con lo que se ve y devuelve el original a lo guardado."""
        limpio = self._validar_nombre(nombre)
        original = self.perfil_editado()
        era_fijo = self.asignacion(self._monitor(self.mirado).clave) is not None
        copia = Perfil(limpio, original.ajuste, original.vinculado)
        self.conf.guardar(copia)
        k = _clave(original.nombre)
        if not original.es_normal:
            self._trabajo.pop(k, None)  # el original vuelve a lo guardado
            if k in self._nuevos:  # y si solo existía sin guardar, desaparece
                self._nuevos.remove(k)
                self._sustituir_referencias(original.nombre, None)
        if self.pendiente is not None and self.pendiente.clave == k:
            self.pendiente = None
        self._reasignar_editado(limpio, era_fijo)
        return limpio

    def renombrar(self, nuevo: str) -> str:
        p = self.perfil_editado()
        if p.es_normal:
            raise ErrorPerfil(f"«{NORMAL}» es fijo y no se puede renombrar.")
        limpio = self._validar_nombre(nuevo, excepto=p.nombre)
        vieja, nueva = _clave(p.nombre), _clave(limpio)
        if vieja in self._nuevos:
            self._nuevos[self._nuevos.index(vieja)] = nueva
        else:
            self.conf.renombrar(p.nombre, limpio)
        trabajo = self._trabajo.pop(vieja, None)
        if trabajo is not None or vieja in self._nuevos or nueva in self._nuevos:
            self._trabajo[nueva] = replace(trabajo or p, nombre=limpio)
        if self.pendiente is not None and self.pendiente.clave == vieja:
            self.pendiente = replace(self.pendiente, clave=nueva)
        self._sustituir_referencias(p.nombre, limpio)
        return limpio

    def borrar(self) -> str:
        """Borra el perfil editado. Los monitores fijos a él siguen al activo; si era el activo, pasa a Normal."""
        p = self.perfil_editado()
        if p.es_normal:
            raise ErrorPerfil(f"«{NORMAL}» es fijo y no se puede borrar.")
        k = _clave(p.nombre)
        if k in self._nuevos:
            self._nuevos.remove(k)
        else:
            self.conf.borrar(p.nombre)
        self._trabajo.pop(k, None)
        if self.pendiente is not None and self.pendiente.clave == k:
            self.pendiente = None
        self._sustituir_referencias(p.nombre, None)
        return p.nombre

    def descartar(self) -> None:
        """Descarta los cambios sin guardar del perfil editado (si era nuevo, desaparece)."""
        p = self.perfil_editado()
        k = _clave(p.nombre)
        self._trabajo.pop(k, None)
        if k in self._nuevos:
            self._nuevos.remove(k)
            self._sustituir_referencias(p.nombre, None)
        if self.pendiente is not None and self.pendiente.clave == k:
            self.pendiente = None

    def descartar_todo(self) -> None:
        self._trabajo.clear()
        for k in self._nuevos:
            self._sustituir_referencias(k, None)
        self._nuevos.clear()
        self.pendiente = None

    # -- A/B, activo y salida ----------------------------------------------------------------------
    def alternar_ab(self) -> bool:
        self.ab = not self.ab
        return self.ab

    def poner_activo(self, si: bool) -> None:
        self.activo_on = si
        if not si:
            self.ab = False

    def rampas(self) -> dict[int, Rampa | None]:
        """Rampa de cada monitor, o ``None`` para devolverle la original (Normal, A/B o desactivado)."""
        salida: dict[int, Rampa | None] = {}
        for m in self.monitores:
            if not self.activo_on or self.ab:
                salida[m.numero] = None
                continue
            p = self.perfil_de_monitor(m.numero)
            if p.es_normal:
                salida[m.numero] = None
                continue
            try:
                salida[m.numero] = color.construir_rampa_segura(p.ajuste)
            except ErrorColor as e:  # no debería pasar: se valida al editar y al leer del disco
                salida[m.numero] = None
                self.aviso = f"«{p.nombre}» no se puede aplicar: {e}"
        return salida

    def conf_persistible(self) -> Configuracion:
        """Lo que se escribe en el archivo: perfiles guardados, activo y monitores fijos.

        Lo que apunte a un perfil sin guardar se escribe como Normal / «sigue al activo».
        """
        guardado = lambda n: n is not None and self.conf.existe(n)  # noqa: E731
        return Configuracion(
            perfiles=list(self.conf.perfiles),
            perfil_activo=self.activo if guardado(self.activo) else NORMAL,
            monitores={k: (v if guardado(v) else None) for k, v in self._fijos.items()},
        )
