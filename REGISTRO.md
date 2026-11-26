# Registro de trabajo

Una entrada por sesión, la más reciente arriba. Formato: fecha · tipo de sesión (planificación / creación / test) · qué se hizo · qué falta · qué debe probarse.

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
