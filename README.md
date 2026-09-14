# Tu taller de escritura

Un espacio en Obsidian para trabajar tu libro y conversar con Claude en español. Puedes traer capítulos, notas, versiones y conversaciones anteriores. El manuscrito, las decisiones y la investigación quedan en tu copia local.

## Cómo empezar

Ya usas Claude Code con tu cuenta. Solo necesitas instalar [Obsidian](https://obsidian.md/download) y darle a Claude Code el enlace de este repositorio:

> Clona este repositorio e instala todo el taller de escritura. Sigue sus instrucciones y déjame Obsidian abierto, con Claudian preparado para recibir los archivos de mi libro.

El agente se encarga de la instalación. No necesitas instalar Python, copiar plugins, crear columnas, elegir rutas internas ni pegar comandos en Terminal. Si tu sistema pide un permiso que solo tú puedes conceder, el agente te explicará esa acción concreta en español.

Al terminar, Obsidian debe estar abierto con el tablero y Claudian en español, en modo **Seguro**, y una respuesta que te invite a traer tu material. Todavía no se importa nada ni se inventa tu historia.

## Qué prepara el agente

Claude Code sigue [las instrucciones de instalación](CLAUDE.md) y ejecuta `instalar.sh`. El instalador:

- Conserva el repositorio descargado como fuente y prepara una copia privada independiente en una carpeta local.
- Prepara Python 3.13.5 y las dependencias fijadas en el entorno del taller, sin instalar paquetes globales ni cambiar archivos de configuración del shell.
- Prepara Pandoc 3.10.2 para exportar a Word.
- Instala los archivos incluidos de Claudian 2.2.6 es.4 y Kanban 2.0.51. No descarga otras versiones desde el catálogo ni exige compilar los plugins.
- Usa el Claude Code y la cuenta que ya tienes. El agente puede conservar el modelo de su sesión; el valor inicial comprobado del instalador es `opus`. Puedes cambiar tu elección después desde Claudian.
- Crea un destino de respaldo local separado del libro. Una segunda carpeta en el mismo equipo no sustituye un respaldo fuera del equipo.
- Registra la bóveda en Obsidian, conserva los demás registros, configura español y activa su interfaz de comandos para completar la preparación.
- Comprueba los plugins cargados, el modo de permisos, el perfil de escritura y el tablero. Después abre Claudian y le envía una petición de bienvenida identificada como preparación automática.

La preparación no copia credenciales de otra persona, no publica el libro y no hace commits ni push del manuscrito. La bóveda conserva su organización en `libro/`. Las instrucciones de escritura viven dentro de esa carpeta.

## Tu primera conversación

Trae lo que ya tengas: capítulos, notas, esquemas, borradores alternativos y conversaciones anteriores. No hace falta preparar biografías ni limpiar los archivos antes.

Puedes decir:

> Aquí está lo que tengo. Ayúdame a reconstruir el estado del libro sin reescribir todavía. Conserva las versiones y muéstrame qué entendiste.

El asistente conserva los originales, identifica versiones y propone una reconstrucción. Tú confirmas qué versión corresponde y si la reconstrucción es correcta antes de avanzar. Una versión sin cambios, una tarjeta terminada o una exportación no significan aceptación literaria.

Después puedes pedir cosas normales: «Quiero planear el próximo capítulo», «Revisa solo este diálogo y conserva el final», «Dame una crítica sin reescribir» o «Continúa donde dejamos».

[Inicio](libro/inicio.md) reúne el [estado del libro](libro/estado.md), el [tablero](libro/trabajo-pendiente.md), el [orden de capítulos](libro/manuscrito/indice.md) y la [biblioteca](libro/investigacion/indice.md).

## Alcance de esta entrega

Esta ruta se comprobó con Claude Code clonando una copia Git limpia, preparando las dependencias locales y dejando Obsidian abierto con una bienvenida real de Claudian. También se comprobó una segunda ejecución sin repetir la bienvenida ni cambiar la conversación, y la conservación de una nota y una preferencia editadas. No se pidió material del libro durante la instalación.

El perfil de escritura comprobado es macOS 26.5.1 en Apple Silicon, Obsidian 1.13.7, Python 3.13.5, Claude Code 2.1.270, Claudian 2.2.6 es.4 y Kanban 2.0.51. Pandoc 3.10.2 permite exportar DOCX. Windows, Linux, otros Mac, móvil y escritura simultánea desde varios dispositivos no están comprobados.

El autor conserva las decisiones y guarda y pausa la edición cuando autoriza aplicar un cambio. La aplicación protegida conserva hashes, versiones y detección de cambios intermedios. No bloquea toda la memoria de Obsidian. Una combinación que no cumpla las comprobaciones no obtiene permiso de escritura por declarar éxito en un instalador.

Las fuentes de investigación guardadas funcionan sin acceso a internet. Exa y Firecrawl se usan para consultas públicas cuando se autoriza esa investigación; no son un destino para subir el manuscrito. Los pasajes que compartes con Claude se procesan mediante tu propia cuenta.

## Para el agente instalador

La instrucción de clonar e instalar autoriza la preparación local. El punto de entrada es [CLAUDE.md](CLAUDE.md). `instalar.sh --consent` prepara el runtime y llama a `instalar.py`. Los parámetros de destino, modelo y perfil son para el agente; no son una lista de decisiones técnicas para el escritor.

`installation-result.json` distingue `prepared`, `starting`, `sending`, `checking`, `complete` y `failed`. Un retorno de preparación no equivale a instalación terminada. Si una bienvenida quedó enviada, conserva su conversación y no la repitas automáticamente. Al reejecutar, preserva el material, las preferencias y las conversaciones existentes.

El repositorio puede ser la fuente de desarrollo o una distribución limpia. Se copian solo los archivos de la lista de distribución y las fuentes iniciales enumeradas. Los planes privados del desarrollador, pruebas, evidencia y material de uso quedan fuera de la copia del escritor. Si hay un manifiesto de distribución, sus huellas tienen que coincidir.

La descarga automática de uv 0.11.7 y Pandoc 3.10.2 verifica sus huellas fijadas antes de usarlas. Python se obtiene mediante el mecanismo de runtimes administrados de uv. Se conservan sus ubicaciones dentro del destino local de instalación. No relajes firmas, permisos, restricciones de escritura o comprobaciones para ocultar un fallo.

Las operaciones de mantenimiento del ayudante existente siguen siendo `verify`, `backup`, `restore-backup`, `update` y `rollback` en `libro/.claude/scripts/setup.py`. Se usan con una petición explícita del autor y sus controles de conservación. La reinstalación no sustituye una actualización y no debe restablecer configuraciones editadas.

## Cuentas y datos del libro

El escritor aporta sus archivos, sus decisiones y, cuando haga falta, título y autoría. No se inventan durante la instalación. El libro es suyo; la licencia del taller no concede derechos sobre su manuscrito. Las conversaciones, claves, configuraciones de ejecución y respaldos locales no forman parte del repositorio de distribución.

## Licencias y procedencia

- La plantilla, sus instrucciones y sus notas originales usan la licencia MIT en español de [LICENCIA.md](LICENCIA.md). Esa licencia no concede derechos sobre tu manuscrito ni sobre obras de terceros.
- Claudian 2.2.6 es de Yishen Tu y usa la licencia MIT, en `vendor/claudian/LICENSE`. Sus dependencias incluidas figuran en `vendor/claudian/THIRD_PARTY_NOTICES.md`. La traducción está en `spanish-ui.patch`, y la fuente original está identificada en `provenance.json`.
- Kanban 2.0.51, de mgmeyers y la comunidad, se distribuye bajo la licencia GNU GPL versión 3 de `vendor/kanban/LICENSE.md`. Su `package.json` original declara MIT, pero el archivo de licencia de esa revisión es GPL-3.0 y es el que se cumple. La fuente original exacta está incluida en `vendor/kanban/upstream.tar.gz`, y los cambios en `es.patch` y `es.ts`. `rebuild.sh` reproduce la compilación a partir de esa fuente, y `provenance.json` registra sus hashes.
- Las notas de la biblioteca son resúmenes originales con enlaces a sus fuentes. No incluyen textos completos de terceros.
