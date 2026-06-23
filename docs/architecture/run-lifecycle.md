# Ciclo de vida de un run

## Visión general

Un *run* es una ejecución identificada del pipeline de extracción. Su ciclo de vida es:

```
[crear run]
     │
     ▼
 prepared  ──────────────────────────────────────────────────────► [verify]
     │
     │  (fases futuras)
     ▼
 running
     │
     ├── éxito ──► succeeded
     │
     └── fallo ──► failed
                       │
                       └── [verify] (diagnóstico post-mortem)
```

---

## Fase 1: Creación (`prepared`) — **implementada en este incremento**

El comando `manifest create` ejecuta los siguientes pasos:

1. **Rechazar symlinks de escenario**. El path del escenario debe ser un fichero regular.
2. **Leer y validar el escenario** (`scenario-v1`). Si el escenario es inválido, se rechaza sin crear ningún directorio.
3. **Resolver o generar `run_id`**. Si no se proporciona `--run-id`, se genera como `run-YYYYMMDD-<8hex>`. El directorio final siempre es `<runs-root>/<run_id>/`.
4. **Verificar el directorio de destino**. Sin `--force`: rechazado si existe. Con `--force`: solo se permite sobrescribir si el run existente contiene `run-manifest.json` válido con `run_id` coincidente y ningún fichero ajeno en la raíz del run.
5. **Construir en staging**. El trabajo ocurre en `<runs-root>/.<run_id>.staging-<suffix>/`:
   ```
   .run-20260623-abc12345.staging-efgh5678/
   ├── inputs/
   ├── artifacts/
   └── reports/
   ```
6. **Copiar el escenario** a `staging/inputs/scenario.json`.
7. **Calcular hash y tamaño** de la copia.
8. **Construir el manifiesto** en memoria y validarlo estructuralmente.
9. **Escribir `run-manifest.json`** de forma atómica dentro del staging.
10. **Publicar**: renombrar staging → directorio final. Si existía un run anterior, se mueve a backup antes del rename; si el rename falla, se restaura el backup.

Si cualquier paso falla antes de la publicación, el staging se elimina. El run anterior permanece intacto hasta que la publicación complete con éxito.

### Estado del run al finalizar `create`

```json
{
  "status": "prepared",
  "started_at": null,
  "finished_at": null,
  "events": [{ "sequence": 1, "type": "prepared", ... }]
}
```

---

## Fases 2-N: Ejecución (`running` → `succeeded`/`failed`) — **no implementadas**

Las fases siguientes son responsabilidad de módulos futuros del pipeline:

- **Descubrimiento de dependencias**: analizar el escenario y encontrar código LN4 relacionado.
- **Extracción de hechos**: extraer información estructurada de trazas y código.
- **Construcción del modelo intermedio**: representar el comportamiento en un modelo versionado.
- **Interpretación semántica**: usar LLM para interpretar comportamiento con evidencia estructurada.
- **Generación de documentación**: producir Markdown reproducible.

Cada fase actualizaría el manifiesto:
- Cambiaría `status` a `running` al comenzar.
- Añadiría eventos `artifact_generated`, `warning`, `error`.
- Registraría cada artefacto con su hash y procedencia.
- Cambiaría `status` a `succeeded` o `failed` al terminar.
- Fijaría `started_at` y `finished_at`.

---

## Verificación (`verify`) — **implementada en este incremento**

El comando `manifest verify`:

1. Carga el manifiesto desde `run-manifest.json`.
2. Valida su estructura (incluyendo consistencia entre `scenario` y la fuente `kind=scenario`).
3. Resuelve rutas relativas desde el directorio del run.
4. Para cada fichero a verificar:
   - Rechaza symlinks (`is_symlink()` → error).
   - Rechaza rutas que resuelven fuera del directorio del run (`resolve().relative_to()` → error).
5. Recomputa SHA-256 y tamaño del escenario y demás fuentes y artefactos.
   - El escenario se verifica una vez vía `manifest.scenario`; la fuente con `kind=scenario` se salta para evitar doble verificación (la validación estructural garantiza que sus campos coincidan).
6. Reporta:
   - Ficheros ausentes.
   - Symlinks detectados.
   - Rutas que escapan del directorio del run.
   - Discrepancias de tamaño o hash.
   - Errores de validación estructural.
7. Devuelve `0` si todo coincide, `2` si hay problemas.

La verificación **no modifica** el manifiesto.

---

## Qué está implementado en este incremento

| Componente                        | Estado          |
|-----------------------------------|-----------------|
| Modelo `run-manifest-v1`          | ✓ Implementado  |
| Serialización JSON (round-trip)   | ✓ Implementado  |
| Validación estructural            | ✓ Implementado  |
| Hashing SHA-256 incremental       | ✓ Implementado  |
| `manifest create`                 | ✓ Implementado  |
| `manifest verify`                 | ✓ Implementado  |
| Escritura atómica del manifiesto  | ✓ Implementado  |
| Estructura de directorios del run | ✓ Implementado  |
| Copia y hash del escenario        | ✓ Implementado  |
| Registro de herramienta principal | ✓ Implementado  |
| Evento `prepared`                 | ✓ Implementado  |

## Qué no está implementado

| Componente                          | Estado       |
|-------------------------------------|--------------|
| Transición `prepared → running`     | Futuro       |
| Registro de artefactos generados    | Futuro       |
| Análisis de código LN4              | Futuro       |
| Extracción de hechos                | Futuro       |
| Modelo intermedio                   | Futuro       |
| Interpretación semántica (LLM)      | Futuro       |
| Generación de Markdown              | Futuro       |
| Reanudación de runs interrumpidos   | Fuera de scope|
| Índice global de runs               | Fuera de scope|
| Paralelismo                         | Fuera de scope|
