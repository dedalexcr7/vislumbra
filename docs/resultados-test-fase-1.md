# Resultados del test de la fase 1

Sesión de test del 2026-11-26. Sin modelos de monitor ni de GPU: solo «monitor N». **Estado: parcial.** Hecha la calibración de la escala; siguen pendientes la lista visual V6–V12 y las pruebas de proceso P1–P8 (ver el final).

## 1. Tests automáticos
- `pytest -q`: **212 pruebas en verde, 6 saltadas** (las 6 llevan el marcador `pantalla`).
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
| `BRILLO_POR_UNIDAD` | 1/250 | 1/375 | U = 2 (con A/B); 1/250 × 2/3 |
| `CONTRASTE_ESCALA` | 50 | 75 | U = 2 (con A/B); 50 × 3/2 |
| `BRILLO_MIN/MAX` | ±125 | ±100 | máximo útil ≈ 45 en la escala nueva; se deja el doble, holgado pero sin exagerar |
| `CONTRASTE_MIN/MAX` | ±82 | ±40 | máximo útil ≈ 15–18 en la escala nueva; idem |
| `GAMMA_MAX` | 4,0 | sin cambio | lo fija el límite de Windows (47 % de 50 %) |

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

## 5. Calibración con el usuario (monitor 2)
**Método.** Se usó el primer patrón de grises (niveles oscuros 0, 2, 4… 40 y claros 215, 217… 255), no el fino de pasos de 1; **se dedujo por cálculo** a partir de los escalones que el usuario indicó, no porque lo dijera. Contar «cuántos escalones se distinguen» o «desde cuál se ve todo igual» resultó inútil (11, 10 y 9 sin ajuste, con gamma 1,7 y con 2,5: ruido, y en sentido contrario al esperado). Lo que funcionó fue la **comparación A/B** (5 s encendido, 5 s apagado, dos veces) y el juicio «se nota / no se nota».

| Ajuste | Resultado (juicio del usuario) | Cálculo |
|---|---|---|
| gamma 1,7 + contraste 5, 30 s | «se veía bien»; sin tintes ni bandas | blancos 14–21 todos en 255 |
| gamma 2,5 + contraste 5, 30 s | «se veía bien en lo oscuro» | — |
| brillo −40 | no distingue ningún escalón oscuro | todos los oscuros quedan en negro |
| brillo +40 | no ve ningún blanco; muy brillante | todos los claros quedan en 255 |
| brillo 5 | se nota | — |
| brillo 2 (A/B) | se nota: el blanco 19 empieza a desaparecer | 251 + 2 niveles acerca al recorte |
| contraste 2 y 4 (sin A/B) | no los vio | efecto de unos 3–7 niveles en los extremos |
| contraste 10 | oscuros desde el 7 u 8, blancos hasta el 13 | blancos en 255 desde el 13 (cuadra) |
| contraste 20 | oscuros desde el 15–16, blancos hasta el 5–6 | cuadra con el primer patrón |
| contraste 2 (A/B) | se nota: el negro 2 y el blanco 19 desaparecen | cuadra |
| gamma 1,1 (A/B) | se nota: el escalón 2 se aclara un poco | +1,4 niveles |

**Umbrales (U):** brillo ≈ 2, contraste ≈ 2 y gamma ≈ 0,1, todos con A/B. Son cotas superiores: no se probó el 1 ni gamma por debajo de 1,1.
**Observaciones.** El contraste positivo **aplasta los negros** y recorta los blancos: sirve para compensar el gamma, no para ver mejor lo oscuro por sí solo. Con la escala nueva, las referencias del autor (contraste 5 en RivaTuner) equivalen a **contraste 7,5**; falta confirmar que «se sienten bien». Con los rangos nuevos las esquinas ya no son ilegibles: el validador sigue rechazando, por ejemplo, brillo −100 con gamma 0,5 (centro bajo el 10 %).
**No calibrado:** contraste y brillo negativos (solo brillo −40), gamma entre 1,2 y 2,0 y por encima de 2,5, y los umbrales del validador.

## 6. Pendiente (necesita al usuario)
- Lista visual V6–V12 (canal, temperatura, monitores, Ctrl+C, V11 y juego sin bordes). V1 se comprobó por ejecución, y V2–V5 con la calibración.
- Pruebas de proceso P1–P8, incluida la decisión sobre `--persist`.
- Confirmar las referencias 0/7,5/1,7 y 0/7,5/2,5 en la escala nueva.
