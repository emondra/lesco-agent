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
