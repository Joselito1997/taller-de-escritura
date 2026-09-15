#!/usr/bin/env python3
"""Administración explícita del espacio local; bootstrap con biblioteca estándar."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import venv
import uuid
from datetime import datetime, timezone


def emit(code, message, ok=True, **extra):
    return dict(ok=ok, code=code, message=message, artifacts=[], next_action='Revise el resultado antes de comenzar a escribir.', **extra)


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('El JSON contiene claves duplicadas; revise la elección antes de continuar.')
        result[key] = value
    return result


def selected_path(prompt):
    choice = input(prompt).strip()
    if not choice:
        raise ValueError('Seleccione una carpeta explícita; no se usa el directorio actual por defecto.')
    return str(Path(choice).expanduser().absolute())


def populated(root):
    return any(p.name != 'indice.md' for p in (root / 'manuscrito').glob('*.md')) or any((root / 'bitacora').glob('*.md')) or any((root / 'importaciones/originales').glob('*')) or any((root / '.writing').glob('*'))


def guided(root, operation):
    print('Esta preparación afecta solo a la carpeta del libro. No publica ni envía el manuscrito.')
    if input('¿Autorizas esta administración local? [s/N] ').strip().casefold() not in ('s', 'sí', 'si'):
        return {'consent': False}
    manifest = {'schema_version': 1, 'operation_id': operation + '-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:8], 'consent': True}
    if operation == 'initialize':
        print('Claude procesa el contexto que selecciones usando tu propia cuenta; no se copian credenciales de otra persona.')
        manifest['model'] = input('Modelo Claude que elegiste en tu cuenta: ').strip()
        backup_choice = input('Carpeta externa de respaldo, o SISTEMA si configurarás el respaldo del sistema operativo: ').strip()
        if backup_choice.casefold() == 'sistema':
            manifest['os_backup'] = True
        elif backup_choice:
            manifest['backup_destination'] = str(Path(backup_choice).expanduser().absolute())
        manifest['install_dependencies'] = True
        if not (root / '.writing/install.json').exists() and populated(root):
            manifest['recover_existing'] = input('Encontré material existente. ¿Conservarlo y recuperar solo la configuración? [s/N] ').strip().casefold() in ('s','sí','si')
        if (root.parent / '.git').is_dir():
            remotes = subprocess.check_output(['git','-C',str(root.parent),'remote'], text=True).split()
            if remotes:
                print('Para desconectar un clon intacto se compara su remoto con la URL oficial de la plantilla; otros remotos se conservan.')
                manifest['expected_origin'] = input('URL oficial de la plantilla indicada en sus instrucciones, o vacío para conservar el remoto: ').strip()
                manifest['disconnect_origin'] = bool(manifest['expected_origin']) and input('¿Desconectar ese remoto si coincide y el clon está intacto? [s/N] ').strip().casefold() in ('s','sí','si')
        release = root.parent / 'release-manifest.json'
        if release.is_file():
            manifest['release_manifest'] = json.loads(release.read_text())
    elif operation == 'update':
        manifest['release_root'] = selected_path('Carpeta de la versión descargada: ')
        manifest['release_manifest'] = json.loads((Path(manifest['release_root']) / 'release-manifest.json').read_text())
    elif operation == 'verify':
        file = root.parent / 'compatibility.json'
        if not file.exists():
            raise ValueError('Falta compatibility.json junto a la carpeta libro. Si es una copia restaurada, ejecute setup.py update con la carpeta de la versión descargada y repita verify; mientras tanto conserve las propuestas separadas.')
        profiles = json.loads(file.read_text(), object_pairs_hook=unique_pairs).get('cooperative_profiles', [])
        profiles = [p for p in profiles if p.get('enabled') is True and p.get('platform') == __import__('platform').system().lower()]
        if not profiles:
            raise ValueError('Esta distribución todavía no tiene perfiles aprobados; conserve las propuestas separadas.')
        for index, profile in enumerate(profiles, 1):
            print(str(index) + '. ' + profile['id'] + ' — Obsidian observado: ' + profile['versions']['obsidian'])
        chosen = input('Número del perfil a verificar [1]: ').strip() or '1'
        if not chosen.isdigit() or not 1 <= int(chosen) <= len(profiles):
            raise ValueError('Seleccione uno de los perfiles mostrados.')
        manifest['cooperative_profile'] = profiles[int(chosen)-1]['id']
    elif operation == 'rollback':
        manifest['source_operation_id'] = input('Identidad de la actualización que quieres deshacer: ').strip()
    elif operation in ('backup','restore-backup'):
        if operation == 'restore-backup':
            manifest['backup_root'] = selected_path('Carpeta del respaldo verificado: ')
        manifest['destination'] = selected_path('Carpeta externa de destino, ya existente: ')
    return manifest


def settings_for(root, python, model):
    helper = root / '.claude/scripts/book.py'
    guard = root / '.claude/scripts/permission_guard.py'
    prefix = shlex.join([str(python), str(helper), '--vault', str(root)])
    if os.name == 'nt':
        from permission_guard import powershell_prefix, POWERSHELL_UTF8
        prefix = powershell_prefix(str(python), str(helper), str(root))
        quote = lambda text: "'" + str(text).replace("'", "''") + "'"
        hook = lambda command: [{'hooks': [{'type': 'command', 'command': POWERSHELL_UTF8 + command, 'shell': 'powershell', 'timeout': 20}]}]
        return {'autoMemoryEnabled': False, 'model': model, 'env': {'CLAUDE_CODE_USE_POWERSHELL_TOOL': '1', 'PYTHONUTF8': '1'},
                'permissions': {'defaultMode': 'default', 'allow': ['Read', 'Grep', 'Glob', 'PowerShell(' + prefix + ' *)'], 'deny': ['Edit', 'Write', 'NotebookEdit', 'Bash']},
                'hooks': {'SessionStart': hook(prefix + ' hook-start'), 'Stop': hook(prefix + ' hook-stop'),
                          'PreToolUse': [{'matcher': 'Bash|PowerShell|Write|Edit|NotebookEdit', 'hooks': [{'type': 'command', 'command': POWERSHELL_UTF8 + '& ' + quote(python) + ' ' + quote(guard), 'shell': 'powershell', 'timeout': 10}]}]}}
    return {'autoMemoryEnabled': False, 'model': model, 'permissions': {'defaultMode': 'default', 'allow': ['Read', 'Grep', 'Glob', 'Bash(' + prefix + ' *)'], 'deny': ['Edit', 'Write', 'NotebookEdit', 'PowerShell']}, 'hooks': {'SessionStart': [{'hooks': [{'type': 'command', 'command': prefix + ' hook-start', 'timeout': 20}]}], 'Stop': [{'hooks': [{'type': 'command', 'command': prefix + ' hook-stop', 'timeout': 20}]}], 'PreToolUse': [{'matcher': 'Bash|PowerShell|Write|Edit|NotebookEdit', 'hooks': [{'type': 'command', 'command': shlex.join([str(python), str(guard)]), 'timeout': 10}]}]}}


def initialize(root, manifest):
    if sys.version_info < (3, 11):
        raise ValueError('Instale Python 3.11 o posterior.')
    if manifest.get('consent') is not True:
        raise ValueError('Confirme la instalación local y el uso del modelo antes de continuar.')
    if (root.parent / 'plan.md').exists() or (root.parent / 'implementation-plan.md').exists() or (root.parent / '.git').is_file():
        raise ValueError('No ejecute el inicializador del destinatario en un checkout de desarrollo.')
    for directory in (root, *root.parents):
        git_entry = directory / '.git'
        if git_entry.exists() or git_entry.is_symlink():
            if directory != root.parent or git_entry.is_symlink() or not git_entry.is_dir():
                raise ValueError('La plantilla pertenece a otro repositorio o worktree; use una copia independiente sin cambiar ese remoto.')
            break
    if not isinstance(manifest.get('model'), str) or not manifest['model'].strip():
        raise ValueError('Indique el modelo Claude elegido; no se selecciona uno por su cuenta.')
    marker = root / '.writing/install.json'
    if not marker.exists() and populated(root) and manifest.get('recover_existing') is not True:
        raise ValueError('Hay contenido sin marca de instalación; confirme recover_existing para conservarlo y recuperar la configuración.')
    if not manifest.get('os_backup') and not manifest.get('backup_destination'):
        raise ValueError('Indique el destino externo de respaldo o confirme que configurará el respaldo del sistema operativo.')
    if (root.parent / '.git').is_dir():
        command = ['git', '-C', str(root.parent)]
        remotes = subprocess.check_output(command + ['remote'], text=True).split()
        if remotes:
            if remotes != ['origin']:
                raise ValueError('Hay remotos inesperados; se conservan sin cambios.')
            origin = subprocess.check_output(command + ['remote', 'get-url', 'origin'], text=True).strip()
            if origin != manifest.get('expected_origin') or manifest.get('disconnect_origin') is not True:
                raise ValueError('El remoto no está autorizado para desconexión; se conserva.')
            if subprocess.check_output(command + ['status', '--porcelain'], text=True).strip():
                raise ValueError('El clon no está intacto; no se desconecta el remoto automáticamente.')
            subprocess.run(command + ['remote', 'remove', 'origin'], check=True, capture_output=True)
            if subprocess.check_output(command + ['remote'], text=True).strip():
                raise ValueError('No se pudo verificar la desconexión del remoto.')
    env = root.parent / '.venv'
    python = env / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.exists():
        if manifest.get('install_dependencies') is not True:
            raise ValueError('Falta el entorno del proyecto; autorice install_dependencies para crearlo.')
        venv.EnvBuilder(with_pip=True).create(env)
    lock = root.parent / 'requirements.lock'
    if manifest.get('install_dependencies') is True:
        if not lock.is_file() or any(not __import__('re').fullmatch(r'(PyYAML|pypdf)==[0-9]+\.[0-9]+\.[0-9]+', line) for line in lock.read_text().splitlines() if line.strip()):
            raise ValueError('El archivo de dependencias no contiene únicamente versiones fijadas permitidas.')
        installed = subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(lock)], capture_output=True, text=True, timeout=180)
        if installed.returncode:
            raise ValueError('No se pudieron instalar las dependencias; conserve el entorno y revise la conexión.')
    # Continuar dentro del entorno aislado; no depender del Python del sistema.
    if Path(sys.executable).absolute() != python.absolute():
        completed = subprocess.run([str(python), str(root / '.claude/scripts/setup.py'), 'initialize', '--manifest', '-'], input=json.dumps({**manifest, 'install_dependencies': False}), text=True, capture_output=True, timeout=180)
        try:
            return json.loads(completed.stdout)
        except ValueError as exc:
            raise ValueError('El entorno aislado no pudo completar la instalación.') from exc
    from book import Book, encoded, sha
    from schemas import require
    book = Book(root)
    helper = root / '.claude/scripts/book.py'
    guard = root / '.claude/scripts/permission_guard.py'
    prefix = shlex.join([str(python), str(helper), '--vault', str(root)])
    if os.name == 'nt':
        from permission_guard import powershell_prefix, POWERSHELL_UTF8
        prefix = powershell_prefix(str(python), str(helper), str(root))
    settings = settings_for(root, python, manifest['model'])
    with book.lock('setup-initialize'):
        book.ensure_directories()
        old = book.read('.claude/settings.json')
        current = json.loads(old, object_pairs_hook=unique_pairs) if old else {}
        require(isinstance(current, dict), 'La configuración existente está dañada.')
        for key, value in settings.items():
            require(key not in current or current[key] == value, f'La configuración existente de {key} no coincide con la solicitada; se conserva para revisión.')
            current.setdefault(key, value)
        versions = {name: importlib.metadata.version(name) for name in ('PyYAML',)}
        try:
            versions['pypdf'] = importlib.metadata.version('pypdf')
        except importlib.metadata.PackageNotFoundError:
            pass
        saved = {'schema_version': 1, 'private_initialized': True, 'components': versions, 'python': sys.version.split()[0], 'model': manifest['model'], 'write_mode': 'candidate-only', 'capabilities': {'static': {'schemas': True, 'root_binding': True}, 'runtime': {'hooks_observed': False, 'permissions_observed': False}, 'ui': {'cooperative_preservation': False}}, 'backup': {'destination': manifest.get('backup_destination'), 'os_backup_selected': bool(manifest.get('os_backup')), 'verified': False}, 'generated_files': {'.claude/settings.json': sha(encoded(current))}}
        baseline = {}
        package = Book(root.parent)
        release_raw = package.read('release-manifest.json')
        # Sin manifiesto en la solicitud se usa el distribuido; si no, las actualizaciones quedarían siempre como propuestas.
        release_manifest = manifest.get('release_manifest', json.loads(release_raw, object_pairs_hook=unique_pairs) if release_raw else {'schema_version': 1, 'files': []})
        require(isinstance(release_manifest, dict) and release_manifest.get('schema_version') == 1 and isinstance(release_manifest.get('files'), list), 'Manifiesto de versión inválido.')
        from maintenance import package_path
        for entry in release_manifest['files']:
            package.path(entry['path'])
            require(isinstance(entry.get('sha256'), str) and __import__('re').fullmatch(r'[0-9a-f]{64}', entry['sha256']), 'Hash de versión inválido.')
            if sha(package.read(entry['path'])) == entry.get('sha256'):
                baseline[entry['path']] = entry['sha256']
        starter = package.read('starter-manifest.json')
        if starter:
            library = json.loads(starter)
            require(library.get('schema_version') == 1 and isinstance(library.get('files'), list), 'Manifiesto de biblioteca inválido.')
            for entry in library['files']:
                package_path(entry['path'])
                if sha(package.read(entry['path'])) == entry.get('sha256'):
                    baseline[entry['path']] = entry['sha256']
        release_raw = package.read('release-manifest.json')
        if release_raw and json.loads(release_raw, object_pairs_hook=unique_pairs) == release_manifest:
            baseline['release-manifest.json'] = sha(release_raw)
        saved['template_files'] = baseline
        existing = book.read('.writing/install.json')
        if existing:
            previous = json.loads(existing, object_pairs_hook=unique_pairs)
            require(previous.get('schema_version') == 1, 'Marca de instalación no compatible.')
            previous['private_initialized'] = True
            previous['model'] = manifest['model']
            previous['components'] = versions
            previous['python'] = sys.version.split()[0]
            generated = previous.setdefault('generated_files', {})
            if generated.get('.claude/settings.json') != sha(encoded(current)):
                previous['write_mode'] = 'candidate-only'
                previous.pop('cooperative_profile', None)
                previous.pop('verified_profile', None)
            generated['.claude/settings.json'] = sha(encoded(current))
            for path, digest in baseline.items():
                # Solo completa entradas ausentes cuyo archivo sigue idéntico a la versión; nunca rebasa una edición.
                previous.setdefault('template_files', {}).setdefault(path, digest)
            saved = previous  # Rerun no borra elecciones ni evidencia previa.
        book.durable('.claude/settings.json', encoded(current))
        book.durable('.writing/install.json', encoded(saved))
        book.capture_outside(book.content_paths())
    return emit('initialized', 'Se preparó la configuración local; faltan las comprobaciones reales de interfaz y permisos.', files=['.claude/settings.json', '.writing/install.json'], helper_command=prefix, write_mode='candidate-only')


def verify(root, manifest):
    from book import Book, parse_json, encoded, now
    from schemas import require
    import runtime
    require(manifest.get('consent') is True, 'La verificación administrativa necesita una elección explícita.', 'invalid-input')
    identity = manifest.get('cooperative_profile')
    require(isinstance(identity, str) and identity, 'Indique el perfil de la distribución que desea verificar.', 'invalid-input')
    book = Book(root)
    with book.lock('setup-verify'):
        book.ensure_directories()
        status = runtime.profile_status(book, identity)
        marker = parse_json(book.read('.writing/install.json') or b'{}')
        require(marker.get('schema_version') == 1, 'Complete primero la inicialización.', 'invalid-input')
        marker['write_mode'] = 'candidate-only'
        marker.pop('cooperative_profile', None)
        marker.pop('verified_profile', None)
        if status['eligible']:
            marker['cooperative_profile'] = identity
            marker['verified_profile'] = {key:status[key] for key in ('profile_id','compatibility_sha256','release_manifest_sha256','checked_versions','ui_observed_versions','current_renderer_checked','evidence')}
            marker['verified_profile']['activated_at'] = now()
            marker['write_mode'] = 'cooperative'
        # Sin evidencia aprobada, válida y vigente la observación vuelve a falso; la configuración estática no la sustituye.
        observations = runtime.runtime_observations(status)
        marker.setdefault('capabilities', {}).setdefault('runtime', {}).update(observations)
        book.durable('.writing/install.json', encoded(marker))
    output = emit('profile-verified' if status['eligible'] else 'cooperative-unavailable', 'El perfil está verificado; cada aplicación aún necesita la declaración actual del autor.' if status['eligible'] else status['reason'], ok=status['eligible'], profile=status, runtime_observations=observations)
    output['next_action'] = 'Registre la declaración actual de guardado y pausa antes de apply; si la combinación cambia, vuelva a candidate-only.' if status['eligible'] else 'Conserve los candidatos y espere una combinación verificada; no active el perfil mediante flags.'
    return output


def main():
    class Parser(argparse.ArgumentParser):
        def error(self, message):
            raise ValueError('Orden inválida; use initialize y --manifest ARCHIVO o -.')
    try:
        parser = Parser(add_help=False, usage='python3 libro/.claude/scripts/setup.py [operación] [--manifest ARCHIVO|-]')
        if '--help' in sys.argv or '-h' in sys.argv:
            print('Preparación del libro en español. Sin argumentos inicia una guía de consentimiento, modelo y respaldo.\nOperaciones: initialize, verify, update, rollback, backup, restore-backup.\n--manifest ARCHIVO o - permite automatizar una elección explícita; no es necesario para la guía.')
            return 0
        parser.add_argument('operation', nargs='?', default='initialize', choices=('initialize', 'verify', 'update', 'backup', 'restore-backup', 'rollback'))
        parser.add_argument('--manifest')
        args = parser.parse_args()
        root = Path(__file__).resolve().parents[2]
        manifest = json.loads(sys.stdin.read() if args.manifest == '-' else Path(args.manifest).read_text(), object_pairs_hook=unique_pairs) if args.manifest else guided(root, args.operation)
        if args.operation == 'initialize':
            output = initialize(root, manifest)
        elif args.operation == 'verify':
            output = verify(root, manifest)
        else:
            import maintenance
            output = getattr(maintenance, args.operation.replace('-', '_'))(root, manifest)
    except (ValueError, OSError, subprocess.SubprocessError, ImportError, EOFError) as exc:
        message = 'El JSON de administración está incompleto o no es válido.' if isinstance(exc, (json.JSONDecodeError, UnicodeError)) else str(exc) if isinstance(exc, ValueError) else 'No se pudo completar la administración local; revise dependencias, espacio y permisos.'
        output = emit('setup-incomplete', message, ok=False)
    except Exception as exc:
        if hasattr(exc, 'code'):
            output = emit(exc.code, exc.message, ok=False)
        else:
            output = emit('invalid-input', 'El manifiesto administrativo contiene valores inválidos.', ok=False)
    print(json.dumps(output, ensure_ascii=False))
    return 0 if output['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
