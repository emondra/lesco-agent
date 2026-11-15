# lesco-agent

**LESCO-Agent:** un agente basado en un modelo de lenguaje que, a partir de una frase en español,
propone una **secuencia candidata** de entradas del Diccionario LESCO del CENAREC (Lengua de Señas
Costarricense). Usa herramientas expuestas con el Model Context Protocol (MCP), una Skill
procedimental opcional y una política de permisos aplicada por el host, y deja una traza completa de
cada ejecución.

> **No es un traductor a LESCO ni sustituye a intérpretes humanos.** Propone entradas de un diccionario
> en el orden del español; no modela la gramática de LESCO ni sus rasgos no manuales.

Este repositorio contiene **solo la implementación técnica**: el agente, el servidor MCP, la Skill,
las políticas, la evaluación, las pruebas, los datos sintéticos y la evidencia de ejecución. Los
documentos académicos del proyecto se entregan aparte y no forman parte del repositorio.

## Arquitectura

```
 caso (frase en español)        Skill (solo config. B)
          │                            │ procedimiento
          ▼                            ▼
 ┌──────────────────── host (código) ─────────────────────┐
 │  Agente (agente/agente.py) ◄──► Política y vinculación │──► trazas JSONL (una por ejecución)
 └───────────────────────────────────┬────────────────────┘
                                     │ llamadas permitidas (MCP, stdio)
                                     ▼
              Servidor MCP (mcp_server/servidor_lesco.py) ──► índice CENAREC (1104 entradas)
```

1. **Entrada:** una frase en español (texto) asociada a un caso.
2. **Agente:** `claude-sonnet-5-5` por la API de Claude, con `SKILL.md` solo en la configuración B.
3. **Servidor MCP propio:** `obtener_transcripcion`, `buscar_sena`, `validar_secuencia` y
   `guardar_resultado`, con validación del lado del servidor contra el vocabulario. Cada ejecución
   arranca el servidor **vinculado a su caso** (`--caso`): solo entrega la transcripción y solo guarda
   el resultado de ese caso (D18).
4. **Salida:** la secuencia validada, con `SIN_COBERTURA` donde no hay entrada.
5. **Transversal:** una traza por ejecución (llamadas, decisiones de política, tokens y duración).

**Qué decide cada parte:** la Skill decide el *procedimiento* (qué omitir, buscar por el lema, cuándo
aceptar una coincidencia, el orden y cuándo usar `SIN_COBERTURA`). El código impone los *límites*,
independientemente del modelo: la política (permitir, denegar u ocultar herramientas; como máximo 1
escritura), la envoltura de los resultados de herramientas como datos no confiables, la validación de
cada ID, la vinculación al caso (D18) y la validez documental de cada traza antes de puntuarla (D19).

El sistema trabaja sobre texto: el reconocimiento de voz no está implementado.

## Estructura del repositorio

| Ruta | Contenido |
|---|---|
| `agente/` | Agente, cliente MCP, configuraciones A/B/demo, ejecutor de casos, ejecutor supervisado sin reintentos y lector de trazas |
| `mcp_server/` | Servidor MCP propio y carga del índice |
| `skill/SKILL.md` | Skill procedimental (solo en la configuración B) |
| `politica/` | Políticas de permisos del experimento y de la demo, con su justificación |
| `data/lexicon/` | Índice del Diccionario LESCO del CENAREC (1104 entradas) y su procedencia |
| `eval/` | Casos sintéticos, guía de anotación, plantilla, prompts de los anotadores LLM, tokenizador, kappa, construcción de referencias, puntuación, especificación y evaluador de ataques, y exclusiones del análisis |
| `reproducir.py` | Regenera las tablas de métricas desde las trazas (falla cerrado si falta o es inconsistente alguna ejecución) |
| `reproduccion/` | Prueba de reproducción en un clon limpio |
| `trazas/`, `resultados/` | Evidencia de ejecución: piloto, experimento A/B (`experimento/`) y ataques de inyección (`ataques/`), con los manifiestos `supervisor.jsonl` |
| `evidencia/` | Registrador de evidencia de pruebas y los informes técnicos de integridad |
| `docs/metricas.md` | Definición de las métricas, congeladas antes de medir |
| `docs/datos_y_etica.md` | Procedencia de los datos y uso del vocabulario |
| `tests/` | Pruebas automatizadas |

## Requisitos e instalación

- Python 3.10 o superior. Sin dependencias externas: el agente usa la API por HTTP con la biblioteca
  estándar.

```bash
git clone https://github.com/emondra/lesco-agent.git
cd lesco-agent
python -m unittest discover -s tests
```

## Configuración del entorno

Solo hace falta para ejecutar el agente o los anotadores con el modelo real, que tiene costo. Las
pruebas, la demo simulada, el evaluador de ataques y la puntuación **no** necesitan clave.

La clave va en la variable de entorno `ANTHROPIC_API_KEY` o en un archivo `.env` local en la raíz
(ignorado por git), nunca en el código, las configuraciones ni las trazas:

```bash
setx ANTHROPIC_API_KEY "sk-ant-api..."
```

Si la clave es de organización y no está asociada a un workspace (la API responde *"not scoped to a
workspace"*), configure también `ANTHROPIC_WORKSPACE_ID`.

## Pruebas

```bash
python -m unittest discover -s tests -v
```

Son pruebas locales con el modelo **simulado** y datos sintéticos: **no usan la API**. Para registrarlas
como evidencia (salida original, metadatos y SHA-256, en `evidencia/privado/`, que no se versiona):

```bash
python evidencia/registrar_pruebas.py registrar --suite completa --tipo ejecucion --etiqueta mi-etiqueta
python evidencia/registrar_pruebas.py verificar evidencia/privado/AAAAMMDD-HHMMSS_mi-etiqueta/original
```

## Servidor MCP

```bash
python mcp_server/servidor_lesco.py --salidas resultados/salidas                       # sin vincular
python mcp_server/servidor_lesco.py --salidas resultados/salidas --casos eval/demo/casos_demo.jsonl --caso demo-001
```

Habla MCP por stdio (JSON-RPC 2.0, un mensaje por línea). Valida cada argumento, rechaza IDs que no
existen en el diccionario y nunca sobrescribe un resultado guardado. Con un caso inválido o
inexistente, no arranca.

## Agente

`--caso` es **obligatorio**: no hay caso implícito. Se valida el identificador completo (1–40
caracteres: letras ASCII, dígitos, `_` o `-`). El agente se niega a ejecutar si la configuración no
arranca el servidor con exactamente una pareja `--caso {caso}`.

Las configuraciones A y B solo difieren en las instrucciones: B añade `skill/SKILL.md` a las
instrucciones genéricas de A. El modelo, el esfuerzo, la política, los límites y el servidor son
iguales.

**Agente simulado (sin clave ni costo):** recorre el bucle completo, la política y el servidor MCP con
un guion fijo.

```bash
python agente/agente.py --config agente/configs/demo.json --simulado --caso demo-001 --salidas resultados/demo_defensa/salidas --trazas resultados/demo_defensa/trazas
python agente/leer_traza.py resultados/demo_defensa/trazas/*.jsonl
```

Con la política de la demo, la escritura requiere aprobación humana: al responder `s`, la primera se
guarda y la segunda la deniega la política (máximo 1). Sin terminal interactiva o sin respuesta, la
escritura se deniega. **La evidencia de lo ocurrido es la traza y el archivo guardado**, no el mensaje
final del modelo simulado, que es fijo. Use carpetas nuevas: el servidor nunca sobrescribe.

**Con el modelo real** (con costo):

```bash
python agente/agente.py --config agente/configs/B.json --caso demo-001 --casos eval/demo/casos_demo.jsonl
python agente/ejecutar_supervisado.py --tope-usd <T> --max-corridas 30        # experimento A/B, sin reintentos
```

El comodín `*` lo expande bash; en PowerShell hay que pasar las rutas explícitamente, por ejemplo
`(Get-ChildItem resultados\demo_defensa\trazas\*.jsonl).FullName`. La carpeta `resultados/demo_defensa/`
está ignorada por git.

## Evaluación

Todo lo siguiente se ejecuta **sin la API**. Las definiciones están en
[docs/metricas.md](docs/metricas.md).

**Ataques de inyección indirecta**, desde las trazas publicadas:

```bash
python eval/evaluar_ataques.py --salida resultados/ataques/resumen.md
```

Lee `eval/ataques/ataques.json` (criterios fijados antes de ejecutar) y las trazas de
`trazas/ataques/`, y calcula por ataque y configuración el éxito del atacante, los intentos del
modelo, las denegaciones, los rechazos, la validez de la traza, la tarea legítima, la negativa del
modelo y la contaminación de la salida.

**Métricas del experimento A/B:**

```bash
python reproducir.py --experimento experimento --referencia <referencia.jsonl> --salida <carpeta>
```

Antes de puntuar, comprueba que existan todas las ejecuciones esperadas (por defecto, A y B con 3
repeticiones) y que cada traza sea documentalmente consistente con su resultado y su caso (D19). La
traza de un fallo de autenticación previo al experimento se excluye por ruta y SHA-256
(`eval/exclusiones_experimento.json`).

| Código de salida | Significado |
|---|---|
| 0 | Tablas generadas |
| 2 | Falta la referencia o las trazas del experimento |
| 3 | Alguna ejecución esperada falta o no es consistente; no se generan tablas ni puntuaciones parciales |

Las referencias se construyen con `eval/construir_referencia.py` (modos `unico` y `consenso`) a
partir de anotaciones con el formato de `eval/anotaciones/plantilla.tsv`, y la concordancia entre
anotadores se mide con `eval/kappa.py`.

## Reproducibilidad: qué se puede regenerar desde este repositorio

| Resultado | Desde este repositorio |
|---|---|
| Comportamiento del código (pruebas) | Sí |
| Evaluación de los ataques de inyección | Sí, desde `trazas/ataques/` |
| Métricas de proceso por corrida (tokens, duración, pasos, llamadas) | Sí, desde las trazas (`agente/leer_traza.py`) |
| Métricas de calidad (F1, exacta, IC 95 %) y kappa | **No**: requieren las anotaciones y las referencias, que no se publican |

**Limitación:** las anotaciones de los dos anotadores LLM y las referencias derivadas **no se
publican**. Sin ellas, `reproducir.py` termina con el código 2. La evidencia completa necesaria para
regenerar las métricas de calidad se entrega por separado, en un paquete académico de reproducción,
junto con la documentación académica del proyecto.

**Prueba en un clon limpio** (sin la API; copia solo los archivos no ignorados a una carpeta nueva):

```bash
python reproduccion/prueba_clon_limpio.py <carpeta_nueva> [--paquete <paquete_de_reproduccion>]
```

Sin paquete, comprueba la suite de pruebas, la evaluación de los ataques y que `reproducir.py` se
niegue a puntuar sin referencia. Con paquete, también el kappa, la reconstrucción de las referencias y
las tablas de calidad.

Volver a ejecutar el agente o los anotadores requiere la API, tiene costo y no es determinista.

## Datos y privacidad

- Los casos son **sintéticos** y no contienen datos personales.
- El vocabulario es un índice de entradas del Diccionario LESCO del CENAREC, citado entrada por entrada
  ([data/lexicon/FUENTE.md](data/lexicon/FUENTE.md)).
- **No se versionan:** `.env`; `evidencia/privado/`; las anotaciones de los anotadores
  (`eval/anotaciones/anotador*`); las referencias derivadas (`eval/referencias/`) y los desacuerdos
  (`eval/desacuerdos.tsv`); la traza del fallo de autenticación previo al experimento; y los
  documentos académicos del proyecto.
- La evidencia de `trazas/experimento/`, `resultados/experimento/`, `trazas/ataques/` y
  `resultados/ataques/` se versiona **byte a byte** (`.gitattributes`), para que sus SHA-256 coincidan
  en cualquier sistema.

Para publicar un registro de evidencia de pruebas: el autor revisa la candidata
(`evidencia/privado/<registro>/candidata/`), decide y autoriza expresamente su publicación, y solo
después se ejecuta `registrar_pruebas.py aprobar`. Este comando no concede ni comprueba la
autorización; deja constancia del texto que se le pasa.

## Estado

| Nivel | Estado |
|---|---|
| Pruebas automatizadas (modelo simulado o datos sintéticos) | 189/189 aprobadas (2026-11-14). Describen el comportamiento del código, no resultados científicos |
| Experimento A/B con el modelo real (48 casos × A/B × 3) | 288/288 corridas válidas según D18/D19 (2026-11-14) |
| Ataques de inyección indirecta | 6 ataques × A/B, 1 repetición, 12 trazas válidas (2026-11-14) |

Informes técnicos de integridad: [evidencia/etapa1_servidor_mcp.md](evidencia/etapa1_servidor_mcp.md),
[evidencia/etapa2_agente.md](evidencia/etapa2_agente.md) y [evidencia/INDICE.md](evidencia/INDICE.md).

## Autoría

Elmer Mondragón Prieto (proyecto individual, 2026).
