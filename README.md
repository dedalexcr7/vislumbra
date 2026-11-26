# Vislumbra

App **gratuita** y sencilla para Windows que ajusta la imagen de la pantalla: brillo, contraste, gamma (global y por canal R/G/B) y temperatura de color, desde un icono en la bandeja del sistema. Pensada para ver mejor las zonas oscuras en juegos y otros usos.

> **Estado:** en desarrollo, todavía sin versión utilizable. Consulta `PLAN.md` para el diseño y las fases.

## Qué pretende ofrecer
- Control fino de los valores (modo preciso, rueda del ratón, campo numérico).
- Perfiles creados por cada usuario y atajos de teclado globales.
- Restauración de la pantalla original al salir y un atajo de emergencia.

## Cómo funciona
Usa la rampa de gamma de Windows (GDI), sin tocar el registro ni los drivers. La configuración de cada usuario se guarda en `%APPDATA%\vislumbra`, fuera del repositorio.

## Licencia
[GNU GPL v3](LICENSE). Dependencias: `pystray` (LGPLv3), `keyboard` (MIT) y `Pillow` (MIT-CMU), todas compatibles con GPL v3.
