#!/usr/bin/env python3
"""Reconstruye y verifica el complemento en un directorio temporal aislado."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='Directorio nuevo para los tres archivos del complemento')
    args = parser.parse_args()
    vendor = Path(__file__).resolve().parent
    expected = dict(line.split('  ', 1)[::-1] for line in (vendor / 'SHA256SUMS').read_text().splitlines())
    for name in ('upstream.tar.gz', 'spanish-ui.patch'):
        if digest(vendor / name) != expected[name]:
            raise SystemExit(f'La suma de comprobación no coincide: {name}')
    for command, version in ((['node', '--version'], 'v24.13.0'), (['npm', '--version'], '11.6.2')):
        actual = subprocess.check_output(command, text=True).strip()
        if actual != version:
            raise SystemExit(f'Versión necesaria de {command[0]}: {version}; encontrada: {actual}')
    if args.output.exists():
        raise SystemExit('El directorio de salida ya existe. Elige uno nuevo para no sobrescribir archivos.')
    env = dict(os.environ, CI='1')
    env.pop('OBSIDIAN_VAULT', None)
    with tempfile.TemporaryDirectory(prefix='claudian-es-') as temporary:
        checkout = Path(temporary)
        with tarfile.open(vendor / 'upstream.tar.gz', 'r:gz') as archive:
            archive.extractall(checkout, filter='data')
        source = next(checkout.iterdir())
        with (vendor / 'spanish-ui.patch').open() as patch:
            subprocess.run(['patch', '-p1'], cwd=source, stdin=patch, check=True, env=env)
        for name in ('SpanishUi.test.ts', 'SpanishPresentation.test.ts'):
            shutil.copyfile(vendor.parents[1] / 'tests/claudian' / name, source / 'tests/unit' / name)
        for command in (
            ['npm', 'ci', '--no-audit', '--no-fund'],
            ['npm', 'run', 'typecheck'],
            ['npm', 'run', 'lint'],
            ['node', 'scripts/run-jest.js', '--selectProjects', 'unit', '--runInBand', '--runTestsByPath',
             'tests/unit/SpanishUi.test.ts', 'tests/unit/SpanishPresentation.test.ts',
             'tests/unit/i18n/locales.test.ts',
             'tests/unit/providers/claude/ui/ClaudeChatUIConfig.test.ts',
             'tests/unit/providers/claude/ui/ClaudeSettingsTab.test.ts'],
            ['npm', 'run', 'build'],
        ):
            print("Ejecutando: " + " ".join(command), flush=True)
            subprocess.run(command, cwd=source, check=True, env=env)
        for name in ('main.js', 'manifest.json', 'styles.css'):
            if digest(source / name) != expected['plugin/' + name]:
                raise SystemExit(f'La compilación no reproduce los bytes esperados: {name}')
        args.output.mkdir(parents=True)
        for name in ('main.js', 'manifest.json', 'styles.css'):
            shutil.copyfile(source / name, args.output / name)
    print('Compilación verificada: los tres archivos coinciden byte por byte.')


if __name__ == '__main__':
    main()
