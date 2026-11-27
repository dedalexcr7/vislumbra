# Diseño del panel: la maqueta como referencia

**Objetivo del autor:** que el panel real quede **igual que la maqueta aprobada**. Este documento guarda el análisis de la captura (`docs/maqueta-panel.png`) y cómo comprobar que quedan iguales. El retoque visual está hecho (ver §4); queda el juicio del autor mirando y la sesión de test.

Maqueta interactiva (fuente de verdad de colores y medidas): https://claude.ai/artifact/FuZBRyF2idJek2YLyuArRr. Las secciones 1 y 2 salen de la captura (aproximadas); los valores exactos, leídos del CSS de la maqueta, están en §4.

## 1. Lo que muestra la maqueta (columna izquierda: el panel)
- **Ventana:** unos 537 px de ancho, esquinas redondeadas (~12 px), borde fino y fondo oscuro algo cálido. Cabecera propia: glifo del logo, «Vislumbra» en negrita, ✕ a la derecha y una línea separadora.
- **Perfil activo:** etiqueta apagada, botón «‹» cuadrado redondeado, nombre centrado **sin caja**, botón «›», y a la derecha una **píldora «● Activo»** con punto verde oliva.
- **Pestañas de monitor:** tres tarjetas redondeadas del mismo ancho. Título en negrita («Monitor 2 · principal») y debajo, apagado, «Oscuro (activo)» o «Código (fijo)». La seleccionada tiene borde y fondo más claros.
- **Fila del monitor:** «Monitor 1» y dos botones tipo píldora. El elegido va **relleno en beige** con texto oscuro («Sigue al perfil activo»); el otro, solo con borde («Perfil fijo»).
- **Editor:** recuadro algo más claro, con borde y esquinas redondeadas. «Editando «Oscuro»» y botones con borde (Guardar apagado cuando no hay cambios, Guardar como…, Renombrar; **Borrar pasa a una segunda línea**).
- **Vincular canales:** casilla con marca beige y, a la derecha, «R, G y B a la vez» apagado.
- **Deslizadores:** etiqueta a la izquierda; pista fina con **tramo relleno desde el neutro** hasta el pulgar (redondo, gris claro) y marca vertical en el neutro; **mínimo y máximo escritos debajo** de la pista (−100,0 / 100,0; 0,50 / 4,00; 3300 K / 10000 K); botones «−» y «+» cuadrados y un campo numérico con borde y el valor a la derecha. La temperatura tiene la pista con **degradado naranja → azul**.
- **Pie:** recuadro de la curva (curva azul, diagonal discontinua) con el pie «Curva (discontinua = normal)»; a la derecha botones anchos «A/B: viendo el ajuste» y «Restablecer», casilla «Modo preciso» y «Margen de Windows … 19 % de 50 %» con barra beige. Debajo, otra línea separadora y el resumen ««Oscuro» en los monitores 1 y 2 · «Código» en el monitor 3.»
- **Menú de la bandeja (derecha, fuera del panel):** «Mostrar panel», «✓ Activo», una sección **plana** «Perfil activo» con la lista (punto en el actual), «Siguiente perfil», «Comparar (A/B)» y «Salir (restaura la pantalla)».

## 2. Diferencias con la app actual (por lectura del código; **no se ha comparado en pantalla**)
| Maqueta | App actual (`panel.py`, `tray.py`) |
|---|---|
| Cabecera propia con logo y ✕ | Barra de título de Windows (ventana de herramienta) |
| Esquinas redondeadas y bordes en tarjetas, botones, píldoras y recuadros | Tk dibuja todo rectangular y plano |
| Píldora «● Activo» con punto verde | Botón plano «● Activo» que cambia de color |
| Fila de monitor con dos botones tipo píldora | Dos `Radiobutton` normales |
| Mínimo y máximo siempre bajo cada deslizador | Solo se ven en modo preciso |
| Tramo relleno desde el neutro y degradado en la temperatura | Tramo relleno sí; la temperatura sin degradado |
| «Borrar» en una segunda línea | Los cinco botones en una sola fila (y hay uno extra, «Descartar») |
| Botón «A/B: viendo el ajuste» (el texto cambia) | Botón «A/B» fijo |
| Pie «Curva (discontinua = normal)»; curva azul | Sin pie; curva beige (azul/rojo/verde solo si los canales difieren) |
| Menú con la lista de perfiles plana | Submenú «Perfil activo»; entrada «Mostrar / ocultar panel» |

## 3. Cómo comprobar que quedan iguales
Hay que **verlo**, no basta con leer el código:
1. **Captura de la ventana real** con un script nuevo (`herramientas/captura_panel.py`) que abra el panel con perfiles de ejemplo, **sin tocar la gamma**, y guarde un PNG con `PIL.ImageGrab` del rectángulo de la ventana (Pillow ya es dependencia).
2. **Comparar lado a lado** ese PNG con `docs/maqueta-panel.png`, a la misma anchura y con el mismo DPI (la maqueta mide ~537 px; la app, `Panel.ANCHO`). Se revisa por zonas, con la lista de la sección 1 como lista de comprobación, y se corrige hasta que coincidan.
3. **Sacar colores y medidas exactos del CSS de la maqueta** (leer el artefacto con la herramienta de artefactos) y pasarlos a las constantes de tema de `panel.py`, en vez de estimarlos de la imagen.
4. **Lo que Tk no hace** (esquinas redondeadas, bordes suaves, degradados) se resuelve dibujando esos elementos en `Canvas` (un ayudante de rectángulo redondeado y widgets propios para botón, píldora, tarjeta y pista). Los **gestos y la lógica no cambian**, así que las pruebas actuales de `estado.py` y `aplicador.py` siguen valiendo.
5. **El autor lo juzga mirando**: una captura no sustituye a su ojo (fuentes, antialiasing, DPI alto, tema claro de Windows). Se le entrega la captura y la lista de la sección 1.

**Riesgo:** los widgets propios en `Canvas` cuestan más que los estándar y hay que repetir las pruebas de humo de `test_panel.py`. Se hace en una sesión de creación propia, con plan previo si toca 3 o más archivos.

## 4. Retoque hecho (sesión de creación) y valores exactos
- **Medidas.** La maqueta mide 490 px de ancho (la captura está ampliada ×1,096). `Panel.ANCHO = 490` y todas las medidas pasan por `widgets.px()`, que aplica el DPI de Tk; las fuentes son de tamaño en píxeles (`widgets.fuente()`).
- **Colores y radios** (constantes de `vislumbra/widgets.py`): ventana `#1d1d1a` con borde `#34332d`; cabecera `#191916` de 40 px; línea `#2c2b26`; botón `#2a2925` con borde `#45443c` (alto 32, radio 7); campo `#141412`; acento `#c9b98f`; texto `#ece8dc` y `#a7a392`; pista `#3a3933` de 6 px; degradado de la temperatura `#d98a45 → #d8d4c8 → #6f9be0`; punto de «Activo» `#9cc47a`; aviso `#e8b062`; curva `#6a9be0`; tarjeta del editor radio 10; pestañas radio 8 con raya inferior de acento.
- **Corrección a §1:** la pista de la maqueta **no** lleva tramo relleno desde el neutro (se comprobó en los píxeles de la captura); solo la marca vertical del neutro. La app ya no lo dibuja.
- **Elementos propios en `Canvas`** (`widgets.py`): `Boton` (también la píldora «● Activo» y los chips), `Casilla`, `Tarjeta`, `TextoMixto` y el logo. El borde de 1 px es un polígono bajo el relleno (el contorno de Tk sale discontinuo en las curvas).
- **Cabecera propia:** `overrideredirect` (sin barra de Windows ni botón en la barra de tareas); se arrastra desde la cabecera; la ✕ llama a `ocultar_panel`. Esquinas redondeadas y borde de la ventana con `sistema.redondear_ventana` (DWM de Windows 11; en Windows 10 queda cuadrada).
- **Se mantienen aunque no estén en la maqueta:** «Descartar» (junto a «Borrar») y «Deshacer» (sin la cuenta atrás de la maqueta). El nombre del perfil activo abre un menú con la lista al pulsarlo (sustituye al desplegable).
- **Bandeja:** `pystray` usa el menú nativo de Windows. Se igualan la estructura y los textos (lista plana bajo la cabecera gris «Perfil activo», punto en el actual, «Mostrar panel» en negrita); no se pueden igualar los colores, las esquinas ni el espaciado. «Mostrar panel» sigue siendo «mostrar u ocultar» (no se toca `app.py`).
- **Diferencias que quedan:** el texto del resumen sale de `estado.resumen()` («en el 3» frente a «en el monitor 3.» de la maqueta); el menos de los límites es «-» y no «−»; no hay cuenta atrás en «Deshacer».
- **Comprobar:** `python herramientas/captura_panel.py salida.png` (sin tocar la gamma; la ventana aparece unos segundos) y comparar con `docs/maqueta-panel.png` a la misma anchura.
