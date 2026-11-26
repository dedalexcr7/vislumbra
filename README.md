# Vislumbra

App **gratuita** y sencilla para Windows que ajusta la imagen de la pantalla: brillo, contraste, gamma (global y por canal R/G/B) y temperatura de color, desde un icono en la bandeja del sistema. Pensada para ver mejor las zonas oscuras en juegos y otros usos.

> **Estado:** en desarrollo, todavía sin versión utilizable. Consulta `PLAN.md` para el diseño y las fases.

## Qué pretende ofrecer
- Control fino de los valores (modo preciso, rueda del ratón, campo numérico).
- Perfiles creados por cada usuario y atajos de teclado globales.
- Restauración de la pantalla original al salir y un atajo de emergencia.

## Uso de la orden (fase 1, sin interfaz todavía)
Requiere Windows y Python 3.10 o superior. Desde la carpeta del proyecto, con el entorno virtual activo (`pip install -r requirements.txt`):

```
python -m vislumbra --list                          # monitores activos
python -m vislumbra --simulate --gamma 1.4          # calcula la rampa, sin tocar la pantalla
python -m vislumbra --gamma 1.4                     # aplica; Ctrl+C restaura
python -m vislumbra --gamma 1.2 --duration 5        # aplica 5 segundos y restaura solo
python -m vislumbra --gamma 1.7 --contrast 5 --monitor todos
python -m vislumbra --channel r --gamma 1.5         # solo el canal rojo
python -m vislumbra --temp 4000                     # temperatura de color en kelvin
python -m vislumbra --reset                         # rampa neutra en todos los monitores
```

Los decimales admiten punto o coma. Por defecto actúa sobre el monitor principal (`--monitor principal|todos|N`).
Mientras la orden está en marcha, la rampa se mantiene; al cerrarla (Ctrl+C, cerrar la ventana) se restaura la original. Con `--persist` se queda aplicada: úsalo solo si sabes deshacerlo con `--reset`.

**Si algo sale mal:** abre otra terminal y ejecuta `python -m vislumbra --reset`. Si no puedes, reiniciar Windows también devuelve la pantalla a la normal (sin verificar).
Los rangos son provisionales y la orden rechaza ajustes que dejarían la pantalla casi ilegible.

## Cómo funciona
Usa la rampa de gamma de Windows (GDI), sin tocar el registro ni los drivers. La configuración de cada usuario se guarda en `%APPDATA%\vislumbra`, fuera del repositorio.

## Licencia
[GNU GPL v3](LICENSE). Dependencias: `pystray` (LGPLv3), `keyboard` (MIT) y `Pillow` (MIT-CMU), todas compatibles con GPL v3.
