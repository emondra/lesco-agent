# Instrucciones para el anotador 1 (autor)

Tiempo estimado: 2–3 horas para 166 palabras de contenido en 48 casos.

1. Lea completa la guía: [eval/guia_anotacion.md](../guia_anotacion.md).
2. Copie `plantilla.tsv` como `anotador1.tsv` en esta carpeta.
3. Abra `anotador1.tsv` en un **editor de texto** (VS Code, Notepad++). **No use Excel:** convierte
   `+` en fórmulas y puede cambiar la codificación. Las columnas están separadas por tabulaciones.
4. Llene la columna `etiqueta` de **todas** las filas con uno de estos valores:
   - `CENAREC-<n>`: la entrada elegida (use el ID que muestra el buscador).
   - `+`: la palabra continúa la expresión de varias palabras de la fila anterior.
   - `SIN_COBERTURA`: palabra de contenido sin entrada ni sinónimo adecuado.
   - `OMITIR`: palabra funcional (§3 de la guía).

   La columna `sugerencia` trae `OMITIR` para la lista cerrada. Cópiela si está de acuerdo, pero
   corríjala cuando la guía lo pida (p. ej. "por" en "por favor" → `+`).
5. Para buscar en el diccionario:

   ```bash
   python eval/buscar.py pagar "por favor" esperar
   ```

   Puede abrir el enlace de cada entrada para ver el video en el sitio del CENAREC.
6. **Independencia:** no abra `anotador2.tsv` ni `anotador2_respuestas.jsonl`, y no mire trazas ni
   salidas del agente hasta terminar.
7. Al terminar, avise. Se calcula el kappa con:

   ```bash
   python eval/kappa.py eval/anotaciones/anotador1.tsv eval/anotaciones/anotador2.tsv
   ```

Si una regla de la guía no alcanza para decidir un caso, anote su duda al final de este archivo
(caso, palabra y por qué). La guía no se cambia durante la anotación.

## Dudas del anotador 1

*(vacío)*
