# Registro de uso de IA

Condición no negociable 5: se declara para qué se usó IA y cómo se verificó el resultado. Este
registro alimenta la declaración de uso de IA del artículo.

| Fecha | Herramienta | Para qué | Cómo se verificó |
|---|---|---|---|
| 2026-10-31 | Claude Code (`claude-opus-5-5`) | Extraer los requisitos de la especificación del proyecto y compararlos con la propuesta inicial; redactar `PLAN_PROYECTO.md`, `README.md` y `TODO.md`. | El autor revisó y aprobó el plan y las decisiones D3, D5, D9 y D11. |
| 2026-10-31 | Claude Code (búsqueda web) | Buscar fuentes del vocabulario LESCO y estimar el presupuesto de la API. | Cada fuente se abrió y se registró con su URL y fecha en `docs/referencias.md`. El presupuesto es una estimación previa que se recalibrará con trazas. |
| 2026-11-01 | Claude Code (`claude-opus-5-5`, búsqueda web) | Redactar el borrador de `docs/propuesta_H1.md` y verificar los metadatos de las referencias candidatas. | Metadatos comprobados en las páginas de los editores o de arXiv. La lectura de cada referencia la registra el autor. |
| 2026-11-03 | `eval/anotador_llm.py` con la API de Claude (modelo declarado en las respuestas: `claude-opus-5-5`) | Anotador 2 (D10): etiquetar las 240 palabras de los 48 casos con la guía v1, el índice del CENAREC y el prompt `eval/prompts/anotador2_v1.md`. | Validación técnica agregada el 2026-11-13. La calidad lingüística queda pendiente del kappa y la adjudicación. Ver la sección "Anotador 2". |
| 2026-11-13 | Claude Code (modelo concreto: no consta en la evidencia del proyecto) | Presentar los 48 textos del conjunto de evaluación para su revisión, en seis grupos de ocho, y validar técnicamente el anotador 2 con un script que solo muestra cifras. | La aceptación de los 48 textos sin cambios se documentó después en `TODO.md`. Las continuaciones entre grupos constan solo en la sesión y no son autorizaciones independientes verificadas. La validación del anotador 2 se describe en la sección "Anotador 2". |
| 2026-11-13 | Claude Code (modelo concreto: no consta en la evidencia del proyecto) | Etapas de integridad 1 y 2: vinculación del servidor MCP y del agente al caso (D18), validación documental antes de puntuar (D19), pruebas automatizadas, instrumento de evidencia y documentación técnica. | Ver la sección "Etapas de integridad 1 y 2" más abajo. |
| 2026-11-14 | Claude Code (modelo concreto: no consta en la evidencia del proyecto) | Diseñar, escribir y revisar el validador revisado del anotador 2 (`eval/validar_anotador2.py`) y sus 28 pruebas sintéticas (`tests/test_validar_anotador2.py`). Ejecutar esas pruebas y la suite completa, y registrar la suite como evidencia. | El autor aprobó, corrigió o rechazó cada propuesta, escritura y ejecución durante la sesión. Eso consta solo en su transcripción y no es un registro independiente. Resultados: 28/28 y 125/125, con datos sintéticos y modelo simulado. Registro `20261114-000942_suite-completa-f5-validador`: VERIFICADA y CONFORME, en `PENDIENTE_REVISION_HUMANA`. Ver la sección "Anotador 2". |
| 2026-11-14 | Claude Code (modelo concreto: no consta en la evidencia del proyecto) | Corrección D19: detectar que `eval/puntuar.py` puntuaba ejecuciones con fallo técnico, proponer y escribir la corrección y 8 pruebas sintéticas, ejecutar la suite completa, registrarla como evidencia y actualizar `TODO.md`. | Autorización individual del autor para cada paso de corrección, pruebas, evidencia, commit y documentación, según consta solo en la transcripción de la sesión. 133/133 con modelo simulado y datos sintéticos. Registro `20261114-080936_suite-completa-d19`: VERIFICADA y CONFORME, en `PENDIENTE_REVISION_HUMANA`. Commit `230d580`, publicado en `origin/main`. Ver la sección "Corrección D19". |

## Usos previstos (se registrarán al ocurrir)

- Programación del servidor MCP, el agente y los scripts (con pruebas automáticas).
- Segundo anotador del conjunto de evaluación (`claude-opus-5-5`, autorizado por el profesor).
  **Ya ejecutado** (2026-11-03). Su trazabilidad está en la sección "Anotador 2".
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
registro de estas etapas, E2-5, dio **97/97**. Hubo además ejecuciones de control de desarrollo que no se registraron
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

Salvo la del anotador 2 (2026-11-03), este registro no tiene entradas entre el 2026-11-01 y el 2026-11-13. En ese periodo hay commits de
programación, anotación y piloto (del `6554a7d` al `e495b06`, del 2026-10-31 al 2026-11-03). El autor
debe completar qué uso de IA hubo en ellos. Este documento no lo deduce. El segundo anotador
(2026-11-03) ya se registra en la sección "Anotador 2".

**Discrepancia cronológica pendiente de aclaración.** La fila fechada el 2026-11-01 ya figura en la
única versión de este archivo registrada en git: el commit `639331d`, fechado el
2026-10-31 10:02:30 -06:00. No se ha determinado a qué se debe. La fila se conserva sin cambios hasta
que el autor lo aclare.

## Anotador 2 (ejecución del 2026-11-03, validación del 2026-11-13)

- **Qué se ejecutó:** `eval/anotador_llm.py` (D10, autorizado por el profesor). El prompt de sistema
  contiene la guía v1, el índice del CENAREC y `eval/prompts/anotador2_v1.md`. El mensaje de cada caso
  contiene solo su plantilla. Según el código, no recibe las etiquetas del anotador 1 ni salidas del
  agente. El registro de respuestas declara las fechas del 2026-11-03 de 14:29:10 a 14:32:49. Quién
  lanzó la ejecución no consta en el repositorio.
- **Modelo:** `claude-opus-5-5`, según el campo `model` de las 48 respuestas de la API que guardó el
  script. Es la declaración de la API registrada por el propio script, no una certificación
  independiente.
- **Validación técnica agregada (2026-11-13):** la hizo Claude Code con autorización del autor,
  mediante un script temporal no versionado
  (SHA-256 `D591098139B69E7CF150025CDBC8663E3D29F98E042EFDEAADC2C3DB4ECB1B13`) que solo lee y solo
  muestra cifras. Resultado:
  - 48 de 48 casos válidos en el primer intento;
  - 240 de 240 posiciones alineadas con la plantilla;
  - 0 etiquetas vacías o inválidas y 0 diferencias entre el TSV y el registro;
  - el SHA-256 del prompt es igual al vigente en los 48 registros.

  Durante la validación no se mostró ninguna etiqueta, palabra ni respuesta.
- **Reproducibilidad de la validación:** el SHA-256 del script temporal histórico queda registrado.
  Ese script no se versiona y la validación real del 2026-11-13 sigue atribuida a él.
- **Validador revisado (2026-11-14):** `eval/validar_anotador2.py` está en el commit `d82df69`,
  publicado en `origin/main`. Es una versión revisada del script temporal y **no** lo sustituye.
  - **Autoría:** lo escribió Claude Code. El autor revisó y aprobó en la sesión el diseño, cada
    corrección, cada escritura y cada ejecución.
  - **Selección:** conserva la regla básica de `eval/anotador_llm.py` (la última respuesta sin
    problemas de cada caso) e incorpora verificaciones adicionales: vigencia del prompt, ausencia de
    duplicados vigentes y formato estricto del TSV. **No** es equivalente en todo a `eval/anotador_llm.py`.
  - **Salida:** solo lee y solo imprime cifras y metadatos saneados. Códigos de salida: 0 = válido,
    1 = incompleto o inválido, 2 = error de lectura.
  - **Pruebas:** 28/28 sintéticas (`tests/test_validar_anotador2.py`) y 125/125 en la suite completa,
    registrada como `20261114-000942_suite-completa-f5-validador`. Integridad VERIFICADA y CONFORME;
    el registro sigue en `PENDIENTE_REVISION_HUMANA`.
  - **Ejecución sobre los archivos reales (2026-11-14):** resultado VÁLIDO (código 0), mostrando solo
    cifras agregadas: 48/48 casos válidos, 240/240 posiciones alineadas y 0 discrepancias de
    consistencia; las cifras coinciden con las del 2026-11-13. La validación se ejecutó mediante
    Claude Code el 14 de noviembre de 2026; consta en el registro de la sesión. **No** tiene un
    expediente formal independiente.
  - Aunque está versionado, la validación **no** se podrá reproducir solo con el repositorio público,
    porque los archivos del anotador 2 están ignorados por git y no se publican.
- **Alcance:**
  - es **completitud técnica**: la calidad lingüística todavía no ha sido evaluada mediante
    adjudicación, y el acuerdo entre anotadores está pendiente de medirse mediante Cohen's kappa;
  - el anotador 2 se ejecutó **antes** que el anotador 1, lo que es una desviación del orden previsto.
    Esa secuencia, por sí sola, no demuestra la independencia.
    La independencia deberá justificarse mediante el protocolo y la trazabilidad del proceso, no
    únicamente mediante el valor de kappa.
- **Archivos:** `eval/anotaciones/anotador2.tsv` y `anotador2_respuestas.jsonl` están ignorados por
  git y no se publican.

## Corrección D19: fallos técnicos antes de puntuar (2026-11-14)

**Herramienta:** Claude Code. Modelo concreto: no consta en la evidencia del proyecto. En la sesión,
Claude Code se identificó como `claude-opus-5-5`; esa identificación no se ha verificado de forma
independiente.

- **Origen:** Claude Code lanzó el 2026-11-14 una solicitud real de 1 caso (A/c001/rep1) con el
  modelo real, como comprobación previa al experimento. La API la rechazó por autenticación
  (HTTP 401) y no se obtuvo ninguna respuesta del modelo. No fue una ejecución experimental válida.
  No consta una autorización previa específica para esa llamada, y no se ha verificado en la
  facturación si tuvo algún costo. Al revisar ese caso, Claude Code detectó que `eval/puntuar.py`
  habría puntuado esa ejecución como un fallo del agente.
- **Qué produjo Claude Code:** el análisis en solo lectura del código; el diff y el código de
  `problemas_de_cierre()` y `PREFIJOS_FALLO_TECNICO`; el cambio del helper de pruebas y 8 pruebas
  sintéticas; la ejecución de la suite y su registro como evidencia; y las actualizaciones de
  `TODO.md` y de este registro.
- **Qué decidió y autorizó el autor (según consta en la sesión):**
  - después del 401, cada paso de corrección, pruebas, evidencia, commit y documentación (D19-A a
    D19-H y siguientes) se autorizó por separado. En cada escritura hubo copia previa con SHA-256,
    diff, verificación y una parada antes del paso siguiente;
  - decisiones del autor: no modificar `.gitignore`, conservar la traza del 401 sin moverla ni
    borrarla, y el mensaje del commit;
  - igual que en las etapas 1 y 2, esas autorizaciones constan solo en la transcripción de la sesión,
    que no es un registro independiente.
- **Comprobaciones automatizadas** (las ejecutó Claude Code; **ninguna es una certificación
  independiente**):
  - `ast.parse` y comparación del árbol sintáctico con la copia previa, en `eval/puntuar.py` y
    `tests/test_puntuar.py`;
  - suite completa **133/133** (con el modelo simulado y datos sintéticos), primero fuera del
    registrador y después en el registro `20261114-080936_suite-completa-d19`
    (`verificacion_posterior`, OK, CONFORME);
  - `verificar` dio integridad criptográfica VERIFICADA en el original y en la candidata, y los dos
    sellos coinciden con `evidencia/INDICE.md`. La publicación sigue en `PENDIENTE_REVISION_HUMANA`;
  - commit `230d580`, publicado en `origin/main` el 2026-11-14 junto con `d82df69` y `592dd74`.
    El push lo autorizó el autor tras una auditoría de privacidad de solo lectura de los 8 archivos
    publicados. La evidencia de `evidencia/privado/` sigue sin publicar.
- **Privacidad:**
  - la traza del 401 solo se inspeccionó con cuatro resultados agregados, sin mostrar el motivo, el
    identificador de solicitud ni credenciales;
  - un recuento automatizado no encontró en el expediente patrones de clave, correos ni rutas
    personales.
- **Evidencia técnica, no resultado científico:**
  - 133/133 describe el comportamiento del código con el modelo simulado y datos sintéticos;
  - **no** es un resultado del experimento A/B ni mide la calidad lingüística;
  - A×3 y B×3 siguen pendientes y, además, bloqueados hasta disponer de una clave válida.
