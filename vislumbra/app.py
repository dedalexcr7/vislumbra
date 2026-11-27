# SPDX-License-Identifier: GPL-3.0-or-later
"""La app: conecta el estado, el panel, la bandeja y el hilo aplicador.

Hilos (ver ``docs/plan-fase-2.md`` §5):

- **Principal**: Tk. Es el único que toca widgets y la sesión de gamma (por las señales).
- **pystray**: los clics del menú; solo meten acciones en ``cola``.
- **Eventos**: espera los eventos con nombre («mostrar», «desactivar», «petición») y los mete en ``cola``.
- **Aplicador**: escribe las rampas y vigila (``aplicador.py``).

Tk revisa ``cola`` cada 50 ms. Todo cierre pasa por ``_parar_todo``, que es idempotente y restaura la pantalla.
"""

from __future__ import annotations

import queue
import sys
import threading
import time
import tkinter as tk
import traceback
from collections.abc import Callable
from pathlib import Path

from . import arranque, display, perfiles, sistema, tray
from .aplicador import Aplicador, Aviso
from .estado import Estado
from .panel import AVISO, PELIGRO, TEXTO_SUAVE, Panel

NOMBRE_PETICION = "peticion.txt"
PETICION_SIGUIENTE = "siguiente"
PETICION_PERFIL = "perfil:"
INTERVALO_COLA_MS = 50
ESPERA_RESET_MS = 600  # lo que espera ``--reset`` a que la app suelte la pantalla antes de aplicar la identidad


def ruta_peticion() -> Path:
    return perfiles.carpeta_config() / NOMBRE_PETICION


class App:
    def __init__(
        self,
        *,
        raiz: tk.Misc | None = None,
        ruta_config: Path | None = None,
        ruta_peticion_: Path | None = None,
        listar: Callable[[], list[display.Monitor]] = display.listar_monitores,
        leer=display.leer_rampa,
        crear_sesion: Callable[[list[display.Monitor]], object] = display.SesionGamma,
        prefijo_sistema: str = sistema.PREFIJO,
        con_bandeja: bool = True,
        reloj: Callable[[], float] = time.monotonic,
        intervalo_vigilancia: float | None = None,
        oculto: bool = False,
        arranque=arranque,
    ):
        self._raiz_dada = raiz
        self.ruta_config = ruta_config
        self.ruta_peticion = ruta_peticion_ or ruta_peticion()
        self._listar, self._leer, self._crear_sesion = listar, leer, crear_sesion
        self._nombres = sistema.nombres(prefijo_sistema)
        self._con_bandeja = con_bandeja
        self._reloj = reloj
        self._intervalo_vigilancia = intervalo_vigilancia
        self._oculto = oculto  # al iniciar sesión: solo el icono, sin abrir el panel
        self._arranque = arranque
        self._arranque_activo = False
        self.cola: queue.Queue = queue.Queue()
        self.raiz = self.estado = self.panel = self.sesion = self.aplicador = self.bandeja = None
        self._mutex = None
        self._eventos: dict[str, sistema.Evento] = {}
        self._hilo_eventos: threading.Thread | None = None
        self._info = tray.InfoBandeja()
        self._corriendo = False
        self._cerrando = False
        self._avisado_ocultar = False
        self.avisos_arranque: list[str] = []

    # -- arranque -------------------------------------------------------------------------------------------------------------
    def iniciar(self) -> bool:
        """Prepara todo. ``False`` si ya hay otra instancia (se le pide que muestre su panel)."""
        self._mutex = sistema.Mutex(self._nombres["mutex"])
        if self._mutex.ya_existia:
            self._mutex.cerrar()
            existente = None if self._oculto else sistema.Evento.abrir(self._nombres["mostrar"])
            if existente is not None:
                existente.activar()
                existente.cerrar()
            return False
        try:
            self._montar()
        except BaseException:
            self._parar_todo()
            raise
        return True

    def _montar(self) -> None:
        conf, avisos = perfiles.cargar(self.ruta_config)
        self.avisos_arranque = list(avisos)
        monitores = self._listar()
        if not monitores:
            raise display.MonitorNoEncontrado("no se ha encontrado ningún monitor activo.")
        for clave in ("mostrar", "desactivar", "peticion"):
            self._eventos[clave] = sistema.Evento(self._nombres[clave])
        self._eventos["parar"] = sistema.Evento()  # local: despierta al hilo de eventos al cerrar
        self.sesion = self._crear_sesion(monitores)
        self.sesion.iniciar()
        self.estado = Estado(conf, monitores)
        if self._raiz_dada is None:
            sistema.activar_dpi()
            self.raiz = tk.Tk()
            self.raiz.withdraw()
        else:
            self.raiz = self._raiz_dada
        self.raiz.report_callback_exception = self._excepcion_tk
        self.panel = Panel(self.raiz, self.estado, self, self._reloj)
        self._crear_aplicador()
        self._corriendo = True
        self._hilo_eventos = threading.Thread(target=self._bucle_eventos, name="vislumbra-eventos", daemon=True)
        self._hilo_eventos.start()
        self._actualizar_info()
        if self._con_bandeja:
            self.bandeja = tray.Bandeja(self._accion_de_bandeja, lambda: self._info)
            self.bandeja.iniciar()
        for texto in self.avisos_arranque:
            self.panel.mensaje(texto, AVISO, 20)
        for m in self.sesion.originales_modificados():
            self.panel.mensaje(
                f"El monitor {m.numero} ya tenía una rampa modificada (otra herramienta o un perfil de color); "
                "al salir se restaurará esa.", AVISO, 20,
            )
        self._arranque_activo = self._arranque.esta_activado()
        if self._arranque_activo and not self._arranque.apunta_a_algo_que_existe():
            self.panel.mensaje("El acceso directo de «Iniciar con Windows» apunta a un programa que ya no existe: "
                               "desactívalo y vuelve a activarlo desde el menú de la bandeja.", AVISO, 30)
        self._actualizar_info()
        self.rampas_cambiaron()  # aplica lo guardado: el perfil activo y los fijos
        if not self._oculto:
            self.panel.mostrar()
        self.raiz.after(INTERVALO_COLA_MS, self._procesar_cola)

    def _crear_aplicador(self) -> None:
        extra = {} if self._intervalo_vigilancia is None else {"intervalo_vigilancia": self._intervalo_vigilancia}
        self.aplicador = Aplicador(
            self.sesion, lambda aviso: self.cola.put(("aviso", aviso)), leer=self._leer, listar=self._listar, reloj=self._reloj, **extra,
        )
        self.aplicador.iniciar()

    def ejecutar(self) -> int:
        """Arranca y atiende hasta que se sale. Devuelve el código de salida."""
        if not self.iniciar():
            return 0
        try:
            self.raiz.mainloop()
        finally:
            self._parar_todo()
            if self._raiz_dada is None:
                try:
                    self.raiz.destroy()
                except tk.TclError:
                    pass
        return 0

    # -- Controlador del panel -----------------------------------------------------------------------------------------------------
    def rampas_cambiaron(self) -> None:
        if self.aplicador is not None and not self._cerrando:
            self.aplicador.pedir(self.estado.rampas())
        self._actualizar_info()

    def persistir(self) -> None:
        try:
            perfiles.guardar_en(self.estado.conf_persistible(), self.ruta_config)
        except OSError as e:
            if self.panel is not None:
                self.panel.mensaje(f"No se pudo guardar la configuración: {e}", PELIGRO, 15)

    def ocultar_panel(self) -> None:
        self.panel.ocultar()
        if not self._avisado_ocultar and self.bandeja is not None:
            self._avisado_ocultar = True
            self.bandeja.avisar("Vislumbra sigue en marcha", "Está en la bandeja del sistema. Clic en el icono para abrir el panel.")

    def salir(self) -> None:
        """Salida ordenada: preguntar por lo no guardado, guardar, parar el hilo, restaurar y cerrar."""
        if self._cerrando:
            return
        if self.estado.sin_guardar():
            self.panel.mostrar()
        if not self.panel.confirmar_salida():
            return
        self._cerrando = True
        self.persistir()
        self._parar_todo()

    # -- estado de la bandeja ------------------------------------------------------------------------------------------------------
    def _actualizar_info(self) -> None:
        e = self.estado
        self._info = tray.InfoBandeja(
            activo_on=e.activo_on, perfil_activo=e.activo, perfiles=tuple(e.nombres()), ab=e.ab and e.activo_on,
            grupos=tuple(e.grupos()), arranque=self._arranque_activo,
        )
        if self.bandeja is not None:
            self.bandeja.actualizar()

    # -- hilos ----------------------------------------------------------------------------------------------------------------------------
    def _accion_de_bandeja(self, accion: str | None, argumento: str | None) -> None:
        self.cola.put(("bandeja", accion, argumento))  # hilo de pystray: solo encola

    def _bucle_eventos(self) -> None:
        nombres = ("mostrar", "desactivar", "peticion", "parar")
        eventos = [self._eventos[n] for n in nombres]
        while True:
            try:
                i = sistema.esperar_alguno(eventos, None)
            except sistema.ErrorSistema:
                return
            if nombres[i] == "parar":
                return
            self.cola.put((nombres[i],))

    def _procesar_cola(self) -> None:
        try:
            while True:
                try:
                    tarea = self.cola.get_nowait()
                except queue.Empty:
                    break
                self._despachar(tarea)
        finally:
            if self._corriendo:
                self.raiz.after(INTERVALO_COLA_MS, self._procesar_cola)

    def _despachar(self, tarea: tuple) -> None:
        tipo = tarea[0]
        if tipo == "mostrar":
            self.panel.mostrar()
        elif tipo == "desactivar":
            self._desactivar_por_reset()
        elif tipo == "peticion":
            self._atender_peticion()
        elif tipo == "aviso":
            self._atender_aviso(tarea[1])
        elif tipo == "bandeja":
            self._atender_bandeja(tarea[1], tarea[2])

    # -- acciones --------------------------------------------------------------------------------------------------------------------------
    def _refrescar_todo(self, persistir: bool = False) -> None:
        self.panel.refrescar()
        self.rampas_cambiaron()
        if persistir:
            self.persistir()

    def _atender_bandeja(self, accion: str | None, argumento: str | None) -> None:
        e = self.estado
        try:
            if accion == tray.MOSTRAR_OCULTAR:
                self.panel.ocultar() if self.panel.visible else self.panel.mostrar()
            elif accion == tray.ALTERNAR_ACTIVO:
                e.poner_activo(not e.activo_on)
                self._refrescar_todo()
            elif accion == tray.PERFIL and argumento is not None:
                e.cambiar_activo(argumento)
                self._refrescar_todo(persistir=True)
            elif accion == tray.SIGUIENTE:
                e.mover_activo(+1)
                self._refrescar_todo(persistir=True)
            elif accion == tray.COMPARAR:
                if e.activo_on:
                    e.alternar_ab()
                    self._refrescar_todo()
            elif accion == tray.ARRANQUE:
                self._alternar_arranque()
            elif accion == tray.SALIR:
                self.salir()
        except perfiles.ErrorPerfil as err:
            self.panel.mensaje(str(err), PELIGRO)

    def _alternar_arranque(self) -> None:
        """«Iniciar con Windows»: crea o borra el acceso directo de la carpeta Inicio (sin registro)."""
        try:
            if self._arranque.esta_activado():
                self._arranque.desactivar()
                texto = "Vislumbra ya no se iniciará con Windows."
            else:
                self._arranque.activar()
                texto = "Vislumbra se iniciará con Windows (acceso directo en la carpeta Inicio, solo el icono)."
            self.panel.mensaje(texto, TEXTO_SUAVE, 10)
        except self._arranque.ErrorArranque as err:
            self.panel.mensaje(str(err), PELIGRO, 15)
        self._arranque_activo = self._arranque.esta_activado()
        self._actualizar_info()

    def _desactivar_por_reset(self) -> None:
        """``--reset`` desde la terminal: la app suelta la pantalla y se queda desactivada."""
        self.estado.poner_activo(False)
        self._refrescar_todo()
        self.panel.mensaje("Desactivado por --reset: pantalla original. Pulsa «Activo» para volver a aplicar.", AVISO, 20)
        if self.bandeja is not None:
            self.bandeja.avisar("Vislumbra desactivado", "Se aplicó --reset desde la terminal.")

    def _atender_peticion(self) -> None:
        """``--perfil`` desde la terminal: lee y borra ``peticion.txt`` y cambia el perfil activo."""
        try:
            texto = self.ruta_peticion.read_text(encoding="utf-8").strip()
            self.ruta_peticion.unlink(missing_ok=True)
        except OSError:
            return
        try:
            if texto == PETICION_SIGUIENTE:
                nombre = self.estado.mover_activo(+1)
            elif texto.startswith(PETICION_PERFIL):
                self.estado.cambiar_activo(texto[len(PETICION_PERFIL):])
                nombre = self.estado.activo
            else:
                self.panel.mensaje("Petición de la terminal no reconocida.", PELIGRO)
                return
        except perfiles.ErrorPerfil as err:
            self.panel.mensaje(str(err), PELIGRO)
            return
        self._refrescar_todo(persistir=True)
        self.panel.mensaje(f"Perfil cambiado desde la terminal: «{nombre}».", TEXTO_SUAVE)
        if self.bandeja is not None:
            self.bandeja.avisar("Perfil cambiado", f"Perfil activo: {nombre}")

    def _atender_aviso(self, a: Aviso) -> None:
        if a.tipo == "aplicado":
            return
        if a.tipo == "monitores":
            self._recrear_sesion()
            return
        color_ = PELIGRO if a.tipo in ("rechazo", "error") else AVISO
        prefijo = "Windows no aceptó la rampa: " if a.tipo == "rechazo" else ""
        self.panel.mensaje(prefijo + a.mensaje, color_, 15)
        if a.tipo == "conflicto" and self.bandeja is not None:
            self.bandeja.avisar("Conflicto con otra herramienta de color", a.mensaje)

    def _recrear_sesion(self) -> None:
        """Cambió la lista de monitores: se restaura lo que se pueda y se vuelve a empezar con la lista nueva."""
        if self._cerrando:
            return
        self.aplicador.parar()
        try:
            self.sesion.cerrar()
        except display.ErrorPantalla as e:
            self.panel.mensaje(str(e), PELIGRO)
        monitores = self._listar()
        if not monitores:
            self.panel.mensaje("No se encuentra ningún monitor activo. Vislumbra está en pausa.", PELIGRO, 30)
            return
        self.sesion = self._crear_sesion(monitores)
        self.sesion.iniciar()
        self.estado.actualizar_monitores(monitores)
        self._crear_aplicador()
        self._refrescar_todo()
        self.panel.mensaje("Cambió la lista de monitores: se han vuelto a aplicar los perfiles.", AVISO, 15)
        if self.bandeja is not None:
            self.bandeja.avisar("Cambió la lista de monitores", "Vislumbra ha vuelto a aplicar los perfiles guardados.")

    # -- cierre -------------------------------------------------------------------------------------------------------------------------------
    def _excepcion_tk(self, tipo, valor, traza) -> None:
        if issubclass(tipo, (KeyboardInterrupt, SystemExit)):  # Ctrl+C o cierre de la consola: la sesión ya restauró
            self._cerrando = True
            self._parar_todo()
            return
        print("Error interno:", file=sys.stderr)
        traceback.print_exception(tipo, valor, traza, file=sys.stderr)
        if self.panel is not None:
            try:
                self.panel.mensaje(f"Error interno: {valor}", PELIGRO, 15)
            except tk.TclError:
                pass

    def _parar_todo(self) -> None:
        """Cierre ordenado e idempotente: aplicador, sesión (restaura), bandeja, hilo de eventos, mutex y bucle de Tk.

        Cada paso va aparte: si uno falla, los demás se hacen igualmente (lo importante es restaurar y liberar).
        """
        self._cerrando = True
        self._corriendo = False

        def paso(que: str, accion) -> None:
            try:
                accion()
            except Exception as e:  # noqa: BLE001 - al cerrar no debe quedar nada a medias
                print(f"Aviso: no se pudo {que}: {e}", file=sys.stderr)

        if self.aplicador is not None:
            paso("parar el aplicador", self.aplicador.parar)
        if self.sesion is not None:
            paso("restaurar la pantalla", self.sesion.cerrar)
        if self.bandeja is not None:
            paso("quitar el icono de la bandeja", self.bandeja.detener)
            self.bandeja = None
        if "parar" in self._eventos:
            paso("avisar al hilo de eventos", self._eventos["parar"].activar)
        if self._hilo_eventos is not None:
            paso("esperar al hilo de eventos", lambda: self._hilo_eventos.join(2.0))
            self._hilo_eventos = None
        for ev in list(self._eventos.values()):
            paso("cerrar un evento", ev.cerrar)
        self._eventos = {}
        if self._mutex is not None:
            paso("liberar la instancia única", self._mutex.cerrar)
            self._mutex = None
        if self.raiz is not None:
            paso("salir del bucle de la interfaz", self.raiz.quit)


# --- Lado de la terminal ------------------------------------------------------------------------------------------------------------
def hay_app_abierta(prefijo: str = sistema.PREFIJO) -> bool:
    """¿Hay otra instancia en marcha? Se comprueba abriendo uno de sus eventos con nombre (no crea nada)."""
    ev = sistema.Evento.abrir(sistema.nombres(prefijo)["mostrar"])
    if ev is None:
        return False
    ev.cerrar()
    return True


def _activar(clave: str, prefijo: str) -> bool:
    ev = sistema.Evento.abrir(sistema.nombres(prefijo)[clave])
    if ev is None:
        return False
    ev.activar()
    ev.cerrar()
    return True


def pedir_desactivar(prefijo: str = sistema.PREFIJO) -> bool:
    """Le pide a la app abierta que suelte la pantalla (para ``--reset``). ``False`` si no hay app."""
    return _activar("desactivar", prefijo)


def pedir_perfil(peticion: str, ruta: Path | None = None, prefijo: str = sistema.PREFIJO) -> bool:
    """Escribe ``peticion.txt`` y avisa a la app abierta. ``False`` si no hay app."""
    if not hay_app_abierta(prefijo):
        return False
    destino = ruta or ruta_peticion()
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(peticion + "\n", encoding="utf-8")
    return _activar("peticion", prefijo)
