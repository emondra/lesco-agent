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

*(ninguno)*
