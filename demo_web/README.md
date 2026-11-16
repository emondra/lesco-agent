# Visor web local de LESCO-Agent

Interfaz web **local** para mostrar el funcionamiento de la arquitectura Agente + Skill + MCP. Usa solo
la biblioteca estándar de Python, funciona sin conexión a Internet y **no llama a la API**.

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

En la simulación, los turnos del «modelo» son un **guion fijo**: no son decisiones autónomas. Lo que sí
es real es el servidor MCP (búsqueda y validación contra el índice CENAREC), la política del host, la
aprobación humana pedida desde la interfaz y la traza.

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
python -m unittest discover -s demo_web/tests -v
```

Cubren: solo `127.0.0.1`, `Host`/`Origin` ajenos, métodos de escritura, lista blanca de archivos,
identificadores de corrida maliciosos, las 288 corridas sin la traza excluida del HTTP 401, lectura sin
modificación (SHA-256), flujo completo de la simulación con aprobación y rechazo, carpeta temporal
fuera del repositorio y eliminada al cerrar, bloqueo de la API, ocultación de rutas y claves, y que
cada control de la interfaz tenga su acción.
