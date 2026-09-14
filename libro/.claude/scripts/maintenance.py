"""Actualización administrativa y copias verificadas a un destino elegido."""
from pathlib import Path, PurePosixPath
import json

from book import Book, encoded, parse_json, sha, result
from schemas import require, HASH

ROOT_FILES = {'README.md', 'LICENSE', 'LICENCIA.md', 'requirements.lock', 'starter-manifest.json', 'compatibility.json', 'release-manifest.json', 'release-allowlist.json'}
# Licencias, avisos, procedencia y fuentes de reconstrucción distribuidos; rutas exactas, no carpetas de vendor.
VENDOR_FILES = {'vendor/claudian/' + name for name in ('LICENSE', 'THIRD_PARTY_NOTICES.md', 'provenance.json', 'SHA256SUMS', 'README.md', 'spanish-ui.patch', 'rebuild.py')} | {'vendor/kanban/' + name for name in ('LICENSE.md', 'provenance.json', 'README.md', 'es.patch', 'es.ts', 'rebuild.sh', 'upstream.tar.gz')}


def consent(manifest):
    require(manifest.get('consent') is True, 'Esta administración requiere una elección explícita del autor.', 'invalid-input')


def package_path(path):
    require(isinstance(path, str) and path and not path.startswith('/') and all(p not in ('', '.', '..') for p in path.split('/')), 'Ruta de paquete inválida.', 'path-outside-scope')
    allowed = path in ROOT_FILES or path in VENDOR_FILES or path == 'libro/CLAUDE.md' or path == 'libro/.mcp.json' or path == 'libro/.claude/settings.template.json' or path.startswith(('libro/.claude/scripts/', 'libro/.claude/skills/', 'libro/.claude/references/', 'libro/.claude/templates/', 'libro/investigacion/fuentes/', 'libro/investigacion/temas/')) or path == 'libro/investigacion/indice.md' or path.startswith(('vendor/claudian/plugin/', 'vendor/kanban/plugin/'))
    require(allowed and not any(p in ('__pycache__', '.env', 'node_modules') for p in PurePosixPath(path).parts), 'El archivo no pertenece al ámbito de actualización del sistema.', 'path-outside-scope')
    return path


def sealed(record):
    record['record_sha256'] = sha(encoded({k:v for k,v in record.items() if k != 'record_sha256'}))
    return encoded(record)


def checked(data):
    record = parse_json(data)
    require(isinstance(record, dict) and record.get('record_sha256') == sha(encoded({k:v for k,v in record.items() if k != 'record_sha256'})), 'El registro administrativo está dañado; no se modifica nada.', 'invalid-input')
    return record


def update(root, manifest):
    consent(manifest)
    require(root.name == 'libro', 'La administración del paquete requiere su carpeta libro; no se escribe en una carpeta vecina.', 'path-outside-scope')
    book = Book(root); package = Book(root.parent)
    operation = book.manifest(manifest)
    require(isinstance(manifest.get('release_root'), str) and manifest['release_root'].strip(), 'Indique la carpeta de la versión seleccionada.', 'invalid-input')
    release = Book(manifest['release_root'])
    listing = manifest.get('release_manifest')
    require(isinstance(listing, dict) and listing.get('schema_version') == 1 and isinstance(listing.get('files'), list) and listing['files'], 'Falta el manifiesto de archivos de la versión.', 'invalid-input')
    selected, ignored = [], []
    for entry in listing['files']:
        path = entry['path']
        require(isinstance(path, str) and path and not path.startswith('/') and all(p not in ('', '.', '..') for p in path.split('/')), 'Ruta de versión inválida.', 'path-outside-scope')
        try:
            package_path(path)
            selected.append(entry)
        except Exception as exc:
            if not hasattr(exc, 'code') or exc.code != 'path-outside-scope':
                raise
            ignored.append(path)
    require(selected, 'El manifiesto no contiene archivos de sistema actualizables.', 'path-outside-scope')
    manifest_bytes = release.read('release-manifest.json')
    if manifest_bytes is not None:
        require(parse_json(manifest_bytes) == listing, 'El manifiesto de versión no coincide con el archivo descargado.', 'invalid-input')
        selected.append(dict(path='release-manifest.json', sha256=sha(manifest_bytes)))
    paths = [entry['path'] for entry in selected]
    require(len(paths) == len(set(p.casefold() for p in paths)), 'Hay rutas duplicadas en la actualización.', 'invalid-input')
    record_path = f'.writing/system-updates/{operation}/operation.json'
    with book.lock(operation):
        require(book.read(record_path) is None, 'La actualización ya tiene un intento conservado; inspecciónelo antes de otra operación.', 'invalid-input')
        install = parse_json(book.read('.writing/install.json') or b'{}')
        require(install.get('schema_version') == 1, 'Falta una marca de instalación válida; recupere setup antes de actualizar.', 'invalid-input')
        baseline = install.get('template_files', {})
        require(isinstance(baseline, dict), 'La lista original de plantilla está dañada.', 'invalid-input')
        record = dict(operation_id=operation, entries=[], previous_baseline=dict(baseline), status='prepared')
        for i, entry in enumerate(selected):
            path = entry['path']; digest = entry.get('sha256')
            require(isinstance(digest, str) and HASH.fullmatch(digest), 'Hash de versión inválido.', 'invalid-input')
            candidate = release.read(path)
            require(candidate is not None and sha(candidate) == digest, f'El archivo de versión no coincide: {path}.', 'invalid-input')
            before = package.read(path)
            history = f'.writing/system-updates/{operation}/{i}'
            book.durable(history + '.candidate', candidate, exclusive=True)
            before_saved = before is not None and path != 'libro/.mcp.json'
            if before_saved:
                book.durable(history + '.before', before, exclusive=True)
            # Las notas visibles siguen candidate-only; solo administración de sistema se aplica.
            shared_note = path.startswith('libro/investigacion/')
            apply = path != 'libro/.mcp.json' and not shared_note and (before is None or baseline.get(path) == sha(before))
            record['entries'].append(dict(path=path, before_sha256=sha(before), candidate_sha256=digest, history=history, before_saved=before_saved, apply=apply, completed=False))
        book.durable(record_path, sealed(record), exclusive=True)
        for entry in record['entries']:
            if not entry['apply']:
                continue
            require(sha(package.read(entry['path'])) == entry['before_sha256'], 'El archivo cambió durante la actualización; conserve las propuestas.', 'stale-base')
            package.durable(entry['path'], book.read(entry['history'] + '.candidate'), exclusive=entry['before_sha256'] is None)
            require(sha(package.read(entry['path'])) == entry['candidate_sha256'], 'No se pudo verificar el archivo actualizado.', 'partial-save')
            entry['completed'] = True
            baseline[entry['path']] = entry['candidate_sha256']
            book.durable(record_path, sealed(record))
        install['template_files'] = baseline
        install['write_mode'] = 'candidate-only'
        capabilities = install.setdefault('capabilities', {})
        capabilities['runtime'] = {'hooks_observed': False, 'permissions_observed': False}
        capabilities['ui'] = {'cooperative_preservation': False}
        book.durable('.writing/install.json', encoded(install))
        record['status'] = 'completed'
        book.durable(record_path, sealed(record))
    return result('system-updated', 'Se actualizaron archivos de sistema verificables; los archivos editados y notas visibles conservan propuestas separadas.', [record_path], entries=record['entries'], ignored_paths=ignored)


def rollback(root, manifest):
    consent(manifest)
    require(root.name == 'libro', 'La administración del paquete requiere su carpeta libro; no se escribe en una carpeta vecina.', 'path-outside-scope')
    book = Book(root); package = Book(root.parent)
    operation = book.manifest(manifest)
    source = manifest.get('source_operation_id')
    book.journal_path(source)
    record_path = f'.writing/system-updates/{source}/operation.json'
    with book.lock(operation):
        record = checked(book.read(record_path) or b'{}')
        require(record['status'] != 'rolled-back', 'La actualización ya fue revertida.', 'invalid-input')
        for entry in record['entries']:
            package_path(entry['path'])
            if entry['apply']:
                current = sha(package.read(entry['path']))
                require(current in (entry['candidate_sha256'], entry['before_sha256']), 'Hay cambios posteriores; no se sobrescriben durante rollback.', 'stale-base')
                entry['completed'] = current == entry['candidate_sha256']
                if entry['before_sha256'] is not None:
                    require(sha(book.read(entry['history'] + '.before')) == entry['before_sha256'], 'La versión anterior está dañada.', 'invalid-input')
        install = parse_json(book.read('.writing/install.json') or b'{}')
        baseline = install.get('template_files', {})
        for entry in reversed(record['entries']):
            if not entry['completed']:
                continue
            if entry['before_sha256'] is None:
                package.unlink(entry['path'])
            else:
                package.durable(entry['path'], book.read(entry['history'] + '.before'))
            if entry['path'] in record['previous_baseline']:
                baseline[entry['path']] = record['previous_baseline'][entry['path']]
            else:
                baseline.pop(entry['path'], None)
        install['template_files'] = baseline
        install['write_mode'] = 'candidate-only'
        capabilities = install.setdefault('capabilities', {})
        capabilities['runtime'] = {'hooks_observed': False, 'permissions_observed': False}
        capabilities['ui'] = {'cooperative_preservation': False}
        book.durable('.writing/install.json', encoded(install))
        record['status'] = 'rolled-back'
        book.durable(record_path, sealed(record))
    return result('rolled-back', 'Se restauró la versión de sistema identificada; la historia se conserva.', [record_path])


def backup_allowed(path):
    parts = PurePosixPath(path).parts
    if path.startswith(('importaciones/originales/', 'investigacion/originales/')):
        return True
    if any(p in {'.git', '.venv', 'node_modules', '__pycache__', 'cache', 'caches'} for p in parts):
        return False
    if any(p.startswith('.env') or p.lower() in {'credentials.json', '.credentials.json', 'auth.json', 'token', 'tokens.json'} for p in parts):
        return False
    # Claudian guarda variables de entorno (posibles claves de proveedor) en estos ajustes, actual y heredado.
    if path.casefold() in {'.claudian/claudian-settings.json', '.claude/claudian-settings.json'}:
        return False
    if path.startswith('.claude/settings') or path == '.mcp.json' or path.endswith('.pyc') or path in {'.writing/lock.json', '.writing/recovery.lock'}:
        return False
    if parts[0] == '.obsidian' and path not in {'.obsidian/app.json', '.obsidian/appearance.json', '.obsidian/core-plugins.json', '.obsidian/community-plugins.json', '.obsidian/bookmarks.json'}:
        return False
    return True


def backup(root, manifest):
    consent(manifest)
    book = Book(root)
    operation = book.manifest(manifest)
    require(isinstance(manifest.get('destination'), str) and manifest['destination'].strip(), 'Indique un destino explícito para la copia.', 'invalid-input')
    destination = Book(manifest['destination'])
    require(destination.root != root and root not in destination.root.parents, 'El respaldo debe estar fuera de la bóveda.', 'path-outside-scope')
    with book.lock(operation):
        require(not destination.path(operation).exists(), 'El destino de respaldo ya existe.', 'invalid-input')
        destination.new_directory(operation)
        files = []
        for source in sorted(root.rglob('*')):
            relative = source.relative_to(root).as_posix()
            if not backup_allowed(relative):
                continue
            require(not source.is_symlink(), 'El respaldo no sigue enlaces simbólicos.', 'path-outside-scope')
            if not source.is_file():
                continue
            data = book.read(relative)
            target = f'{operation}/libro/{relative}'
            destination.durable(target, data, exclusive=True)
            require(destination.read(target) == data, 'No se pudo verificar una copia del respaldo.', 'storage-failure')
            files.append(dict(path='libro/' + relative, sha256=sha(data)))
        lock = root.parent / 'requirements.lock'
        if lock.exists():
            require(not lock.is_symlink(), 'Las dependencias no pueden ser un enlace.', 'path-outside-scope')
            data = lock.read_bytes()
            destination.durable(f'{operation}/requirements.lock', data, exclusive=True)
            files.append(dict(path='requirements.lock', sha256=sha(data)))
        valid = all(sha(book.read(e['path'][6:])) == e['sha256'] for e in files if e['path'].startswith('libro/'))
        record = dict(schema_version=1, files=files, valid=valid, exclusions=['credenciales', 'settings locales', 'entornos', 'cachés', 'plugins instalados', 'bloqueos activos'])
        destination.durable(f'{operation}/manifest.json', sealed(record), exclusive=True)
        require(valid, 'La bóveda cambió durante la copia; el respaldo queda marcado inválido.', 'stale-base')
        book.durable('.writing/last-backup.json', encoded(dict(destination=str(destination.root / operation), verified=True, files=len(files))))
    return result('backed-up', 'La copia fue verificada; restaure una muestra en otra carpeta antes de confiar en su plan de respaldo.', [str(destination.root / operation)])


def restore_backup(root, manifest):
    consent(manifest)
    book = Book(root)
    operation = book.manifest(manifest)
    require(isinstance(manifest.get('backup_root'), str) and manifest['backup_root'].strip(), 'Indique la copia de respaldo seleccionada.', 'invalid-input')
    source = Book(manifest['backup_root'])
    require(isinstance(manifest.get('destination'), str) and manifest['destination'].strip(), 'Indique un destino explícito para la copia.', 'invalid-input')
    destination = Book(manifest['destination'])
    require(root != destination.root and root not in destination.root.parents, 'Restaure en una ubicación distinta de la bóveda activa.', 'path-outside-scope')
    record = checked(source.read('manifest.json') or b'{}')
    require(record.get('schema_version') == 1 and record.get('valid') is True and isinstance(record.get('files'), list), 'El respaldo no está verificado.', 'invalid-input')
    require(not destination.path(operation).exists(), 'La restauración nunca sobrescribe un destino existente.', 'invalid-input')
    require(len(record['files']) == len({e['path'].casefold() for e in record['files']}), 'El manifiesto de respaldo repite rutas.', 'invalid-input')
    for entry in record['files']:
        path = entry['path']
        require(path == 'requirements.lock' or path.startswith('libro/') and backup_allowed(path[6:]), 'El respaldo contiene una ruta no permitida.', 'path-outside-scope')
        data = source.read(path)
        require(data is not None and sha(data) == entry['sha256'], 'El respaldo cambió o está incompleto.', 'invalid-input')
    destination.new_directory(operation)
    for entry in record['files']:
        data = source.read(entry['path'])
        destination.durable(operation + '/' + entry['path'], data, exclusive=True)
        require(sha(destination.read(operation + '/' + entry['path'])) == entry['sha256'], 'La restauración no coincide con el respaldo.', 'storage-failure')
    return result('backup-restored', 'La copia se restauró en otra carpeta. Regenere la configuración local antes de escribir.', [str(destination.root / operation)])
