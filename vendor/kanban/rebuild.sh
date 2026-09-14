#!/bin/sh
# Solo mantenimiento. El destinatario usa los archivos precompilados de plugin/.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
build_dir=${1:?Indica una ruta nueva para la compilación aislada}
test ! -e "$build_dir"
# Fuente correspondiente incluida: revisión 8501981a1afacb4c8fc03ec60604aa5eedfbd857 (etiqueta 2.0.51).
printf '%s  %s\n' dcf4fcc99f12749a0e0f596f92873a4dd206a929b18bbf30e5dd13725dbbe0ff "$root/upstream.tar.gz" | shasum -a 256 -c -
mkdir -p "$build_dir"
tar -xzf "$root/upstream.tar.gz" -C "$build_dir" --strip-components 1
cmp "$root/LICENSE.md" "$build_dir/LICENSE.md"
cd "$build_dir"
git apply "$root/es.patch"
cmp "$root/es.ts" src/lang/locale/es.ts
npx --yes yarn@1.22.22 install --frozen-lockfile --non-interactive
npm run typecheck
npm run build
for artifact in main.js styles.css manifest.json; do
  cmp "$artifact" "$root/plugin/$artifact"
done
printf '%s\n' 'Compilación verificada: los tres archivos coinciden byte por byte.'
