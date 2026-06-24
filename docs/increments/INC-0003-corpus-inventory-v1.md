# INC-0003 — Corpus inventory v1

## Estado

Aceptado y cerrado.

## Objetivo

Implementar un inventario versionado, determinista y verificable del corpus PeopleNet/Meta4 que permita:

- identificar exactamente los ficheros disponibles;
- registrar rutas relativas, hashes y tamaños;
- clasificar ficheros estructurados y no estructurados;
- reconocer estructura PeopleNet a partir de rutas;
- conservar información Git opcional;
- comparar un corpus físico con un snapshot previo;
- detectar altas, bajas y modificaciones;
- proporcionar una entrada estable para el futuro indexador.

El incremento debía resolver la identidad y trazabilidad del corpus sin construir todavía un índice SQLite ni analizar contenido LN4.

## Motivación

Antes de este incremento, el corpus se recorría de forma implícita y quedaba acoplado al indexador del prototipo.

Esto presentaba varios problemas:

- no existía un snapshot explícito del corpus;
- la identidad dependía del estado externo del árbol de ficheros;
- la obsolescencia se apoyaba en conteos y `mtime`;
- inventario, parsing de rutas e indexación estaban mezclados;
- no podía distinguirse con claridad un cambio de corpus de un cambio de lógica;
- no existía una evidencia completa de hashes por fichero;
- el futuro índice podía construirse sobre un corpus distinto sin detectarlo.

El inventario se establece como contrato entre:

```text
corpus físico
→ corpus-manifest-v1
→ futuro índice
→ futuro descubrimiento
→ futuro análisis
```

## Resultado implementado

- Contrato versionado `corpus-manifest-v1`.
- Versión de esquema `1.0` (inicial) → `1.1` desde INC-0006.
- Inventario determinista de ficheros.
- Rutas relativas y portables con `/`.
- Hash SHA-256 y tamaño por fichero.
- Clasificación cerrada de ficheros.
- Reconocimiento de rutas PeopleNet estructuradas.
- Reconocimiento de recursos META4OBJECT (INC-0006).
- Conservación de ficheros LN4 no estructurados.
- Descubrimiento y filtrado de raíces de primer nivel.
- Normalización de filtros duplicados.
- Información Git opcional:
  - commit HEAD;
  - estado dirty.
- Resumen consistente y validado.
- Comparación estructurada:
  - `added`;
  - `removed`;
  - `modified`;
  - `unchanged`.
- CLI:
  - `corpus inventory`;
  - `corpus verify`.
- Escritura segura del manifiesto.
- Verificación exacta del alcance inventariado.
- Rechazo de symlinks y rutas fuera del corpus.
- Tests positivos, negativos y de regresión.
- Documentación de esquema, arquitectura y decisión técnica.

## Estructura del manifiesto

El contrato representa como mínimo:

- `schema_version`;
- `corpus_id`;
- `created_at`;
- información de root;
- información Git;
- `included_source_roots`;
- `files`;
- `summary`;
- `warnings`;
- `errors`.

## Clasificaciones soportadas

Catálogo cerrado:

- `structured_ln4`;
- `unstructured_ln4`;
- `metadata_json`;
- `m4o_node_json` _(INC-0006)_;
- `m4o_alias_json` _(INC-0006)_;
- `m4o_mapping_json` _(INC-0006)_;
- `other_supported`;
- `ignored`.

Las clasificaciones arbitrarias se rechazan durante la deserialización y validación.

## Estructura PeopleNet reconocida

Se reconocen rutas equivalentes a:

```text
<source_root>/
  NODE STRUCTURE/
    <meta4object>/
      ITEM/
        <item_type>/
          <item_name>/
            RULES/
              <rule_file>.ln4
```

Cuando la ruta y el nombre encajan, se extraen:

- `meta4object`;
- `item_type`;
- `item_name`;
- `rule_id`;
- `rule_date`.

No se limita `item_type` a `METHOD`; también se admiten `CONCEPT` y otros tipos no vacíos.

## Recursos META4OBJECT reconocidos (INC-0006)

A partir de INC-0006 se reconocen tres patrones bajo `META4OBJECT/`:

### Nodo propio (`m4o_node_json`)

```text
<source_root>/META4OBJECT/<ID_T3>/NODE/<ID_NODE>/<file>.json
```

Extrae `M4oStructure(id_t3, id_node)`.

### Alias (`m4o_alias_json`)

```text
<source_root>/META4OBJECT/<ID_T3>/M4O ALIAS RESOLUTION/<ID_NODE>/<file>.json
```

Extrae `M4oStructure(id_t3, id_node)`.

### Herencia / Mapping (`m4o_mapping_json`)

```text
<source_root>/META4OBJECT/<ID_T3>/MAPPING META4OBJECT/<ID_T3>/<file>.json
```

El `<ID_T3>` exterior e interior deben coincidir. Si no coinciden, el fichero se clasifica como `other_supported` con el warning `malformed_m4o_mapping_path`.

Extrae `M4oStructure(id_t3, id_node=None)`.

### Modelo `M4oStructure`

```python
@dataclass(frozen=True)
class M4oStructure:
    id_t3: str       # Identificador del tipo T3
    id_node: str | None  # Null para mappings; obligatorio para nodo y alias
```

El campo `M4oStructure` es complementario a `Ln4Structure`; son mutuamente excluyentes.

### Recursos fuera de alcance

Los subdirectorios desconocidos bajo `META4OBJECT/` se clasifican como `other_supported` sin warning.

El JSON raíz del T3 (`META4OBJECT/<ID_T3>/<file>.json`) es out-of-scope sin warning.

Solo los ficheros con extensión `.json` reciben clasificaciones M4O.

### Política de warnings

Los warnings se emiten únicamente cuando un path parece pertenecer a un patrón conocido pero está mal formado:

| Situación | Código de warning |
|---|---|
| `NODE/<file>.json` sin nivel `ID_NODE` | `malformed_m4o_node_path` |
| `M4O ALIAS RESOLUTION/<file>.json` sin `ID_NODE` | `malformed_m4o_alias_path` |
| `MAPPING META4OBJECT/<ID_T3_B>` con `ID_T3_B != ID_T3` | `malformed_m4o_mapping_path` |

### Nota INC-0006

INC-0006 no interpreta el contenido de los JSON Meta4Object. Solo inventaría y clasifica recursos a partir de rutas observadas.

No se leen tablas `M4RCH_NODES`, `M4RCH_T3_ALIAS_RES` ni `SPR_DIN_OBJECTS`.

### Serialización

Los manifests `1.1` incluyen en cada `FileEntry`:

```json
"m4o_structure": {
  "id_t3": "OBJ_T3_A",
  "id_node": "NODE_X"
}
```

o `null` cuando no aplica.

Los manifests `1.0` sin este campo se leen correctamente con `m4o_structure = null`.

### Compatibilidad de versiones

| Versión | Escritura | Lectura |
|---|---|---|
| `1.0` | No (histórico) | Sí |
| `1.1` | Sí (desde INC-0006) | Sí |

El código anterior puede rechazar `1.1` explícitamente. Eso es aceptable siempre que el error sea claro.

## Ficheros no estructurados

Los `.ln4` que no encajan en la estructura reconocida:

- no se descartan;
- se clasifican como `unstructured_ln4`;
- mantienen ruta, hash y tamaño;
- pueden incluir warnings;
- no reciben metadatos estructurales inventados.

Los ficheros directos en el root del corpus se representan con:

```text
source_root = null
```

## Hashing

Los hashes se calculan mediante SHA-256:

- sobre los bytes originales;
- sin normalizar saltos de línea;
- sin decodificar contenido;
- sin usar `mtime` como evidencia;
- mediante lectura incremental;
- reutilizando la utilidad del Incremento 2.

También se registra el tamaño real en bytes.

## Rutas y portabilidad

Las rutas del manifiesto:

- son relativas al corpus root;
- usan `/`;
- no contienen `..`;
- no son absolutas;
- preservan los nombres originales;
- se ordenan determinísticamente.

La ruta absoluta operativa del corpus no se almacena en el manifiesto.

## Raíces del corpus

Sin filtros:

- se descubren las raíces de primer nivel;
- se inventarían los ficheros bajo esas raíces;
- se inventarían también los ficheros directos en root;
- los ficheros directos usan `source_root = null`.

Con filtros `--source-root`:

- solo se incluyen las raíces solicitadas;
- no se incluyen otras raíces;
- no se incluyen ficheros directos en root;
- las raíces inexistentes producen error;
- los filtros duplicados se normalizan.

Ejemplo:

```text
--source-root CP --source-root CP
```

es equivalente a:

```text
--source-root CP
```

## Semántica exact-scope de `corpus verify`

`corpus verify` verifica exactamente el alcance registrado en el manifiesto.

### Con raíces declaradas

Si:

```json
"included_source_roots": ["CP"]
```

se verifica únicamente `CP`.

Una nueva raíz física `GTO` queda fuera del snapshot y no se reporta.

### Snapshot root-only

Si:

```json
"included_source_roots": []
```

el snapshot representa exclusivamente los ficheros directos en el root del corpus.

Por tanto:

- se verifican los ficheros directos;
- las nuevas raíces físicas se ignoran;
- un nuevo fichero directo se detecta;
- un fichero directo modificado se detecta;
- un fichero directo eliminado se detecta.

No existe modo full-scope.

## Información Git

Cuando el corpus está dentro de un repositorio Git, se registra opcionalmente:

- commit HEAD;
- estado limpio o sucio.

No se almacenan URL remota, usuario, email, credenciales ni rutas absolutas.

Si Git no está disponible o el corpus no pertenece a un repositorio:

- el inventario no falla;
- `commit = null`;
- `dirty = null`;
- puede emitirse un warning informativo.

## Resumen

El manifiesto incluye:

- `total_files`;
- `total_bytes`;
- `structured_files`;
- `unstructured_files`;
- `by_source_root`;
- `by_extension`;
- `by_classification`.

El resumen se valida contra el detalle de `files`.

## Coherencias validadas

Para cada fichero se valida, entre otros:

- path relativo;
- ausencia de traversal;
- path único;
- SHA-256 válido;
- tamaño no negativo;
- clasificación válida;
- extensión coherente con `path`;
- `source_root` coherente con el primer componente del path;
- `source_root = null` para ficheros directos;
- pertenencia de `source_root` a `included_source_roots`;
- estructura coherente con la clasificación;
- tipos correctos en JSON.

Los tipos inválidos producen errores estructurados y no tracebacks.

## `created_at`

`created_at` debe:

- ser ISO 8601;
- incluir zona;
- estar expresado en UTC;
- aceptar `Z`;
- aceptar `+00:00`;
- rechazar offsets distintos de cero;
- rechazar timestamps naive;
- rechazar tipos no string.

## Comparación de inventarios

La comparación clasifica los ficheros en:

- `added`;
- `removed`;
- `modified`;
- `unchanged`.

Para los modificados puede identificar cambios en:

- hash;
- tamaño;
- clasificación;
- estructura.

Los renombrados se representan como fichero eliminado y fichero añadido.

## CLI implementada

### Inventario

```bash
uv run peoplenet-process-extractor corpus inventory \
  --corpus-root $env:PEOPLENET_CORPUS_ROOT \
  --output corpus-manifest.json
```

Opciones principales:

- `--corpus-root`;
- `--output`;
- `--corpus-id`;
- `--source-root`;
- `--force`.

### Verificación

```bash
uv run peoplenet-process-extractor corpus verify \
  --corpus-root $env:PEOPLENET_CORPUS_ROOT \
  corpus-manifest.json
```

Códigos de salida:

- `0` si el snapshot coincide;
- distinto de cero ante diferencias o errores.

`verify` no modifica corpus, manifiesto ni repositorio.

## Escritura segura

El manifiesto se escribe mediante:

- fichero temporal;
- escritura completa;
- reemplazo final;
- limpieza de temporales en caso de error.

No se sobrescribe un output existente sin `--force`.

## Symlinks

La implementación:

- rechaza corpus root symlink;
- no sigue directorios symlink;
- no inventaría silenciosamente ficheros symlink como normales;
- evita escapes fuera del corpus root.

Los tests reales de symlinks pueden quedar `skipped` en Windows si el entorno no permite crearlos.

## Integración futura con `run-manifest-v1`

El futuro pipeline registrará `corpus-manifest.json` como fuente agregada del run.

No se registrarán todos los `.ln4` individualmente en `run-manifest-v1`.

Esta integración queda documentada, pero no automatizada en este incremento.

## Fuera de alcance confirmado

- SQLite.
- Tablas de índice.
- Parsing de contenido LN4.
- Extracción de llamadas.
- Resolución de métodos.
- Consultas `path`, `callers` o `callees`.
- Grafo de llamadas.
- Análisis funcional.
- Procesamiento de trazas.
- Generación de Markdown.
- Indexación incremental.
- Watchers.
- Monitorización.
- Copia del corpus al repositorio.
- Modificación del corpus.
- Hash agregado de directorios.
- Detección heurística de renames.
- Múltiples versiones del esquema.
- Servicio REST.
- Persistencia en base de datos.
- Modo full-scope.
- Pseudo-raíces.
- Integración directa con `meta4_ai_tools`.

## Decisiones finales

- El corpus permanece externo.
- El inventario es un snapshot inmutable.
- Los hashes son evidencia primaria.
- Las rutas son relativas y portables.
- Los ficheros no estructurados se conservan.
- Inventario e índice son responsabilidades distintas.
- El futuro índice consumirá `corpus-manifest-v1`.
- `verify` aplica exact-scope.
- Una lista vacía de raíces representa root-only.
- Los filtros duplicados se normalizan.
- No se siguen symlinks.
- No se usa `mtime` como prueba de identidad.
- No se introducen dependencias externas innecesarias.

## Criterios de aceptación

| Criterio | Estado | Evidencia |
|---|---|---|
| Contrato `corpus-manifest-v1` | Cumplido | `docs/schemas/corpus-manifest-v1.md` |
| Versión `1.0`/`1.1` | Cumplido | Modelo y validación |
| Inventario de ficheros relevantes | Cumplido | Servicio de inventario |
| Hash y tamaño | Cumplido | Tests de hashing |
| Rutas relativas con `/` | Cumplido | Validación y tests |
| Sin rutas absolutas | Cumplido | Tests y serialización |
| Orden determinista | Cumplido | Orden por path |
| Parsing de estructura PeopleNet | Cumplido | Tests de paths |
| Recursos META4OBJECT (INC-0006) | Cumplido | Tests de paths y servicio |
| LN4 no estructurados conservados | Cumplido | Fixtures y tests |
| Raíces incluidas registradas | Cumplido | `included_source_roots` |
| Filtros estrictos | Cumplido | Tests de filtro |
| Filtros duplicados normalizados | Cumplido | Tests y documentación |
| Git opcional | Cumplido | Tests aislados |
| Resumen coherente | Cumplido | Validación |
| Round trip | Cumplido | Tests de serialización |
| Detección de añadidos, eliminados y modificados | Cumplido | Tests de verify |
| Exact-scope | Cumplido | Tests y documentación |
| Root-only | Cumplido | Tests específicos |
| `created_at` UTC | Cumplido | Tests positivos y negativos |
| Tipos JSON robustos | Cumplido | Tests de manipulación |
| Escritura segura | Cumplido | Tests |
| CLI `corpus inventory` | Cumplido | Tests y ejecución manual |
| CLI `corpus verify` | Cumplido | Tests y ejecución manual |
| Sin SQLite | Cumplido | Alcance preservado |
| Sin parsing LN4 | Cumplido | Alcance preservado |
| Tests y Ruff | Cumplido | Verificación final |

## Verificación final

```bash
uv run pytest -q
uv run ruff check .
uv run peoplenet-process-extractor --help
uv run peoplenet-process-extractor scenario --help
uv run peoplenet-process-extractor manifest --help
uv run peoplenet-process-extractor corpus --help
uv run peoplenet-process-extractor corpus inventory --help
uv run peoplenet-process-extractor corpus verify --help
git diff --check
git diff --cached --check
git ls-files "*.pyc"
git ls-files "*__pycache__*"
```

Resultado final:

- Suite completa en verde.
- Ruff en verde.
- CLI operativas.
- Ambos diff checks en verde.
- Sin `.pyc` ni `__pycache__` versionados.
- Codex: revisión funcional aceptada tras las correcciones.
- Tests finales reforzados para comprobar errores estructurados estables.

## Revisiones realizadas

1. Implementación inicial por Claude Code.
2. Revisión independiente completa por Codex.
3. Correcciones de filtros, coherencias, UTC y documentación.
4. Revisión focalizada por Codex.
5. Correcciones de pertenencia, filtros múltiples y duplicados y robustez JSON.
6. Comprobación final por Codex.
7. Corrección de semántica root-only y referencias full-scope.
8. Refuerzo final de tests para comprobar errores estructurados específicos.

## Limitaciones conocidas

- Los tests de symlinks pueden quedar omitidos en Windows sin privilegios.
- No existe todavía índice SQLite.
- No se analiza contenido LN4.
- No se extraen llamadas.
- No se automatiza todavía la integración con `run-manifest-v1`.
- `verify` no detecta raíces nuevas fuera del alcance inventariado.
- No existe modo full-scope.
- No se implementa detección heurística de renames.

## Documentación relacionada

- `docs/schemas/corpus-manifest-v1.md`
- `docs/decisions/ADR-0003-corpus-inventory.md`
- `docs/architecture/corpus-lifecycle.md`
- `docs/schemas/run-manifest-v1.md`
- `docs/schemas/scenario-v1.md`

## Commit

```text
feat: add versioned corpus inventory and verification
```

Commit SHA:

```text
<PENDIENTE_DE_RELLENAR>
```

## Fecha de cierre

2026-06-23
