---
name: examinar
description: Inspecciona continuidad, conocimiento, perspectiva, claridad o aspectos de oficio y devuelve hallazgos con evidencia. Úsala para comprobar, criticar o hacer una lectura en frío; no reescribe el manuscrito ni acepta capítulos en nombre del autor.
---

# Examinar sin reescribir

Lee [contrato](../../references/workflow-contract.md) y [registros](../../references/records.md). Resuelve primero si se pide inspección habitual, lectura en frío o auditoría de evidencia. No crees otro asistente permanente ni concedas a una lectura aislada control del manuscrito o tablero.

## Procedimiento

1. Identifica pasaje, versión y criterios. «Comprueba esto» incluye continuidad, conocimiento, perspectiva, ajuste al plan y claridad básica. Una crítica amplia puede incluir oficio; «solo continuidad» lo excluye. Define cobertura y lee los bytes actuales con sus hashes, no solo resúmenes.
2. Compara pasajes y registros pertinentes al alcance. Diferencia contradicción demostrable, interpretación abierta y consejo de escritura. Una nota desactualizada puede estar equivocada sin que lo esté la prosa. No conviertas falta de contexto en defecto ni una elección deliberada en error.
3. Señala fortalezas específicas que se conservarían. Para cada hallazgo importante enlaza pasaje y versión, explica evidencia y efecto, y ofrece acción concreta. Usa [el molde de hallazgo](../../templates/finding.md). No impongas cantidad de problemas ni puntuación de calidad.
4. Revisa hallazgos previos y decisiones intencionales o descartadas. Agrupa causas compartidas y evita duplicación por capítulo. Reconsidera un descarte solo con evidencia nueva explicada. Prioriza impacto y dependencias, separando lo comprobado de lo que requiere otra lectura.
5. Guarda informe vinculado bajo `planes/` por el helper. En la sesión primaria crea o actualiza tarjetas pertinentes, dejando elección del autor pendiente y sin cambiar prosa. Actualiza cobertura, estado y bitácora según el resultado real. Si el material cambió, revalida los hallazgos afectados antes de presentarlos como actuales.
6. Presenta fortalezas, hallazgos más útiles y siguiente decisión, con enlaces al detalle. Corregir requiere una petición posterior o alcance explícito ya incluido que se ejecuta mediante Revisar. Una revisión favorable no acepta texto ni etapa.

## Lectura nueva opcional

Solo cuando el autor la pide, prepara un paquete para una conversación nueva de Claudian. La lectura en frío recibe exclusivamente manuscrito solicitado y criterios, sin planes explicativos, bitácoras ni alternativas. Una auditoría de evidencia recibe además los registros aceptados y fuentes pertinentes. Ambos paquetes indican alcance, hashes, permiso de lectura del manuscrito y exclusiones. No nombres archivos adicionales como lectura opcional si deben quedar fuera del paquete frío.

El lector aislado informa contexto faltante y guarda un informe independiente con hashes revisados. El informe, también en la respuesta si no puede guardarse, nombra cada archivo con su hash; si no puede calcularlo, copia el hash del paquete y lo atribuye al host, sin presentarlo como medición propia ni pedir acceso para repetirla. No modifica manuscrito, estado actual, notas compartidas ni tablero. Si necesita bitácora, usa `role: isolated-review` sin autoridad primaria y guardado solo en su salida asignada. No inicies escritores concurrentes; con otro bloqueo vivo, permanece en lectura y entrega informe sin persistir hasta una vía permitida.

La sesión primaria comprueba cambios intermedios y reconcilia hallazgos con el tablero. Recibir un informe no prueba que la versión actual fue revisada ni autoriza aceptación. Si no puede abrirse una conversación independiente, informa la limitación y ofrece una inspección explícitamente no independiente, sin simular memoria vacía.

## Salida y fallos

Entrega alcance real, versiones, fortalezas, hallazgos clasificados, límites y decisión pendiente. Si una fuente o guardado falta, explica qué conclusión o registro queda pendiente. Comprueba prosa correcta con notas antiguas, misterio intencional, elección descartada, alcance estrecho, paquete frío frente a auditoría y cambios directos del autor. No modifiques la evidencia para que coincida con tu lectura.
