# Propuesta H1 — LESCO-Agent

> **Borrador** (2026-11-01). Estructura según los puntos que exige el H1 en la especificación.
> No se encontró `plantilla_propuesta.md` en el kit; si aparece, se migra a ella.
> Marcas: **[?]** = dato que el autor debe confirmar.

**Título:** LESCO-Agent: Diseño y evaluación de un agente inteligente basado en Skills y MCP para la
generación asistida de secuencias en Lengua de Señas Costarricense a partir de audio en español.

**Autor:** Elmer Mondragón Prieto (proyecto individual autorizado por el profesor).

## 1. Problema y usuario concreto

**Usuario:** una persona sorda usuaria de LESCO que realiza un trámite en la ventanilla de atención
al público de una institución pública costarricense. (Escenario adoptado el 2026-11-01; puede
cambiarse si la cobertura del diccionario resulta insuficiente en la fase 2.)

**Situación:** el funcionario explica de forma oral los requisitos, documentos, pasos y plazos del
trámite. No hay intérprete de LESCO disponible en ese momento, y la alternativa habitual es pasar a
comunicación escrita en español, que no es la lengua materna de muchas personas sordas.

**Costo actual (evidencia disponible):**

- Hay una lista de **30 intérpretes y mediadores certificados** frente a una población sorda que se
  estima en **más de 70 000 personas** (Teletica, 30 sep. 2023; la nota no atribuye la estimación de
  población).
- Un representante de una asociación de personas sordas estima **unos 80 intérpretes** en el país y
  señala que, por esa escasez, instituciones piden a las personas sordas comunicarse **solo por
  escrito** (El Mundo CR, opinión, 10 mar. 2026).
- **[?] Costo monetario:** falta una tarifa vigente y verificable de interpretación LESCO por hora.
  Se encontró una referencia a una tarifa institucional de la UNED de 2018, pero el documento ya no
  está disponible en línea (HTTP 404 el 2026-10-31), así que no se usa.

El costo actual se expresa, por tanto, como **falta de acceso**: la información oral del trámite no
llega en LESCO cuando no hay intérprete.

**Alcance ético:** LESCO-Agent propone **secuencias candidatas** de señas de un vocabulario
documentado como apoyo. No traduce LESCO completo (que tiene gramática propia) ni sustituye a
intérpretes.

## 2. Por qué un agente

La tarea exige varias decisiones encadenadas sobre un texto variable: segmentar la frase, buscar cada
concepto en un vocabulario cerrado, elegir entre señas candidatas, detectar conceptos sin seña
disponible, validar la secuencia y registrar el resultado. Un agente con herramientas permite que
esas decisiones queden **trazadas** y que el servidor **impida** usar señas fuera del vocabulario.

## 3. Datos

- **Vocabulario:** subconjunto temático del Diccionario LESCO del CENAREC (lesco.cenarec.go.cr),
  elaborado a partir del LESCO Corpus (Oviedo y Ramírez Valerio, 2018). Se registran solo ID, glosa,
  variantes en español, URL y fecha de consulta; no se copian videos. Condiciones de uso por
  confirmar (plan B: citar entrada por entrada y pedir permiso al CENAREC).
- **Casos de evaluación:** ≥ 40 frases de trámites redactadas por el autor, sin datos personales,
  ≥ 30 % difíciles. Etiquetadas por el autor y por un LLM (autorizado por el profesor); se reporta
  kappa de Cohen.
- **Audio (solo demo):** sintético o grabado por el autor.

## 4. Herramientas previstas (servidor MCP propio)

| Herramienta | Tipo | Propósito |
|---|---|---|
| `buscar_sena` | Lectura | Buscar entradas del vocabulario para una palabra o concepto en español. |
| `validar_secuencia` | Lectura | Verificar que todos los IDs de una secuencia existen en el vocabulario. |
| `guardar_resultado` | Escritura | Guardar la secuencia final; el servidor rechaza IDs inexistentes y rutas no permitidas. |

## 5. Pregunta de investigación

¿En qué medida la incorporación de una Skill procedimental (`SKILL.md`) mejora la precisión en la
selección de secuencias de LESCO por parte de un agente, frente al mismo agente con instrucciones
genéricas, y qué impacto tiene sobre el tiempo de procesamiento y el consumo de tokens?

## 6. Línea base y diseño

| | Config A — línea base | Config B — propuesta |
|---|---|---|
| Modelo | `claude-sonnet-5-5` | `claude-sonnet-5-5` |
| Herramientas, política y límites | Idénticos | Idénticos |
| Instrucciones | Genéricas (rol y tarea) | Genéricas + `SKILL.md` (procedimiento, reglas, casos borde, criterio de parada) |
| Casos | Los mismos ≥ 40, congelados antes de ejecutar | Los mismos |
| Repeticiones | 3 | 3 |

**Métricas (definidas antes de ejecutar):** F1 a nivel de seña, exactitud de secuencia completa, tasa
de abstención correcta (`SIN_COBERTURA`), IDs inválidos propuestos, tokens y duración por caso;
media y desviación estándar.

## 7. Viabilidad y plan B

| Riesgo | Plan B |
|---|---|
| Condiciones de uso del diccionario poco claras | Citar entrada por entrada; pedir permiso al CENAREC. |
| Escenario sin vocabulario suficiente en el diccionario | Cambiar a otro contexto con más cobertura antes de congelar casos. |
| Sesgo del LLM anotador | Modelo distinto del agente, sin ver otras etiquetas; se reporta como limitación. |
| Plazo (entrega 2026-11-17) | Recortar la demo de audio antes que el experimento. |

## 8. Referencias leídas

Ver [referencias.md](referencias.md). **[?] Pendiente:** que el autor lea y resuma las tres
referencias propuestas para el H1 y marque cada una como leída.
