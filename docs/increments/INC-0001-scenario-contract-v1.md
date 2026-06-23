# INC-0001 — Scenario contract v1

## Estado

Aceptado y cerrado.

## Objetivo

Implementar un contrato versionado de escenario que represente de forma explícita y validable el caso concreto que se quiere analizar, separando:

- proceso funcional;
- punto de entrada;
- inputs observados;
- bindings entre inputs y propiedades;
- valores calculados durante la ejecución;
- flags;
- configuración;
- alcance manual del análisis;
- notas;
- procedencia;
- estado de conocimiento;
- referencias a fuentes.

Además, implementar un adaptador desde el formato legacy `peoplenet_call.json`.

## Motivación

El formato legacy mezclaba en un único fichero:

- inputs capturados desde Chrome;
- flags añadidos o corregidos manualmente;
- valores intermedios calculados;
- métodos seleccionados manualmente;
- proceso funcional;
- propiedades;
- notas técnicas.

Esta mezcla dificultaba distinguir:

- hechos observados;
- valores derivados;
- decisiones manuales;
- información desconocida;
- valores runtime;
- alcance del análisis;
- evidencias y procedencia.

El incremento crea una base estable para futuros análisis de ramas, dependencias y valores.

## Resultado implementado

- Contrato versionado `scenario-v1`.
- Versión de esquema `1.0`.
- Modelo de datos basado en tipos estructurados.
- Separación entre:
  - `process`;
  - `entry_point`;
  - `entry_inputs`;
  - `property_bindings`;
  - `runtime_values`;
  - `flags`;
  - `configuration`;
  - `analysis_scope`;
  - `notes`;
  - `source_files`.
- Catálogos cerrados de procedencia y estado.
- Adaptador desde `peoplenet_call.json`.
- Parsing del método de entrada y sus argumentos.
- Informe estructurado de migración.
- Validación determinista.
- Serialización JSON estable y round trip sin pérdida.
- CLI de migración.
- Fixtures anonimizados.
- Golden test revisado manualmente.
- Documentación del esquema, arquitectura y decisión técnica.

## Alcance entregado

### Modelo

El modelo representa:

- identificador del escenario;
- proceso funcional;
- punto de entrada;
- argumentos del método;
- inputs observados;
- bindings;
- valores runtime;
- flags;
- configuración;
- alcance de métodos;
- notas;
- referencias a fuentes.

### Procedencias soportadas

- `frontend_call`
- `sql_query`
- `database_trace`
- `source_code`
- `manual_derivation`
- `default`
- `unknown`

### Estados soportados

- `observed`
- `derived`
- `assumed`
- `unknown`
- `not_applicable`

### Migración legacy

Se migran los campos:

- `meta4object`;
- `nodo`;
- `metodo`;
- `proceso`;
- `metodos`;
- `flags`;
- `inputs`;
- `propiedades`;
- `notas`.

Los campos legacy desconocidos se reportan y no se ignoran silenciosamente.

## Comportamiento relevante

### Inputs observados

Los valores del bloque legacy `inputs` se clasifican como:

```text
source = frontend_call
status = observed
```

### Flags

Los flags legacy se clasifican inicialmente como:

```text
source = manual_derivation
status = derived
```

### Alcance manual

Los métodos legacy de `metodos` se trasladan a `analysis_scope.methods`.

### Bindings a valores no observados

Un binding como:

```json
{
  "propiedad": "GLB_COND_HOR_SRZ",
  "input": "P_14"
}
```

se conserva aunque `P_14` no aparezca en los inputs observados.

El sistema:

- no falla;
- emite un warning;
- no crea un valor `null`;
- no inventa un runtime value.

### Coherencia del proceso

Si `process.id` y `P_ID_FLUJO` no coinciden:

- la migración falla;
- se genera un único error `process_id_mismatch`;
- no se genera el escenario;
- el informe se genera si fue solicitado.

## CLI implementada

Comando canónico:

```bash
uv run peoplenet-process-extractor scenario migrate \
  tests/fixtures/scenarios/legacy_peoplenet_call.json \
  --output scenario.json \
  --report migration-report.json
```

También se mantiene el alias top-level de migración cuando corresponda.

La CLI:

- devuelve códigos de salida coherentes;
- no sobrescribe sin `--force`;
- escribe escenario e informe de forma coordinada;
- evita outputs parciales;
- genera el informe también en errores bloqueantes cuando es posible;
- no muestra tracebacks ante errores de validación esperados.

## Serialización

La salida:

- es JSON UTF-8;
- utiliza indentación estable;
- termina con salto de línea;
- conserva tipos JSON;
- no introduce timestamps ni identificadores aleatorios;
- permite round trip sin pérdida;
- preserva el orden original de las colecciones legacy.

Los campos opcionales estables del esquema se serializan siempre:

- los escalares sin valor se representan como `null`;
- las colecciones vacías se representan como `[]` o `{}`.

## Orden de colecciones

Se conserva el orden original de:

- inputs;
- flags;
- bindings;
- métodos.

La finalidad es mantener trazabilidad con la captura original.

El determinismo se garantiza para la misma entrada textual. Dos JSON semánticamente equivalentes, pero con distinto orden, pueden producir outputs ordenados de forma diferente.

La canonicalización queda fuera de alcance de esta versión.

## Parsing del método

Se soportan llamadas simples con:

- nombre de método;
- paréntesis;
- argumentos literales;
- strings;
- números;
- booleanos;
- `null`.

Ejemplo:

```text
GLB_M_PC_EXE("STEP_SAVE")
```

se transforma en:

```json
{
  "method": "GLB_M_PC_EXE",
  "arguments": ["STEP_SAVE"]
}
```

Los escapes no soportados se rechazan explícitamente. No se implementa un parser general de LN4.

## Fuera de alcance confirmado

- Análisis de código LN4.
- Parser completo de LN4.
- Descubrimiento de llamadas.
- Grafo de dependencias.
- Cálculo automático de flags.
- Evaluación de ramas.
- Seguimiento completo de variables.
- Procesamiento de trazas SQL.
- Correlación código-traza.
- Generación de Markdown funcional.
- Integración con `meta4_ai_tools`.
- Acceso a SQL Server.
- Persistencia en base de datos.
- API REST.
- Interfaz gráfica.
- Soporte de múltiples versiones del esquema.

## Decisiones finales

- El escenario es un contrato independiente del Markdown.
- El modelo está versionado mediante `schema_version`.
- Se mantiene compatibilidad con el formato legacy mediante adaptador.
- La procedencia y el estado son explícitos.
- Los inputs observados se separan de los valores runtime.
- Los flags se separan del contrato de entrada.
- El alcance manual se separa del punto de entrada.
- Los bindings a inputs no observados no implican valor nulo.
- Los errores estructurales son bloqueantes.
- La salida es determinista para la misma entrada textual.
- No se añaden dependencias externas innecesarias.
- La biblioteca estándar es suficiente para este incremento.

## Criterios de aceptación

| Criterio | Estado | Evidencia |
|---|---|---|
| Contrato `scenario-v1` | Cumplido | `docs/schemas/scenario-v1.md` |
| Versión explícita `1.0` | Cumplido | Modelo y validación |
| Separación de conceptos | Cumplido | Modelos de escenario |
| Procedencias cerradas | Cumplido | Enums y validación |
| Estados cerrados | Cumplido | Enums y validación |
| Adaptador legacy | Cumplido | Módulo de migración |
| Conservación de campos conocidos | Cumplido | Tests de migración |
| Reporte de campos desconocidos | Cumplido | `MigrationReport` |
| Parsing de método y argumentos | Cumplido | Tests de parsing |
| Inputs observados correctamente clasificados | Cumplido | Tests de migración |
| Flags correctamente clasificados | Cumplido | Tests de migración |
| Bindings no observados conservados | Cumplido | Tests específicos |
| Sin runtime values inventados | Cumplido | Tests específicos |
| Mismatch de proceso bloqueante | Cumplido | Tests y CLI |
| Informe estructurado | Cumplido | Modelo y serialización |
| CLI operativa | Cumplido | Tests y ejecución manual |
| Salida determinista | Cumplido | Tests de serialización |
| Round trip sin pérdida | Cumplido | Tests de serialización |
| Fixtures anonimizados | Cumplido | `tests/fixtures/scenarios/` |
| Golden test revisado manualmente | Cumplido | Test y fixture expected |
| Sin análisis LN4 | Cumplido | Alcance preservado |
| Tests y lint | Cumplido | Verificación final |

## Verificación final

```bash
uv run pytest -q
uv run ruff check .
uv run peoplenet-process-extractor --help
uv run peoplenet-process-extractor scenario migrate --help
git diff --check
git ls-files "*.pyc"
git ls-files "*__pycache__*"
```

Resultado final:

- Tests: `98 passed` antes de las correcciones y suite ampliada en verde al cierre.
- Ruff: `All checks passed`.
- Codex: `Aceptada`.
- Sin `.pyc` ni `__pycache__` versionados.

## Revisiones realizadas

1. Implementación inicial por Claude Code.
2. Revisión independiente por Codex.
3. Corrección de:
   - validación de `source` y `status`;
   - duplicación de `process_id_mismatch`;
   - escritura parcial de outputs;
   - console script del paquete;
   - política de opcionales;
   - revisión manual del golden;
   - documentación del orden;
   - tratamiento de escapes;
   - generación del informe en fallos bloqueantes;
   - retirada de artefactos `.pyc`.
4. Comprobación final de Codex: aceptada.

## Limitaciones conocidas

- El parser solo soporta llamadas simples con argumentos literales.
- No se canonicaliza el orden de colecciones.
- El adaptador no calcula automáticamente flags ni valores runtime.
- La procedencia legacy aplicada por defecto puede requerir confirmación posterior.
- El informe solo refleja la información disponible en la migración.

## Documentación relacionada

- `docs/schemas/scenario-v1.md`
- `docs/decisions/ADR-0001-scenario-contract.md`
- `docs/architecture/pipeline-overview.md`

## Commit

```text
feat: add versioned scenario contract and legacy adapter
```

Commit:

```text
dcf9e37
```

## Fecha de cierre

2026-06-23
