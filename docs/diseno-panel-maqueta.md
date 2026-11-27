# Diseño del panel: la maqueta como referencia

**Objetivo del autor:** que el panel real quede **igual que la maqueta aprobada**. Este documento guarda el análisis de la captura (`docs/maqueta-panel.png`) y cómo comprobar que quedan iguales. Es trabajo para una sesión de creación (retoque visual) y su sesión de test, **no está hecho**.

Maqueta interactiva (fuente de verdad de colores y medidas): https://claude.ai/artifact/FuZBRyF2idJek2YLyuArRr. Solo se analizó la captura; **los valores de abajo son aproximados**, leídos a ojo. Los exactos están en el CSS de la maqueta.

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
