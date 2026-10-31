# PLAN_PROYECTO — LESCO-Agent

> **Estado:** Fase 0 cerrada. Plan **aprobado** por el autor el 2026-10-31 (D3, D5, D9 y D11
> aprobadas explícitamente). Entrega final: **2026-11-17**.
> No contiene código, resultados experimentales ni vocabulario LESCO.

**Título:** LESCO-Agent: Diseño y evaluación de un agente inteligente basado en Skills y MCP para la
generación asistida de secuencias en Lengua de Señas Costarricense a partir de audio en español.

## Convenciones de este documento

| Marca | Significado |
|---|---|
| **[R]** | Requisito tomado literalmente de la especificación/rúbrica del proyecto final. |
| **[P]** | Elemento ya presente en la propuesta inicial (documento `Proyecto- Elmer Mondragon_LESCO.doc`). |
| **[D]** | Decisión de diseño de este plan (aprobada por el autor el 2026-10-31); no es un requisito de la rúbrica. |
| **[?]** | Dato que falta y que debe confirmar el equipo o el profesor. |

Fuentes analizadas:

1. `proyecto_final_maestria.pdf` — especificación oficial y rúbrica (6 páginas).
2. `Proyecto- Elmer Mondragon_LESCO.doc` — propuesta inicial (texto + diagrama de 6 capas).

---

## 1. Requisitos obligatorios de la rúbrica [R]

### 1.1 Condiciones no negociables

| ID | Requisito |
|---|---|
| NN1 | Sin artículo, sin nota: el proyecto no se evalúa sin el artículo completo. |
| NN2 | Citas verificables: una referencia inexistente, inventada o no leída anula la sección de trabajo relacionado. |
| NN3 | Resultados reproducibles: toda cifra del artículo debe regenerarse desde las trazas entregadas; si no, el criterio de resultados queda con nota máxima "Aceptable". |
| NN4 | Datos anonimizados: ningún dato personal real sin anonimizar en repositorio, trazas ni artículo. |
| NN5 | Uso de IA declarado: para qué se usó y cómo se verificó el resultado. |

### 1.2 Requisitos mínimos del sistema

| ID | Componente | Mínimo exigido |
|---|---|---|
| S1 | Dominio | Distinto del caso de reseñas. Un usuario concreto con un problema concreto. |
| S2 | Servidor MCP propio | ≥ 3 herramientas, ≥ 1 de escritura, validación del lado del servidor. Descripciones que dicen cuándo usar cada herramienta; esquemas estrictos; rechazos con mensajes útiles. |
| S3 | Skill | Un `SKILL.md` con procedimiento, reglas, criterio de parada y reglas para casos borde. |
| S4 | Política de permisos | Herramientas permitidas, con confirmación, denegadas u ocultas; límites de pasos y tokens. Versionada y justificada en el artículo. |
| S5 | Trazas | Una traza por ejecución con cada llamada, decisión, tokens y duración. Todas las trazas reportadas en el repositorio. |
| S6 | Conjunto de evaluación | ≥ 40 casos, ≥ 30 % difíciles, etiquetados por dos personas, acuerdo (kappa) reportado. |
| S7 | Análisis de seguridad | ≥ 5 ataques de inyección indirecta, probados y documentados con su resultado; defensas en la skill **y** en el código. |
| S8 | Reproducibilidad | Un comando regenera los resultados; README con instalación, configuración y ese comando. Un integrante que no escribió el código lo verifica en máquina limpia. |

### 1.3 Requisitos del experimento

| ID | Requisito |
|---|---|
| E1 | Pregunta de investigación comparativa: dos configuraciones que difieren en **una sola variable**. |
| E2 | Mismo conjunto de evaluación para ambas configuraciones; línea base real. |
| E3 | Métricas definidas **antes** de ejecutar. |
| E4 | ≥ 3 ejecuciones por configuración; reportar media y dispersión. |
| E5 | No ajustar el conjunto de evaluación después de ver resultados. |
| E6 | Análisis de errores con tipología y ejemplos tomados de las trazas. |

### 1.4 Artículo científico

| ID | Requisito |
|---|---|
| A1 | Plantilla LaTeX del curso (`plantilla_paper/`), compila sin cambios en Overleaf; español o inglés. |
| A2 | 6–8 páginas sin contar referencias ni apéndices. |
| A3 | Resumen/abstract de 150–200 palabras con el resultado principal **con una cifra**. |
| A4 | Secciones: Introducción, Trabajo relacionado (3 grupos temáticos contrastados), Sistema propuesto (con figura), Metodología, Resultados, Discusión y limitaciones, Conclusiones, Apéndice (comandos exactos, versión del modelo, fecha). |
| A5 | ≥ 8 referencias, ≥ 5 revisadas por pares, todas abiertas y leídas por el equipo. |
| A6 | Explicar qué decide la skill y qué decide el código. |
| A7 | Limitaciones, amenazas a la validez, ética, riesgos de despliegue y declaración de uso de IA. |

### 1.5 Hitos y puntaje

| Hito | Semana | Entregable | Pts |
|---|---|---|---|
| H1 · Propuesta | 2 | Una página con la plantilla de propuesta: problema, por qué un agente, datos, herramientas previstas, pregunta de investigación, línea base y **tres referencias leídas**. | 10 |
| H2 · Avance | 5 | Arquitectura de extremo a extremo funcionando con trazas; conjunto de evaluación completo con kappa; **línea base medida**; borrador de Introducción, Trabajo relacionado y Metodología. | 15 |
| H3 · Entrega final | 8 | Repositorio con el sistema, trazas de todas las ejecuciones reportadas y artículo en PDF (Sistema 25 + Artículo 35). | 60 |
| H4 · Defensa | 8 o 9 | 15 min: 8 presentación, 3 demo en vivo (traza real + una acción bloqueada por la política), 4 preguntas. Cualquier integrante debe poder responder sobre cualquier parte. | 15 |

### 1.6 Organización

| ID | Requisito |
|---|---|
| O1 | Equipos de 3 personas. |
| O2 | Se permite (y se espera) reutilizar el kit de la clase 3: `agente.py`, servidores, `leer_traza.py` (`--csv`), `plantilla_propuesta.md`, `plantilla_paper/`. |

---

## 2. Cobertura de la propuesta actual

| Req. | Estado | Evidencia en la propuesta / comentario |
|---|---|---|
| S1 Dominio | ✅ Cubierto | LESCO, distinto de reseñas. |
| S1 Usuario concreto | ⚠️ Parcial | "Personas sordas usuarias de LESCO" en entornos educativos, institucionales y de atención al público: es una **población**, no un usuario concreto en una situación concreta. Falta el **costo actual estimado** (criterio H1). |
| Por qué un agente | ✅ Cubierto | Coordinación de STT, análisis semántico, consulta de vocabulario validado, selección de secuencias y control de animaciones. |
| E1 Pregunta comparativa | ✅ Cubierto | Skill procedimental vs. mismo agente sin Skill; impacto en tiempo y recursos. Coincide con el tipo de pregunta que la rúbrica pone como ejemplo. |
| E2 Línea base | ⚠️ Implícita | "El mismo agente sin dicha Skill" funciona como línea base, pero no está definida explícitamente (qué instrucciones genéricas recibe). |
| E3 Métricas | ❌ Falta | "Precisión en la selección de secuencias" no está operacionalizada. |
| S2 Servidor MCP | ⚠️ Esbozado | Diagrama: `buscar_sena`, `validar_secuencia`, `guardar_resultado` (3 herramientas, 1 de escritura). Faltan esquemas, validaciones y descripciones. |
| S3 Skill | ⚠️ Esbozado | Diagrama: `SKILL.md` — "Reglas y procedimiento". Falta criterio de parada y casos borde. |
| S4 Política | ⚠️ Esbozado | Diagrama: "Política de permisos — límites y controles". Sin clasificación de herramientas ni límites. |
| S5 Trazas | ⚠️ Esbozado | Diagrama: "Servicio transversal: trazas, métricas y auditoría". |
| Datos | ⚠️ Fuente candidata | La propuesta no la identifica. Candidata encontrada: diccionario LESCO del CENAREC (ver D9). Licencia pendiente de confirmar. |
| S6 Conjunto de evaluación | ❌ Falta | Sin casos, sin anotadores, sin kappa. |
| S7 Seguridad | ❌ Falta | No se identifican vectores de inyección indirecta ni ataques. |
| S8 Reproducibilidad | ❌ Falta | Repositorio vacío (solo README y .gitignore). |
| H1 Tres referencias leídas | ❌ Falta | La propuesta no incluye referencias. |
| A1–A7 Artículo | ❌ Falta | Aún no iniciado (esperado en esta etapa). |
| NN4 Anonimización | ❌ Falta | No hay plan de datos (audio con voces reales es dato personal). |
| NN5 Uso de IA | ❌ Falta | Aún no declarado. |
| O1 Equipo de 3 | ✅ Excepción autorizada | **Proyecto individual**, autorizado por el profesor (confirmación informada por el autor el 2026-10-31). El profesor también autorizó un LLM como segundo anotador (D10). |
| O2 Kit clase 3 | ⚠️ Parcial | Recibidos `agente.py` y `leer_traza.py`. **Faltan:** `mcp_cliente.py` (importado por `agente.py`, imprescindible), `config.json`, `instrucciones.md`, archivo de política, guion simulado, servidores de ejemplo, `plantilla_propuesta.md` y `plantilla_paper/`. |

Capas del diagrama de la propuesta: (1) Entrada de audio, (2) Procesamiento STT → normalización → segmentación,
(3) Agente IA (LLM + Skill + política), (4) Servidor MCP, (5) Avatar 3D, (6) Visualización (avatar,
subtítulos, indicadores de incertidumbre), más un servicio transversal de trazas.

---

## 3. Requisitos que faltan (resumen accionable)

1. **Usuario concreto y costo actual** (H1): elegir *una* situación (p. ej., un tipo de aviso institucional) y estimar el costo actual con una fuente citable. **[?]**
2. **Fuente de datos LESCO:** candidata identificada (D9); falta confirmar licencia/condiciones de uso.
3. **Tres referencias leídas** para H1 (y ≥ 8, ≥ 5 revisadas por pares, para el artículo). Ninguna se añadirá sin haber sido abierta y verificada.
4. **Línea base explícita** y **métricas definidas antes** del experimento.
5. **Conjunto de evaluación** ≥ 40 casos, ≥ 30 % difíciles, 2 anotadores, kappa.
6. **Diseño de seguridad**: vectores de inyección indirecta y 5 ataques.
7. **Política de permisos** concreta y versionada.
8. **Plan de anonimización** y de datos sintéticos.
9. **Archivos faltantes del kit de clase 3** (sobre todo `mcp_cliente.py`) y confirmación del trabajo individual. **[?]**
10. **Artículo** en la plantilla del curso.

---

## 4. Viabilidad técnica

| Componente | Viabilidad | Comentario |
|---|---|---|
| Agente + Skill + MCP + política + trazas | **Alta** | Es el mismo patrón construido en clase; se reutiliza el kit de la clase 3. |
| Selección de secuencias sobre un léxico cerrado | **Alta**, condicionada a datos | Técnicamente es recuperación + selección + validación contra un vocabulario. Depende por completo de contar con un léxico LESCO verificable. |
| Speech-to-Text en español | **Media-alta** | Existen motores de STT para español; añade variabilidad y costo, y su error contaminaría la variable experimental (ver D3). |
| Corrección lingüística de la salida | **Baja sin apoyo experto** | LESCO tiene gramática propia; no es una traducción palabra a palabra. Sin personas competentes en LESCO no puede afirmarse corrección lingüística, solo correspondencia con un estándar de referencia. |
| Avatar 3D con manos, cuerpo y expresiones faciales | **Baja en 8 semanas** | Requiere datos de animación por seña que la propuesta no identifica. No aporta a la pregunta de investigación. |
| Conjunto de evaluación con 2 anotadores | **Media** | Viable si se consiguen dos anotadores con conocimiento de LESCO; es el principal cuello de botella humano. |
| Costo de ejecución | **Alta** | Estimación previa de US$ 2–70 según el modelo (sección 6.5). |
| Calendario | **Media-baja** | 17 días (hasta el 2026-11-17) para una sola persona. Viable solo con el alcance recortado (D3, D5) y sin holgura para rehacer el conjunto de evaluación. |

**Conclusión:** el proyecto es viable si se acota a *generación asistida de secuencias de glosas/IDs
de un léxico LESCO verificado*, a partir de texto transcrito, con STT como etapa de entrada para la
demostración y el avatar 3D fuera del alcance mínimo.

---

## 5. Riesgos principales y plan B

| # | Riesgo | Prob. | Impacto | Mitigación / Plan B |
|---|---|---|---|---|
| R1 | Las condiciones de uso del diccionario CENAREC no permiten reutilizar sus entradas, o el sitio deja de estar disponible. | Media | Crítico | Guardar solo ID, glosa y URL de cada entrada (sin copiar videos). Pedir permiso por la vía de contacto del sitio. Plan B: citar las entradas una por una con fecha de consulta y usar la copia de Internet Archive como respaldo. **Nunca** generar entradas con un LLM. |
| R2 | Sesgo del LLM como segundo anotador (autorizado por el profesor). | Media | Medio | D10: modelo distinto del agente, prompt fijo y versionado, sin ver otras etiquetas. Se reporta como amenaza a la validez en el artículo. |
| R11 | Archivos faltantes del kit (`mcp_cliente.py`). | Cierta | Medio | D13: se escriben desde cero (cliente MCP mínimo por stdio). Se prueban con `--simulado` antes de gastar en la API. |
| R13 | Filtración de la clave de la API. | Media | Alto | D14. La clave compartida en el chat el 2026-10-31 debe revocarse y reemplazarse. |
| R12 | Plazo corto (entrega el 2026-11-17). | Cierta | Alto | Calendario día a día (sección 7), alcance mínimo, congelar el conjunto de evaluación el 8 de noviembre como máximo. |
| R3 | Afirmar "traducción" cuando el sistema solo selecciona señas. | Media | Alto (ético y de validez) | Lenguaje acotado: "secuencia candidata asistida". El sistema no sustituye a intérpretes. |
| R4 | El error de STT confunde la comparación Skill vs. sin Skill. | Alta | Alto (metodología) | D3: experimento sobre transcripciones fijas; STT solo en la demo. |
| R5 | El avatar 3D consume el calendario. | Alta | Alto | D5: fuera del MVP; visualización mínima. |
| R6 | Datos personales en audios o trazas. | Media | Crítico (NN4) | Casos redactados por el equipo; audio sintético o grabado con consentimiento; revisión de trazas antes de cada commit. |
| R7 | Referencias no verificadas. | Media | Crítico (NN2) | Registro de lectura por referencia (quién la leyó, DOI/URL, fecha). |
| R8 | Variabilidad del modelo / cambios de versión. | Media | Medio | Fijar versión del modelo, temperatura y fecha en la traza y el apéndice. |
| R9 | Una sola persona responde por todo en la defensa. | Cierta | Medio | Trabajo individual autorizado; ensayar preguntas sobre todas las partes. |
| R10 | Costo de API. | Baja-media | Medio | Desarrollar con `--simulado` (sin costo). Recalibrar la estimación con una corrida piloto de 5 casos. |

---

## 6. Arquitectura mínima viable (aprobada) [D]

Se conserva la estructura de capas de la propuesta, ajustando el alcance:

```
 [Audio .wav]                                 (solo demo y entrada opcional)
      │  stt/  — transcripción + normalización + segmentación (cacheada en disco)
      ▼
 [Texto en español]  ◄─── eval/casos  (entrada del experimento: texto fijo)
      │
      ▼
 ┌──────────────────────── agent/ (basado en agente.py del kit) ─────────────────────┐
 │  LLM  +  Config A: instrucciones genéricas   |   Config B: skill/SKILL.md          │
 │  policy/permisos (permitidas · confirmación · denegadas · ocultas; límites)        │
 │  Envoltura de resultados de herramienta como datos no confiables                   │
 └──────────────┬─────────────────────────────────────────────────────────────────────┘
                │ MCP (stdio)
                ▼
 ┌──────────── mcp_server/ ─────────────┐        ┌──────── data/lexicon/ ────────┐
 │ buscar_sena        (lectura)         │ ─────► │ entradas con ID, glosa,       │
 │ validar_secuencia  (lectura)         │        │ fuente, licencia, validador   │
 │ guardar_resultado  (escritura)       │ ─────► │ outputs/ (resultados)         │
 │ validación de esquemas en servidor   │        └───────────────────────────────┘
 └──────────────────────────────────────┘
                │
                ▼
 [Salida] secuencia de IDs/glosas + segmentos sin cobertura + indicador de incertidumbre
                │
                ▼
 viz/ mínima (texto/HTML: glosas + subtítulo)          Avatar 3D → trabajo futuro

 Transversal: traces/ (una traza JSON por ejecución) → leer_traza.py --csv → results/
```

### Decisiones de diseño

D3, D5, D9 y D11 fueron aprobadas explícitamente por el autor el 2026-10-31; el resto se aprobó con el plan.

| ID | Decisión | Justificación |
|---|---|---|
| D1 | La unidad de salida es una **secuencia de IDs del léxico** (con su glosa), no una animación. | Medible contra un estándar de referencia; evita afirmar corrección lingüística no verificable. |
| D2 | El servidor rechaza cualquier ID que no exista en el léxico. | Defensa en profundidad (S2): el agente no puede "inventar" señas. |
| D3 | El experimento usa **texto fijo** como entrada; el STT queda fuera del lazo experimental (se usa en la demo). | E1: una sola variable. El error del STT sería un confusor. |
| D4 | Variable experimental única: presencia de `SKILL.md` (B) vs. instrucciones genéricas (A). Todo lo demás idéntico: modelo, temperatura, herramientas, política, límites, casos. | Responde la pregunta de la propuesta y cumple E1. |
| D5 | Avatar 3D fuera del MVP; visualización mínima de glosas, subtítulo e incertidumbre. | Riesgo R5; no afecta a la pregunta. |
| D6 | Cuando no hay seña en el léxico, el agente marca el segmento como **sin cobertura** en lugar de aproximar. | Evita contenido inventado; caso difícil medible. |
| D7 | Resultados de herramientas envueltos y tratados como datos no confiables; `guardar_resultado` con ruta restringida y esquema estricto. | S7: defensas en la skill y en el código. |
| D8 | Python + kit de clase 3 (sin dependencias externas, como el kit); dependencias fijadas si se agregan. | O2 y S8. |
| D9 | **Fuente del léxico:** Diccionario LESCO del CENAREC (Oviedo y Ramírez Valerio; diccionario básico de ~1100 entradas según su publicación de 2018). *Actualizado 2026-11-01:* se registró el **índice completo** (1104 entradas: `idw` y glosa) en `data/lexicon/cenarec_indice.tsv`, verificado con SHA-256 contra la página fuente; la URL de cada entrada se deriva del `idw`. Usar el índice completo, en vez de un subconjunto, permite distinguir de forma objetiva los conceptos que no están en el diccionario (`SIN_COBERTURA`). | Fuente pública, institucional y con publicación académica asociada. La validación es **documental** (coincide con la fuente), no lingüística por una persona experta: se declara como limitación. |
| D10 | **Anotación:** Anotador 1 = el autor. Anotador 2 = un LLM distinto del modelo del agente, con un prompt fijo, sin ver las salidas del agente ni las etiquetas del autor. Kappa de Cohen sobre etiquetas por segmento (ID del léxico o `SIN_COBERTURA`). Si aparece una segunda persona, reemplaza al LLM. | Única opción viable para una persona sola. **Autorizada por el profesor**; en el artículo se declara la autorización y el posible sesgo del LLM. |
| D11 | **Modelo del agente:** `claude-sonnet-5-5` vía la API de Claude, como ya hace `agente.py`. Mismo modelo, versión y parámetros para A y B; la versión y la fecha se registran en cada traza. **Segundo anotador (D10):** `claude-opus-5-5`, otro modelo distinto del agente. Desarrollo y depuración con `--simulado` (sin costo). | Sonnet 5.5 usa bien las herramientas, cuesta la mitad que Opus 5.5 (≈ US$ 32 con margen) y no es tan fuerte como para que la Skill deje de notarse (efecto techo). Alternativa económica: `claude-haiku-5-5` (≈ US$ 2), con más riesgo de fallar con las herramientas. |
| D13 | **Kit de clase 3 como referencia:** los archivos que faltan (`mcp_cliente.py`, configuración, política, guion simulado) se escriben desde cero en este repositorio, siguiendo el estilo del kit (Python estándar, sin dependencias). El artículo se escribe en LaTeX con una estructura que respete las secciones de la rúbrica; si llega la plantilla oficial, se migra a ella. | Decisión del autor (2026-10-31): el kit es un ejemplo. |
| D14 | **Secretos:** la clave de la API solo se lee desde la variable de entorno `ANTHROPIC_API_KEY` o desde un `.env` local ignorado por git. Nunca se escribe en el código, la configuración, las trazas ni el artículo. | Seguridad y anonimización (NN4). |
| D12 | **Calendario comprimido** al 2026-11-17 (sección 7). | Plazo de entrega confirmado por el autor. |

### Herramientas MCP previstas (desde la propuesta, a especificar)

| Herramienta | Tipo | Política propuesta | Validación del servidor (borrador) |
|---|---|---|---|
| `buscar_sena` | Lectura | Permitida | Texto no vacío, longitud máxima, sin caracteres de control. |
| `validar_secuencia` | Lectura | Permitida | Lista de IDs con tamaño máximo; cada ID debe existir. |
| `guardar_resultado` | Escritura | Con confirmación en demo / permitida en experimento con ruta fija **[D, a discutir]** | IDs válidos, esquema estricto, nombre de archivo saneado, directorio fijo, sin sobrescritura. |
| Escritura/borrado arbitrario de archivos, red | — | Denegadas / ocultas | — |

### Métricas propuestas (a congelar antes del experimento) [D]

- Exactitud de secuencia (coincidencia exacta con el estándar).
- Precisión, exhaustividad y F1 a nivel de seña.
- Tasa de abstención correcta en segmentos sin cobertura.
- IDs inválidos propuestos por el agente (rechazados por el servidor).
- Tokens, duración, pasos, llamadas, denegaciones y errores por ejecución (desde `leer_traza.py --csv`).
- Media y desviación estándar sobre ≥ 3 ejecuciones por configuración.

### Vectores de inyección indirecta a estudiar [D]

1. Texto transcrito que contiene instrucciones dirigidas al agente.
2. Campos textuales de entradas del léxico devueltas por `buscar_sena`.
3. Metadatos de casos o archivos de entrada.

Los 5 ataques concretos se diseñan en la fase 7; los resultados se reportarán solo desde trazas.

### 6.5 Presupuesto estimado (estimación previa, no resultado experimental) [D]

Precios de lista de la API de Anthropic (tabla vigente al 2026-10-06, US$ por millón de tokens):
Opus 5.5: 4 entrada / 20 salida · Sonnet 5.5: 2 / 10 · Haiku 5.5: 0,10 / 0,50.

**Supuestos** (se recalibran con un piloto de 5 casos medido con `leer_traza.py`):
≈ 20 000 tokens de entrada y ≈ 1 500 de salida por caso (5 pasos aprox., con la conversación acumulada).

| Concepto | Ejecuciones de caso |
|---|---|
| Experimento: 40 casos × 2 configuraciones × 3 repeticiones | 240 |
| Piloto | 10 |
| Ataques de inyección: 5 × 2 configuraciones × 3 repeticiones | 30 |
| Depuración con modelo real (el resto se hace con `--simulado`) | ~100 |
| **Total** | **~380** |

| Modelo | Costo por caso | Total estimado | Con margen del 50 % |
|---|---|---|---|
| `claude-opus-5-5` | ≈ US$ 0,11 | ≈ US$ 42 | **≈ US$ 65** |
| `claude-sonnet-5-5` | ≈ US$ 0,055 | ≈ US$ 21 | **≈ US$ 32** |
| `claude-haiku-5-5` | ≈ US$ 0,003 | ≈ US$ 1,10 | **≈ US$ 2** |

El LLM anotador (D10, 40 llamadas cortas con Opus 5.5) suma menos de US$ 1.
**Modelo elegido (D11): Sonnet 5.5 → presupuesto de referencia ≈ US$ 32.** Las cifras reales solo podrán reportarse
desde las trazas.

---

## 7. Fases de desarrollo

Calendario comprimido (D12) con **entrega final el 2026-11-17**. Las fechas de H1, H2 y la defensa
no se conocen; si alguna cae antes, se reordena. Cada fase termina en uno o más commits pequeños y
revisables.

| Fase | Días (2026) | Objetivo | Entregables en el repositorio | Criterio de salida |
|---|---|---|---|---|
| **F0** Planificación | 31 oct | Analizar rúbrica y propuesta; acordar arquitectura. | `PLAN_PROYECTO.md`, `README.md`, `TODO.md` | ✅ Plan aprobado. |
| **F1** Propuesta y referencias | 1 – 2 nov | Usuario concreto, datos, línea base; empezar a leer referencias. | `docs/propuesta_H1.md`, `docs/referencias.md` (registro de lectura) | 3 referencias leídas y registradas. |
| **F2** Léxico y ética | 2 – 4 nov | Subconjunto del diccionario CENAREC (D9) y política de datos. | `data/lexicon/`, `docs/datos_y_etica.md` | Cada entrada con URL y fecha de consulta. |
| **F3** Servidor MCP | 3 – 5 nov | Implementar las 3 herramientas con validación. | `mcp_server/`, pruebas de validación | Pruebas pasan; rechazos con mensajes útiles. |
| **F4** Agente, Skill y política | 5 – 6 nov | Adaptar el kit: Config A y B, política, trazas, ejecutor de casos. | `agent/`, `skill/SKILL.md`, `policy/` | Un caso de extremo a extremo con traza completa (primero `--simulado`, luego el modelo real). |
| **F5** Conjunto de evaluación | 3 – 8 nov (en paralelo) | ≥ 40 casos, ≥ 30 % difíciles, anotación (D10) y kappa. | `eval/` | Kappa calculado; conjunto **congelado el 8 nov** (etiqueta git). |
| **F6** Piloto y línea base | 8 – 9 nov | Piloto de 5 casos; Config A × 3. | `results/`, `traces/` | Línea base medida desde trazas. |
| **F7** Experimento y seguridad | 9 – 11 nov | Config B × 3; 5 ataques de inyección; script de un comando. | `results/`, `security/` | Tablas regenerables desde trazas. |
| **F8** Demo de audio (mínima) | 12 nov | STT de un audio sintético hacia el agente; salida en texto. | `stt/` | Demo de extremo a extremo con una acción bloqueada por la política. |
| **F9** Artículo | 9 – 15 nov | Artículo completo (introducción, trabajo relacionado y metodología pueden escribirse desde el 5 nov). | `paper/` (PDF) | 6–8 páginas; resumen con cifra. |
| **F10** Cierre y entrega | 16 – 17 nov | Prueba en clon limpio, lista de comprobación, entrega; preparar defensa. | `README.md` final, `docs/defensa/` | Lista de comprobación completa; **entrega el 17 nov**. |

Como no hay holgura: si el 8 de noviembre no está congelado el conjunto de evaluación, se recorta el
STT (F8) antes que el experimento o el artículo.

### Reglas de trabajo

- Ninguna cifra en el artículo sin traza y script que la regeneren.
- El conjunto de evaluación se congela antes de ejecutar la Config B y no se modifica después.
- Ninguna entrada de vocabulario LESCO sin fuente verificable.
- Ninguna referencia sin haber sido abierta y leída; registro en `docs/referencias.md`.
- Revisión de datos personales antes de cada commit que incluya trazas o datos.
- Registro de uso de IA en `docs/uso_de_ia.md` desde la fase 0.

---

## 8. Decisiones registradas y preguntas abiertas

**Registradas (2026-10-31):**

- Equipo: proyecto individual, **autorizado por el profesor**.
- Segundo anotador: LLM, **autorizado por el profesor** → D10.
- Kit: `agente.py` y `leer_traza.py` recibidos; se copiarán al repositorio en F4.
- Léxico: el autor delega la búsqueda de la fuente → propuesta D9 (CENAREC). **No** se usará un LLM para generar vocabulario.
- Anotación: el autor propone usar un LLM como segundo anotador → D10, declarada como desviación.
- Plazo: unas dos semanas → D12 (luego precisado: entrega el 2026-11-17).
- Modelo: el autor delega la elección → D11 (Sonnet 5.5 para el agente, Opus 5.5 como anotador).
- Kit: el autor indica que es un ejemplo y que los archivos faltantes se construyan en el proyecto → D13.
- El autor dispone de una clave de la API → D14.

- D3, D5, D9 y D11: **aprobadas** por el autor.
- Entrega final: **2026-11-17**.

**Abiertas (no bloquean el inicio):**

1. Fecha de la defensa y si el H1/H2 tienen fecha propia o se evalúan con la entrega final.

## 9. Fuentes consultadas para D9 (pendientes de lectura completa)

Se encontraron en una búsqueda web el 2026-10-31. **Todavía no cuentan como referencias leídas.**

- Oviedo, A. y Ramírez Valerio, C. (2018). *The LESCO Corpus. Data for the Description of Costa Rican
  Sign Language*. LREC 2018, 8th Workshop on the Representation and Processing of Sign Languages,
  pp. 167–170. ELRA. <https://www.sign-lang.uni-hamburg.de/lrec/pub/18004.html>
- Ficha del LESCO Corpus (licencia CC BY-NC-SA, según la ficha):
  <https://www.sign-lang.uni-hamburg.de/lr/compendium/corpus/lescocorpus.html>
- Sitio del Diccionario LESCO / gramática (CENAREC): <https://lesco.cenarec.go.cr/>.
  No se encontró aviso de licencia en la portada. La URL alternativa
  `cenarec-lesco.org/DiccionarioLESCO.php` devolvió 404 el 2026-10-31.
