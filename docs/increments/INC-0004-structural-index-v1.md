# INC-0004 — Structural Index v1

## Estado

**Cerrado**

## Identificación

- **Incremento:** INC-0004
- **Nombre:** `structural-index-v1`
- **Rama de implementación:** `feat/structural-index-v1`
- **Rama de corrección posterior:** `fix/structural-index-golden-reproducibility`
- **Repositorio:** `peoplenet-process-extractor`
- **Resultado:** aceptado, integrado y validado en `main`

---

## Objetivo

Construir un índice estructural SQLite versionado a partir de un `corpus-manifest-v1` válido y del corpus físico correspondiente.

El índice debía permitir consultar de forma eficiente:

- ficheros del corpus;
- clasificaciones;
- raíces de origen;
- Meta4Objects;
- tipos de ítem;
- nombres de ítem;
- reglas;
- fechas de regla;
- warnings;
- hashes, tamaños y procedencia.

El incremento debía limitarse a persistir y consultar estructura ya conocida, sin analizar contenido LN4 ni resolver llamadas.

---

## Motivación

Los incrementos anteriores proporcionaban:

1. `scenario-v1`;
2. `run-manifest-v1`;
3. `corpus-manifest-v1`.

Faltaba un artefacto intermedio consultable que:

- evitara recorrer repetidamente el corpus;
- preservara identidad y trazabilidad;
- sirviera de base para futuros extractores de referencias y llamadas;
- permitiera validar que el snapshot indexado coincide exactamente con el manifiesto.

---

## Alcance implementado

### Esquema SQLite versionado

Identidad:

```text
index_format = structural-index-v1
schema_version = 1
```

Tablas:

- `index_metadata`;
- `source_files`;
- `structural_elements`;
- `file_warnings`.

### Metadatos del índice

Se registran, entre otros:

- formato y versión;
- generador y versión;
- `corpus_id`;
- SHA-256 y tamaño del manifiesto;
- fecha del manifiesto;
- fecha de creación del índice;
- información Git opcional;
- contadores;
- estado de construcción.

### Ficheros

Una fila por cada entrada del manifiesto, incluyendo:

- path;
- SHA-256;
- tamaño;
- extensión;
- source root;
- clasificación;
- número de warnings.

### Elementos estructurales

Una fila por cada fichero `structured_ln4`, con:

- Meta4Object;
- item type;
- item name;
- rule ID;
- rule date.

### Warnings

Persistencia ordenada de warnings mediante:

- `source_file_id`;
- `sequence`;
- `message`.

### CLI

Comandos implementados:

```bash
peoplenet-process-extractor index build
peoplenet-process-extractor index verify
peoplenet-process-extractor index query files
peoplenet-process-extractor index query elements
peoplenet-process-extractor index query stats
```

---

## Principios aplicados

### El manifiesto gobierna el índice

El constructor:

- consume exclusivamente `corpus-manifest-v1`;
- no descubre libremente nuevos ficheros;
- no amplía el alcance de snapshots filtrados;
- respeta root-only y filtros por source root.

### Verificación previa

Antes de construir se verifica la coherencia del corpus físico con el manifiesto.

Se rechazan:

- ficheros añadidos dentro del alcance;
- ficheros eliminados;
- cambios de hash;
- cambios de tamaño;
- incoherencias estructurales.

### Equivalencia exacta manifiesto ↔ SQLite

`index verify` compara:

- paths;
- hashes;
- tamaños;
- extensiones;
- roots;
- clasificaciones;
- warning counts;
- warnings ordenados;
- estructura PeopleNet;
- identidad y metadatos del corpus.

### Construcción segura

La base se construye:

1. en un fichero temporal;
2. dentro de una transacción;
3. se valida antes de publicar;
4. se publica mediante reemplazo atómico;
5. se limpian temporales ante éxito o fallo.

No se usa WAL para la construcción offline.

### Apertura read-only portable

Las conexiones de validación y consulta usan URI correctamente escapada, incluyendo paths con:

- espacios;
- `#`;
- paréntesis;
- caracteres no ASCII.

### Reproducibilidad lógica

Se implementó una exportación lógica determinista y un golden revisable.

El export incluye:

- metadata estable;
- hashes y tamaños;
- IDs internos deterministas;
- elementos estructurales;
- warnings con `sequence` y `message`.

---

## Decisiones principales

### SQLite

Se eligió SQLite porque proporciona:

- consultas estructuradas;
- índices;
- constraints;
- integridad referencial;
- portabilidad;
- ausencia de servicio externo.

### Separación entre ficheros y elementos

`source_files` y `structural_elements` se mantienen separados para distinguir:

- identidad física del fichero;
- estructura lógica PeopleNet derivada.

### IDs internos deterministas

Los IDs se asignan según orden estable por path.

No son identidad de negocio.

### Sin ORM

Se utiliza `sqlite3` de la biblioteca estándar.

### Sin WAL

Se descartó WAL porque:

- la construcción es offline;
- no existe concurrencia útil;
- introduce sidecars;
- complica la publicación atómica.

### Warnings estructurados

Los warnings se almacenan en tabla separada para conservar:

- orden;
- contenido;
- trazabilidad.

---

## Correcciones derivadas de la revisión

La revisión independiente detectó y motivó las siguientes correcciones:

### Validación completa

Inicialmente se comparaban principalmente paths.

Se amplió la validación para cubrir todos los campos del manifiesto y la estructura completa.

### Limpieza de WAL y sidecars

Se eliminó WAL y se reforzaron pruebas de:

- temporales;
- `-wal`;
- `-shm`;
- fallo de publicación;
- conservación de la base anterior con `--force`.

### URI SQLite

Se corrigió la construcción de URI read-only para soportar `#` y otros caracteres especiales.

### Dominios cerrados

Se añadieron constraints y validación defensiva para:

- clasificaciones;
- `corpus_git_dirty`;
- hashes hexadecimales;
- formato;
- versión;
- build status.

### Golden lógico

Se fortaleció para incluir:

- hash y tamaño del manifiesto;
- hashes y tamaños de ficheros;
- IDs;
- versión del generador;
- fecha del índice;
- warnings con secuencia.

### Reproducibilidad EOL

Tras la integración se detectó un fallo en Windows por dos causas:

1. `write_text()` convertía saltos LF a CRLF al escribir el manifiesto;
2. `core.autocrlf=true` convertía fixtures textuales en el checkout.

Corrección:

- escritura mediante bytes UTF-8;
- `.gitattributes` específico con `eol=lf`;
- normalización de fixtures y golden;
- pruebas byte a byte entre generaciones.

---

## Pruebas

### Resultado final en `main`

```text
690 passed, 4 skipped
```

### Ruff

```text
All checks passed!
```

### Git

```text
On branch main
Your branch is up to date with 'origin/main'.

nothing to commit, working tree clean
```

### Cobertura relevante

Se probaron, entre otros:

- esquema y constraints;
- foreign keys;
- construcción válida;
- manifiesto inválido;
- corpus inconsistente;
- `--force`;
- fallo antes de publicación;
- fallo de `os.replace`;
- ausencia de temporales y sidecars;
- root-only;
- filtros de raíz;
- equivalencia exacta;
- manipulación de metadata;
- manipulación de ficheros;
- manipulación de elementos;
- warnings extra, ausentes y reordenados;
- URI con `#`;
- consultas parametrizadas;
- inyección tratada como valor;
- stats;
- reproducibilidad lógica;
- reproducibilidad byte a byte del manifiesto;
- golden estable entre Windows y Unix.

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

## Fuera de alcance confirmado

No se implementó:

- parsing semántico de LN4;
- extracción de `Call()`;
- resolución de referencias;
- callers/callees;
- grafo de dependencias;
- SQL embebido;
- validaciones funcionales;
- escrituras funcionales;
- integraciones externas;
- búsqueda full-text;
- actualización incremental;
- API REST;
- interfaz gráfica;
- ORM;
- integración automática completa con `run-manifest-v1`.

---

## Riesgos residuales

No quedan riesgos bloqueantes conocidos para este incremento.

Riesgos futuros:

- crecimiento del índice con corpus grandes;
- evolución de esquema;
- necesidad de migraciones;
- coste de extracción de contenido LN4;
- referencias ambiguas entre objetos y reglas.

Estos riesgos corresponden a incrementos posteriores.

---

## Resultado

El incremento proporciona una base estructural:

- determinista;
- versionada;
- consultable;
- verificable;
- trazable;
- portable entre Windows y Unix.

Sirve como punto de partida para el siguiente paso del pipeline: extracción de referencias y llamadas LN4 con evidencia.

---

## Siguiente incremento recomendado

**INC-0005 — Extracción de referencias y llamadas LN4 v1**

Alcance recomendado:

- lectura de contenido LN4;
- detección determinista de llamadas y referencias;
- preservación de fichero, línea y fragmento;
- clasificación de referencias;
- sin resolución global del grafo;
- sin interpretación funcional.
