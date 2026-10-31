# Registro de uso de IA

Condición no negociable 5: se declara para qué se usó IA y cómo se verificó el resultado. Este
registro alimenta la declaración de uso de IA del artículo.

| Fecha | Herramienta | Para qué | Cómo se verificó |
|---|---|---|---|
| 2026-10-31 | Claude Code (`claude-opus-5-5`) | Extraer los requisitos de la especificación del proyecto y compararlos con la propuesta inicial; redactar `PLAN_PROYECTO.md`, `README.md` y `TODO.md`. | El autor revisó y aprobó el plan y las decisiones D3, D5, D9 y D11. |
| 2026-10-31 | Claude Code (búsqueda web) | Buscar fuentes del vocabulario LESCO y estimar el presupuesto de la API. | Cada fuente se abrió y se registró con su URL y fecha en `docs/referencias.md`. El presupuesto es una estimación previa que se recalibrará con trazas. |
| 2026-11-01 | Claude Code (`claude-opus-5-5`, búsqueda web) | Redactar el borrador de `docs/propuesta_H1.md` y verificar los metadatos de las referencias candidatas. | Metadatos comprobados en las páginas de los editores o de arXiv. La lectura de cada referencia la registra el autor. |

## Usos previstos (se registrarán al ocurrir)

- Programación del servidor MCP, el agente y los scripts (con pruebas automáticas).
- Segundo anotador del conjunto de evaluación (`claude-opus-5-5`, autorizado por el profesor).
- Apoyo de redacción del artículo (el autor revisa cada sección y cada cifra contra las trazas).

**Nunca:** generar entradas del vocabulario LESCO ni referencias bibliográficas.
