> Copia de lectura de `.claude/references/records.md`.

# Registros, versiones y tablero

Consulta esta referencia al leer o escribir registros. El [contrato de trabajo](workflow-contract.md) conserva autoridad, etapa y guardado. El asistente mantiene notas legibles; el autor no necesita llenar formularios. Recupera información existente y deja desconocidos como null u omisión, sin inventar biografías, fechas o aceptación.

## Moldes e instancias

Los dieciocho moldes están en [templates](../templates/status.md). Usan `id: null` porque no son registros activos. Para una instancia completa el contenido necesario y retira los textos de ayuda. `snapshot` con `allocate_id: true` asigna la identidad bajo bloqueo. Una identidad asignada no hace activo un candidato ni acepta su prosa. El tablero conserva su codificación de complemento y no lleva identidad YAML ordinaria.

Los registros activos tienen `schema_version: 1`, `id` inmutable y `type`. No cambies IDs al renombrar o reordenar. Las relaciones son wikilinks relativos a la bóveda entre comillas o listas de esas cadenas. `tags` y `aliases` mantienen su sentido nativo. Marcas temporales llevan zona, por ejemplo `2026-09-11T20:00:00-04:00`. Conserva campos desconocidos compatibles y bytes fuera del cambio. Versiones de esquema no admitidas, tipos erróneos, claves duplicadas y etiquetas inseguras requieren diagnóstico, no reescritura optimista.

`inicio.md` e `investigacion/indice.md` usan `type: index`, `index_kind: navigation`. `manuscrito/indice.md` usa `index_kind: manuscript` y el encabezado exacto `## Orden de lectura`; su lista vacía es válida. Solo esa lista posee el orden, con capítulos únicos y enlaces existentes. Identifica los objetivos futuros como planeados, sin aparentar enlaces válidos a archivos ausentes.

## Plantillas y responsabilidad

| Molde | Tipo y contenido que completa el asistente |
| --- | --- |
| [status](../templates/status.md) | `status`: etapa, foco, bitácora, próximo paso, limitación y recuperación |
| [creative-direction](../templates/creative-direction.md) | `creative-direction`: idioma, decisiones narrativas, preferencias con alcance y ejemplos aprobados |
| [chapter](../templates/chapter.md) | `chapter`: identidad `ch-NNN`, título y solo prosa con sus encabezados y anclas |
| [character](../templates/character.md) | `character`: rasgos, objetivos, relaciones, apariencia, voz, conocimiento temporal y cambios pendientes juntos |
| [relationship](../templates/relationship.md) | `relationship`: participantes, cada perspectiva, cambios y evidencia |
| [location](../templates/location.md) | `location`: alcance, hechos físicos, acceso, condiciones por momento y cambios |
| [faction](../templates/faction.md) | `faction`: objetivos, capacidades, diferencias internas, relaciones y afirmaciones |
| [world-rule](../templates/world-rule.md) | `world-rule`: asunto, alcance temporal y espacial, capacidad, límites, excepciones, evidencia y supuestos ficticios |
| [timeline-event](../templates/timeline-event.md) | `timeline-event`: fecha nullable, precisión, orden parcial, participantes y consecuencias de conocimiento |
| [plan](../templates/plan.md) | `plan`: objetivos, decisión, encargo, opciones, enfoque, restricciones, dependencias y comprobaciones |
| [alternative](../templates/alternative.md) | `alternative`: objetivo, selección, localizador base, aplicación, candidato y motivo |
| [finding](../templates/finding.md) | `finding`: objetivos, categoría, severidad, tarea, evidencia, acción y razón de descarte |
| [source](../templates/source.md) | `source`: bibliografía, edición, captura, tipo, original, cobertura, hash, derechos y límites |
| [topic](../templates/topic.md) | `topic`: fuentes, síntesis, desacuerdos, dudas e informes |
| [research-brief](../templates/research-brief.md) | `research-brief`: pregunta, alcance, respuesta, evidencia, límites, uso de herramientas y aplicaciones propuestas |
| [import-inventory](../templates/import-inventory.md) | `import-inventory`: originales por hash, derivados, unidades cubiertas, fallos, candidatos y reanudación |
| [session-log](../templates/session-log.md) | `session-log`: sesión, decisiones, versiones, resultados y puntos de guardado |
| [revision-backlog](../templates/revision-backlog.md) | Formato `kanban`: único estado de trabajo, seis columnas, tarjetas e historial |

Los planes y hallazgos viven en `planes/`; alternativas, en `alternativas/`. Las carpetas de personajes, relaciones, lugares y facciones existen desde la instalación en `historia/personajes/`, `historia/relaciones/`, `historia/lugares/`, `historia/facciones/`. Reglas y cronología empiezan en `historia/reglas-del-mundo.md` e `historia/cronologia.md` cuando existan hechos, con registros vinculados si crecen. Todas las carpetas de contenido se crean vacías desde la instalación, según `VAULT_DIRECTORIES` en `schemas.py`; `check action: layout` informa su existencia real. No se crean archivos ficticios ni plantillas vacías para poblarlas. Cualquier información aportada sobre una entidad basta para crear su nota durante la importación.

## Cobertura obligatoria de la importación

La importación debe registrar toda información disponible, aunque sea escasa. Cada personaje o entidad identificable recibe una nota mínima respaldada; no exijas biografía, nombre propio, protagonismo, utilidad ni un mínimo de palabras. Los campos sin datos quedan null u omitidos. Una referencia breve no permite inventar rasgos. Mantén un dato del documento de idea separado de lo que muestran los capítulos, una posibilidad separada de un hecho y versiones contradictorias sin elegir por tu cuenta.

Recorre las categorías de `IMPORT_RECORDS` en `schemas.py`: personajes, relaciones, lugares, facciones, reglas, cronología, planes, alternativas, fuentes, temas e informes. Usa sus destinos y moldes. Registra planes o informes que ya existan en lo aportado, sin crear nuevas tareas de planificación o investigación. Manuscrito, originales, derivados, inventario, estado, tablero y bitácora conservan además sus obligaciones habituales. `exportaciones/` permanece vacía hasta una exportación solicitada; una carpeta vacía no es trabajo pendiente si las fuentes no contienen información para ella. No produzcas documentos ni datos para llenar carpetas.

En la cabecera del inventario conserva `reconstruction`:

- `reviewed_sources`: mapa de ruta original conservada a su SHA256, para todas las fuentes revisadas. `check action: import-coverage` devuelve el alcance real en `source_scope`; leerlo no sustituye leer las fuentes.
- `categories`: un objeto por cada categoría, con `status: recorded`, `no-source` o `pending` y `records: [{path, sha256}]`. Usa hashes reales de notas ya guardadas, obtenidos de los resultados del helper. `recorded` exige notas en la ruta y tipo de esa categoría. Una nota parcial con un solo dato cuenta; desconocidos no impiden guardarla.
- `no-source` solo significa que, después de revisar las fuentes del alcance, no existe información para esa categoría; deja `records: []` y explica la ausencia en `reason`. No significa poca información, poca importancia o falta de tiempo. Si no has leído una fuente o no preparaste una nota necesaria, usa `pending` con el motivo.

Presenta las notas propuestas junto con la reconstrucción, sin pedir otra autorización para prepararlas. Después de guardar y anotar las operaciones en bitácora, ejecuta `check action: import-coverage`. Solo `complete: true` permite declarar el cierre. El helper comprueba categorías declaradas, rutas, tipos, hashes, fuentes, carpetas y operaciones sin registrar; no puede demostrar por sí solo que el asistente haya reconocido todas las entidades del texto. Relee el material por categorías antes del cierre para contrastar que ninguna mención respaldada quedó solo en los originales. Si hay límites reales, declara qué parte falta; no reduzcas el alcance en silencio.

## Escenas y evidencia exacta

El helper asigna `ch-NNN` con comprobación de colisiones. La identidad no indica posición de lectura. `title` contiene el título humano, o cadena vacía si no se conoce; no inventes uno para validar.

Cada escena identificada usa `sc-` seguido de UUID4 como identificador de bloque nativo de Obsidian en su primer párrafo, después del encabezado o separador. Un comentario HTML no sirve como ancla. Los límites van desde encabezado de escena o línea independiente `* * *` hasta el siguiente límite o fin de capítulo. El inicio anterior al primer límite puede ser una escena. Texto aún sin segmentar usa localizador de capítulo o párrafo hasta establecer límites, sin inventar anclas.

Un localizador contiene ruta de capítulo, ID de escena si existe, encabezado actual, hash del tramo y cita breve de apoyo. Obtén intervalos y hashes de texto compartido con la lectura exacta de `check action: inspect` descrita en el [guardado](workflow-contract.md#preparar-y-guardar-sin-sobrescribir); no calcules hashes con shell general ni los inventes. Para originales usa página, ID y rol de mensaje, sección o unidades de conversión exactas, más hash de la fuente y versión del derivado. Si un ancla desaparece o se mueve, no adivines su sustituto. Un movimiento deliberado conserva ID y actualiza ruta; división o fusión recibe IDs nuevos y vínculos `predecessors`. Detecta duplicados antes de confiar en enlaces.

Distingue tres hashes: evidencia sobre el tramo citado; base de escritura sobre bytes completos del archivo; aceptación sobre la prosa identificada, normalizando solo finales de línea y excluyendo únicamente cabecera y marcadores de ID del sistema. Nunca elimines puntuación o espacios internos. No uses un hash de nota como si fuera hash del original externo.

## Afirmaciones y conocimiento

Cada afirmación importante de una nota mantiene bloque `claim-UUID`, texto, `basis`, localizador, `as_of` opcional y `provenance`. Puedes usar un bloque de líneas rotuladas legibles; no hace falta convertir toda la nota en una tabla ni declarar todo canon. Ejemplo de forma, que se completa con evidencia real al instanciar:

```text
Afirmación: contenido respaldado. ^claim-UUID
basis: working-text
Fuente: ruta, escena o párrafo, encabezado, hash del tramo y cita breve.
as_of: momento de la historia pertinente.
provenance: author-edited
```

`basis` distingue `working-text` texto de trabajo, `author-decision` decisión, `planned` intención futura, `interpretation` lectura interpretativa, `unresolved` duda y `superseded` sustituida. La última enlaza la decisión que la reemplazó. `provenance` distingue `imported`, `ai-draft-unreviewed` y `author-edited`. Conserva rol de fuente `human|assistant` en importaciones: un mensaje humano puede pegar una alternativa o dar instrucciones, sin aprobar automáticamente toda la prosa que contiene.

Las entradas de conocimiento especifican quién sabe o cree qué y desde cuándo. Verdad ficticia, sospecha, engaño y conocimiento del lector son distintos. Un plan de traición no significa que sucedió; una sospecha tampoco la demuestra. Una nota puede describir un borrador de IA sin convertirlo en decisión del autor. Mantén presente, cambios aceptados aún no escritos y posibilidades juntos en la nota primaria del personaje.

## Selección, aceptación y reconciliación

Planes usan `decision_status: proposed|accepted|rejected|superseded`; alternativas, `selection_status: proposed|selected|rejected|superseded`. Aplicación y estado de tarea son distintos. Hallazgos usan `kind: contradiction|interpretation|craft` y `severity: blocker|major|minor`. La severidad explica impacto, no puntuación literaria. Preserva decisiones intencionales y descartes para evitar sugerencias repetidas.

Cada aceptación de prosa se registra bajo el encabezado exacto `Aceptado por el autor`, ligada a `target`, `sha256`, `author_statement`, `timestamp` y `reason` solo si se dio. La lista `acceptances` de cabecera conserva esos valores técnicos para validación; el cuerpo explica la misma decisión y su contexto sin mantener una segunda selección independiente. Identifica el alcance del tramo aceptado además de su versión. Selección para trabajar, satisfacción y fin de etapa permanecen distintos.

Tras edición posterior, el índice o estado muestra «versión aceptada modificada después» cuando se reconcilie. La aceptación histórica queda con el hash anterior. No apruebes el nuevo texto por herencia ni reabras todo el libro por un cambio local de palabras.

Al aceptar una revisión identificada: conserva la base, aplica la selección si corresponde al alcance y capacidad, actualiza notas sustentadas, registra la decisión, crea o actualiza tareas por consecuencias pendientes y deja la etapa igual salvo decisión expresa. Esa actualización administrativa no necesita otra aprobación, pero no autoriza reescrituras de capítulos dependientes. Si falla una nota, describe el guardado parcial. Nunca alteres resúmenes para fingir que una decisión futura ya está en prosa.

## Bitácoras y recuperación

Usa `bitacora/YYYY-MM-DD-HHMM-asunto.md`, con UUID en cabecera y sufijos `-2`, `-3` si colisiona el nombre. Fecha y hora son locales del autor y las marcas almacenadas llevan offset. Usa `local_time` de un resultado actual del helper para nombrar la bitácora; `observed_at` representa ese mismo instante en UTC. No inventes la hora ni deduzcas un guardado de la marca temporal. Una bitácora primaria comienza con trabajo significativo; una conversación de lectura puede cerrarse con relato breve sin inventar cambios.

Campos obligatorios: `id`, `type: session-log`, `schema_version: 1`, `role: primary|isolated-review`, `started`, `closed` o null, `status: open|closed|interrupted|recovered`, `previous`, `workflows`, `targets`, `stage_at_start`, `stage_at_close` o null. Usa nombres técnicos de directorio en `workflows`. Preserva los once encabezados exactos:

1. Resumen
2. Trabajo realizado
3. Cambios y motivos
4. Aceptado por el autor
5. Alternativas
6. Registros actualizados
7. Pendientes
8. Etapa y aceptación
9. Próximo paso
10. Notas del autor
11. Puntos de guardado

Deja secciones vacías cuando corresponda; no inventes decisiones para completarlas. La hora de una sesión, punto o entrada de recuperación nuevos copia el `local_time` de un resultado del helper ya observado: el de la operación que registra o, para una observación sin operación propia, el último recibido antes de componer la entrada. No la redondees ni la tomes del nombre de un archivo, de una etiqueta de operación o del guardado previsto. Fechas históricas, entradas y notas existentes, fechas de fuentes y horas rotuladas como planeadas o ficticias se conservan. Cada punto lleva hora, disparador, enlaces y hashes, resultado guardado/fallido y pendiente. Escríbelo después de observar la operación que registra, con su `operation_id`, `code` real y los `candidate_sha256` o hashes de archivo devueltos. Por eso la bitácora se guarda en una operación posterior a la de esos artefactos; no contiene su propio hash ni el resultado de la operación que la guarda, que van en la respuesta o en el punto siguiente. Si un punto quedó por confirmar y la operación ya se conoce, conserva una bitácora corregida mediante otra operación o informa esa reconciliación como pendiente. Conserva Notas del autor. Para recordar «¿por qué quitamos la traición?», busca primero `Aceptado por el autor` y los objetivos relacionados, y sigue evidencia. No cargues todas las bitácoras ni concluyas por el archivo más reciente.

Al retomar, compara artefactos por hash con el punto de control; las fechas solo orientan. Una bitácora aislada no controla estado o tablero compartidos. Una operación aplicada sin reconciliación requiere terminar registros, no repetir la escritura. La nueva bitácora de recuperación enlaza la anterior y preserva su historia. [Retomar y cerrar](../skills/handoff/SKILL.md) ejecuta este procedimiento.

## Tablero único

`trabajo-pendiente.md` conserva `kanban-plugin: board`, las columnas Por hacer, En curso, Esperando al autor, En espera de otra tarea, Para después y Terminado, y el cierre `%% kanban:settings` con JSON `{"kanban-plugin":"board","max-archive-size":-1}`. No añadas `**Completo**` a Terminado: activaría presentación de completado automático. Una casilla nunca acepta prosa.

Una tarjeta tiene texto breve, enlace al plan o hallazgo, siguiente acción e ID `^task-UUID4`. El soporte conserva `board_task_id`, `disposition: proposed|selected|declined`, `targets`, `depends_on`, razones y criterios de resolución, sin copiar el estado de columna. Otros registros pueden enlazar `[[trabajo-pendiente#^task-UUID4]]` una vez que ese ID real exista. No inventes enlaces a tarjetas ausentes.

Conserva tarjetas manuales y su redacción. Asigna un ID faltante en un punto seguro; solo resuelve objetivos con evidencia. Reconoce columnas conocidas sin distinguir mayúsculas, conserva extras como opacas, ajustes desconocidos y texto ajeno. Una estructura no reconocida produce candidato aparte, no reemplazo total.

Mover manualmente a Terminado afirma estado de tarea. Si falta evidencia necesaria, respeta el movimiento y señala revisión pendiente con razón; no lo reviertas ni aceptes una versión desconocida. Al resolverse una tarea revisa dependientes por sus criterios reales, incluida decisión creativa cuando corresponda. Por hacer indica trabajo disponible, no lo autoriza. Compara tarjetas desaparecidas con snapshots y archivo; pregunta solo si afecta trabajo activo o restauración.

La codificación del complemento español comprobada usa `**Completo**` y archivo tras `***` y `## Archivo`. La observación de la versión probada mostró que los enlaces a tarjetas archivadas abren el tablero con la tarjeta oculta; el modo Markdown sí permite localizarla. Por ese límite no archives automáticamente: conserva las tareas completadas en Terminado. Si el autor archiva manualmente, conserva el archivo en la misma nota e indícale abrir la vista Markdown para localizar la tarjeta. No anuncies navegación visual de archivo completa. Una versión futura solo podrá archivar automáticamente tras comprobar ida y vuelta y enlaces, conservando visibles las tareas recién terminadas. No borres historial ni inventes un comando automático de archivo ausente.

## Fuentes, importaciones y actualizaciones

Cada original conserva bytes inmutables por hash completo, con derivados separados que registran herramienta, opciones y unidades de cobertura. No reemplaces un derivado citado sin preservar su edición. Una fuente de investigación tiene una sola copia, aunque haya llegado por Importar; el inventario la enlaza. PDF conserva páginas; conversaciones conservan IDs, roles y secuencia.

Las notas de fuente registran título original, autoría conocida, URL solicitada/final cuando difieran, publicación/edición, consulta/captura, clase de fuente, original local si existe, `coverage: complete|partial|unavailable`, hash real o null y `reuse_status`. En notas públicas de enlace, `original` es null y el enlace externo queda en `url` y el cuerpo; un hash de captura de preparación debe explicarse como tal, sin afirmar que hay copia local en la bóveda. Completo se refiere al documento comprobado, no a un sitio entero. Faltan activos, texto, acceso o lectura: describe cuáles, sin completar desde memoria. Las notas españolas bastan para orientarse sin leer inglés y no redistribuyen traducciones íntegras.

`starter-manifest.json`, fuera de la bóveda, identifica rutas distribuidas, hashes de archivo, fuentes, capturas, procedencia y derechos. `link-only` distribuye nota propia y enlace; `bundled-with-verified-terms` exige términos comprobados de esa edición; `recipient-preserved` describe copia local, nunca permiso de publicación. Solo actualiza si se pidió: añade archivos ausentes y reemplaza únicamente los que sigan iguales al hash original distribuido. Conserva anotaciones y ofrece candidatos cuando haya diferencias, con copia anterior y recuperación verificable. La publicación requiere autorización propia.
