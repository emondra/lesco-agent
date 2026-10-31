# Datos y ética

## 1. Vocabulario LESCO (D9)

**Fuente:** Diccionario LESCO del Proyecto de Descripción Básica de la Lengua de Señas Costarricense,
CENAREC. Visor: <https://lesco.cenarec.go.cr/DiccLESCO.php>. Publicación asociada: Oviedo y Ramírez
Valerio (2018).

**Qué se guarda en el repositorio** (`data/lexicon/`), y nada más:

| Campo | Origen |
|---|---|
| `idw` | Número de la entrada en la URL del visor (`DiccLESCO.php?idw=N`). |
| `glosa` | Texto de la glosa tal como aparece en el índice del visor. |
La URL de cada entrada (`DiccLESCO.php?idw=N`) y la fecha de extracción se derivan del `idw` y de
[data/lexicon/FUENTE.md](../data/lexicon/FUENTE.md). Las categorías temáticas no se guardaron (ver
ese archivo).

**Qué no se guarda:** videos, imágenes, configuraciones de mano, ejemplos ni traducciones del sitio.
El agente nunca "ve" una seña: trabaja con IDs y glosas, y el usuario final consulta el video en la
fuente mediante el enlace.

**Condiciones de uso.** El `robots.txt` del sitio (consultado el 2026-11-01) declara
`Content-Signal: search=yes, ai-train=no, use=reference` y `Allow: /`. No hay aviso de licencia en
las páginas consultadas. Por eso:

- No se entrena ni se ajusta ningún modelo con estos datos (`ai-train=no`).
- Se guarda solo un índice de referencia con enlace a cada entrada (`use=reference`).
- El sitio responde con error 429 a clientes automáticos fuera del navegador. **No se eludió esa
  protección:** el índice se leyó desde un navegador en una sola carga de página pública. Un intento
  posterior de leer las categorías temáticas recibió 403 y se abandonó sin insistir.
- Uso académico, sin fines de lucro y con atribución.
- Pendiente (autor): escribir al contacto del sitio para informar del uso y pedir permiso explícito.

**Validación.** Es **documental**: cada entrada coincide con la fuente en la fecha de consulta. No
hubo validación por una persona experta en LESCO. Se declara como limitación.

**Generación de contenido:** prohibido generar glosas, IDs o señas con un LLM. Si un concepto no
está en el índice, la salida correcta es `SIN_COBERTURA`.

## 2. Casos de evaluación

- Frases en español sobre trámites en ventanilla, redactadas para el proyecto. **Sin nombres,
  cédulas, teléfonos, direcciones ni otros datos personales reales**; si una frase necesita un dato,
  se usa un marcador (`[NOMBRE]`, `[FECHA]`, `[NUMERO]`).
- Etiquetas: autor (anotador 1) y `claude-opus-5-5` (anotador 2, autorizado por el profesor).

## 3. Audio (solo demo)

- Voz sintética o del propio autor, con frases del conjunto de casos. Ninguna grabación de terceros.

## 4. Trazas

- Las trazas guardan entradas, llamadas y salidas del agente. Como los casos no contienen datos
  personales, las trazas tampoco. Antes de cada commit con trazas se ejecuta una búsqueda de patrones
  de datos personales y de claves (`sk-ant`).
- La clave de la API nunca aparece en código, configuración ni trazas (D14).

## 5. Alcance ético del sistema

- Propone **secuencias candidatas** de señas de un vocabulario documentado; no traduce LESCO completo
  (gramática propia, rasgos no manuales) ni sustituye a intérpretes.
- Los segmentos sin cobertura se muestran como tales, en vez de aproximarse con una seña dudosa.
- El sistema no se probó con personas sordas; cualquier uso real requeriría su participación y la de
  intérpretes (Yin et al., 2021, recomiendan involucrar a las comunidades).
