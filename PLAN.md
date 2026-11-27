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
- **Atajos globales:** `RegisterHotKey` de Windows en un hilo propio (`ctypes`), **sin la librería `keyboard`**, que usa un gancho global que ve todas las teclas (ver `docs/plan-fase-3.md`). **Bandeja:** `pystray`. **Panel:** `tkinter` (sin dependencias pesadas).
- **Persistencia:** `%APPDATA%\Vislumbra\config.json` (perfiles, perfil activo y asignación por monitor; nunca dentro del repositorio).
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
│  ├─ escala.py       (fase 2) posición del deslizador ↔ valor, pasos y formato
│  ├─ perfiles.py     (fase 2) perfiles, perfil activo y asignación por monitor en JSON
│  ├─ estado.py       (fase 2) modelo del panel, sin Tk
│  ├─ aplicador.py    (fase 2) hilo que aplica y vigila la rampa
│  ├─ sistema.py      (fase 2) instancia única, eventos con nombre y DPI
│  ├─ panel.py        (fase 2) panel emergente
│  ├─ tray.py         (fase 2) icono de bandeja
│  ├─ app.py          (fase 2) arranque y cierre de la app
│  ├─ atajos.py       (fase 3) combinaciones de teclas, validación y valores por defecto (lógica pura)
│  ├─ teclado.py      (fase 3) atajos globales con RegisterHotKey en su propio hilo
│  └─ watcher.py      perfil automático por proceso (fase 4)
├─ assets/            (fase 2) logo e iconos
├─ herramientas/      (fase 2) generar_iconos.py
└─ tests/             pytest sobre las funciones puras y lectura/escritura de rampa
```

## Fases
Cada fase termina con una entrada en `REGISTRO.md` y, si procede, un commit.

- **Fase 0 – Preparación:** entorno virtual, `requirements.txt`, `.gitignore`, `git init`, repositorio **privado** en GitHub (con OK del usuario antes del primer `push`), `README.md` básico.
- **Fase 1 – Núcleo:** `color.py` y `display.py`: aplicar, leer y restaurar la rampa, con una orden de terminal para probarla (`python -m vislumbra --gamma 1.4`, `--reset`). Sin interfaz todavía.
- **Fase 2 – Panel, bandeja y perfiles** (**implementada**, pendiente de test; plan: `docs/plan-fase-2.md`):
  - Panel con sliders por canal y opción «vincular canales»: brillo, contraste, gamma y temperatura. Incluye control fino y modo preciso, gráfico de la curva, restablecer y A/B.
  - Perfiles creados por el usuario: crear, guardar, guardar como, renombrar y borrar. Solo «Normal» viene incluido.
  - **Cada monitor sigue al perfil activo o tiene un perfil fijo**; por ejemplo, un monitor de código con su propio ajuste que no cambia al cambiar el perfil activo.
  - Cambio de perfil desde el panel, desde la bandeja y con `--perfil`.
  - Vigilancia que vuelve a aplicar la rampa si algo la reinicia, e instancia única.
- **Fase 3 – Atajos globales y menú para personalizarlos** (**implementada**, pendiente de probar pulsando y en un juego; plan: `docs/plan-fase-3.md`):
  - Acciones: siguiente y anterior perfil, uno por perfil (también «Normal»), A/B, activo, mostrar u ocultar el panel, modo preciso y **emergencia** (suelta la pantalla sin pasar por la interfaz).
  - Menú «Atajos…» para grabar, cambiar y quitar combinaciones, con detección de conflictos con otras aplicaciones y aviso de AltGr, y aviso opcional al usar un atajo (ninguno, sonido o notificación).
  - Se quita la dependencia `keyboard`.
  - **Aparcado para después:** duplicar, reordenar, importar y exportar perfiles y atajos; ajuste rápido de gamma o brillo con atajos.
- **Fase 4 – Perfil por juego** (**implementada**, pendiente de probar en un juego; ver `REGISTRO.md`): el usuario asocia a un perfil el `.exe` de cualquier juego o programa; la app lo detecta, aplica el perfil y restaura al cerrarlo.
- **Fase 5 – Avanzado (solo si la 1–3 se quedan cortas):** ampliar el rango de la rampa con la clave de registro `GdiICMGammaRange`, o usar la API del driver (NVAPI / AMD ADL). **Requiere preguntar y tener un plan de reversión antes de tocar nada.**
- **Fase 6 – Empaquetado (opcional, siguiente):** `.exe` con PyInstaller y arranque con Windows (este último, solo con OK explícito). Puntos a resolver y relevo en la entrada del 2026-11-27 de `REGISTRO.md`.

## Riesgos conocidos
- Windows ignora rampas muy alejadas de la lineal; el efecto puede ser más suave que en RivaTuner antiguo. Esto se mide en la primera sesión de test antes de pasar a la fase 5.
- Algunos monitores externos no aceptan DDC/CI; el brillo por hardware puede no funcionar.
- Los atajos con `RegisterHotKey` pueden no saltar con una ventana ejecutada como administrador, o con un juego en pantalla completa exclusiva (sin verificar; se prueba en el test de la fase 3). Una combinación solo la puede tener una aplicación.
- Si la app muere sin restaurar, la rampa queda aplicada hasta reiniciar o ejecutar `--reset`.

## Antes de hacer público el repositorio
- Buscar rutas personales, correos, nombres y claves en todo el historial, no solo en los archivos actuales.
- Licencia GPL v3 elegida: comprobar que todas las dependencias (`pystray`, `Pillow`, `screen_brightness_control` si llega a usarse, etc.; `keyboard` se quita en la fase 3) son compatibles con GPL v3 y dejar constancia de ello.
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
- **Logo:** el usuario aportó un icono hecho con ChatGPT (PNG 1254×1254, en la raíz, sin versionar). En la fase 2 se guarda en `assets/` y los iconos de la bandeja (solo el glifo, transparente) se generan por script. **Pendiente antes de hacer público el repositorio:** revisar los términos vigentes de OpenAI sobre la propiedad de lo generado y anotarlo en el README.
- Cuándo hacer público el repositorio: lo decide el autor; hasta entonces permanece **privado**.
- ~~Cuenta de GitHub~~ → resuelto: `github.com/dedalexcr7` (verificada, existe). Repositorio previsto: `dedalexcr7/vislumbra`, libre el 2026-11-26. Se crea **privado**, con OK del usuario antes del primer `push`.
