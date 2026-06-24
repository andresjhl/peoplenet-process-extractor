# INC-0005 — Reference Extraction v1

## Estado

**En curso** (rama `feat/reference-extraction-v1` pendiente de integración)

## Identificación

- **Incremento:** INC-0005
- **Nombre:** `reference-extraction-v1`
- **Rama de implementación:** `feat/reference-extraction-v1`
- **Repositorio:** `peoplenet-process-extractor`
- **Resultado:** implementado y validado; pendiente de integración en `main`

---

## Objetivo

Detectar y catalogar de forma determinista, reproducible y verificable todas las expresiones `Call(...)` presentes en los ficheros `structured_ln4` del corpus, produciendo un artefacto JSON canónico que preserve posición exacta, texto original, clasificación de argumentos, estado y diagnósticos.

El incremento se limita a extraer y verificar; no resuelve llamadas ni construye grafo de dependencias.

---

## Motivación

Los incrementos anteriores proporcionaban:

1. `scenario-v1` — modelo de escenario de migración;
2. `run-manifest-v1` — trazabilidad de ejecución con SHA-256;
3. `corpus-manifest-v1` — inventario físico del corpus;
4. `structural-index-v1` — índice SQLite de ficheros y elementos estructurales.

Faltaba el primer paso de análisis de contenido LN4: localizar y catalogar cada `Call()` con evidencia verificable, sin dependencia de herramientas externas de parsing, de modo que:

- las posiciones sean trazables al texto Unicode decodificado del fichero, vinculadas al corpus físico mediante SHA-256;
- el artefacto sea re-verificable de forma independiente;
- los pasos posteriores (resolución, grafo) puedan consumirlo como entrada estable.

---

## Alcance implementado

### Artefacto

Formato: `reference-extraction-v1`, `schema_version = 1`.

Fichero JSON canónico con:

- metadatos del generador y timestamp de creación;
- SHA-256 y tamaño del manifiesto y del índice usados;
- resumen agregado con 10 contadores;
- un registro por cada fichero `structured_ln4`, con sus referencias ordenadas por offset.

### Scanner de estado

Máquina de estados de caracteres con cuatro estados:

```
NORMAL → IN_STRING → NORMAL
NORMAL → IN_LINE_COMMENT → NORMAL
NORMAL → IN_BLOCK_COMMENT → NORMAL
```

Detecta `Call` con verificación de frontera de palabra.
Maneja `Call()` anidados, comentarios de línea (`'`, `//`) y bloque (`/* */`), y literales de cadena.
No normaliza saltos de línea; procesa CRLF directamente.

### Extractor

Módulo `extraction.py`:

- `extract_references()` — entrada pública; valida índice, itera ficheros, escribe atómicamente;
- `_process_file()` — procesa un fichero: hash, encoding, detección de EOL, scan, construcción de `FileResult`;
- `_build_summary()` — agrega 10 contadores a partir de la lista de `FileResult`;
- `_get_index_info()` — lee SHA-256, tamaño y registros `structured_ln4` del índice.

Escritura atómica: `tempfile.mkstemp` + `validate_extraction_model()` sobre el temporal + `os.replace()`.
El temporal se elimina ante cualquier fallo.

### Verificador

Módulo `validation.py`:

- `validate_extraction_model()` — valida campos, contadores y fórmulas de ID del modelo en memoria;
- `_parse_utc_created_at()` — acepta `+00:00` y `Z`; rechaza formato inválido, sin timezone y offsets no UTC;
- `verify_extraction()` — verificación completa; re-extrae en memoria y compara campo a campo.

Resolución de importación circular: `_process_file`, `_build_summary`, `_get_index_info` y `_GENERATOR_VERSION` se importan de `extraction.py` de forma diferida, dentro del cuerpo de `verify_extraction()`.

### Serialización

Módulo `serialization.py`:

- UTF-8 sin BOM;
- 2 espacios de indentación;
- saltos de línea LF;
- newline final.

### CLI

Módulo `cli.py`, subcomandos bajo `references`:

```bash
peoplenet-process-extractor references extract
peoplenet-process-extractor references verify
peoplenet-process-extractor references query
```

### Modelos

Módulo `models.py`:

- `FORMAT = "reference-extraction-v1"`;
- `SCHEMA_VERSION = 1`;
- `GENERATOR_NAME = "peoplenet-process-extractor"`;
- dominios cerrados: `VALID_FILE_STATUSES`, `VALID_STATUSES`, `VALID_KINDS`, `VALID_ARG_KINDS`, `VALID_ERROR_CODES`.

---

## Fuera de alcance

No se implementó:

- resolución de llamadas (`Call(target, method)` → elemento estructural);
- grafo de callers/callees;
- análisis semántico de LN4;
- parsing de gramática completa de LN4;
- almacenamiento en SQLite;
- análisis con LLM;
- actualización incremental del artefacto;
- integración automática con `run-manifest-v1`.

---

## Entradas

| Entrada | Descripción |
|---------|-------------|
| `--corpus-root` | Directorio raíz del corpus LN4 |
| `--corpus-manifest` | Fichero `corpus-manifest-v1` que describe el corpus |
| `--index` | Base SQLite `structural-index-v1` construida a partir del manifiesto |
| `--created-at` | Timestamp UTC ISO-8601 opcional para reproducibilidad byte a byte |

El extractor verifica que el índice fue construido a partir del manifiesto exacto antes de procesar.

---

## Artefacto generado

### Estructura de alto nivel

```json
{
  "format": "reference-extraction-v1",
  "schema_version": 1,
  "generator": { "name": "peoplenet-process-extractor", "version": "..." },
  "created_at": "2026-06-24T12:00:00+00:00",
  "source_manifest": { "sha256": "...", "size_bytes": 1234 },
  "source_index": { "sha256": "...", "size_bytes": 5678 },
  "summary": { ... },
  "files": [ ... ]
}
```

### Resumen — 10 contadores

```json
{
  "files_total": 10,
  "files_processed": 9,
  "files_with_calls": 5,
  "calls_total": 42,
  "observed": 40,
  "partially_parsed": 0,
  "ambiguous": 0,
  "malformed": 2,
  "unsupported": 0,
  "file_errors": 1
}
```

### Registro de fichero

```json
{
  "path": "CP/.../METH#R1#1800_01_01.ln4",
  "source_file_id": 3,
  "source_file_sha256": "abcdef...",
  "encoding": "utf-8",
  "line_ending": "lf",
  "status": "processed",
  "errors": [],
  "references": [ ... ]
}
```

### Registro de referencia

```json
{
  "id": "ref:abcdef...:42:65",
  "kind": "call",
  "function_name": "Call",
  "status": "observed",
  "source_file_id": 3,
  "path": "CP/.../METH#R1#1800_01_01.ln4",
  "source_file_sha256": "abcdef...",
  "start_offset": 42,
  "end_offset": 65,
  "line_start": 5,
  "column_start": 3,
  "line_end": 5,
  "column_end": 25,
  "raw_expression": "Call(nodeId, \"METHOD\")",
  "raw_arguments": "nodeId, \"METHOD\"",
  "arguments": [ ... ],
  "parser_rule": "ln4_call_v1",
  "diagnostics": []
}
```

### ID de referencia

```
ref:{source_file_sha256}:{start_offset}:{end_offset}
```

Offsets 0-based sobre el texto Unicode decodificado; `end_offset` exclusivo.

### Convenciones de posición

- **Offsets:** 0-based; `text[start:end] == raw_expression`.
- **Líneas:** 1-based; `\n` incrementa línea y reinicia columna.
- **Columnas:** 1-based; `\r` se cuenta como carácter de columna, no como salto.

---

## Flujo de extracción

1. Validar que corpus root, manifiesto e índice existen.
2. Calcular SHA-256 y tamaño del manifiesto y del índice.
3. Deserializar el manifiesto y verificar el corpus (ficheros presentes, hashes correctos).
4. Ejecutar `validate_index()` completo sobre el índice.
5. Obtener la lista de ficheros `structured_ln4` del índice.
6. Para cada fichero:
   a. Leer bytes y calcular SHA-256 (error `hash_mismatch` si difiere del índice).
   b. Detectar encoding (`utf-8-bom` si BOM presente; `utf-8` en otro caso).
   c. Decodificar con `utf-8-sig` (suprime BOM si lo hay).
   d. Detectar line endings (`lf`, `crlf`, `mixed`, `none`).
   e. Ejecutar el scanner de estados sobre el texto decodificado.
   f. Construir objetos `Reference` a partir de los `ScanCall` detectados.
7. Construir y validar el modelo `ReferenceExtraction` con `validate_extraction_model()`.
8. Serializar en formato canónico a fichero temporal.
9. Validar el temporal; publicar con `os.replace()`; limpiar temporal en cualquier fallo.

---

## Flujo de verificación

`references verify` re-extrae en memoria y compara campo a campo:

1. Cargar el JSON del artefacto; validar `format` y `schema_version`.
2. Verificar `created_at`: formato UTC ISO-8601 válido (acepta `Z` y `+00:00`; rechaza otros).
3. Re-calcular SHA-256 y tamaño del manifiesto; comparar contra `source_manifest`.
4. Re-calcular SHA-256 y tamaño del índice; comparar contra `source_index`.
5. Deserializar el manifiesto y verificar corpus (ficheros presentes, hashes correctos).
6. Ejecutar `validate_index()` completo.
7. Re-extraer en memoria todos los ficheros `structured_ln4`; `created_at` no interviene en la re-extracción.
8. Verificar cobertura: ningún path ausente ni extra respecto al artefacto.
9. Comparar campos raíz:
   - `generator.name` contra `GENERATOR_NAME`;
   - `generator.version` contra `_GENERATOR_VERSION` (importado diferido);
   - los 10 contadores del `summary` contra `_build_summary()` sobre la re-extracción.
10. Para cada fichero (incluyendo ficheros con `status = "error"`):
    - `source_file_id`, `source_file_sha256`, `encoding`, `line_ending`, `status`;
    - lista `errors` ordenada (campo a campo: `code`, `message`, `evidence`);
    - si ambos ficheros tienen `status = "processed"`: comparar número de referencias y campo a campo los 17 campos de cada referencia y los 5 campos de cada argumento.
11. Ejecutar `validate_extraction_model()` final sobre el artefacto cargado.

### Semántica de `created_at`

`extraction.created_at` registra cuándo se ejecutó el extractor; es independiente de `corpus-manifest.created_at`.
`references verify` valida únicamente que el valor sea un timestamp UTC ISO-8601 bien formado.
No compara contra ningún otro timestamp del pipeline.
La integridad externa del campo frente a manipulación silenciosa está garantizada por el SHA-256 del artefacto registrado en `run-manifest-v1`.

---

## Decisiones de diseño

### Scanner de caracteres en lugar de regex

Una regex no puede manejar `Call()` anidados, literales de cadena que contengan `Call(...)`, comentarios de línea o bloque, ni tracking correcto de línea/columna. El scanner de estados es más simple de probar de forma aislada.

### Sin gramática LN4 completa

Una gramática completa (lark, antlr) añadiría una dependencia externa, sería más lenta, y es innecesaria para extraer únicamente `Call()`.

### JSON en lugar de SQLite

El artefacto es de sólo lectura tras su creación, legible por humanos, difable en control de versiones, y no requiere consultas estructuradas sobre millones de filas.

### Todos los ficheros `structured_ln4` incluidos

Distingue «procesado sin llamadas» de «nunca procesado». Facilita comprobaciones de cobertura.

### SHA-256 del índice en el artefacto

Permite que `references verify` detecte si el índice fue reconstruido a partir de un manifiesto diferente.

### `Call` sensible a mayúsculas con verificación de frontera

Evita falsos positivos en identificadores como `CALLBACK` o `MyCall`.

### Resolución de importación circular mediante import diferido

`extraction.py` importa `validate_extraction_model` desde `validation.py`.
`validation.py` necesita `_process_file`, `_build_summary`, `_get_index_info` y `_GENERATOR_VERSION` de `extraction.py`.
Se resuelve importando estos símbolos dentro del cuerpo de `verify_extraction()`, no en el nivel de módulo.

### Escritura atómica

Usa `tempfile.mkstemp` + `os.replace()`. El fichero anterior nunca se toca hasta que el nuevo está validado y listo para publicar.

---

## Sintaxis LN4 soportada

El scanner detecta:

- `Call(arg, ...)` — forma canónica;
- `Call (arg, ...)` — espacio entre nombre y paréntesis;
- `Call()` anidados dentro de argumentos (re-descubiertos al avanzar el cursor sólo sobre `Call`);
- ficheros con BOM UTF-8;
- ficheros con CRLF.

El scanner excluye:

- `Call` dentro de literales de cadena (`"...Call..."`);
- `Call` dentro de comentarios de línea (`' Call`, `// Call`);
- `Call` dentro de comentarios de bloque (`/* Call */`);
- `Callp`, `CallList` y otras palabras donde `Call` no es un token completo.

No hay soporte de:

- secuencias de escape dentro de cadenas (`\"`);
- literales de cadena multilínea que crucen un límite de comentario.

---

## Estados y diagnósticos

### Estados de referencia

| Estado | Producido por INC-0005 | Significado |
|--------|------------------------|-------------|
| `observed` | sí | Paréntesis cerrado; argumentos parseables |
| `malformed` | sí | Paréntesis nunca cerrado (fin de fichero) |
| `partially_parsed` | reservado | — |
| `ambiguous` | reservado | — |
| `unsupported` | reservado | — |

### Tipos de argumento

| Tipo | Producido por INC-0005 |
|------|------------------------|
| `string_literal` | sí |
| `numeric_literal` | sí |
| `identifier` | sí |
| `expression` | sí |
| `empty` | sí |

### Códigos de error de fichero

| Código | Producido por INC-0005 | Significado |
|--------|------------------------|-------------|
| `file_not_found` | sí | Fichero en índice no leíble |
| `hash_mismatch` | sí | SHA-256 en disco difiere del índice |
| `decode_error` | sí | Bytes no decodificables como UTF-8 |
| `parser_failure` | sí | Excepción inesperada en el scanner |
| `unsupported_encoding` | reservado | — |

### Diagnósticos de referencia

| Código | Producido por INC-0005 | Significado |
|--------|------------------------|-------------|
| `unclosed_parenthesis` | sí | Fin de fichero sin `)` de cierre |
| `unterminated_string` | sí | Cadena sin `"` de cierre dentro de argumentos |
| `unexpected_end_of_file` | reservado | — |

---

## Evidencia y trazabilidad

### Documentación técnica

- Esquema: [`docs/schemas/reference-extraction-v1.md`](../schemas/reference-extraction-v1.md)
- Decisión de arquitectura: [`docs/decisions/ADR-0005-reference-extraction.md`](../decisions/ADR-0005-reference-extraction.md)
- Ciclo de vida: [`docs/architecture/reference-extraction-lifecycle.md`](../architecture/reference-extraction-lifecycle.md)

### Ficheros de implementación

| Módulo | Ruta |
|--------|------|
| Modelos | `src/peoplenet_process_extractor/references/models.py` |
| Scanner | `src/peoplenet_process_extractor/references/scanner.py` |
| Extractor | `src/peoplenet_process_extractor/references/extraction.py` |
| Validación | `src/peoplenet_process_extractor/references/validation.py` |
| Serialización | `src/peoplenet_process_extractor/references/serialization.py` |
| CLI | `src/peoplenet_process_extractor/references/cli.py` |

### Cadena de procedencia

```
corpus bytes
  └── sha256 por fichero ──► corpus-manifest-v1.json
        sha256, size ───────────────────────────────► structural-index-v1.sqlite
                                sha256, size ─────────────────────────────────► reference-extraction-v1.json
```

---

## CLI

### Extracción

```bash
uv run peoplenet-process-extractor references extract \
  --corpus-root /ruta/al/corpus \
  --corpus-manifest corpus-manifest.json \
  --index structural-index.sqlite \
  --output reference-extraction.json
```

Opciones:

- `--force` — sobreescribe un fichero de salida existente;
- `--created-at ISO8601_UTC` — fija el timestamp para salida byte a byte reproducible (acepta `Z` y `+00:00`).

### Verificación

```bash
uv run peoplenet-process-extractor references verify \
  --corpus-root /ruta/al/corpus \
  --corpus-manifest corpus-manifest.json \
  --index structural-index.sqlite \
  --references reference-extraction.json
```

### Consulta

```bash
uv run peoplenet-process-extractor references query \
  --references reference-extraction.json \
  [--path "ruta/relativa/al/fichero.ln4"] \
  [--status observed|malformed] \
  [--function-name Call] \
  [--kind call] \
  [--json]
```

Código de salida `0` en éxito; no-cero en cualquier error.

---

## Pruebas

### Resultado final

```text
893 passed, 4 skipped
```

### Ruff

```text
All checks passed!
```

### Módulo `tests/test_references/` — 203 pruebas

| Clase | Pruebas | Fichero |
|-------|---------|---------|
| `TestValidateExtractionModel` | 15 | `test_validation.py` |
| `TestVerifyExtraction` | 5 | `test_validation.py` |
| `TestVerifyExhaustiveFieldTampering` | 18 | `test_validation.py` |
| `TestVerifyRemovedAddedReferences` | 2 | `test_validation.py` |
| `TestVerifyRootFieldTampering` | 19 | `test_validation.py` |
| `TestVerifyFileLevelTampering` | 6 | `test_validation.py` |
| `TestVerifyCreatedAtSemantics` | 7 | `test_validation.py` |
| `TestGoldenFile` | 13 | `test_golden.py` |
| `TestReproducibility` | 8 | `test_reproducibility.py` |
| `TestOsReplaceFailure` | 1 | `test_reproducibility.py` |
| `TestExtractionSuccess` | 6 | `test_extraction.py` |
| `TestExtractionErrors` | 6 | `test_extraction.py` |
| `TestExtractionIndexValidation` | 2 | `test_extraction.py` |
| `TestEncodingDetection` | 3 | `test_extraction.py` |
| `TestDeserialize` | 9 | `test_serialization.py` |
| `TestSerialize` | 8 | `test_serialization.py` |
| `TestSimpleCall` | 5 | `test_scanner.py` |
| `TestWordBoundary` | 6 | `test_scanner.py` |
| `TestCommentExclusion` | 6 | `test_scanner.py` |
| `TestStringExclusion` | 2 | `test_scanner.py` |
| `TestNestedCalls` | 3 | `test_scanner.py` |
| `TestMalformedCall` | 2 | `test_scanner.py` |
| `TestScanEmpty` | 3 | `test_scanner.py` |
| `TestLineColumnTracking` | 4 | `test_scanner.py` |
| `TestMultilineCall` | 2 | `test_scanner.py` |
| `TestMultipleCallsSameLine` | 2 | `test_scanner.py` |
| `TestCallWithSpaceBeforeParen` | 2 | `test_scanner.py` |
| `TestSplitArguments` | 6 | `test_scanner.py` |
| `TestClassifyArgument` | 8 | `test_scanner.py` |
| `TestEmptyArgument` | 1 | `test_scanner.py` |
| `TestExtractCommand` | 8 | `test_cli.py` |
| `TestVerifyCommand` | 2 | `test_cli.py` |
| `TestQueryCommand` | 5 | `test_cli.py` |
| `TestHelp` | 4 | `test_cli.py` |
| `TestPreviousCLIsStillWork` | 4 | `test_cli.py` |

### Corpus de fixtures

7 ficheros LN4 de prueba:

- `METH_SIMPLE` — llamadas `Call()` simples;
- `METH_COMPLEX` — argumentos anidados;
- `METH_MALFORMED` — paréntesis sin cerrar;
- `METH_NO_CALLS` — fichero sin llamadas (cero referencias);
- `METH_BOM` — encoding `utf-8-bom`;
- `METH_CRLF` — line endings CRLF;
- `CONC_EMPTY` — fichero vacío.

---

## Revisiones independientes y correcciones

### Corrección 1 — Verificación de campos raíz y fichero incompleta

**Defecto detectado:** `verify_extraction()` no comparaba `generator.name`, `generator.version` ni los 10 contadores del `summary`. Los ficheros con `status = "error"` se saltaban silenciosamente en el bucle de comparación.

**Corrección:**
- Comparación de `generator.name` contra `GENERATOR_NAME`.
- Comparación de `generator.version` contra `_GENERATOR_VERSION` (import diferido).
- `_build_summary()` se llama sobre los ficheros re-extraídos; los 10 contadores se comparan contra el artefacto almacenado.
- Comparación de `source_file_id` por fichero.
- Comparación de la lista `errors` ordenada y campo a campo (`code`, `message`, `evidence`).
- Eliminación del `continue` que saltaba ficheros con `status = "error"`.

### Corrección 2 — Alineación UTC en CLI y verificación

**Defecto detectado:** La CLI rechazaba el sufijo `Z` válido en `--created-at`. El verificador tampoco aceptaba `Z`.

**Corrección:**
- `_parse_utc_created_at()` en `validation.py` acepta `Z` y `+00:00`.
- La CLI normaliza con `.astimezone(timezone.utc)` tras parsear, haciendo `Z` y `+00:00` equivalentes.
- Ambas variantes producen un artefacto byte a byte idéntico.
- Texto de ayuda actualizado: `"ISO-8601 UTC, e.g. 2026-06-24T12:00:00+00:00 or 2026-06-24T12:00:00Z"`.

### Corrección 3 — Comparación circular de `created_at` (revertida)

**Defecto tentativo detectado:** `created_at` del artefacto aceptaba cualquier timestamp UTC válido, incluyendo fechas futuras arbitrarias, sin ninguna comprobación.

**Solución tentativa:** Comparar `stored_created_at` contra `manifest.created_at` como ancla.

**Error de diseño identificado:** `manifest.created_at` registra cuándo se tomó el snapshot del corpus; `extraction.created_at` registra cuándo se ejecutó el extractor. Son eventos distintos y legítimamente difieren cuando la extracción se realiza después de que se construyó el manifiesto. Comparar ambos valores constituiría un falso negativo para toda extracción tardía.

**Corrección definitiva:** Retirada de la comparación de timestamps entre artefactos. `references verify` valida únicamente que `created_at` es un timestamp UTC ISO-8601 bien formado. La integridad externa está garantizada por el SHA-256 del artefacto en `run-manifest-v1`. Documentado en ADR-0005, schema y lifecycle.

---

## Limitaciones conocidas

- No se manejan secuencias de escape en cadenas (`\"`); no se han observado en el corpus.
- Sólo se detecta la palabra clave `Call`; `Callp`, `CallList` y variantes se excluyen explícitamente.
- No hay soporte para literales de cadena multilínea que crucen un límite de comentario.
- `\r` se trata como carácter de columna, no como salto de línea (correcto para convención CRLF).
- Los IDs de referencia dependen del SHA-256 del fichero: si el fichero cambia, los IDs cambian.
- El artefacto no es actualizable de forma incremental; requiere re-extracción completa.

---

## Riesgos pendientes

- **Corpus grandes:** la re-extracción en memoria durante `verify` carga todos los ficheros; puede requerir ajustes con corpus de varios GB.
- **Evolución del esquema:** añadir campos al artefacto requerirá `schema_version = 2` y posiblemente migraciones.
- **Nuevas variantes de `Call`:** formas no observadas en el corpus actual pueden requerir actualización del scanner y regeneración del golden.
- **Resolución de referencias ambiguas:** llamadas a `Call(target, method)` donde `target` es una expresión compleja se clasificarán como `expression`; su resolución es responsabilidad de INC-0006.

---

## Criterios de aceptación

- [x] `uv run pytest -q` pasa con 893 pruebas (0 fallos).
- [x] `uv run ruff check .` no reporta errores.
- [x] `references extract` produce un artefacto válido y reproducible.
- [x] `references verify` detecta cualquier manipulación de campos: `generator`, `summary`, campos de fichero, referencias y argumentos.
- [x] `references verify` acepta `Z` y `+00:00` como sufijos UTC equivalentes.
- [x] `references verify` rechaza timestamps sin timezone y offsets no UTC.
- [x] `references verify` no compara `created_at` contra `manifest.created_at`.
- [x] Dos ejecuciones con las mismas entradas y el mismo `--created-at` producen un artefacto byte a byte idéntico.
- [x] Los ficheros con `status = "error"` se verifican campo a campo sin ser saltados.
- [x] El golden es estable entre Windows y Unix.
- [x] No hay importaciones circulares entre `extraction.py` y `validation.py`.

---

## Comando único de verificación

```bash
uv run pytest -q && uv run ruff check .
```

En PowerShell:

```powershell
uv run pytest -q
uv run ruff check .
```

---

## Resultado final

El incremento proporciona un extractor de referencias:

- determinista y reproducible (byte a byte con `--created-at`);
- verificable mediante re-extracción completa en memoria;
- trazable al texto decodificado de cada fichero mediante offsets Unicode, y al corpus físico mediante SHA-256 por fichero;
- portable entre Windows y Unix;
- con dominios cerrados y estados reservados para extensión futura;
- con cadena de procedencia completa: corpus → manifiesto → índice → artefacto.

---

## Siguiente incremento recomendado

**INC-0006 — Resolución de llamadas v1**

Alcance recomendado:

- tomar `reference-extraction-v1` y `structural-index-v1` como entradas;
- mapear cada `Call(target, method)` a un `source_file_id` en el índice estructural;
- producir un artefacto `call-resolution-v1`;
- sin construcción del grafo completo de dependencias.
