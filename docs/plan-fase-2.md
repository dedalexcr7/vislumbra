# Plan de la fase 2 — Panel, bandeja y perfiles

**Estado: aprobado por el autor.** Revisado tras la maqueta interactiva. El autor decidió dos cosas: **cada monitor sigue al perfil activo o tiene un perfil fijo**, y **la base de los perfiles entra en esta fase**. Los atajos globales van en la fase 3. Las siete decisiones pendientes de §11 se aprobaron con la opción recomendada. Lo ejecuta una sesión de creación.

## 0. Punto de partida (verificado al planificar, sin tocar la gamma)
- **Repositorio.** `main` en `f8c7095`. Solo hay un archivo sin versionar: el logo de la raíz.
- **Tests.** `pytest -q` da 212 en verde y 6 saltadas (las de pantalla).
- **Entorno.** `.venv` con Python 3.10.11 y **Tk 8.6.12** disponible, `pystray` 0.19.5 y `Pillow` 12.3.0. No hace falta ninguna dependencia nueva: el JSON de los perfiles usa la biblioteca estándar.
- **`pystray` en Windows** (leído en su código):
  - `run_detached()` arranca el bucle de mensajes en un hilo propio, y los clics del menú se ejecutan en ese hilo.
  - `notify()` usa el globo o la notificación de Windows.
  - Vuelve a poner el icono si se reinicia el Explorador.
- **Tiempos (medidos).**
  - `construir_rampa` tarda 0,56 ms.
  - `leer_rampa` tarda de 0,6 a 0,9 ms por monitor en los 3 monitores.
  - **La escritura no se ha medido.**
- **Límite de Windows (I-12).** Los datos encajan con esta regla: Windows rechaza la rampa si algún valor se aleja más de **32 768** (50 %) de la identidad.
  - 3250 K: desviación de 32 450, **aceptada**.
  - 3200 K: desviación de 33 266, **rechazada**.
  - Las 3 predicciones del test también encajan.
  - Hoy el validador acepta «3300 K + contraste −20» (52,7 %) y «3300 K + brillo −45» (54,5 %), que Windows rechazaría.
- **Desviación de los ajustes habituales** (cálculo):

  | Ajuste | Desviación |
  |---|---|
  | 0/7,5/1,7 | 19 % |
  | 0/7,5/2,5 | 33 % |
  | gamma 3 | 39 % |
  | gamma 4 | 47 % |
  | 3300 K | 48 % |
  | 4000 K | 34 % |
  | brillo ±100 | 27 % |
  | contraste ±40 | 15 % |

- **Logo.** PNG RGB de 1254×1254, **sin transparencia**, hecho con ChatGPT.
  - La loseta completa a 16 px deja el glifo diminuto.
  - Solo el glifo, con fondo transparente, se reconoce de 24 a 48 px y queda justo a 16 px.
- **Maqueta interactiva** (aprobada en aspecto por el autor): https://claude.ai/artifact/FuZBRyF2idJek2YLyuArRr. Es una simulación en el navegador y no toca la pantalla.
- **Pendiente de la fase 1:** P8 (juego en modo sin bordes), sin probar. La vigilancia de §5 cubre los dos casos: que el juego mantenga la rampa o que la reinicie.

## 1. Alcance
**Entra:**
- App en la bandeja con un panel.
- Brillo, contraste y gamma, con canales vinculados o separados, y la temperatura.
- Control fino y modo preciso (desde el panel).
- **Perfiles:** crear, guardar, guardar como, renombrar y borrar.
  - «Normal» viene incluido, no se modifica ni se borra.
  - Se guardan en `%APPDATA%\Vislumbra`.
- **Perfil activo** y **monitores:** cada monitor sigue al perfil activo o tiene un perfil fijo.
- **Cambiar de perfil:**
  - con ‹ › en el panel;
  - desde el menú de la bandeja («Perfil activo» y «Siguiente perfil»);
  - con `python -m vislumbra --perfil NOMBRE|siguiente`.
- Aplicación en vivo en un hilo aparte, con vigilancia que vuelve a aplicar la rampa.
- A/B, «Restablecer» con deshacer, y «Activo».
- Gráfico de la curva y margen de Windows.
- Confirmación de «Ajuste fuerte».
- Instancia única, y que `--reset` desactive la app abierta.
- Las incidencias I-12 e I-4 y, si se aprueba, I-5 e I-11b.

**No entra:**

| Queda fuera | Cuándo |
|---|---|
| Atajos globales de teclado (siguiente perfil, uno por perfil, A/B, modo preciso y emergencia) | fase 3 |
| Duplicar perfiles, reordenarlos, importarlos y exportarlos | fase 3 |
| Perfil por proceso | fase 4 |
| `.exe` y arranque con Windows | fase 6 |
| Brillo por hardware | sin fecha |

Al aprobar este plan, `PLAN.md` se actualiza para reflejar este reparto entre las fases 2 y 3.

## 2. Modelo de perfiles y monitores
- **Perfil:** nombre más ajuste: vinculado o no, brillo, contraste y gamma por canal, y temperatura.
  - **«Normal»** es especial. Un monitor en Normal **no se toca**: se le devuelve su rampa original.
  - Normal no se puede editar. Si el usuario mueve un deslizador mientras edita Normal, se crea «Perfil N» (sin guardar) y se asigna en lugar de Normal. Es lo que hace la maqueta.
- **Perfil activo:** hay uno, global. Lo siguen los monitores en «Sigue al perfil activo».
- **Asignación por monitor:** «sigue al activo» o «fijo: <perfil>». Ejemplo: los monitores 1 y 2 siguen al activo y el 3 tiene fijo «Código». Al cambiar el perfil activo, el monitor 3 no cambia.
- **Qué se edita.** Las pestañas de monitor eligen qué monitor se mira. Los deslizadores editan **el perfil que usa ese monitor**, ya sea el activo o su perfil fijo. Un cambio se aplica en vivo a **todos** los monitores que usan ese perfil.
- **Guardar.** Los cambios se aplican en vivo pero quedan «● sin guardar» hasta pulsar «Guardar».
  - «Guardar como…» crea otro perfil y devuelve el original a lo guardado.
  - Al salir con cambios sin guardar, la app pregunta: Guardar, Descartar o Cancelar.
  - **La asignación de los monitores y el perfil activo se guardan solos** (no son «el perfil»).
- **Borrar** pide confirmación. Los monitores fijos a ese perfil pasan a «sigue al activo». Si era el activo, el activo pasa a ser Normal.
- **Identificar los monitores.** La clave es el `DeviceID` del monitor (segundo nivel de `EnumDisplayDevices`), con `\\.\DISPLAYn` como respaldo, para que la asignación sobreviva a que cambie el número del monitor.
  - Ese identificador incluye un código del modelo. Solo se guarda en `%APPDATA%`, **nunca en el repositorio**.
  - Que sea estable tras reiniciar y tras desconectar y volver a conectar el monitor es una hipótesis que comprueba el test.
- **Archivo** `%APPDATA%\Vislumbra\config.json`, versión 1:
  ```json
  {"version": 1,
   "perfiles": [{"nombre": "Código", "vinculado": true,
                 "canales": {"r": {"brillo": -20, "contraste": 5, "gamma": 1.0}, "g": {...}, "b": {...}},
                 "temperatura": 6000}],
   "perfil_activo": "Código",
   "monitores": {"<clave>": {"asignacion": "activo"}, "<clave>": {"asignacion": "Código"}}}
  ```
  - Normal no se guarda, porque es fijo.
  - Se escribe de forma atómica: primero a un temporal y luego `os.replace`.
  - Si el archivo está dañado o tiene valores fuera de rango, se renombra a `config.dañado-<fecha>.json`, se arranca con Normal y se avisa. Nunca se aplica un ajuste inválido leído del disco.
  - Los nombres de perfil tienen de 1 a 40 caracteres, sin repetir (sin distinguir mayúsculas) y sin ser «Normal».

## 3. Archivos y responsabilidades
| Archivo | Qué hace | ¿Toca Windows? |
|---|---|---|
| `vislumbra/color.py` | Límite de desviación (I-12), validación sin el tinte (I-4) y `desviacion(r)` | no |
| `vislumbra/display.py` | `SesionGamma` con una rampa distinta por monitor; `Monitor.clave` (estable) | sí |
| `vislumbra/escala.py` (nuevo) | Funciones puras: posición del deslizador ↔ valor, pasos, formato y lectura con coma | no |
| `vislumbra/perfiles.py` (nuevo) | `Perfil`, `Configuracion` (perfiles, activo y asignaciones), validación y JSON atómico en `%APPDATA%` | solo el sistema de archivos |
| `vislumbra/estado.py` (nuevo) | Modelo del panel sin Tk: monitor mirado, perfil editado, canal, vincular, tope, ajuste fuerte, A/B, restablecer y deshacer, «sin guardar» y rampas por monitor | no |
| `vislumbra/aplicador.py` (nuevo) | Hilo que aplica `{monitor: rampa}` y vigila; recibe la sesión inyectada | a través de `display` |
| `vislumbra/sistema.py` (nuevo) | `ctypes`: instancia única, eventos con nombre, DPI y área de trabajo | sí, sin tocar la pantalla |
| `vislumbra/panel.py` (nuevo) | Tkinter: `Deslizador`, `GraficoCurva` y la ventana `Panel` | no |
| `vislumbra/tray.py` (nuevo) | Icono, menú (con el submenú de perfiles), estados y avisos | no |
| `vislumbra/app.py` (nuevo) | Conecta las piezas: arranque, hilos, colas, peticiones de la terminal y cierre ordenado | no |
| `vislumbra/__main__.py` | Sin argumentos abre la app; `--perfil`; `--reset` avisa a la app; los ajustes se rechazan si la app está abierta | — |
| `assets/` y `herramientas/generar_iconos.py` (nuevos) | Logo maestro e iconos generados por un script | — |

Las cabeceras siguen el formato de la fase 1: `SPDX-License-Identifier: GPL-3.0-or-later`, sin nombre.

## 4. Panel (como en la maqueta)
```
┌ Vislumbra ───────────────────────────────── ✕ ┐
│ Perfil activo  ‹  Oscuro  ›          [● Activo] │
│ [Monitor 1    ] [Monitor 2 · princ.] [Monitor 3] │
│  Oscuro (activo)  Oscuro (activo)     Código (fijo)
│ Monitor 2   (Sigue al perfil activo)(Perfil fijo)│
│ ┌ Editando «Oscuro» ● sin guardar               │
│ │ [Guardar] [Guardar como…] [Renombrar] [Borrar]│
│ │ [✓] Vincular canales          R, G y B a la vez│
│ │ Brillo      ├───●───┤ − [ 0,0 ] +             │
│ │ Contraste   ├────●──┤ − [ 7,5 ] +             │
│ │ Gamma       ├─────●─┤ − [1,70 ] +             │
│ │ Temperatura ├───●───┤ − [6500 K] +            │
│ └───────────────────────────────────────────────│
│ ┌curva┐ [A/B] [Restablecer] [ ] Modo preciso     │
│ └─────┘ Margen de Windows ▓▓░ 19 % de 50 %       │
│ «Oscuro» en los monitores 1 y 2 · «Código» en el 3 │
└─────────────────────────────────────────────────┘
```
- **Ventana.**
  - Pequeña, de tipo herramienta y con «siempre encima» activado.
  - La primera vez se abre junto a la bandeja.
  - La ✕ la oculta en la bandeja.
  - Tema oscuro y Segoe UI.
  - Consciente del DPI del sistema (`SetProcessDpiAwareness(1)`); el modo por monitor se descarta porque Tk 8.6 no cambia de escala al pasar de un monitor a otro.
- **Pestañas de monitor.** Muestran el perfil de cada monitor y si es activo o fijo, como en la maqueta.
  - Con un solo monitor no salen pestañas.
  - Los nombres reales de los monitores no se muestran. Se usa «Monitor N» y «principal», igual que `--list` sin modelos.
- **Canales.**
  - Al desvincular, cada canal parte del valor actual.
  - Al volver a vincular con canales distintos, se pide confirmación y se usan los valores del canal visible.
  - La temperatura es global en cada perfil.
- **A/B y «Activo»** actúan sobre todos los monitores. A/B alterna entre el ajuste y la pantalla normal (botón o barra espaciadora con el panel enfocado). «Activo» apagado devuelve las rampas originales y para la vigilancia.
- **Restablecer** pone en neutro el perfil editado (sin guardar). Durante 10 s ofrece «Deshacer».
- **Ajuste fuerte** (desviación > 40 %, por ejemplo gamma > ~3,1 o temperatura < ~3700 K): se aplica y aparece «se deshará en 10 s · [Mantener]».
- **Línea de estado.** Resume qué perfil hay en cada monitor y muestra los avisos (original modificado, conflicto, tope y errores).
- **Al arrancar** se aplica lo guardado: el perfil activo en los monitores que lo siguen y los fijos en los suyos (ver la decisión 3). La primera vez todo está en Normal y no se escribe nada. Si la rampa original de un monitor no era la identidad, se avisa y se ofrece «Usar la neutra como original».

### Control fino
| Parámetro | Rango | Escala (neutro en el centro) | Rueda o flechas | Shift | Ventana del modo preciso | Decimales |
|---|---|---|---|---|---|---|
| Brillo | −100 a 100 | cuadrática (a media carrera, ±25) | 1 | 0,1 | ±10 | 1 |
| Contraste | −40 a 40 | cuadrática (a media carrera, ±10) | 0,5 | 0,1 | ±4 | 1 |
| Gamma | 0,5 a 4,0 | logarítmica a tramos (de 0,5 a 1 y de 1 a 4) | 0,05 | 0,01 | ±0,25 | 2 |
| Temperatura | 3300 a 10000 K | lineal en mired a tramos | 100 K | 10 K | ±500 K | 0 |

- **Arrastrar con Shift** mueve 10 veces más despacio. **Doble clic** devuelve el valor a neutro. El campo numérico admite coma y punto.
- **Tope:** si un movimiento daría una rampa que el validador rechaza, el deslizador se para en el último valor válido (por bisección) y dice el motivo.
- **Modo preciso:** cada deslizador cubre una ventana lineal alrededor del valor y se recentra al soltar. La rueda usa los pasos finos. Sustituye al «zoom de rango» de `PLAN.md`.
- **Valores provisionales:** se calibran en el test con A/B. Umbrales notados en la fase 1: brillo 2, contraste 2 y gamma 0,1.

## 5. Hilos, aplicación, vigilancia y seguridad
```
Hilo principal ─ Tk mainloop ─ único que toca widgets
   ▲ cola_ui (Tk la revisa con after(50))
   ├── Hilo de pystray (run_detached): menú → cola_ui
   ├── Hilo de eventos: WaitForMultipleObjects(mostrar, desactivar, peticion, parar) → cola_ui
   └── Hilo aplicador: espera «hay cambio», con un tiempo máximo de 2 s
          ├── cambio → {monitor: rampa} → valida y aplica → resultado → cola_ui
          └── vence el tiempo → vigilancia
```
- **Último gana.** El panel deja el estado deseado (`{monitor: rampa}`) en una ranura. El aplicador aplica siempre el último, con un intervalo mínimo de 15 ms. La interfaz nunca espera a Windows.
- **`SesionGamma` por monitor.** Se abre sobre **todos** los monitores y guarda sus originales. Métodos nuevos:
  - `aplicar_por_monitor({numero: rampa})` aplica a cada monitor su rampa.
  - `restaurar(solo=…)` restaura solo los indicados.

  Un monitor en Normal se restaura a su original. Si uno falla, se deshacen los de esa llamada. La API actual se mantiene, así que la orden de terminal no cambia. La sesión se crea en el hilo principal (señales, `atexit` y consola).
- **Si Windows rechaza** (no debería pasar, porque el validador ya modela el límite): el aplicador vuelve a aplicar la última rampa aceptada de ese monitor y el panel muestra el motivo.
- **Vigilancia cada 2 s** (si la app está activa):
  - Lee las rampas de los monitores tocados y vuelve a aplicar la que no coincida (tolerancia 64).
  - Si tiene que hacerlo **más de 5 veces en 60 s**, deja de hacerlo, marca «en conflicto» y avisa.
  - Si cambia la lista de monitores, restaura lo que pueda, vuelve a crear la sesión en el hilo principal y aplica las asignaciones guardadas por clave. Un monitor nuevo arranca siguiendo al perfil activo.
- **Instancia única:** un mutex `Local\…`.
  - Una segunda `python -m vislumbra` activa «mostrar» y termina.
  - Las órdenes de ajuste (`--gamma`, etc.) se niegan con código 3 si la app está abierta.
- **`--perfil NOMBRE|siguiente`.**
  - **Con la app abierta:** escribe la petición en `%APPDATA%\Vislumbra\peticion.txt` y activa el evento «petición». La app la lee, la borra y cambia el perfil activo. Si el nombre no existe, la orden falla con código 1 y la lista de perfiles.
  - **Sin la app:** aplica ese perfil como la orden de la fase 1. Se queda viva hasta Ctrl+C, y admite `--duration` y `--persist`.
- **`--reset` con la app abierta:**
  1. Activa «desactivar»: la app restaura sus originales, se desactiva y avisa.
  2. Aplica la identidad como siempre.

  **Es la salida de emergencia de la fase 2**, junto con «Activo» y «Salir». El atajo global llega en la fase 3.
- **Cierre ordenado:**
  1. Preguntar por los cambios sin guardar.
  2. Parar el aplicador.
  3. `sesion.cerrar()`.
  4. `icon.stop()`.
  5. `root.destroy()`.

  Desde la terminal, cerrarla restaura (P3).
- **`pythonw` sin consola:** `print` no falla. Al cerrar sesión se cuenta con `WM_SAVE_YOURSELF` de Tk (hipótesis). Si la app muere sin restaurar, la rampa se queda y el siguiente arranque lo avisa.
- **Nada de registro de Windows, drivers ni cambios del sistema.** Solo se escribe en `%APPDATA%\Vislumbra`.

## 6. Bandeja e icono
- **Icono:** solo el glifo, con fondo transparente, en 16 a 64 px, generado por `herramientas/generar_iconos.py` desde el logo maestro.
  - Hay una variante inactiva y un `vislumbra.ico` para la fase 6.
  - **No se redibuja el logo.** Si a 16 px no se distingue, se anota como incidencia.
- **Clic izquierdo:** muestra u oculta el panel.
- **Menú (como en la maqueta):**
  - Mostrar panel
  - Activo ✓
  - Perfil activo (uno por perfil, marcado el actual)
  - Siguiente perfil
  - Comparar (A/B)
  - Salir (restaura la pantalla)
- **Texto al pasar el ratón:** «Vislumbra · activo · Oscuro (1, 2) · Código (3)».
- **Avisos:** conflicto, cambio de monitores, desactivado por `--reset`, perfil cambiado desde la terminal, configuración dañada y la primera vez que se oculta.

## 7. Incidencias de la fase 1 que se resuelven aquí
- **I-12:** `DESVIACION_MAX = 32_000` en `validar_rampa`, sobre la rampa final. Es un margen bajo el 32 768 inferido; «3300 K», con 31 652, sigue siendo válido. El mensaje dice que se supera lo que Windows permite. Se añade la función `desviacion(r)` para el indicador.
- **I-4:** la legibilidad se juzga sobre la rampa sin el factor de temperatura. Sobre la rampa final solo se miran la monotonía y el límite de Windows.
- **I-5 e I-11b** (opcionales): error de uso en las opciones que se ignorarían en silencio y con `--monitor ""`.

## 8. Tests (los escribe la sesión de creación, sin tocar la pantalla)
- **`test_color.py`:**
  - I-12: los dos casos de 3300 K se rechazan; 3300 K, gamma 4 y las referencias siguen siendo válidas; la desviación de la identidad es 0.
  - I-4.
  - El invariante de seguridad sobre la rejilla.
- **`test_escala.py`:** ida y vuelta posición ↔ valor; neutro en el centro; extremos exactos; funciones monótonas; pasos; lectura de «1,7», «−3» y «abc».
- **`test_perfiles.py`**, en una carpeta temporal y nunca en el `%APPDATA%` real:
  - guardar y leer de ida y vuelta;
  - escritura atómica;
  - un archivo dañado o con valores fuera de rango se aparta y se avisa;
  - Normal no se edita ni se borra;
  - nombres únicos y válidos;
  - renombrar actualiza las asignaciones y el activo;
  - borrar pasa los fijos a «activo» y el activo a Normal;
  - «siguiente» da la vuelta.
- **`test_estado.py`:**
  - el perfil editado depende del monitor mirado;
  - editar un perfil cambia las rampas de todos los monitores que lo usan;
  - editar Normal crea «Perfil N»;
  - «sin guardar», guardar como y descartar;
  - vincular, tope por bisección, ajuste fuerte, restablecer y deshacer, modo preciso;
  - un monitor en Normal no recibe rampa (se restaura).
- **`test_aplicador.py`**, con una sesión doble y un reloj falso:
  - último gana;
  - una rampa distinta por monitor;
  - rechazo y vuelta a la última aceptada;
  - vigilancia y conflicto;
  - desactivar;
  - A/B;
  - cambio de la lista de monitores;
  - parar.
- **`test_display.py`:** `aplicar_por_monitor` y `restaurar(solo=…)` con dobles; con `--con-pantalla`, una prueba real con dos rampas distintas.
- **`test_sistema.py`:** mutex y eventos con nombres aleatorios.
- **`test_cli.py`:**
  - sin argumentos se abre la app (con un doble);
  - `--perfil` con la app abierta (se escribe la petición y se activa el evento) y sin ella (se aplica);
  - un perfil inexistente da código 1;
  - con la app abierta, `--gamma` da código 3;
  - `--reset` activa el evento.
- **`test_panel.py`** (humo, con Tk oculto; se salta si no hay Tk): construir el panel, campo numérico, rueda y doble clic.
- **`tray.py`:** solo la función pura que construye el menú según el estado.

## 9. Comprobación mínima de la sesión de creación
1. `pytest -q` en verde.
2. `--list` y `--simulate` siguen funcionando.
3. `python -m vislumbra` abre el icono y el panel.
4. **Un solo cambio real con el usuario mirando:**
   1. Crear un perfil con gamma 1,2.
   2. Guardarlo.
   3. Pulsar «Salir».
   4. Comprobar por lectura que las rampas de los 3 monitores vuelven a la identidad.
   5. Comprobar que `config.json` existe en `%APPDATA%\Vislumbra`.
5. Con la app abierta, `--reset` la desactiva.
6. La búsqueda de privacidad con `git grep` no da resultados (en el repositorio no aparece ninguna clave de monitor).

**Queda para la sesión de test de la fase 2:**
- fluidez con 1 y con 3 monitores y el tiempo de escritura;
- sensación y pasos de los deslizadores;
- **un perfil fijo en un monitor mientras se cambia el activo**;
- perfiles tras reiniciar la app;
- claves de monitor estables (reiniciar Windows, desconectar y volver a conectar);
- `--perfil`;
- tope y ajuste fuerte;
- vigilancia y conflicto;
- **P8 en el juego**;
- segunda instancia;
- cierre forzado;
- `pythonw` y cierre de sesión;
- DPI;
- icono en barra de tareas clara y oscura.

## 10. Riesgos, reversión e hipótesis
| Riesgo | Mitigación o reversión |
|---|---|
| Ajuste malo con el panel abierto | Doble clic, Restablecer, A/B, «Activo», «Salir» o `--reset` (que también desactiva la app) |
| La app muere sin restaurar | La rampa se queda: `--reset`. Al volver a arrancar se avisa del original modificado |
| `config.json` dañado o editado a mano con valores peligrosos | Se valida al leer; se aparta, se arranca con Normal y se avisa |
| La clave de un monitor cambia | Ese monitor vuelve a «sigue al activo»; no se aplica nada raro |
| La vigilancia se pelea con otra herramienta | Se detecta el conflicto y deja de reaplicar |
| La regla del 50 % no es exacta en otro equipo | Se vuelve a la última rampa aceptada y se muestra el motivo |
| Tk o `pystray` se bloquean entre hilos | Solo el hilo principal toca Tk y todo pasa por colas |
| Licencia del logo (ChatGPT) | Repositorio privado; revisar los términos de OpenAI antes de hacerlo público |

Todo va en commits pequeños y se revierte con `git revert`. Fuera del repositorio solo se escribe en `%APPDATA%\Vislumbra` (se borra a mano) y la rampa, que se restaura.

**Hipótesis sin verificar:**
- el tiempo de escritura;
- Ctrl+C con el bucle de Tk;
- `WM_SAVE_YOURSELF`;
- P8 y la luz nocturna;
- el icono a 16 px;
- la regla del 50 % en otros equipos;
- que el `DeviceID` del monitor sea estable.

## 11. Decisiones
**Ya decididas por el autor:**

| Tema | Decisión |
|---|---|
| Modelo | Cada monitor sigue al perfil activo o tiene un perfil fijo |
| Fases | La base de los perfiles va en la fase 2 y los atajos globales en la fase 3 |
| Logo | Hecho con ChatGPT; no se venderá el producto. Antes de hacer público el repositorio se revisan los términos vigentes de OpenAI (según recuerdo, ceden al usuario sus derechos sobre el resultado; **sin verificar**) y se anota en el README |

**Pendientes (la recomendada, primero):**
1. **Incidencias:** I-12 e I-4 al principio (el panel las necesita), y también I-5 e I-11b (baratas). *Alternativa:* solo I-12 e I-4.
2. **Arranque:** `python -m vislumbra` sin argumentos abre la app (o `pythonw`, sin consola). *Alternativa:* una opción `--panel`.
3. **Al abrir la app** se aplica lo guardado: perfil activo y fijos. *Alternativa:* arrancar siempre en Normal y que el usuario elija.
4. **Ventana:** pequeña, de herramienta, con «siempre encima» activable y la ✕ ocultándola en la bandeja. *Alternativa:* un panel sin bordes que se oculta al perder el foco.
5. **Ajuste fuerte:** confirmación con reversión a los 10 s por encima del 40 %. *Alternativas:* otro umbral, o ninguna.
6. **Guardar:** cambios en vivo, marcados «sin guardar» hasta pulsar «Guardar», con pregunta al salir. *Alternativa:* guardado automático de cada cambio.
7. **Icono:** solo el glifo, sin fondo, generado por un script; el logo maestro en `assets/` del repositorio privado.

## 12. Commits (en español, sin firmas de IA ni `Co-Authored-By`)
Cada commit deja los tests en verde. No hay `push` sin OK del usuario.
1. `color: límite de desviación de Windows en el validador (I-12)`
2. `color: juzgar la legibilidad sin el tinte de la temperatura (I-4)`
3. `orden: error en opciones que se ignorarían y en --monitor vacío (I-5, I-11b)`
4. `display: clave estable de monitor y rampa distinta por monitor en la sesión`
5. `escala: deslizadores no lineales, pasos y formato de valores`
6. `perfiles: modelo, validación y guardado atómico en %APPDATA%`
7. `estado: modelo del panel (perfil editado, monitores, tope, ajuste fuerte)`
8. `sistema: instancia única, eventos con nombre, DPI y área de trabajo`
9. `aplicador: hilo de aplicación por monitor con vigilancia y conflicto`
10. `assets: logo e iconos de la bandeja generados por script`
11. `panel: deslizador fino y gráfico de la curva`
12. `panel: ventana con perfiles, monitores, canales, A/B y modo preciso`
13. `bandeja: icono, menú con perfiles, estado y avisos`
14. `app: arranque, instancia única, peticiones de la terminal y cierre ordenado`
15. `orden: --perfil y --reset que desactiva la app abierta`
16. `Documentación: uso del panel y de los perfiles, PLAN.md y registro de la fase 2`
