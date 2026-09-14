# Kanban en español

Versión base: Kanban 2.0.51. Esta variante traduce su diccionario de español y conecta rótulos de accesibilidad, ajustes y recuperación de errores con su mecanismo de traducción existente. Se distribuye bajo la GNU GPL versión 3 de `LICENSE.md`, la licencia que trae esa revisión. Su `package.json` declara «MIT», pero el archivo de licencia es GPL-3.0 y es el que se conserva y cumple. `upstream.tar.gz` contiene la fuente original exacta; `es.patch`, `es.ts` y `rebuild.sh` completan la fuente correspondiente de esta compilación. Los tres archivos de `plugin/` ya están compilados; no necesitas Node ni herramientas de desarrollo.

## Instalación

1. En Obsidian, abre Preferencias → Acerca de → Idioma y selecciona Español. Reinicia cuando se indique.
2. Cierra Obsidian antes de copiar los archivos. En la bóveda del libro, crea `.obsidian/plugins/obsidian-kanban/` si no existe.
3. Copia `main.js`, `manifest.json` y `styles.css` desde `plugin/` a esa carpeta. Si sustituyes una instalación, conserva antes una copia de sus tres archivos y de `data.json`, si existe. No borres los ajustes ni los tableros.
4. Abre la bóveda y activa Kanban en Preferencias → Complementos comunitarios. Confía únicamente en el paquete cuya procedencia has verificado.
5. Crea un tablero de prueba, añade y mueve una tarjeta, edítala y archívala. Abre el archivo como Markdown y confirma que el texto sigue disponible. Reinicia y vuelve a comprobarlo.

La ficha del complemento conserva el nombre, la descripción y la versión del original. Su descripción inglesa significa «Crea tableros Kanban guardados como archivos Markdown en Obsidian». En una apertura inicial en inglés, «Trust author and enable plugins» corresponde al botón español «Confiar en el autor y activar complementos»; úsalo solo para una bóveda y un paquete conocidos.

## Actualización y conservación

Una actualización del complemento original puede sustituir esta traducción. No instales una actualización de Kanban hasta que se haya comprobado su interfaz en español y la lectura de los tableros existentes. Conserva la versión anterior para poder volver a ella. No es necesario desactivar las actualizaciones del resto de Obsidian.

Los archivos del tablero permanecen en la bóveda. El archivo de tarjetas usa el separador `***` y el encabezado `## Archivo`. El marcador `**Completo**` hace que una lista complete automáticamente sus tarjetas; el tablero del libro no debe incluirlo en «Terminado». Mantén `"max-archive-size": -1` para que Kanban no elimine tarjetas archivadas por un límite de tamaño. Los enlaces a tarjetas usan identificadores nativos `^task-...`.

El enlace a una tarjeta archivada abre el tablero, pero la tarjeta queda oculta en esa vista. Usa «Abrir como Markdown» para leer el archivo. El sistema debe mantener el archivado automático desactivado y las tareas terminadas visibles hasta que se verifique una navegación de archivo compatible.

Mantén Obsidian en español mientras uses estos tableros. El original interpreta los marcadores de archivo y finalización según el idioma activo. Cambiar de idioma requiere comprobar esos marcadores antes de editar o guardar.

## Verificación de desarrollo

`provenance.json` identifica la revisión original, los hashes SHA256, las versiones de compilación y los marcadores. `es.patch` contiene el diccionario y los cambios de rótulos en `ItemCheckbox.tsx`, `Settings.ts` y `Kanban.tsx`, sin cambios de comportamiento del tablero. `es.ts` contiene las 200 traducciones, y `LICENSE.md` conserva sin cambios la licencia GPL-3.0 original. `upstream.tar.gz` es el archivo de la revisión `8501981a1afacb4c8fc03ec60604aa5eedfbd857` publicado por GitHub, con SHA256 `dcf4fcc99f12749a0e0f596f92873a4dd206a929b18bbf30e5dd13725dbbe0ff`.

Con Git, Node 24.13.0 y npm 11.6.2, ejecuta desde este repositorio:

```sh
sh vendor/kanban/rebuild.sh /tmp/kanban-es-compilacion-nueva
python3 -m unittest discover -s tests/ui -v
```

La ruta de compilación debe ser nueva. El script comprueba el hash de `upstream.tar.gz`, extrae esa fuente incluida sin descargarla de nuevo, confirma su licencia, aplica el parche, instala las dependencias con el archivo de bloqueo original y Yarn 1.22.22, comprueba TypeScript y compila. Finalmente compara los tres archivos con el paquete incluido, byte por byte. No modifica la configuración global ni instala herramientas para el destinatario.

Los resultados de interfaz, los límites observados y las capturas se registran por separado en `development/evidence/ui/`. Las pruebas estáticas de traducción e integridad no demuestran por sí solas que la interfaz o la edición simultánea sean seguras.
