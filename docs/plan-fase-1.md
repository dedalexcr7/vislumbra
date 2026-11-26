# Plan de la fase 1 — Núcleo (`color.py`, `display.py` y orden de terminal)

**Estado: aprobado por el autor.** Las seis decisiones del final se aprobaron con la opción recomendada. Lo ejecuta una sesión de creación; no hace falta preguntar nada más salvo que algo de lo verificado cambie.

## 0. Lo verificado al planificar
- El repositorio estaba limpio tras la fase 0; `vislumbra/` y `tests/` no existían.
- `.venv` usa Python 3.10.11 con `pystray`, `keyboard` y `Pillow`. **`pytest` no está instalado.**
- `EnumDisplayDevicesW` + `CreateDCW("DISPLAY", nombre)` + `GetDeviceGammaRamp` funcionan desde `ctypes`.
- El equipo de pruebas tiene **3 monitores activos en 2 GPU** (portátil con gráficos híbridos) y 17 entradas inactivas de adaptadores virtuales. Hay que filtrar por `ATTACHED_TO_DESKTOP` (0x1).
- Las rampas leídas eran la identidad exacta: `ramp[i] = i·257`, con `ramp[255] = 65535`.
- Con la fórmula y la escala provisional de abajo (cálculo, no pantalla): la identidad sale exacta; los valores de referencia del autor (0/5/1,7 y 0/5/2,5) dan rampas monótonas con rango completo; la esquina «brillo +125, contraste −82» deja casi todo blanco y «brillo −125, contraste −82» casi todo negro (rango de salida del 16 %).

## 1. Archivos y orden de implementación
| # | Archivo | Responsabilidad |
|---|---|---|
| 1 | `requirements-dev.txt`, `pytest.ini` | `pytest` (MIT) solo para desarrollo; `testpaths = tests`, `pythonpath = .` y la opción `--con-pantalla` |
| 2 | `vislumbra/__init__.py` | Solo `__version__ = "0.1.0"` |
| 3 | `vislumbra/color.py` + `tests/test_color.py` | Funciones puras, sin `ctypes` ni pantalla |
| 4 | `vislumbra/display.py` | Toda la E/S con Windows (`gdi32` y `user32` vía `ctypes`) |
| 5 | `vislumbra/__main__.py` + `tests/test_cli.py` | Orden de terminal |
| 6 | `README.md` | Uso de la orden y qué hacer si algo sale mal (solo ejemplos genéricos) |

- **Desviación de `PLAN.md`:** el cálculo de canales va en `color.py`, no en `display.py`. Actualizar `PLAN.md` al cerrar la fase.
- **Cabecera de cada archivo nuevo:** `# SPDX-License-Identifier: GPL-3.0-or-later`, sin nombre de autor (el aviso de copyright sigue pendiente).
- **Kelvin → RGB:** escribirlo desde la aproximación pública de Tanner Helland, citándola en un comentario. No copiar código de otros proyectos por sus licencias.

## 2. `color.py`: fórmula, tipos y límites
```python
@dataclass(frozen=True)
class AjusteCanal:
    brillo: float = 0.0      # unidades de usuario; 0 = neutro
    contraste: float = 0.0
    gamma: float = 1.0       # 1.0 = neutro

@dataclass(frozen=True)
class Ajuste:
    r: AjusteCanal = AjusteCanal(); g: AjusteCanal = AjusteCanal(); b: AjusteCanal = AjusteCanal()
    temperatura: float = 6500.0
    @classmethod
    def uniforme(cls, brillo=0.0, contraste=0.0, gamma=1.0, temperatura=6500.0) -> "Ajuste": ...

Rampa = list[int]   # 768 enteros 0..65535: 256 de R, 256 de G y 256 de B

def validar_ajuste(a: Ajuste) -> None                      # lanza ValorFueraDeRango
def brillo_a_desplazamiento(brillo: float) -> float        # b = brillo * BRILLO_POR_UNIDAD
def contraste_a_factor(contraste: float) -> float          # c = 2 ** (contraste / CONTRASTE_ESCALA)
def kelvin_a_rgb(kelvin: float) -> tuple[float, float, float]
def curva_canal(a: AjusteCanal, factor_temp: float = 1.0) -> list[int]   # 256 valores
def construir_rampa(a: Ajuste) -> Rampa                    # valida el ajuste y construye
def rampa_identidad() -> Rampa
def validar_rampa(r: Sequence[int]) -> None                # lanza RampaIlegible
```

**Fórmula de `curva_canal`**, para `i` de 0 a 255 y `v = i/255`:
1. `v = v ** (1/gamma)`
2. `v = (v − 0.5) · c + 0.5`
3. `v = v + b`
4. `v = v · factor_temp`
5. recorte a [0, 1] y `round(v · 65535)`

**Conversión de escala** (provisional; la calibración definitiva es de la sesión de test). Las constantes van agrupadas arriba de `color.py`:

| Parámetro | Rango de usuario | Conversión inicial |
|---|---|---|
| Brillo | −125 a 125 | `b = brillo / 250` (±0,5) |
| Contraste | −82 a 82 | `c = 2 ** (contraste / 50)` (0,32 a 3,1) |
| Gamma | 0,5 a **4,0** | (RivaTuner llega a 6,0; se amplía solo si hace falta) |
| Temperatura | 2500 a 10000 K | 6500 K = neutro |

- **Contraste exponencial:** `c` siempre es positivo y la curva siempre monótona, aunque se recalibre la escala.
- **Temperatura:** factor = `rgb(T)/rgb(6500)` dividido por su máximo. El neutro es (1, 1, 1) y ningún canal supera 1. Valores de ejemplo (cálculo con Helland, no vistos en pantalla): 2500 K → (1,0; 0,626; 0,28); 4000 K → (1,0; 0,81; 0,664); 10000 K → (0,776; 0,841; 1,0).

**Barrera final contra pantalla ilegible.** Los rangos solos no bastan (ver las esquinas de la sección 0). `validar_rampa` lanza `RampaIlegible` si, en cualquier canal:
- no es monótona no decreciente;
- el rango de salida `ramp[255] − ramp[0]` es menor del **25 %** de 65535;
- el valor central `ramp[128]` queda fuera del 10 %–90 %.

Umbrales propuestos, a afinar en test. `display.aplicar_rampa` y la orden la llaman **antes** de tocar la pantalla.

## 3. `display.py`: la rampa de Windows
```python
@dataclass(frozen=True)
class Monitor:
    numero: int          # 1, 2, 3… solo activos, como lo muestra --list
    dispositivo: str     # r"\\.\DISPLAY6"
    adaptador: str
    nombre: str | None   # segundo nivel de EnumDisplayDevices; puede faltar
    principal: bool

class ErrorPantalla(Exception) ; class MonitorNoEncontrado(ErrorPantalla) ; class RampaRechazada(ErrorPantalla)

def listar_monitores() -> list[Monitor]
def elegir_monitores(seleccion: str, monitores: list[Monitor]) -> list[Monitor]  # "principal" | "todos" | "N"
def leer_rampa(m: Monitor) -> Rampa
def aplicar_rampa(m: Monitor, r: Rampa) -> bool   # True si la lectura posterior coincide
def restaurar_identidad(monitores: list[Monitor]) -> None
class SesionGamma:  # gestor de contexto: guarda el original y lo restaura, de forma idempotente
```
- **Enumeración:** `EnumDisplayDevicesW(None, i)` filtrando por `ATTACHED_TO_DESKTOP` y excluyendo `MIRRORING_DRIVER`. Contexto de dispositivo con `CreateDCW("DISPLAY", dispositivo, ...)` y `DeleteDC` en un `finally`.
- **`ctypes`:** declarar `argtypes` y `restype` de todas las funciones (para que los `HDC` de 64 bits no se trunquen) y usar `use_last_error=True`.
- **Varios monitores:** por defecto, el **principal**. `--monitor todos` aplica en secuencia y, si uno falla, deshace los ya aplicados en esa llamada. `--reset` sin `--monitor` actúa sobre **todos**.
- **Original y reset:** al arrancar la sesión guarda la rampa real de cada monitor y la restaura al salir. Si ese original no es la identidad, avisa («otra herramienta o un perfil de color ya la había modificado»). `--reset` aplica siempre la **identidad** y lo dice, porque no puede conocer un original perdido.
- **Restauración al salir:** `SesionGamma.restaurar()` con `atexit`, manejadores de `SIGINT`, `SIGTERM` y `SIGBREAK`, y `SetConsoleCtrlHandler` para `CTRL_CLOSE_EVENT`, cierre de sesión y apagado. Conservar la referencia del callback para que no la recoja el recolector de basura.
- **Si `SetDeviceGammaRamp` devuelve `False`:** lanzar `RampaRechazada` con el monitor, el código de `GetLastError` si no es 0 y el consejo de usar un ajuste más suave. **No sugerir el registro de Windows** (es la fase 5 y requiere preguntar).
- **Si devuelve `True` pero el controlador la limita:** leer la rampa de vuelta y comparar (tolerancia por determinar). Si difiere, aviso, no error.
- **Si el proceso muere sin restaurar** (`taskkill /F`, fallo, corte de luz): se asume que la rampa queda hasta que otra cosa la cambie, o hasta `--reset` o reiniciar. Mitigación: validador, `--duration`, aviso de arranque y `--reset`.

## 4. Comportamiento de `--gamma`
**Decidido: B por defecto** (el proceso se queda vivo hasta Ctrl+C y restaura al salir), con `--duration S` (aplica, espera S segundos y restaura) y `--persist` (aplica y termina sin restaurar, avisándolo).
- A (aplica y termina) es más simple, pero si el proceso era lo que mantenía la rampa esta se pierde, y no restaura sola.
- B deshace solo al cerrar, es seguro para probar a mano y es el mismo modelo que la futura bandeja.
- Si la sesión de test comprueba que la rampa **no** sobrevive al proceso, se retira `--persist`.

## 5. Orden de terminal
```
python -m vislumbra --list
python -m vislumbra --simulate --gamma 1.4
python -m vislumbra --gamma 1.4 [--brightness B] [--contrast C] [--temp K]
                    [--channel all|r|g|b] [--monitor principal|todos|N] [--duration S | --persist]
python -m vislumbra --reset [--monitor ...]
```
- Opciones: `--list`, `--monitor`, `--gamma`, `--brightness`, `--contrast`, `--temp`, `--channel`, `--reset`, más `--simulate`, `--duration` y `--persist`. Decimales con punto o con coma. `main(argv: list[str] | None = None) -> int` para poder probarla.
- Reglas: se exige al menos un ajuste salvo con `--list` o `--reset`; `--reset` no se mezcla con ajustes; `--duration` y `--persist` son excluyentes; `--channel r|g|b` aplica brillo, contraste y gamma solo a ese canal y deja los otros neutros; `--temp` con `--channel` es error.
- `--simulate`: valida y muestra los valores de la rampa en 0, 64, 128, 192 y 255 por canal, **sin tocar la pantalla**.
- Salida en español: subclase de `ArgumentParser` que sobrescribe `error`, con `add_help=False`, `-h/--help` propio y grupos con títulos en español (los textos por defecto de `argparse` salen en inglés).
- Códigos de salida: 0 correcto; 1 valor inválido o rampa ilegible; 2 uso incorrecto; 3 error de Windows o de monitor.

Mensajes de ejemplo:
- `Error: --gamma 7 está fuera del rango permitido (0,5 a 4,0).`
- `Error: este ajuste dejaría la pantalla casi ilegible (rango de salida demasiado bajo). No se ha aplicado nada.`
- `Error: Windows ha rechazado la rampa en el monitor 2. Prueba con valores más suaves.`
- `Error: el monitor 5 no existe. Usa --list para ver los disponibles.`
- `Aplicado al monitor 1 (principal): gamma 1,40. Pulsa Ctrl+C para restaurar.`
- `Aviso: el monitor 2 aceptó la rampa, pero la lectura posterior no coincide; el controlador puede estar limitándola.`

## 6. Tests con pytest
**Los escribe la sesión de creación (sin tocar la pantalla):**
- `test_color.py`:
  - identidad exacta (`i·257`);
  - gamma > 1 sube los medios, gamma < 1 los baja, y los extremos 0 y 65535 quedan fijos;
  - contraste y brillo en el sentido esperado, con recorte correcto;
  - monotonía y rango 0–65535 en una rejilla de combinaciones (`itertools.product`);
  - `kelvin_a_rgb(6500) == (1, 1, 1)`, canales en (0, 1] y tendencias correctas (a 3000 K, B < R; a 10000 K, R < B);
  - `NaN`, `inf` y `gamma ≤ 0` rechazados con mensaje en español;
  - `validar_rampa` rechaza rampas planas, invertidas, no monótonas y demasiado oscuras o claras;
  - **invariante de seguridad:** toda combinación de la rejilla o pasa `validar_rampa` o lanza `RampaIlegible`, y nunca produce una rampa que viole la monotonía o el rango;
  - los valores de referencia del autor (0/5/1,7 y 0/5/2,5) y el neutro siempre validan.
- `test_cli.py`: con `monkeypatch` sobre `display`, sin tocar la pantalla real. Análisis de argumentos, códigos de salida, mensajes en español, incompatibilidades y `--simulate`.

**Los escribe la sesión de test (`test_display.py`):**
- *Seguros por defecto*, con salto automático si no hay monitores: `listar_monitores()` devuelve al menos 1 con exactamente 1 principal, y `leer_rampa` devuelve 768 enteros en rango y monótonos.
- *Escritura, solo con `pytest --con-pantalla`:* un fixture lee la rampa de todos los monitores antes y la restaura siempre en el `finalizer`, incluso si el test falla. Identidad → lectura == identidad; gamma suave (1,2) → lectura ≈ rampa construida (tolerancia a medir); `restaurar()` deja el original; una excepción dentro de `SesionGamma` restaura.
- *Sondeo manual* con el usuario mirando: aplicar 1 s ajustes cada vez más fuertes (gamma 1,5, 2, 3, 4), anotando cuáles rechaza Windows y cuáles limita el controlador en la lectura.

## 7. Comprobación mínima y lo que queda para test
**La sesión de creación comprueba solo:**
1. `python -c "import vislumbra"` y `pytest -q` (tests puros y de la orden), en verde.
2. `python -m vislumbra --list`, que debe mostrar los monitores activos (3 en el equipo de pruebas).
3. `python -m vislumbra --simulate --gamma 1.4`, sin tocar la pantalla.
4. **Un único cambio real**, con el usuario mirando: `--gamma 1.2 --duration 5`, que debe volver solo a normal. Después, `--reset`.
5. `git grep -nE "C:\\\\Users|[A-Za-z0-9._-]+@[A-Za-z0-9.-]+\.[a-z]{2,}"` sin resultados (privacidad).

**Queda para la sesión de test:** los tests de pantalla y el sondeo de límites; la persistencia tras terminar el proceso (decide si se conserva `--persist`); el cierre de la ventana de la terminal con el ajuste aplicado; `--monitor 2` y `todos` en la configuración híbrida; la calibración de la escala.

**Lista de comprobación visual para el usuario** (abrir antes una segunda terminal con `python -m vislumbra --reset` ya escrito, por si hace falta):
1. `--list` muestra los monitores correctos, con el principal marcado.
2. `--gamma 1.7 --contrast 5 --duration 10` y luego `--gamma 2.5`: se ven más detalles en lo oscuro, sin tinte raro ni bandas visibles.
3. `--brightness −40` y `+40`: la imagen sube y baja sin volverse blanca o negra.
4. `--contrast`: ¿un paso de 1–2 unidades cambia **demasiado**, **poco** o **bien**? Anotarlo.
5. `--channel r --gamma 1.5`: tinte rojizo. `--temp 4000`: más cálido. `--temp 9000`: más frío.
6. `--monitor 2`: solo cambia ese monitor. `--monitor todos`: cambian todos.
7. Ctrl+C devuelve la imagen original. Un ajuste ilegible (p. ej. `--brightness 125 --contrast -82`) se rechaza sin cambiar nada.
8. Opcional: abrir un juego en modo sin bordes con el ajuste aplicado y ver si persiste.

## 8. Riesgos, reversión e hipótesis
| Riesgo | Reversión |
|---|---|
| Pantalla fea o ilegible | Ctrl+C, `--duration` o `--reset`. Si no hay terminal visible, reiniciar Windows (hipótesis) |
| Proceso muerto sin restaurar | `--reset`, que aplica la identidad |
| Windows o el controlador rechazan o limitan la rampa | Error claro y sin cambios. Salir de esa limitación es la fase 5 y se pregunta antes |
| Fallo a medias con varios monitores | Se deshacen los ya aplicados |
| Rampa original no era la identidad | Aviso al arrancar; `--reset` recuerda que aplica la identidad |

Todo el código es nuevo y va en commits pequeños, así que se revierte con `git revert`. **No se toca el registro de Windows, ni drivers, ni nada fuera del repositorio.**

**Hipótesis sin verificar** (las prueba la sesión de test):
- Las reglas exactas con las que Windows rechaza una rampa.
- Que la rampa persista tras terminar el proceso.
- Que `atexit` y `SetConsoleCtrlHandler` restauren al cerrar la ventana de Windows Terminal.
- Que la lectura posterior refleje lo aplicado de verdad.
- Que el nombre del monitor salga del segundo nivel de `EnumDisplayDevices`.
- Que la rampa se comporte igual en ambas GPU.
- Que la aproximación de Helland se vea bien.
- Los umbrales del validador y las constantes de escala.

## 9. Commits pequeños (en español, sin firmas de IA ni `Co-Authored-By`)
Cada commit deja los tests en verde. No hay `push` sin OK del usuario.
1. `Pruebas: añadir pytest como dependencia de desarrollo`
2. `color: tipos, constantes de rango y validación de ajustes`
3. `color: curva por canal, conversión de escala y rampa`
4. `color: temperatura de color (Kelvin a RGB)`
5. `color: validación de rampa legible`
6. `display: enumerar monitores y leer la rampa`
7. `display: aplicar rampa con verificación por lectura y restaurar identidad`
8. `display: sesión con restauración al salir (atexit, señales y cierre de consola)`
9. `orden: --list, --simulate y --reset`
10. `orden: ajustes de gamma, brillo, contraste, temperatura, canal y monitor`
11. `Documentación: uso de la orden y registro de la fase 1`

## 10. Decisiones aprobadas
1. `--gamma`: modo B (vivo y restaura al salir) con `--duration` y `--persist` opcional.
2. Monitor por defecto: el principal; `--reset` sobre todos.
3. Escala inicial: contraste exponencial, gamma máxima 4,0, brillo ±0,5.
4. Umbrales del validador: rango de salida ≥ 25 % y valor central entre 10 % y 90 %.
5. Cabecera de licencia: `GPL-3.0-or-later`, sin nombre.
6. `requirements-dev.txt` y `pytest.ini` aprobados.
