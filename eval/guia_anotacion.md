# Guía de la tarea y de anotación (versión 1, 2026-11-01)

Esta guía define **qué es una respuesta correcta**. La siguen los dos anotadores (el autor y
`claude-opus-5-5`) para construir las etiquetas de referencia, y la Skill (configuración B) la
operacionaliza para el agente. La configuración A no la recibe: esa es la variable del experimento.

Se congela junto con el conjunto de evaluación. Cualquier cambio posterior invalida las etiquetas.

## 1. Alcance

La salida es una **secuencia candidata de entradas del Diccionario LESCO del CENAREC**, en el orden de
la frase en español. Es una simplificación declarada: no se modelan el orden sintáctico de LESCO, los
rasgos no manuales, la dactilología ni los clasificadores.

## 2. Unidad de anotación

La transcripción se divide en palabras con el tokenizador del proyecto (secuencias de letras o
dígitos; la puntuación se descarta). **Cada palabra recibe exactamente una etiqueta:**

| Etiqueta | Uso |
|---|---|
| `CENAREC-<n>` | La palabra se representa con esa entrada del diccionario. |
| `+` | La palabra forma parte de la expresión de varias palabras iniciada por la palabra anterior etiquetada (regla 4). |
| `SIN_COBERTURA` | La palabra tiene contenido, pero no hay entrada adecuada (regla 8). |
| `OMITIR` | Palabra funcional de la lista cerrada (regla 3). |

La secuencia de referencia se obtiene leyendo las etiquetas en orden y descartando `OMITIR` y `+`;
`SIN_COBERTURA` aparece como `SIN_COBERTURA:<palabra>`.

## 3. Palabras que se omiten (lista cerrada)

- Artículos: el, la, los, las, lo, un, una, unos, unas.
- Preposiciones y contracciones: a, al, ante, bajo, de, del, en, entre, hacia, por, según, tras.
- Conjunciones: y, e, ni, que.
- Pronombres personales y clíticos: yo, tú, vos, usted, ustedes, él, ella, ellos, ellas, nosotros,
  nosotras, me, te, se, le, les, nos, mí, ti, sí (pronombre).
- Posesivos: mi, mis, tu, tus, su, sus, nuestro, nuestra, nuestros, nuestras.
- Verbos **auxiliares**: haber en tiempos compuestos ("ha pagado"); ser y estar como cópula o en
  pasiva ("está cerrado", "es importante": se omite *está/es* y se representa *cerrado/importante*).

Cualquier otra palabra se considera de contenido y se busca. En particular **no** se omiten:
no, sí (afirmación), con, sin, para, desde, hasta, o, interrogativos, números, *hay* (haber
existencial) y *poder/deber/necesitar*.

Ambigüedad *lo/la/los/las*: siempre `OMITIR` (artículo o clítico).

## 4. Expresiones de varias palabras

Si varias palabras **contiguas** de la frase corresponden a una sola glosa del diccionario
(p. ej. EN-LA-MAÑANA, POR-FAVOR, A-PARTIR-DE, LUNES-A-VIERNES, CORREO-ELECTRÓNICO,
LLAMAR-POR-TELÉFONO), la primera palabra del tramo recibe el ID y las siguientes `+`. Se prefiere el
tramo más largo. Esta regla tiene prioridad sobre la regla 3.

## 5. Forma de búsqueda

Se busca el **lema**: infinitivo para verbos ("pague" → pagar), singular para sustantivos
("facturas" → factura), masculino singular para adjetivos ("cerrada" → cerrado).

## 6. Variantes numeradas

Si hay variantes del mismo sentido (ABRIR y ABRIR-2), se elige la que **no** tiene número; si todas
tienen número, la de número menor.

## 7. Sentido

Si hay entradas con sentidos distintos, se elige la que corresponde al contexto
(CAFÉ (BEBIDA) frente a CAFÉ (COLOR)). Las coincidencias **parciales** del buscador solo se usan si
la glosa completa corresponde al significado de la palabra en la frase.

## 8. Sinónimos y sin cobertura

- Si el lema no tiene entrada, se acepta **un** sinónimo directo en español con el mismo
  significado en contexto ("abonar" → PAGAR; "aguardar" → ESPERAR).
- Si tampoco hay sinónimo adecuado: `SIN_COBERTURA`. Incluye nombres propios y siglas sin entrada.
- Números: si existe la entrada del número (CINCO, QUINCE, CIEN), se usa; si no, `SIN_COBERTURA`.

## 9. Casos difíciles (definición previa)

Un caso es **difícil** si cumple al menos una condición:

1. tiene al menos una palabra `SIN_COBERTURA`;
2. requiere una expresión de varias palabras (regla 4);
3. requiere elegir entre variantes o sentidos (reglas 6 y 7);
4. requiere un sinónimo (regla 8);
5. tiene 12 palabras o más.

El conjunto de evaluación debe tener al menos 30 % de casos difíciles.

## 10. Procedimiento de los anotadores

1. Cada anotador etiqueta todas las palabras de forma independiente, con el índice
   `data/lexicon/cenarec_indice.tsv` y el buscador del proyecto, sin ver las etiquetas del otro ni
   salidas del agente.
2. Se calcula kappa de Cohen sobre las etiquetas por palabra.
3. Los desacuerdos se resuelven aplicando esta guía; se registra cada resolución y su motivo.
