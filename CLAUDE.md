# Vislumbra (carpeta de trabajo: App para pantalla)

App **gratuita** y sencilla para Windows: sustituto moderno de la pestaña de corrección de color de RivaTuner v2.24c. Brillo, contraste y gamma (por canal R/G/B) y temperatura de color desde un icono en la bandeja, con control fino y modo preciso, perfiles y atajos globales. Los perfiles los crea cada usuario; no se atan a ningún juego ni persona.

## Antes de hacer nada
1. Lee `PLAN.md` (diseño, fases, decisiones) y `REGISTRO.md` (qué se ha hecho y dónde se quedó).
2. **Pregunta al usuario qué tipo de sesión es y espera su respuesta**: `creación` o `test`. No empieces sin saberlo.
3. Las reglas comunes (idioma, firmas, privacidad, plan para cambios grandes) están en `~/.claude/CLAUDE.md`; no se repiten aquí.

## Sesión de creación
- Implementa **una fase del plan cada vez**, empezando por la primera sin completar en `REGISTRO.md`.
- Commits pequeños, en español, sin firmas de IA.
- No pruebes en profundidad: haz solo una comprobación mínima de que arranca y deja las pruebas para la sesión de test.
- Al cerrar, añade una entrada a `REGISTRO.md` (qué se hizo, qué falta, qué debe probarse).

## Sesión de test
- No añadas funciones. Puedes escribir tests y corregir fallos pequeños y claros; lo demás se anota en `REGISTRO.md` como incidencia para la sesión de creación.
- Distingue en el informe lo verificado por ejecución, lo verificado por lectura y lo que solo puede juzgar el usuario mirando su pantalla (entrega una lista de comprobación visual).
- Tras cualquier prueba que toque la gamma, **restaura la rampa original** (`python -m vislumbra --reset` cuando exista).

## Reglas propias del proyecto
- Seguridad primero: nada de registro de Windows, drivers (NVAPI/ADL) ni cambios del sistema sin preguntar. Primero lo sencillo; lo avanzado solo si hace falta y con OK explícito.
- Los valores extremos nunca deben dejar la pantalla ilegible: rangos limitados, restauración al salir y un atajo de emergencia.
- Licencia: **GPL v3**. Toda dependencia nueva debe ser compatible con ella; comprueba su licencia antes de añadirla.
- GitHub (`dedalexcr7/vislumbra`): repositorio **privado** hasta que el usuario decida hacerlo público. No hagas `push` ni cambies la visibilidad sin su OK.
- Nada de rutas personales, correos ni claves en código, docs o commits. La configuración del usuario vive en `%APPDATA%`, fuera del repositorio.
