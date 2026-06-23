# ADR-0002 — Manifiesto de ejecución como registro de procedencia

**Estado:** Aceptado  
**Fecha:** 2026-06-23

---

## Contexto

El pipeline de extracción de PeopleNet procesa escenarios, trazas y código LN4 para generar modelos y documentación. Sin un registro de ejecución:

- Es imposible reproducir una ejecución pasada.
- No hay forma de detectar si un fichero de entrada fue modificado después de una ejecución.
- Los artefactos generados no tienen procedencia trazable.
- Múltiples ejecuciones concurrentes o sucesivas del mismo escenario interfieren entre sí si comparten directorios de salida.

## Problema

Necesitamos un mecanismo que:

1. Identifique de forma estable cada ejecución.
2. Registre qué entradas y versiones de herramientas participaron.
3. Permita verificar que los ficheros registrados no han cambiado.
4. Sea portable entre máquinas sin depender de rutas absolutas.
5. No requiera base de datos ni servicio externo.

## Decisión

### 1. Un directorio exclusivo por ejecución

Cada ejecución crea un directorio propio bajo `runs/<run_id>/`. No existe un workspace global compartido.

**Estructura:**
```
runs/<run_id>/
├── run-manifest.json
├── inputs/
│   └── scenario.json
├── artifacts/
└── reports/
```

**Por qué:** Elimina interferencias entre ejecuciones. Un directorio por run es la unidad de aislamiento más simple y efectiva. Permite borrar un run completo sin afectar otros.

### 2. Manifiesto como índice de ejecución

`run-manifest.json` es el único fichero que describe la ejecución. Contiene:

- Identificador del run (`run_id`).
- Estado de la ejecución.
- Referencia al escenario con hash SHA-256.
- Lista de fuentes (inputs con hashes).
- Lista de herramientas con versiones.
- Lista de artefactos con estado y procedencia.
- Secuencia de eventos.
- Warnings y errores estructurados.

**Por qué:** Un único fichero JSON en la raíz del run es suficiente para describir todo su contenido. No necesita base de datos. Es legible y editable manualmente en casos de emergencia.

### 3. Hashes SHA-256 sobre inputs y artefactos

Todos los ficheros relevantes se hashean con SHA-256 en el momento de su registro.

**Por qué:** SHA-256 es suficientemente fuerte para detectar modificaciones accidentales y está disponible en la biblioteca estándar de Python (`hashlib`). Los bytes se leen sin normalización para que el hash refleje exactamente el contenido del fichero.

### 4. Rutas relativas al directorio del run

El manifiesto almacena rutas relativas al directorio del run, con `/` como separador.

**Por qué:** Hace el manifiesto portable entre máquinas y sistemas operativos. Una ruta absoluta como `C:\Users\...` invalida el manifiesto en cualquier otra máquina.

### 5. Escritura atómica del manifiesto

`run-manifest.json` se escribe vía fichero temporal y `rename` atómico. Si la escritura falla, el fichero anterior no se corrompe.

**Por qué:** Un fallo a mitad de escritura dejaría un JSON parcial ilegible. El patrón temp+rename garantiza que el fichero publicado siempre es válido o no existe.

### 6. Construcción en staging y publicación atómica del run

`manifest create` construye el run completo en un directorio staging (`.<run_id>.staging-<suffix>`) y solo al final renombra staging al directorio definitivo. Si existe un run anterior y se usa `--force`, se mueve a backup antes del rename; si el rename falla, se restaura el backup.

**Por qué:** La alternativa (`rmtree` + `mkdir`) deja un intervalo en el que el run anterior ya no existe pero el nuevo todavía no. Si el proceso muere en ese hueco, se pierde el run anterior sin haber creado el nuevo. El patrón staging elimina ese riesgo: el run anterior solo desaparece cuando el nuevo está completamente listo.

### 7. Espacio de nombres global de IDs

Los IDs de fuentes y artefactos comparten un único espacio de nombres. No se permite el mismo ID en ambas colecciones.

**Por qué:** Permite que `derived_from` y `reference_id` en eventos referencien cualquier entidad de procedencia sin ambigüedad. Una referencia compartida es imposible de resolver si fuentes y artefactos pueden tener IDs idénticos.

### 8. Unicidad de sequencias y timestamps con timezone

Las secuencias de eventos deben ser enteros positivos y estrictamente crecientes por posición de lista. Los timestamps deben incluir timezone explícita (se acepta `Z` o `+HH:MM`); los timestamps naives son rechazados.

**Por qué:** Sin estas restricciones un manifiesto podría construirse con datos temporales incorrectos que pasen la validación sin advertencia, dificultando el diagnóstico post-mortem.

---

## Alternativas consideradas

| Alternativa                      | Razón de rechazo                                              |
|----------------------------------|---------------------------------------------------------------|
| Índice SQLite global             | Dependencia externa, no portable, más complejo de mantener   |
| Directorio de salida compartido  | Interferencias entre ejecuciones, imposible trazar procedencia|
| Log de texto plano               | No estructurado, difícil de validar y procesar               |
| Base de datos relacional         | Infraestructura excesiva para la fase actual del proyecto     |
| JSON Schema externo              | Dependencia innecesaria; la validación está en código Python  |

---

## Consecuencias

- Cada ejecución ocupa su propio directorio. Para ejecutar el mismo escenario varias veces se necesita un `run_id` diferente.
- El tamaño del directorio `runs/` crece con cada ejecución. El borrado es responsabilidad del usuario (no hay borrado automático).
- La verificación de integridad (`manifest verify`) recomputa hashes; no es instantánea para ficheros grandes.
- El manifiesto no es transaccional: si el proceso muere a mitad de ejecución, el run queda en estado incompleto. La reanudación no está implementada.

---

## Fuera de alcance de este ADR

- Análisis de código LN4.
- Generación funcional de artefactos (solo su representación).
- Índice global de runs.
- Ejecución paralela.
- Reanudación de runs interrumpidos.
- Firma criptográfica de artefactos.
- Almacenamiento remoto.
