# Procedencia de `cenarec_indice.tsv`

| Campo | Valor |
|---|---|
| Fuente | Diccionario LESCO, Proyecto de Descripción Básica de la LESCO, CENAREC |
| Visor | <https://lesco.cenarec.go.cr/DiccLESCO.php> |
| URL de cada entrada | `https://lesco.cenarec.go.cr/DiccLESCO.php?idw=<idw>` |
| Fecha de extracción | 2026-11-01 |
| Entradas | 1104 (la publicación asociada describe un diccionario básico de ~1100 entradas) |
| SHA-256 del archivo | `7987a6148bf8bc3b5c8d2596f7409a4b98ce609e8af788f9b3fe278b32f0f5d4` |
| Cita | Oviedo, A. y Ramírez Valerio, C. (2018). The LESCO Corpus. Data for the Description of Costa Rican Sign Language. LREC 2018 Workshop on the Representation and Processing of Sign Languages, pp. 167–170. |

## Método

1. Se abrió el visor en un navegador. El índice de la pestaña "Glosa" lista todas las entradas en
   una sola página, con enlaces `DiccLESCO.php?idw=N`.
2. Se leyó ese índice desde la página (una sola carga) y se guardó cada enlace como `idw` y su texto
   como `glosa`, sin modificaciones y en el orden del índice.
3. El SHA-256 calculado en el navegador sobre el texto extraído coincidió con el del archivo
   guardado.

No se guardaron videos, imágenes, ejemplos, traducciones ni categorías temáticas. Se intentó leer las
categorías temáticas (una página por tema), pero el sitio respondió 403 tras unas pocas solicitudes y
se abandonó el intento sin insistir. Condiciones de uso: ver
[docs/datos_y_etica.md](../../docs/datos_y_etica.md).

## Formato

TSV en UTF-8 con saltos de línea LF y encabezado `idw	glosa`.

- `idw`: entero, único.
- `glosa`: tal como en la fuente. Convenciones observadas: palabras unidas con `-` (`A-PARTIR-DE`);
  sufijo numérico para variantes (`ABRIR-2`); `/` para glosas con varios sentidos
  (`CONTINUAR/SEGUIR`); aclaraciones entre paréntesis (`CAFÉ (BEBIDA)`); `^` en compuestos
  (`SORDO^MUDO`); `PRO*` para pronombres; `LETRA-*` para el alfabeto manual.

Este archivo **no se edita a mano**. Cualquier corrección se hace volviendo a la fuente y
documentándola aquí.
