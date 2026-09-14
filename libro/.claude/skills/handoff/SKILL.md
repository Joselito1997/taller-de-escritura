---
name: retomar-y-cerrar
description: Reconstruye el punto de trabajo, guarda un relevo o cierra la sesión con versiones, decisiones y próximo paso comprobados. Una petición explícita de exportación usa su rama de exportar, sin aprobar, publicar o terminar el manuscrito.
---

# Retomar, guardar y cerrar

Lee [contrato](../../references/workflow-contract.md), [registros](../../references/records.md) y [molde de bitácora](../../templates/session-log.md). Mantén puntos de control durante el trabajo; no dependas de que el autor diga adiós o de un hook final. Una conversación de lectura puede cerrar con relato breve sin inventar cambios.

## Retomar

1. Lee inicio, estado, orden, bitácora primaria activa o anterior pertinente y tarjetas relacionadas. Consulta instalación y operaciones reales. Tras reinicio o compactación conserva español, procedimiento y etapa; el hook solo facilita punteros y no sustituye estas lecturas.
2. Compara hashes de artefactos con el último punto de control. Describe diferencias de forma neutral como posibles ediciones directas o trabajo interrumpido, no como aceptación. Los tiempos orientan búsqueda, pero no deciden qué se aplicó. Journal y bitácora tienen responsabilidades distintas; comprueba archivos y reporta discrepancia.
3. Si hay operación aplicada sin reconciliar, completa solo registros pendientes según evidencia y alcance. No reapliques prosa ni la reviertas para ajustar la historia. Una base que no coincide conserva el candidato y requiere resolver conflicto. Un bloqueo vivo permite lectura sin mutar estado ni robarlo.
4. Para recuperación crea bitácora nueva vinculada a la anterior, y añade una entrada de recuperación allí sin reescribir su relato. En `candidate-only` conserva ambas como candidatos según el contrato. Conserva lo guardado con certeza. Pregunta solo elecciones ambiguas necesarias para continuar; no inventes selección para cerrar el pendiente.
5. Explica dónde quedó el trabajo y el próximo paso exacto con enlaces. «Continúa» retoma la revisión activa; no abre por sí sola el siguiente capítulo.

## Puntos de guardado

Inicia bitácora primaria al primer trabajo significativo. Tras candidato guardado, elección del autor, lote de importación, informe de investigación o cambio de dependencia, registra el punto como indica la sección Bitácoras de [registros](../../references/records.md), después de observar la operación. Usa los once encabezados españoles exactos. En `Aceptado por el autor` registra declaración, objetivo y hash de prosa, marca temporal y razón solo si se dio. Conserva Notas del autor.

## Cierre ordenado

1. Inspecciona archivos y resultados reales, incluidos candidatos no aplicados. No afirmes guardado por tener un texto preparado.
2. Reconcilia notas actuales y tareas dentro del alcance. Distingue edición local completa y consecuencias pendientes. Conserva elecciones rechazadas o aplazadas y decisiones aún no escritas.
3. Fija siguiente acción con objetivo y material concreto: unidad de importación, selección entre versiones, revisión del pasaje o registro faltante. El estado no se convierte en otra lista de tareas.
4. Verifica guardados mediante el helper. La versión probada oculta la tarjeta archivada al abrir su enlace en vista de tablero. No archives automáticamente: conserva todas las completadas visibles en Terminado. Si el autor las archiva manualmente, explica cómo localizarlas en vista Markdown y conserva IDs e historial.
5. Añade punto final y cierra la bitácora solo con el estado verdadero. Cerrar sesión no acepta prosa, termina capítulo ni avanza etapa. Una bitácora `isolated-review` no modifica estado o tablero primarios.

Si prosa se guardó pero falla la bitácora, reintenta ese registro una sola vez si la base sigue vigente. Deja el hueco en estado si puede guardarse; si tampoco puede, informa en conversación qué no persistió. Nunca declares un relevo completo con registros pendientes ocultos.

## Exportación explícita

Lee [el procedimiento de exportar](references/export.md) solo al pedir exportación. Es una rama de este procedimiento, no un noveno flujo. Comprueba operación y conversor disponibles, resuelve orden y alcance y conserva límites. Exportar no publica ni envía, no cambia aceptación y deja editable la bóveda.

## Salida

Entrega enlaces al trabajo real, decisiones vigentes, pendientes y próximo paso. La sesión nueva debe distinguir selección, aceptación histórica y texto editado después. Una bitácora válida demuestra estructura, no comprensión futura ni calidad literaria; esas pruebas se realizan por separado.
