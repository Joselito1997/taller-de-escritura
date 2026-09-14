---
name: revisar
description: Cambia prosa existente según una petición o dirección seleccionada, preservando texto protegido y ediciones del autor. No se activa para crítica sin reescritura ni amplía una revisión local a capítulos no solicitados.
---

# Revisar prosa existente

Lee [contrato](../../references/workflow-contract.md), [registros](../../references/records.md) y la [selección de guías de Redactar](../draft/SKILL.md). Usa las mismas cinco guías de prosa, sin copias. Un pedido claro puede autorizar aplicación; pedir opciones produce candidatos separados. No exijas palabras rituales ni autorización repetida.

## Procedimiento

1. Resuelve objetivo, versión actual, cambio solicitado y material que debe quedar exacto. Lee archivos completos antes de preparar sustitución y registra hashes de base y tramos protegidos. «Solo cambia X» protege el resto, incluidas ediciones directas posteriores a tu último borrador. No dependas de tu versión recordada. Si solo cambia el diálogo, toda narración queda protegida, también la acotación del narrador dentro de una línea de réplica (« —dijo…», gestos): obtén con `inspect` sobre la preimagen un tramo propio para cada una, no solo para las líneas sin diálogo. Si una acotación se repite, amplía su tramo con bytes contiguos que tampoco cambian hasta que sea única, o detén esa aplicación.
2. Recupera encargo, plan, notas pertinentes, decisiones y dependencias del tablero. Conserva etapa activa. Si un punto pendiente cambia sentido, motivo, conocimiento o secuencia, vuelve a Planificar para esa decisión. Un cambio claro de palabras no requiere otro plan formal. Si el pedido necesita cambios colaterales de significado fuera de alcance, explica y pregunta antes de aplicar.
3. Lee las guías de prosa pertinentes según el alcance: diálogo y voz para diálogo, narración y voz para narración; añade atmósfera o ritmo cuando corresponda. Una revisión amplia puede necesitar las cinco. Lee cada una completa al primer uso y recarga tras pérdida de contexto, sin repetir una guía que sigue vigente en la conversación.
4. Prepara el cambio acotado más pequeño que resuelva la petición. Conserva perspectiva, hechos, conocimiento, puntuación y texto protegido. Una opción distinta queda separada. No mezcles candidatos por gusto ni uses un plan de revisión como permiso para encadenar capítulos no pedidos.
5. Compara con la base: comprueba el problema indicado, tramos conservados y cambios accidentales de certeza, agencia, cronología, implicación, humor o voz. Corrige errores introducidos dentro del alcance. Si el propio objetivo o texto protegido es ambiguo, detén esa aplicación y conserva trabajo independiente. Un error de historia previo no autoriza reparar otra escena.
6. Usa `snapshot` y `apply` conforme al contrato compartido, con candidatos, hashes, alcance y protecciones reales. Sin capacidad comprobada y pausa de edición, deja propuesta aparte; en `candidate-only` eso incluye `apply` con `protected_spans` y `diff`, no solo el candidato. Una base obsoleta conserva ambas versiones y detiene la sustitución; no reintentes ni sobrescribas para resolver la discrepancia.
7. Verifica artefactos y registra versión seleccionada o aceptación exacta solo cuando el autor lo haya indicado. Si la revisión aceptada cambia motivos, relación, mundo o conocimiento, actualiza las notas respaldadas, conserva historia de decisión y crea trabajo para dependientes todavía no revisados. No declares todo reconciliado después de un cambio local.
8. Cierra según el paso 7 del contrato con estos registros exigidos: estado con resultado y `next_action`; tablero con la tarjeta de la tarea trabajada, cuya columna y texto dan el motivo real del pendiente; y bitácora con su punto de guardado. Si el candidato quedó sin aplicar solo por `candidate-only` y el pedido ya lo autorizaba, dilo como límite técnico de la instalación: no lo presentes como decisión creativa pendiente ni pidas otra aprobación, y usa Esperando al autor solo si de verdad falta una decisión suya. En `candidate-only` estos registros se conservan como candidatos sin otra autorización. Si prosa ya se aplicó y una nota falló, conserva ese estado parcial, sin repetir la prosa ni ocultar el fallo. La etapa permanece igual salvo decisión correspondiente del autor.

## Salida y comprobación

Enlaza el pasaje guardado y explica brevemente cambios importantes o dudas restantes. Si solo guardaste candidato, di que falta aplicación. Si guardar falló, señala objetivo no modificado y dónde quedó la propuesta, o que solo está en conversación. No confundas aplicación verificada con satisfacción literaria.

Comprueba final protegido, edición directa intermedia, cambio únicamente de diálogo, base obsoleta, pedido de opciones y corrección con efectos posteriores. Una petición de «continúa» retoma la revisión activa. Una sesión nueva debe distinguir versión de trabajo, aceptación histórica y dependencias sin completar.
