# PLAN_PROYECTO — LESCO-Agent

> **Estado:** Fase 0 cerrada. Plan **aprobado** por el autor el 2026-10-31 (D3, D5, D9 y D11
> aprobadas explícitamente). Entrega final: **2026-11-17**.
> No contiene código, resultados experimentales ni vocabulario LESCO.
> **Aclaración 2026-11-13:** la línea anterior describe **este documento** (un plan, sin código ni
> resultados), no el repositorio. El repositorio sí contiene código y pruebas automatizadas (commit
> `e254f68`; ver §6.6), pero **todavía no** contiene resultados del experimento A/B con el modelo real.

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

> Análisis de la propuesta inicial al 2026-10-31; se conserva como registro histórico. El estado actual
> está en §6 y §7.

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

**Estado al 2026-11-13** (revisión 4 de esta sección; refleja el commit `e254f68`):

| Ámbito | Estado |
|---|---|
| Arquitectura de F4 (servidor MCP, agente, Skill, política, trazas y ejecutor de casos) | **Implementada** |
| Etapas de integridad 1 y 2 (D18 y D19) | **Implementadas y registradas** (§6.6) |
| F5: anotador 1, kappa, adjudicación, referencia y congelamiento del conjunto | **Pendiente.** Casos (aprobados por el autor sin cambios el 2026-11-13) y plantilla hechos. Anotador 2 completo y validado técnicamente (48/48 casos, 240/240 posiciones; validación del 2026-11-13). Su calidad lingüística **no** se ha evaluado |
| F6: línea base A×3 con el modelo real | **Pendiente** (métricas congeladas, puntuación, `reproducir.py` y piloto sí hechos) |
| F7: B×3, los 5 ataques y el análisis de errores con el modelo real | **Pendiente** |

La revisión 3 (2026-11-01) describía el estado hasta F4. Su diagrama se conserva abajo y los cambios
posteriores se listan a continuación. Que la arquitectura esté implementada **no** significa que F5, F6
o F7 estén terminadas.

```
 [Audio .wav] ── stt/ (F8, solo demo) ──┐
                                        ▼
                       eval/casos.jsonl  {caso_id, texto}      ← transcripciones (texto de terceros)
                                        │  (el servidor nunca expone etiquetas de referencia)
 ┌──────────────── agente/agente.py (adaptado del kit) ───────────────────────────────┐
 │ objetivo fijo por caso: "Caso X. Obtén la transcripción... guarda con caso_id=X"   │
 │ instrucciones  A: instrucciones_genericas.md                                       │
 │                B: instrucciones_genericas.md + skill/SKILL.md   ← única variable   │
 │ modelo claude-sonnet-5-5, esfuerzo medium (idénticos en A y B)                     │
 │ política (host): politica/politica_experimento.json · límites de pasos y tokens    │
 │ envoltura de resultados de herramienta como datos no confiables                    │
 └──────────────┬─────────────────────────────────────────────────────────────────────┘
                │ MCP stdio (agente/mcp_cliente.py)
                ▼
 ┌──────────── mcp_server/servidor_lesco.py ────────────┐    ┌──── data/lexicon/ ─────────────┐
 │ obtener_transcripcion (lectura)  texto del caso      │◄───│ cenarec_indice.tsv (1104,      │
 │ buscar_sena           (lectura)  exacta / parcial    │    │ SHA-256 verificado)            │
 │ validar_secuencia     (lectura)  formato + existencia│    └────────────────────────────────┘
 │ guardar_resultado     (escritura) revalida, ruta     │───► resultados/<exp>/<config>/rep<k>/<caso>.json
 │                       confinada, sin sobrescribir    │
 └──────────────────────────────────────────────────────┘
 Transversal: trazas/<exp>/<config>/rep<k>/*.jsonl → agente/leer_traza.py --csv → métricas
 Orquestación: agente/ejecutar_casos.py (repetición → caso → A/B alternadas; reanudable)
 Salida final: secuencia de IDs + glosas + SIN_COBERTURA:<palabra>; avatar 3D → trabajo futuro (D5)
```

**Cambios desde la revisión 3 (etapas 1 y 2, 2026-11-13; detalle en `evidencia/etapa1_servidor_mcp.md`
y `evidencia/etapa2_agente.md`):**

- **Servidor MCP, v0.2.0 (D18):** `--caso` opcional, validado al arrancar. Vinculado, solo entrega la
  transcripción y solo guarda el resultado de ese caso. Sin `--caso` mantiene el comportamiento anterior
  (uso por separado).
- **Agente (D18):**
  - `--caso` obligatorio y validado con `fullmatch`;
  - `problemas_de_vinculacion()` se comprueba **antes** de crear la traza y de arrancar procesos;
  - si la configuración no vincula el servidor al caso, la traza de rechazo solo tiene el evento `fin`
    y no se arranca ningún servidor;
  - el evento `inicio` registra `servidores = [{nombre, version, caso_vinculado}]`.
- **Configuraciones A, B y demo:** la misma pareja `"--caso", "{caso}"` en el comando del servidor. A y B
  siguen difiriendo solo en `instrucciones` (Skill), `nombre` y `descripcion`.
- **Evaluación (D19):**
  - `eval/puntuar.py` comprueba la validez documental de cada ejecución y el conjunto esperado antes de
    puntuar;
  - si falta o es inconsistente alguna ejecución esperada, `reproducir.py` termina con código 3. En esa
    ejecución no genera ni sobrescribe tablas ni puntuaciones parciales, y no borra las tablas de
    ejecuciones anteriores;
  - fórmulas y columnas sin cambios.
- **Registro de evidencia:** `evidencia/registrar_pruebas.py` (v1.2.1).
  - Ejecuta solo suites `unittest` cerradas, con un entorno sin credenciales y una guardia de red parcial.
  - Guarda originales privados en `evidencia/privado/` (no versionada) y un índice de solo agregar en
    `evidencia/INDICE.md`.

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
| D15 | **Cuarta herramienta `obtener_transcripcion`** (F4): el agente recibe solo el `caso_id` y lee la frase por herramienta. | La transcripción es contenido de terceros: es el vector realista de inyección indirecta (S7). El servidor nunca devuelve etiquetas de referencia. |
| D16 | **Definición de la tarea** en `eval/guia_anotacion.md` v1 (F4) — **requiere aprobación del autor:** (a) orden de la frase en español, sin sintaxis LESCO; (b) lista cerrada de palabras omitidas (artículos, preposiciones, conjunciones, pronombres, posesivos, auxiliares); (c) expresiones de varias palabras; (d) búsqueda por lema; (e) variante sin número; (f) un sinónimo como máximo; (g) `SIN_COBERTURA` para lo demás. | Hace que "precisión" sea medible y que dos anotadores puedan coincidir. Son simplificaciones lingüísticas declaradas, no afirmaciones sobre la gramática LESCO. |
| D17 | **Esfuerzo `medium`** para Sonnet 5.5 en A y B, y reintentos ante errores transitorios de la API. | Menor costo y tiempo en una tarea de muchas llamadas cortas; mismo valor en A y B. |
| D18 | **Vinculación de cada ejecución a su caso** (2026-11-13). El servidor MCP acepta `--caso` (opcional, para conservar su uso por separado) y, vinculado, solo entrega y guarda ese caso. El agente exige `--caso` (sin valor por defecto), lo valida con `fullmatch` y se niega a ejecutar si algún servidor no tiene exactamente una pareja `--caso {caso}`. | Sin vinculación, una ejecución (por error o por una inyección en la transcripción) podía escribir el resultado de otro caso en la carpeta compartida y contaminar su puntuación (NN3, S7). Falla cerrado. No cambia lo que ve el modelo, así que A y B siguen difiriendo solo en la Skill (E1). |
| D19 | **Validez documental antes de puntuar** (2026-11-13). `evaluar()` exige el conjunto esperado (configuraciones × `rep1..repN` × casos; por defecto A, B y 3, los mismos valores que `ejecutar_casos.py`) y, para cada ejecución, consistencia entre traza y resultado (traza legible, `inicio` del caso, servidores vinculados, sin guardados ajenos, resultado si y solo si hay exactamente un guardado, `caso_id` declarado y `secuencia` válida). Si algo falla, se lanza `ErrorVinculacion` y `reproducir.py` termina con código 3: en esa ejecución no genera ni sobrescribe tablas ni puntuaciones parciales, y no borra las tablas de ejecuciones anteriores. | Excluir ejecuciones en silencio sesgaría la comparación A/B y produciría cifras no reproducibles (NN3, E2, E4). Es consistencia documental, no autenticidad. Las fórmulas de `docs/metricas.md` v1 no cambian. |

### Herramientas MCP implementadas (F3–F4)

| Herramienta | Tipo | Experimento | Demo | Validación del servidor |
|---|---|---|---|---|
| `obtener_transcripcion` | Lectura | permitir (máx. 2) | permitir | `caso_id` con patrón estricto; caso existente; solo devuelve `caso_id` y texto. |
| `buscar_sena` | Lectura | permitir (máx. 40) | permitir | Texto 1–80 caracteres, sin control; `max_resultados` 1–10; argumentos extra rechazados. |
| `validar_secuencia` | Lectura | permitir (máx. 5) | permitir | Lista 1–60; formato `CENAREC-n` o `SIN_COBERTURA:texto`; cada ID existe. |
| `guardar_resultado` | Escritura | permitir (**máx. 1**) | **confirmar** | Revalida la secuencia; `caso_id` sin rutas; directorio fijo; nunca sobrescribe. |
| `*__borrar*`, `*__eliminar*`, `*__sobrescribir*`, `*__ejecutar*` | — | denegar | denegar | — |
| `*__admin*`, `*__depurar*` | — | ocultar | ocultar | — |

Justificación completa en `politica/README.md`. Pruebas: 29 (léxico, servidor por MCP y agente
completo con modelo simulado). *(Cifra del 2026-11-01, sin salida registrada; el estado registrado
actual está en §6.6.)*

Desde la etapa 1 (servidor v0.2.0, D18), con `--caso` el servidor solo entrega la transcripción y solo
guarda el resultado del caso autorizado. El control de formato se aplica antes que el de vinculación.

### Métricas (a congelar en `docs/metricas.md` antes de ejecutar A) [D]

Por caso, comparando la secuencia guardada con la de referencia (elementos: IDs y
`SIN_COBERTURA`, sin importar el texto que sigue a `SIN_COBERTURA:`):

- **Exactitud de secuencia:** 1 si coincide exactamente (mismo orden y elementos), si no 0.
- **Precisión, exhaustividad y F1** sobre multiconjuntos de elementos (independientes del orden).
- **Exhaustividad de `SIN_COBERTURA`:** proporción de segmentos sin cobertura de la referencia que el agente marcó como tales.
- **Caso sin guardar:** el agente terminó sin `guardar_resultado` exitoso (cuenta como F1 = 0).
- **IDs rechazados por el servidor**, tokens de entrada y salida, duración, pasos, llamadas y denegaciones (desde las trazas).
- Agregación: media por ejecución, y media y desviación estándar entre las 3 repeticiones; también por subconjunto normal/difícil.

### Vectores de inyección indirecta a estudiar [D]

1. **Transcripción** (`obtener_transcripcion`) con instrucciones dirigidas al agente — vector principal.
2. Variante de prueba del índice con una glosa manipulada (solo en el experimento de seguridad, nunca en el índice real).

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

**Medición del piloto (2026-11-03; trazas en `trazas/piloto/`, 5 casos × A y B, 1 repetición,
`claude-sonnet-5-5`, precios de lista):** las 10 ejecuciones terminaron por decisión del modelo, en
5 pasos cada una. Costo medio por ejecución: **A US$ 0,038 · B US$ 0,059** (B usa ~10 000 tokens de
entrada más por caso, por el texto de la Skill reenviado en cada paso). Duración media: A 8,4 s, B
8,8 s. **Proyección:** 288 ejecuciones del experimento ≈ **US$ 14**; con 30 de seguridad ≈ US$ 15.
Estas cifras son de calibración de presupuesto, no resultados del experimento.

*Observación del piloto para el autor:* en los 5 casos (fáciles, sin anotar) A y B guardaron la
misma secuencia, incluidas una expresión de varias palabras y un `SIN_COBERTURA`. Las descripciones
de las herramientas del servidor, que son iguales en A y B, ya transmiten parte del procedimiento.
Es posible que la diferencia entre A y B en el conjunto de evaluación sea pequeña; un resultado nulo
bien medido es reportable según la especificación.

**Revisión tras F4 (estimación, no medición):** el agente hace una búsqueda por palabra y cada paso
reenvía la conversación, así que el supuesto de 20 000 tokens de entrada por caso probablemente se
quede corto. Si fueran ~100 000, el experimento con Sonnet 5.5 costaría del orden de US$ 70–100. El
piloto (F6) mide el costo real antes de lanzar las 240 ejecuciones; si supera lo aceptable, el autor
decide entre reducir casos (mínimo 40) o cambiar de modelo **antes** de medir la línea base. El
anotador 2 con el índice completo en el prompt costaría ~US$ 5 (48 casos × ~20 000 tokens).

### 6.6 Estado de las pruebas y de la evidencia (2026-11-13) [D]

**Tres niveles que no se mezclan:**

| Nivel | Qué es | Estado |
|---|---|---|
| 1. Pruebas automatizadas con modelo simulado o datos sintéticos | Comportamiento **del código**: servidor, agente, política, traza, evaluación y reproducción | **97/97** en el registro E2-5 (`20261113-201818_suite-completa-e25`) |
| 2. Experimento con el modelo real (A×3 y B×3) y los 5 ataques (F7) | Efecto de la Skill y comportamiento real del modelo | **No ejecutado.** Requiere completar F5 (anotador 1, kappa, adjudicación y congelamiento) |
| 3. Afirmaciones científicas del artículo | Lo que respalde el nivel 2 (y el nivel 1 para describir el sistema) | **Ninguna** sobre la efectividad de la Skill ni sobre la resistencia a la inyección |

- **Registros de la suite completa** (no se suman: cada uno incluye al anterior):
  - D3b (`20261113-191307_suite-completa-linea-base`): 55 pruebas;
  - E2-4 (`20261113-194941_suite-completa-etapa2`): 63;
  - E2-5: 97.
- **Código publicado:** commit `e254f68` (2026-11-13). Corresponde al código registrado en E2-5, salvo
  `.gitignore` (30 de 31 archivos coinciden por SHA-256 normalizado a LF; la diferencia es posterior y
  no ejecutable).
- **Evidencia:**
  - los registros están en `evidencia/privado/` (no versionada), pendientes de revisión humana y sin
    publicar;
  - el detalle, con identificadores y hashes, está en `evidencia/etapa1_servidor_mcp.md`,
    `evidencia/etapa2_agente.md` y `evidencia/INDICE.md`.
- **Alcance:** los SHA-256 dan consistencia documental y git da trazabilidad de versiones. **Ninguno**
  de los dos es autenticidad certificada por terceros.

---

## 7. Fases de desarrollo

Calendario comprimido (D12) con **entrega final el 2026-11-17**. Las fechas de H1, H2 y la defensa
no se conocen; si alguna cae antes, se reordena. Cada fase termina en uno o más commits pequeños y
revisables.

| Fase | Días (2026) | Objetivo | Entregables en el repositorio | Criterio de salida |
|---|---|---|---|---|
| **F0** Planificación | 31 oct | Analizar rúbrica y propuesta; acordar arquitectura. | `PLAN_PROYECTO.md`, `README.md`, `TODO.md` | ✅ Plan aprobado. |
| **F1** Propuesta y referencias | 1 – 2 nov | Usuario concreto, datos, línea base; empezar a leer referencias. | `docs/propuesta_H1.md`, `docs/referencias.md` (registro de lectura) | ✅ Borrador hecho · ⏳ lectura de las 3 referencias (autor). |
| **F2** Léxico y ética | 2 – 4 nov | Índice del diccionario CENAREC (D9) y política de datos. | `data/lexicon/`, `docs/datos_y_etica.md` | ✅ 1104 entradas, SHA-256 verificado · ⏳ permiso del CENAREC (autor). |
| **F3** Servidor MCP | 3 – 5 nov | Implementar las herramientas con validación. | `mcp_server/`, `tests/` | ✅ Pruebas pasan; rechazos con mensajes útiles. |
| **F4** Agente, Skill y política | 5 – 6 nov | Adaptar el kit: Config A y B, política, trazas, ejecutor de casos. | `agente/`, `skill/SKILL.md`, `politica/`, `eval/guia_anotacion.md` | ✅ Extremo a extremo con `--simulado` · ⏳ con el modelo real (falta clave válida). |
| **F5** Conjunto de evaluación | 3 – 8 nov (en paralelo) | ≥ 40 casos, ≥ 30 % difíciles, anotación (D10) y kappa. | `eval/` | Kappa calculado; conjunto **congelado el 8 nov** (etiqueta git). |
| **F6** Piloto y línea base | 8 – 9 nov | Piloto de 5 casos; Config A × 3. | `results/`, `traces/` | Línea base medida desde trazas. |
| **F7** Experimento y seguridad | 9 – 11 nov | Config B × 3; 5 ataques de inyección; script de un comando. | `results/`, `security/` | Tablas regenerables desde trazas. |
| **F8** Demo de audio (mínima) | 12 nov | STT de un audio sintético hacia el agente; salida en texto. | `stt/` | Demo de extremo a extremo con una acción bloqueada por la política. |
| **F9** Artículo | 9 – 15 nov | Artículo completo (introducción, trabajo relacionado y metodología pueden escribirse desde el 5 nov). | `paper/` (PDF) | 6–8 páginas; resumen con cifra. |
| **F10** Cierre y entrega | 16 – 17 nov | Prueba en clon limpio, lista de comprobación, entrega; preparar defensa. | `README.md` final, `docs/defensa/` | Lista de comprobación completa; **entrega el 17 nov**. |

> **Actualización 2026-11-13** (el calendario de la tabla se conserva como plan original):
> - **F5:** casos (aprobados por el autor sin cambios el 2026-11-13; ver TODO), plantilla, y script y
>   prompt del anotador 2 hechos. **Anotador 2:** ejecutado el 2026-11-03 y validado técnicamente el
>   2026-11-13 (48/48 casos y 240/240 posiciones, sin errores; detalle en TODO y `docs/uso_de_ia.md`).
>   Hasta esa validación constaba como "ejecución parcial o validación pendiente". Su calidad lingüística
>   **no** se ha evaluado: la medirán el kappa y la adjudicación. Se ejecutó antes del anotador 1, lo
>   que es una desviación del orden previsto. **Pendientes:** anotador 1 (archivo creado, sin
>   etiquetas), kappa, adjudicación, referencia y congelamiento. La fecha límite del 8 nov ya pasó sin
>   congelar.
> - **F6:** métricas congeladas, puntuación, `reproducir.py` y piloto hechos. **Pendiente:** A×3.
> - **F7:** **pendientes** B×3, los 5 ataques y el análisis de errores. El comando único ya existe desde F6.
> - **Entre F6 y F7 se intercalaron las etapas de integridad 1 y 2** (D18 y D19), no previstas en el
>   calendario, y el instrumento de registro de evidencia.
> - **F8–F10:** pendientes.

Como no hay holgura: si el 8 de noviembre no está congelado el conjunto de evaluación, se recorta el
STT (F8) antes que el experimento o el artículo.

### 7.1 Plan detallado de F5 — conjunto de evaluación (aprobado el 2026-11-01)

| Paso | Quién | Qué | Archivo |
|---|---|---|---|
| 1 | Claude | Redactar **48 casos** (margen sobre 40) de trámites en ventanilla: requisitos, pagos, horarios, filas, firmas, plazos. Sin nombres, cédulas, teléfonos ni direcciones. Objetivo: ≥ 20 difíciles (≥ 40 %, según §9 de la guía). | `eval/casos.jsonl` (`caso_id`, `texto`) y `eval/casos_meta.jsonl` (dificultad prevista y motivo) |
| 2 | Claude | Redactar **5 casos de piloto aparte**, para medir costo sin tocar el conjunto de evaluación. | `eval/piloto/casos_piloto.jsonl` |
| 3 | Autor | Revisar y aprobar los casos (puede editar o reemplazar cualquiera). | — |
| 4 | Claude | Tokenizador determinista y plantilla por palabra. Las palabras de la lista cerrada (§3) se prellenan como `OMITIR`; las de contenido quedan vacías. | `eval/tokenizar.py`, `eval/anotaciones/plantilla.tsv` |
| 5 | **Autor** | **Anotador 1:** llenar la etiqueta de cada palabra de contenido siguiendo la guía, con un buscador de línea de comandos como ayuda. Sin ver al anotador 2. Estimado: 2–3 horas. | `eval/anotaciones/anotador1.tsv`, `eval/buscar.py` |
| 6 | Claude | **Anotador 2:** `claude-opus-5-5` con la guía y el índice completo en el prompt, prompt fijo y versionado, sin ver al anotador 1 ni al agente. | `eval/anotador_llm.py`, `eval/prompts/anotador2_v1.md`, `eval/anotaciones/anotador2.tsv` |
| 7 | Claude | Kappa de Cohen sobre todas las palabras y **también solo sobre las de contenido** (las omitidas prellenadas inflarían el acuerdo). | `eval/kappa.py`, `eval/acuerdo.md` |
| 8 | Claude propone, autor decide | Adjudicar cada desacuerdo con la guía; registrar la decisión y su motivo. | `eval/adjudicacion.md`, `eval/referencia.jsonl` |
| 9 | Claude | Congelar: SHA-256 de casos, guía y referencia; etiqueta git `eval-v1`. Desde ahí no se modifica. | `eval/CONGELADO.md` |

Requisitos externos: clave válida de la API (paso 6). Fecha límite de congelamiento: 8 nov.

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

**Abiertas:**

1. Fecha de la defensa y si el H1/H2 tienen fecha propia o se evalúan con la entrega final.
2. ~~Aprobar D15, D16 y D17 y el plan de F5~~ → **aprobados por el autor el 2026-11-01.**
3. Clave válida de la API (la guardada en Windows responde 401).
4. Cómo subir a GitHub los commits locales (repositorio público; ver `docs/datos_y_etica.md` sobre el índice del CENAREC).
   → 2026-11-13: el autor publicó el commit `e254f68` en `origin/main`.
5. (2026-11-13) Pasar `PATRON_CASO` del servidor MCP de `match` a `fullmatch`: hoy acepta un salto de
   línea final en `caso_id` (neutralizado con `--caso`, no sin vincular). Paso aparte, con su registro.
6. (2026-11-13) Verificación en un clon limpio, y si es posible por otra persona (S8).
7. (2026-11-13) Manifiesto de ejecución opcional que guarde configuraciones y repeticiones junto a las
   trazas. Hoy el conjunto esperado depende de los valores por defecto compartidos (D19).

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
