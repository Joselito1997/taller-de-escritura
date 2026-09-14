# Operaciones del helper según la tarea

Lee solo la rama necesaria. Usa el prefijo instalado y transporte literal del [contrato compartido](workflow-contract.md#preparar-y-guardar-sin-sobrescribir), sustituyendo la operación y el JSON. Comprueba la capacidad real y la respuesta; no suplas una operación ausente con shell general, otra cuenta o un proveedor nuevo.

## Importar archivos

El procedimiento [Importar](../skills/import/SKILL.md) conserva decisiones, cobertura y límites de conversión. Su operación es `import`:

```json
{"schema_version":1,"operation_id":"importar-001","input_root":"/ruta/elegida","files":["capitulo.txt","conversacion.json"]}
```

`input_root` es la carpeta elegida por el autor; `files` contiene rutas relativas a ella. La operación exige inicialización privada comprobada y ausencia de remotos reaparecidos. Si falta esa preparación, informa el bloqueo y conserva la comparación permitida sin afirmar importación. No ejecutes setup ni cambies Git para eludirlo.

El resultado conserva originales, derivados y cursor por unidades. Repite la misma solicitud e ID para continuar el lote; una entrada externa disponible con bytes distintos necesita otra operación. Si desaparece la entrada, la reanudación puede usar el original inmutable ya conservado. Un conversor cambiado entre lotes detiene la reanudación.

`ledger.candidates` devuelve `target`, `expected_file_sha256`, `candidate_path`, `candidate_sha256` y `format`. Usa esos valores en una nueva operación `apply` con el alcance autorizado; los candidatos importados no se aplican ni seleccionan solos. Conserva `role`/`content_role`, fecha, cobertura y hash del texto extraído. Si se agrupan versiones, `target_map` debe expresar una agrupación elegida, nunca una selección inferida.

Un JSON desconocido puede conservarse como `unsupported-schema`; páginas sin texto quedan `needs-ocr`. Si faltan adaptador o dependencias, declara la cobertura real y los originales efectivamente conservados. Un original guardado no demuestra conversión completa, reconstrucción aceptada ni soporte de cualquier exportación de cuenta.

## Consultar fuentes públicas

[Investigar](../skills/research/SKILL.md) posee selección de fuentes, privacidad, presupuestos y condiciones de parada. Las conexiones `writing-exa` y `writing-firecrawl` se invocan por la rama `import` con `kind: research`, no mediante shell o credenciales generales:

```json
{"schema_version":1,"operation_id":"consulta-001","brief_id":"informe-001","kind":"research","mode":"quick","tool":"web_search_exa","arguments":{"query":"estructura narrativa de escenas"},"public_query_confirmed":true}
```

Mantén el mismo `brief_id` para contabilizar la investigación y una identidad de operación por solicitud. `mode` admite `quick`, `standard` o `extended`; la última exige autorización expresa y `extended_authorized: true`. `public_query_confirmed` registra que la consulta es pública y no contiene datos privados, no concede autorización para divulgar el libro.

`tool` admite `web_search_exa`, `web_fetch_exa`, `firecrawl_scrape` y `preserve_pdf`. La búsqueda usa `arguments.query`; las lecturas admiten `arguments.url` o `arguments.urls` según el contrato de la herramienta instalada. Para `preserve_pdf` usa solo `arguments.url`. `preserve_pdf` conserva bytes de un PDF público seleccionado; no busca ni convierte páginas. Usa HTTPS público sin credenciales ni redirecciones, con los límites del helper. Después Importar puede convertir ese mismo `original.pdf` bajo investigación sin duplicarlo.

`refresh: true` pide una lectura nueva; `offline: true` reutiliza una respuesta guardada con su edad o informa indisponibilidad. `max_age_seconds` limita la edad aceptada, con 86400 como valor predeterminado. Conserva URL, hash y fecha de la respuesta usada. Una extracción guardada tiene cobertura parcial, no equivale a documento íntegro. No llames a un proveedor si el entorno no lo expone o el alcance prohíbe red; informa cero llamadas cuando no hubo ninguna. Fallos de acceso, autenticación o presupuesto se explican con el resultado real y las reglas de parada de Investigar, sin instalar ni cambiar proveedor.

## Exportar para lectura

Esta operación sigue la petición explícita y el [procedimiento de exportar](../skills/handoff/references/export.md). Usa `export`:

```json
{"schema_version":1,"operation_id":"lectura-001","targets":["manuscrito/capitulo-001.md"],"docx":true,"numbering":false,"contents":false,"preliminaries":false,"title":"Título confirmado","author":"Autor confirmado"}
```

Omite `targets` para el índice completo o indica el subconjunto pedido en su orden. Omite título/autor desconocidos. El helper conserva entradas estables y manifiesto en una carpeta nueva bajo `exportaciones/`, produce Markdown y solicita DOCX cuando `docx` es true. No reutilices el ID para otra exportación. Solo admite esas claves; otra clave o un valor que no sea `true`/`false` en `docx`, `numbering`, `contents` o `preliminaries` se rechaza sin exportar. Por omisión `docx` es true y las otras tres son false, con la salida de siempre.

- `numbering: true` numera cada capítulo por su posición actual en `Orden de lectura`, nunca por su `ch-NNN`. Una selección conserva esa posición: exportar solo el tercer y cuarto capítulo da `Capítulo 3` y `Capítulo 4`. Solo cambia el título inicial `# ` del capítulo, que queda `# Capítulo N. Título`, o `# Capítulo N` si no tiene título; no añade un segundo título ni toca encabezados de escena. No la pidas si los títulos ya llevan número.
- `contents: true` añade tras los preliminares un apartado `# Índice` con una viñeta por capítulo seleccionado, en orden y con el mismo título exportado. Es texto normal en Markdown y DOCX, sin números de página ni campo de Word que actualizar. Un capítulo sin título se rechaza salvo que se pida numeración.
- `preliminaries: true` incluye primero `manuscrito/preliminares.md` para portada, dedicatoria o epígrafe. Usa el formato de capítulo (`type: chapter`, `id` `ch-NNN` único y `title`, que puede quedar vacío) y no figura en `Orden de lectura`. Su cuerpo sale tal cual, sin título añadido, numeración ni entrada en el índice. Si falta, tiene otro formato o está listado en el orden, se rechaza; otro material fuera del orden no se exporta.

El manifiesto de salida registra `options` y, por entrada, `role` (`chapter` o `preliminaries`), `position`, `sha256` de bytes, `prose_sha256` (el mismo hash normalizado de aceptación), palabras y estado de versión.

Comprueba rutas y hashes de salidas, y la validez indicada. Un cambio durante captura invalida el intento; no presentes una mezcla como exportación terminada. Si falta Pandoc, informa Markdown disponible y DOCX ausente según el resultado real. Sin operación implementada, deja el alcance resuelto en conversación sin fabricar archivos. La verificación de bytes no sustituye revisar el documento en un visor. Exportar no publica, acepta prosa ni termina una etapa.
