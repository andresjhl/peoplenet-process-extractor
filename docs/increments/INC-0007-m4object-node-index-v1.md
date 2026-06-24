# INC-0007 — m4object-node-index-v1

## Estado

Implementado en `main`, pendiente de commit de cierre.

## Identificación

- **Incremento:** INC-0007
- **Nombre:** `m4object-node-index-v1`
- **Repositorio:** `peoplenet-process-extractor`
- **Artefacto:** `m4object-node-index-v1` (JSON)

---

## Objetivo

Crear un nuevo artefacto JSON versionado `m4object-node-index-v1` que consuma
exclusivamente entradas de `corpus-manifest-v1` clasificadas como `m4o_node_json`,
`m4o_alias_json` y `m4o_mapping_json`, y extraiga:

- Bindings de nodos (`M4RCH_NODES`): relación `ID_NODE` ↔ `ID_TI`, indicador `IS_ROOT`.
- Bindings de aliases (`M4RCH_T3_ALIAS_RES`): alias → nodo/estructura resueltos.
- Aristas de herencia directa (`SPR_DIN_OBJECTS`): relación base/derivado.
- Evidencia por fila.
- Diagnósticos estructurados.
- Resumen de extracción.
- Referencia exacta al manifest fuente.

---

## Motivación

El índice estructural (`structural-index-v1`) modela la jerarquía física `NODE STRUCTURE/`.
El índice de nodos M4O modela la jerarquía lógica `META4OBJECT/`. Son dominios distintos
que deben permanecer separados (ADR-0007). INC-0007 construye la primera pieza del dominio
lógico necesaria para INC-0008 (resolución de Call()).

---

## Alcance

- Extracción desde `m4o_node_json`, `m4o_alias_json`, `m4o_mapping_json`.
- Verificación hash por recurso antes de interpretarlo.
- Normalización estricta de `IS_ROOT`.
- Detección de duplicados y conflictos con política determinista.
- Orden canónico de todas las listas.
- Publicación atómica.
- Verificación en dos fases (identidad + reconstrucción exacta).
- Suite de tests completa con golden byte-idéntico.

---

## Fuera de alcance

- Resolución de aliases efectivos.
- Herencia transitiva.
- Resolución de `Call()` o `ChannelCall()`.
- Integración con `structural-index-v1`.
- Otras tablas M4O.
- Comando `compare`.

---

## Decisiones

### 1. Módulo top-level separado

El módulo `m4oindex/` es independiente de `index/`, `references/` y `manifest/`.
Importa solo modelos y servicios de `corpus/` y utilidades compartidas.
Razón: ADR-0007 — separación de dominios.

### 2. `manifest_ref` calculado desde bytes físicos

La función `build_m4o_node_index` recibe `manifest_ref` ya construido. El service
lo calcula desde los bytes físicos del manifest antes de deserializarlo. Esto permite
que `verify` compare el hash almacenado contra el hash actual sin reconstruirlo desde
el objeto en memoria.

### 3. `DIAGNOSTIC_LEVELS` no serializado

Los niveles de diagnóstico son una propiedad derivada del catálogo de códigos. No se
serializan. La validación del modelo verifica que todo código tenga exactamente un nivel.

### 4. Valores de campos no normalizados

Los valores extraídos se almacenan tal cual, sin recortar ni cambiar casing. La
validación de vacío/whitespace usa `value.strip()` solo para el check, nunca para
transformar el valor almacenado.

### 5. `IS_ROOT` None sin diagnóstico es error de validación

Un `NodeBinding` con `is_root=None` sin un `invalid_is_root` diagnostic asociado
falla `validate_index_model`. Esto garantiza trazabilidad completa.

### 6. Ficheros fallidos vs parseados

Un fichero cuenta como `successfully_parsed_file_count` si superó: localización,
lectura, hash, decodificación, JSON válido, raíz objeto. Puede tener errores de tabla
o fila y seguir contando como parseado.

### 7. Codificación de fuentes UTF-8 con BOM opcional

Los ficheros M4O JSON se decodifican con `utf-8-sig` (BOM opcional). Esto es coherente
con el entorno Windows donde estos ficheros pueden generarse con BOM.

---

## Pruebas

### Ficheros de test

```
tests/test_m4oindex/
├── __init__.py
├── conftest.py
├── generate_golden.py
├── test_cli.py
├── test_extraction.py
├── test_golden.py
├── test_models.py
├── test_serialization.py
├── test_service.py
└── test_validation.py
```

### Cobertura

- Modelos y normalización (`test_models.py`).
- Pipeline de acceso a recursos: fichero ausente, hash mismatch, encoding inválido,
  JSON inválido, raíz lista/string (`test_extraction.py`).
- Tablas ausentes, null, tipo inválido, vacías; filas no-objeto (`test_extraction.py`).
- Validación de campos: ausente, vacío, whitespace, tipo inválido (`test_extraction.py`).
- Todos los formatos válidos e inválidos de `IS_ROOT` (`test_extraction.py`).
- Diagnósticos de consistencia: id_t3_mismatch, id_node_mismatch, owner_derived_mismatch,
  path_node_reference_mismatch (`test_extraction.py`).
- Duplicados y conflictos en nodos, aliases y mappings (`test_extraction.py`).
- Serialización round-trip, formato canónico, errores de deserialización (`test_serialization.py`).
- Validación del modelo: formato, versión, summary, orden, is_root=None sin diagnostic
  (`test_validation.py`).
- Servicio build y verify, drift de manifest, recurso modificado, índice no canónico
  (`test_service.py`).
- CLI: build, verify, --force, output existente, created-at fijo, --help, exit codes
  (`test_cli.py`).
- Golden byte-idéntico (`test_golden.py`).

---

## Golden

```
tests/golden/m4object-node-index-v1.json
```

Generado con:
```python
FIXED_NOW = datetime(2026, 6, 24, 12, 0, 0, tzinfo=timezone.utc)
FIXED_GENERATOR_VERSION = "0.1.0"
corpus_id = "node-index-corpus"
```

El golden incluye hashes del manifest y evidencias. No se sobrescribe durante tests.

Para regenerar manualmente:
```powershell
python tests/test_m4oindex/generate_golden.py
```

---

## Riesgos

- La interpretación base/derivado de `SPR_DIN_OBJECTS` (ID_T3 / ID_T3_I) está observada
  en la muestra inspeccionada pero no universalmente confirmada. El índice registra los
  valores crudos; la semántica se confirma en INC-0008.
- El componente de ruta bajo `M4O ALIAS RESOLUTION/` se almacena como
  `path_node_reference` con semántica provisional. Puede no coincidir siempre con
  `id_node` del contenido JSON.
- Ficheros M4O con estructuras inesperadas (tablas extra, arrays anidados) se ignoran
  silenciosamente salvo que la tabla esperada esté presente con el tipo incorrecto.

---

## Comando de verificación

```powershell
uv run python -m pytest tests/test_m4oindex/ -q
uv run python -m ruff check .

uv run peoplenet-process-extractor m4object-node-index build `
  --corpus-root tests/fixtures/m4o_node_index_corpus `
  --corpus-manifest <manifest_path> `
  --output <output_path> `
  --created-at 2026-06-24T12:00:00+00:00

uv run peoplenet-process-extractor m4object-node-index verify `
  --corpus-root tests/fixtures/m4o_node_index_corpus `
  --corpus-manifest <manifest_path> `
  --index <output_path>
```

---

## Estado pendiente de revisión/cierre

El incremento quedará formalmente cerrado cuando:

1. El diff no contenga cambios accidentales ni rutas absolutas.
2. No existan entradas no intencionadas en `git status`.
3. Se cree el commit de cierre con todos los ficheros del incremento.
4. El árbol de trabajo quede limpio después del commit.
