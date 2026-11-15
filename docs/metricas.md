# Métricas del experimento (versión 1, congeladas antes de ejecutar la configuración A)

Este documento fija **antes de medir** cómo se calcula cada cifra (requisito E3). Lo implementan
`eval/puntuar.py` y `reproducir.py`. Cualquier cambio posterior se registra al final con fecha y
motivo, y las cifras se reportan con ambas versiones.

## 1. Unidad y referencia

- **Unidad de evaluación:** un caso de `eval/casos.jsonl` en una ejecución (configuración ×
  repetición).
- **Referencia:** `eval/referencia.jsonl`, construida a partir de la anotación adjudicada
  (`eval/construir_referencia.py`). La secuencia de referencia son las etiquetas por palabra en
  orden, sin `OMITIR` ni `+`.
- **Normalización de elementos:** un ID se compara tal cual (`CENAREC-195`); cualquier
  `SIN_COBERTURA:<texto>` se compara como `SIN_COBERTURA`. El texto que sigue a los dos puntos no se
  evalúa.
- **Salida del agente:** el archivo que guardó `guardar_resultado` para ese caso. Si no existe, el
  caso cuenta como **no guardado** y su secuencia como vacía.

## 2. Métricas de calidad (por caso)

| Métrica | Definición |
|---|---|
| `exacta` | 1 si la secuencia normalizada del agente es idéntica a la de referencia (mismos elementos, mismo orden); si no, 0. |
| `precision` | \|S ∩ R\| / \|S\| sobre multiconjuntos (S: agente, R: referencia). Si \|S\| = 0, vale 0. |
| `exhaustividad` | \|S ∩ R\| / \|R\|. |
| `f1` | Media armónica de las dos anteriores; 0 si ambas son 0. **Métrica principal.** |
| `sin_cobertura_ok` | Proporción de los `SIN_COBERTURA` de R que también están en S (multiconjunto). Solo en casos donde R tiene alguno. |
| `guardado` | 1 si existe el resultado guardado. |

## 3. Métricas de proceso y costo (por caso, desde la traza)

`tokens_entrada`, `tokens_salida`, `duracion_s`, `pasos`, `llamadas`, `denegadas`, `errores`
(definidos en `agente/leer_traza.py`), más:

- `ids_rechazados`: llamadas a `validar_secuencia` o `guardar_resultado` cuya respuesta contiene
  "no existe en el diccionario" (el agente propuso un ID que no existe).
- `termino_bien`: la ejecución terminó por decisión del modelo (`end_turn`).
- `costo_usd`: tokens × precio de lista del modelo de la traza, con la tabla de `reproducir.py`
  (precios vigentes al 2026-10-06; se declara la fecha).

## 4. Agregación

1. Para cada configuración y repetición: media de cada métrica sobre los casos (todas, y por
   subconjunto `normal` / `dificil`).
2. Para cada configuración: **media y desviación estándar muestral entre las 3 repeticiones** de esas
   medias. Es la cifra que se reporta como "media ± DE".
3. **Comparación B − A:** por caso, se promedia `f1` sobre las repeticiones de cada configuración y
   se calcula la diferencia por caso. Se reporta la media de las diferencias y su **intervalo de
   confianza del 95 % por bootstrap pareado** sobre casos (10 000 remuestreos, semilla 20261117).
   La misma comparación se reporta para `exacta`, `tokens_entrada` y `duracion_s`.

## 5. Dificultad

Un caso es `dificil` si la referencia cumple al menos un criterio de la guía (§9): contiene
`SIN_COBERTURA`, contiene `+`, tiene 12 palabras o más, o el motivo `variante_sentido` / `sinonimo`
quedó confirmado en la adjudicación (`eval/casos_meta.jsonl` actualizado al congelar).

## 6. Lo que no se mide

No se mide la corrección lingüística de la secuencia en LESCO (requeriría personas expertas en
LESCO); solo la concordancia con la referencia construida según la guía. Se declara como limitación.

## Registro de cambios

### 2026-11-13 · Validación documental antes de puntuar (D19). Las métricas no cambian

**Qué no cambia.** Las fórmulas, definiciones, denominadores, columnas, la agregación, el bootstrap
(10 000 remuestreos, semilla 20261117) y el criterio de dificultad de las secciones 1 a 6 siguen
siendo los mismos. Por eso este documento sigue en la **versión 1** y no hay cifras que reportar en
dos versiones. Las funciones de puntuación (`normalizar`, `puntuar_caso`, `proceso_desde_traza`,
`ultima_traza`, `agregar`, `diferencia_pareada`) y las constantes `PRECIOS`, `SEMILLA` y
`REMUESTREOS` no se modificaron (comparación estática, `evidencia/etapa2_agente.md` §5.3).

**Qué se añade.** Antes de calcular cualquier métrica, `eval/puntuar.py` (`evaluar`) comprueba dos
cosas.

1. **Conjunto esperado.** Deben estar exactamente las configuraciones y repeticiones esperadas
   (`rep1`…`repN`), y cada una debe tener una traza por cada caso de la referencia. `reproducir.py`
   las indica siempre: por defecto `--configs A B` y `--repeticiones 3`, los mismos valores que
   `agente/ejecutar_casos.py`. Falla si la referencia está vacía, si falta o sobra una configuración o
   repetición, o si falta la traza de una ejecución esperada.
2. **Consistencia de cada ejecución** (`problemas_de_validez`). Se comprueba que:
   - la traza se puede leer: cada línea es un objeto JSON con `tipo`, y los eventos `herramienta`
     tienen los campos esperados;
   - tiene un evento `inicio` del mismo caso;
   - todos los servidores MCP registrados declaran estar vinculados a ese caso (`caso_vinculado`) y
     tienen versión;
   - ningún `guardar_resultado` exitoso apunta a otro caso;
   - `<caso>.json` existe **si y solo si** la traza registra exactamente un guardado exitoso de ese
     caso;
   - el archivo, si existe, es un objeto JSON con el mismo `caso_id` y con `secuencia` como lista de
     textos.

**Efecto sobre el caso "no guardado"** (§1). Un caso solo cuenta como no guardado, con secuencia
vacía, si su traza es consistente y no registra ningún guardado exitoso. Si la traza registra un
guardado y falta el archivo, o al revés, la ejecución se considera inconsistente y no se puntúa como
no guardada.

**Fallo cerrado.** Si se incumple alguna de estas condiciones, `evaluar` lanza `ErrorVinculacion`
con la lista de ejecuciones afectadas. Los mensajes indican la línea o el archivo, nunca su contenido.
Ante ese error, `reproducir.py` termina con **código 3** antes de escribir nada: en esa ejecución no
genera ni sobrescribe tablas ni puntuaciones parciales. Tampoco borra los archivos de
`resultados/tablas/` que haya generado una ejecución anterior, que quedan como estaban y no
corresponden al estado actual de las trazas. El código 2 sigue indicando que falta la referencia o
las trazas del experimento.

**Alcance.** Es una comprobación de **consistencia documental**: verifica lo que declaran la traza y
el resultado. **No** demuestra autenticidad ni qué proceso escribió un archivo. Los SHA-256 del
registro de evidencia dan consistencia documental, no autenticidad certificada por terceros. Git
aporta trazabilidad de versiones.

**Estado de la evidencia.** Las 97/97 pruebas aprobadas del registro E2-5
(`20261113-201818_suite-completa-e25`) son pruebas automatizadas con el modelo **simulado** o con
datos sintéticos. Describen el comportamiento del código, **no** son resultados del experimento A/B
con el modelo real, que sigue pendiente. Este documento todavía no contiene cifras experimentales.

**Motivo:** evitar que se puntúen ejecuciones incompletas, mezcladas entre casos o sin vinculación
demostrada del servidor (D18 y D19, `PLAN_PROYECTO.md` §6). Detalle en `evidencia/etapa2_agente.md`
§5.

### 2026-11-14 · Referencia con dos anotadores LLM (D20). Las fórmulas no cambian

Registro **previo**: se escribe antes de ejecutar el anotador LLM A, antes de calcular ningún acuerdo y
antes de construir ninguna referencia. Ninguna cifra de esta entrada procede de esas anotaciones.

**Qué no cambia.** Las definiciones y fórmulas de las secciones 2 a 4 (`exacta`, `precision`,
`exhaustividad`, `f1`, `sin_cobertura_ok`, `guardado`, las métricas de proceso y costo, la agregación,
el bootstrap pareado con 10 000 remuestreos y semilla 20261117) y la normalización de §1. Este documento
sigue en la **versión 1**. Las secciones 1 y 5 se conservan tal como se congelaron; esta entrada indica
cómo se aplican ahora.

**Qué cambia: el origen de la referencia (§1).** El diseño congelado preveía una referencia adjudicada
a partir de un anotador humano (el autor) y un LLM (D10). Según informó el autor, el profesor autorizó
verbalmente usar LLM como anotadores, y el autor no hará la anotación humana (D20). Por eso:

- **Anotadores:** el anotador 2 (`claude-opus-5-5`, `eval/prompts/anotador2_v1.md`) y el anotador LLM A
  (`eval/prompts/anotador_llm_a_v1.md`, con un modelo distinto del agente y del anotador 2, que se
  confirmará antes del primer consumo). Los dos usan la misma guía congelada v1 y el mismo índice, y
  ninguno ve las etiquetas del otro ni salidas del agente.
- **No hay adjudicación** ni ningún tercer anotador. En su lugar se usan tres referencias.

**Acuerdo entre los dos anotadores LLM** (`eval/kappa.py`):

1. kappa de Cohen sobre **todas** las posiciones (240). Lo inflan las palabras que la plantilla ya
   sugiere como `OMITIR`;
2. kappa de Cohen solo sobre las **palabras de contenido** (las 166 posiciones sin sugerencia en la
   plantilla). **Es la medida principal**;
3. **acuerdo exacto por caso:** proporción de los 48 casos con todas sus etiquetas iguales.

Se reporta como **concordancia entre dos LLM**, nunca como acuerdo entre personas ni como medida de
corrección.

**Tres referencias, definidas de antemano:**

- **R1:** la secuencia de referencia (§1) obtenida de las etiquetas del anotador 2, en los 48 casos.
- **R2:** la misma construcción con las etiquetas del anotador LLM A, en los 48 casos.
- **Rc:** solo los casos con **acuerdo exacto completo** entre los dos anotadores (todas las posiciones
  iguales), con esas etiquetas comunes. Los demás casos quedan fuera de Rc.

R1, R2 y Rc son **referencias automáticas**, no verdad lingüística validada por personas.

**Cómo se reportan:**

- **Desacuerdos:** el número total, por posición y por tipo (dos IDs distintos, un ID frente a
  `SIN_COBERTURA`, una palabra de contenido frente a `OMITIR`, y diferencias en `+`), con
  `eval/desacuerdos.tsv` como fuente. Los ejemplos que se citen en el artículo se tomarán de esa lista.
- **Casos excluidos de Rc:** su número, sus `caso_id` y su dificultad prevista. Rc se reporta siempre
  con su tamaño (*n*).
- **Métricas:** las de §2–4 se calculan por separado con R1, R2 y Rc (`reproducir.py --referencia`).
  Las métricas de proceso y costo no dependen de la referencia.
- **Sensibilidad de B frente a A:** para `f1` y `exacta` se reportan la media de las diferencias y su
  IC95 % con cada referencia. La conclusión sobre el efecto de la Skill se considera **robusta** solo si
  la diferencia B − A en `f1` tiene el mismo signo en R1, R2 y Rc y su IC95 % excluye el 0 en las tres.
  En cualquier otro caso se reporta como **dependiente de la referencia** o **no concluyente**.
- **Dificultad (§5):** se aplican los criterios que se derivan de cada referencia (`SIN_COBERTURA`, `+`,
  12 palabras o más). Los motivos `variante_sentido` y `sinonimo` ya no pueden confirmarse en una
  adjudicación: se usan los **previstos** (`eval/casos_meta.jsonl`, 25 de 48 casos difíciles previstos),
  y se declara así.

**Limitaciones que se declaran:**

- No existe validación humana de las etiquetas.
- Los dos anotadores son modelos del mismo proveedor, así que su independencia es parcial.
- La Skill de la configuración B operacionaliza la misma guía que siguen los anotadores, lo que puede
  sesgar las referencias a favor de B.
- El kappa mide concordancia, no corrección lingüística.
- No se ha demostrado que los resultados se generalicen a la traducción real a LESCO (ya declarado en §6).

**Motivo:** completar la evaluación de un proyecto individual sin presentar anotaciones automáticas como
humanas y sin cambiar silenciosamente el diseño congelado (D20, `PLAN_PROYECTO.md` §6).
