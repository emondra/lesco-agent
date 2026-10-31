# TODO — LESCO-Agent

Tareas pendientes, ordenadas según el calendario de 14 días de
[PLAN_PROYECTO.md](PLAN_PROYECTO.md#7-fases-de-desarrollo). Las referencias D1–D12 apuntan a las
decisiones de ese plan.

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

- [ ] Esquemas estrictos y descripciones de "cuándo usar" para las 3 herramientas.
- [ ] Implementar `buscar_sena`, `validar_secuencia`, `guardar_resultado`.
- [ ] Validación del lado del servidor con mensajes de rechazo útiles.
- [ ] Pruebas de entradas válidas e inválidas.

## F4 · Agente, Skill y política (5 – 6 nov)

- [ ] Copiar `agente.py` y `leer_traza.py` al repositorio y escribir lo que falta (D13): `mcp_cliente.py`, configuración, política y guion simulado.
- [ ] Adaptar el agente: Config A y Config B (única diferencia: `SKILL.md`), modelo `claude-sonnet-5-5`, clave leída solo del entorno.
- [ ] Adaptar `leer_traza.py`: hoy cuenta como escrituras `crear_ticket` y `guardar_borrador_correo`; debe contar `guardar_resultado`.
- [ ] Redactar `skill/SKILL.md`: procedimiento, reglas, casos borde, criterio de parada.
- [ ] Redactar la política de permisos (permitidas, confirmación, denegadas, ocultas; límites de pasos y tokens).
- [ ] Ejecutor de casos: un caso por ejecución, una traza por ejecución.
- [ ] Caso de extremo a extremo con `--simulado` y luego con el modelo real.

## F5 · Conjunto de evaluación (3 – 8 nov)

- [ ] Guía de anotación: etiqueta por segmento = ID del léxico o `SIN_COBERTURA`; criterio de "difícil" definido antes.
- [ ] Redactar ≥ 40 casos sin datos personales, ≥ 30 % difíciles.
- [ ] Anotador 1 (autor) y anotador 2 (LLM distinto del agente, prompt fijo, sin ver otras etiquetas).
- [ ] Calcular kappa de Cohen y resolver desacuerdos (documentando cómo).
- [ ] Congelar el conjunto el 8 nov (etiqueta git + hash).

## F6 · Piloto y línea base (8 – 9 nov)

- [ ] Congelar métricas en `docs/metricas.md` antes de ejecutar.
- [ ] Piloto de 5 casos; recalibrar el presupuesto con `leer_traza.py`.
- [ ] Ejecutar Config A × 3; guardar todas las trazas.

## F7 · Experimento y seguridad (9 – 11 nov)

- [ ] Ejecutar Config B × 3 con los mismos casos y parámetros.
- [ ] Diseñar y ejecutar ≥ 5 ataques de inyección indirecta; documentar el resultado de cada uno.
- [ ] Script de un comando que regenera las tablas desde las trazas.
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
