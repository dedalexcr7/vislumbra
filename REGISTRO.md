# Registro de trabajo

Una entrada por sesión, la más reciente arriba. Formato: fecha · tipo de sesión (planificación / creación / test) · qué se hizo · qué falta · qué debe probarse.

## 2026-11-26 · creación (fase 2)
- **Hecho** (siguiendo `docs/plan-fase-2.md`, 16 commits): I-12 e I-4 (`color.py`: `DESVIACION_MAX`, `validar_legibilidad`, `construir_rampa_segura`), I-5 e I-11b (orden); `display.py` (`Monitor.clave`, `aplicar_por_monitor`, `restaurar(solo=)`); módulos nuevos `escala`, `perfiles`, `estado`, `sistema`, `aplicador`, `panel`, `tray`, `app`; `assets/` e iconos por script; `--perfil` y `--reset` que desactiva la app abierta; sin argumentos se abre la app. Pruebas nuevas en todos los módulos.
- **Desviaciones del plan:** archivo JSON con `{"asignacion": "fijo", "perfil": "X"}` en vez del nombre suelto (evita ambigüedad); «siguiente» es nombre reservado; botón extra «Descartar»; el clic izquierdo de la bandeja es «Mostrar / ocultar panel»; `--list`/`--simulate` siguen funcionando con la app abierta; una sola raíz de Tk en las pruebas (crear varias fallaba a ratos).
- **Verificado por ejecución:** `pytest -q` 540 en verde y 6 saltadas (las de pantalla), repetido 3 veces sin intermitencias; `--list`, `--simulate` y `--perfil siguiente --simulate`; **prueba real con el usuario mirando**: app con Tk, bandeja y panel reales; gamma 1,2 creó «Perfil 1» y la rampa del monitor principal se leyó igual a la esperada; se guardó y existió `config.json`; `--reset` desde otro proceso desactivó la app (código 0); tras salir, los 3 monitores en identidad. Se borró `%APPDATA%\Vislumbra` (lo creó la prueba) y se hizo un `--reset` final. `git grep` de rutas personales, correos y modelos de monitor: sin resultados.
- **Hallazgo de privacidad:** `assets/logo.png` lleva incrustada la credencial de contenido C2PA de OpenAI (firmada por una autoridad externa; sin datos personales visibles). Se deja tal cual; tenerlo en cuenta al revisar los términos antes de hacer público el repositorio.
- **No verificado / sin implementar:** «Usar la neutra como original» (aviso de rampa original modificada: solo se avisa); el aspecto real del panel con DPI altos y con tema de Windows claro; icono a 16 px (a fondo oscuro las partes olivas del glifo quedan tenues: posible incidencia); `WM_SAVE_YOURSELF`/cierre de sesión; `pythonw`; Ctrl+C con el bucle de Tk (solo con dobles).
- **A probar en la sesión de test de la fase 2:** lo listado en `docs/plan-fase-2.md` §9 («Queda para la sesión de test»): fluidez y tiempo de escritura con 1 y 3 monitores, perfil fijo en un monitor mientras cambia el activo, perfiles tras reiniciar, claves de monitor estables (reiniciar, desconectar), tope y ajuste fuerte, vigilancia y conflicto, P8 en el juego, segunda instancia, cierre forzado, DPI e icono en barra clara y oscura; y la calibración de la escala de los deslizadores.
- **Siguiente:** sesión de test de la fase 2 (o fase 3: atajos globales, con plan previo).

## 2026-11-26 · planificación (fase 2)
- **Hecho:** plan de la fase 2 aprobado por el autor y guardado en `docs/plan-fase-2.md` (panel, bandeja y perfiles). Antes se publicó una **maqueta interactiva** del panel, privada en claude.ai, que solo simula y no toca la pantalla; al autor le encantó la interfaz.
- **Decisiones del autor:**
  - La base de los perfiles se adelanta a la fase 2: crear, guardar, guardar como, renombrar y borrar, en `%APPDATA%\Vislumbra\config.json`.
  - Cada monitor **sigue al perfil activo o tiene un perfil fijo**; por ejemplo, un monitor de código con brillo más bajo que no cambia al cambiar de perfil.
  - El perfil se cambia desde el panel (‹ ›), desde la bandeja y con `--perfil NOMBRE|siguiente`.
  - Los atajos globales pasan a la fase 3.
  - Las siete decisiones restantes de §11 se aprobaron con la opción recomendada.
  - `PLAN.md` se ha actualizado: fases 2 y 3, archivos, persistencia y logo.
- **Hallazgo (cálculo con los datos del test):** el límite de Windows encaja con «ningún valor a más de 32 768 de la identidad»: 3250 K da 32 450 y se aceptó; 3200 K da 33 266 y se rechazó. El validador actual deja pasar combinaciones que Windows rechazaría. Por eso la fase 2 empieza arreglando I-12 e I-4.
- **Verificado por ejecución, sin tocar la gamma:** `pytest -q` con 212 en verde y 6 saltadas; Tk 8.6.12 disponible; `construir_rampa` tarda 0,56 ms y `leer_rampa` de 0,6 a 0,9 ms por monitor. **Verificado por lectura:** `pystray` 0.19.5 lleva su propio hilo en Windows.
- **Logo:** hecho con ChatGPT y el producto no se venderá. Antes de hacer público el repositorio hay que revisar los términos de OpenAI.
- **Sin verificar:** tiempo de escritura de la rampa; que el identificador de cada monitor sea estable; P8 (juego en modo sin bordes; el autor no llegó a probarlo); legibilidad del icono a 16 px.
- **Siguiente:** sesión de creación de la fase 2, siguiendo `docs/plan-fase-2.md`.

## 2026-11-26 · test (fase 1)
- **Verificado por ejecución:** `pytest -q` 212 en verde y 6 saltadas (marcador `pantalla`); con `--con-pantalla`, las 6 en verde. Sondeo de límites en los 3 monitores: todo lo aceptado se lee exacto (diferencia 0); **Windows rechaza temperaturas por debajo de ~3250 K** y, en general, rampas con desviación mayor de ~50 % respecto a la identidad (hipótesis confirmada con 3 predicciones). Privacidad (I-10) e I-11 comprobadas. Rampas en identidad tras cada prueba.
- **Arreglado (con test):** I-1 (monitor tocado antes de escribir, `BaseException`), I-2 (Ctrl+C fuera de la espera, código 130), I-3 (`--duration inf`/`nan`) y la duración con decimales (I-11a).
- **Constantes** (detalle en `docs/resultados-test-fase-1.md`): `TEMPERATURA_MIN` 2500 → 3300 K; `TOLERANCIA_LECTURA` 512 → 64; calibradas con el usuario mirando (comparación A/B): `BRILLO_POR_UNIDAD` 1/250 → 1/375, `CONTRASTE_ESCALA` 50 → 75, rango de brillo ±125 → ±100 y de contraste ±82 → ±40. Umbrales notados: brillo 2, contraste 2, gamma 0,1. Las referencias (contraste 5 de RivaTuner) equivalen ahora a 7,5.
- **Método:** contar escalones no sirvió (resultados incoherentes); la comparación A/B sí. El usuario miraba el patrón de pasos de 2, no el fino (deducido por cálculo).
- **Incidencias para la sesión de creación:** I-4 (el validador aplica la temperatura antes de validar), I-5 (combinaciones ignoradas en silencio), I-11b (`--monitor ""` cae al principal) e **I-12** (el validador no modela el límite del ~50 % de Windows; Windows rechaza con un mensaje genérico). `GAMMA_MAX` 4,0 está en el límite: ampliar exige la fase 5.
- **Confirmado por el usuario mirando** (con comprobación de las rampas por lectura): V2–V11 y P1, P2, P3a, P3b, P3c, P4, P6 y P7. Detalle en `docs/resultados-test-fase-1.md` §6.
- **Decisión sobre `--persist`:** **se conserva**: la rampa sobrevive al proceso y a Win+L. Nota añadida al README, con lo que no se probó (suspensión, UAC, resolución, reinicio).
- **Verificado solo por lectura o con dobles:** `SIGBREAK` (P5, saltada: el usuario no tiene la tecla) y el código de salida 0 tras un Ctrl+C real (PowerShell interrumpe la línea entera). I-9 sin probar.
- **Sin verificar:** P8 y V12 (juego en modo sin bordes; el usuario lo probará en el juego y decidirá cuándo hacer público el repositorio), contraste y brillo negativos, gamma 3 y 4 mirando, umbrales del validador y las referencias en la escala nueva (0/7,5/1,7 y 0/7,5/2,5).
- **Siguiente:** sesión de creación para las incidencias (I-4, I-5, I-11b, I-12) o fase 2 (panel y bandeja, con plan previo; ya hay un logo, ver arriba). Antes, si el usuario lo prefiere, probar P8 en el juego y anotar si la rampa se mantiene.

## 2026-11-26 · planificación (test de la fase 1)
- **Hecho:** plan de test de la fase 1 aprobado por el autor y guardado en `docs/plan-test-fase-1.md` (tests de `test_display.py` con dobles y con `--con-pantalla`, sondeo de límites, pruebas de proceso, calibración, lista visual, revisión de código, commits y riesgos). Las seis decisiones de §9 se aprobaron con la opción recomendada: arreglar I-1, I-2 e I-3 en la sesión de test; sondeo fuera de rango solo si gamma 4,0 se queda corta; resultados en `docs/resultados-test-fase-1.md`; I-4 como incidencia de diseño; `--persist` se conserva solo si la rampa sobrevive al proceso.
- **Verificado por ejecución (sin tocar la gamma):** `pytest -q` con 186 pruebas en verde; `--list` con 3 monitores y el 2 como principal; las 3 rampas en identidad; `--simulate` de los casos citados en el plan.
- **Hallazgos por lectura, no ejecutados:** I-1 (`SesionGamma.aplicar` puede dejar un monitor modificado sin restaurar si falla la lectura posterior o llega un Ctrl+C) e I-4 (el validador rechaza combinaciones cálidas razonables; esto sí se comprobó con `--simulate`). Ver §6 del plan.
- **Siguiente:** sesión de test de la fase 1, siguiendo `docs/plan-test-fase-1.md`.

## 2026-11-26 · creación (fase 1)
- **Hecho** (siguiendo `docs/plan-fase-1.md`): `requirements-dev.txt` y `pytest.ini` (`pytest` 9.2.0, MIT), `vislumbra/color.py`, `vislumbra/display.py`, `vislumbra/__main__.py`, `tests/test_color.py`, `tests/test_cli.py`, `tests/conftest.py` (opción `--con-pantalla`) y la sección de uso del `README.md`. Se actualizó `PLAN.md` (el cálculo de canales está en `color.py`).
- **Desviaciones del plan:** los commits 9 y 10 se fusionaron en uno (la orden no tiene sentido a medias). Se añadió `SesionGamma.conservar()` para `--persist` y `tests/conftest.py` para registrar `--con-pantalla`. Aviso de privacidad: los nombres de monitor salen por pantalla pero no se guardan en ningún archivo.
- **Verificado por ejecución:** `pytest` 186 pruebas en verde (no tocan la pantalla); `--list` (3 monitores, principal marcado); `--simulate --gamma 1.4`; rechazo de `--brightness 125 --contrast -82` (código 1); uso sin argumentos (código 2); `git grep` de rutas personales y correos sin resultados. **Cambio real:** `--gamma 1.2 --duration 5` en el monitor principal terminó con código 0, sin aviso de lectura no coincidente, y la lectura posterior de los 3 monitores era la identidad; luego `--reset` en los 3. Pantallas restauradas.
- **Verificado por lectura:** la lógica de `SesionGamma` (restauración al cerrar, señales, `SetConsoleCtrlHandler`) y la reversión parcial con varios monitores; **no se ha probado en ejecución** (ni con `--monitor todos`, ni cerrando la ventana, ni `Ctrl+C`).
- **Confirmado por el usuario mirando:** a la primera repetición no vio la pantalla; en la segunda (`--gamma 1.7 --contrast 5 --duration 10`, monitor principal) **sí notó el cambio** y la ejecución terminó con la rampa de los 3 monitores en identidad. **Sigue pendiente de su juicio:** el resto de la lista visual de `docs/plan-fase-1.md` §7 (tintes, bandas, brillo, sensibilidad del contraste, varios monitores).
- **A probar en la sesión de test:** `tests/test_display.py` (lectura segura y escritura con `--con-pantalla`), sondeo de límites que Windows rechaza o el controlador limita, persistencia de la rampa tras terminar el proceso (decide si se conserva `--persist`), cierre de la ventana con el ajuste aplicado, `--monitor 2` y `todos` en la configuración híbrida, calibración de la escala y de los umbrales del validador y de `TOLERANCIA_LECTURA`.
- **Siguiente:** sesión de test de la fase 1 (o fase 2: panel y bandeja, con plan previo).

## 2026-11-26 · planificación (fase 1)
- **Hecho:** plan de la fase 1 aprobado por el autor y guardado en `docs/plan-fase-1.md` (archivos, fórmula y escala, rampa de Windows, orden de terminal, tests, comprobación mínima, riesgos y commits). Las seis decisiones se aprobaron con la opción recomendada.
- **Verificado en solo lectura:** la enumeración de monitores y la lectura de la rampa funcionan desde `ctypes` (3 monitores activos en 2 GPU, rampas en identidad). No se modificó la pantalla ni ningún archivo de código.
- **No verificado (hipótesis):** reglas de rechazo de Windows, persistencia de la rampa tras terminar el proceso, restauración al cerrar la ventana, y los umbrales y constantes de escala. Los prueba la sesión de test.
- **Siguiente:** sesión de creación de la fase 1, siguiendo `docs/plan-fase-1.md`. Al cerrarla, actualizar `PLAN.md` (el cálculo de canales va en `color.py`).

## 2026-11-26 · creación (fase 0)
- **Hecho:** `git init` (rama `main`), `.gitignore`, `requirements.txt` (`pystray`, `keyboard`, `Pillow`), `LICENSE` (texto oficial de GPL v3, descargado de gnu.org), `README.md` básico y primer commit. Autoría local con el correo `noreply` de GitHub, para no dejar correos personales en el historial.
- **Licencias comprobadas** (en un entorno temporal, con `pip show` y los metadatos): `pystray` LGPLv3, `keyboard` MIT, `six` MIT, `Pillow` MIT-CMU. Todas compatibles con GPL v3.
- **Carpeta:** el usuario la movió a `D:\Claude\Proyectos\Vislumbra` (con la sesión cerrada, porque Windows la bloquea). Después se creó el `.venv` y se instaló `requirements.txt` (`pystray` 0.19.5, `keyboard` 0.13.5, `Pillow` 12.3.0; instalación sin errores).
- **Repositorio:** creado como **privado** (`dedalexcr7/vislumbra`) y primer `push` de `main` hecho con OK del usuario. Visibilidad comprobada con `gh repo view`: PRIVATE. Los `push` posteriores también requieren su OK.
- **Fase 0 completa.** Siguiente: fase 1 (núcleo), con plan previo preparado en una sesión de planificación.
- **Decisiones:** el aviso de copyright («Copyright 2026 …») sigue pendiente. El usuario decide qué fases se hacen en cada sesión (puede haber más de una).
- **A probar:** que `pip install -r requirements.txt` funcione en el `.venv` definitivo.

## 2026-11-26 · planificación
- Se definió el objetivo, la tecnología (Python), el uso (bandeja + panel + perfiles + atajos) y el enfoque de riesgo (empezar sencillo).
- Referencia: la pestaña de color de RivaTuner v2.24c, usada en un vídeo sobre Tarkov para ver mejor en oscuro.
- Se escribieron `CLAUDE.md`, `PLAN.md` y este registro. No se ha creado código ni entorno ni repositorio.
- Segunda tanda de planificación: se leyeron las capturas de la ventana de RivaTuner (rangos, método GDI gamma ramp, esquemas «gamma 1» = 0/5/1,7 y «gamma 2» = 0/5/2,5). Se añadieron a `PLAN.md` los perfiles iniciales, el requisito de control fino y la propuesta de nombre (Nictalope, pendiente de confirmar).
- Tercera tanda: nombre confirmado **Vislumbra** (verificado libre en web, GitHub y PyPI; ver `PLAN.md`) y renombrados los documentos. Decisiones nuevas: los perfiles los crea cada usuario (solo viene «Normal»), la app es gratuita, se añade un **modo preciso**, y la calibración de la escala se hará probando porque RivaTuner ya no está instalado.
- Cuarta tanda: licencia **GPL v3** elegida; cuenta de GitHub `dedalexcr7` confirmada; el repositorio se mantiene **privado** hasta que el autor decida lo contrario.
- **Siguiente paso:** sesión de creación, fase 0 y fase 1 (ver la entrada de arriba para el estado).
- **Sin verificar:** si Tarkov usa BattlEye (se cree que sí); el rendimiento real de la rampa gamma en el equipo del usuario.
