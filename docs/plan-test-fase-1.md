# Plan de test de la fase 1

**Estado: aprobado por el autor.** Las seis decisiones de §9 se aprobaron con la opción recomendada. Lo ejecuta una sesión de test. Reglas (`CLAUDE.md`): no añadir funciones; se pueden escribir tests y corregir fallos pequeños y claros; lo demás se anota como incidencia en `REGISTRO.md`. Tras cualquier prueba que toque la gamma, `--reset` y comprobación con LECTURA.

## 0. Punto de partida

**Verificado al planificar (por ejecución, sin tocar la gamma):**
- `pytest -q`: 186 pruebas en verde.
- `--list` muestra 3 monitores con un solo principal: el monitor 2.
- Las rampas de los 3 monitores estaban en identidad (desviación máxima 0).
- Según la enumeración de la planificación de la fase 1, el monitor 1 está en la GPU integrada, y los monitores 2 y 3 en la dedicada. La sesión de test lo confirma con `--list`.
- `--simulate` (cálculo puro):
  - `--gamma 4`, `--brightness 75`, `--brightness -60`, `--contrast 82`, `--contrast -40`, `--temp 10000` y `--temp 2500 --gamma 0.8` pasan el validador.
  - `--brightness 100` se rechaza: centro fuera del 10–90 %.
  - `--temp 2500 --contrast -20` se rechaza: rango del canal B del 21 %. Ver la incidencia I-4.
- Desviación máxima respecto a la identidad (cálculo, 16 bits):

| Ajuste | Desviación máxima |
|---|---|
| 0/5/1,7 | 19 % |
| 0/5/2,5 | 33 % |
| gamma 3 | 38 % |
| gamma 4 | 47 % |
| brillo 75 | 30 % |
| contraste 82 | 34 % |
| temp 2500 | 72 % |
| gamma 4,5 / 5 / 6 (fuera de rango) | 51 % / 53 % / 58 % |

**Verificado en la sesión de creación** (según `REGISTRO.md`): un cambio real con `--duration` que se restauró solo y que el usuario vio.

**Solo leído, nunca ejecutado:** restauración al cerrar la ventana, Ctrl+C real, `--persist`, `--monitor todos` y la reversión parcial.

### Utilidades que se usan en todo el plan
Todas se ejecutan desde la carpeta del repositorio, en PowerShell.

- **TERMINAL DE EMERGENCIA:** antes de tocar la gamma, abrir una segunda ventana de terminal en la carpeta del repositorio y dejar escrito, sin pulsar Enter:
  `.\.venv\Scripts\python.exe -m vislumbra --reset`
- **LECTURA** (solo lectura; comprobado que funciona al planificar):
  ```powershell
  .\.venv\Scripts\python.exe -c "from vislumbra import display as d, color as c; i=c.rampa_identidad(); [print(f'monitor {m.numero}: desviación máx', max(abs(x-y) for x,y in zip(d.leer_rampa(m), i))) for m in d.listar_monitores()]"
  ```
  Una desviación de 0 es la identidad. Un valor mayor indica que hay una rampa aplicada.
- **PATRÓN DE GRISES:** imagen PNG generada con Pillow en el scratchpad, **no en el repositorio**. Tiene una fila de escalones casi negros (niveles 0, 2, 4… hasta 40) y otra de casi blancos (215… 255), numerados. Se abre a pantalla completa en el monitor que se prueba. La medida objetiva es **cuántos escalones oscuros se distinguen**.

## 1. Tests automáticos: `tests/test_display.py`

### 1.1 Configuración (`tests/conftest.py`)
- Registrar el marcador `pantalla` en `pytest_configure`.
- En `pytest_collection_modifyitems`, saltar los tests marcados si no se pasa `--con-pantalla` («requiere --con-pantalla»).
- Fixture `monitores_reales`: `listar_monitores()`. Si la lista está vacía o la llamada falla, `pytest.skip("no hay monitores activos")`.
- **Solo con `--con-pantalla`**, doble red de seguridad:
  - fixture de **sesión** que lee la rampa de todos los monitores al empezar y la restaura con `display._escribir` al terminar;
  - fixture de **función** `rampas_guardadas` que hace lo mismo por test, en el `finalizer`, aunque el test falle.
  Ambas comprueban después con `leer_rampa` que la rampa coincide con la guardada, y si no, lo informan en la salida sin ocultarlo.

### 1.2 Seguros por defecto (solo lectura; se saltan si no hay monitores)
- `listar_monitores()`:
  - devuelve al menos 1 monitor, exactamente 1 principal y números 1…n sin huecos;
  - `dispositivo` empieza por `\\.\DISPLAY`.
- `leer_rampa(m)` para cada monitor: 768 enteros entre 0 y 65535, y cada canal monótono.
- `elegir_monitores` con la lista real: `principal` devuelve el que tiene `principal=True`; `todos` devuelve todos; `str(n)` devuelve el n-ésimo; `"99"` y `"abc"` lanzan `MonitorNoEncontrado`.
- `elegir_monitores` con lista vacía lanza `MonitorNoEncontrado`. Este caso no necesita pantalla.

### 1.3 Con dobles (sin tocar la pantalla; se ejecutan siempre)
**Regla de seguridad de estos tests**, porque `SesionGamma` real registra `atexit`, señales y `SetConsoleCtrlHandler`:
- `monkeypatch` de `display._escribir` y `display.leer_rampa` por un doble en memoria (un diccionario por monitor);
- `monkeypatch` de `display.atexit.register` y `display.atexit.unregister`, y de `SesionGamma._instalar_manejadores` y `SesionGamma._desinstalar_manejadores`, por versiones vacías;
- monitores falsos con dispositivos **inexistentes** (`r"\\.\PRUEBA1"`…), nunca `\\.\DISPLAYn`, y originales iguales a la identidad.

Así, si un test falla a medias, ningún `atexit` puede escribir en un monitor real al salir de pytest.

Casos:
1. **Reversión parcial:** 3 monitores falsos; el doble de `_escribir` lanza `RampaRechazada` al llegar al monitor 2. Se espera que `aplicar` relance el error, que el monitor 1 vuelva a su original, que el 3 no se toque y que `_tocados` quede vacío.
2. **Fallo en la lectura posterior** (I-1): `_escribir` funciona, pero la `leer_rampa` que sigue a la escritura del monitor 1 lanza `ErrorPantalla`. Se espera que el monitor 1 vuelva a su original. **Hoy falla por lectura de código**: se marca `xfail(strict=True)` hasta que se aplique el arreglo de I-1.
3. **`KeyboardInterrupt` a mitad de `aplicar`** (I-1): igual que el caso anterior, pero lanzando `KeyboardInterrupt`. Se espera que, tras salir del `with`, todos los monitores escritos vuelvan a su original. También `xfail(strict=True)` hasta el arreglo.
4. **Excepción dentro del `with`:** `RuntimeError` después de `aplicar`; todos se restauran y la excepción se propaga.
5. **`restaurar()` idempotente:** dos llamadas seguidas producen una sola escritura por monitor.
6. **`conservar()`:** tras `conservar()` y `cerrar()` no hay escrituras de restauración.
7. **`originales_modificados()`:** con un original no identidad, devuelve ese monitor.
8. **`restaurar_identidad`:** si el doble falla en un monitor, intenta todos y lanza `ErrorPantalla` al final con los fallos.
9. **Manejadores:** se prueban por separado con un doble de `_restaurar_sin_excepcion`.
   - `_al_evento_consola(2)` (cierre) llama a restaurar y devuelve `False`;
   - `_al_evento_consola(0)` (Ctrl+C) no llama a restaurar;
   - `_al_recibir_senal(SIGINT)` restaura y lanza `KeyboardInterrupt`;
   - `_al_recibir_senal(SIGBREAK)` restaura y lanza `SystemExit(1)`.

### 1.4 De escritura real (marcador `pantalla`; solo con `--con-pantalla`)
Ajustes siempre suaves (identidad y gamma 1,2), con `rampas_guardadas` activo. El usuario no necesita mirar, pero se le avisa de que habrá parpadeos breves.
1. **Identidad:** `aplicar_rampa(m, identidad)` devuelve `True` y `leer_rampa(m) == identidad` en cada monitor.
2. **Gamma suave:** `aplicar_rampa(m, rampa(gamma 1,2))`. Se mide la diferencia máxima entre lo leído y lo aplicado por monitor y se imprime con `-s`. Se comprueba que es ≤ `TOLERANCIA_LECTURA`.
3. **`SesionGamma.restaurar()` real:** sesión con todos los monitores, aplicar gamma 1,2 y `restaurar()`. La lectura vuelve al original guardado.
4. **Excepción dentro de `SesionGamma` real:** `RuntimeError` dentro del `with`; se espera que la lectura vuelva al original. Con `atexit` y manejadores neutralizados como en 1.3, porque aquí se prueba el `with`, no las señales.
5. **Reversión parcial real** (solo si hay ≥ 2 monitores): envolver el `_escribir` real para que lance `RampaRechazada` **antes** de escribir en el segundo monitor de la sesión. El primero se escribe de verdad. Se espera que la lectura del primero vuelva al original y que el segundo no cambie.

Se ejecuta con:
```powershell
.\.venv\Scripts\python.exe -m pytest -q                       # sin pantalla
.\.venv\Scripts\python.exe -m pytest -q -s -m pantalla --con-pantalla   # con pantalla (el usuario avisado)
```
Después, siempre: LECTURA (todo a 0) y, si hiciera falta, `--reset`.

## 2. Sondeo de límites

### 2.1 Parte automática (medición, sin juicio del usuario)
Test `tests/test_display.py::test_sondeo_limites` con el marcador `pantalla` y **saltado salvo con `--con-pantalla`**.

- **Mecánica:** para cada monitor y cada ajuste de la escalera, construir la rampa y pasarle `color.validar_rampa`. Si es ilegible, anotar «rechazada por el validador» sin tocar la pantalla. Si no:
  1. `_escribir`, distinguiendo `RampaRechazada` (Windows devolvió `False`) del éxito;
  2. `leer_rampa`, para medir la diferencia máxima con lo aplicado;
  3. restaurar el original y esperar 0,3 s.
- **Salida:** una tabla impresa con `-s`; nunca falla por los resultados, solo informa.
- **Aviso de fotosensibilidad:** son parpadeos rápidos de pocos milisegundos. Si el usuario lo prefiere, se mira hacia otro lado o se apaga el monitor mientras dura (unos 30 s).

**Escalera** (todos dentro del rango actual):
- Gamma: 1,5 · 2,0 · 2,5 · 3,0 · 3,5 · 4,0
- Brillo: +25 · +50 · +75 · −25 · −50 · −60
- Contraste: +20 · +40 · +82 · −20 · −40
- Temperatura: 5000 · 4000 · 3500 · 3000 · 2500 · 8000 · 10000
- Referencias del autor: 0/5/1,7 · 0/5/2,5

### 2.2 Parte visual (con el usuario mirando el PATRÓN DE GRISES)
Con la TERMINAL DE EMERGENCIA lista. En el monitor 2 (principal), y después repetir 3–4 casos en los monitores 1 y 3:
```powershell
.\.venv\Scripts\python.exe -m vislumbra --gamma 3 --duration 4 --monitor 2
```
Para cada caso: código de salida (`$LASTEXITCODE`), avisos de la terminal, escalones oscuros visibles y si es legible.

Orden: referencias 0/5/1,7 y 0/5/2,5 → gamma 3 y 4 → brillo +75 y −60 → contraste +82 y −40 → temperatura 3000 y 2500. Tras cada caso, la LECTURA debe dar 0.

### 2.3 Tabla de resultados
Se rellena en `docs/resultados-test-fase-1.md`. Sin modelos de monitor ni de GPU: solo «monitor N» y «GPU integrada / dedicada».

| Ajuste | Monitor (GPU) | Validador | Windows (`SetDeviceGammaRamp`) | Diferencia de lectura máx. | ¿Se ve el cambio? | Escalones oscuros visibles | ¿Legible? | Notas |
|---|---|---|---|---|---|---|---|---|
| identidad | 2 (dedicada) | válida | aceptada | 0 | — | n de 21 | sí | |
| gamma 3 | … | | | | | | | |

### 2.4 Criterio para la fase 5 (ampliar rango por registro o driver)
- **No hace falta la fase 5** si todos los ajustes que el usuario juzga útiles en la calibración (§4) los acepta Windows y la lectura coincide en el monitor donde juega. Los rechazos que solo aparezcan por encima de lo útil se documentan, y el rango se recorta a lo aceptado (`GAMMA_MAX`, `TEMPERATURA_MIN`).
- **Se propone la fase 5** si un ajuste útil se rechaza o el controlador lo limita en ese monitor, o si con el máximo aceptado el efecto es insuficiente para las zonas oscuras.
- Proponerla **no es ejecutarla**: se anota la incidencia y se pregunta al autor, con un plan de reversión por escrito. La sesión de test **no toca nunca el registro ni drivers**.

### 2.5 Sondeo fuera de rango (opcional; ver decisión 3)
Solo si el usuario juzga que gamma 4,0 se queda corta. Desde un script en el **scratchpad** (no en el repositorio):
- gamma 4,5, 5,0 y 6,0 (el máximo de RivaTuner), y temperatura 2000;
- 1 s cada uno, restauración en un `finally`, con la TERMINAL DE EMERGENCIA lista;
- se salta `validar_rampa` solo para estas rampas, que siguen siendo monótonas y de rango completo.

## 3. Pruebas de proceso (manuales y seguras)
Comunes a todas:
- empezar con LECTURA (todo a 0);
- terminar con `--reset` + LECTURA;
- usar el ajuste suave `--gamma 1.5` en el monitor 2, salvo que se indique otro;
- **ejecutarlas en una ventana de terminal aparte que abre el usuario**, nunca en la de la sesión de Claude, porque varias pruebas cierran o matan esa ventana.

| # | Prueba | Pasos | Resultado esperado | Cómo deshacer |
|---|---|---|---|---|
| P1 | Ctrl+C real | `--gamma 1.5`, ver el cambio y pulsar Ctrl+C | «Pantalla restaurada.», código 0, LECTURA a 0 | `--reset` |
| P2 | `--persist` | `--gamma 1.3 --persist`; el proceso termina. LECTURA a los 5 s y al minuto. Luego Win+L y desbloquear, y LECTURA. Opcional: suspender y reanudar; abrir y cancelar un aviso de UAC; LECTURA tras cada uno | La rampa **sigue** tras terminar (LECTURA ≠ 0 y el usuario lo ve). Anotar en qué evento se pierde, si se pierde | `--reset` |
| P3a | Cerrar la pestaña de Windows Terminal | En la ventana aparte, `--gamma 1.5` y cerrar **la pestaña** con la X. LECTURA desde otra terminal | Restaurado (LECTURA a 0) gracias a `SetConsoleCtrlHandler` | `--reset` |
| P3b | Cerrar la ventana entera | Igual que P3a, cerrando la ventana completa | Restaurado | `--reset` |
| P3c | Consola clásica | `conhost.exe .\.venv\Scripts\python.exe -m vislumbra --gamma 1.5` y cerrar con la X | Restaurado | `--reset` |
| P4 | Muerte forzada | En la ventana aparte, `--gamma 1.3`. Desde otra: `Get-CimInstance Win32_Process -Filter "Name='python.exe'" \| Where-Object CommandLine -like '*vislumbra*' \| Select-Object ProcessId, CommandLine` y luego `Stop-Process -Id <PID> -Force`. **Nunca** `taskkill /IM python.exe` (mataría otros procesos de Python) | La rampa **queda** (LECTURA ≠ 0); `--reset` la arregla (LECTURA a 0) | `--reset` |
| P5 | Ctrl+Pausa (SIGBREAK, opcional) | `--gamma 1.5` y pulsar Ctrl+Pausa | Restaura; código 1; no imprime «Pantalla restaurada.» (anotar lo que sale) | `--reset` |
| P6 | Monitor concreto | `--gamma 1.5 --duration 5 --monitor N` con N = 1, 2 y 3 | Solo cambia ese monitor | `--reset` |
| P7 | Todos | `--gamma 1.5 --duration 5 --monitor todos` | Cambian los 3 a la vez y vuelven los 3 | `--reset` |
| P8 | Juego sin bordes (opcional) | `--gamma 1.7 --contrast 5` en espera; abrir el juego en modo sin bordes, alternar con Alt+Tab y entrar y salir de menús. LECTURA al volver | Anotar si la rampa se mantiene o el juego la reinicia (importante para el diseño de la fase 2). Usarlo en partida es decisión del usuario | Ctrl+C o `--reset` |

**Decisión sobre `--persist`:**
- Se conserva si P2 confirma que la rampa sigue tras terminar el proceso. Los eventos que la borran se documentan en el README; esa nota de documentación la puede hacer la sesión de test.
- Si no sobrevive, se anota la incidencia para retirarla en la sesión de creación.

## 4. Calibración de la escala

**Preparación:**
- PATRÓN DE GRISES a pantalla completa en el monitor 2;
- luz de la habitación como cuando juega el usuario;
- TERMINAL DE EMERGENCIA lista.

**Protocolo por escalera** (cada paso con `--duration 4`, siempre comparando con el anterior):
- Contraste: 0 → 2 → 5 → 10 → 20 → 40
- Brillo: 0 → 5 → 10 → 20 → 40 → −10 → −20
- Gamma: 1,0 → 1,1 → 1,2 → 1,4 → 1,7 → 2,0 → 2,5

**Para cada paso se anota:**
- **Juicio:** demasiado, bien o poco cambio respecto al paso anterior.
- **Escalones oscuros visibles:** el número del patrón.
- **¿Útil?:** sí o no para ver en lo oscuro.

**Medidas finales:**
- **U (umbral):** el paso más pequeño que el usuario nota de verdad.
- **Valor útil habitual:** con qué valores se queda para jugar.
- **Máximo útil:** a partir de dónde ya se ve mal o no aporta.

**Traducción a constantes en `vislumbra/color.py`.** El objetivo es que el paso mínimo que se nota sea de unas **U\* = 3 unidades**. Así el slider normal tiene margen, y el modo preciso de la fase 2 da pasos más finos todavía.
- **Contraste:** `CONTRASTE_ESCALA_nueva = CONTRASTE_ESCALA × (U* / U_medido)`. Ejemplo: si el usuario nota 1 unidad, 50 × 3 = 150.
- **Brillo:** `BRILLO_POR_UNIDAD_nuevo = BRILLO_POR_UNIDAD × (U_medido / U*)`.
- **Rangos:**
  - `BRILLO_MIN/MAX` y `CONTRASTE_MIN/MAX` se reajustan para que el extremo de la escala coincida con el **máximo útil** en las unidades nuevas, redondeado;
  - `GAMMA_MAX` se fija al máximo útil que Windows acepte (§2);
  - `TEMPERATURA_MIN`, igual.
- Tras cambiar constantes:
  - `pytest -q` en verde, actualizando los tests que fijan números (p. ej. `test_conversiones_de_escala`, `test_valores_de_ejemplo_del_plan` y `test_las_esquinas_del_plan_se_rechazan`);
  - repetir con el usuario las dos referencias para confirmar que «se siente bien».

**Validador** (`RANGO_SALIDA_MIN`, `CENTRO_MIN/MAX`):
- con `--simulate`, buscar los casos límite (p. ej. brillo entre 75 y 100, contraste entre −40 y −82, brillo −60 con gamma 0,6);
- mostrarlos 4 s cada uno al usuario.
- Si un ajuste **aceptado** se juzga ilegible, se **endurece** el umbral (cambio pequeño, permitido).
- Si se **rechaza** uno útil, como `--temp 2500 --contrast -20`, **no se relaja** el umbral global: es un cambio de diseño (I-4) para la sesión de creación.

**`TOLERANCIA_LECTURA`:**
- con las diferencias medidas en §1.4 y §2.1, poner `TOLERANCIA_LECTURA = max(64, 2 × diferencia máxima observada en ajustes aceptados)`;
- si alguna GPU muestra diferencias grandes y sistemáticas (cuantización o recorte), anotarlo como hallazgo, no esconderlo con la tolerancia.

Los cambios de constantes los hace la sesión de test, cada uno en su propio commit. Los de fórmula o diseño se anotan como incidencia.

## 5. Lista de comprobación visual para el usuario
Con la TERMINAL DE EMERGENCIA lista y el PATRÓN DE GRISES abierto. Todo en el monitor 2 salvo que se indique.

| # | Orden | Qué mirar | Resultado (sí/no + nota) |
|---|---|---|---|
| V1 | `--list` | 3 monitores, el 2 como principal | |
| V2 | `--gamma 1.7 --contrast 5 --duration 10` | Más escalones oscuros visibles; sin tinte ni bandas | |
| V3 | `--gamma 2.5 --contrast 5 --duration 10` | Aún más detalle oscuro; ¿sigue siendo agradable? | |
| V4 | `--brightness -40 --duration 6` y `--brightness 40 --duration 6` | Baja y sube sin quedar negra o blanca | |
| V5 | `--contrast 2 --duration 4` y `--contrast 4 --duration 4` | ¿Demasiado, poco o bien? | |
| V6 | `--channel r --gamma 1.5 --duration 6` | Tinte rojizo | |
| V7 | `--temp 4000 --duration 6` y `--temp 9000 --duration 6` | Más cálido; más frío | |
| V8 | `--gamma 1.5 --duration 5 --monitor 1` y luego `--monitor 3` | Solo cambia ese monitor | |
| V9 | `--gamma 1.5 --duration 5 --monitor todos` | Cambian los 3 | |
| V10 | `--gamma 1.5` y Ctrl+C | Vuelve a la normal | |
| V11 | `--brightness 125 --contrast -82` | Error y **ningún** cambio | |
| V12 | (opcional) juego en modo sin bordes, como en P8 | ¿Persiste? | |

Tras la lista: `--reset` y LECTURA.

## 6. Revisión de lectura (segunda mirada al código)
Hallazgos por lectura, no ejecutados todavía. Los marcados como **arreglo pequeño** los puede hacer la sesión de test si el autor lo aprueba (decisiones 1 y 2), siempre con su test. Los demás son incidencias.

| ID | Dónde | Hallazgo | Tipo |
|---|---|---|---|
| I-1 | `display.py` `SesionGamma.aplicar` (líneas 285-293) | El monitor se añade a `aplicados` y `_tocados` **después** de escribir y leer. Si la lectura posterior falla (`ErrorPantalla`) o llega un `KeyboardInterrupt` entre la escritura y el `add`, ese monitor **queda modificado y nadie lo restaura**. Además, `except Exception` no cubre `KeyboardInterrupt` ni `SystemExit`. Arreglo: marcar el monitor como tocado **antes** de `aplicar_rampa` (restaurar un monitor que no llegó a cambiar es inocuo) y usar `except BaseException`. | Arreglo pequeño (tests 1.3.2 y 1.3.3) |
| I-2 | `__main__.py` `main` (líneas 252-267) | Un Ctrl+C fuera de `_esperar` (durante `iniciar` o `aplicar`) sale como traza en inglés. El manejador ya restauró, pero el mensaje y el código son feos. Arreglo: capturar `KeyboardInterrupt` en `main` y mostrar «Interrumpido. Pantalla restaurada.» con código 130. | Arreglo pequeño |
| I-3 | `__main__.py` `_segundos` (línea 57) | `--duration inf` se acepta: espera infinita y el mensaje dice «Se restaurará en inf s.». Arreglo: exigir un número finito. | Arreglo pequeño |
| I-4 | `color.py` `curva_canal` y `validar_rampa` | La temperatura se multiplica antes de validar por canal. Las temperaturas cálidas reducen el rango del canal B, y se rechazan combinaciones razonables (`--temp 2500 --contrast -20`, verificado con `--simulate`). Opciones: validar la curva antes de aplicar la temperatura, o escalar los umbrales por el factor del canal. | Incidencia de diseño |
| I-5 | `__main__.py` `_comprobar_uso` | Combinaciones que se ignoran en silencio: `--simulate --monitor`, `--list --monitor/--channel`, `--reset --channel r`. Proponer error de uso o aviso. | Incidencia menor |
| I-6 | `display.py` `originales_modificados` (línea 270) | Compara con la identidad **exacta**. Si una GPU lee la identidad con pequeñas diferencias, saldría un aviso falso. Hoy los 3 monitores leen exacto. Revisar con los datos de §1.4. | Observación |
| I-7 | `display.py` `aplicar_rampa` (línea 193) | Lee justo después de escribir. Si un controlador aplica de forma asíncrona, habría avisos falsos. Ver en §1.4 y §2.1. | Observación |
| I-8 | `display.py` manejador de consola (líneas 329-332) | Windows lo ejecuta en **otro hilo**. Toma el `RLock` (correcto) y Windows da unos 5 s antes de matar el proceso. Confirmarlo en P3. | Observación |
| I-9 | `display.py` `_restaurar_monitores` | Si el original leído al arrancar era una rampa que Windows no acepta escribir (p. ej. puesta por un driver con más rango), restaurar fallaría y el aviso diría «no se pudo restaurar». Comprobar que el mensaje es comprensible y sugiere `--reset`. | Observación |
| I-10 | Privacidad | `--list` imprime nombres de monitor solo por pantalla. Comprobar que no se guardan en archivos: `git grep -nE "C:\\\\Users\|[A-Za-z0-9._-]+@[A-Za-z0-9.-]+\.[a-z]{2,}"` sin resultados y `git log --format='%ae' \| sort -u` solo con la dirección `noreply`. **No copiar** nombres de monitor ni modelos de GPU en `REGISTRO.md` ni en los resultados. | Comprobación |
| I-11 | `argparse` | Revisar a mano: `--gamma=1,4`, `--gamma -1` (valor, no opción), `--monitor ""`, `--monitor 0`, `--duration 0,5` y `--help` con `--gamma 7`. Lo que no esté cubierto por `test_cli.py` se añade como test. | Tests |

## 7. Cierre: registro y commits

**Entrada en `REGISTRO.md`** («fecha · test (fase 1)»):
- **Verificado por ejecución:** número de tests y resultados de §1.
- **Confirmado por el usuario mirando:** §2.2, §3 y §5.
- **Verificado solo por lectura:** lo que quede.
- **Resultados:** decisión sobre `--persist`, constantes calibradas (antes → después), tolerancia medida, veredicto sobre la fase 5.
- **Incidencias para la sesión de creación:** las I-n que no se arreglaron.
- **Siguiente paso.**
- Sin nombres de monitor ni modelos de GPU.

**Commits pequeños**, en español, sin firmas de IA ni `Co-Authored-By`; cada uno con `pytest -q` en verde. **No hay `push` sin OK del autor**, y el repositorio sigue siendo privado.
1. `Pruebas: marcador de pantalla y restauración garantizada en conftest`
2. `Pruebas: lectura segura de monitores y rampa`
3. `Pruebas: sesión y reversión parcial con dobles de pantalla`
4. `display: marcar el monitor como tocado antes de escribir` (I-1, si se aprueba; quita los `xfail`)
5. `orden: Ctrl+C fuera de la espera y duración finita` (I-2 e I-3, si se aprueban)
6. `Pruebas: escritura real y sondeo de límites con --con-pantalla`
7. `color: calibración de escala y umbrales tras la prueba en pantalla` (si cambian)
8. `display: tolerancia de lectura medida` (si cambia)
9. `Documentación: resultados de la prueba de la fase 1 y registro` (`docs/resultados-test-fase-1.md`, `REGISTRO.md` y la nota de `--persist` en el README si procede)

## 8. Orden de ejecución y riesgos

**Orden recomendado:**
1. Solo lectura: `pytest -q`, `--list` y LECTURA.
2. §1.1–1.3 (conftest, lectura y dobles), con los arreglos I-1 a I-3 si se aprueban.
3. Revisión §6 (I-10, I-11).
4. §1.4 (escritura real suave).
5. §2.1 (sondeo automático).
6. §5 (lista visual).
7. §3 (pruebas de proceso).
8. §2.2 y §4 (sondeo visual y calibración).
9. §2.5 (opcional).
10. Cierre §7.

El usuario solo tiene que estar delante en los pasos 4 a 9.

**Qué puede dejar la pantalla mal y cómo se revierte:**

| Paso | Riesgo | Reversión |
|---|---|---|
| §1.4 y §2.1 | Un test falla a medias | Fixtures de función y de sesión que restauran en el `finalizer`; después `--reset` + LECTURA |
| §2.2, §4 y §5 | Ajuste incómodo | `--duration` restaura solo; Ctrl+C; TERMINAL DE EMERGENCIA |
| P2 y P4 | La rampa queda aplicada a propósito | `--reset` + LECTURA |
| P3 | No restaura al cerrar | `--reset` desde otra terminal (y se anota como incidencia) |
| §2.5 | Rampa fuera de rango aceptada por Windows | 1 s y `finally`; TERMINAL DE EMERGENCIA |
| Cualquiera | No hay terminal visible o legible | Reiniciar Windows (hipótesis: la rampa GDI no sobrevive al reinicio) |
| Calibración | Constantes mal ajustadas | `git revert` del commit de calibración |

**Nada de este plan toca el registro de Windows ni drivers.**

**Hipótesis que este plan debe resolver:**
- Si la rampa persiste tras terminar el proceso (P2).
- Si `SetConsoleCtrlHandler` restaura al cerrar la pestaña, la ventana o conhost (P3).
- Qué rechaza Windows y qué limita el controlador en cada GPU (§2).
- Si la lectura posterior es exacta (§1.4).
- Si un juego en modo sin bordes reinicia la rampa (P8).
- Las constantes de escala y los umbrales (§4).

**Hipótesis que seguirán sin verificar:**
- El comportamiento tras suspender o tras cambiar de resolución, si no se prueba la parte opcional de P2.
- Otros equipos, GPU o monitores distintos de los del autor.
- Si la rampa GDI sobrevive o no a un reinicio. Se asume que no; no se prueba a propósito.

## 9. Decisiones del autor
1. **Arreglo I-1 en la sesión de test** (marcar el monitor como tocado antes de escribir y `except BaseException`). Recomendado: **sí**; es pequeño, claro y evita una pantalla atascada. Alternativa: dejarlo como incidencia.
2. **Arreglos I-2 (Ctrl+C fuera de la espera) e I-3 (`--duration inf`).** Recomendado: **sí**. I-5 queda como incidencia.
3. **Sondeo fuera de rango (§2.5).** Recomendado: **solo si** el usuario juzga que gamma 4,0 se queda corta. Alternativa: hacerlo siempre, para conocer el margen de cara a la fase 5.
4. **Dónde guardar las tablas de resultados.** Recomendado: `docs/resultados-test-fase-1.md`. Alternativa: solo un resumen en `REGISTRO.md`.
5. **Incompatibilidad entre temperatura y validador (I-4).** Recomendado: incidencia de diseño para la sesión de creación. Alternativa, no recomendada: relajar `RANGO_SALIDA_MIN` globalmente, porque debilita la protección.
6. **Criterio sobre `--persist`.** Recomendado: se conserva si sobrevive al terminar el proceso, documentando cuándo se pierde; si no, se retira en la sesión de creación.
