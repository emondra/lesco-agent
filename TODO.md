# TODO — LESCO-Agent

Tareas pendientes, ordenadas según el calendario de 14 días de
[PLAN_PROYECTO.md](PLAN_PROYECTO.md#7-fases-de-desarrollo). Las referencias D1–D19 apuntan a las
decisiones de ese plan.

> **Estado al 2026-11-13:**
> - **Implementado y verificado con pruebas automatizadas:** la arquitectura de F4 y las etapas de
>   integridad 1 y 2 (D18 y D19). El registro E2-5 dio 97/97 pruebas aprobadas con el modelo
>   **simulado** y datos sintéticos.
> - **Pendiente:** el experimento A/B con el modelo real (F5 a F7) y F8 a F10. **Todavía no hay
>   resultados del experimento A/B formal.** El piloto de 5 casos (2026-11-03) no forma parte del
>   experimento formal.
> - El calendario de cada fase se conserva como plan original. La actualización está en
>   PLAN_PROYECTO.md §7.

## Bloqueantes

- [x] Aprobar D3 (experimento sobre texto fijo), D5 (sin avatar 3D), D9 (diccionario CENAREC) y D11 (Sonnet 5.5).
- [ ] **Revocar la clave de la API compartida en el chat** y crear una nueva en la consola de Anthropic.
- [ ] Guardar la clave nueva solo como variable de entorno `ANTHROPIC_API_KEY` (D14).
- [x] Elegir modelo → D11.
- [x] Decidir qué hacer con los archivos faltantes del kit → D13 (se escriben en el proyecto).
- [x] Confirmar fecha de la entrega final → 2026-11-17.
- [ ] Confirmar fecha de la defensa.
- [x] Consultar al profesor: trabajo individual y LLM como segundo anotador (D10) → autorizados.
- [ ] Revisar las condiciones de uso del sitio del CENAREC; si no están claras, escribir a su contacto.

## F0 · Planificación (31 oct)

- [x] Extraer requisitos de la rúbrica.
- [x] Analizar cobertura de la propuesta.
- [x] Evaluar viabilidad y riesgos.
- [x] Proponer arquitectura mínima viable y fases.
- [x] Buscar una fuente candidata del vocabulario LESCO y estimar el presupuesto.
- [x] Aprobar `PLAN_PROYECTO.md`.
- [x] Crear `docs/uso_de_ia.md` (registro de uso de IA desde el inicio).

## F1 · Propuesta y referencias (1 – 2 nov)

- [x] Proponer usuario concreto: persona sorda en ventanilla de trámites de una institución pública.
- [x] Adoptar el escenario (el autor delegó lo técnico el 2026-11-01); revisar si la cobertura del diccionario alcanza (F2).
- [x] Reunir evidencia del costo actual (escasez de intérpretes; comunicación solo escrita).
- [ ] **Autor (opcional):** conseguir una tarifa vigente y verificable de interpretación LESCO por hora.
- [x] Explicitar línea base (Config A: instrucciones genéricas).
- [x] Verificar metadatos de 3 referencias para el H1 y 2 candidatas más (`docs/referencias.md`).
- [ ] **Autor:** leer las 3 referencias del H1, marcarlas como leídas y escribir un resumen propio de cada una.
- [x] Redactar borrador de `docs/propuesta_H1.md`.

## F2 · Léxico y ética (2 – 4 nov)

- [x] Definir el esquema del léxico (`idw`, glosa; URL derivada) → `data/lexicon/FUENTE.md`.
- [x] Registrar el índice completo del CENAREC (1104 entradas, verificado con SHA-256). Ninguna entrada generada por LLM.
- [x] Comprobar la cobertura del escenario: hay PAGAR, FIRMAR, FACTURA, CERTIFICADO, ESPERAR, FILA, OFICINA, EXPEDIENTE; faltan DOCUMENTO, CÉDULA, FORMULARIO y TRÁMITE (servirán para los casos `SIN_COBERTURA`).
- [x] Redactar `docs/datos_y_etica.md`.
- [ ] **Autor:** escribir al contacto del sitio del CENAREC para informar del uso académico y pedir permiso explícito.

## F3 · Servidor MCP (3 – 5 nov)

- [x] Esquemas estrictos y descripciones de "cuándo usar" para las 3 herramientas.
- [x] Implementar `buscar_sena`, `validar_secuencia`, `guardar_resultado`.
- [x] Validación del lado del servidor con mensajes de rechazo útiles.
- [x] Cliente MCP mínimo (`agente/mcp_cliente.py`, interfaz del kit; D13).
- [x] Pruebas de entradas válidas e inválidas (24 pruebas, todas pasan).

## F4 · Agente, Skill y política (5 – 6 nov)

- [x] Copiar `agente.py` y `leer_traza.py` al repositorio (commit sin cambios) y escribir lo que falta (D13): `mcp_cliente.py`, configuraciones, políticas y guion simulado.
- [x] Adaptar el agente: Config A y Config B (única diferencia: `skill/SKILL.md`; verificado por prueba), `claude-sonnet-5-5`, esfuerzo `medium`, clave leída solo del entorno o `.env`.
- [x] Adaptar `leer_traza.py` a `guardar_resultado` y a los metadatos del experimento.
- [x] Agregar `obtener_transcripcion` al servidor: la frase llega como contenido de terceros (vector de inyección indirecta).
- [x] Redactar `eval/guia_anotacion.md` (definición de la tarea) y `skill/SKILL.md` (procedimiento, reglas, casos borde, criterio de parada).
- [x] Redactar la política de permisos (`politica/`): permitidas, con confirmación (demo), denegadas, ocultas; límites.
- [x] Ejecutor de casos reanudable (`agente/ejecutar_casos.py`).
- [x] Extremo a extremo con `--simulado` (prueba automática; la política bloquea un segundo guardado).
- [ ] **Autor:** crear una clave de API válida (la guardada en Windows da 401) y guardarla con `setx`.
- [x] Extremo a extremo con el modelo real (2026-11-03, clave del curso).

## F5 · Conjunto de evaluación (3 – 8 nov)

Detalle y responsables en PLAN_PROYECTO.md §7.1.

- [x] Guía de anotación v1 (`eval/guia_anotacion.md`): etiqueta por palabra; criterio de "difícil" definido antes.
- [x] **Autor:** aprobar D15, D16 (guía de la tarea), D17 y el plan de F5 (2026-11-01).
- [x] Redactar 48 casos sin datos personales (25 difíciles previstos, 52 %) y 5 casos de piloto aparte.
- [x] **Autor:** revisar y aprobar los casos.
  - *Registro (2026-11-13):* el autor revisó los 48 casos en 6 grupos de 8 (texto, dificultad
    prevista y motivos) y los aceptó **sin cambios**, según consta en la sesión. La aprobación
    corresponde al contenido del commit `f29713d`:
    `eval/casos.jsonl` SHA-256 `CB3BB55AF9A1764BA839D249512E9F81E0B17EE2184B4609F2B686D19C21E278`;
    `eval/casos_meta.jsonl` SHA-256 `8B7C8806AB25E7EB4C2C5713A110F28C03A21A217C5F41F18EB7FE4ADD58FD67`;
    `eval/anotaciones/plantilla.tsv` SHA-256 `A911FE4BA90BCCCDC159DF966A71F25D472AC96033168E83864D13F38BBF8193`.
    La dificultad sigue siendo **prevista** (25 de 48). Los motivos `variante_sentido` y `sinonimo` se
    confirman en la adjudicación (`docs/metricas.md` §5).
- [x] Tokenizador, plantilla con `OMITIR` prellenado (240 palabras, 166 por etiquetar), buscador e instrucciones.
- [ ] **Autor:** anotador 1 (2–3 horas estimadas).
  - *Estado (2026-11-13):* `eval/anotaciones/anotador1.tsv` creado como copia exacta de la plantilla
    aprobada (mismo SHA-256), con 0 de 240 etiquetas. Sin versionar todavía.
- [x] Script del anotador 2 y prompt v1 (`eval/anotador_llm.py`).
- [x] Ejecutar el anotador 2 (2026-11-03) y validarlo técnicamente (2026-11-13).
  - *Validación técnica agregada (2026-11-13):*
    - 48 de 48 casos con respuesta válida en el primer intento;
    - 240 de 240 posiciones alineadas con la plantilla;
    - 0 etiquetas vacías o inválidas y 0 diferencias entre `anotador2.tsv` y el registro de respuestas;
    - el SHA-256 del prompt de los 48 registros coincide con el del prompt vigente;
    - modelo declarado en las respuestas de la API: `claude-opus-5-5`.

    Validador: script temporal histórico que solo muestra cifras, con SHA-256
    `D591098139B69E7CF150025CDBC8663E3D29F98E042EFDEAADC2C3DB4ECB1B13`. Ese script no se
    versiona y la validación real del 2026-11-13 sigue atribuida a él. Una versión revisada,
    `eval/validar_anotador2.py`, se incorporará al repositorio en el próximo commit (ver la tarea
    siguiente). Aun así, la validación no se podrá reproducir solo con el repositorio público,
    porque sus entradas están ignoradas por git.
  - **Alcance:** es completitud técnica. **No** evalúa la calidad lingüística de las etiquetas; eso lo
    hacen el kappa y la adjudicación.
  - **Desviación de orden:** se ejecutó antes del anotador 1, no "después de que el autor termine" como
    se preveía. Esa secuencia, por sí sola, no demuestra la independencia.
  - Hasta esta validación constaba como "ejecución parcial o validación pendiente".
- [x] Validador revisado del anotador 2 (`eval/validar_anotador2.py`) y 28 pruebas sintéticas
      (`tests/test_validar_anotador2.py`), implementados y probados el 2026-11-14. **Falta el
      commit:** se incorporarán al repositorio en el próximo.
  - Solo lee y solo imprime cifras. Códigos de salida: 0 = válido, 1 = incompleto o inválido,
    2 = error de lectura.
  - Conserva la regla básica de selección de `eval/anotador_llm.py` (la última respuesta sin
    problemas de cada caso) e incorpora verificaciones adicionales:
    - vigencia del prompt;
    - ausencia de duplicados vigentes;
    - formato estricto del TSV.

    **No** es equivalente en todo a `eval/anotador_llm.py`.
  - Pruebas: **28/28** sintéticas aprobadas y **125/125** en la suite completa, registrada como
    `20261114-000942_suite-completa-f5-validador`. Integridad VERIFICADA y CONFORME, pero el registro
    sigue en `PENDIENTE_REVISION_HUMANA`.
  - **Todavía no se ha ejecutado sobre los archivos reales del anotador 2.** Las pruebas usan solo
    datos sintéticos.
  - La calidad lingüística todavía no ha sido evaluada mediante adjudicación, y el acuerdo entre
    anotadores está pendiente de medirse mediante Cohen's kappa. La independencia deberá justificarse
    mediante el protocolo y la trazabilidad del proceso, no únicamente mediante el valor de kappa.
- [ ] Opcional: ejecutar `eval/validar_anotador2.py` sobre los archivos reales, mostrando solo
      cifras, para enlazarlo con la validación del 2026-11-13.
- [x] Script de kappa (todas las palabras y solo contenido) y lista de desacuerdos.
- [ ] Calcular kappa y adjudicar (registro en `eval/adjudicacion.md`).
- [ ] Congelar el conjunto el 8 nov (SHA-256 + etiqueta git `eval-v1`).

## F6 · Piloto y línea base (8 – 9 nov)

- [x] Congelar métricas en `docs/metricas.md` (v1) antes de ejecutar.
- [x] Puntuación y comando único (`eval/puntuar.py`, `reproducir.py`), referencia desde la adjudicación (`eval/construir_referencia.py`); probado con trazas simuladas.
- [x] Piloto de 5 casos × A y B (2026-11-03): 10/10 terminaron bien; ≈ US$ 0,05 por ejecución → experimento ≈ US$ 14.
  - *Nota (2026-11-13):* el piloto usó casos aparte (`eval/piloto/`) para medir el costo y el
    funcionamiento. **No** sustituye a A×3 ni a B×3 y **no** es un resultado del experimento formal.
- [ ] Ejecutar Config A × 3; guardar todas las trazas.

## Etapas de integridad 1 y 2 · D18 y D19 (13 nov; no previstas en el calendario)

Detalle en `evidencia/etapa1_servidor_mcp.md`, `evidencia/etapa2_agente.md` y PLAN_PROYECTO.md §6.

- [x] Servidor MCP v0.2.0: `--caso` opcional y validado al arrancar. Vinculado, solo entrega la
      transcripción y solo guarda el resultado de ese caso (D18).
- [x] Agente: `--caso` obligatorio y validado con `fullmatch`. No arranca el servidor si la
      configuración no lo vincula al caso. La traza registra servidor, versión y caso vinculado (D18).
- [x] Configuraciones A, B y demo con la pareja `--caso {caso}`.
- [x] Validación documental y conjunto esperado antes de puntuar (D19). Si falla, se lanza
      `ErrorVinculacion` y `reproducir.py` termina con código 3: en esa ejecución no genera ni
      sobrescribe tablas ni puntuaciones parciales. No borra archivos de ejecuciones anteriores. Las
      fórmulas de `docs/metricas.md` v1 no cambian.
- [x] Instrumento de evidencia `evidencia/registrar_pruebas.py` (v1.2.1), con sus pruebas.
- [x] Registro E2-5: **97/97** pruebas automatizadas aprobadas, con el modelo simulado y datos
      sintéticos. **No** es el experimento A/B con el modelo real.
- [x] Commit `e254f68`, hecho y publicado por el autor. Contrastado con E2-5: 30 de 31 archivos de
      código coinciden; la diferencia es `.gitignore`.
- [ ] Actualización documental E2-6: **preparada en local, sin commit ni publicación en GitHub**.
      Incluye las adendas de los dos informes de evidencia, `PLAN_PROYECTO.md`, `README.md`,
      `docs/metricas.md`, `docs/uso_de_ia.md` y este archivo. Cada edición se verificó por separado.
      **Pendiente:** la verificación integral del conjunto después de la última edición.
- [ ] **Autor:** revisar los cambios documentales de E2-6 y decidir su commit y publicación.
- [ ] **Autor:** revisar las candidatas de evidencia (`PENDIENTE_REVISION_HUMANA`) y decidir si se
      publican.
- [ ] Servidor MCP: pasar `PATRON_CASO` de `match` a `fullmatch`. Hoy acepta un salto de línea final
      sin `--caso` (PLAN §8, abierto 5).
- [ ] Verificación en un clon limpio, y si es posible por otra persona (PLAN §8, abierto 6; ver también
      F10).
- [ ] Opcional: manifiesto de ejecución con configuraciones y repeticiones junto a las trazas (PLAN §8,
      abierto 7).
- [ ] **Autor:** completar en `docs/uso_de_ia.md` el uso de IA del 2026-11-01 al 2026-11-13 y aclarar
      la discrepancia cronológica de la fila del 2026-11-01.

## F7 · Experimento y seguridad (9 – 11 nov)

- [ ] Ejecutar Config B × 3 con los mismos casos y parámetros.
- [ ] Diseñar y ejecutar ≥ 5 ataques de inyección indirecta; documentar el resultado de cada uno.
- [x] Script de un comando que regenera las tablas desde las trazas → `reproducir.py` (hecho en F6).
      Desde D19, si falta o es inconsistente alguna ejecución, termina con código 3 sin generar ni
      sobrescribir tablas. No borra las de ejecuciones anteriores.
- [ ] Análisis de errores con tipología y ejemplos de trazas.

## F8 · Demo de audio (12 nov)

- [ ] STT de un audio sintético hacia el agente (se recorta si hay atraso).

## F9 · Artículo (9 – 15 nov; borradores desde el 5 nov)

- [ ] Artículo en la plantilla: 6–8 páginas, resumen con cifra, ≥ 8 referencias (≥ 5 revisadas por pares).
- [ ] Declarar en el artículo: trabajo individual y LLM como anotador (ambos autorizados por el profesor) y validación documental del léxico.
- [ ] Limitaciones, ética y declaración de uso de IA.

## F10 · Cierre y entrega (16 – 17 nov)

- [ ] README final con instalación, configuración y comando de reproducción.
- [ ] Prueba en un clon limpio siguiendo solo el README.
- [ ] Revisión final de datos personales en repositorio, trazas y artículo.
- [ ] Presentación (8 min) + demo en vivo (3 min) con traza real y acción bloqueada + preguntas (4 min).
