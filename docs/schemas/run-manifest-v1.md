# run-manifest-v1 — Manifiesto de ejecución

## Propósito

El manifiesto de ejecución (`run-manifest.json`) registra de forma reproducible una ejecución concreta del pipeline de extracción. Responde a las preguntas:

- ¿Qué escenario se utilizó?
- ¿Qué ficheros participaron y con qué hashes?
- ¿Qué herramientas produjeron cada artefacto?
- ¿De qué fuentes deriva cada artefacto?
- ¿Cuál fue el estado final de la ejecución?
- ¿Los ficheros siguen coincidiendo con lo registrado?

---

## Estructura

```json
{
  "schema_version": "1.0",
  "run_id": "run-20260623-abc12345",
  "status": "prepared",
  "scenario": { ... },
  "sources": [ ... ],
  "tools": [ ... ],
  "artifacts": [ ... ],
  "events": [ ... ],
  "warnings": [ ... ],
  "errors": [ ... ],
  "started_at": null,
  "finished_at": null
}
```

---

## Versión

Solo se soporta `schema_version = "1.0"`. Una versión distinta genera error de validación.

---

## run_id

Identificador único de la ejecución. Requisitos:

- No vacío.
- Válido como nombre de directorio: `[a-zA-Z0-9][a-zA-Z0-9._-]*`.
- No contiene separadores de ruta ni caracteres especiales de SO.
- Estable durante toda la ejecución.

Si no se proporciona, se genera automáticamente como `run-YYYYMMDD-<8 hex>`.

---

## Estados

Catálogo cerrado:

| Estado      | Significado                                |
|-------------|---------------------------------------------|
| `prepared`  | El run ha sido creado y está listo         |
| `running`   | En ejecución activa                         |
| `succeeded` | Terminó con éxito (incompatible con errores)|
| `failed`    | Terminó con fallos (requiere al menos un error)|
| `cancelled` | Cancelado antes de terminar                 |

---

## Escenario (`scenario`)

Referencia al escenario `scenario-v1` utilizado en el run.

```json
{
  "path": "inputs/scenario.json",
  "sha256": "a3f8c1b2...",
  "size_bytes": 1234,
  "scenario_id": "11-jorn-store-u",
  "schema_version": "1.0"
}
```

- `path`: ruta relativa al directorio del run, con `/`.
- `sha256`: hash SHA-256 de la copia almacenada en `inputs/`.
- `size_bytes`: tamaño en bytes de la copia.
- `scenario_id`: identificador del escenario dentro del contrato `scenario-v1`.
- `schema_version`: versión del contrato del escenario.

---

## Fuentes (`sources`)

Lista de ficheros de entrada que participaron o se esperan en el run.

```json
{
  "id": "scenario",
  "kind": "scenario",
  "path": "inputs/scenario.json",
  "sha256": "a3f8c1b2...",
  "size_bytes": 1234,
  "exists": true,
  "required": true,
  "description": "Scenario v1 used for this run"
}
```

### Campos

| Campo         | Tipo            | Requerido | Descripción                              |
|---------------|-----------------|-----------|------------------------------------------|
| `id`          | string          | sí        | Identificador único en el run            |
| `kind`        | SourceKind      | sí        | Tipo de fuente (ver catálogo)            |
| `path`        | string          | sí        | Ruta relativa al directorio del run      |
| `sha256`      | string \| null  | —         | SHA-256 (requerido si `exists=true`)     |
| `size_bytes`  | int \| null     | —         | Tamaño (requerido si `exists=true`)      |
| `exists`      | boolean         | sí        | Si el fichero existía al crear el run    |
| `required`    | boolean         | sí        | Si el fichero es obligatorio para el run |
| `description` | string \| null  | no        | Descripción opcional                     |

### Catálogo de `kind`

`scenario` · `frontend_call` · `database_trace` · `query_results` · `ln4_source` · `manual_input` · `configuration` · `other`

---

## Herramientas (`tools`)

Lista de herramientas que participaron en el run.

```json
{
  "id": "peoplenet-process-extractor",
  "name": "peoplenet-process-extractor",
  "version": "0.1.0",
  "command": "peoplenet-process-extractor manifest create",
  "git_commit": null,
  "schema_info": null
}
```

| Campo        | Tipo           | Descripción                        |
|--------------|----------------|------------------------------------|
| `id`         | string         | Identificador único en el run      |
| `name`       | string         | Nombre legible                     |
| `version`    | string         | Versión del ejecutable             |
| `command`    | string \| null | Comando invocado (sin rutas abs.)  |
| `git_commit` | string \| null | Commit Git de la herramienta        |
| `schema_info`| string \| null | Info de esquema o configuración    |

No se almacenan rutas absolutas ni información sensible.

---

## Artefactos (`artifacts`)

Lista de salidas que el pipeline produce o planea producir.

```json
{
  "id": "report-migration",
  "kind": "migration_report",
  "path": "reports/migration.json",
  "sha256": "b4e5f6a7...",
  "size_bytes": 2048,
  "producer": "peoplenet-process-extractor",
  "derived_from": ["scenario"],
  "status": "planned"
}
```

| Campo          | Tipo            | Descripción                                |
|----------------|-----------------|--------------------------------------------|
| `id`           | string          | Identificador único en el run              |
| `kind`         | ArtifactKind    | Tipo de artefacto (ver catálogo)           |
| `path`         | string          | Ruta relativa al directorio del run        |
| `sha256`       | string \| null  | SHA-256 (requerido si `status=generated`)  |
| `size_bytes`   | int \| null     | Tamaño (requerido si `status=generated`)   |
| `producer`     | string \| null  | ID de la herramienta que lo produjo        |
| `derived_from` | array[string]   | IDs de fuentes o artefactos predecesores   |
| `status`       | ArtifactStatus  | Estado actual del artefacto                |

### Catálogo de `kind`

`scenario` · `migration_report` · `clean_trace` · `writes_trace` · `intermediate_model` · `validation_report` · `markdown` · `other`

### Catálogo de `status`

| Estado      | Significado                        |
|-------------|-------------------------------------|
| `planned`   | Previsto pero no generado aún       |
| `generated` | Generado correctamente              |
| `failed`    | La generación falló                 |
| `missing`   | Se esperaba pero no se encontró     |

---

## Eventos (`events`)

Registro cronológico de hitos en la ejecución.

```json
{
  "sequence": 1,
  "type": "prepared",
  "timestamp": "2026-06-23T14:30:00Z",
  "message": "Run 'run-20260623-001' prepared",
  "reference_id": null
}
```

| Campo          | Tipo           | Descripción                                       |
|----------------|----------------|---------------------------------------------------|
| `sequence`     | int            | Entero positivo, único, estrictamente creciente por posición en la lista |
| `type`         | EventType      | Tipo de evento (ver catálogo)                     |
| `timestamp`    | string         | ISO 8601 con timezone explícita (`Z` o `+HH:MM`)  |
| `message`      | string         | Mensaje legible                                   |
| `reference_id` | string \| null | ID de fuente, artefacto o herramienta relacionada |

### Catálogo de `type`

`prepared` · `started` · `artifact_generated` · `warning` · `error` · `finished`

---

## Warnings y errores

Entradas estructuradas de advertencias y errores registrados durante la ejecución.

```json
{
  "code": "W001",
  "message": "Descripción del warning",
  "reference_id": null
}
```

| Campo          | Tipo           | Descripción                        |
|----------------|----------------|------------------------------------|
| `code`         | string         | Código de warning/error            |
| `message`      | string         | Mensaje legible                    |
| `reference_id` | string \| null | Entidad relacionada (opcional)     |

---

## Hashes

- Algoritmo: SHA-256.
- Formato: 64 caracteres hexadecimales en minúsculas.
- Los bytes se leen sin normalización: sin decodificación de texto, sin normalización de saltos de línea, sin modificar el fichero.
- Lectura incremental (chunks de 64 KB) para soportar ficheros grandes.

---

## Rutas

- Siempre relativas al directorio del run.
- Siempre con `/` como separador (también en Windows).
- No se almacenan rutas absolutas de la máquina.
- No se permiten componentes `..` (rechazo de path traversal).

---

## Procedencia

- `derived_from` en artefactos: lista de IDs de fuentes o artefactos predecesores.
- `producer` en artefactos: ID de la herramienta que generó el artefacto.
- Las referencias se validan: IDs inexistentes, duplicados y auto-referencias generan error.
- Los IDs de fuentes y artefactos comparten un único espacio de nombres: no puede existir el mismo ID en ambas colecciones.

---

## Timestamps

- Formato: ISO 8601 con timezone explícita → `2026-06-23T14:30:00Z` o `2026-06-23T14:30:00+05:30`.
- Timestamps sin timezone (naives) son rechazados.
- `started_at` / `finished_at`: opcionales (null en estado `prepared`).
- La comparación `finished_at >= started_at` se realiza sobre los valores parseados, no sobre cadenas.
- `finished_at` no puede ser anterior a `started_at`.

---

## Validaciones

| Regla                                                                  | Código de error               |
|------------------------------------------------------------------------|-------------------------------|
| `schema_version` no soportada                                         | `unsupported_schema_version`  |
| `run_id` vacío                                                        | `empty_run_id`                |
| `run_id` con caracteres inválidos                                     | `invalid_run_id`              |
| `status` no válido                                                    | `invalid_run_status`          |
| SHA-256 con formato incorrecto                                        | `invalid_sha256`              |
| Tamaño negativo                                                       | `negative_size`               |
| Ruta absoluta                                                         | `absolute_path`               |
| Separadores no portables (`\`)                                        | `non_portable_path`           |
| Path traversal (`..`)                                                 | `path_traversal`              |
| IDs de fuente duplicados                                              | `duplicate_source_id`         |
| IDs de herramienta duplicados                                         | `duplicate_tool_id`           |
| IDs de artefacto duplicados                                           | `duplicate_artifact_id`       |
| Mismo ID en fuente y artefacto (espacio de nombres global)            | `duplicate_global_id`         |
| Falta fuente con `kind=scenario`                                      | `no_scenario_source`          |
| Más de una fuente con `kind=scenario`                                 | `multiple_scenario_sources`   |
| Fuente scenario con `path` distinto al de `scenario`                  | `scenario_source_path_mismatch` |
| Fuente scenario con `sha256` distinto al de `scenario`                | `scenario_source_sha256_mismatch` |
| Fuente scenario con `size_bytes` distinto al de `scenario`            | `scenario_source_size_mismatch` |
| `derived_from` referencia inexistente                                 | `unknown_derived_from`        |
| `derived_from` referencia duplicada                                   | `duplicate_derived_from`      |
| `derived_from` con auto-referencia                                    | `self_reference_in_derived_from` |
| `producer` inexistente                                                | `unknown_producer`            |
| Secuencia de evento ≤ 0                                               | `invalid_event_sequence`      |
| Secuencia de evento duplicada                                         | `duplicate_event_sequence`    |
| Secuencias no estrictamente crecientes por posición                   | `non_increasing_sequence`     |
| Timestamp de evento sin timezone o con formato inválido               | `invalid_event_timestamp`     |
| `reference_id` de evento inexistente                                  | `unknown_event_reference`     |
| `succeeded` con errores                                               | `succeeded_with_errors`       |
| `failed` sin errores                                                  | `failed_without_errors`       |
| `started_at` o `finished_at` sin timezone o inválido                 | `invalid_timestamp`           |
| `finished_at` anterior a `started_at`                                 | `incoherent_timestamps`       |
| Hash ausente cuando se requiere                                       | `missing_hash`                |
| Tamaño ausente cuando se requiere                                     | `missing_size`                |

---

## Ejemplo completo

```json
{
  "schema_version": "1.0",
  "run_id": "run-20260623-abc12345",
  "status": "prepared",
  "scenario": {
    "path": "inputs/scenario.json",
    "sha256": "a3f8c1b2d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1",
    "size_bytes": 1234,
    "scenario_id": "test-scenario-001",
    "schema_version": "1.0"
  },
  "sources": [
    {
      "id": "scenario",
      "kind": "scenario",
      "path": "inputs/scenario.json",
      "sha256": "a3f8c1b2d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1",
      "size_bytes": 1234,
      "exists": true,
      "required": true,
      "description": "Scenario v1 used for this run"
    }
  ],
  "tools": [
    {
      "id": "peoplenet-process-extractor",
      "name": "peoplenet-process-extractor",
      "version": "0.1.0",
      "command": "peoplenet-process-extractor manifest create",
      "git_commit": null,
      "schema_info": null
    }
  ],
  "artifacts": [],
  "events": [
    {
      "sequence": 1,
      "type": "prepared",
      "timestamp": "2026-06-23T14:30:00Z",
      "message": "Run 'run-20260623-abc12345' prepared",
      "reference_id": null
    }
  ],
  "warnings": [],
  "errors": [],
  "started_at": null,
  "finished_at": null
}
```
