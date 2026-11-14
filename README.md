# lesco-agent

**LESCO-Agent: Diseño y evaluación de un agente inteligente basado en Skills y MCP para la generación
asistida de secuencias en Lengua de Señas Costarricense a partir de audio en español.**

Proyecto final del curso *Inteligencia Artificial Distribuida* — Maestría Profesional en Ingeniería del
Software con énfasis en IA Aplicada, Universidad CENFOTEC (2026).

> **Estado (2026-11-13):** el agente, el servidor MCP, la Skill, la política, las trazas, la evaluación y
> la reproducción están implementados y cubiertos por pruebas automatizadas (commit `e254f68`).
> **Todavía no hay resultados del experimento A/B con el modelo real.** Entrega final: 17 de noviembre de 2026.
> Ver [PLAN_PROYECTO.md](PLAN_PROYECTO.md) (§6 y §6.6) y [TODO.md](TODO.md).

## Problema

Las personas sordas usuarias de la Lengua de Señas Costarricense (LESCO) pueden enfrentar barreras de
acceso a información transmitida oralmente en entornos educativos, institucionales y de atención al
público, donde la disponibilidad de interpretación humana puede ser limitada.

LESCO-Agent explora si un agente basado en una Skill procedimental y un servidor MCP propio puede
proponer **secuencias candidatas** de señas tomadas de un vocabulario LESCO validado, a partir de
español hablado o escrito. **No es un traductor ni sustituye a intérpretes humanos.**

## Pregunta de investigación

¿En qué medida la incorporación de una Skill procedimental mejora la precisión en la selección de
secuencias de LESCO por parte de un agente inteligente, en comparación con el mismo agente sin dicha
Skill, y qué impacto tiene sobre el tiempo de procesamiento y el consumo de recursos?

## Arquitectura aprobada

1. **Entrada:** audio en español → transcripción (STT), normalización y segmentación.
2. **Agente:** modelo de lenguaje + `SKILL.md` + política de permisos.
3. **Servidor MCP propio:** `obtener_transcripcion`, `buscar_sena`, `validar_secuencia` y
   `guardar_resultado`, con validación del lado del servidor contra el vocabulario LESCO. Cada ejecución
   del agente arranca el servidor **vinculado a su caso** (`--caso`): solo entrega la transcripción y solo
   guarda el resultado de ese caso (decisión D18).
4. **Salida:** secuencia de señas con indicadores de incertidumbre y segmentos sin cobertura.
5. **Transversal:** una traza por ejecución (llamadas, decisiones, tokens, duración).

El vocabulario será un subconjunto del Diccionario LESCO del CENAREC, citado entrada por entrada.
El agente usará `claude-sonnet-5-5` a través de la API de Claude, como en el kit del curso.
El experimento se ejecuta sobre texto fijo; el reconocimiento de voz se usa en la demostración. El avatar 3D de la propuesta original se plantea como trabajo futuro. Detalles y justificación en
[PLAN_PROYECTO.md](PLAN_PROYECTO.md#6-arquitectura-mínima-viable-aprobada-d).

## Principios del proyecto

- Ningún vocabulario LESCO sin fuente verificable.
- Ninguna referencia bibliográfica sin haber sido leída.
- Toda cifra experimental se regenera desde las trazas del repositorio.
- Ningún dato personal real sin anonimizar.
- Uso de IA declarado.

## Estructura del repositorio

| Archivo | Contenido |
|---|---|
| `PLAN_PROYECTO.md` | Requisitos, cobertura, viabilidad, riesgos, arquitectura y fases. |
| `TODO.md` | Tareas pendientes por fase. |
| `docs/` | Propuesta H1, referencias, datos y ética, registro de uso de IA. |
| `data/lexicon/` | Índice del Diccionario LESCO del CENAREC (1104 entradas) y su procedencia. |
| `mcp_server/` | Servidor MCP propio: `obtener_transcripcion`, `buscar_sena`, `validar_secuencia`, `guardar_resultado`. |
| `agente/` | Agente (adaptado del kit de la clase 3), cliente MCP, configuraciones A/B/demo, ejecutor de casos y lector de trazas. |
| `skill/SKILL.md` | Skill procedimental (solo en la configuración B). |
| `politica/` | Políticas de permisos del experimento y de la demo, con su justificación. |
| `eval/` | Casos de evaluación, guía de anotación, tokenizador, kappa, construcción de la referencia y puntuación (`puntuar.py`). |
| `reproducir.py` | Comando único que regenera las tablas desde las trazas (falla cerrado si falta o es inconsistente alguna ejecución). |
| `evidencia/` | Registro de evidencia de pruebas (`registrar_pruebas.py`), su índice y los informes de las etapas de integridad. Los originales de cada registro están en `evidencia/privado/`, que **no se versiona**. |
| `tests/` | Pruebas automáticas. |

## Requisitos

Python 3.10 o superior. Sin dependencias externas.

## Pruebas

```bash
python -m unittest discover -s tests -v
```

Son pruebas locales, con el modelo **simulado** y datos sintéticos: **no usan la API**.

Para registrarlas como evidencia (salida original, metadatos y SHA-256, guardados en
`evidencia/privado/`), primero se registra una ejecución con una etiqueta nueva, en minúsculas:

```bash
python evidencia/registrar_pruebas.py registrar --suite completa --tipo ejecucion --etiqueta mi-etiqueta
```

Después se verifica el registro creado. La carpeta tiene la forma `AAAAMMDD-HHMMSS_mi-etiqueta`;
el registrador la indica al terminar:

```bash
python evidencia/registrar_pruebas.py verificar evidencia/privado/AAAAMMDD-HHMMSS_mi-etiqueta/original
```

## Servidor MCP

Uso por separado, sin vincular a un caso:

```bash
python mcp_server/servidor_lesco.py --salidas resultados/salidas
```

Vinculado a un caso (así lo arranca el agente):

```bash
python mcp_server/servidor_lesco.py --salidas resultados/salidas --casos eval/demo/casos_demo.jsonl --caso demo-001
```

Habla MCP por stdio (JSON-RPC 2.0, un mensaje por línea). El servidor valida cada argumento,
rechaza IDs que no existen en el diccionario y nunca sobrescribe un resultado guardado.

`--caso` es **opcional** en el servidor. Si se indica, exige `--casos` y que el caso exista en ese archivo.
Con un caso inválido o inexistente, el servidor no arranca. Vinculado, solo entrega la transcripción y
solo guarda el resultado de ese caso.

## Agente

Configure la clave de la API solo como variable de entorno (nunca en archivos del repositorio):

```bash
setx ANTHROPIC_API_KEY "sk-ant-api..."
```

Si la clave es de organización y no está asociada a un workspace (la API responde
*"not scoped to a workspace"*), configure también el ID del workspace:

```bash
setx ANTHROPIC_WORKSPACE_ID "wrkspc_..."
```

`--caso` es **obligatorio** en el agente: no hay caso implícito. Se valida el identificador completo
(1–40 caracteres: letras ASCII, dígitos, `_` o `-`, empezando por letra o dígito). El agente se niega a
ejecutar si la configuración no arranca el servidor con exactamente una pareja `--caso {caso}`.
`agente/configs/A.json`, `B.json` y `demo.json` ya la incluyen.

Las configuraciones A y B difieren en `instrucciones`, `nombre` y `descripcion`. La diferencia
experimental relevante es la Skill: B añade `skill/SKILL.md` a las instrucciones genéricas de A. El
resto (modelo, esfuerzo, política, límites y servidor) es igual en ambas.

Sin clave ni costo (modelo simulado, recorre el bucle completo y la política):

```bash
python agente/agente.py --config agente/configs/demo.json --simulado --caso demo-001
```

Con el modelo real (`claude-sonnet-5-5`):

```bash
python agente/agente.py --config agente/configs/B.json --caso demo-001 --casos eval/demo/casos_demo.jsonl
```

Corrida de varias configuraciones y repeticiones (reanudable):

```bash
python agente/ejecutar_casos.py --configs A B --repeticiones 3 --casos eval/casos.jsonl
```

Resumen de trazas:

```bash
python agente/leer_traza.py trazas/experimento/*/*/*.jsonl --csv resultados/metricas_trazas.csv
```

El comodín `*` lo expande bash. En PowerShell o cmd hay que pasar las rutas de las trazas
explícitamente.

## Reproducir los resultados

Un solo comando regenera todas las tablas desde las trazas y los resultados guardados, sin llamar
a la API (definiciones en [docs/metricas.md](docs/metricas.md)):

```bash
python reproducir.py
```

Escribe `resultados/tablas/experimento_filas.csv` y `resultados/tablas/experimento_resumen.md`.

Por defecto espera las configuraciones `A` y `B` con 3 repeticiones, los mismos valores que
`agente/ejecutar_casos.py`. Se pueden cambiar con `--configs` (una o más configuraciones) y
`--repeticiones` (un número entero, 1 o más). Por ejemplo:

```bash
python reproducir.py --configs A B --repeticiones 3
```

Antes de puntuar comprueba que existan todas las ejecuciones esperadas y que cada traza sea
documentalmente consistente con su resultado y su caso (decisión D19).

| Código de salida | Significado |
|---|---|
| 0 | Tablas generadas |
| 2 | Falta la referencia o las trazas del experimento |
| 3 | Alguna ejecución esperada falta o no es consistente; no se generan tablas ni puntuaciones parciales |

## Estado de las pruebas y de la evidencia

| Nivel | Estado |
|---|---|
| Pruebas automatizadas (modelo simulado o datos sintéticos) | **97/97** aprobadas en el registro E2-5 (`20261113-201818_suite-completa-e25`). Describen el comportamiento del código, no resultados científicos |
| Experimento A/B con el modelo real (A×3, B×3) y ataques de inyección | **Pendiente.** Requiere completar la anotación, el kappa, la adjudicación y el congelamiento del conjunto de evaluación |
| Afirmaciones sobre la efectividad de la Skill o la resistencia a la inyección | **Ninguna todavía** |

El commit `e254f68` corresponde al código registrado en E2-5. Se verificó comparando el SHA-256
normalizado a LF: 30 de 31 archivos de código coinciden, y la única diferencia es `.gitignore`,
modificado después del registro y que no se ejecuta.

Esta verificación demuestra consistencia documental. Git aporta trazabilidad de versiones, no una
autenticidad certificada por terceros.

Detalle en [evidencia/etapa1_servidor_mcp.md](evidencia/etapa1_servidor_mcp.md),
[evidencia/etapa2_agente.md](evidencia/etapa2_agente.md) y [evidencia/INDICE.md](evidencia/INDICE.md).

## Datos privados y publicación de evidencia

> **Advertencia:** no uses datos personales reales ni publiques evidencia sin revisión y autorización
> humana explícita.

No se versionan (están ignorados por git):

- `evidencia/privado/`, con los originales y las candidatas de cada registro;
- `Solicitud/`;
- los archivos del segundo anotador;
- `.env`.

Para publicar la evidencia de un registro, el orden es:

1. El autor revisa la candidata (`evidencia/privado/<registro>/candidata/`, incluido su `PUBLICACION.json`).
2. El autor decide y autoriza expresamente su publicación.
3. Solo después se ejecuta `registrar_pruebas.py aprobar`, que deja constancia de esa autorización.

`aprobar` **no** concede ni comprueba la autorización. Lo que hace es:

- comprobar que la candidata está íntegra y no contiene coincidencias sensibles;
- copiarla a `evidencia/pruebas/`;
- registrar en `evidencia/APROBACIONES.md` el texto de autorización que se le pasa.

Mientras no exista revisión y autorización humana explícita, la candidata permanece en estado
PENDIENTE_REVISION_HUMANA. La aprobación local y la publicación en GitHub son operaciones distintas.

La clave de la API va solo en una variable de entorno o en un `.env` local. Nunca en el código, las
configuraciones, las trazas ni la evidencia.

## Autoría

Elmer Mondragón Prieto (proyecto individual). Profesor: Jean Carlo Álvarez Ramírez.
