# INC-0002 — Run manifest v1

## Estado

Aceptado y cerrado.

## Objetivo

Implementar un contrato versionado de ejecución que permita identificar una ejecución concreta del pipeline, registrar sus entradas y artefactos, conservar su procedencia y verificar posteriormente la integridad de los ficheros utilizados y generados.

El incremento debía establecer una base reproducible antes de abordar:

- indexación del corpus;
- descubrimiento de dependencias;
- análisis LN4;
- procesamiento de trazas;
- generación de documentación.

## Motivación

El flujo anterior presentaba varios problemas:

- uso de un workspace compartido;
- posibilidad de consumir outputs residuales;
- ausencia de identidad inequívoca de ejecución;
- falta de hashes de inputs y artefactos;
- ausencia de trazabilidad sobre las versiones utilizadas;
- dificultad para demostrar si un resultado correspondía exactamente a unos inputs;
- riesgo de modificar o reemplazar ficheros después del análisis sin detectarlo.

El manifiesto de ejecución resuelve estas carencias mediante un directorio aislado por run y un inventario estructurado y verificable.

## Resultado implementado

- Contrato versionado `run-manifest-v1`.
- Versión de esquema `1.0`.
- Directorio independiente por ejecución.
- Creación de runs bajo:

```text
<runs-root>/<run_id>/
```

- Registro estructurado de:
  - escenario;
  - fuentes;
  - herramientas;
  - artefactos;
  - eventos;
  - warnings;
  - errores;
  - timestamps de inicio y finalización.
- Cálculo SHA-256 sobre los bytes originales.
- Registro de tamaños en bytes.
- Rutas relativas y portables con `/`.
- Verificación posterior de integridad.
- Validación de referencias de procedencia.
- Escritura segura mediante staging.
- Sustitución controlada mediante `--force`.
- Restauración del run anterior ante fallos de publicación.
- Rechazo de symlinks y rutas que escapen del directorio del run.
- CLI integrada:
  - `scenario migrate`;
  - `manifest create`;
  - `manifest verify`.
- Tests positivos, negativos y de regresión.
- Documentación de esquema, arquitectura y decisión técnica.

## Estructura del directorio de ejecución

Cada run se almacena en un directorio propio:

```text
<runs-root>/<run_id>/
├── run-manifest.json
├── inputs/
│   └── scenario.json
├── artifacts/
└── reports/
```

No se utiliza un workspace global compartido.

## Modelo `run-manifest-v1`

El manifiesto representa como mínimo:

- `schema_version`;
- `run_id`;
- estado de la ejecución;
- referencia al escenario;
- fuentes;
- herramientas;
- artefactos;
- eventos;
- warnings;
- errores;
- `started_at`;
- `finished_at`.

## Estados de ejecución

Catálogo cerrado:

- `prepared`
- `running`
- `succeeded`
- `failed`
- `cancelled`

## Tipos de fuente

Catálogo inicial:

- `scenario`
- `frontend_call`
- `database_trace`
- `query_results`
- `ln4_source`
- `manual_input`
- `configuration`
- `other`

## Tipos de artefacto

Catálogo inicial:

- `scenario`
- `migration_report`
- `clean_trace`
- `writes_trace`
- `intermediate_model`
- `validation_report`
- `markdown`
- `other`

## Estados de artefacto

- `planned`
- `generated`
- `failed`
- `missing`

## Tipos de evento

- `prepared`
- `started`
- `artifact_generated`
- `warning`
- `error`
- `finished`

## Integración con `scenario-v1`

El comando `manifest create`:

1. carga un escenario `scenario-v1`;
2. lo valida;
3. rechaza escenarios inválidos;
4. lo copia a `inputs/scenario.json`;
5. calcula su hash y tamaño;
6. registra:
   - `scenario_id`;
   - versión del esquema;
   - ruta relativa;
   - SHA-256;
   - tamaño.

Debe existir exactamente una fuente de tipo `scenario`.

Esa fuente debe coincidir con el bloque principal `scenario` en:

- ruta;
- hash;
- tamaño.

Cualquier contradicción invalida el manifiesto.

## Hashing

Los hashes se calculan mediante SHA-256:

- sobre los bytes originales;
- sin normalizar saltos de línea;
- sin decodificar el contenido;
- sin modificar el fichero;
- mediante lectura incremental por bloques.

Se registra también el tamaño real en bytes.

## Procedencia

Los artefactos pueden declarar:

```text
derived_from
```

mediante IDs de fuentes o artefactos.

No se utilizan rutas libres como referencias de procedencia.

Fuentes y artefactos comparten un espacio global de identificadores, por lo que:

- no puede existir el mismo ID en ambas colecciones;
- las referencias son inequívocas;
- se rechazan referencias inexistentes;
- se rechazan autorreferencias directas.

La detección general de ciclos entre varios artefactos queda fuera de alcance.

## Herramientas

El manifiesto puede registrar:

- identificador;
- nombre;
- versión;
- comando opcional;
- commit Git opcional;
- información de configuración o esquema opcional.

Se registra al menos la herramienta principal:

```text
peoplenet-process-extractor
```

No se almacenan rutas locales completas ni datos sensibles.

## Eventos y timestamps

Cada evento incluye:

- secuencia;
- tipo;
- timestamp;
- mensaje;
- referencia opcional.

La secuencia debe ser:

- entera;
- no booleana;
- positiva;
- única;
- estrictamente creciente según el orden de la lista.

Los timestamps deben:

- ser ISO 8601;
- incluir zona horaria;
- representar un instante inequívoco;
- permitir comparación cronológica real.

Se rechazan:

- timestamps inválidos;
- timestamps sin zona;
- secuencias string;
- floats;
- booleanos;
- valores nulos;
- cero;
- negativos;
- duplicados;
- secuencias desordenadas.

`finished_at` no puede ser anterior a `started_at`.

## Portabilidad y seguridad de rutas

Las rutas almacenadas en el manifiesto:

- son relativas al directorio del run;
- utilizan `/`;
- no contienen rutas absolutas;
- no permiten traversal mediante `..`;
- no deben resolver fuera del directorio del run.

En la creación y verificación se rechazan:

- symlinks;
- rutas absolutas;
- rutas que escapen del run;
- ficheros no regulares cuando se espera un fichero.

Los tests de symlinks pueden quedar omitidos localmente en Windows cuando el usuario no dispone de permisos para crearlos.

## CLI implementada

### Migración de escenario

```bash
uv run peoplenet-process-extractor scenario migrate   tests/fixtures/scenarios/legacy_peoplenet_call.json   --output scenario.json   --report migration-report.json
```

### Creación de run

```bash
uv run peoplenet-process-extractor manifest create   --scenario scenario.json   --runs-root runs   --run-id run-20260623-001
```

El directorio final será:

```text
runs/run-20260623-001/
```

Si se omite `--run-id`, se genera automáticamente y se utiliza exactamente el mismo valor para:

- el nombre del directorio;
- `manifest.run_id`.

### Verificación

```bash
uv run peoplenet-process-extractor manifest verify   runs/run-20260623-001/run-manifest.json
```

`verify`:

- carga y valida el manifiesto;
- resuelve rutas respecto al directorio del manifiesto;
- recalcula hashes y tamaños;
- detecta:
  - ficheros ausentes;
  - ficheros modificados;
  - tamaños distintos;
  - hashes distintos;
  - referencias rotas;
  - incoherencias estructurales;
- devuelve código distinto de cero ante inconsistencias;
- no modifica el manifiesto.

## Semántica de `--force`

Sin `--force`:

- si el directorio final existe, la creación se rechaza;
- no se modifica el contenido existente.

Con `--force`:

- solo se puede sustituir un run gestionado válido;
- el `run_id` del manifiesto debe coincidir con el nombre del directorio;
- solo se permiten las rutas conocidas:
  - `run-manifest.json`;
  - `inputs/`;
  - `artifacts/`;
  - `reports/`;
- cualquier fichero o directorio desconocido provoca rechazo;
- no se borra contenido ajeno.

La sustitución usa:

1. construcción completa en staging;
2. validación del nuevo run;
3. backup temporal del run anterior;
4. publicación del staging;
5. restauración del backup si falla la publicación;
6. limpieza de staging y backup.

La implementación evita perder el run anterior ante fallos normales durante la publicación.

## Escritura segura

`run-manifest.json` se escribe mediante:

- fichero temporal;
- escritura completa;
- reemplazo final;
- limpieza de temporales ante fallo.

No debe quedar JSON parcial o corrupto.

## Validaciones implementadas

Entre otras:

- versión de esquema soportada;
- `run_id` no vacío y seguro;
- estados válidos;
- IDs únicos;
- unicidad global entre fuentes y artefactos;
- exactamente una fuente `scenario`;
- coherencia entre fuente `scenario` y bloque `scenario`;
- hashes SHA-256 válidos;
- tamaños no negativos;
- referencias `derived_from` existentes;
- `producer` existente;
- autorreferencia rechazada;
- secuencias de evento válidas;
- timestamps con zona;
- coherencia entre fechas;
- `succeeded` incompatible con errores;
- `failed` con error o evento de error;
- rutas relativas y portables;
- ausencia de traversal;
- ausencia de symlinks.

## Fuera de alcance confirmado

- Análisis de código LN4.
- Parser LN4.
- Indexación SQLite.
- Descubrimiento de dependencias.
- Grafo de llamadas.
- Evaluación de ramas.
- Seguimiento de variables.
- Procesamiento de trazas SQL.
- Generación de Markdown.
- Consolidación.
- Reanudación de runs.
- Paralelismo.
- Servicio REST.
- Persistencia en base de datos.
- Almacenamiento remoto.
- Firma criptográfica.
- Hash de directorios completos.
- Integración con `meta4_ai_tools`.
- Acceso a SQL Server.
- Detección general de ciclos de procedencia.
- Configuración de CI para symlinks.

## Decisiones finales

- Un directorio por ejecución.
- El manifiesto es el índice de la ejecución.
- Inputs y artefactos llevan hash y tamaño.
- Las rutas son relativas y portables.
- `run_id` determina el nombre del directorio.
- La CLI utiliza `--runs-root`.
- Fuentes y artefactos comparten un espacio global de IDs.
- Debe existir exactamente una fuente `scenario`.
- `--force` no borra contenido desconocido.
- La publicación se realiza mediante staging y backup.
- El run anterior se restaura ante fallo de publicación.
- Los eventos usan secuencias enteras positivas y timestamps con zona.
- Se rechazan symlinks y rutas que escapen del run.
- La biblioteca estándar es suficiente.
- No se introduce un framework genérico de workflows.

## Criterios de aceptación

| Criterio | Estado | Evidencia |
|---|---|---|
| Contrato `run-manifest-v1` | Cumplido | `docs/schemas/run-manifest-v1.md` |
| Versión explícita `1.0` | Cumplido | Modelo y validación |
| Round trip sin pérdida | Cumplido | Tests de serialización |
| Escenario, fuentes, herramientas, artefactos y eventos | Cumplido | Modelo del manifiesto |
| SHA-256 sobre bytes originales | Cumplido | Tests de hashing |
| Tamaños correctos | Cumplido | Tests de hashing y verify |
| Rutas relativas con `/` | Cumplido | Tests y documentación |
| Sin rutas absolutas almacenadas | Cumplido | Validación |
| IDs globalmente únicos | Cumplido | Validación y tests |
| `derived_from` inequívoco | Cumplido | Validación y tests |
| `producer` validado | Cumplido | Validación |
| Eventos y timestamps válidos | Cumplido | Tests negativos y positivos |
| Creación desde escenario válido | Cumplido | Tests de create |
| Rechazo de escenario inválido | Cumplido | Tests de create |
| Directorio exclusivo por run | Cumplido | `<runs-root>/<run_id>` |
| Escenario copiado | Cumplido | Tests |
| Hash, tamaño, ID y versión registrados | Cumplido | Manifiesto generado |
| Herramienta principal registrada | Cumplido | Tests |
| Evento `prepared` | Cumplido | Tests |
| Escritura segura | Cumplido | Tests de temporales |
| `--force` no destructivo | Cumplido | Tests de contenido desconocido |
| Restauración ante fallo de publicación | Cumplido | Test específico de backup/restore |
| Verificación de hashes | Cumplido | Tests de verify |
| Detección de modificación | Cumplido | Tests de verify |
| Detección de ausencia | Cumplido | Tests de verify |
| Fuente scenario coherente | Cumplido | Validación y tests |
| Symlinks y traversal rechazados | Cumplido con limitación de entorno | Tests condicionados |
| CLI de escenarios sin regresiones | Cumplido | `scenario migrate` |
| Sin análisis LN4 | Cumplido | Alcance preservado |
| Tests y lint | Cumplido | Verificación final |

## Verificación final

```bash
uv run pytest -q
uv run ruff check .
uv run peoplenet-process-extractor --help
uv run peoplenet-process-extractor scenario --help
uv run peoplenet-process-extractor scenario migrate --help
uv run peoplenet-process-extractor manifest --help
git diff --check
git ls-files "*.pyc"
git ls-files "*__pycache__*"
```

Resultado final:

- Suite completa en verde.
- Ruff: `All checks passed`.
- CLI de escenario y manifiesto operativas.
- Sin `.pyc` ni `__pycache__` versionados.
- Codex: `Aceptada`.

## Revisiones realizadas

1. Implementación inicial por Claude Code.
2. Revisión independiente completa por Codex.
3. Corrección de:
   - verificación de la fuente `scenario`;
   - seguridad de `--force`;
   - staging y restauración;
   - unicidad global de IDs;
   - validación de `derived_from`;
   - secuencias de eventos;
   - timestamps con zona;
   - relación entre `run_id` y directorio;
   - jerarquía CLI;
   - symlinks y traversal.
4. Revisión focalizada por Codex.
5. Corrección de:
   - tipo robusto de `Event.sequence`;
   - test de restauración ante fallo de publicación.
6. Comprobación final de Codex: aceptada.

## Limitaciones conocidas

- Los tests reales de symlinks pueden quedar `skipped` en Windows sin privilegios suficientes.
- No se implementa detección general de ciclos entre varios artefactos.
- No se garantiza atomicidad frente a un fallo físico exacto entre operaciones de renombrado del sistema de archivos.
- No existe todavía un pipeline funcional que genere artefactos de análisis.
- El manifiesto registra y verifica artefactos, pero no decide cómo producirlos.

## Documentación relacionada

- `docs/schemas/run-manifest-v1.md`
- `docs/decisions/ADR-0002-run-manifest.md`
- `docs/architecture/run-lifecycle.md`
- `docs/schemas/scenario-v1.md`

## Commit

```text
feat: add versioned run manifest and provenance tracking
```

Commit SHA:

```text
<PENDIENTE_DE_RELLENAR>
```

## Fecha de cierre

2026-06-23
