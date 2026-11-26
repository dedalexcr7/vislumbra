# Registro de trabajo

Una entrada por sesión, la más reciente arriba. Formato: fecha · tipo de sesión (planificación / creación / test) · qué se hizo · qué falta · qué debe probarse.

## 2026-11-26 · creación (fase 0)
- **Hecho:** `git init` (rama `main`), `.gitignore`, `requirements.txt` (`pystray`, `keyboard`, `Pillow`), `LICENSE` (texto oficial de GPL v3, descargado de gnu.org), `README.md` básico y primer commit. Autoría local con el correo `noreply` de GitHub, para no dejar correos personales en el historial.
- **Licencias comprobadas** (en un entorno temporal, con `pip show` y los metadatos): `pystray` LGPLv3, `keyboard` MIT, `six` MIT, `Pillow` MIT-CMU. Todas compatibles con GPL v3.
- **Pendiente de la fase 0:**
  1. Renombrar la carpeta `App para pantalla` a `vislumbra` (no se pudo con la sesión abierta; Windows bloquea la carpeta). Hacerlo con la sesión cerrada.
  2. Crear el `.venv` **después** del renombrado (guarda rutas absolutas) e instalar `requirements.txt`.
  3. Crear el repositorio privado `dedalexcr7/vislumbra` y hacer el primer `push`: **requiere OK del usuario**.
- **Decisiones:** el aviso de copyright («Copyright 2026 …») sigue pendiente. El usuario decide qué fases se hacen en cada sesión (puede haber más de una).
- **A probar:** que `pip install -r requirements.txt` funcione en el `.venv` definitivo.

## 2026-11-26 · planificación
- Se definió el objetivo, la tecnología (Python), el uso (bandeja + panel + perfiles + atajos) y el enfoque de riesgo (empezar sencillo).
- Referencia: la pestaña de color de RivaTuner v2.24c, usada en un vídeo sobre Tarkov para ver mejor en oscuro.
- Se escribieron `CLAUDE.md`, `PLAN.md` y este registro. No se ha creado código ni entorno ni repositorio.
- Segunda tanda de planificación: se leyeron las capturas de la ventana de RivaTuner (rangos, método GDI gamma ramp, esquemas «gamma 1» = 0/5/1,7 y «gamma 2» = 0/5/2,5). Se añadieron a `PLAN.md` los perfiles iniciales, el requisito de control fino y la propuesta de nombre (Nictalope, pendiente de confirmar).
- Tercera tanda: nombre confirmado **Vislumbra** (verificado libre en web, GitHub y PyPI; ver `PLAN.md`) y renombrados los documentos. Decisiones nuevas: los perfiles los crea cada usuario (solo viene «Normal»), la app es gratuita, se añade un **modo preciso**, y la calibración de la escala se hará probando porque RivaTuner ya no está instalado.
- Cuarta tanda: licencia **GPL v3** elegida; cuenta de GitHub `dedalexcr7` confirmada; el repositorio se mantiene **privado** hasta que el autor decida lo contrario.
- **Siguiente paso:** sesión de creación, fase 0 y fase 1 (ver la entrada de arriba para el estado).
- **Sin verificar:** si Tarkov usa BattlEye (se cree que sí); el rendimiento real de la rampa gamma en el equipo del usuario.
