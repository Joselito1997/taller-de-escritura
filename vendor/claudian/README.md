# Claudian en español

Compilación local `2.2.6-es.4` de Claudian 2.2.6. Corrige textos de la interfaz mediante el sistema de traducción original. Conserva el identificador `realclaudian`, la versión `2.2.6`, los proveedores, los comandos y los permisos originales. No es una publicación oficial de Claudian.

## Instalación del complemento ya compilado

No necesitas Node ni compilar. Los archivos listos para instalar están en `plugin/`: `main.js`, `manifest.json` y `styles.css`.

1. Cierra Obsidian y conserva una copia de seguridad de la carpeta del complemento existente.
2. En una instalación nueva, crea `.obsidian/plugins/realclaudian/` dentro de la bóveda. Copia allí los tres archivos de `plugin/`. Conserva también `LICENSE` y `THIRD_PARTY_NOTICES.md` con la distribución.
3. Si Claudian ya está instalado, reemplaza solamente esos tres archivos en su carpeta existente. No copies configuraciones de otra persona ni sustituyas `data.json`.
4. Abre Obsidian, habilita Claudian en Preferencias → Complementos comunitarios y selecciona Español en Preferencias → Acerca de → Idioma y en la pestaña «General» de Claudian. Reinicia Obsidian: hasta entonces el botón de la barra lateral puede seguir diciendo «Open Claudian».
5. Comprueba el saludo, el campo de escritura, el contenido vinculado, el historial, los permisos y los ajustes. La validación real de esta compilación corresponde al entorno desechable del proyecto y sigue pendiente en este paquete.

El manifiesto original exige Obsidian 1.13.0 o posterior y uso de escritorio. La compilación se verificó en macOS arm64; esto no certifica todavía la instalación ni el funcionamiento en ningún sistema del destinatario.

“Seguro” es el nombre traducido de `Safe`, no una garantía nueva. “YOLO · sin confirmación” conserva `yolo`. Los botones de permiso devuelven exactamente las decisiones originales. La protección que limita las escrituras al ayudante del libro debe verificarse por separado.

No actualices este complemento sin comprobar antes que la nueva versión conserva la interfaz en español. Una actualización oficial puede sustituir este parche. Para volver atrás, cierra Obsidian y restaura los tres archivos guardados; conserva la configuración y los datos del usuario.

## Fuente y cambios

Fuente oficial: [YishenTu/claudian, etiqueta 2.2.6](https://github.com/YishenTu/claudian/tree/2.2.6).

- Etiqueta anotada: `4db38353c197b493913d7c8fa04361f1b07b815d`.
- Commit exacto: `8b9d499ba92b0e4d0044782ef9c14a565b034cb7`.
- Archivo original: `upstream.tar.gz`, obtenido de `https://codeload.github.com/YishenTu/claudian/tar.gz/8b9d499ba92b0e4d0044782ef9c14a565b034cb7`.
- Cambios: `spanish-ui.patch`. Las modificaciones son de presentación y traducción; no se añade otro sistema de idiomas.
- Licencia original MIT: `LICENSE`, sin cambios. Los avisos de las dependencias se conservan en `THIRD_PARTY_NOTICES.md`.
- Identidad de los archivos: `SHA256SUMS` y `provenance.json`.

Se traducen las rutas habituales de chat, selección de archivos, menús de sesiones, preguntas y permisos, edición en la nota, estados de trabajo y ajustes compartidos y de Claude. Se mantienen los identificadores de herramientas y proveedores, las rutas del usuario, el contenido del autor y los diagnósticos recibidos de servicios externos. Otros proveedores y la colaboración entre dispositivos no se declaran localizados ni validados por este parche.

Si aparece un diagnóstico externo en inglés, conserva su código y detalle. Una falta de autenticación se resuelve con la cuenta del destinatario; un límite de uso o una conexión fallida se comprueba en el proveedor. No cambies los permisos para resolver un error de conexión. La guía de preparación del libro debe completar estas instrucciones con las comprobaciones reales del entorno admitido.

## Reconstrucción para mantenimiento

Este apartado es para quien mantiene el paquete. El destinatario utiliza los archivos ya compilados.

Requisitos verificados: macOS arm64, Node `24.13.0`, npm `11.6.2`, Python 3.14.7 y `patch`. Usa herramientas ya disponibles o un entorno de compilación aislado; no hace falta instalarlas globalmente. La instalación de dependencias respeta el `package-lock.json` original, incluida la comprobación de integridad de npm.

Desde la raíz del repositorio:

```sh
python3 vendor/claudian/rebuild.py --output /tmp/claudian-es-verificado
```

El directorio de salida debe ser nuevo. El script comprueba las sumas de la fuente y del parche, extrae la fuente en un directorio temporal, aplica el parche, instala las dependencias locales, ejecuta `typecheck`, `lint`, las pruebas de localización y la compilación original. Al final compara los tres archivos con las sumas publicadas aquí. No define una bóveda de Obsidian ni instala el resultado en una aplicación.

Las pruebas completas de upstream se registran por separado en `development/evidence/claudian/report.md`. Los fallos preexistentes de caducidad y de una ruta LAN siguen abiertos; no se presentan como pruebas aprobadas ni como aceptación de M1. La suite enfocada comprueba también que los textos traducidos no alteren las decisiones de permiso. La corrección es.4 y sus 19 regresiones de valores renderizados se documentan en `development/evidence/claudian-ui-fix/report.md`. Incluyen descripciones de permiso, estados accesibles de herramientas y pestañas, títulos de modelos, vacíos de habilidades, complementos y explicación del entorno de Claude.
