# Plan de la fase 3: atajos globales y menú para personalizarlos

**Estado: aprobado por el autor.** Las ocho decisiones de §9 se aprobaron con la opción recomendada. Lo ejecuta una sesión de creación. Después viene el `.exe` (fase 6), con su propio plan (§11).

## 0. Punto de partida (verificado al planificar, sin tocar la gamma)
- **Repositorio.** `main` en `4e4280f`, árbol limpio. `pytest -q`: **690 en verde y 6 saltadas**.
- **Atajos: no existe nada todavía.** No hay código de teclado. La librería `keyboard` está en `requirements.txt` desde la fase 0, pero **no se usa en ninguna parte**.
- **`keyboard` funciona con un gancho global de bajo nivel** (`SetWindowsHookEx` con `WH_KEYBOARD_LL`, leído en su código instalado, versión 0.13.5). Ese gancho recibe **todas las teclas de todas las aplicaciones**, también contraseñas. Windows ofrece `RegisterHotKey`: Windows avisa solo de las combinaciones registradas y la app no ve nada más. Esa diferencia decide el diseño (§2.1).
- **Cómo despacha acciones la app hoy.** La bandeja, la orden `--perfil` y el hilo de procesos meten tareas en `App.cola`, y el hilo principal (Tk) las procesa en `_despachar`.
  - Las acciones de la bandeja ya existen en `_atender_bandeja`: mostrar u ocultar, activo, perfil, siguiente y A/B.
  - Los atajos pueden **reutilizarlas** en vez de duplicar la lógica.
  - `Estado.mover_activo(±1)` ya sirve para «anterior».
- **Configuración.** `config.json` sigue en versión 1 y ya admite campos opcionales (`programas`). `Configuracion.renombrar` y `borrar` y `Estado._sustituir_referencias` ya arrastran las referencias a un perfil. Los atajos de perfil se apoyan en ese mecanismo.
- **Sondeo de combinaciones en este equipo.** Medido registrando cada combinación con `RegisterHotKey` y liberándola al instante, en un proceso aparte:

  | Grupo | Rechazadas (ya en uso) |
  |---|---|
  | Ctrl+Alt+tecla | L, M, Supr |
  | Ctrl+Mayús+tecla | X, F5, F12, F20 |
  | Ctrl+Alt+Mayús+tecla | O, F1, F5, F13 a F21 |
  | Alt+Mayús+tecla | R, F10 |
  | Win+Alt y Win+Mayús | muchas (reservadas por Windows) |
  | Sin modificador | ninguna: F13 a F24 y Pausa se registran |

  El código de error en todos los casos fue 1409 (`ERROR_HOTKEY_ALREADY_REGISTERED`). No sé qué programa tiene cada una, y esto **solo vale para este equipo**: en otro habrá otras.
- **AltGr.** El teclado de pruebas tiene AltGr, que Windows trata como **Ctrl+Alt**. Con Ctrl+Alt, de letras, dígitos y teclas de navegación, **solo la Q** escribe un carácter (en este teclado, «@»). Si un atajo usa esa tecla con Ctrl+Alt, el usuario ya no puede escribir ese carácter.

## 1. Alcance
**Entra:**
- Atajos globales que funcionan con la app en la bandeja, con el panel oculto y con otra ventana (por ejemplo un juego) en primer plano.
- Acciones (ver §2.2): siguiente y anterior perfil, **un atajo por perfil** (también para «Normal»), A/B, activo, mostrar u ocultar el panel, modo preciso y **emergencia**.
- **Menú «Atajos…»** para personalizarlos: cambiar grabando la combinación, quitar, restaurar los valores por defecto, avisar de conflictos y elegir el aviso al usar un atajo.
- Se abre desde el panel y desde la bandeja.
- Guardado en `config.json`.

**No entra** (queda anotado para después):

| Queda fuera | Por qué |
|---|---|
| Ajuste rápido (subir o bajar gamma o brillo con atajos) | Idea natural, pero cambia el modelo (¿se guarda el cambio en el perfil?); se plantea aparte |
| Importar y exportar atajos | Con el resto de la fase «más perfiles» |
| Atajos que solo funcionan con ciertos programas | Ya existe el perfil por programa (fase 4) |
| Registrar atajos que Windows reserva (Win+L, Ctrl+Alt+Supr) | No se puede con `RegisterHotKey` |

## 2. Diseño

### 2.1 Mecanismo: `RegisterHotKey`, sin la librería `keyboard`
- Un hilo propio (`vislumbra-atajos`) con su bucle de mensajes registra cada combinación con `RegisterHotKey(None, id, mods | MOD_NOREPEAT, vk)` y recibe `WM_HOTKEY`.
  - `MOD_NOREPEAT` evita que **mantener** pulsada una combinación repita la acción (si no, A/B parpadearía).
  - `RegisterHotKey` solo se puede llamar desde el hilo que recibe los mensajes. Por eso el cambio de atajos se pide con `PostThreadMessageW` y el hilo contesta con el resultado de cada registro.
- **No pide permisos de administrador** ni se instala nada nuevo en el sistema.
- **Efecto de la tecla:** cuando salta un atajo, Windows no entrega ese último pulsado a la ventana en primer plano (los modificadores sí llegan).
- **Consecuencias:**
  - se **quita `keyboard`** de `requirements.txt` (una dependencia menos, y una menos que empaquetar en el `.exe`);
  - hay que actualizar `PLAN.md` («Atajos globales: librería `keyboard`», el riesgo de permisos elevados y la lista de licencias), el `README.md` y el texto de licencias.
- **Límites conocidos de `RegisterHotKey`:**
  - una combinación solo puede tenerla **una** aplicación (si otra la tiene, el registro falla);
  - no sirve para teclas modificadoras solas;
  - no distingue pulsar de soltar.
- **Hipótesis sin verificar (las prueba la sesión de test):** que salte con un juego en primer plano en modo sin bordes y en pantalla completa exclusiva; que salte con una ventana ejecutada como administrador; que ningún anticheat reaccione a ello. Un gancho global como el de `keyboard` es **más** llamativo para esos programas que `RegisterHotKey`, aunque no he comprobado cómo reacciona ninguno.

### 2.2 Acciones y valores por defecto
| Acción | Qué hace | Por defecto |
|---|---|---|
| Siguiente perfil | `Estado.mover_activo(+1)` | Ctrl+Alt+P |
| Perfil anterior | `Estado.mover_activo(−1)` | Ctrl+Alt+Mayús+P |
| Comparar (A/B) | alterna el ajuste y la pantalla normal | Ctrl+Alt+B |
| Activo sí o no | `Estado.poner_activo(...)` | Ctrl+Alt+V |
| Mostrar u ocultar el panel | como el clic en el icono | Ctrl+Alt+Mayús+V |
| Modo preciso | activa o desactiva la casilla del panel | sin atajo |
| **Emergencia** | suelta la pantalla ya, sin pasar por la interfaz (§2.5) | Ctrl+Alt+0 |
| Un perfil concreto | `Estado.cambiar_activo(nombre)` | sin atajo (cada usuario asigna los suyos) |

- Todas las combinaciones por defecto están **libres en este equipo** (sondeo de §0) y **no usan la Q**. Otros equipos pueden tener conflictos: por eso el menú de personalización los detecta y deja cambiarlos.
- Los atajos de acción son un conjunto fijo; los de perfil dependen de los perfiles del usuario. Los de perfil no traen valores por defecto (ni se asignan solos).
- **Cambiar de perfil con un atajo actúa como el menú de la bandeja** (misma lógica, una sola vía), salvo lo decidido en §9 (decisión 4) sobre «Activo» apagado.

### 2.3 Combinaciones válidas y conflictos
- Una combinación es un conjunto de modificadores (Ctrl, Alt, Mayús, Win) más **una tecla**.
- **Reglas (lógica pura, probada sin Windows):**
  - hay que tener al menos un modificador de Ctrl, Alt o Win. **Mayús solo no vale**, porque bloquearía escribir mayúsculas;
  - se admiten sin modificador solo F13 a F24 y Pausa, que nadie usa para escribir (decisión 7);
  - teclas admitidas: letras, dígitos, F1 a F24, flechas, Inicio, Fin, RePág, AvPág, Ins, Supr y Pausa;
  - no se repite una combinación entre acciones (el mensaje dice cuál ya la usa);
  - el JSON guarda un texto canónico (`Ctrl+Alt+Mayús+P` se guarda como `Ctrl+Alt+Shift+P`) y acepta mayúsculas o minúsculas y cualquier orden de modificadores al leerlo.
- **Conflictos con otra aplicación o con Windows:** se detectan **al registrar** (falla con 1409). El menú muestra «En uso por otra aplicación» junto a esa acción.
- **Conflicto con AltGr (aviso, no bloqueo):** si la combinación lleva Ctrl+Alt y esa tecla escribe un carácter con AltGr en la distribución activa, el menú avisa: «Ctrl+Alt+Q escribe «@» con AltGr; no podrás escribirlo». Se comprueba con `ToUnicodeEx` (sondeado en este equipo; en otras distribuciones queda por probar).

### 2.4 Hilos y flujo
```
Hilo de atajos (GetMessage) ── WM_HOTKEY ──► cola de la app ──► Tk (_despachar) ──► las mismas acciones de la bandeja
        └── emergencia: Aplicador.emergencia() directo (sin Tk) y después aviso por la cola
```
- El hilo de atajos **solo encola** (como `pystray`). No toca Tk ni el estado.
- **Arranque:** tras cargar la configuración se registran todos. Los que fallan se avisan en el panel y, si es la emergencia, también en la bandeja. La app arranca igualmente.
- **Cierre:** `_parar_todo` desregistra todo y para el hilo.
- **Cambios en el menú:** `GestorAtajos.aplicar(mapa)` devuelve el resultado por atajo. El hilo principal espera con un límite de 2 s.
- **Mientras se graba una combinación** los atajos se **pausan** (se desregistran): si no, grabar un atajo que la app ya tiene (por ejemplo para cambiar su acción) activaría esa acción en vez de grabarlo. Se reanudan al terminar, aunque falle o se cancele.

### 2.5 Emergencia
- **Objetivo:** que la pantalla vuelva a su rampa original aunque la interfaz esté ocupada o un deslizador siga en movimiento.
- **Cómo:** el hilo de atajos llama a un método nuevo, `Aplicador.emergencia()`, que (1) deja de aceptar peticiones normales, (2) pide a todos los monitores `None` (su rampa original), con lo que la vigilancia no la reaplica, y (3) encola una tarea para que la interfaz ponga «Activo» en apagado, llame a `Aplicador.reanudar()` y avise.
  - Así **no hay carrera** con un deslizador que se esté moviendo.
  - Siempre avisa (mensaje en el panel y notificación de la bandeja), tenga el aviso de atajos activado o no.
- **Límites:**
  - no ayuda si el controlador de vídeo se queda bloqueado dentro de `SetDeviceGammaRamp`; entonces quedan cerrar el proceso o `--reset`, y ninguno de los dos está probado en ese caso;
  - no se puede **quitar** el atajo de emergencia (sí cambiarlo; decisión 6);
  - si su combinación está ocupada al arrancar, se avisa de forma visible.

### 2.6 Aviso al usar un atajo
- Opciones en el menú, guardadas en la configuración: **Ninguno** (por defecto), **Sonido** (`winsound` de la biblioteca estándar) y **Notificación** (la de la bandeja).
- **No se dibuja nada encima de la pantalla** (por ejemplo, una superposición con el nombre del perfil). **Hipótesis, no medida:** una ventana siempre visible sobre un juego en modo sin bordes podría sacarlo de la presentación directa de Windows y causar el tirón que el autor ya notó con otros cambios. El propio cambio de imagen ya sirve de aviso.
- Las notificaciones de Windows se silencian durante un juego en pantalla completa si el modo «Asistente de concentración» está activo (comportamiento general de Windows, **no comprobado** aquí): por eso no es el aviso por defecto.

### 2.7 Configuración (`config.json`, sigue en versión 1)
```json
"atajos": {
  "acciones": {"siguiente": "Ctrl+Alt+P", "comparar": "Ctrl+Alt+B", "preciso": null},
  "perfiles": {"Código": "Ctrl+Alt+2", "Normal": "Ctrl+Alt+1"},
  "aviso": "ninguno"
}
```
- Una acción **ausente** usa su valor por defecto; `null` significa «sin atajo» a propósito.
- Un archivo **sin** el campo `atajos` se lee igual que ahora (valores por defecto): no hace falta migrar.
- Un atajo inválido, repetido o de una acción desconocida **no estropea el archivo**: se descarta solo ese atajo y se avisa. (Con un campo `atajos` entero ilegible se arranca con los valores por defecto.)
- Renombrar un perfil mueve su atajo; borrarlo lo quita. «Normal» no se puede renombrar ni borrar, y sí puede tener atajo.
- **Privacidad:** solo se guardan combinaciones de teclas. Nada de rutas, nombres de monitor ni datos personales.

## 3. Menú «Atajos…»
Mismo estilo que «Programas…» (maqueta oscura, `widgets`: `Boton`, `Selector`, `Tarjeta`) y que los demás diálogos de `dialogos.py`:
```
┌ Atajos de teclado ─────────────────────────────── ✕ ┐
│ Acciones                                             │
│  Siguiente perfil          Ctrl+Alt+P     [Cambiar] [Quitar]
│  Perfil anterior           Ctrl+Alt+Mayús+P
│  Comparar (A/B)            Ctrl+Alt+B
│  Activo sí o no            Ctrl+Alt+V
│  Mostrar u ocultar panel   Ctrl+Alt+Mayús+V
│  Modo preciso              sin atajo
│  Emergencia: pantalla original   Ctrl+Alt+0   (no se puede quitar)
│ Perfiles (ir directamente a uno)                     │
│  Normal                    Ctrl+Alt+1
│  Código                    Ctrl+Alt+2   ● En uso por otra aplicación
│ Aviso al usar un atajo  [ Ninguno ▾ ]                │
│ ⚠ Ctrl+Alt+Q escribe «@» con AltGr en tu teclado.    │
│ [Restaurar valores por defecto]            [Cerrar]  │
└──────────────────────────────────────────────────────┘
```
- **Cambiar:** la fila pasa a «Pulsa la combinación… (Esc cancela)» y se pausan los atajos. Se toma la tecla del evento de Tk y los modificadores con `GetAsyncKeyState` (incluye Win). Después se valida, se comprueba que no esté repetida, se **intenta registrar** y se muestra el resultado en la propia fila. Si falla, la fila vuelve a su combinación anterior y dice por qué.
- **Quitar** deja la acción sin atajo (menos la emergencia). **Restaurar valores por defecto** pide confirmación y no toca los atajos de perfil.
- **Entradas:** botón «Atajos…» junto a «Programas…» en el panel y entrada «Atajos…» en la bandeja.
- **Atajos a la vista:** el menú de la bandeja muestra la combinación a la derecha de cada acción («Siguiente perfil → Ctrl+Alt+P») usando el tabulador de los menús de Win32. **Hipótesis sin verificar con `pystray`**: si no sale bien, se omite sin más y no es motivo para rehacer nada.
- **Riesgo:** grabar una combinación con la tecla Windows puede abrir el menú Inicio al soltarla; el diálogo recomienda Ctrl, Alt y Mayús.
- **Para elegir el aspecto antes de programarlo,** se puede hacer una maqueta como la del panel (decisión del autor; no es necesaria).

## 4. Archivos
| Archivo | Cambio |
|---|---|
| `vislumbra/atajos.py` (nuevo) | Lógica pura: `Combinacion`, tabla de teclas, validación, valores por defecto, `Atajos` (acciones, perfiles, aviso) y su JSON |
| `vislumbra/teclado.py` (nuevo) | `ctypes`: `GestorAtajos` (hilo, registro, pausa y reanudación), lectura de modificadores y comprobación de AltGr |
| `vislumbra/perfiles.py` | `Configuracion.atajos`; renombrar y borrar arrastran los de perfil; JSON tolerante |
| `vislumbra/estado.py` | Atajos en el estado; `_sustituir_referencias` también los arrastra; asignar y quitar con comprobación de duplicados |
| `vislumbra/aplicador.py` | `emergencia()` y `reanudar()` |
| `vislumbra/app.py` | Crear y parar el gestor; tarea `atajo`; acciones nuevas (anterior, modo preciso, emergencia); avisos |
| `vislumbra/dialogos.py` | `DialogoAtajos` |
| `vislumbra/panel.py`, `tray.py` | Botón y entrada «Atajos…», acciones nuevas y combinaciones en el menú |
| `requirements.txt`, `README.md`, `PLAN.md` | Se quita `keyboard`; uso de los atajos |

Cabeceras: `SPDX-License-Identifier: GPL-3.0-or-later`, sin nombre. **No toca el registro de Windows ni los drivers.**

## 5. Tests (los escribe la sesión de creación, sin tocar la pantalla)
- **`test_atajos.py` (puro):**
  - ida y vuelta de texto a combinación;
  - orden canónico y lectura tolerante;
  - reglas: Mayús sola rechazada, sin modificador solo F13–F24 y Pausa;
  - duplicados;
  - los valores por defecto son válidos y no se repiten;
  - JSON: ausente = por defecto, `null` = sin atajo, un atajo inválido se descarta con aviso, un archivo antiguo sin `atajos` se lee bien.
- **`test_perfiles.py` y `test_estado.py`:**
  - renombrar mueve el atajo de perfil y borrar lo quita;
  - «Normal» admite atajo;
  - asignar uno ya usado da error con el nombre de la acción.
- **`test_teclado.py`:**
  - registro **real** de una combinación improbable (por ejemplo Ctrl+Alt+Mayús+F24, libre en este equipo), siempre liberada al terminar; se salta si está ocupada;
  - el segundo registro de la misma combinación falla con 1409 (prueba el camino de conflicto con Windows de verdad);
  - `WM_HOTKEY` **simulado** con `PostThreadMessageW` al hilo (no se inyectan teclas reales);
  - pausar y reanudar, cambiar el mapa y parar (el hilo termina).
- **`test_aplicador.py`:** `emergencia()` pide `None` a todos los monitores, ignora peticiones hasta `reanudar()` y la vigilancia no reaplica.
- **`test_app.py`:**
  - cada acción de atajo llega al estado (con un gestor doble);
  - emergencia con la cola sin procesar: la pantalla ya está suelta;
  - los registros fallidos se avisan en el panel y en la bandeja.
- **`test_dialogos.py` (Tk oculto, se salta si no hay Tk):** construir el diálogo, grabar una combinación con eventos simulados, rechazar un duplicado y quitar.
- **`test_tray.py`:** el menú incluye «Atajos…» y, si procede, las combinaciones.

## 6. Comprobación mínima de la sesión de creación
1. `pytest -q` en verde.
2. `python -m vislumbra` abre la app y los atajos por defecto quedan registrados (el diálogo no marca ninguno en conflicto).
3. **Un solo cambio real, con el autor delante:** pulsar Ctrl+Alt+P y ver que cambia el perfil; pulsar Ctrl+Alt+0 y ver que vuelve la pantalla original; salir; comprobar por lectura que las rampas de los 3 monitores están en identidad.
4. `git grep` de rutas personales y correos sin resultados.

## 7. Queda para la sesión de test de la fase 3
**Lo que solo se puede ver pulsando** (lista para el autor):
- Que cada atajo por defecto hace lo que dice, con el panel oculto.
- Que mantener pulsado A/B **no** parpadea (`MOD_NOREPEAT`).
- **P8-atajos: con el juego en primer plano** (modo sin bordes y, si se puede, pantalla completa exclusiva), ¿saltan los atajos? ¿y con un programa ejecutado como administrador?
- Una combinación ocupada por otra aplicación (por ejemplo Ctrl+Alt+L, que aquí está en uso): el menú debe decirlo.
- Ctrl+Alt+Q: el aviso de AltGr, y que Ctrl+Alt+Q no deja de escribir «@» **mientras no esté asignada**.
- Reasignar una combinación que la app ya tiene: la grabación no debe activar la acción.
- Renombrar y borrar perfiles con atajo; reiniciar la app y comprobar que persisten.
- Cambiar la distribución de teclado de Windows y ver qué ocurre con los atajos.
- Emergencia con el panel abierto y un deslizador moviéndose.
- El menú de la bandeja con las combinaciones al lado (si funciona el tabulador).
- Sonido y notificación (con y sin el modo de concentración de Windows).

## 8. Riesgos, reversión e hipótesis
| Riesgo | Mitigación o reversión |
|---|---|
| Un atajo choca con otra aplicación o con Windows | Se detecta al registrar, se muestra en el menú y se cambia; la app sigue funcionando |
| Un atajo con Ctrl+Alt impide escribir un carácter (AltGr) | Aviso al asignarlo; los valores por defecto evitan la Q, que es la tecla afectada **en este teclado** |
| El atajo se activa sin querer en un juego | Por defecto son combinaciones de 3 teclas; el autor puede cambiarlas o quitarlas |
| Atajos que no saltan con un juego en primer plano | No se puede garantizar; quedan la bandeja, el panel y `--perfil`, y se anota el resultado |
| La emergencia no responde | Panel (Activo), bandeja (Salir) y `--reset`, igual que ahora |
| Un archivo de configuración con atajos raros | Se valida al leer; se descarta solo el atajo malo |

Todo va en commits pequeños y se revierte con `git revert`. Fuera del repositorio solo se escribe `%APPDATA%\Vislumbra\config.json`, como hasta ahora.

**Hipótesis sin verificar:**
- que los atajos funcionen con un juego en primer plano y con una ventana elevada;
- que ningún anticheat reaccione a `RegisterHotKey`;
- que el evento de teclado de Tk dé el código de tecla de Windows al grabar (si no, se leerá con `GetAsyncKeyState`);
- que `ToUnicodeEx` detecte bien AltGr en otras distribuciones;
- que el tabulador de los menús de Win32 funcione con `pystray`;
- que una superposición en pantalla causaría el tirón (se descarta sin probar);
- que Windows silencie las notificaciones en un juego (comportamiento general, sin comprobar).

## 9. Decisiones (la recomendada, primero)
1. **Mecanismo:** `RegisterHotKey`, quitando la dependencia `keyboard` (§2.1). *Alternativa:* seguir con la librería `keyboard` (gancho global que ve todas las teclas).
2. **Acciones y valores por defecto:** los de §2.2, con la emergencia en Ctrl+Alt+0. *Alternativa:* ningún atajo asignado al principio.
3. **Atajos de perfil** (también «Normal») dentro del mismo menú «Atajos…». *Alternativa:* asignarlos desde la ficha de cada perfil en el panel.
4. **Atajo de perfil con «Activo» apagado:** el atajo **reactiva** la aplicación, porque si no no se vería nada. *Alternativa:* se comporta como el menú de la bandeja (cambia el perfil sin aplicarlo).
5. **Aviso al usar un atajo:** «Ninguno» por defecto, con «Sonido» y «Notificación» como opciones, y sin superposición en pantalla (§2.6). *Alternativa:* sonido por defecto.
6. **Emergencia:** se puede cambiar pero no quitar. *Alternativa:* poder quitarla con una confirmación.
7. **Requisito de modificador:** al menos Ctrl, Alt o Win, salvo F13–F24 y Pausa solas. *Alternativa:* permitir cualquier tecla suelta.
8. **Combinaciones en el menú de la bandeja:** mostrarlas a la derecha de cada acción si `pystray` lo permite. *Alternativa:* no mostrarlas.

## 10. Commits (en español, sin firmas de IA ni `Co-Authored-By`)
Cada commit deja los tests en verde. No hay `push` sin OK del usuario.
1. `atajos: combinaciones, teclas, validación y valores por defecto (lógica pura)`
2. `perfiles: atajos en config.json, arrastrados al renombrar y borrar`
3. `estado: asignar y quitar atajos con comprobación de duplicados`
4. `teclado: gestor de atajos globales con RegisterHotKey en su propio hilo`
5. `aplicador: emergencia que suelta la pantalla sin pasar por la interfaz`
6. `app: atajos globales, acciones nuevas (anterior, modo preciso, emergencia) y avisos`
7. `dialogos: «Atajos…» con grabación de combinaciones y comprobación de conflictos`
8. `panel y bandeja: botón y entrada «Atajos…» y combinaciones en el menú`
9. `Dependencias: quitar keyboard, que los atajos ya no necesitan`
10. `Documentación: uso de los atajos, PLAN.md, README y registro de la fase 3`

## 11. Después: el `.exe` (fase 6)
- Va en **otra sesión de planificación**, con las cuestiones que ya dejó el relevo de `REGISTRO.md` (licencia de PyInstaller, recursos de `assets/`, ventana sin consola, `--list`, `--simulate`, `--perfil` y `--reset` desde el ejecutable, logo, antivirus y «Iniciar con Windows»).
- **Cómo la afecta esta fase:**
  - sin `keyboard` hay una dependencia menos que empaquetar;
  - `RegisterHotKey` no necesita administrador, así que el `.exe` no tendría por qué pedir elevación (**hipótesis**: que los atajos salten con ventanas elevadas se prueba aquí);
  - los atajos tienen que funcionar también en el ejecutable, y se añade a su lista de pruebas.
