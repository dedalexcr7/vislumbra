# Resultados del test de la fase 1

Sesión de test del 2026-11-26. Sin modelos de monitor ni de GPU: solo «monitor N». **Estado: parcial.** Lo medido por ejecución está aquí; lo que depende de la pantalla del usuario (§2.2, §3, §4 y §5 del plan) sigue pendiente y está marcado.

## 1. Tests automáticos
- `pytest -q`: **211 pruebas en verde, 6 saltadas** (las 6 llevan el marcador `pantalla`).
- `pytest -q -s -m pantalla --con-pantalla`: **6 en verde** (identidad, gamma 1,2, `restaurar()` real, excepción dentro del `with` real, reversión parcial real y sondeo). Tras cada ejecución, la lectura de los 3 monitores dio desviación 0.
- Los dos casos de I-1 (fallo de lectura y `KeyboardInterrupt` a mitad de `aplicar`) **fallaron como se esperaba** antes del arreglo (`xfail` estricto, comprobado con `--runxfail`) y pasan tras él.

## 2. Sondeo de límites (parte automática, los 3 monitores)
Cada ajuste se aplicó unos milisegundos, se midió la lectura posterior y se restauró. **En los 3 monitores el resultado fue idéntico.**

| Ajuste | Validador | Windows (`SetDeviceGammaRamp`) | Diferencia de lectura máx. |
|---|---|---|---|
| gamma 1,5 · 2,0 · 2,5 · 3,0 · 3,5 · 4,0 | válida | aceptada | 0 |
| brillo +25 · +50 · +75 · −25 · −50 · −60 | válida | aceptada | 0 |
| contraste +20 · +40 · +82 · −20 · −40 | válida | aceptada | 0 |
| temperatura 5000 · 4000 · 3500 · 8000 · 10000 | válida | aceptada | 0 |
| temperatura 3000 · 2500 | válida | **rechazada** | — |
| referencias 0/5/1,7 · 0/5/2,5 | válida | aceptada | 0 |

**Umbral de temperatura** (monitor principal, aislada): aceptada hasta 3250 K, rechazada desde 3200 K.

**Hipótesis confirmada con 3 predicciones (monitor principal):** Windows rechaza una rampa cuya desviación máxima respecto a la identidad supera ~50 %.

| Ajuste | Desviación máx. calculada | Resultado |
|---|---|---|
| temp 3300 + contraste −20 | 54,6 % | rechazada |
| temp 4000 + contraste −40 | 47,7 % | aceptada |
| temp 3300 + gamma 4 | 48,3 % | aceptada |

Consecuencias:
- Gamma 4,0 (47 %) está justo bajo el límite: **no se puede subir `GAMMA_MAX`** sin cambiar de método. Gamma 4,5 / 5 / 6 darían 51 % / 53 % / 58 % (cálculo, no probado en pantalla).
- El validador no conoce este límite: acepta combinaciones que Windows rechaza después con el mensaje genérico «Prueba con valores más suaves». Es seguro, pero poco claro (incidencia I-12).
- La lectura posterior es **exacta** (diferencia 0) en todos los ajustes aceptados, en las 2 GPU: no hay cuantización ni recorte sistemático.

## 3. Cambios de constantes hechos
| Constante | Antes | Después | Motivo |
|---|---|---|---|
| `TEMPERATURA_MIN` | 2500 K | 3300 K | Windows rechaza por debajo de ~3250 K (medido) |
| `TOLERANCIA_LECTURA` | 512 | 64 | `max(64, 2 × 0)`; diferencia observada 0 |

## 4. Revisión de lectura (§6 del plan)
| ID | Estado |
|---|---|
| I-1 | **Arreglado** (monitor marcado como tocado antes de escribir; `except BaseException`) y con test |
| I-2 | **Arreglado**: Ctrl+C fuera de la espera da «Interrumpido. Pantalla restaurada.» y código 130; probado con doble (no con Ctrl+C real) |
| I-3 | **Arreglado**: `--duration inf` y `nan` dan error de uso (código 2) |
| I-4 | Parcialmente absorbida por el recorte de `TEMPERATURA_MIN`; el problema de fondo (validar por canal tras aplicar la temperatura) sigue. Incidencia |
| I-5 | Incidencia menor: sigue ignorándose en silencio `--simulate --monitor`, `--list --monitor/--channel` y `--reset --channel` (comprobado con dobles) |
| I-6 · I-7 | Descartadas en este equipo: la lectura posterior es exacta (diferencia 0) y no hay avisos falsos |
| I-8 · I-9 | **Sin verificar**: dependen de P3 y de una rampa original distinta de la identidad |
| I-10 | **Verificada por ejecución**: `git grep` de rutas y correos sin resultados; el único autor del historial es la dirección `noreply` |
| I-11 | **Verificada por ejecución con dobles**; ver hallazgos nuevos abajo |

**Hallazgos nuevos**
- I-11a: `--duration 0,5` mostraba «Se restaurará en 0 s.» → **arreglado** (ahora «0,5 s») con test.
- I-11b: `--monitor ""` se trata como «no indicado» y aplica al principal, sin error. Incidencia menor.
- I-12: el validador no modela el límite del ~50 % de Windows (ver §2). Incidencia de diseño.

## 5. Pendiente (necesita al usuario)
- §5 lista visual V1–V12 · §3 pruebas de proceso P1–P8 (incluida la decisión sobre `--persist`) · §2.2 sondeo visual · §4 calibración de la escala (brillo, contraste, gamma) y del validador.
- Patrón de grises: se genera con Pillow fuera del repositorio.
