# Instalar el taller de escritura

Este archivo guía a Claude Code cuando el usuario pide clonar e instalar el taller. Para trabajar en un libro ya instalado, usa `libro/CLAUDE.md` y sus procedimientos.

## Encargo de instalación

El usuario ya tiene Claude Code con su cuenta y Obsidian instalado. Tu trabajo termina cuando Obsidian está abierto en la bóveda correcta, el tablero funciona, Claudian está en español y en modo Seguro, y una respuesta real de Claudian invita al usuario a traer sus archivos. Un script que termina sin errores no demuestra ese resultado.

1. Lee `README.md` y ejecuta `bash instalar.sh --consent` desde este repositorio. La petición explícita de instalar autoriza esta preparación local. Usa el modelo de la sesión instaladora con `--model IDENTIFICADOR` cuando lo conozcas; en caso contrario se usa el modelo probado indicado por el instalador. El instalador informa su elección y crea un destino de respaldo local separado. No pidas al usuario comandos de Terminal, rutas internas, instalación de Python, copias de plugins ni configuración de tablero.
2. Mantén los archivos personales fuera del repositorio de distribución. El instalador prepara una copia privada independiente y preserva la estructura `libro`. No copies cuentas, tokens ni material de otras bóvedas a la distribución o al libro. La copia local de la configuración de Obsidian previa a este cambio sirve únicamente para restaurarla. No publiques ni hagas push.
3. Comprueba el resultado de `installation-result.json` en el destino que imprime el instalador. `prepared` significa que todavía falta la apertura; `starting` y `checking` son comprobaciones en curso. `sending` significa que se intentó enviar el mensaje; no demuestra aceptación ni respuesta. Solo `complete` con respuesta real, bóveda exacta, plugins cargados y modo Seguro satisface la instalación. No repitas un mensaje ya enviado ni borres el marcador para forzar otro intento.
4. Si aparece un error, resuelve la causa concreta dentro de este encargo y vuelve a comprobar. Una solicitud de permiso del sistema operativo o de Claude se explica en español; no se elude ni se finge aceptada. No conviertas un error técnico en una lista de tareas para el escritor. Si hace falta una intervención que solo él puede realizar, explica únicamente esa intervención y espera.
5. Deja Obsidian abierto con Claudian listo para recibir el material. La importación comienza cuando el usuario lo aporte. No inventes su libro ni uses material de prueba como si fuera suyo. Cierra con una frase breve que lo dirija a Claudian; no enumeres detalles técnicos ni conectores personales ajenos al taller.

La preparación es local. No instala dependencias globales ni cambia la cuenta de Claude. Las versiones no verificadas conservan sus límites; no habilites escrituras mediante flags, no relajes las guardas y no afirmes compatibilidad que no se haya comprobado.
