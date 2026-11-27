# Plan de la fase 6: empaquetado como `.exe`

**Estado: aprobado por el autor.** D1 a D4 de §9 se aprobaron con la opción recomendada; D5 a D7 quedan con la recomendada por defecto (el autor puede cambiarlas). **Orden:** la fase 3 (atajos globales) **ya está implementada** (2026-11-27, sin probar con las teclas reales); ahora toca la sesión de creación de este plan y luego una sesión de test del `.exe` (§7).

## 0. Punto de partida (verificado al planificar)
Todo lo de esta sección sale de ejecutar o leer, sin tocar la gamma ni el repositorio. La compilación de prueba se hizo en un entorno virtual y una carpeta temporales, fuera del proyecto.

- **Repositorio:** `main` en `786ce86`, árbol limpio. Python 3.10.11, Tk 8.6.12.
- **PyInstaller se compila sin problemas** con el código actual (6.22.3, ~38 s): sin errores; los avisos son módulos de Linux o Mac que no aplican.
- **Licencia de PyInstaller:** «GPLv2 o posterior con una excepción especial» que permite distribuir programas con el bootloader incrustado sin restricciones. Compatible con GPL v3; además solo se usa para compilar. Sus utilidades (`altgraph` MIT, `pefile` MIT, `pywin32-ctypes` BSD-3, `pyinstaller-hooks-contrib` Apache/GPL) quedan fuera del `.exe`.
- **Resultado de la prueba** (carpeta con 3 ejecutables: app sin consola, consola y una sonda):
  - 37,8 MB en carpeta; **19,3 MB en un `.zip`**; cada `.exe` pesa unos 2 MB y comparten `_internal\`.
  - **Los recursos se resuelven solos:** `tray.ICONOS` apunta a `_internal\assets\iconos` y existe, sin cambiar código (el PyInstaller 6 pone `__file__` bajo `_internal`). El backend de la bandeja (`pystray._win32`) entra sin configurarlo. Tk y la importación de `app`, `tray`, `panel` y `widgets` funcionan.
  - **`vislumbra-cli.exe`:** `--version`, `--list` (3 monitores), `--simulate` y el error de valor (código 1) dan la misma salida que `python -m vislumbra`.
  - **Windows Defender (análisis local, 1 solo motor):** sin amenazas en la carpeta.
  - **Manifiesto:** `asInvoker` (no pide administrador) y sin declaración de DPI: la app sigue llamando a `SetProcessDpiAwareness(1)` al arrancar, como ahora.
  - **Arranque** (`--version`, media de 5): **204 ms** en carpeta frente a **1 906 ms** en un solo archivo (este último descomprime en `%TEMP%` cada vez; 16 MB).
- **Fallo encontrado: sin consola, el `.exe` se rompe con `--help`, `--version` o un error de uso.** Sin consola Windows no da `stdout` ni `stderr` (valen `None`) y `argparse` de Python 3.10 escribe sin comprobarlo: `AttributeError: 'NoneType' object has no attribute 'write'`. Los `print` normales no fallan. Se reprodujo lanzando una sonda sin consola y sin redirecciones.
- **`assets/vislumbra.ico` ya existe** (6 tamaños, de 16 a 256 px; lo genera `herramientas/generar_iconos.py`). El relevo del 2026-11-27 decía que faltaba: ya no.
- **Único recurso que el programa lee de disco:** los iconos PNG de la bandeja (`assets/iconos/`; solo se usa el de 64 px). El logo del panel se dibuja con código. `assets/logo.png` **no** se incluye en el `.exe`.
- **C2PA:** `logo.png` contiene la credencial de OpenAI; **ni `vislumbra.ico` ni los glifos PNG la contienen** (búsqueda de bytes). La pregunta de los términos de OpenAI sigue pendiente, pero afecta a lo derivado del logo, no a un metadato oculto.
- **`keyboard`:** no se importaba en ninguna parte; la prueba se compiló sin ella y funcionó. La fase 3 ya la quitó de `requirements.txt`. **Nuevo desde la fase 3:** `teclado.py` (atajos con `RegisterHotKey`), que esta compilación de prueba **no** incluía: la creación debe comprobar que entra en el `.exe`.
- **«Iniciar con Windows» ya contempla el `.exe`:** `arranque.destino_por_defecto()` usa `sys.executable` con `--oculto` si está congelado.

## 1. Alcance
**Entra:**
- Compilar Vislumbra a ejecutables de Windows con PyInstaller, con script reproducible en el repositorio.
- Arreglar la salida sin consola y dejar un registro de errores (§2.3).
- Verificar el `.exe` real (§7) y documentar cómo compilarlo y usarlo.

**No entra** (se anota para después):

| Queda fuera | Por qué |
|---|---|
| Instalador (Inno Setup, MSI) | Hace falta solo si se reparte a otros; el zip portable basta |
| Firma de código | Cuesta dinero y no hace falta para usarlo en el equipo propio (§8) |
| Publicar una release en GitHub o cambiar la visibilidad | Requiere OK explícito del autor y lo decide cuando quiera |
| Auto-actualización | Fuera de un primer `.exe` |
| Recortar tamaño (excluir `ssl`, etc.) | Ahorra poco y aumenta el riesgo de módulos que falten |
| Cambiar de versión de Python | Ver §8 |

## 2. Diseño

### 2.1 Formato de entrega: carpeta con `.exe` (onedir) en un `.zip`
- Carpeta `dist\Vislumbra\` con `Vislumbra.exe`, `vislumbra-cli.exe` y `_internal\`; se reparte como `.zip` (~19 MB).
- **Un solo archivo (onefile)** es posible (16 MB solo el de consola), pero cada arranque descomprime en `%TEMP%` y tarda ~2 s frente a ~0,2 s. Eso pesa en el arranque con Windows y sobre todo en `--reset`, que es la salida de emergencia.
- **Contrapartida de la carpeta:** `Vislumbra.exe` no funciona si se saca de su carpeta (necesita `_internal\`). Se avisa en el README.

### 2.2 Dos ejecutables: `Vislumbra.exe` (sin consola) y `vislumbra-cli.exe` (con consola)
- **`Vislumbra.exe`** es el que se abre con doble clic o con «Iniciar con Windows»: sin ventana de terminal. Un programa sin consola no escribe en la terminal que lo lanza (en la prueba sí escribió, pero porque la herramienta le pasó una tubería; en una consola interactiva **no está probado**).
- **`vislumbra-cli.exe`** se usa desde terminal: `--list`, `--simulate`, `--reset`, `--perfil`, `--help`. Comparte `_internal\` con el otro, así que solo añade ~2 MB.
- El código es el mismo: un lanzador de tres líneas (`herramientas/lanzador.py`) que llama a `vislumbra.__main__.main`; el `.spec` crea los dos con `MERGE`.
- **Alternativa descartada:** un solo `.exe` sin consola que se «enganche» a la terminal con `AttachConsole`. Funciona a medias (PowerShell no espera a los programas sin consola y el prompt se mezcla con la salida).

### 2.3 Sin consola: `stdout` y `stderr` nulos
Dos cambios pequeños en el código, ambos con pruebas:
1. **Arreglo del fallo:** al empezar `main()`, si `sys.stdout` o `sys.stderr` valen `None`, se sustituyen por un destino válido. Lo mismo para la app (`App._excepcion_tk` imprime tracebacks).
2. **Registro de errores** (decisión §9-D3): ese destino es `%APPDATA%\Vislumbra\vislumbra.log`, abierto en cada arranque con un tope (propuesta: 256 KB, se recorta lo más antiguo). Sin él, un fallo del `.exe` no deja ninguna pista. Solo se activa **sin consola**; con `python -m vislumbra` no cambia nada. Se anota en el README que el registro puede contener rutas del equipo y que nunca se envía a ningún sitio.

### 2.4 Recursos, icono y metadatos
- **Recursos:** `datas = [(assets/iconos → assets/iconos)]`; **no** hace falta tocar `tray.py` (verificado). No se incluye `logo.png`.
- **Icono del `.exe`:** `assets/vislumbra.ico` en los dos ejecutables.
- **Información de versión** (propiedades del archivo en el Explorador): nombre «Vislumbra», descripción, versión tomada de `vislumbra.__version__`. **Sin línea de copyright** hasta que el autor decida el nombre (pendiente en `PLAN.md`).

### 2.5 Script de compilación y dependencias
- `herramientas/vislumbra.spec` (los dos ejecutables, datos, icono, excluye `keyboard` y `pytest`), `herramientas/lanzador.py` y `herramientas/compilar.py` (lanza PyInstaller con salida en `dist\` y `build\`, que ya están en `.gitignore`, y comprueba que existen los dos `.exe`).
- **`requirements-build.txt`** nuevo, con `-r requirements.txt` y `pyinstaller>=6.22,<7`; así `requirements-dev.txt` sigue ligero. Se compila con el `.venv` del proyecto (en esta sesión se probó con un entorno aparte con las mismas versiones de `pystray` y `Pillow`).
- **No se versiona nada compilado:** ni `dist\` ni `build\` ni el `.zip`.

### 2.5.1 Prueba de humo
`herramientas/probar_exe.py <carpeta>`: ejecuta `vislumbra-cli.exe` con `--version`, `--list`, `--simulate --gamma 1.4` y un valor inválido, y comprueba códigos y textos. **No aplica nada a la pantalla.**

### 2.6 «Iniciar con Windows»
No cambia: es la casilla opcional de la bandeja, que ya crea un acceso directo en la carpeta Inicio (sin registro). Con el `.exe` apunta a `Vislumbra.exe --oculto`. Lo nuevo es **probarla** con el `.exe` real y, por fin, reiniciando sesión (nunca se ha verificado). No se activa nunca sin que el autor marque la casilla.

## 3. Archivos que toca la creación

| Archivo | Cambio |
|---|---|
| `vislumbra/__main__.py` | proteger `stdout`/`stderr` nulos; llamar al registro |
| `vislumbra/bitacora.py` (nuevo) | abrir el registro con tope; solo sin consola |
| `tests/test_bitacora.py`, `tests/test_cli.py` | pruebas con `stdout`/`stderr` nulos y del tope del registro |
| `herramientas/lanzador.py`, `vislumbra.spec`, `compilar.py`, `probar_exe.py` (nuevos) | compilación y prueba de humo |
| `requirements-build.txt` (nuevo) | `pyinstaller` |
| `README.md` | sección del `.exe`, compilación, licencia de PyInstaller, aviso del registro y de la carpeta |
| `PLAN.md`, `REGISTRO.md` | fase 6 y entrada de sesión |

**Cómo se deshace:** todo es añadido salvo el arreglo de `__main__.py`. Borrar `dist\` y `build\` quita el `.exe`; el acceso directo de Inicio se quita desmarcando la casilla. No se toca el registro de Windows, ni drivers, ni la gamma al compilar.

## 4. Commits propuestos (en español, sin firmas de IA)
1. `main: sin consola, stdout y stderr nulos ya no rompen --help, --version ni los errores de uso` (+ pruebas).
2. `bitacora: registro de errores en %APPDATA% cuando no hay consola` (+ pruebas), si se aprueba D3.
3. `herramientas: lanzador, .spec y script para compilar el .exe con PyInstaller` + `requirements-build.txt`.
4. `herramientas: prueba de humo del .exe`.
5. Documentación: README, `PLAN.md` y `REGISTRO.md`.

## 5. Comprobación mínima de la sesión de creación
Compilar; `probar_exe.py` en verde; `pytest -q` sin regresiones (837 en verde y 6 saltadas de partida tras la fase 3, más las nuevas); lanzar `Vislumbra.exe --version` sin redirecciones no debe dejar una ventana de error de PyInstaller. **No** se prueba a fondo la app: eso es §7.

## 6. Riesgos
- **Falsos positivos de antivirus.** Solo se probó Windows Defender en local. No se ha subido nada a servicios externos (subirlo es enviar el archivo a terceros: solo con OK).
- **SmartScreen y «Smart App Control» de Windows 11** pueden advertir o bloquear un `.exe` sin firmar y sin reputación cuando se descarga de Internet. **Sin verificar** (en este equipo los `.exe` compilados se ejecutaron sin avisos, porque no vienen de Internet).
- **Python 3.10:** según el calendario de Python (PEP 619), su soporte termina en octubre de 2026, y el `.exe` lleva el intérprete dentro. Para uso propio basta; antes de **repartirlo** conviene compilar con una versión con soporte (instalar otra implica cambios en el equipo: se pregunta antes).
- **Sin consola** los errores no se ven: de ahí el registro (§2.3).
- **`menus_oscuros`** usa funciones sin documentar de `uxtheme.dll`; el `.exe` no cambia nada, pero sigue valiendo lo ya anotado.
- Carpeta movida o `_internal\` borrada: el `.exe` no arranca; el aviso del acceso directo de Inicio ya detecta que el destino no existe.

## 7. Qué probará la sesión de test del `.exe`
**Por ejecución** (sin tocar la pantalla): `probar_exe.py`; los atajos del `.exe` (registro de combinaciones y errores de conflicto); registro de errores sin consola; el arranque de `Vislumbra.exe` desde una carpeta con espacios y tildes y desde otra unidad; instancia única (segundo `Vislumbra.exe` avisa al primero); `vislumbra-cli.exe --perfil` con la app abierta; `vislumbra-cli.exe --reset` con la app abierta (suelta la pantalla) y sin ella.
**Con el autor mirando** (lista visual): **pulsar de verdad** Ctrl+Alt+P y Ctrl+Alt+0 (emergencia) con el `.exe` (ninguna combinación se ha pulsado aún, ni siquiera con Python; ver `docs/plan-fase-3.md` §7); doble clic abre bandeja y panel; icono del `.exe` en el Explorador y de la bandeja (claro y oscuro); el panel idéntico al de `python -m vislumbra` con DPI 1,25; un ajuste real se aplica; «Salir» restaura la pantalla; cerrar desde el Administrador de tareas y `--reset`; «Iniciar con Windows» (crea el acceso, apunta al `.exe`, **reiniciar sesión y ver que arranca solo con el icono**); mover la carpeta y ver el aviso; arranque en frío (tiempo hasta ver el icono).
Tras cualquier prueba que toque la gamma: `vislumbra-cli.exe --reset`.

## 8. Qué se queda sin verificar al planificar
Funcionamiento de la **app** compilada (solo se probó la consola y una sonda; no se abrió la app real para no tocar la gamma sin que el autor mire); un `.exe` sin consola lanzado desde un acceso directo real; SmartScreen y Smart App Control; otros antivirus; Windows 10 (la app usa DWM de Windows 11 para las esquinas, ya con respaldo); otras resoluciones y DPI.

## 9. Decisiones del autor
D1 a D4: **aprobadas con la opción recomendada** (2026-11-27). D5 a D7: recomendada por defecto, sin objeción.

| # | Decisión | Recomendada | Alternativa |
|---|---|---|---|
| D1 | Formato de entrega | **Carpeta + `.zip` portable** (arranque 0,2 s) | Un solo `.exe` (~2 s por arranque) o instalador (después) |
| D2 | Ejecutables | **Dos:** `Vislumbra.exe` sin consola y `vislumbra-cli.exe` con consola | Uno solo sin consola (las órdenes `--list`, `--help`… no se verían) |
| D3 | Errores sin consola | **Registro en `%APPDATA%\Vislumbra\vislumbra.log`** con tope de tamaño | Descartarlos (más simple, pero sin pistas ante un fallo) |
| D4 | Orden con la fase 3 | **Fase 3 primero** (hecho) (se quita `keyboard` y el `.exe` ya incluye los atajos y la emergencia por teclado) | Empaquetar ya (`keyboard` ya no se usa; se vuelve a compilar tras la fase 3) |
| D5 | `pyinstaller` en un `requirements-build.txt` aparte | Sí | En `requirements-dev.txt` |
| D6 | Copyright en las propiedades del `.exe` | Omitirlo hasta decidir el nombre | Poner el usuario de GitHub |
| D7 | Firma, instalador, release y subida a VirusTotal | **Fuera de esta fase** | — |
