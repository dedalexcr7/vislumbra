# Vislumbra

App **gratuita** y sencilla para Windows que ajusta la imagen de la pantalla: brillo, contraste, gamma (global y por canal R/G/B) y temperatura de color, desde un icono en la bandeja del sistema. Pensada para ver mejor las zonas oscuras en juegos y otros usos.

> **Estado:** en desarrollo (fase 2 de 6 hecha: orden de terminal, panel, bandeja y perfiles). Todavía sin probar a fondo ni empaquetar. Consulta `PLAN.md` para el diseño y las fases.

## Qué pretende ofrecer
- Control fino de los valores (modo preciso, rueda del ratón, campo numérico).
- Perfiles creados por cada usuario y atajos de teclado globales.
- Restauración de la pantalla original al salir y un atajo de emergencia.

## La app (panel y bandeja)
Requiere Windows y Python 3.10 o superior. Desde la carpeta del proyecto, con el entorno virtual activo (`pip install -r requirements.txt`):

```
python -m vislumbra          # abre la app: icono en la bandeja y panel
```

- **Panel:** brillo, contraste, gamma y temperatura, con canales R, G y B vinculados o separados. Cada deslizador admite arrastrar (con **Mayús**, 10 veces más lento), rueda del ratón y flechas, doble clic para volver al neutro y escribir el número (coma o punto). El **modo preciso** hace que el deslizador cubra solo una ventana pequeña alrededor del valor.
- **Perfiles:** «Normal» viene incluido y no se modifica. Al mover un deslizador con Normal, se crea «Perfil N» (sin guardar). Puedes guardar, guardar como, renombrar y borrar. Se guardan en `%APPDATA%\Vislumbra\config.json`, fuera del repositorio.
- **Monitores:** cada monitor **sigue al perfil activo** o tiene un **perfil fijo** (por ejemplo, uno de código con menos brillo que no cambia al cambiar de perfil).
- **A/B** muestra la pantalla normal un momento (también con la barra espaciadora); **Restablecer** pone el perfil en neutro durante 10 s con «Deshacer»; **Activo** la apaga del todo.
- **Seguridad:** el control se detiene en el último valor que Windows y el validador aceptan, un ajuste fuerte (más del 40 % de desviación) se deshace solo a los 10 s si no pulsas «Mantener», y al salir se restaura la pantalla original. Si algo cambia la rampa (un juego), la app la vuelve a aplicar; si es un conflicto continuo, avisa y deja de insistir.
- **Perfil automático por programa:** botón «Programas…» del panel (o menú de la bandeja). Asocias un programa (por el nombre de su `.exe`, por ejemplo `juego.exe`, elegido entre los abiertos o escrito) a un perfil. Mientras el programa está abierto se activa ese perfil; al cerrarlo vuelve el que tenías. El perfil que pone un programa **no se guarda como tu perfil activo** (si el PC se apaga en mitad del juego, al volver tendrás el tuyo), y si cambias de perfil a mano durante el juego, se respeta tu cambio. Cada programa tiene un **alcance**: **el monitor donde esté** su ventana (los demás monitores no cambian, ni el perfil activo; sirve para tener todos los monitores con perfil fijo y que solo cambie el del juego, y el perfil sigue a la ventana si la arrastras a otro monitor; minimizar o hacer alt-tab no lo quita), **un monitor concreto** (siempre ese) o **el perfil activo** (cambia el perfil activo global). Al elegir un programa de la lista puedes cambiarle el perfil, el alcance e incluso el nombre con «Guardar cambios», sin borrarlo. Lo que ponen los programas nunca se guarda: al cerrarlos, cada monitor vuelve a su perfil fijo. Sobre un mismo monitor manda el último programa que se abrió. Solo se guarda el nombre del `.exe`, nunca la ruta, y se detecta leyendo la lista de procesos (como el Administrador de tareas), sin tocar el juego. Un programa ejecutado como administrador también se ve.
- **Iniciar con Windows (opcional, desactivado por defecto):** casilla en el menú de la bandeja. Crea un acceso directo `Vislumbra.lnk` en tu carpeta Inicio (`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`), sin tocar el registro, y al iniciar sesión abre solo el icono (`--oculto`). Al desmarcarla se borra. Hoy lanza `pythonw.exe -m vislumbra` del entorno virtual, así que **no muevas la carpeta del proyecto** (la app avisa si el acceso apunta a algo que ya no existe); con el `.exe` apuntará a él.
- **Bandeja:** clic izquierdo muestra u oculta el panel. El menú permite activar o desactivar, cambiar de perfil, comparar y salir (restaura la pantalla).
- **Desde otra terminal:** `python -m vislumbra --perfil NOMBRE` (o `--perfil siguiente`) cambia el perfil activo de la app abierta; `python -m vislumbra --reset` la desactiva y devuelve la pantalla a la normal (es la salida de emergencia, junto con «Activo» y «Salir»). Con la app abierta, los ajustes sueltos (`--gamma`, etc.) se rechazan.

## Uso de la orden de terminal
Sin la app abierta, también se puede aplicar un ajuste desde la terminal:

```
python -m vislumbra --list                          # monitores activos
python -m vislumbra --simulate --gamma 1.4          # calcula la rampa, sin tocar la pantalla
python -m vislumbra --gamma 1.4                     # aplica; Ctrl+C restaura
python -m vislumbra --gamma 1.2 --duration 5        # aplica 5 segundos y restaura solo
python -m vislumbra --gamma 1.7 --contrast 5 --monitor todos
python -m vislumbra --channel r --gamma 1.5         # solo el canal rojo
python -m vislumbra --temp 4000                     # temperatura de color en kelvin
python -m vislumbra --perfil NOMBRE                 # aplica un perfil guardado (sin la app abierta)
python -m vislumbra --reset                         # rampa neutra en todos los monitores
```

Los decimales admiten punto o coma. Por defecto actúa sobre el monitor principal (`--monitor principal|todos|N`).
Mientras la orden está en marcha, la rampa se mantiene; al cerrarla (Ctrl+C, cerrar la ventana) se restaura la original. Con `--persist` se queda aplicada: úsalo solo si sabes deshacerlo con `--reset`.
Con `--persist` la rampa sigue aplicada cuando el proceso ya ha terminado. Comprobado (un solo equipo): tras 1 minuto y tras bloquear y desbloquear la sesión (Win+L). **Sin comprobar:** suspensión, avisos de control de cuentas (UAC), cambios de resolución y reinicio. Se deshace siempre con `--reset`. Si el proceso se mata a la fuerza (sin `--persist`), la rampa también se queda aplicada hasta `--reset`.

**Si algo sale mal:** abre otra terminal y ejecuta `python -m vislumbra --reset`. Si no puedes, reiniciar Windows también devuelve la pantalla a la normal (sin verificar).
Los rangos se calibraron en un solo equipo y pueden ajustarse. La orden rechaza ajustes que dejarían la pantalla casi ilegible, y Windows rechaza los que se desvían demasiado de la rampa neutra (por ejemplo, temperaturas por debajo de unos 3300 K).

## Cómo funciona
Usa la rampa de gamma de Windows (GDI), sin tocar el registro ni los drivers. La configuración de cada usuario se guarda en `%APPDATA%\Vislumbra`, fuera del repositorio. El archivo guarda, para recordar qué perfil lleva cada monitor, el identificador de Windows de cada monitor (incluye un código del modelo); no se envía a ningún sitio.

## Logo
El logo (`assets/logo.png`) se generó con ChatGPT, e incluye la credencial de contenido (C2PA) que incrusta el generador. Los iconos de la bandeja salen de él con `herramientas/generar_iconos.py`. **Pendiente antes de hacer público el repositorio:** revisar los términos vigentes de OpenAI sobre la propiedad de lo generado y anotar aquí el resultado.

## Licencia
[GNU GPL v3](LICENSE). Dependencias: `pystray` (LGPLv3), `keyboard` (MIT) y `Pillow` (MIT-CMU), todas compatibles con GPL v3 (`keyboard` se usará en la fase 3). Solo para desarrollo: `pytest` (MIT).
