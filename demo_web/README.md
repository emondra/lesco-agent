# Visor web local de LESCO-Agent

Interfaz web **local** para mostrar el funcionamiento de la arquitectura Agente + Skill + MCP. Usa solo
la biblioteca estándar de Python. **Por defecto** funciona sin conexión a Internet y **no llama a la API**;
la IA real y el visor oficial de CENAREC son opcionales, se activan al iniciar y requieren conexión.

> Todo lo que añade esta demo (voz, motor de reglas, monitor, visor, IA real en vivo) es **posterior al
> experimento** y no forma parte de las 288 corridas evaluadas.

> LESCO-Agent propone secuencias candidatas de entradas del Diccionario LESCO del CENAREC. No es un
> traductor validado y no sustituye a intérpretes humanos.

## Inicio y cierre (PowerShell, desde la raíz del repositorio)

```powershell
# Iniciar (abre el navegador en http://127.0.0.1:8765)
powershell -ExecutionPolicy Bypass -File demo_web\iniciar_demo.ps1

# Equivalente sin el script
python demo_web\servidor_demo.py --abrir

# Otro puerto, si el 8765 está ocupado
powershell -ExecutionPolicy Bypass -File demo_web\iniciar_demo.ps1 -Puerto 8766
```

**Opciones de arranque** (se pueden combinar; sin ninguna, todo es local y sin costo):

| Opción del script | Opción de Python | Efecto |
|---|---|---|
| *(ninguna)* | — | Traza real, simulación y voz con el motor de reglas. Sin API y sin Internet |
| `-PermitirApi` | `--permitir-api` | Habilita «IA real (API)» en el modo de voz (con costo; ver más abajo) |
| `-VisorCenarec` | `--visor-cenarec` | Visor con la página **oficial** de CENAREC (pendiente de confirmar condiciones y permiso) |
| `-VisorCenarecPrueba` | `--visor-cenarec-prueba` | Visor con una página **local** de prueba, sin videos |
| `-Puerto N` · `-SinNavegador` | `--puerto N` · *(sin `--abrir`)* | Puerto y apertura del navegador |

Ejemplo: `powershell -ExecutionPolicy Bypass -File demo_web\iniciar_demo.ps1 -PermitirApi -VisorCenarec`

**Cierre:** `Ctrl+C` (o `Ctrl+Break`) en la ventana de PowerShell. Se borra la carpeta temporal de la
simulación. Si la ventana se cerró sin `Ctrl+C` y el puerto quedó ocupado:

```powershell
Get-NetTCPConnection -LocalPort 8765 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess }
```

## Modos

| Modo | Qué muestra | Origen de los datos |
|---|---|---|
| **Traza real** | Una de las 288 corridas formales A/B, evento por evento | `resultados/experimento/supervisor.jsonl` y `trazas/experimento/`, en solo lectura. Es una ejecución histórica del 2026-11-14, no una llamada en vivo. |
| **Simulación local** | El agente con el modelo **simulado** sobre el caso `demo-001`: obtener la transcripción, buscar las señas, validar, pedir aprobación, guardar una vez y bloquear el segundo guardado | Guion fijo `agente/guion_simulado.json` + servidor MCP real + `politica/politica_demo.json`, en una carpeta temporal aislada (`%TEMP%\lesco_demo_web_*`). |
| **🎤 Demostración por voz** (fase 1) | Una oración en español, dictada o escrita, que una persona corrige y **confirma**; se procesa en vivo y el monitor de 11 etapas se actualiza solo | Motor local de reglas (`modelo_reglas.py`) + host de `agente/agente.py` + servidor MCP real + `politica_demo.json`, con un caso temporal (`voz-NNN`) en `%TEMP%\lesco_demo_web_voz_*`. |
| **🎤 Voz con IA real** (fase 2, opcional) | La misma oración procesada en vivo por `claude-sonnet-5-5` con la Skill (configuración B), tras autorizarla en la interfaz | Proceso aparte `ejecutor_api.py` + host del agente + servidor MCP real + `politica_demo.json`, caso temporal `vozia-NNN` en `%TEMP%\lesco_demo_web_vozia_*`. Con costo. |

| Quién decide en cada modo | Traza real | Simulación | Voz · reglas | Voz · IA real |
|---|---|---|---|---|
| Turnos del «modelo» | LLM real, **histórico** | **Guion fijo** | **Reglas fijas** (no es un LLM) | LLM real, **en vivo** |
| Servidor MCP, política y traza | reales (leídos) | reales | reales | reales |
| Costo | 0 | 0 | 0 | ≈ US$ 0,06 por frase (estimación) |

En la simulación, los turnos del «modelo» son un **guion fijo**: no son decisiones autónomas. Lo que sí
es real es el servidor MCP (búsqueda y validación contra el índice CENAREC), la política del host, la
aprobación humana pedida desde la interfaz y la traza.

## Modo de voz (fase 1, sin API)

**MOTOR LOCAL DE REGLAS — NO ES UN LLM.** No usa Claude, la API, el guion fijo ni la Skill. Reglas
fijas de [`modelo_reglas.py`](modelo_reglas.py):

1. Pide la transcripción del caso temporal.
2. Separa palabras con `eval/tokenizar.palabras` y quita las de la lista cerrada `OMITIR` de la guía de
   anotación.
3. Busca cada palabra **tal cual**, sin lematizar: «firme» no encuentra FIRMAR y «correo electrónico»
   se busca como dos palabras.
4. Acepta solo coincidencias `exacta`; si hay varias, la de menor número CENAREC; si no hay,
   `SIN_COBERTURA:<palabra>`.
5. Valida la secuencia y pide guardarla una sola vez. La política exige aprobación humana.
6. Ante cualquier error de una herramienta se detiene y lo informa, sin inventar glosas ni IDs.

**Flujo en la interfaz:** 🎤 Activar micrófono (o escribir) → corregir el texto → **Confirmar texto y
procesar** → los eventos aparecen solos, uno cada 0,6 s, con autoseguimiento de la línea de tiempo →
**Aprobar guardado** o **Rechazar** con un clic → resultado y traza. `←` pausa el autoseguimiento y
**Seguir en vivo** lo reanuda.

**Monitor de etapas:** Micrófono → STT → Texto → Motor local → MCP → Búsquedas → Validación →
Política → Aprobación → Guardado → Resultado.

- Cada etapa se marca como **hecha** solo con evidencia: un evento del navegador (micrófono, STT), la
  respuesta del servidor (texto confirmado) o un evento de la traza (las demás).
- Los errores se muestran con el mensaje real.
- *Omitido* significa entrada manual o que no se pidió guardar; *no aplica* significa navegador sin
  reconocimiento de voz.

**Reconocimiento de voz:**

- Usa la Web Speech API del navegador solo si existe. Antes de activarlo se avisa que puede depender
  de servicios externos del navegador (Google, Microsoft).
- Si el navegador informa reconocimiento en el equipo (`SpeechRecognition.available`), se indica
  como «informado por el navegador», sin afirmarlo como verificado.
- La demo no recibe ni guarda audio: solo el texto confirmado.
- Sin micrófono, sin permiso o sin Internet, la entrada manual funciona igual.

**Origen en la traza:** el host escribe `modelo: "simulado"` en el evento `inicio` para cualquier
modelo que no sea la API. El adaptador [`voz.py`](voz.py) no modifica la traza: añade `origen.json`
en la carpeta temporal y el campo `motor` (`es_llm: false`, `usa_api: false`) en `/api/voz`, y la
interfaz lo rotula como motor de reglas.

**Seguridad del texto:**

- La transcripción es un dato no confiable.
- Se acepta solo de 1 a 200 caracteres, con letras, dígitos, espacios y puntuación común: sin barras,
  comillas invertidas, llaves, `$`, `|`, `<`, `>` ni caracteres de control. Debe tener como máximo 30
  palabras de contenido.
- Las órdenes dictadas («borra los archivos…») son solo palabras que se buscan en el diccionario.
- La voz no aprueba nada: la aprobación es un clic.
- Hay una sola ejecución a la vez entre la simulación y la voz (409 si hay otra en curso).

## Voz con IA real (fase 2, deshabilitada por defecto)

Dentro de **🎤 Demostración por voz**, el selector **Motor de reglas / IA real (API)** permite procesar la
oración confirmada con **claude-sonnet-5-5** y la **configuración B** (instrucciones genéricas + `SKILL.md`),
con el servidor MCP real vinculado a un caso temporal, la política de la demo (guardar exige un clic) y el
monitor de etapas.

| Garantía | Cómo se cumple |
|---|---|
| Deshabilitada por defecto | Sin `--permitir-api` (`-PermitirApi`), la opción aparece deshabilitada y `/api/voz-ia/*` responde 403 |
| El servidor web no llama a la API | Sigue blindado (`blindar_sin_api`). La ejecución real la hace un proceso aparte, [`ejecutor_api.py`](ejecutor_api.py), uno por ejecución autorizada |
| Clave fuera del navegador | Si `ANTHROPIC_API_KEY` está en el entorno al iniciar, se quita del proceso web y solo se pasa al entorno del proceso hijo. Si no, el agente la busca en `.env` como siempre. Las respuestas pasan por el limpiador (rutas y textos con forma de clave) |
| Autorización desde la interfaz | **Confirmar texto y revisar costo** solo emite un permiso de un solo uso ligado al texto (vigencia: 2 min). La ejecución ocurre únicamente cuando la interfaz envía **Autorizar esta ejecución (con costo)**, como mínimo 1,5 s después de mostrar el costo (el botón cuenta hacia atrás y el servidor lo exige). Enter, la voz, el modelo y Cancelar no autorizan. **El servidor no puede verificar un clic físico**: se apoya en controles verificables (permiso de un solo uso, vigencia, espera mínima, `Origin` propio obligatorio y cabecera `X-Lesco-Demo`, tope y presupuesto) |
| Tope | 5 ejecuciones reales por sesión del servidor. Cuentan al autorizar, terminen como terminen; la sexta responde 429 |
| Sin reintentos | `ejecutar_supervisado.sin_reintentos` (0 reintentos, 120 s por solicitud, identidad del modelo comprobada). Un error detiene la ejecución y se informa |
| Límites | `configs/voz_api.json`: 10 pasos, 60 000 tokens y 4 000 por respuesta (B usó como máximo 6 pasos y 39 433 tokens) |
| Costo | Se muestra como **estimación** (media B ≈ US$0,06, máximo observado US$0,09), **no** como tope garantizado. Tras la ejecución se muestra el costo estimado desde los tokens de la traza |
| Tiempos honestos | Los eventos se muestran a medida que el modelo responde; si ya llegaron varios, se espacian 0,6 s en pantalla. La interfaz indica el tiempo real (traza) y aclara que la visualización no es el tiempo real |
| Aprobación del guardado | El guardado sigue requiriendo **Aprobar guardado**; la aprobación viaja de `/api/voz-ia/aprobacion` al proceso hijo por su canal de protocolo |

### Límites, estimaciones y gasto real

| | Qué es | Valor | ¿Puede superarse? |
|---|---|---|---|
| **A. Límites implementados** | Ejecuciones por sesión | 5 | No: se cuentan al autorizar, con candado |
| | Pasos por ejecución | 10 | No: una solicitud por paso; la prueba `bucle` hace exactamente 10 |
| | Tokens de salida por respuesta | 4 000 | No: `max_tokens` lo impone el proveedor |
| | Reintentos automáticos | 0 | No: `REINTENTOS = 0`; la prueba con error 500 hace 1 solicitud |
| | Tokens por ejecución | 60 000 | Aproximado: antes de cada solicitud se comprueba *acumulado + entrada estimada (caracteres ÷ 3, conservador) + 4 000*. Si la estimación de entrada se quedara corta, se podría superar por poco. El host del agente lo vuelve a comprobar después de cada paso |
| | Presupuesto estimado de la sesión | US$ 1,00 | Bloquea una ejecución nueva si *lo estimado ya gastado + el peor caso teórico de una ejecución (60 000 tokens × US$ 10/M = US$ 0,60)* lo superaría. Una ejecución cortada sin registro cuenta como US$ 0,60. Se reinicia al reiniciar la demo |
| **B. Costo estimado histórico** | Media de las 144 corridas B (máximo observado) | ≈ US$ 0,06 (US$ 0,09) | Es una referencia, no un límite |
| **C. Gasto facturado** | Lo que cobra el proveedor | Solo en la consola de Anthropic | La demo no lo conoce. Una solicitud cortada por tiempo podría facturarse sin que la demo vea su consumo |

Estos límites no reemplazan los controles de gasto de la cuenta del proveedor.

**Pruebas sin costo:** [`tests/test_voz_ia.py`](tests/test_voz_ia.py) usa una API **falsa** local
([`tests/api_falsa.py`](tests/api_falsa.py), que responde con el motor de reglas o con errores 500/401) o el
modo sin clave del ejecutor. La única prueba con configuración de producción comprueba el aislamiento de la
clave sin autorizar nunca una ejecución. Ninguna prueba contacta la API real.
[`tests/test_seguridad_ia.py`](tests/test_seguridad_ia.py) contiene la auditoría:

- peticiones cruzadas: sin `Origin`, origen ajeno, `null`, el marco de CENAREC, sin la cabecera propia,
  `Sec-Fetch-Site` de otro sitio, `Host` ajeno, `OPTIONS` y tipos de contenido;
- permisos: espera mínima, 12 autorizaciones simultáneas con un solo ganador, permiso reemplazado;
- órdenes en la transcripción y un «modelo» malicioso que intenta autorizarse y guardar;
- topes de pasos, presupuesto de tokens antes de cada solicitud y presupuesto de sesión;
- corte brusco: cuenta el peor caso y termina el árbol de procesos;
- entorno mínimo del proceso hijo, retiro de la clave antes del servidor MCP, ocultación literal de la clave;
- sin clave en las trazas, sin red externa en el proceso web y sin lectura de `.env` en el proceso web.

**Ejecución real supervisada** (cada una con la autorización del autor; tiene costo):

1. Tener la clave en `ANTHROPIC_API_KEY` **o** en `.env`, como para el experimento. El agente usa
   **primero la variable de entorno**: si existe una variable vieja o con un texto de ejemplo, tiene
   prioridad sobre `.env` y la API responde 401 (*invalid x-api-key*). Para comprobarlo sin mostrar la
   clave, compare solo su longitud y sus primeros/últimos caracteres con los que muestra la consola de
   Anthropic; para borrar una variable vieja:
   `[Environment]::SetEnvironmentVariable('ANTHROPIC_API_KEY', $null, 'User')` y abrir una ventana nueva.
2. `powershell -ExecutionPolicy Bypass -File demo_web\iniciar_demo.ps1 -PermitirApi`
3. 🎤 Demostración por voz → **IA real (API)** → escribir o dictar la oración → **Confirmar texto y revisar
   costo** → leer el diálogo → **Autorizar esta ejecución (con costo)**.
4. Seguir el monitor → **Aprobar guardado** (o Rechazar) → resultado, traza y costo estimado.
5. Cerrar con Ctrl+C. Contrastar el gasto en la consola del proveedor.

**Estado (2026-11-15):** el autor hizo ejecuciones reales supervisadas en local. La primera respondió 401
porque la variable de entorno tenía un texto de ejemplo en lugar de la clave (se detuvo sin costo y sin
reintentos). Una vez corregido, «El banco cierra las cuatro.» terminó con BANCO · CERRAR · CUATRO guardado
tras la aprobación (costo estimado US$ 0,0586 desde los tokens). Son comprobaciones de funcionamiento de la
demo, **no resultados experimentales**.

## Visor de señas CENAREC (capa de presentación, desactivado por defecto)

Muestra la **página oficial** de cada entrada de la secuencia validada dentro de un `iframe`, con
navegación manual. Funciona igual en los tres modos (traza real, simulación y voz): lee solo la
secuencia que el servidor MCP ya validó.

> **Habilitarlo para uso público depende de confirmar las condiciones de uso de CENAREC y de su
> permiso.** Que sea técnicamente posible no es una autorización.

| Opción de arranque | Efecto |
|---|---|
| *(ninguna)* | Visor desactivado: no hay botón, la CSP no admite marcos de otro origen |
| `--visor-cenarec` (`-VisorCenarec` en `iniciar_demo.ps1`) | Página oficial `https://lesco.cenarec.go.cr/DiccLESCO.php?idw=N`; la CSP añade `frame-src https://lesco.cenarec.go.cr` y nada más |
| `--visor-cenarec-prueba` (`-VisorCenarecPrueba`) | Página LOCAL de sustitución en `/prueba_cenarec/DiccLESCO.php?idw=N`, rotulada «PÁGINA DE PRUEBA LOCAL — NO ES CONTENIDO DE CENAREC», sin video. Para pruebas: no contacta a CENAREC |

**Cómo se usa:**

- Con una secuencia validada aparece **▶ Ver señas CENAREC**. También se puede hacer clic en una
  glosa de la tarjeta.
- El visor muestra las entradas en el orden candidato, con la activa resaltada, y tiene los
  controles **◀ Seña anterior**, **Seña siguiente ▶**, **Abrir página oficial ↗** y **✕ Cerrar
  visor**.
- Teclas: `←`/`→` cambian de seña y `Esc` cierra.
- Para ver la seña se pulsa ▶ en el reproductor de CENAREC.

**Reglas que cumple:**

- **Origen de la dirección:** el `idw` sale del campo `url` oficial de `validar_secuencia`, validado
  con una expresión regular y convertido a entero. Nunca sale de texto escrito o dictado.
- **Carga diferida:** el `iframe` no existe hasta que una persona pide ver una entrada, y se elimina
  al cerrar o al cambiar de seña.
- **SIN_COBERTURA:** no muestra video ni enlace a una entrada, sino «no está en el diccionario».
- **Textos fijos:** siempre se ven «Fuente: Diccionario LESCO, CENAREC» y la advertencia «La sucesión
  de entradas del diccionario no constituye una traducción gramatical validada a LESCO».
- **Página completa:** se muestra la página oficial entera; solo se escala con CSS para que quepa.
  No se extrae ni se reconstruye el reproductor.
- **Sin descargas ni recolección:** no se descargan, guardan, copian ni redistribuyen videos. No se
  extraen las URL de los MP4 ni se recolecta nada del sitio. Las direcciones de los videos no se
  derivan del `idw`.
- **Sin reproducción automática:** no se adivinan duraciones. Un `iframe` de otro origen no da
  eventos fiables de fin, así que la navegación es manual.
- **Sin falsas confirmaciones:**
  - Si el navegador indica que no hay conexión, no se carga nada y se muestra un aviso con el enlace
    oficial.
  - Si hay conexión, el texto de estado dice que la demo **no puede verificar** si la página o el
    video cargaron.
- **Atributos del marco:** `sandbox` (sin navegación de la página principal),
  `referrerpolicy="no-referrer"` y `allow="autoplay; fullscreen"`.

## Controles

| Control | Tecla | Acción |
|---|---|---|
| Traza real / Simulación local | — | Cambia de modo |
| Iniciar demostración | — | Carga la corrida elegida o ejecuta la simulación |
| Siguiente evento | `→`, `Espacio`, `AvPág` | Muestra el siguiente evento de la traza |
| Evento anterior | `←`, `RePág` | Vuelve un evento |
| Reiniciar visualización | `Inicio` | Vuelve al primer evento (no repite la ejecución) |
| Mostrar detalles de la herramienta | `D` | Muestra el evento completo de la traza (JSON) |
| Pantalla completa | `F` | Alterna la pantalla completa |
| Aprobar guardado / Rechazar | — | Responde a la política `confirmar` de `guardar_resultado` (solo simulación) |

Los punteros de presentación que envían `AvPág`/`RePág` avanzan y retroceden eventos.

Colores: azul = traza histórica real; violeta = agente simulado (guion); turquesa = llamada MCP
permitida; gris = host y decisiones de política; verde = resultado realmente guardado; rojo = acción
denegada; ámbar = palabra sin cobertura o error del servidor.

## Seguridad

- Escucha solo en `127.0.0.1`; rechaza cabeceras `Host` y `Origin` ajenas (protección contra
  DNS rebinding y peticiones desde otros sitios).
- Sirve únicamente `index.html`, `app.js` y `estilo.css` desde una lista fija; las corridas se eligen
  por su identificador del manifiesto, nunca por ruta.
- Abre las trazas en modo lectura y no escribe en el repositorio. La simulación escribe solo en su
  carpeta temporal, que se elimina al iniciar otra simulación o al cerrar.
- No acepta comandos: las únicas acciones son «iniciar simulación» (sin parámetros) y
  `{"aprobar": true|false}`. `PUT`, `DELETE` y `PATCH` responden 405.
- Sin API: en este proceso se bloquean el modelo real, la lectura de la clave y `urllib`, y se quitan
  `ANTHROPIC_API_KEY` y `ANTHROPIC_WORKSPACE_ID` del entorno antes de arrancar los subprocesos MCP.
- Las rutas locales y cualquier texto con forma de clave se sustituyen antes de enviarse al navegador.
- Política de contenido (CSP) `default-src 'self'`: sin recursos externos. Los únicos enlaces externos
  son los de las entradas del diccionario (`lesco.cenarec.go.cr`) que ya están en la evidencia; requieren
  conexión para abrirse.

## Pruebas

```powershell
python -m unittest discover -s tests            # 189 pruebas del agente, MCP y evaluación
python -m unittest discover -s demo_web/tests   # 86 pruebas de la demo web (ninguna llama a la API real)
```

Cubren: solo `127.0.0.1`, `Host`/`Origin` ajenos, métodos de escritura, lista blanca de archivos,
identificadores de corrida maliciosos, las 288 corridas sin la traza excluida del HTTP 401, lectura sin
modificación (SHA-256), flujo completo de la simulación con aprobación y rechazo, carpeta temporal
fuera del repositorio y eliminada al cerrar, bloqueo de la API, ocultación de rutas y claves, y que
cada control de la interfaz tenga su acción. `test_voz.py` cubre el modo de voz:

- validación del texto (vacío, largo, caracteres de control, rutas, comandos);
- reglas del motor y que cada ID provenga de una coincidencia exacta real;
- aprobación, rechazo sin reintento y órdenes dictadas tratadas como datos;
- carpeta temporal, sin rutas privadas y restauración del agente;
- una ejecución a la vez y que la simulación quede igual después de usar la voz.

`test_visor_cenarec.py` cubre el visor:

- desactivado por defecto;
- `frame-src` exclusivo del dominio oficial y base exacta;
- página de prueba local sin video ni recursos externos;
- solo `idw` enteros del índice;
- glosa escapada;
- textos obligatorios y controles;
- sin `iframe` en el HTML inicial;
- dirección construida solo desde la evidencia;
- sin reproducción automática ni duraciones;
- sin afirmar una carga verificada.

Los ensayos visuales (1920×1080 y 1280×720, con un navegador sin interfaz) se hicieron fuera del
repositorio y no forman parte de estas pruebas.

## Riesgos residuales

- **Micrófono:** el dictado con un micrófono real solo se probó a mano; el reconocimiento lo hace el
  navegador y puede usar servicios externos (se avisa antes de activarlo).
- **Motor de reglas:** no lematiza ni une expresiones; da más SIN_COBERTURA que el agente, a propósito.
- **IA real:** resultados variables entre ejecuciones; el tope de tokens es aproximado (estimación
  conservadora de la entrada); el gasto facturado solo lo conoce el proveedor; el tope de 5 y el
  presupuesto estimado de US$ 1,00 se reinician al reiniciar la demo; un proceso local con acceso al equipo
  podría imitar la interfaz (fuera del modelo de amenaza de una demo local).
- **Visor oficial:** usarlo en público depende de confirmar las condiciones de uso y el permiso de CENAREC;
  el reproductor real dentro del marco (con `sandbox`) se comprobó solo a mano.
- **Textos de aprobación:** la simulación y el motor de reglas registran «aprobada por una persona en la
  interfaz»; el servidor no puede verificar un clic físico (la IA real ya usa «desde la interfaz»).
