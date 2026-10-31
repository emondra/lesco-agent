# Política de permisos

La política vive en el **host** (`agente/agente.py`, clase `Politica`), no en el servidor ni en el
modelo. Orden de evaluación: ocultar > denegar > confirmar > permitir > por defecto. Además, cada
herramienta tiene un máximo de llamadas por ejecución; al superarlo, la llamada se deniega.

| Herramienta | Experimento | Demo | Máx. llamadas | Justificación |
|---|---|---|---|---|
| `obtener_transcripcion` | permitir | permitir | 2 | Lectura de un solo caso; 2 deja margen a un reintento por error transitorio. |
| `buscar_sena` | permitir | permitir | 40 | Lectura sin efectos; 40 cubre frases de hasta ~25 palabras con lema y sinónimo. |
| `validar_secuencia` | permitir | permitir | 5 | Lectura; el criterio de parada de la Skill admite 2 rondas de corrección. |
| `guardar_resultado` | permitir | **confirmar** | **1** | Única escritura. En el experimento no hay una persona para aprobar 240+ ejecuciones, así que se permite pero se limita a una llamada por caso; en la demo una persona aprueba. El servidor además impide sobrescribir. |
| `*__borrar*`, `*__eliminar*`, `*__sobrescribir*`, `*__ejecutar*` | denegar | denegar | — | Acciones destructivas o de ejecución arbitraria: prohibidas aunque un servidor futuro las exponga. |
| `*__admin*`, `*__depurar*` | ocultar | ocultar | — | Herramientas de mantenimiento: el modelo ni siquiera las ve. |
| Cualquier otra | denegar (por defecto) | denegar (por defecto) | — | Mínimo privilegio. |

**Límites globales** (en cada configuración): `max_pasos` y `presupuesto_tokens` acotan la
autonomía; al alcanzarlos la ejecución termina y la traza registra el motivo.

**Defensa en profundidad:** aunque la política permita `guardar_resultado`, el servidor vuelve a
validar la secuencia, rechaza IDs inexistentes, confina la ruta y no sobrescribe.

La política es la misma en las configuraciones A y B: no es la variable del experimento.
