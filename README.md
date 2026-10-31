# lesco-agent

**LESCO-Agent: Diseño y evaluación de un agente inteligente basado en Skills y MCP para la generación
asistida de secuencias en Lengua de Señas Costarricense a partir de audio en español.**

Proyecto final del curso *Inteligencia Artificial Distribuida* — Maestría Profesional en Ingeniería del
Software con énfasis en IA Aplicada, Universidad CENFOTEC (2026).

> **Estado:** Plan aprobado (fase 0 cerrada). Entrega final: 17 de noviembre de 2026.
> Todavía no hay código, datos ni resultados.
> Ver [PLAN_PROYECTO.md](PLAN_PROYECTO.md) y [TODO.md](TODO.md).

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
3. **Servidor MCP propio:** `buscar_sena`, `validar_secuencia`, `guardar_resultado`, con validación
   del lado del servidor contra el vocabulario LESCO.
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
| `eval/` | Guía de la tarea y de anotación; casos de demostración. |
| `tests/` | Pruebas automáticas. |

## Requisitos

Python 3.10 o superior. Sin dependencias externas.

## Pruebas

```bash
python -m unittest discover -s tests -v
```

## Servidor MCP

```bash
python mcp_server/servidor_lesco.py --salidas resultados/salidas
```

Habla MCP por stdio (JSON-RPC 2.0, un mensaje por línea). El servidor valida cada argumento,
rechaza IDs que no existen en el diccionario y nunca sobrescribe un resultado guardado.

## Agente

Configure la clave de la API solo como variable de entorno (nunca en archivos del repositorio):

```bash
setx ANTHROPIC_API_KEY "sk-ant-api..."
```

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

*El comando único que regenera las tablas del artículo se documentará con el experimento.*

## Autoría

Elmer Mondragón Prieto (proyecto individual). Profesor: Jean Carlo Álvarez Ramírez.
