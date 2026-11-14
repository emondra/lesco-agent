# Etapa 2 — Vinculación obligatoria del agente al caso y validez documental de la evaluación

> Registro técnico-científico. Estado: **borrador pendiente de revisión del autor**.
> Las cifras proceden de registros con salida original conservada (sección 8). Los hechos sin
> evidencia original se marcan "consta en la sesión".
> **Los registros originales están en `evidencia/privado/`, que no está versionada ni publicada.
> Divulgar cualquier evidencia requiere revisión humana y aprobación explícita del autor**
> (estado actual: PENDIENTE_REVISION_HUMANA).
> Este documento continúa `evidencia/etapa1_servidor_mcp.md` (etapa 1, servidor MCP con `--caso`).
> **Adenda posterior (2026-11-13):** publicación del commit `e254f68` y su correspondencia con E2-5.
> Ver el final del documento.

## 1. Objetivo y alcance

**Objetivo:** que la protección de la etapa 1 quede activa en toda ejecución del agente y que la
evaluación solo puntúe ejecuciones cuya traza y resultado sean documentalmente consistentes con el caso.

**Alcance (cuatro partes):**
- **E2-1:** `agente/agente.py`: `--caso` obligatorio y validado; rechazo de configuraciones sin una
  vinculación correcta antes de crear la traza o arrancar procesos; registro de la vinculación en la traza.
- **E2-2:** `agente/configs/A.json`, `B.json` y `demo.json`: la misma pareja `"--caso", "{caso}"` en el
  comando del servidor.
- **E2-3:** `tests/test_agente_simulado.py`: 8 pruebas nuevas.
- **E2-5:** `eval/puntuar.py`, `reproducir.py` y `tests/test_puntuar.py`: validez documental antes de
  puntuar, conjunto esperado de configuraciones y repeticiones, tratamiento de JSON mal formado y
  34 pruebas nuevas.

**Fuera de alcance:**
- el servidor MCP (sin cambios desde la etapa 1);
- la Skill y las políticas (sin cambios);
- el experimento A/B con el modelo real;
- los ataques de inyección con el modelo real;
- la demostración.

## 2. Requisitos y trazabilidad

IDs y textos tomados de `PLAN_PROYECTO.md` §1. La columna "Aporte" es una interpretación del
proyecto, no un texto de la especificación.

| ID | Texto en PLAN_PROYECTO.md §1 (resumido) | Aporte de la etapa 2 |
|---|---|---|
| NN3 | Toda cifra del artículo debe regenerarse desde las trazas entregadas | `reproducir.py` no genera tablas si alguna ejecución esperada falta o no es documentalmente consistente (código 3) |
| E1 | Dos configuraciones que difieren en una sola variable | A y B siguen difiriendo solo en `instrucciones` (B añade `skill/SKILL.md`), además de `nombre` y `descripcion` |
| E2 | Mismo conjunto de evaluación para ambas configuraciones | Se rechaza la evaluación si a una configuración le falta un caso, una repetición o la configuración entera |
| E4 | ≥ 3 ejecuciones por configuración; media y dispersión | El conjunto esperado (por defecto A, B y 3 repeticiones) se comprueba antes de puntuar |
| S4 | Política de permisos; límites de pasos y tokens | Sin cambios en la política. La traza registra si una llamada la permitió la política y la rechazó el servidor |
| S5 | Una traza por ejecución con cada llamada, decisión, tokens y duración | El evento `inicio` registra además el servidor, su versión y el caso vinculado |
| S7 | Defensas en la skill **y** en el código | Defensa en el código del host (vinculación obligatoria) y en la evaluación. **No** incluye los 5 ataques con el modelo real (pendientes, F7) |
| S8 | Un comando regenera los resultados | `python reproducir.py` sigue siendo el comando. Ahora falla cerrado ante evidencia incompleta o inconsistente |
| NN4 | Ningún dato personal real | Pruebas con casos sintéticos y carpetas temporales. Los mensajes de error no muestran contenido |
| NN5 | Uso de IA declarado | Sección 11 |

## 3. Arquitectura

**Flujo de una ejecución:**

```
ejecutar_casos.py (--configs, --repeticiones, --casos)
  └─ agente.argumentos(): --caso obligatorio; caso_valido() con PATRON_CASO.fullmatch
     │    caso_id inválido → argparse termina con código 2 (sin crear traza)
     └─ agente.ejecutar():
          1. vuelve a validar args.caso; si no es válido → ValueError (sin crear traza)
          2. problemas_de_vinculacion(config)   ← validación ANTES de crear la traza y de arrancar procesos
          3. Traza(...)                          ← se crea la traza
             · si hubo problemas en 2: se registra solo el evento 'fin' con el motivo de rechazo,
               la ejecución termina con código 2 y no se arranca ningún servidor MCP
          4. servidor MCP: python mcp_server/servidor_lesco.py --casos {casos} --caso {caso} --salidas {salidas}
          5. evento 'inicio' con servidores=[{nombre, version, caso_vinculado}]
          6. bucle del modelo → política en el host → servidor (que vuelve a validar)
reproducir.py (--configs A B, --repeticiones 3 por defecto)
  └─ puntuar.evaluar(..., configuraciones, repeticiones)
       ├─ conjunto esperado: configuraciones × rep1..repN × casos de la referencia
       ├─ problemas_de_validez(traza, caso, resultado) por ejecución
       └─ ErrorVinculacion → código 3, sin tablas;  si todo es válido → mismas fórmulas que antes
```

**Dos rechazos distintos en el agente:**
- **`caso_id` inválido:** se rechaza en la entrada (argparse o el inicio de `ejecutar()`) y **no se crea
  traza**. Lo prueban `test_t6_cli_exige_caso_valido` y `test_t6_ejecutar_rechaza_caso_invalido_sin_crear_traza`.
- **Configuración sin vinculación correcta:** la comprobación se hace **antes** de crear la traza y de
  arrancar procesos. Después se crea una **traza de rechazo**, con solo el evento `fin` y el motivo, para
  que el rechazo quede registrado. **No se arranca ningún servidor MCP.** Lo prueba
  `test_t3_rechazo_antes_de_iniciar_procesos` (`ClienteMCP` no se crea y la traza solo contiene `fin`).

**Componentes:**

| Componente | Estado en esta etapa |
|---|---|
| Servidor MCP (`mcp_server/servidor_lesco.py` v0.2.0) | Sin cambios desde la etapa 1. 4 herramientas. Con `--caso` solo entrega y guarda ese caso |
| Agente (`agente/agente.py`) | Funciones nuevas: `caso_valido()` y `problemas_de_vinculacion()`. Falla cerrado. Campo `servidores` en el evento `inicio`. **No** registra el comando completo ni rutas |
| Skill (`skill/SKILL.md`) | Sin cambios. Solo forma parte de B y demo |
| Política (`politica/*.json`) | Sin cambios: permitir, confirmar, denegar, ocultar y máximos de llamadas por herramienta |
| Evaluación (`eval/puntuar.py`) | Nuevos: `ErrorVinculacion`, `problemas_de_validez()` y `_breve()`. `evaluar()` comprueba el conjunto esperado. **Fórmulas sin cambios** (sección 5.3) |
| Reproducción (`reproducir.py`) | Nuevas opciones `--configs` y `--repeticiones`. Código 3 sin tablas |

## 4. Configuraciones experimentales A/B

| Clave | A | B | demo |
|---|---|---|---|
| `nombre`, `descripcion` | A | B | demo |
| `instrucciones` | `instrucciones_genericas.md` | `instrucciones_genericas.md` + `skill/SKILL.md` | igual que B |
| `modelo`, `esfuerzo`, `limites`, `envolver_resultados` | Idénticos | Idénticos | Idénticos |
| `politica` | `politica_experimento.json` | `politica_experimento.json` | `politica_demo.json` (guardar requiere confirmación) |
| `servidores` (comando con `--caso {caso}`) | Idéntico | Idéntico | Idéntico |

- **Evidencia de la diferencia única:** `test_a_y_b_solo_difieren_en_instrucciones` (existente) compara todas
  las claves de A y B. `test_t1_configuraciones_con_una_vinculacion_valida` comprueba una única pareja
  válida en A, B y demo. Ambas pasaron en E2-5.
- **Lo que no cambió:** lo que ve el modelo (instrucciones, descripciones y esquemas de las herramientas,
  objetivo, política y límites) es igual que en el piloto. `--caso` solo actúa en el host y en el servidor.

## 5. Validación de la vinculación y de la validez documental

### 5.1 Durante la ejecución (agente y servidor)

- **`caso_valido()`:** acepta solo `[A-Za-z0-9][A-Za-z0-9_-]{0,39}` completo (`fullmatch`). Rechaza vacíos,
  rutas, espacios, saltos de línea finales, caracteres no ASCII y más de 40 caracteres.
- **`problemas_de_vinculacion()`:** cada servidor debe tener exactamente una pareja `--caso {caso}`.
  Rechaza:
  - duplicados;
  - un valor fijo o vacío;
  - `--caso=<valor>`;
  - el marcador fuera de la pareja;
  - configuraciones sin servidores;
  - comandos mal formados.
- **El servidor vinculado** rechaza leer o guardar otro caso (etapa 1).

### 5.2 Al evaluar (`problemas_de_validez()` y `evaluar()`)

**Condiciones de cada ejecución:**
0. traza legible: cada línea es un objeto JSON con `tipo`, y los eventos `herramienta` tienen los campos
   que usa `agente/leer_traza.py`, con su tipo;
1. evento `inicio` del caso;
2. todos los servidores registrados declaran vinculación al caso;
3. ningún `guardar_resultado` exitoso apunta a otro caso;
4. existe `<caso>.json` si y solo si la traza registra exactamente un guardado exitoso del caso;
5. el resultado es un objeto JSON que declara ese `caso_id`;
6. `secuencia` es una lista de textos.

**Comprobaciones del conjunto:**
- configuraciones esperadas sin ausencias ni sobrantes;
- repeticiones `rep1..repN` sin ausencias ni sobrantes;
- una traza para cada ejecución esperada;
- rechazo de la referencia vacía y de la ausencia de trazas, configuraciones o repeticiones.

**Si algo falla:** `ErrorVinculacion` con todos los motivos. No hay puntuaciones parciales.
`reproducir.py` termina con código 3 sin crear la carpeta de tablas.

**Mensajes:** indican línea, archivo o recuento. Un `caso_id` solo se muestra si cumple por completo el
formato. Si no, se muestra `'identificador inválido'`, sin ningún fragmento.

**Naturaleza de la comprobación:** es **consistencia documental**. Verifica lo que declaran la traza y el
resultado; **no** demuestra autenticidad ni qué proceso escribió un archivo.

### 5.3 Lo que no cambió

Comparación del árbol sintáctico antes y después de editar (consta en la sesión): `normalizar`,
`puntuar_caso`, `proceso_desde_traza`, `ultima_traza`, `_media`, `agregar`, `diferencia_pareada`,
`METRICAS_CALIDAD`, `METRICAS_PROCESO`, `PRECIOS`, `SEMILLA` y `REMUESTREOS` no cambiaron.

Las ejecuciones válidas se puntúan con las mismas funciones y producen las mismas columnas.
`docs/metricas.md` v1 sigue vigente.

## 6. Procedimiento de pruebas y entorno

- **Pruebas:** `unittest`, solo biblioteca estándar.
  - **Agente:** con el modelo simulado (`--simulado`), guiones fijos y casos sintéticos en carpetas
    temporales. El servidor MCP real se arranca por stdio.
  - **Evaluación:** trazas y resultados sintéticos con la estructura real de `evaluar()`.
- **Sin API:** ninguna de las 97 pruebas usa la API ni el modelo real.
- **Registro:** `evidencia/registrar_pruebas.py` v1.2.1, sin cambios respecto de E2-4. Su SHA-256 normalizado
  a LF coincide con el registrado en E2-4.
  - **Ejecución:** suite cerrada `completa` (`python -m unittest discover -s tests -v`), entorno mínimo sin
    credenciales y guardia de red **parcial** (solo procesos Python).
  - **Lo que registra:** stdout, stderr, `cambios.patch`, fuentes sin seguimiento, metadatos y SHA-256.
- **Defensa adicional en E2-5:** el entorno de la llamada se lanzó sin variables de credenciales de
  modelos, así que tampoco el registrador ni git las tuvieron.
- **Entorno registrado:** CPython 3.12.10, base `e495b062492cb34e073fb99bb283f38924c0d30c` más los cambios
  sin commit de `cambios.patch`.

## 7. Inventario de pruebas nuevas e interpretación

**Fuente de los resultados:** `stderr.txt` del registro E2-5 (SHA-256 en la sección 8): 97 `ok`, 0 FAIL,
0 ERROR y 0 omitidas, con `Ran 97 tests in 4.823s` / `OK`. Las 42 pruebas nuevas de esta etapa están entre
esas 97.

### 7.1 Agente (`tests/test_agente_simulado.py`, 8 nuevas; 12 en total)

| Prueba | Qué comprueba |
|---|---|
| test_t1_configuraciones_con_una_vinculacion_valida | A, B y demo tienen una única pareja `--caso {caso}` válida |
| test_t2_traza_registra_servidor_version_y_caso | El evento `inicio` registra `{nombre, version: 0.2.0, caso_vinculado}`, sin ruta del intérprete, rutas absolutas ni el comando |
| test_t3_tabla_problemas_de_vinculacion | 15 configuraciones (1 válida y 14 inválidas) más un caso de dos servidores |
| test_t3_rechazo_antes_de_iniciar_procesos | Sin vinculación, con la pareja duplicada o con un valor fijo: código 2, `ClienteMCP` sin crear y traza solo con `fin` |
| test_t4_inyeccion_no_crea_archivo_de_otro_caso | La política **permite** las llamadas y el **servidor** vinculado rechaza leer y guardar otro caso. No se crea ningún archivo ajeno |
| test_t5_inyeccion_no_altera_resultado_existente | El rechazo es **por vinculación** y no por la regla de no sobrescribir. El resultado ajeno queda idéntico byte a byte |
| test_t6_cli_exige_caso_valido | Sin `--caso`, o con `""`, `"c1\n"`, `"c1 "`, `"../x"`, `"a/b"`, `"_x"`, `"ñ1"` o 41 caracteres: código 2 |
| test_t6_ejecutar_rechaza_caso_invalido_sin_crear_traza | Al llamar directamente a `ejecutar()` con un caso inválido: `ValueError` y ninguna traza |

### 7.2 Evaluación (`tests/test_puntuar.py`, 34 nuevas; 43 en total)

- **Consistencia por ejecución (14):**
  - válidas: con resultado, y sin resultado (cuenta como "no guardado");
  - rechazos: traza histórica sin `servidores`, servidor vinculado a otro caso, resultado sin guardado,
    guardados duplicados, guardado sin resultado, guardado de otro caso, resultado que declara otro caso,
    traza sin `inicio`, ejecución esperada sin traza y repetición ausente en una configuración;
  - sin puntuaciones parciales;
  - `reproducir.py` termina con código 3 sin tablas.
- **Conjunto esperado (10):**
  - protocolo completo válido;
  - rechazos: configuración ausente, configuración no esperada, repeticiones insuficientes, repetición no
    esperada, sin trazas, sin configuraciones, configuraciones sin repeticiones y referencia vacía;
  - coincidencia de los valores por defecto de `reproducir.py` y `ejecutar_casos.py` (por lectura estática).
- **JSON mal formado (10):**
  - rechazos en la traza: JSON mal formado, línea que no es objeto, evento sin `tipo` y herramienta sin sus
    campos;
  - rechazos en el resultado: JSON mal formado, resultado que no es objeto, sin `secuencia` y `secuencia`
    que no es lista de textos;
  - mensajes sin contenido (ni la marca completa ni su prefijo);
  - `reproducir.py` termina con código 3 ante una traza mal formada.

### 7.3 Interpretación: tres niveles que no deben mezclarse

| Nivel | Qué es | Estado |
|---|---|---|
| **1. Pruebas automatizadas con modelo simulado o datos sintéticos** | Comportamiento **del código**: servidor, agente, política, traza, evaluación y reproducción | **Hecho y registrado** (E2-5: 97/97) |
| **2. Experimento con el modelo real** (A×3 y B×3 sobre el conjunto congelado) y los 5 ataques (F7) | Efecto de la Skill y comportamiento real del modelo | **No ejecutado.** Depende de la anotación, el kappa, la adjudicación y el congelamiento del conjunto |
| **3. Afirmaciones científicas del artículo** | Lo que respalde el nivel 2 (y el nivel 1 para describir el sistema) | **Ninguna sobre la efectividad de la Skill ni sobre la resistencia a la inyección** |

**Cómo leer las pruebas:**
- **T4 y T5:** usan un modelo simulado que **obedece la inyección a propósito**. Demuestran la defensa del
  código (host y servidor). **No** demuestran que el modelo resista la inyección, ni otros efectos de una
  inyección dentro del propio caso.
- **El número de pruebas:** describe la cobertura del código, no un resultado científico.

## 8. Registros de evidencia

Los registros citados están **solo** en `evidencia/privado/` (ignorada por git) y no están publicados ni
versionados. Cada uno contiene una candidata de publicación generada mediante controles automáticos. E2-4
y E2-5 no presentan redacciones ni exclusiones. Ninguna candidata ha recibido aprobación humana.
`evidencia/pruebas/` y `evidencia/APROBACIONES.md` no existen.

| Registro | Etapa | Suite | Inicio–fin (-06:00) | Instrumento | Resultado | Integridad operativa | Sello original | Sello candidata |
|---|---|---|---|---|---|---|---|---|
| `20261113-194941_suite-completa-etapa2` (**E2-4**) | Después de E2-1 a E2-3 | completa | 2026-11-13 19:49:41–19:49:47 | v1.2.1 | OK, **63** pruebas | CONFORME | `3cd089a8cacba2736fce4b24a8c3001990878cea5da9242c6f220eebe107a89b` | `9f8393eea2064a704bf11c797dd41d4fddf0a0b97689b68749a80a681e570105` |
| `20261113-201818_suite-completa-e25` (**E2-5**) | Después de E2-5 | completa | 2026-11-13 20:18:18–20:18:24 | v1.2.1 | OK, **97** pruebas | CONFORME | `15732a6a4c94689dd37724043ebf6e2a1d0fc4701620fe4ab9f72bbcdc183ac8` | `1f55f988ecd4dfd0074f408490e96f474aac62206b5c1943a2c52c859aa31d7e` |

**SHA-256 de `stderr.txt` y `cambios.patch`** (de `contexto.json`):

| Registro | `stderr.txt` | `cambios.patch` |
|---|---|---|
| E2-4 | `f203c4fec09fa7839432ca7a8fc267c4e8bedd14fc8a574ca8e4f9ceabfa0269` | `5e674f219d2bf982153048adf8c880d47caa614011cfdad8a5916fce0719e1cc` |
| E2-5 | `784759c313fe573059d9db8dea0f8841a8230d49af14d380fb0e21a3cb2f8c77` | `332a3bc92308f66870ab4bd680f8e8088b601c0b5f699fe54322f71f4e302ef5` |

**Relación entre registros:**
- **No se suman.** Las 97 de E2-5 **incluyen** las 63 de E2-4, que a su vez incluyen las 55 de la línea base
  D3b (`20261113-191307_suite-completa-linea-base`).
- **Reparto por módulo en E2-5:** `puntuar` 43, `servidor_mcp` 19, `lexico` 14, `agente_simulado` 12 y `eval` 9.
- **Mismo código del agente:** E2-4 y E2-5 tienen los mismos hashes (normalizados a LF) de `agente/agente.py`
  (`0b86dc4a…af86ac`), de las tres configuraciones y de `tests/test_agente_simulado.py`.
- **Distinto código de evaluación:** difieren en `eval/puntuar.py`, `reproducir.py` y `tests/test_puntuar.py`,
  que son los cambios de E2-5. **E2-4 no cubre la validación de E2-5.**

**Verificación de ambos registros:**
- `registrar_pruebas.py verificar`: integridad criptográfica VERIFICADA y operativa CONFORME;
- recálculo independiente con `Get-FileHash`: 0 discrepancias;
- registros anteriores, D4 e índice intactos (con hashes);
- `git status` sin cambios.

**Alcance de estas verificaciones:**
- **Lo que demuestran los SHA-256:** **consistencia documental**. Los archivos no cambiaron respecto de lo
  registrado y los registros concuerdan entre sí.
- **Lo que no son:** una autenticidad certificada por terceros.
- **Lo que aportará git** cuando se haga el commit: **trazabilidad de versiones** (qué contenido existía en
  cada versión y cómo cambió). Tampoco eso es una autenticidad independiente.
- **Lo que haría falta para la autenticidad independiente:** garantías adicionales que este proyecto no
  incluye, como firmas criptográficas de los commits o un sellado de tiempo de terceros.

**Auditoría de privacidad de E2-5** (consta en la sesión): búsqueda de `anotador2` (sin distinguir
mayúsculas) y de `eval/anotaciones` en el registro, sin mostrar el contenido de las líneas.
- **Total:** 8 coincidencias, 4 en el original y 4 en la candidata, en **2 archivos por lado**.
- **`stderr.txt` (3 por lado):** nombres de una clase de pruebas existente en la salida de unittest.
- **La copia en `fuentes/` de `evidencia/test_registrar_pruebas.py` (1 por lado):** código fuente de las
  pruebas del registrador, en concreto la ruta de un archivo sintético de un repositorio temporal.

Ninguna contiene datos del segundo anotador. Ninguna línea se reproduce aquí.

## 9. Errores, correcciones y decisiones (constan en la sesión, salvo indicación)

1. **Escritura de trazas fuera de su carpeta.** `--caso` formaba el nombre de la traza antes de validarse.
   Corregido con `caso_valido()` (E2-1).
2. **Salto de línea final aceptado.** `PATRON_CASO.match` con `$` acepta `"c1\n"`. El agente y la
   evaluación usan `fullmatch`. **El servidor sigue usando `match`** (pendiente, sección 10).
3. **E2-1 sin E2-2 rechaza las configuraciones actuales.** Es el comportamiento buscado (falla cerrado).
   Se aplicaron y validaron juntos.
4. **Espacio perdido al aplicar E2-1** (`politica =Politica(`). Se corrigió antes de validar.
5. **T4 y T5 reforzadas:** distinguen el rechazo del servidor del de la política, y el rechazo por
   vinculación del de la regla de no sobrescribir.
6. **E2-5, endurecimientos sucesivos antes de aplicar:**
   - de exclusión silenciosa a rechazo de las ejecuciones sin traza;
   - conjunto esperado de configuraciones y repeticiones;
   - rechazo de evaluaciones vacías;
   - tratamiento controlado del JSON mal formado;
   - `_breve()` cambiado para no mostrar fragmentos de identificadores inválidos.
7. **Decisiones:**
   - `--caso` obligatorio en el agente y opcional en el servidor (compatibilidad con su uso por separado);
   - fallar cerrado en vez de excluir ejecuciones (excluir sesgaría A frente a B);
   - el conjunto esperado toma los valores por defecto de `ejecutar_casos.py` porque no hay manifiesto;
   - no cambiar las fórmulas, las descripciones de las herramientas, la Skill ni la política.

## 10. Limitaciones, amenazas a la validez y reproducibilidad

- **Sin experimento real:** el experimento A/B con el modelo real **no se ha ejecutado**. Tampoco los 5
  ataques con el modelo real.
- **Alcance de la validez:** pruebas deterministas con un modelo simulado. No miden el comportamiento del
  modelo real.
- **Servidor con `match`:** acepta un salto de línea final en `caso_id`. Con `--caso`, el rechazo por
  vinculación lo neutraliza; sin vincular, no. La corrección es un paso aparte, con su registro.
- **Guardia de red parcial:** solo procesos Python. La ausencia de llamadas a la API se apoya en la lista
  cerrada de suites, en el entorno sin credenciales y en la revisión del código, no en un aislamiento de red.
- **Consistencia documental, no autenticidad:** la validación de `puntuar.py` y los SHA-256 no impiden que
  alguien edite a mano a la vez una traza y su resultado de forma coherente.
- **Conjunto esperado sin manifiesto:** si se ejecuta el experimento con otros parámetros y se evalúa con
  los valores por defecto, la evaluación **falla cerrado**; no puntúa en silencio.
- **Trazas del piloto** (servidor v0.1.0, sin `servidores`): se rechazarían si se intentaran puntuar.
  Nunca se puntuaron.
- **`referencia.jsonl` mal formado:** sigue fallando con traceback en `reproducir.py` (fuera del alcance de E2-5).
- **Sin commit, sin clon limpio y un solo entorno:** el código probado se identifica con la base `e495b06…`
  más `cambios.patch`. No hay verificación en un clon limpio ni por una segunda persona. Windows y
  CPython 3.12.10. *(Lo de "sin commit" describe la situación a la fecha de los registros; ver adenda.
  Sigue sin haber verificación en un clon limpio ni por una segunda persona.)*
- **`.env` presente en el disco:** las pruebas no lo leen, pero `cargar_clave()` lo leería como respaldo si
  se creara el cliente real. Ninguna prueba lo hace sin reemplazar `cargar_clave`.

**Cómo reproducir** (en un directorio aislado, nunca en el repositorio de trabajo):

*Procedimiento A, reproducción histórica del estado registrado en E2-5* (base `e495b06…` +
`cambios.patch` + fuentes sin seguimiento del registro). No se combina con el procedimiento B de la adenda.
1. Clonar el repositorio en una carpeta temporal y, dentro de esa copia, hacer `git checkout e495b06…`.
2. Aplicar `cambios.patch` del registro E2-5. Solo será accesible si se aprueba la publicación de la
   candidata; mientras tanto, solo el autor puede hacerlo con el original privado.
3. Copiar las fuentes sin seguimiento del registro.
4. Ejecutar `python -m unittest discover -s tests -v`. Se esperan 97 `ok`.
5. Comparar los hashes del código con `codigo_sha256_lf_antes` del registro.

## 11. Uso de IA

**Herramienta:** Claude Code. No se indica el modelo concreto porque no consta en la evidencia del proyecto.

**Lo que hizo Claude Code:**
- auditorías estáticas;
- propuestas de diff;
- redacción del código y de las pruebas;
- ejecución de las pruebas y verificaciones autorizadas e informe de sus resultados;
- redacción de este documento.

**Lo que hizo el autor, según consta en la sesión:**
- **Autorizó comandos:** cada edición y cada ejecución se autorizó explícitamente, una a una.
  - *Aclaración posterior (2026-11-13):* "una a una" describe el procedimiento seguido en la sesión
    de Claude Code. Claude Code presentaba el diff o el comando, el autor lo aprobaba, pedía cambios o
    lo rechazaba, y después se informaba de la verificación. Ese procedimiento consta solo en la
    transcripción de la sesión, que no forma parte del repositorio. **No** es un registro
    independiente ni una certificación. Ver `docs/uso_de_ia.md`.
- **Revisó propuestas y resultados:** revisó diffs e informes y pidió correcciones de diseño. Por ejemplo:
  - `fullmatch` y la vinculación estricta;
  - la distinción entre política y servidor en T4 y T5;
  - el rechazo de trazas ausentes y del conjunto esperado;
  - el JSON mal formado;
  - `_breve()` sin fragmentos;
  - el filtro de credenciales adicional en el registro E2-5;
  - la auditoría de privacidad sin mostrar contenido.
- **Verificó directamente:** no consta que el autor haya ejecutado por su cuenta pruebas,
  verificaciones de SHA-256 ni reproducciones.

**Verificaciones estáticas realizadas tras cada edición** (constan en la sesión; las ejecutó Claude Code
con autorización del autor):

*Aclaración posterior (2026-11-13):* "tras cada edición" se limita a los pasos de la tabla siguiente.
La comparación del árbol sintáctico solo se hizo donde la tabla lo indica: E2-3 y las dos ediciones de
E2-5. En E2-1 y E2-2 se registran `ast.parse`, `json.loads`, el diff y las huellas, sin esa
comparación. Las ediciones documentales posteriores (E2-6) no tuvieron análisis del árbol sintáctico.

| Paso | Verificaciones |
|---|---|
| E2-1 y E2-2 (agente y configuraciones) | `ast.parse` de `agente.py` y `json.loads` de A, B y demo. Diff real. Comparación de claves entre A y B y comprobación de la pareja `--caso {caso}` (leyendo el JSON, sin importar el agente). Huella SHA-256 del proyecto y de `evidencia/` antes y después |
| E2-3 (`test_agente_simulado.py`) | `ast.parse`. Recuento de métodos de prueba. **Comparación del árbol sintáctico** de los métodos originales con la copia previa. Huellas SHA-256 |
| E2-5, primera edición (`puntuar.py`, `reproducir.py`, `test_puntuar.py`) | `ast.parse` de los tres. Recuento de pruebas. **Comparación del árbol sintáctico** de las pruebas originales y de las funciones y constantes de `puntuar.py` con la copia previa. Huellas SHA-256 |
| E2-5, endurecimiento ante JSON mal formado (`puntuar.py`, `test_puntuar.py`) | `ast.parse`. Recuento. **Comparación del árbol sintáctico** de las 33 pruebas previas, sus auxiliares y las funciones y constantes de `puntuar.py`. **Inspección del árbol sintáctico** de los valores que se insertan en los mensajes de `problemas_de_validez`. Huellas SHA-256 |

**Cómo se verificó el resultado funcional:**
- pruebas automatizadas, primero como control de desarrollo y después registradas (E2-4 y E2-5) con su
  salida original;
- SHA-256 recalculados con una herramienta distinta del instrumento.

**Falta una verificación independiente** (sección 10). La declaración formal del proyecto se mantiene en
`docs/uso_de_ia.md`.

## 12. Relación con el artículo

| Sección del artículo | Uso de esta etapa |
|---|---|
| Sistema propuesto | Vinculación obligatoria del agente al caso. Falla cerrado. Traza con la vinculación |
| Metodología | Validez documental antes de puntuar. Conjunto esperado (A, B, 3 repeticiones). Un comando de reproducción con código 3 |
| Discusión: amenazas a la validez | Contaminación entre casos y evaluación con ejecuciones faltantes (mitigadas). Consistencia documental frente a autenticidad. Guardia de red parcial. Servidor con `match` |
| Apéndice: reproducción | Commit base, patch, comando, versión del instrumento y hashes de E2-4 y E2-5 |
| Declaración de uso de IA | Sección 11 |

## 13. Afirmaciones y su evidencia

| Afirmación | ¿Se puede afirmar? | Evidencia |
|---|---|---|
| El agente no se ejecuta sin un `--caso` válido | **Sí** | E2-5: `test_t6_cli_exige_caso_valido`, `test_t6_ejecutar_rechaza_caso_invalido_sin_crear_traza` |
| El agente no arranca el servidor si la configuración no lo vincula correctamente al caso | **Sí**, para las 3 variantes de extremo a extremo y las 14 de la tabla | E2-5: `test_t3_rechazo_antes_de_iniciar_procesos`, `test_t3_tabla_problemas_de_vinculacion` |
| La traza registra el servidor, su versión y el caso vinculado, sin rutas ni comando | **Sí**, en la ejecución simulada probada | E2-5: `test_t2_traza_registra_servidor_version_y_caso` |
| Con un modelo simulado que obedece una inyección, el código impide leer o escribir otro caso | **Sí** | E2-5: `test_t4_…`, `test_t5_…` |
| La evaluación no puntúa si falta o es inconsistente alguna ejecución esperada, y `reproducir.py` no genera tablas | **Sí**, para los escenarios probados | E2-5: 34 pruebas de `test_puntuar.py` (sección 7.2) |
| Las fórmulas de las métricas no cambiaron | **Sí**, por comparación estática del código | Sección 5.3 (consta en la sesión). `docs/metricas.md` v1 |
| A y B difieren solo en la Skill | **Sí**, en sus configuraciones | E2-5: `test_a_y_b_solo_difieren_en_instrucciones`, T1 |
| La Skill mejora (o no) la selección de secuencias | **No se ha medido** | Requiere el experimento A/B real (nivel 2) |
| El agente o el modelo resisten la inyección de instrucciones | **No se ha medido** | Pendiente: F7 con el modelo real |
| El experimento real está protegido contra la contaminación entre casos | **El mecanismo está implementado y probado con simulación.** Su funcionamiento en el experimento real se verá cuando se ejecute | E2-5 (nivel 1). Experimento pendiente |
| Las pruebas se reproducen en un clon limpio | **No verificado** | Pendiente |
| La evidencia es pública, autenticada por terceros o sellada en git | **No** | `PENDIENTE_REVISION_HUMANA`. Sin commit a la fecha de los registros (ver adenda: el código ya está en `e254f68`, pero la evidencia privada sigue sin publicar y el commit, sin firmar, da trazabilidad y no autenticidad certificada por terceros). Los SHA-256 solo dan consistencia documental |
| El código publicado en `e254f68` es el que se verificó en E2-5 | **Sí**, como consistencia documental: 30 de 31 archivos de código coinciden; la diferencia es `.gitignore`, posterior y no ejecutable | Adenda (comparación de SHA-256 normalizado a LF, de solo lectura) |

## 14. Datos no verificables o pendientes de confirmar

- **Modelo concreto de Claude Code:** no consta en la evidencia del proyecto.
- **Rama sin `.env` de `test_cabecera_de_workspace_opcional`:** no se ha ejecutado.
- **Comparaciones del árbol sintáctico y endurecimientos sucesivos de E2-5:** constan en la sesión. El
  resultado final está registrado en E2-5; los pasos intermedios, no.
- **Correspondencia entre "Aporte" y requisito:** la columna de §2 es una interpretación. Los IDs y textos
  coinciden con `PLAN_PROYECTO.md` §1.
- **URL del repositorio para el clon:** no se incluye. La publicación y el commit no están hechos.
  *(A la fecha de los registros; ver adenda.)*

## Adenda posterior (2026-11-13): publicación del commit `e254f68` y correspondencia con E2-5

- **Commit:** después del registro E2-5, el autor publicó el commit
  `e254f6833c6686037ebb47000e65215666bd63bb` (2026-11-13 20:58:58 -06:00) en `origin/main`.
  - **Sincronización:** la referencia local `origin/main` coincide con `HEAD`; no se consultó GitHub
    en directo.
  - **Firma:** el commit **no está firmado**.
- **Lo que incluye y lo que no:**
  - **Incluye:** el código de las etapas 1 y 2, las pruebas, el registrador y sus pruebas,
    `evidencia/INDICE.md`, `evidencia/etapa1_servidor_mcp.md` y este documento.
  - **No incluye:** `evidencia/privado/`, `Solicitud/`, los archivos del segundo anotador ni `.env`.
- **Verificación de correspondencia** (solo lectura, 2026-11-13): para cada uno de los 31 archivos de
  código publicados en `HEAD` (con el mismo alcance que usa el registrador: agente y configuraciones,
  servidor, scripts de `eval/`, pruebas, Skill, políticas, `reproducir.py`, el registrador,
  `.gitattributes` y `.gitignore`) se comparó su SHA-256 normalizado a LF con `codigo_sha256_lf_antes`
  del registro E2-5 (`20261113-201818_suite-completa-e25`).

| Resultado | Archivos |
|---|---|
| COINCIDE | 30 |
| DIFERENTE | 1: `.gitignore`, modificado después de E2-5 para excluir `Solicitud/` y los archivos del segundo anotador. No se ejecuta y no afecta a pruebas ni métricas |
| Nuevos o ausentes | 0 |

- **Consecuencia:** el resultado registrado en E2-5 (97/97 pruebas, integridad VERIFICADA y CONFORME)
  corresponde al código publicado en `e254f68`, salvo `.gitignore`.
  - **Lo que no cambia:** E2-4 (63 pruebas) sigue describiendo el estado anterior a E2-5.
  - **Cifras y hashes:** los de E2-4 y E2-5 no cambian.
- **Procedimiento B, reproducción con el código publicado** (alternativo al procedimiento A de la
  sección 10; no se combinan):
  1. Clonar el repositorio en una carpeta temporal nueva, nunca en el repositorio de trabajo.
  2. Dentro de esa copia: `git checkout e254f6833c6686037ebb47000e65215666bd63bb`.
  3. Ejecutar `python -m unittest discover -s tests -v`. Se esperan 97 `ok`.
  4. Solo con acceso autorizado a la metadata privada del registro E2-5: comparar los hashes del
     código con `codigo_sha256_lf_antes` (se espera la diferencia conocida de `.gitignore`).
  5. Borrar la carpeta temporal al terminar.

  Los pasos 1, 2, 3 y 5 se pueden hacer solo con el código publicado; **no** necesitan `cambios.patch`
  ni las fuentes privadas del registro. El paso 4 **sí** requiere la metadata privada de E2-5, que
  está en `evidencia/privado/` y no se publica. Hasta que se apruebe la publicación de su candidata,
  solo puede hacerlo quien tenga acceso autorizado. Una persona externa no puede completar esa
  comparación solo con el repositorio público.
- **Trazabilidad frente a autenticidad:**
  - **Lo que da el commit:** **trazabilidad de versiones**.
  - **Lo que no da:** no aporta autenticidad certificada por terceros (sin firma ni sellado de tiempo
    de terceros).
  - **La correspondencia con E2-5:** es **consistencia documental** basada en SHA-256.
- **Lo que sigue pendiente o igual:**
  - la evidencia de `evidencia/privado/` sigue sin publicar;
  - las candidatas siguen PENDIENTE_REVISION_HUMANA;
  - sigue sin haber verificación en un clon limpio ni por una segunda persona;
  - este documento se publicó con el estado "borrador pendiente de revisión del autor", que se mantiene
    hasta su revisión final.
