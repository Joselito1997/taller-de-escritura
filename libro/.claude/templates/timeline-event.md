---
schema_version: 1
id: null
type: "timeline-event"
story_date: null
precision: null
order_before: []
order_after: []
---

# Evento de la cronología

## Evento y participantes
Describe lo ocurrido en el texto identificado o la intención futura, con esa diferencia explícita.

## Momento y orden
Usa fecha solo si se conoce; precision explica su alcance. order_before y order_after enlazan eventos sin fabricar calendario.

## Escena fuente
Ruta, identidad de escena o localizador de párrafo, encabezado, hash del tramo y breve apoyo textual.

## Consecuencias para el conocimiento
Quién aprende qué, por qué medio y desde qué punto. El lector puede saber algo antes que el grupo.

## Cambios pendientes
Orden o significado por resolver, decisiones aún no escritas y dependencias.

## Evidencia de las afirmaciones
Para cada afirmación importante usa un bloque legible con identidad claim-UUID, texto, basis, localizador de fuente, as_of cuando corresponda y provenance. El localizador identifica ruta, escena, encabezado, hash del tramo y cita breve de apoyo. Distingue texto de trabajo, decisión del autor, plan, interpretación y cuestión sin resolver. No declares canónica toda la nota. Consulta el contrato de registros al instanciar.
