# Etapa 1 — Vinculación del servidor MCP al caso autorizado (`--caso`)

> Registro técnico-científico. Estado: **borrador pendiente de revisión del autor**.
> Las cifras de resultados proceden de registros con salida original conservada (sección 8). Los
> hechos sin evidencia original se marcan "consta en la sesión".
> **Los registros originales están en `evidencia/privado/`, que no está versionada ni publicada.
> Divulgar cualquier evidencia requiere revisión humana y aprobación explícita del autor**
> (estado actual: PENDIENTE_REVISION_HUMANA).

## 1. Objetivo y alcance

**Objetivo:** impedir que una ejecución del agente escriba el resultado de un caso distinto del que
se le asignó. Sin esa garantía, el resultado de un caso puede contaminar la puntuación de otro.

**Alcance de la etapa 1:** solo el servidor MCP (`mcp_server/servidor_lesco.py`, v0.1.0 → v0.2.0) y
sus pruebas (`tests/test_servidor_mcp.py`).

**Fuera de alcance:** el agente y las configuraciones A, B y demo todavía **no** arrancan el servidor
con `--caso`. Eso es la etapa 2, que no está implementada. Por eso la protección **no está activa
todavía en el experimento**.

## 2. Requisitos y trazabilidad

IDs y textos tomados de `PLAN_PROYECTO.md` §1. La columna "Aporte" es una interpretación del
proyecto, no un texto de la especificación.

| ID | Texto en PLAN_PROYECTO.md §1 (resumido) | Aporte de la etapa 1 |
|---|---|---|
| NN3 | Resultados reproducibles: toda cifra del artículo debe regenerarse desde las trazas entregadas | Que un resultado guardado corresponda al caso al que se atribuye |
| NN4 | Ningún dato personal real sin anonimizar en repositorio, trazas ni artículo | Las pruebas usan casos sintéticos en carpetas temporales |
| NN5 | Uso de IA declarado: para qué se usó y cómo se verificó el resultado | Sección 11 |
| S2 | ≥ 3 herramientas, ≥ 1 de escritura, validación del lado del servidor; rechazos con mensajes útiles | Validación de `caso_id` contra el caso autorizado al arrancar |
| S7 | ≥ 5 ataques de inyección indirecta; defensas en la skill **y** en el código | Una defensa en el código, limitada a la escritura y la lectura de casos. **No** cubre los 5 ataques, que siguen pendientes (F7) |
| S8 | Un comando regenera los resultados; README; verificación en una máquina limpia | Pruebas registradas con su salida original. La verificación en máquina limpia está **pendiente** |

## 3. Arquitectura y funcionamiento de `--caso`

**El problema, diagnosticado leyendo el código (consta en la sesión):**
- `guardar_resultado` aceptaba cualquier `caso_id` con formato válido.
- El ejecutor de casos usa una carpeta de salidas compartida por configuración y repetición.
- El `caso_id` lo escribe el modelo, y la política solo decide por el nombre de la herramienta.
- Así, una instrucción en la transcripción del caso X podía hacer que se guardara `Y.json`.

**La corrección (servidor v0.2.0):**
- Argumento opcional `--caso <id>`, validado **al arrancar**. Exige `--casos`, un formato válido y un
  caso que exista; si no se cumple, el servidor termina con código 2 (falla cerrado).
- Con `--caso`, el servidor solo expone la transcripción de ese caso.
- Con `--caso`, `guardar_resultado` rechaza cualquier otro `caso_id` con el mensaje
  "este servidor solo puede guardar el caso '<id>' (autorizado al iniciar el servidor)".
- El control de formato (rutas, longitud) se aplica **antes** que el de vinculación.
- La comparación es exacta: `C1` ≠ `c1`. Esto cierra también la colisión de nombres de archivo en
  Windows, donde no se distinguen mayúsculas.
- **Sin `--caso`**, el comportamiento es el de la v0.1.0. Se mantuvo así por compatibilidad con las
  12 pruebas existentes y con el uso del servidor por separado.

**Lo que no cambió:** descripciones y esquemas de las herramientas, política de permisos y
comparación A/B.

**Alcance de la protección:** las pruebas verifican **solo** el comportamiento del servidor cuando
se arranca con `--caso`. Comprueban que:
- rechaza guardar otro caso;
- no entrega otras transcripciones;
- no arranca con un caso inválido.

**No** demuestran resistencia general a la inyección de instrucciones. **No** protegen al agente
mientras este no arranque el servidor con `--caso` (etapa 2). **No** cubren otros efectos de una
instrucción inyectada, por ejemplo una secuencia de señas incorrecta guardada para el caso correcto.

## 4. Procedimiento de pruebas y entorno

- **Pruebas:** `unittest`, solo biblioteca estándar. El servidor se arranca como subproceso y se
  comunica por stdio, con casos sintéticos en carpetas temporales. Sin red ni API.
- **Registro:** `evidencia/registrar_pruebas.py` v1.2.1, validado antes de usarlo (V1–V4, sección 9).
  - Solo ejecuta suites `unittest` cerradas.
  - Usa un entorno sin credenciales y una guardia de red **parcial** (solo procesos Python).
  - Guarda stdout, stderr, `cambios.patch`, las fuentes sin seguimiento, los metadatos y SHA-256.
  - Comprueba que no cambien el código ni los datos protegidos.
- **Entorno registrado:** CPython 3.12.10, Windows-11-10.0.22631-SP0, salida en UTF-8
  (`PYTHONIOENCODING`), rama `main`, base `e495b062492cb34e073fb99bb283f38924c0d30c`, más los cambios
  sin commit de `cambios.patch`.

## 5. Inventario de las 19 pruebas

Fuente única de los resultados: `stderr.txt` del registro D3a (SHA-256
`45709c1e0ab2d38633a29d18a956ba2844e680fc19cf987e7d8658e1856682a5`).

| # | Prueba | Clase | Qué comprueba | Resultado (D3a) |
|---|---|---|---|---|
| 1 | test_inicializacion | TestServidorMCP | Responde a `initialize` con nombre y capacidades | ok |
| 2 | test_catalogo_con_esquemas_estrictos | TestServidorMCP | 4 herramientas, sin campos extra, con descripción de uso | ok |
| 3 | test_metodo_desconocido | TestServidorMCP | Rechaza métodos no soportados | ok |
| 4 | test_herramienta_desconocida | TestServidorMCP | Rechaza herramientas inexistentes | ok |
| 5 | test_transcripcion_sin_etiquetas_de_referencia | TestServidorMCP | No expone etiquetas de referencia | ok |
| 6 | test_transcripcion_de_caso_inexistente | TestServidorMCP | Rechaza un caso inexistente | ok |
| 7 | test_buscar | TestServidorMCP | Búsqueda en el léxico | ok |
| 8 | test_argumento_no_permitido | TestServidorMCP | Rechaza argumentos extra | ok |
| 9 | test_argumento_faltante | TestServidorMCP | Rechaza argumentos faltantes | ok |
| 10 | test_guardar_una_sola_vez | TestServidorMCP | No sobrescribe (modo sin vincular) | ok |
| 11 | test_guardar_rechaza_ids_inventados | TestServidorMCP | Rechaza IDs inexistentes | ok |
| 12 | test_guardar_rechaza_rutas | TestServidorMCP | Rechaza rutas e IDs mal formados | ok |
| 13 | test_p1_guarda_caso_autorizado | TestServidorVinculado | Guarda el caso autorizado | ok |
| 14 | test_p2_transcripcion_del_caso_autorizado | TestServidorVinculado | Entrega la transcripción autorizada | ok |
| 15 | test_n1_rechaza_guardar_otro_caso | TestServidorVinculado | Rechaza `c2` y `C1`; no crea archivos ajenos | ok |
| 16 | test_n2_rechaza_guardar_caso_inexistente | TestServidorVinculado | Rechaza `c999` (formato válido, no autorizado) | ok |
| 17 | test_n3_no_entrega_transcripcion_de_otro_caso | TestServidorVinculado | No entrega ni filtra el texto de otro caso | ok |
| 18 | test_n4_no_arranca_con_caso_invalido_o_inexistente | TestServidorVinculado | Código 2, mensaje en stderr, stdout vacío (5 situaciones) | ok |
| 19 | test_n5_mantiene_rechazo_de_formato_invalido | TestServidorVinculado | El formato se valida antes que la vinculación | ok |

Resumen literal: `Ran 19 tests in 1.482s` / `OK` (19 ok, 0 FAIL, 0 ERROR).

## 6. Ejecuciones históricas frente a la verificación posterior D3a

### 6.1 Ejecuciones reportadas en la sesión (sin salida original; no son mediciones verificadas)

| | Ejecución A | Ejecución B |
|---|---|---|
| Comando reportado | `python -m unittest tests.test_servidor_mcp -v` | El mismo |
| Resultado reportado | 12 pruebas, OK | 19 pruebas, OK |
| Estado del código | Servidor nuevo, sin docstring ni pruebas nuevas (no conservado) | Con docstring y las 7 pruebas (no verificable) |
| Fecha | 2026-11-13, sin hora | 2026-11-13, sin hora |

No se citan duraciones ni otros datos de estas ejecuciones. No se usan como resultado.

### 6.2 Verificación posterior registrada (salida original conservada)

| | D3a |
|---|---|
| Registro | `20261113-190735_servidor-mcp-verificacion-posterior` |
| Inicio–fin | 2026-11-13T19:07:35-06:00 – 19:07:38-06:00 |
| Resumen literal (de `stderr.txt`) | `Ran 19 tests in 1.482s` / `OK` |
| Código | Base `e495b062492cb34e073fb99bb283f38924c0d30c` + `cambios.patch` (SHA-256 `008c9ca9d991d3fb20c79819fd8aeb7fd35debea9ae34207d942796623306d41`) |
| Uso en el artículo | Es la evidencia citable de la etapa 1 |

## 7. Relación con la línea base D3b

- D3b ejecutó la suite completa (`python -m unittest discover -s tests -v`): **55 pruebas**, de las
  cuales **19 son las de este informe** (módulo `test_servidor_mcp`) y **36** son de otros módulos
  (`lexico` 14, `eval` 9, `puntuar` 9, `agente_simulado` 4).
- D3a y D3b usaron el **mismo código**. Coinciden:
  - el SHA-256 de `cambios.patch`: `008c9ca9d991d3fb20c79819fd8aeb7fd35debea9ae34207d942796623306d41`;
  - los hashes del código registrados en `codigo_sha256_lf_antes` (SHA-256 con finales de línea
    normalizados a LF) de `mcp_server/servidor_lesco.py`:
    `416dbd6711bfffb5e3bb6963ff7d06febc5948f8c733d025c060628278063008`;
  - y de `tests/test_servidor_mcp.py`:
    `e3643274b558dcd7f7e1b9835a5481df3a759deb673b2f7cb11a98fbedcd0962`.
- **Interpretación correcta:** D3b muestra que, con la etapa 1 aplicada, las 36 pruebas de otros
  módulos también pasan (no hay regresiones observadas). El total es 55, no 55 + 19.

## 8. Registros de evidencia

Los cuatro registros mencionados están **solo** en `evidencia/privado/` (ignorada por git) y no
están publicados ni versionados. Cada registro contiene una candidata de publicación generada
mediante controles automáticos. Los registros D3a y D3b no presentan redacciones ni exclusiones;
ninguna candidata ha recibido aprobación humana. `evidencia/pruebas/` y `evidencia/APROBACIONES.md`
no existen.

| Registro | Tipo | Suite | Inicio–fin | Instrumento | Resultado | Integridad operativa | Sello original | Sello candidata |
|---|---|---|---|---|---|---|---|---|
| `20261113-190735_servidor-mcp-verificacion-posterior` (D3a) | verificacion_posterior | servidor | 19:07:35–19:07:38 (-06:00) | v1.2.1 | OK (19) | CONFORME | `204bdb5311adf8a0c2991201b9f8bc442d9ec016dd27d9da31d8d5c08cee5eba` | `a87819a1a9fd22b1668098719af192e868054740c6bb1b964442289422788315` |
| `20261113-191307_suite-completa-linea-base` (D3b) | ejecucion | completa | 19:13:07–19:13:11 (-06:00) | v1.2.1 | OK (55) | CONFORME | `02139288c827c3f86088017491d26fafe12e14281963aae98ec6b2302d77d493` | `1bef915c839930aa3acf0454aef4b3f0ee5cd0917ea9b49f09b5479a6a572f7b` |

**Verificación de ambos registros:** `registrar_pruebas.py verificar` dio integridad criptográfica
VERIFICADA y operativa CONFORME, con 0 discrepancias en el SHA-256 independiente (`Get-FileHash`).

**SHA-256 de stderr:**
- D3a: `45709c1e0ab2d38633a29d18a956ba2844e680fc19cf987e7d8658e1856682a5`
- D3b: `90d64cfd2fc97bfc74ff840a728d0c5b02630a3ee410db048121d08f7b1fd198`

**Registros de validación del instrumento** (no son evidencia del servidor):
- `20261113-184408_registrador-validacion` (v1.2.0);
- `20261113-185833_registrador-validacion-v121` (v1.2.1).

## 9. Errores, correcciones y decisiones (constan en la sesión, salvo indicación)

1. **Contaminación entre casos.** Detectada por inspección estática; corregida con `--caso` (servidor v0.2.0).
2. **Aplicación parcial del diff.** La edición del docstring se rechazó al momento de aplicarla y se
   autorizó y aplicó después. No afectó al comportamiento.
3. **Instrumento de evidencia, v1.1.0 → v1.2.0.** La revisión estática encontró cinco defectos:
   - sello del original dependiente de la candidata;
   - contenido binario no tratado;
   - autorización vacía aceptada;
   - git podía reescribir `.git/index`;
   - entorno sin el directorio personal.
4. **Falso positivo en la v1.2.0**, observado en el registro `20261113-184408_registrador-validacion`:
   - las fuentes del instrumento se excluyeron por mencionar el texto "GIT binary patch";
   - corregido en la v1.2.1 con una detección específica de parches binarios y 3 pruebas de regresión;
   - el registro de la v1.2.0 se conserva sin cambios.
5. **`--verifica` en D3a.** El comando autorizado no incluía `--verifica`, y el instrumento lo exige
   con `--tipo verificacion_posterior`.
   - Se detectó **antes de ejecutar**.
   - El autor eligió el texto.
   - El registro D3a se ejecutó **una sola vez**, ya con ese parámetro.
   - No hubo ninguna ejecución fallida ni ningún registro descartado por este motivo.
   - Texto registrado: "Etapa 1 (servidor MCP --caso): ejecuciones del 2026-11-13 reportadas solo en
     la sesion (12/12 y 19/19), sin salida original".
6. **Decisiones:**
   - `--caso` opcional en el servidor; la obligatoriedad se trasladará al agente en la etapa 2;
   - no exigir `texto_fuente` idéntico a la transcripción, para no introducir un factor de confusión en A/B;
   - no cambiar las descripciones de las herramientas.

## 10. Limitaciones, amenazas a la validez y reproducibilidad

- **Protección no activa en el experimento** hasta implementar y verificar la etapa 2.
- **Alcance de la validez:** pruebas unitarias deterministas del servidor. No miden el comportamiento
  del modelo real (pendiente: F7).
- **Un solo entorno y sin verificación independiente:** Windows-11-10.0.22631-SP0, CPython 3.12.10,
  una máquina. **No se ha validado en un clon limpio** ni lo ha ejecutado una segunda persona.
- **Estado sin commit:** el código probado se identifica con la base `e495b06…` + `cambios.patch`.
  Hasta el commit, la integridad depende de SHA-256 guardados solo en local.
- **`.env` presente durante D3b:**
  - en un clon sin `.env`, `test_cabecera_de_workspace_opcional` (de `test_agente_simulado.py`, que
    no forma parte de las 19) tomaría la otra rama;
  - según el código debería pasar, pero no se ha ejecutado;
  - D3a no incluye esa prueba.
- **Guardia de red parcial:**
  - solo cubre procesos Python;
  - no cubre programas que no sean Python, código nativo ni procesos lanzados con `-I`, `-E` o `-S`;
  - que no haya llamadas a la API se apoya en la lista cerrada de suites y en la revisión del código,
    no en un aislamiento de red.
- **Ejecuciones A y B sin evidencia original** (sección 6.1).

**Procedimiento de reproducción, en un directorio aislado y nunca en el repositorio de trabajo:**
1. Clonar el repositorio en una carpeta temporal nueva, por ejemplo
   `git clone <url-del-repositorio> <carpeta-temporal>/lesco-verif`.
2. Dentro de **esa** copia: `git checkout e495b062492cb34e073fb99bb283f38924c0d30c`.
3. Aplicar `cambios.patch` del registro D3a: `git apply <ruta>/cambios.patch`. El patch solo será
   accesible si se aprueba la publicación de la candidata; mientras tanto, solo el autor puede
   hacerlo con el original privado.
4. Ejecutar `python -m unittest tests.test_servidor_mcp -v`. Se esperan 19 `ok`.
5. Comparar los hashes del código con `codigo_sha256_lf_antes` del registro y borrar la carpeta
   temporal al terminar.

## 11. Uso de IA

**Herramienta:** Claude Code. No se indica el modelo concreto porque no consta en la evidencia del proyecto.

**Lo que hizo Claude Code:**
- diagnosticar la vulnerabilidad por inspección estática;
- proponer los diffs;
- escribir el código del servidor, de las pruebas y del instrumento de evidencia;
- ejecutar las pruebas y verificaciones autorizadas e informar de sus resultados;
- redactar este documento.

**Lo que hizo el autor, según consta en la sesión:**
- **Autorizó comandos:** cada modificación de archivos y cada ejecución se autorizó explícitamente,
  una a una, antes de hacerse.
- **Revisó propuestas y resultados:** revisó los diffs propuestos (en algunos casos pidió cambios,
  por ejemplo el mensaje de rechazo de `guardar_resultado` y dos aserciones de una prueba) y los
  informes de resultados que entregó Claude Code.
- **Verificó directamente:** no consta que el autor haya ejecutado por su cuenta pruebas,
  verificaciones de SHA-256 ni reproducciones.

**Cómo se verificó el trabajo asistido:**
- pruebas automatizadas con su salida original registrada;
- SHA-256 recalculados con una herramienta distinta del instrumento (`Get-FileHash`);
- una prueba de manipulación sobre una copia (V4).

Todas esas verificaciones las ejecutó Claude Code con autorización del autor. **Falta una
verificación independiente** (ver sección 10).

La declaración formal del proyecto se mantiene en `docs/uso_de_ia.md`.

## 12. Relación con el artículo

| Sección del artículo | Uso de esta etapa |
|---|---|
| Sistema propuesto | Servidor MCP y defensa del código: validación de `caso_id` y falla cerrado |
| Metodología | Protocolo de registro de pruebas, entorno e integridad de los resultados por caso |
| Discusión: amenazas a la validez | Riesgo de contaminación entre casos, corregido antes del experimento |
| Apéndice: reproducción | Commit base, patch, comando y hashes de D3a y D3b |
| Declaración de uso de IA | Sección 11 |

## 13. Afirmaciones y su evidencia

| Afirmación | ¿Se puede afirmar? | Evidencia |
|---|---|---|
| Arrancado con `--caso`, el servidor rechaza `guardar_resultado` para un `caso_id` distinto del autorizado (probado con `c2`, `C1` y `c999`) | **Sí**, para esos casos | D3a: `test_n1_rechaza_guardar_otro_caso`, `test_n2_rechaza_guardar_caso_inexistente` |
| Arrancado con `--caso`, el servidor no entrega la transcripción de otro caso ni filtra su texto en el error | **Sí**, para el caso probado | D3a: `test_n3_no_entrega_transcripcion_de_otro_caso` |
| El servidor no arranca con `--caso` inexistente, `../x`, vacío, de 41 caracteres o sin `--casos` | **Sí**, para esas 5 entradas | D3a: `test_n4_no_arranca_con_caso_invalido_o_inexistente` |
| Sin `--caso`, el servidor mantiene el comportamiento que cubren las 12 pruebas originales | **Sí**, limitado a esas pruebas | D3a: pruebas 1–12 |
| Con la etapa 1 aplicada, pasan las 55 pruebas de la suite (19 MCP + 36 de otros módulos) | **Sí**, en ese entorno y estado de código | D3b |
| El experimento A/B está protegido contra la contaminación entre casos | **No** | Requiere la etapa 2 |
| El agente o el modelo resisten la inyección de instrucciones | **No se ha medido** | Pendiente: F7 |
| Las pruebas se reproducen en un clon limpio | **No verificado** | Pendiente |
| Las 19 pruebas pasaron en las ejecuciones A y B | **Solo consta en la sesión** | Sin salida original |
| La evidencia es pública y está sellada en git | **No** | PENDIENTE_REVISION_HUMANA; sin commit |

## 14. Datos no verificables o pendientes de confirmar

- **Ejecuciones A y B:** su hora, entorno y estado exacto del código (§6.1).
- **Modelo concreto de Claude Code:** no consta en la evidencia del proyecto.
- **Rama sin `.env` de `test_cabecera_de_workspace_opcional`:** no se ha ejecutado.
- **Correspondencia exacta entre "Aporte" y requisito:** la columna "Aporte" de §2 es una
  interpretación del proyecto; los IDs y textos sí coinciden con `PLAN_PROYECTO.md` §1.
- **URL del repositorio para el clon:** se deja como marcador (`<url-del-repositorio>`). La
  publicación y el commit no están hechos.
