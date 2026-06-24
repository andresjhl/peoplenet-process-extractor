# INC-0006 — META4OBJECT Resources in corpus-manifest-v1

## Estado

Implementado en `main`, pendiente de commit de cierre.

## Identificación

- **Incremento:** INC-0006
- **Nombre:** `m4object-resources-manifest-v1`
- **Repositorio:** `peoplenet-process-extractor`
- **Schema afectado:** `corpus-manifest-v1` → versión `1.1`

---

## Objetivo

Extender `corpus-manifest-v1` para descubrir, clasificar y registrar los recursos META4OBJECT presentes en el corpus (`NODE`, `M4O ALIAS RESOLUTION`, `MAPPING META4OBJECT`), sin leer el contenido JSON de los ficheros.

El incremento no implementa resolución de aliases, herencia, Call() ni construcción de índice de nodos.

---

## Motivación

El corpus PeopleNet contiene una segunda jerarquía de ficheros bajo `<source_root>/META4OBJECT/` que la versión 1.0 del manifiesto clasificaba como `other_supported`. Disponer de los tres patrones reconocidos con sus identificadores (`id_t3`, `id_node`) permite que etapas posteriores del pipeline filtren y accedan a los recursos M4O sin necesidad de re-escanear el corpus.

---

## Cambios en el esquema

### Versión 1.0 → 1.1

| Aspecto | Antes (1.0) | Después (1.1) |
|---------|-------------|---------------|
| `schema_version` | `"1.0"` | `"1.1"` |
| `FileEntry.m4o_structure` | ausente | presente (null o objeto) |
| Clasificaciones M4O | `other_supported` | `m4o_node_json`, `m4o_alias_json`, `m4o_mapping_json` |

**Compatibilidad retroactiva:** Los manifiestos 1.0 se leen correctamente; el campo `m4o_structure` ausente se trata como `null`.

---

## Patrones META4OBJECT reconocidos

| Patrón | Ruta | Clasificación |
|--------|------|---------------|
| NODE | `<src>/META4OBJECT/<ID_T3>/NODE/<ID_NODE>/<file>.json` | `m4o_node_json` |
| M4O ALIAS RESOLUTION | `<src>/META4OBJECT/<ID_T3>/M4O ALIAS RESOLUTION/<ID_NODE>/<file>.json` | `m4o_alias_json` |
| MAPPING META4OBJECT | `<src>/META4OBJECT/<ID_T3>/MAPPING META4OBJECT/<ID_T3>/<file>.json` | `m4o_mapping_json` |

### Reglas de clasificación

- Solo se reconocen ficheros `.json`; otras extensiones resultan en `other_supported` sin warning.
- `ID_T3` e `ID_NODE` deben ser no vacíos (ni solo espacios).
- En MAPPING, el `ID_T3` interior debe coincidir exactamente con el exterior.
- La profundidad debe ser exactamente 6 componentes.
- Los patrones desconocidos bajo `META4OBJECT` son `other_supported` sin warning.
- Si un fichero en META4OBJECT tiene nombre `metadata.json`, prevalece la regla de mayor prioridad (`metadata_json`); los warnings M4O se descartan.

### Warnings M4O

| Código | Causa |
|--------|-------|
| `malformed_m4o_node_path` | Ruta NODE mal formada (profundidad incorrecta, `ID_T3`/`ID_NODE` vacíos). |
| `malformed_m4o_alias_path` | Ruta M4O ALIAS RESOLUTION mal formada. |
| `malformed_m4o_mapping_path` | Ruta MAPPING mal formada (`ID_T3` mismatch, vacíos, profundidad incorrecta). |

Los warnings M4O solo se incluyen cuando la clasificación final es `m4o_*` o `other_supported`. Si una regla de mayor prioridad gana, los warnings M4O se suprimen.

---

## Nuevos tipos de datos

### `M4oStructure`

```python
@dataclass(frozen=True)
class M4oStructure:
    id_t3: str        # META4OBJECT identifier, always non-empty
    id_node: str | None  # Node identifier; None for MAPPING pattern
```

Mutuamente exclusivo con `Ln4Structure` en `FileEntry`.

### Ejemplo de FileEntry (m4o_node_json)

```json
{
  "path": "CP/META4OBJECT/OBJ_T3_A/NODE/NODE_X/node_x.json",
  "sha256": "...",
  "size_bytes": 2,
  "extension": ".json",
  "source_root": "CP",
  "classification": "m4o_node_json",
  "structure": null,
  "m4o_structure": { "id_t3": "OBJ_T3_A", "id_node": "NODE_X" },
  "warnings": []
}
```

---

## Nuevos códigos de validación

| Código | Condición |
|--------|-----------|
| `missing_m4o_structure` | Clasificación M4O pero `m4o_structure` es null. |
| `unexpected_m4o_structure` | `m4o_structure` presente para clasificación no-M4O. |
| `missing_id_node_for_m4o_resource` | NODE/ALIAS con `id_node=null`. |
| `mapping_m4o_structure_has_id_node` | MAPPING con `id_node` no nulo. |
| `empty_m4o_id_t3` | `m4o_structure.id_t3` es cadena vacía. |

---

## Archivos modificados / creados

| Fichero | Cambio |
|---------|--------|
| `src/.../corpus/enums.py` | Tres nuevas clasificaciones M4O. |
| `src/.../corpus/models.py` | `M4oStructure`, `FileEntry.m4o_structure`, `SUPPORTED_SCHEMA_VERSIONS`. |
| `src/.../corpus/path_parsing.py` | `parse_m4o_path`, `_parse_m4o_node`, `_parse_m4o_mapping`. |
| `src/.../corpus/inventory.py` | `classify_file` delega en `parse_m4o_path`; `build_file_entry` filtra warnings M4O. |
| `src/.../corpus/serialization.py` | Serialización/deserialización de `m4o_structure`. |
| `src/.../corpus/validation.py` | Coherencia `m4o_structure` ↔ clasificación. |
| `src/.../corpus/comparison.py` | `_structure_key` extendido con tag `"m4o"`. |
| `src/.../corpus/service.py` | `schema_version="1.1"`. |
| `tests/fixtures/m4o_manifest_corpus/` | 7 ficheros JSON de fixture M4O. |
| `tests/golden/m4o-corpus-manifest-v1.json` | Golden del manifiesto M4O fixture. |
| `tests/test_corpus/test_m4o.py` | Tests exhaustivos del módulo M4O. |
| `tests/golden/structural-index-v1.json` | Actualizado `corpus_manifest_sha256`/`size_bytes`. |
| `tests/golden/reference-extraction-v1.json` | Actualizado hashes derivados del manifiesto. |
| `docs/schemas/corpus-manifest-v1.md` | Documentación schema 1.1. |

---

## Restricciones aplicadas

- No se lee el contenido JSON de ningún fichero del corpus.
- `PEOPLENET_CORPUS_ROOT` es de solo lectura; no se modifica ni se usa en tests.
- Los tests usan exclusivamente fixtures anónimas.
- No se han añadido rutas absolutas al código ni a los goldens.
- El incremento no implementa resolución de aliases, herencia Call(), ni índice de nodos M4O.

---

## Riesgos

**Riesgos reales:**

- El reconocimiento de patrones se basa en las rutas observadas en el corpus actual. Si Meta4/PeopleNet introduce subdirectorios adicionales bajo `META4OBJECT/` con nombres distintos, serán clasificados como `other_supported` sin warning hasta que el parser se amplíe.
- El contenido de los ficheros JSON M4O no se interpreta: el manifiesto registra existencia y metadatos de ruta, no la semántica del recurso. Inconsistencias internas en el JSON son invisibles a este incremento.
- `structural_elements.meta4object` en el índice estructural conserva su nombre histórico aunque semánticamente contiene `ID_T3`; esta divergencia entre nomenclatura de campo y semántica deberá resolverse de forma coordinada con futuros incrementos.
- INC-0007 dependerá de interpretar correctamente los objetos descubiertos aquí (`M4RCH_NODES`, `M4RCH_T3_ALIAS_RES`, `SPR_DIN_OBJECTS` y similares); si los patrones de ruta de esos objetos difieren de los tres reconocidos en este incremento, el parser requerirá extensión.
- Futuros cambios en la estructura de directorios del corpus (p. ej. anidamiento adicional, renombrado de etiquetas) pueden invalidar las reglas de profundidad fija (`_M4O_DEPTH = 6`) sin error explícito: los ficheros afectados pasarán silenciosamente a `other_supported`.

**Fuera de alcance (no son riesgos del presente incremento):**

- Resolución de aliases M4O.
- Construcción de grafo de herencia o dependencias entre objetos.
- Interpretación de expresiones `Call()` en contexto M4O.
- Validación semántica del contenido JSON de los recursos M4O.

---

## Verificación

Comandos ejecutados y resultados reales:

```powershell
python -m pytest -q
```

```text
951 passed, 4 skipped
```

```powershell
python -m ruff check .
```

```text
All checks passed!
```

```powershell
peoplenet-process-extractor corpus verify `
  --corpus-root tests/fixtures/m4o_manifest_corpus `
  tests/golden/m4o-corpus-manifest-v1.json
```

```text
Corpus matches manifest exactly. 7 files verified.
```

---

## Criterio de cierre

El incremento quedará formalmente cerrado cuando:

1. El diff final no contenga cambios accidentales (artefactos temporales, rutas absolutas, ficheros de depuración).
2. No existan entradas sin seguimiento no intencionadas en `git status`.
3. Se cree el commit de cierre con todos los ficheros del incremento.
4. El árbol de trabajo quede limpio después del commit (`git status` sin cambios).
