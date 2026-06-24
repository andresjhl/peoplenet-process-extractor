## Corpus PeopleNet externo

El corpus real no forma parte de este repositorio.

La ruta se obtiene desde:

1. argumento CLI explicito, cuando el comando lo soporte;
2. variable de entorno `PEOPLENET_CORPUS_ROOT`;
3. configuracion local ignorada por Git, solo si el proyecto ya la soporta.

Reglas:

- tratar el corpus como solo lectura;
- no modificar, renombrar ni eliminar ficheros;
- no generar artefactos dentro del corpus;
- no copiar contenido real a fixtures sin anonimizacion y aprobacion;
- no incluir rutas absolutas en codigo, tests, golden files o documentacion versionada;
- usar unicamente fixtures anonimizados en pruebas automatizadas;
- registrar las rutas consultadas como evidencia en inspecciones;
- detenerse con error claro si la ruta requerida no esta configurada.
