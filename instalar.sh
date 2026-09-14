#!/bin/bash
# El agente instalador ejecuta este archivo; el escritor no necesita Terminal.
set -euo pipefail
source_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
destination="$HOME/Taller de escritura"
consent=false
args=("$@")
while [ "$#" -gt 0 ]; do
  case "$1" in
    --dest) destination="$2"; shift 2 ;;
    --consent) consent=true; shift ;;
    *) shift ;;
  esac
done
if [ "$consent" != true ]; then
  echo 'Falta la autorización de instalación. El agente debe confirmar que el usuario pidió instalar este repositorio.' >&2
  exit 1
fi
if [ "$(uname -s)" != Darwin ] || [ "$(uname -m)" != arm64 ]; then
  echo 'Esta entrega está comprobada en macOS Apple Silicon. No se instalará una combinación no comprobada.' >&2
  exit 1
fi
if [ -L "$destination" ]; then echo 'El destino no puede ser un enlace simbólico.' >&2; exit 1; fi
if [ -d "$destination" ] && [ -n "$(ls -A "$destination")" ] && [ ! -f "$destination/.installer/owned" ]; then
  echo 'El destino ya contiene archivos ajenos a esta instalación. El agente debe elegir otra carpeta con --dest.' >&2
  exit 1
fi
mkdir -p "$destination/.installer"
touch "$destination/.installer/owned"
python_bin=''
for candidate in python3.13 python3; do
  if [ "$(command -v "$candidate" 2>/dev/null || true)" = /usr/bin/python3 ]; then continue; fi
  if command -v "$candidate" >/dev/null 2>&1 && [ "$("$candidate" -c 'import platform; print(platform.python_version())' 2>/dev/null)" = '3.13.5' ]; then
    python_bin="$(command -v "$candidate")"; break
  fi
done
if [ -z "$python_bin" ]; then
  uv_bin="$destination/.installer/uv-aarch64-apple-darwin/uv"
  if [ ! -x "$uv_bin" ]; then
    archive="$destination/.installer/uv.tar.gz"
    curl --fail --location --proto '=https' --tlsv1.2 'https://github.com/astral-sh/uv/releases/download/0.11.7/uv-aarch64-apple-darwin.tar.gz' -o "$archive"
    printf '%s  %s\n' '66e37d91f839e12481d7b932a1eccbfe732560f42c1cfb89faddfa2454534ba8' "$archive" | shasum -a 256 -c -
    tar -xzf "$archive" -C "$destination/.installer"
  fi
  export UV_PYTHON_INSTALL_DIR="$destination/.installer/python"
  export UV_CACHE_DIR="$destination/.installer/cache"
  "$uv_bin" python install --no-bin 3.13.5
  python_bin="$("$uv_bin" python find --managed-python 3.13.5)"
fi
export PYTHONDONTWRITEBYTECODE=1
exec "$python_bin" "$source_dir/instalar.py" "${args[@]}"
