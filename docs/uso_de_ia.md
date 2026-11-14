# Registro de uso de IA

Condición no negociable 5: se declara para qué se usó IA y cómo se verificó el resultado. Este
registro alimenta la declaración de uso de IA del artículo.

| Fecha | Herramienta | Para qué | Cómo se verificó |
|---|---|---|---|
| 2026-10-31 | Claude Code (`claude-opus-5-5`) | Extraer los requisitos de la especificación del proyecto y compararlos con la propuesta inicial; redactar `PLAN_PROYECTO.md`, `README.md` y `TODO.md`. | El autor revisó y aprobó el plan y las decisiones D3, D5, D9 y D11. |
| 2026-10-31 | Claude Code (búsqueda web) | Buscar fuentes del vocabulario LESCO y estimar el presupuesto de la API. | Cada fuente se abrió y se registró con su URL y fecha en `docs/referencias.md`. El presupuesto es una estimación previa que se recalibrará con trazas. |
| 2026-11-01 | Claude Code (`claude-opus-5-5`, búsqueda web) | Redactar el borrador de `docs/propuesta_H1.md` y verificar los metadatos de las referencias candidatas. | Metadatos comprobados en las páginas de los editores o de arXiv. La lectura de cada referencia la registra el autor. |
| 2026-11-13 | Claude Code (modelo concreto: no consta en la evidencia del proyecto) | Etapas de integridad 1 y 2: vinculación del servidor MCP y del agente al caso (D18), validación documental antes de puntuar (D19), pruebas automatizadas, instrumento de evidencia y documentación técnica. | Ver la sección "Etapas de integridad 1 y 2" más abajo. |

## Usos previstos (se registrarán al ocurrir)

- Programación del servidor MCP, el agente y los scripts (con pruebas automáticas).
- Segundo anotador del conjunto de evaluación (`claude-opus-5-5`, autorizado por el profesor).
- Apoyo de redacción del artículo (el autor revisa cada sección y cada cifra contra las trazas).

**Nunca:** generar entradas del vocabulario LESCO ni referencias bibliográficas.

## Etapas de integridad 1 y 2 (2026-11-13)

**Fecha:** 2026-11-13 es la fecha de los registros de evidencia (`evidencia/INDICE.md`) y del commit
`e254f68`. La fecha de inicio de la sesión de trabajo no consta en el repositorio.

**Herramienta:** Claude Code. No se indica el modelo concreto porque no consta en la evidencia del
proyecto.

### Qué propuso o produjo Claude Code

- Auditoría estática del servidor, del agente y de la evaluación. De ahí salió el hallazgo de
  contaminación entre casos en `guardar_resultado`.
- Propuestas de diff y redacción del código y de las pruebas de:
  - la vinculación del servidor MCP (`--caso`) y del agente al caso (D18);
  - la validación documental antes de puntuar y el conjunto esperado, con `ErrorVinculacion` y el
    código de salida 3 de `reproducir.py` (D19);
  - el instrumento de evidencia `evidencia/registrar_pruebas.py` y sus pruebas.
- Ejecución de las pruebas y verificaciones autorizadas, e informe de sus resultados.
- Redacción de la documentación técnica: `evidencia/etapa1_servidor_mcp.md`,
  `evidencia/etapa2_agente.md`, y las actualizaciones de `PLAN_PROYECTO.md`, `README.md`,
  `docs/metricas.md` y este registro.

### Qué decidió y autorizó el autor (según consta en la sesión)

- **Procedimiento de revisión y autorización seguido en la sesión de Claude Code:**
  - Claude Code presentaba el diff o el comando propuesto y esperaba la respuesta del autor.
  - El autor lo aprobaba, pedía correcciones o lo rechazaba. Hubo propuestas rechazadas y rehechas.
  - Después de aplicar o ejecutar, Claude Code informaba de la verificación y se detenía.
- **Alcance de ese registro:** el procedimiento y las autorizaciones constan solo en la transcripción
  de la sesión. Esa transcripción no forma parte del repositorio ni es un registro independiente. Este
  documento no afirma más de lo que consta en ella. El commit `e254f68` se hizo fuera de la sesión y
  no pasó por este procedimiento.
- **Decisiones y correcciones de diseño** sobre las propuestas. Por ejemplo:
  - el mensaje de rechazo de `guardar_resultado`;
  - `fullmatch` y la vinculación estricta;
  - el rechazo de trazas ausentes y el conjunto esperado;
  - la protección ante JSON mal formado;
  - los mensajes sin fragmentos de contenido;
  - el filtro de credenciales en el registro E2-5;
  - la auditoría de privacidad sin mostrar contenido.
- **Commit:** el autor hizo y publicó desde Visual Studio Code el commit `e254f68`
  (2026-11-13 20:58:58 -06:00, sin firmar), fuera de la sesión de Claude Code. Después, Claude Code lo
  contrastó, en solo lectura, con los hashes del registro E2-5: 30 de 31 archivos de código coinciden
  y la diferencia es `.gitignore`.
- **Verificación propia:** no consta que el autor haya ejecutado por su cuenta pruebas, verificaciones
  de SHA-256 ni reproducciones.

### Comprobaciones automatizadas

Las ejecutó Claude Code, la misma herramienta que propuso los cambios, con autorización del autor.
**Ninguna es una certificación independiente.**

**a) Ejecución de pruebas.** Pruebas `unittest` con el modelo **simulado** y datos sintéticos.
Las ejecuciones registradas, con su salida original, están en `evidencia/INDICE.md`. El último
registro, E2-5, dio **97/97**. Hubo además ejecuciones de control de desarrollo que no se registraron
como evidencia.

**b) Verificaciones técnicas de integridad.**
- SHA-256 de cada registro comprobados con el subcomando `verificar` del instrumento y recalculados
  con una herramienta distinta (`Get-FileHash`).
- Una prueba de manipulación sobre una copia (V4, `evidencia/etapa1_servidor_mcp.md` §11).
- Huellas SHA-256 del proyecto y de `evidencia/` antes y después de la edición, **solo** en las
  ediciones que tienen ese registro:
  - E2-1 a E2-5, según `evidencia/etapa2_agente.md` §11;
  - las ediciones documentales de E2-6, cuya verificación consta en la sesión.

  No se afirma para el desarrollo anterior (commits hasta `e495b06`).
- El contraste en solo lectura del commit `e254f68` con los hashes de E2-5.

**c) Comprobaciones estáticas y del árbol sintáctico documentadas.** Solo las que figuran en
`evidencia/etapa2_agente.md` §11:
- `ast.parse` en E2-1, E2-2, E2-3 y E2-5;
- comparación del árbol sintáctico con la copia previa solo en E2-3 y en las dos ediciones de E2-5.

`evidencia/etapa1_servidor_mcp.md` §11 no documenta comparaciones del árbol sintáctico. Las ediciones
documentales de E2-6 (Markdown) se verificaron con el diff real, la comparación textual de las partes
que no debían cambiar y huellas SHA-256, sin análisis del árbol sintáctico. **No todos los cambios
tuvieron comparación del árbol sintáctico.**

### Alcance

- **Pruebas automatizadas, no experimento.** Las 97/97 pruebas describen el comportamiento del código.
  **No** son resultados del experimento A/B con el modelo real, que sigue pendiente. En estas etapas no
  se ejecutó el agente con el modelo real ni se usó la clave de la API del proyecto.
- **Consistencia, trazabilidad y autenticidad son cosas distintas:**
  - los SHA-256 dan consistencia documental;
  - git da trazabilidad de versiones;
  - ninguno de los dos da autenticidad certificada por terceros.
- **Falta una verificación independiente**, por ejemplo la reproducción en un clon limpio
  (`evidencia/etapa2_agente.md`, sección 10 y adenda).

### Pendiente de registrar

Este registro no tiene entradas entre el 2026-11-01 y el 2026-11-13. En ese periodo hay commits de
programación, anotación y piloto (del `6554a7d` al `e495b06`, del 2026-10-31 al 2026-11-03). El autor
debe completar qué uso de IA hubo en ellos, incluido el segundo anotador previsto arriba. Este documento
no lo deduce.

**Discrepancia cronológica pendiente de aclaración.** La fila fechada el 2026-11-01 ya figura en la
única versión de este archivo registrada en git: el commit `639331d`, fechado el
2026-10-31 10:02:30 -06:00. No se ha determinado a qué se debe. La fila se conserva sin cambios hasta
que el autor lo aclare.
