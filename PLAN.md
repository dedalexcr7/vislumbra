# Plan de `vislumbra`

## Objetivo
Una app **gratuita** de Windows 11 sencilla para ajustar la imagen de la pantalla (brillo, contraste, gamma y color), pensada para ver mejor las zonas oscuras en juegos u otros usos. Reproduce lo que hace la pestaña de color de RivaTuner v2.24c, pero con una interfaz rápida y un control mucho más preciso.

**No está atada a ningún juego ni usuario concreto:** cada persona crea sus propios perfiles. La app solo trae un estado neutro («Normal»); los ajustes del autor son solo referencia para probar.

## Decisiones tomadas
| Tema | Decisión |
|---|---|
| Parámetros | Brillo, contraste, gamma (global y por canal R/G/B) y temperatura de color |
| Tecnología | Python 3.10 (ya instalado), entorno virtual dentro del proyecto |
| Uso | Icono en la bandeja + panel emergente + perfiles + atajos globales |
| Interfaz | Panel oscuro, compacto, sliders grandes con valor numérico editable |
| Nombre | **Vislumbra** (paquete y carpeta: `vislumbra`) |
| Licencia | Gratuita, bajo **GPL v3** (decidido por el autor para que las versiones derivadas sigan abiertas). El archivo `LICENSE` se añade en la fase 0 |
| Caso de prueba del autor | Tarkov, siempre en modo sin bordes (la rampa gamma funciona bien así) |
| Método | GDI gamma ramp, el mismo que usa RivaTuner (su ventana lo indica: «Control via: GDI gamma ramp») |
| Perfiles | Los crea el usuario; la app solo incluye «Normal» (neutro). Ver sección «Perfiles» |
| Precisión | Requisito clave: control fino y **modo preciso**. Ver sección «Control fino» |
| Enfoque de riesgo | Empezar con lo sencillo y seguro; lo avanzado solo si hace falta y con OK |
| Repositorio | GitHub, **privado** al principio; se hará público cuando el usuario lo decida |
| Registro | `REGISTRO.md`, una entrada por sesión |

Aclaración sobre anticheat: el cambio de gamma es del sistema, no se inyecta en el juego. Se cree que Tarkov usa BattlEye, pero no está verificado; la decisión de usarla es del usuario.

## Referencia: la ventana de RivaTuner v2.24c («Low-level color adjustment»)
Datos leídos de capturas del vídeo de referencia:
- Tres sliders: **Brillo** (−125 a 125), **Contraste** (−82 a 82) y **Gamma** (0,5 a 6,0).
- Selector de canales («All channels» o canal individual) y modo «classic B/C/G».
- Gráfico de la curva resultante, en vivo.
- Esquemas de color con nombre (guardar, borrar, elegir), botón «Defaults» y opción de aplicar al arrancar Windows.

### Perfiles
- Un perfil es simplemente **una configuración guardada por el usuario** (nombre + valores de brillo, contraste, gamma, canales y temperatura). Cada usuario crea los suyos, para el juego o uso que quiera.
- **No se incluyen perfiles de juegos** ni del autor. Solo existe «Normal» (neutro: brillo 0, contraste 0, gamma 1,0), que sirve de reinicio y no se puede borrar.
- Crear, renombrar, duplicar y borrar perfiles; cada uno puede tener un atajo de teclado opcional (y, en la fase 4, un proceso asociado).
- **Valores de referencia del autor, solo para pruebas** (leídos de las capturas de RivaTuner; no se distribuyen como perfiles): brillo 0 / contraste 5 / gamma 1,7 («oscuro») y brillo 0 / contraste 5 / gamma 2,5 («muy oscuro»).

### Calibración de la escala
Los rangos de RivaTuner (brillo −125 a 125, contraste −82 a 82, gamma 0,5 a 6,0) se usan como punto de partida, pero su fórmula exacta no se conoce y el autor ya no lo tiene instalado, así que **no hay comparación lado a lado**. Se calibra probando: en la sesión de test, el usuario mueve los valores de referencia y se decide a ojo cuánto cambia cada paso, ajustando la conversión interna hasta que se sienta razonable.

### Control fino (requisito clave)
Problema de la herramienta original: la escala es demasiado sensible; pasar de contraste 5 a 7 ya cambia mucho y el slider obliga a mover el ratón casi nada. La app nueva debe permitir ajustar con precisión:
- **Respuesta no lineal del slider:** más resolución cerca del valor neutro y de los valores habituales.
- **Mantener Shift mientras se arrastra:** el movimiento se reduce unas 10 veces (modo fino).
- **Rueda del ratón y flechas del teclado:** un paso pequeño fijo (gamma 0,01; contraste y brillo 0,1).
- **Campo numérico editable** junto a cada slider y botones − / + .
- **Zoom de rango (opcional):** una ventana de ±10 % alrededor del valor actual.
- **Modo preciso (interruptor, pensado para perfeccionistas):** los sliders pasan a tener un rango reducido alrededor del valor actual y pasos de 0,01 (o equivalente), con el campo numérico siempre visible. Se activa y desactiva desde el panel y con un atajo. Mientras no esté activo, la app usa el modo normal.
- Aplicación **en vivo** (sin botón «Apply») y sin congelar la interfaz: la rampa se aplica en un hilo aparte con debounce, y se reaplica sola si el juego o el sistema la reinician. El vídeo muestra que la app antigua «se queda pegada» entre cambios; la causa no está verificada, pero este diseño la evita.

### Competencia existente (no verificada a fondo)
La búsqueda web muestra herramientas parecidas: **GammaBoost+** (Steam, para Windows, con sliders de precisión de gamma, brillo y contraste; según el autor es de pago), **Gammy / DynaGammy** y otras. Vislumbra se diferencia por ser **gratuita** y por su control fino. Conviene mirar esas herramientas como referencia de interfaz y de problemas conocidos antes de la fase 2.

## Cómo funciona (diseño técnico)
- **Gamma, contraste y temperatura:** rampa de gamma de Windows (`SetDeviceGammaRamp` / `GetDeviceGammaRamp` de `gdi32`, vía `ctypes`), con un contexto de dispositivo por monitor (`EnumDisplayDevices` + `CreateDCW`).
- **Cálculo por canal** (valores de entrada normalizados `v = i/255`):
  1. gamma: `v = v ** (1 / gamma)`
  2. contraste: `v = (v - 0.5) * contraste + 0.5`
  3. brillo: `v = v + brillo`
  4. temperatura: multiplicar cada canal por el factor RGB del Kelvin elegido (6500 K = neutro)
  5. limitar a [0, 1] y escalar a 16 bits
- **Brillo por hardware** (opcional, fase aparte): `screen_brightness_control` (WMI en portátiles, DDC/CI en monitores externos). Es independiente del brillo por software de la rampa.
- **Atajos globales:** librería `keyboard`. **Bandeja:** `pystray`. **Panel:** `tkinter` (sin dependencias pesadas).
- **Persistencia:** `%APPDATA%\vislumbra\perfiles.json` (nunca dentro del repositorio).
- **Seguridad:** guardar la rampa original al arrancar y restaurarla al salir (`atexit`); opción «Restablecer» en la bandeja; atajo de emergencia (propuesta: `Ctrl+Alt+0`); rangos limitados; confirmación con reversión automática a los 10 s para valores extremos; reaplicar la rampa cada pocos segundos por si un juego la reinicia.

## Estructura de archivos prevista
```
vislumbra/
├─ CLAUDE.md          instrucciones de sesión
├─ PLAN.md            este documento
├─ REGISTRO.md        registro de trabajo
├─ README.md          (fase 0) descripción pública, sin datos personales
├─ requirements.txt
├─ .gitignore         .venv/, __pycache__/, config local
├─ vislumbra/
│  ├─ __main__.py     arranque y --reset
│  ├─ display.py      E/S con Windows: monitores, leer/aplicar/restaurar la rampa, sesión
│  ├─ color.py        funciones puras: cálculo de canales, Kelvin → RGB, validación de la rampa
│  ├─ panel.py        panel emergente
│  ├─ tray.py         icono de bandeja
│  ├─ profiles.py     perfiles en JSON
│  ├─ hotkeys.py      atajos globales
│  └─ watcher.py      perfil automático por proceso (fase 4)
└─ tests/             pytest sobre las funciones puras y lectura/escritura de rampa
```

## Fases
Cada fase termina con una entrada en `REGISTRO.md` y, si procede, un commit.

- **Fase 0 – Preparación:** entorno virtual, `requirements.txt`, `.gitignore`, `git init`, repositorio **privado** en GitHub (con OK del usuario antes del primer `push`), `README.md` básico.
- **Fase 1 – Núcleo:** `color.py` y `display.py`: aplicar, leer y restaurar la rampa, con una orden de terminal para probarla (`python -m vislumbra --gamma 1.4`, `--reset`). Sin interfaz todavía.
- **Fase 2 – Panel y bandeja:** sliders por canal con opción «vincular canales», brillo, contraste, gamma, temperatura, botón de restablecer y botón A/B para comparar con la pantalla normal.
- **Fase 3 – Perfiles y atajos:** perfiles creados por el usuario (crear, renombrar, duplicar, borrar; solo «Normal» viene incluido); atajos globales por perfil, para A/B, para el modo preciso y para el reinicio de emergencia.
- **Fase 4 – Perfil por juego (opcional):** el usuario asocia a un perfil el `.exe` de cualquier juego o programa; la app lo detecta, aplica el perfil y restaura al cerrarlo.
- **Fase 5 – Avanzado (solo si la 1–3 se quedan cortas):** ampliar el rango de la rampa con la clave de registro `GdiICMGammaRange`, o usar la API del driver (NVAPI / AMD ADL). **Requiere preguntar y tener un plan de reversión antes de tocar nada.**
- **Fase 6 – Empaquetado (opcional):** `.exe` con PyInstaller y arranque con Windows.

## Riesgos conocidos
- Windows ignora rampas muy alejadas de la lineal; el efecto puede ser más suave que en RivaTuner antiguo. Esto se mide en la primera sesión de test antes de pasar a la fase 5.
- Algunos monitores externos no aceptan DDC/CI; el brillo por hardware puede no funcionar.
- `keyboard` puede requerir permisos elevados para atajos globales en ciertos contextos.
- Si la app muere sin restaurar, la rampa queda aplicada hasta reiniciar o ejecutar `--reset`.

## Antes de hacer público el repositorio
- Buscar rutas personales, correos, nombres y claves en todo el historial, no solo en los archivos actuales.
- Licencia GPL v3 elegida: comprobar que todas las dependencias (`pystray`, `keyboard`, `screen_brightness_control`, etc.) son compatibles con GPL v3 y dejar constancia de ello.
- Decidir con el autor qué nombre va en el aviso de copyright («Copyright 2026 …»): nombre real o solo el usuario de GitHub.
- Revisar que el README no afirme nada sin verificar (compatibilidad con anticheats, por ejemplo).
- Confirmar la autoría y la licencia del logo (ver «Logo» en «Pendiente de decidir»).

## Nombre
**Vislumbra** (confirmado por el autor; de «vislumbrar»: ver algo con poca claridad). Paquete y carpeta: `vislumbra`.
Comprobado el 2026-11-26: la búsqueda web no encuentra ninguna app, programa o juego con ese nombre; 0 repositorios en GitHub con ese nombre en el título; el nombre de usuario/organización `vislumbra` en GitHub está libre; libre en PyPI.
**No comprobado:** marcas registradas, Microsoft Store, Steam y nombres parecidos en otros idiomas. Existe un repositorio con el nombre cercano «Vislumbre» (otra palabra, sin relación con pantallas), y por eso se eligió la forma «Vislumbra».
Descartados: «Nictalope» (válido, pero no elegido), «Candil» (187 repos) y «Tenebra» (197 repos).

## Pendiente de decidir
- Nombre para el aviso de copyright del `LICENSE` (ver arriba).
- **Logo:** el usuario aportó un icono (PNG 1254×1254, en la raíz, sin versionar). Para la bandeja (fase 2) hace falta una versión transparente y legible a 16–48 px, y un `.ico`. Decidir dónde guardarlo (`assets/`) y su licencia.
- Cuándo hacer público el repositorio: lo decide el autor; hasta entonces permanece **privado**.
- ~~Cuenta de GitHub~~ → resuelto: `github.com/dedalexcr7` (verificada, existe). Repositorio previsto: `dedalexcr7/vislumbra`, libre el 2026-11-26. Se crea **privado**, con OK del usuario antes del primer `push`.
