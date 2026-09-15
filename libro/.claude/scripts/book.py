#!/usr/bin/env python3
"""Preservación local: candidatos, instantáneas y operaciones recuperables."""
import argparse
import contextlib
import ctypes
import difflib
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import socket
import stat
import sys
import time
import uuid
from datetime import datetime, timezone

try:
    from schemas import Problem, require, validate, frontmatter, BLOCK, HASH, KNOWN_FIELDS, KANBAN_SETTINGS, TYPES
except ModuleNotFoundError:
    print(json.dumps(dict(ok=False, code='missing-dependency', message='Falta PyYAML en el entorno del proyecto.', artifacts=[], next_action='Instale requirements.lock en el entorno virtual y repita la comprobación.'), ensure_ascii=False))
    raise SystemExit(1)

ROOT_FILES = {'inicio.md', 'estado.md', 'direccion-creativa.md', 'trabajo-pendiente.md'}
CONTENT_ROOTS = {'manuscrito', 'historia', 'planes', 'alternativas', 'bitacora'}
ID = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]{0,100}$')


def sha(data):
    return hashlib.sha256(data).hexdigest() if data is not None else None


def now():
    return datetime.now(timezone.utc).isoformat()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode() + b'\n'


def object_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'El JSON contiene claves duplicadas.', 'invalid-input')
        result[key] = value
    return result


def identity_parts(data):
    """Cabecera y cuerpo sin exigir un documento completo; solo una nota sin cabecera o con id nulo carece de identidad."""
    try:
        meta, body = frontmatter(data)
    except Problem as exc:
        if exc.code != 'unsupported-format':
            raise
        meta, body = {}, data.decode('utf-8')
    require(meta.get('id') is None or isinstance(meta['id'], str) and meta['id'], 'Una identidad existente es ilegible; resuélvala antes de asignar otra.')
    return meta, body


def unregistered(meta):
    """Nota del autor aún sin registrar: sin id, sin marca de tablero y sin esquema o tipo ajenos al actual."""
    schema = meta.get('schema_version', 1)
    return meta.get('id') is None and 'kanban-plugin' not in meta and type(schema) is int and schema == 1 and (meta.get('type') is None or isinstance(meta['type'], str) and meta['type'] in TYPES)


def parse_json(data):
    try:
        return json.loads(data, object_pairs_hook=object_pairs)
    except (ValueError, UnicodeError) as exc:
        raise Problem('invalid-input', 'El registro JSON está incompleto o dañado.') from exc


def process_identity(pid):
    """Inicio real del proceso. None nunca demuestra que el dueño murió."""
    if type(pid) is not int or pid <= 0:
        return None
    if sys.platform == 'win32':
        from windows_files import identity
        return identity(pid)
    if sys.platform == 'darwin':
        class BSDInfo(ctypes.Structure):
            _fields_ = [('prefix', ctypes.c_uint32 * 12), ('comm', ctypes.c_char * 16), ('name', ctypes.c_char * 32), ('middle', ctypes.c_uint32 * 6), ('seconds', ctypes.c_uint64), ('microseconds', ctypes.c_uint64)]
        lib = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
        fn = lib.proc_pidinfo
        fn.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int]
        fn.restype = ctypes.c_int
        info = BSDInfo()
        if fn(pid, 3, 0, ctypes.byref(info), ctypes.sizeof(info)) != ctypes.sizeof(info):
            return None
        return f'darwin:{info.seconds}:{info.microseconds}'
    if sys.platform.startswith('linux'):
        try:
            fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
            boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
            return f'linux:{boot}:{fields[19]}'
        except (OSError, IndexError):
            return None
    return None


def proven_dead(owner):
    if owner['hostname'] != socket.gethostname() or process_identity(os.getpid()) is None:
        return False
    recorded = owner.get('process_start_identity')
    if not isinstance(recorded, str) or not recorded.startswith(process_identity(os.getpid()).split(':')[0] + ':') or not re.fullmatch(r'(?:darwin:[0-9]+:[0-9]+|linux:[0-9a-f-]{36}:[0-9]+|windows:[0-9]+)', recorded):
        return False
    current = process_identity(owner['pid'])
    if current is not None:
        return current != owner['process_start_identity']
    if sys.platform == 'win32':
        from windows_files import dead
        return dead(owner['pid'])
    try:
        os.kill(owner['pid'], 0)
    except ProcessLookupError:
        return True
    except (PermissionError, OSError):
        pass
    return False


def result(code, message, artifacts=None, ok=True, **extra):
    observed = extra.pop('observed_at', None) or now()
    local = datetime.fromisoformat(observed.replace('Z', '+00:00')).astimezone().isoformat()
    return dict(ok=ok, code=code, message=message, observed_at=observed, local_time=local, artifacts=artifacts or [], next_action='Abra la propuesta conservada, compare con el texto actual y prepare una nueva solicitud con su hash vigente.' if not ok and artifacts else 'Inspeccione el registro indicado; no repita la escritura hasta resolver el conflicto.' if not ok else 'Revise el resultado y continúe con el alcance acordado.', **extra)


class Book:
    def __init__(self, vault, *, cooperative_capability=None, checkpoint=None):
        raw = Path(vault).absolute()
        require(raw.is_dir() and not raw.is_symlink(), 'La bóveda no es un directorio válido.', 'path-outside-scope')
        # No resolver silenciosamente un antecesor enlazado.
        require(raw == raw.resolve(), 'La ruta de la bóveda contiene enlaces.', 'path-outside-scope')
        self.root = raw
        if os.name == 'nt':
            from windows_files import WindowsFiles
            self.windows = WindowsFiles(self)
        else:
            require(hasattr(os, 'O_NOFOLLOW') and hasattr(os, 'O_DIRECTORY'), 'Este sistema no dispone de las operaciones de archivo verificadas; conserve propuestas separadas y solicite una instalación compatible.', 'unsupported-format')
            self.root_fd = os.open(raw, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        self.capability = cooperative_capability
        self.checkpoint = checkpoint or (lambda phase, operation: None)

    def path(self, relative, *, shared=False):
        require(isinstance(relative, str) and relative and '\\' not in relative and '\x00' not in relative, 'Ruta inválida.', 'path-outside-scope')
        parts = PurePosixPath(relative).parts
        require(not relative.startswith('/') and all(p not in ('', '.', '..') for p in relative.split('/')), 'La ruta sale del alcance.', 'path-outside-scope')
        if os.name == 'nt':
            require(all(not any(c in p for c in ':<>"|?*') and not p.endswith((' ', '.')) and not re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\..*)?', p) for p in parts), 'Nombre reservado o ruta alternativa de Windows.', 'path-outside-scope')
        if shared:
            allowed = relative in ROOT_FILES or (parts[0] in CONTENT_ROOTS and len(parts) > 1)
            allowed |= parts[0] == 'importaciones' and (relative == 'importaciones/inventario.md' or len(parts) > 2 and parts[1] == 'derivados')
            allowed |= parts[0] == 'investigacion' and (relative == 'investigacion/indice.md' or len(parts) > 2 and parts[1] in {'fuentes', 'temas', 'informes', 'derivados'})
            require(allowed and relative.endswith('.md') and all(not p.startswith('.') for p in parts), 'El destino no es contenido editable permitido.', 'path-outside-scope')
        current = self.root
        for part in parts:
            current /= part
            if current.is_symlink():
                raise Problem('path-outside-scope', f'No se permiten enlaces simbólicos: {relative}.')
            if current.exists():
                require(not getattr(current.lstat(), 'st_file_attributes', 0) & 0x400, 'No se permiten puntos de reanálisis.', 'path-outside-scope')
                mode = current.stat().st_mode
                require(stat.S_ISREG(mode) or stat.S_ISDIR(mode), 'Tipo de archivo no permitido.', 'path-outside-scope')
                if stat.S_ISREG(mode):
                    require(current.stat().st_nlink == 1, 'No se permiten archivos con enlaces físicos.', 'path-outside-scope')
        return current

    def __del__(self):
        if hasattr(self, 'windows'):
            self.windows.close()
        if hasattr(self, 'root_fd'):
            os.close(self.root_fd)

    @contextlib.contextmanager
    def parent_fd(self, relative, create=False):
        self.path(relative)
        parts = PurePosixPath(relative).parts
        fd = os.dup(self.root_fd)
        try:
            for part in parts[:-1]:
                if create:
                    try:
                        os.mkdir(part, dir_fd=fd)
                        os.fsync(fd)
                    except FileExistsError:
                        pass
                try:
                    child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                except OSError as exc:
                    if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                        raise Problem('path-outside-scope', 'Un directorio cambió o se convirtió en enlace; no se sigue ese destino.') from exc
                    raise
                os.close(fd)
                fd = child
            yield fd, parts[-1]
        finally:
            os.close(fd)

    def read(self, relative, shared=False, max_bytes=None):
        if hasattr(self, 'windows'):
            return self.windows.read(relative, shared, max_bytes)
        self.path(relative, shared=shared)
        try:
            with self.parent_fd(relative) as (parent, name):
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
                with os.fdopen(fd, 'rb') as stream:
                    info = os.fstat(stream.fileno())
                    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'Se requiere un archivo ordinario sin enlaces.', 'path-outside-scope')
                    data = stream.read() if max_bytes is None else stream.read(max_bytes + 1)
                    require(max_bytes is None or len(data) <= max_bytes, 'El archivo supera el límite autorizado de lectura.', 'invalid-input')
                    return data
        except FileNotFoundError:
            return None

    def unlink(self, relative):
        if hasattr(self, 'windows'):
            return self.windows.unlink(relative)
        with self.parent_fd(relative) as (parent, name):
            os.unlink(name, dir_fd=parent)
            os.fsync(parent)

    def new_directory(self, relative):
        if hasattr(self, 'windows'):
            return self.windows.new_directory(relative)
        with self.parent_fd(relative, create=True) as (parent, name):
            try:
                os.mkdir(name, dir_fd=parent)
            except FileExistsError as exc:
                raise Problem('invalid-input', 'El directorio de destino ya existe; no se reutiliza.') from exc
            os.fsync(parent)

    def ensure_directories(self):
        from schemas import VAULT_DIRECTORIES
        for relative in VAULT_DIRECTORIES:
            path = self.path(relative)
            if not path.exists():
                self.new_directory(relative)
            require(path.is_dir(), 'Una ruta prevista como carpeta contiene un archivo: ' + relative, 'path-outside-scope')
        return list(VAULT_DIRECTORIES)

    def durable(self, relative, data, *, exclusive=False):
        if hasattr(self, 'windows'):
            return self.windows.write(relative, data, exclusive=exclusive)
        with self.parent_fd(relative, create=True) as (parent, name):
            temporary = name if exclusive else '.book-' + str(uuid.uuid4())
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                if not exclusive:
                    os.replace(temporary, name, src_dir_fd=parent, dst_dir_fd=parent)
                os.fsync(parent)
            finally:
                if not exclusive:
                    try:
                        os.unlink(temporary, dir_fd=parent)
                    except FileNotFoundError:
                        pass

    @contextlib.contextmanager
    def lock(self, operation, recover=False):
        lock_path = '.writing/lock.json'
        identity = process_identity(os.getpid())
        require(identity is not None, 'No se puede verificar la identidad del proceso; mantenga los candidatos separados.', 'lock-busy')
        owner = dict(hostname=socket.gethostname(), pid=os.getpid(), process_start_identity=identity, operation_id=operation, acquired_at=now())
        existing = self.read(lock_path)
        if existing is not None:
            old = parse_json(existing)
            require(isinstance(old, dict) and {'hostname', 'pid', 'process_start_identity', 'operation_id', 'acquired_at'} <= old.keys() and type(old['pid']) is int and old['pid'] > 0 and isinstance(old['process_start_identity'], str) and old['process_start_identity'], 'El bloqueo está dañado; requiere inspección.', 'lock-busy')
            from schemas import timestamp
            require(isinstance(old['hostname'], str) and isinstance(old['operation_id'], str) and ID.fullmatch(old['operation_id']) and timestamp(old['acquired_at']), 'El bloqueo contiene campos inválidos; requiere inspección.', 'lock-busy')
            require(recover and proven_dead(old), 'Otro escritor conserva el bloqueo o su identidad no se puede comprobar.', 'lock-busy')
            # Serializa también a los recuperadores; nunca dos desalojos simultáneos.
            with self.recovery_guard():
                require(self.read(lock_path) == existing, 'El bloqueo cambió durante la recuperación.', 'lock-busy')
                self.unlink(lock_path)
                self.durable(lock_path, encoded(owner), exclusive=True)
        else:
            try:
                self.durable(lock_path, encoded(owner), exclusive=True)
            except FileExistsError as exc:
                raise Problem('lock-busy', 'Otro escritor adquirió el bloqueo.') from exc
        try:
            self.audit_internal()
            yield
        finally:
            if self.read(lock_path) == encoded(owner):
                self.unlink(lock_path)

    @contextlib.contextmanager
    def recovery_guard(self):
        name = '.writing/recovery.lock'
        try:
            self.durable(name, encoded({'pid': os.getpid()}), exclusive=True)
        except FileExistsError as exc:
            raise Problem('lock-busy', 'Hay una recuperación pendiente; inspeccione su bloqueo.') from exc
        try:
            yield
        finally:
            self.unlink(name)

    def manifest(self, manifest):
        require(isinstance(manifest, dict) and type(manifest.get('schema_version')) is int and manifest['schema_version'] == 1, 'Manifiesto de versión no compatible.', 'invalid-input')
        operation = manifest.get('operation_id')
        require(isinstance(operation, str) and ID.fullmatch(operation), 'Identidad de operación inválida.', 'invalid-input')
        return operation

    def validate_apply(self, manifest):
        operation = self.manifest(manifest)
        require(isinstance(manifest.get('kind'), str) and manifest['kind'], 'Falta el tipo de operación.', 'invalid-input')
        scope = manifest.get('authorized_scope')
        require(isinstance(scope, dict) and isinstance(scope.get('request'), str) and scope['request'].strip() and isinstance(scope.get('targets'), list), 'Falta el alcance autorizado.', 'invalid-input')
        writes = manifest.get('writes')
        require(isinstance(writes, list) and writes, 'No hay archivos propuestos.', 'invalid-input')
        targets = []
        for write in writes:
            require(isinstance(write, dict) and {'target', 'expected_file_sha256', 'candidate_path', 'candidate_sha256', 'format'} <= write.keys(), 'Propuesta incompleta.', 'invalid-input')
            self.path(write['target'], shared=True)
            require(write['target'] in scope['targets'], 'El destino no está autorizado.', 'path-outside-scope')
            require(write['expected_file_sha256'] is None or isinstance(write['expected_file_sha256'], str) and HASH.fullmatch(write['expected_file_sha256']), 'Hash base inválido.', 'invalid-input')
            require(isinstance(write['candidate_sha256'], str) and HASH.fullmatch(write['candidate_sha256']), 'Hash candidato inválido.', 'invalid-input')
            require(isinstance(write['candidate_path'], str) and write['candidate_path'].startswith('.writing/candidates/'), 'El candidato debe estar en el área de propuestas.', 'path-outside-scope')
            self.path(write['candidate_path'])
            require(write['format'] in {'chapter', 'index', 'record', 'session-log', 'kanban'}, 'Formato no compatible.', 'unsupported-format')
            require(isinstance(write.get('protected_spans', []), list), 'Intervalos protegidos inválidos.', 'invalid-input')
            targets.append(write['target'])
        require(len(set(t.casefold() for t in targets)) == len(targets), 'Destinos duplicados.', 'invalid-input')
        require(all(isinstance(t, str) for t in scope['targets']) and set(targets) == set(scope['targets']), 'El alcance no coincide con los destinos.', 'invalid-input')
        return operation

    def journal_path(self, operation):
        require(isinstance(operation, str) and ID.fullmatch(operation), 'Identidad de operación inválida.', 'invalid-input')
        return f'.writing/operations/{operation}.json'

    def load_journal(self, operation):
        raw = self.read(self.journal_path(operation))
        require(raw is not None, 'No existe esa operación.', 'source-unavailable')
        journal = parse_json(raw)
        require(isinstance(journal, dict) and {'manifest', 'manifest_sha256', 'phase', 'last_verified_phase', 'completed_targets', 'entries'} <= journal.keys(), 'Registro de operación dañado.', 'invalid-input')
        require(journal.get('journal_sha256') == sha(encoded({k: v for k, v in journal.items() if k != 'journal_sha256'})), 'La integridad del diario no coincide.', 'invalid-input')
        self.validate_apply(journal['manifest'])
        require(journal['manifest']['operation_id'] == operation and sha(encoded(journal['manifest'])) == journal['manifest_sha256'], 'El manifiesto histórico cambió.', 'invalid-input')
        require(journal['phase'] in {'prepared', 'applied', 'reconciled', 'failed'} and journal['last_verified_phase'] in {'prepared', 'applied', 'reconciled'}, 'Fase de diario inválida.', 'invalid-input')
        require(isinstance(journal['entries'], list) and len(journal['entries']) == len(journal['manifest']['writes']), 'Faltan imágenes históricas.', 'invalid-input')
        targets = [w['target'] for w in journal['manifest']['writes']]
        require(isinstance(journal['completed_targets'], list) and len(set(journal['completed_targets'])) == len(journal['completed_targets']) and set(journal['completed_targets']) <= set(targets), 'Lista de archivos completados inválida.', 'invalid-input')
        require(journal['phase'] != 'reconciled' or journal['last_verified_phase'] == 'reconciled' and set(journal['completed_targets']) == set(targets), 'El diario declara conciliación incompleta.', 'invalid-input')
        for i, (entry, write) in enumerate(zip(journal['entries'], journal['manifest']['writes'])):
            expected = f'.writing/history/{operation}/{i}'
            require(isinstance(entry, dict) and entry.get('target') == write['target'] and entry.get('candidate') == expected + '.candidate' and entry.get('before') == (expected + '.before' if write['expected_file_sha256'] is not None else None), 'Ruta histórica inválida.', 'invalid-input')
            before = self.read(entry['before']) if entry['before'] else None
            candidate = self.read(entry['candidate'])
            require(sha(before) == write['expected_file_sha256'] and candidate is not None and sha(candidate) == write['candidate_sha256'], 'La historia está incompleta o cambió.', 'invalid-input')
            validate(candidate, write['format'])
        return journal

    def audit_internal(self):
        base = self.path('.writing')
        if not base.exists():
            return
        for path in base.rglob('*'):
            self.path(path.relative_to(self.root).as_posix())
        operations = self.path('.writing/operations')
        if operations.exists():
            for path in operations.iterdir():
                require(path.suffix == '.json' and path.is_file(), 'Archivo de diario inesperado.', 'invalid-input')
                self.load_journal(path.stem)
        history = self.path('.writing/history')
        if history.exists():
            for directory in history.iterdir():
                require(directory.is_dir() and self.read(self.journal_path(directory.name)) is not None, 'Hay historia parcial sin diario; inspecciónela sin sobrescribirla.', 'invalid-input')
                journal = self.load_journal(directory.name)
                require(self.read(f'.writing/history/{directory.name}/manifest.json') == encoded(journal['manifest']), 'El manifiesto inmutable cambió.', 'invalid-input')
        outside = self.path('.writing/outside')
        if outside.exists():
            for path in outside.iterdir():
                record = parse_json(self.read(path.relative_to(self.root).as_posix()))
                require(isinstance(record, dict) and record.get('kind') == 'outside-edit' and {'target', 'before_sha256', 'current_sha256', 'observed_at'} <= record.keys(), 'Registro externo dañado.', 'invalid-input')
                self.path(record['target'], shared=True)
                for key in ('before_sha256', 'current_sha256'):
                    digest = record[key]
                    require(digest is None or isinstance(digest, str) and HASH.fullmatch(digest) and sha(self.read(f'.writing/objects/{digest}')) == digest, 'Versión externa dañada.', 'invalid-input')
        cache = self.read('.writing/known.json')
        if cache is not None:
            known = parse_json(cache)
            require(isinstance(known, dict), 'Registro de versiones inválido.', 'invalid-input')
            for target, digest in known.items():
                self.path(target, shared=True)
                require(isinstance(digest, str) and HASH.fullmatch(digest) and sha(self.read(f'.writing/objects/{digest}')) == digest, 'Instantánea conocida dañada.', 'invalid-input')

        import runtime
        runtime.audit_extensions(self)

    def content_paths(self):
        paths = []
        for path in self.root.rglob('*'):
            if path.is_symlink() and not path.relative_to(self.root).parts[0].startswith('.'):
                raise Problem('path-outside-scope', 'La bóveda contiene un enlace simbólico en contenido.')
            if path.suffix != '.md':
                continue
            rel = path.relative_to(self.root).as_posix()
            if rel.split('/')[0].startswith('.'):
                continue
            try:
                self.path(rel, shared=True)
            except Problem:
                if path.is_symlink():
                    raise
                continue
            paths.append(rel)
        return sorted(paths)

    def capture_outside(self, targets):
        known = parse_json(self.read('.writing/known.json') or b'{}')
        artifacts = []
        for target in targets:
            data = self.read(target, shared=True)
            digest = sha(data)
            previous = known.get(target)
            if digest == previous:
                continue
            if data is not None:
                blob = f'.writing/objects/{digest}'
                if self.read(blob) is None:
                    self.durable(blob, data, exclusive=True)
                require(sha(self.read(blob)) == digest, 'Instantánea dañada.', 'storage-failure')
            record = f'.writing/outside/{uuid.uuid4()}.json'
            self.durable(record, encoded(dict(kind='outside-edit', target=target, before_sha256=previous, current_sha256=digest, observed_at=now())), exclusive=True)
            artifacts.append(record)
            if digest is None:
                known.pop(target, None)
            else:
                known[target] = digest
        self.durable('.writing/known.json', encoded(known))
        return artifacts

    def remember(self, target, data):
        digest = sha(data)
        blob = f'.writing/objects/{digest}'
        if self.read(blob) is None:
            self.durable(blob, data, exclusive=True)
        known = parse_json(self.read('.writing/known.json') or b'{}')
        known[target] = digest
        self.durable('.writing/known.json', encoded(known))

    def read_reference(self, relative):
        require(isinstance(relative, str), 'Referencia inválida.', 'path-outside-scope')
        if relative.startswith(('importaciones/originales/', 'investigacion/originales/')):
            data = self.read(relative)
            if data is not None or PurePosixPath(relative).suffix:
                return data
            return self.read(relative + '.md')
        if not PurePosixPath(relative).suffix:
            relative += '.md'
        if relative.startswith('guia-del-taller/') and relative.endswith('.md'):
            return self.read(relative)
        return self.read(relative, shared=True)

    def inspect(self, manifest):
        target = manifest.get('target')
        self.path(target, shared=True)
        spans = manifest.get('spans', [])
        include_text = manifest.get('include_text', False)
        require(isinstance(spans, list) and len(spans) <= 100 and type(include_text) is bool, 'Solicite hasta 100 intervalos y use include_text como booleano.', 'invalid-input')
        if 'expected_file_sha256' in manifest:
            expected = manifest['expected_file_sha256']
            require(isinstance(expected, str) and HASH.fullmatch(expected), 'Hash base inválido.', 'invalid-input')
        data = self.read(target, shared=True)
        observed_at = now()
        require(data is not None, 'El archivo solicitado no está disponible.', 'source-unavailable')
        digest = sha(data)
        require('expected_file_sha256' not in manifest or expected == digest, 'El texto cambió desde la lectura; vuelva a partir de una instantánea vigente.', 'stale-base')
        try:
            text = data.decode('utf-8')
            resolved = []
            for span in spans:
                require(isinstance(span, dict) and (set(span) == {'quote'} or set(span) == {'start', 'end'}), 'Indique una cita exacta o un intervalo de bytes.', 'invalid-input')
                if 'quote' in span:
                    require(isinstance(span['quote'], str) and span['quote'], 'La cita debe ser texto no vacío.', 'invalid-input')
                    quote = span['quote'].encode('utf-8')
                    start = data.find(quote)
                    require(start >= 0 and data.find(quote, start + 1) < 0, 'La cita falta o aparece más de una vez; indique límites exactos.', 'invalid-input')
                    end = start + len(quote)
                else:
                    start, end = span['start'], span['end']
                    require(type(start) is int and type(end) is int and 0 <= start < end <= len(data), 'Límites de intervalo inválidos.', 'invalid-input')
                selected = data[start:end]
                quote = selected.decode('utf-8')
                item = dict(start=start, end=end, sha256=sha(selected))
                if include_text:
                    item['quote'] = quote
                resolved.append(item)
        except UnicodeError as exc:
            raise Problem('invalid-input', 'El archivo, la cita o los límites no representan texto UTF-8 válido.') from exc
        output = result('inspected', 'Lectura exacta terminada sin escrituras.', target=target, file_sha256=digest, observed_at=observed_at, byte_count=len(data), spans=resolved)
        if include_text and not spans:
            output['text'] = text
        require(len(encoded(output)) <= 64 * 1024, 'El resultado excede 64 KiB; solicite menos texto o lea la preimagen inmutable y conserve el mismo hash base.', 'invalid-input')
        return output

    def check(self, manifest=None):
        self.audit_internal()
        if manifest and manifest.get('action') == 'inspect':
            return self.inspect(manifest)
        if manifest and manifest.get('action') in ('layout', 'import-coverage'):
            import runtime
            return runtime.layout(self) if manifest['action'] == 'layout' else runtime.import_coverage(self)
        if manifest and manifest.get('action') in ('search', 'board', 'readiness'):
            import runtime
            return runtime.search(self, manifest) if manifest['action'] == 'search' else runtime.readiness(self) if manifest['action'] == 'readiness' else runtime.board(self)
        targets = manifest.get('targets', self.content_paths()) if manifest else self.content_paths()
        require(isinstance(targets, list), 'Alcance de comprobación inválido.', 'invalid-input')
        identities, blocks, documents = {}, {}, {}
        for target in targets:
            data = self.read(target, shared=True)
            require(data is not None, f'Falta el archivo {target}.', 'source-unavailable')
            doc = validate(data)
            identity = doc['metadata'].get('id')
            require(identity is None or identity not in identities, f'Identidad duplicada: {identity}.')
            identities[identity] = target
            for block in doc['ids']:
                require(block not in blocks, f'Bloque duplicado: {block}.')
                blocks[block] = target
            if doc['format'] == 'chapter':
                from schemas import scene_locators
                scene_locators(data, target)
            documents[target] = doc
        for target, doc in documents.items():
            if doc['metadata'].get('sha256') and doc['metadata'].get('original'):
                original = doc['metadata']['original']
                reference = original[2:-2].split('|')[0] if original.startswith('[[') and original.endswith(']]') else original
                source = self.read_reference(reference)
                require(source is not None, f'Original no disponible: {reference}.', 'source-unavailable')
                require(sha(source) == doc['metadata']['sha256'], f'El original cambió: {reference}.', 'stale-base')
            for link in re.findall(r'\[\[([^\]|]+)(?:\|[^\]]*)?\]\]', self.read(target).decode()):
                dest, _, anchor = link.partition('#')
                dest = dest or target
                data = self.read_reference(dest)
                require(data is not None, f'Enlace ausente en {target}: {dest}.', 'source-unavailable')
                if anchor.startswith('^'):
                    require(anchor[1:] in validate(data)['ids'], f'Ancla ausente: {link}.', 'source-unavailable')
                elif anchor:
                    require(anchor in [re.sub(r'^#+ ', '', line).strip() for line in data.decode().splitlines() if line.startswith('#')], f'Encabezado ausente: {link}.', 'source-unavailable')
        if manifest:
            from schemas import validate_locator
            for locator in manifest.get('locators', []):
                validate_locator(locator)
                data = self.read(locator['path'], shared=True)
                require(data is not None, 'La fuente del localizador no está disponible.', 'source-unavailable')
                require(locator['end'] <= len(data), 'El intervalo citado cambió desde la lectura.', 'stale-base')
                span = data[locator['start']:locator['end']]
                require(sha(span) == locator['sha256'] and locator['quote'].encode() in span, 'La fuente citada cambió; conserve la cita histórica y vuelva a localizar el pasaje.', 'stale-base')
                if locator.get('scene_id'):
                    require(locator['scene_id'] in validate(data)['ids'], 'El ancla citada ya no está presente.', 'source-unavailable')
        known = parse_json(self.read('.writing/known.json') or b'{}')
        changed = [dict(target=t, before_sha256=known.get(t), current_sha256=sha(self.read(t, shared=True))) for t in sorted(set(targets) | set(known)) if sha(self.read(t, shared=True)) != known.get(t)]
        return result('checked', 'Comprobación terminada.', targets, documents=len(documents), changed_files=changed)

    def snapshot(self, manifest):
        operation = self.manifest(manifest)
        targets = manifest.get('targets', [])
        candidates = manifest.get('candidates', [])
        base_hashes = {}
        if manifest.get('action') == 'normalize-board':
            import runtime
            with self.lock(operation):
                base_hashes['trabajo-pendiente.md'] = sha(self.read('trabajo-pendiente.md', shared=True))
                text = runtime.board(self, normalize=True)
            candidates = [dict(format='kanban', text=text)]
            targets = ['trabajo-pendiente.md']
        require(isinstance(targets, list) and all(isinstance(t, str) for t in targets) and len(targets) == len(set(targets)), 'Destinos de instantánea inválidos.', 'invalid-input')
        require(isinstance(candidates, list) and (targets or candidates), 'Falta el contenido de la instantánea.', 'invalid-input')
        with self.lock(operation):
            artifacts = self.capture_outside(targets)
            # La captura fija la base; una edición externa posterior no la sustituye.
            known = parse_json(self.read('.writing/known.json'))
            bases = []
            for target in targets:
                digest = known.get(target)
                preimage = f'.writing/objects/{digest}' if digest is not None else None
                require(preimage is None or sha(self.read(preimage)) == digest, 'Instantánea dañada.', 'storage-failure')
                bases.append(dict(target=target, file_sha256=digest, preimage_path=preimage))
            staged = []
            for i, candidate in enumerate(candidates):
                require(isinstance(candidate, dict) and isinstance(candidate.get('text'), str) and candidate.get('format') in {'chapter', 'index', 'record', 'session-log', 'kanban'}, 'Candidato de texto inválido.', 'invalid-input')
                text = candidate['text']
                require(len(text.encode()) <= 10 * 1024 * 1024, 'El candidato excede el límite de 10 MB.', 'invalid-input')
                path = f'.writing/candidates/{operation}-{i}.md'
                existing = self.read(path)
                # El molde puede pedir una identidad; solo sustituimos su línea id: null.
                if candidate.get('allocate_id') is True:
                    used = set()
                    # Reserva toda identidad reconocible aunque el resto del documento no valide.
                    for target in self.content_paths():
                        used.add(identity_parts(self.read(target))[0].get('id'))
                    for item in self.path('.writing/candidates').glob('*.md'):
                        used.add(identity_parts(self.read(item.relative_to(self.root).as_posix()))[0].get('id'))
                    identity = str(uuid.uuid4())
                    if candidate['format'] == 'chapter':
                        number = 1
                        while f'ch-{number:03d}' in used:
                            number += 1
                        identity = f'ch-{number:03d}'
                    if existing is not None:
                        identity = validate(existing, candidate['format'])['metadata']['id']
                    text, count = re.subn(r'(?m)^id: null[ \t]*$', 'id: ' + identity, text, count=1)
                    require(count == 1, 'El molde debe contener id: null.', 'invalid-input')
                data = text.encode()
                validate(data, candidate['format'])
                require(existing is None or existing == data, 'Ya existe otra propuesta con esta identidad.', 'invalid-input')
                if existing is None:
                    self.durable(path, data, exclusive=True)
                staged.append(dict(candidate_path=path, candidate_sha256=sha(data), format=candidate['format']))
                artifacts.append(path)
        return result('snapshotted', 'Se conservaron las versiones observadas y las propuestas indicadas.', artifacts, candidates=staged, bases=bases, base_hashes=base_hashes)

    def protected(self, write, before, candidate):
        for span in write.get('protected_spans', []):
            require(isinstance(span, dict) and {'start', 'end', 'sha256'} <= span.keys(), 'Intervalo protegido incompleto.', 'invalid-input')
            start, end = span['start'], span['end']
            require(type(start) is int and type(end) is int and before is not None and 0 <= start < end <= len(before), 'Límites de intervalo inválidos.', 'invalid-input')
            require(sha(before[start:end]) == span['sha256'], 'El texto protegido cambió desde la lectura.', 'protected-span-mismatch')
            # Permite desplazamientos, pero exige una única copia exacta, no una semejanza.
            require(before.count(before[start:end]) == 1 and candidate.count(before[start:end]) == 1, 'No se conserva inequívocamente el texto protegido.', 'protected-span-mismatch')

    def prepare(self, manifest):
        operation = self.validate_apply(manifest)
        history = f'.writing/history/{operation}'
        require(not self.path(history).exists(), 'Hay historia sin diario; inspecciónela antes de continuar.', 'invalid-input')
        entries, candidates = [], {}
        for i, write in enumerate(manifest['writes']):
            before = self.read(write['target'], shared=True)
            candidate = self.read(write['candidate_path'])
            require(candidate is not None and sha(candidate) == write['candidate_sha256'], 'El candidato cambió o falta.', 'stale-base')
            validate(candidate, write['format'])
            if before is not None:
                meta, body = identity_parts(before)
                # Una nota del autor aún sin identidad se registra; conserva sus campos y anclas.
                unassigned = unregistered(meta)
                previous = dict(metadata=meta, body=body, ids=BLOCK.findall(body)) if unassigned else validate(before, write['format'])
                updated = validate(candidate, write['format'])
                require(unassigned or previous['metadata'].get('id') == updated['metadata'].get('id'), 'La identidad del documento no puede cambiar.')
            require(sha(before) == write['expected_file_sha256'], 'El texto cambió desde que preparé esta versión. Guardé la propuesta por separado.', 'stale-base')
            if before is not None:
                for key in previous['metadata'].keys() - KNOWN_FIELDS:
                    require(key in updated['metadata'] and previous['metadata'][key] == updated['metadata'][key], f'La propuesta elimina o altera el campo personal {key}.')
                if write['format'] == 'kanban':
                    old_sections = re.split(r'(?m)^(## .*)$', previous['body'])
                    new_sections = re.split(r'(?m)^(## .*)$', updated['body'])
                    old_map = dict(zip(old_sections[1::2], old_sections[2::2]))
                    new_map = dict(zip(new_sections[1::2], new_sections[2::2]))
                    from schemas import BOARD_STATES
                    for heading, section in old_map.items():
                        if heading[3:].casefold() not in {label.casefold() for label in BOARD_STATES}:
                            require(heading in new_map and section == new_map[heading], f'La columna o archivo {heading} debe conservarse sin cambios.')
                    old_settings = parse_json(KANBAN_SETTINGS.search(previous['body'])[1])
                    new_settings = parse_json(KANBAN_SETTINGS.search(updated['body'])[1])
                    require(all(new_settings.get(k) == v for k, v in old_settings.items()), 'La propuesta altera ajustes existentes del tablero.')
                require(set(previous['ids']) <= set(updated['ids']), 'La propuesta elimina o mueve un ancla; resuelva su correspondencia antes de guardar.')
            self.protected(write, before, candidate)
            entries.append(dict(target=write['target'], before=f'{history}/{i}.before' if before is not None else None, candidate=f'{history}/{i}.candidate'))
            candidates[write['target']] = candidate
        if 'estado.md' in candidates:
            self.require_import_completion(candidates['estado.md'])
        # Identidades globales incluyendo creaciones dentro de la misma operación.
        ids = set()
        for target in sorted(set(self.content_paths()) | set(candidates)):
            data = candidates.get(target) if target in candidates else self.read(target)
            meta, body = identity_parts(data)
            if not unregistered(meta):
                validate(data)
            for identity in [meta.get('id'), *BLOCK.findall(body)]:
                if identity is not None:
                    require(identity not in ids, f'Identidad duplicada: {identity}.')
                    ids.add(identity)
        # Comprobar bases antes de comprometer el diario, conservando candidatos en staging.
        for write in manifest['writes']:
            require(sha(self.read(write['target'], shared=True)) == write['expected_file_sha256'], 'El texto cambió desde que preparé esta versión. Guardé la propuesta por separado.', 'stale-base')
        for entry, write in zip(entries, manifest['writes']):
            before = self.read(write['target'], shared=True)
            require(sha(before) == write['expected_file_sha256'], 'El texto cambió durante la captura.', 'stale-base')
            if entry['before']:
                self.durable(entry['before'], before, exclusive=True)
            self.durable(entry['candidate'], candidates[write['target']], exclusive=True)
        self.durable(f'{history}/manifest.json', encoded(manifest), exclusive=True)
        journal = dict(manifest=manifest, manifest_sha256=sha(encoded(manifest)), phase='prepared', last_verified_phase='prepared', completed_targets=[], entries=entries)
        self.save_journal(journal)
        self.checkpoint('prepared', journal)
        return journal

    def save_journal(self, journal):
        journal['journal_sha256'] = sha(encoded({k: v for k, v in journal.items() if k != 'journal_sha256'}))
        self.durable(self.journal_path(journal['manifest']['operation_id']), encoded(journal))

    def cooperative(self, manifest):
        # Una bandera CLI, install.json o un disco tranquilo no prueban la UI.
        return callable(self.capability) and self.capability(self.root, manifest) is True

    def require_import_completion(self, candidate):
        if not any(self.path('.writing/imports').glob('*.json')):
            return
        current = self.read('estado.md')
        old_stage = identity_parts(current)[0].get('stage') if current else None
        new_stage = validate(candidate)['metadata'].get('stage')
        if old_stage in (None, 'setup', 'import', 'reconstruct') and new_stage not in ('setup', 'import', 'reconstruct'):
            from runtime import import_coverage
            coverage = import_coverage(self)
            require(coverage['complete'], 'Complete y compruebe los registros de la importación antes de avanzar: ' + '; '.join(coverage['issues']), 'incomplete-import')

    def replace_shared(self, write, candidate):
        self.path(write['target'], shared=True)
        if write['target'] == 'estado.md':
            self.require_import_completion(candidate)
        if hasattr(self, 'windows'):
            return self.windows.write(write['target'], candidate, exclusive=write['expected_file_sha256'] is None, expected=write['expected_file_sha256'], shared=True)
        with self.parent_fd(write['target'], create=True) as (parent, target):
            temporary = '.book-' + str(uuid.uuid4())
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(candidate)
                    stream.flush()
                    os.fsync(stream.fileno())
                require(sha(self.read(write['target'], shared=True)) == write['expected_file_sha256'], 'El texto cambió antes de guardar. La propuesta permanece separada.', 'stale-base')
                # La comprobación y el destino deben seguir nombrando el mismo directorio.
                with self.parent_fd(write['target']) as (current_parent, _):
                    require((os.fstat(parent).st_dev, os.fstat(parent).st_ino) == (os.fstat(current_parent).st_dev, os.fstat(current_parent).st_ino), 'El directorio de destino cambió.', 'path-outside-scope')
                if write['expected_file_sha256'] is None:
                    try:
                        os.link(temporary, target, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
                    except FileExistsError as exc:
                        raise Problem('stale-base', 'El archivo ya existe; se conserva sin cambios.') from exc
                    os.unlink(temporary, dir_fd=parent)
                else:
                    os.replace(temporary, target, src_dir_fd=parent, dst_dir_fd=parent)
                os.fsync(parent)
            finally:
                try:
                    os.unlink(temporary, dir_fd=parent)
                except FileNotFoundError:
                    pass

    def run_journal(self, journal, recovery=False, authorization=None, allow_apply=True):
        manifest = journal['manifest']
        effective = manifest
        if recovery:
            scope = authorization or {k:v for k,v in manifest['authorized_scope'].items() if k != 'editing_boundary'}
            require(isinstance(scope, dict) and isinstance(scope.get('request'), str) and scope['request'].strip() and isinstance(scope.get('targets'), list) and set(scope['targets']) == set(manifest['authorized_scope']['targets']), 'La recuperación requiere el mismo alcance y una solicitud explícita.', 'invalid-input')
            effective = {**manifest, 'authorized_scope': scope}
        artifacts = [e['candidate'] for e in journal['entries']]
        if journal['phase'] == 'reconciled':
            return result('already-completed', 'La operación ya terminó y no se vuelve a aplicar.', artifacts)
        if not allow_apply or not self.cooperative(effective):
            return result('candidate-only', 'Guardé la propuesta por separado. Hace falta un perfil verificado y una declaración actual de guardado y pausa; consulte check con action readiness.', artifacts, phase=journal['phase'])
        if recovery and authorization:
            journal.setdefault('recovery_authorizations', []).append(authorization)
            self.save_journal(journal)
        for entry, write in zip(journal['entries'], manifest['writes']):
            current = sha(self.read(write['target'], shared=True))
            require(current in {write['expected_file_sha256'], write['candidate_sha256']}, 'El texto cambió desde que preparé esta versión. Guardé la propuesta por separado.', 'stale-base')
            if write['target'] in journal['completed_targets']:
                require(current == write['candidate_sha256'], 'Un archivo ya aplicado cambió; no se vuelve a aplicar.', 'stale-base')
        try:
            for entry, write in zip(journal['entries'], manifest['writes']):
                candidate = self.read(entry['candidate'])
                if sha(self.read(write['target'], shared=True)) != write['candidate_sha256']:
                    self.checkpoint('before-replace', journal)
                    self.replace_shared(write, candidate)
                    self.checkpoint('after-replace', journal)
                require(sha(self.read(write['target'], shared=True)) == write['candidate_sha256'], 'El archivo cambió durante el guardado.', 'partial-save')
                self.remember(write['target'], candidate)
                self.checkpoint('before-settle', journal)
                time.sleep(0.02)
                if sha(self.read(write['target'], shared=True)) != write['candidate_sha256']:
                    self.capture_outside([write['target']])
                    raise Problem('partial-save', 'Se detectó una edición externa; conservé ambas versiones.')
                if write['target'] not in journal['completed_targets']:
                    journal['completed_targets'].append(write['target'])
                journal['phase'] = journal['last_verified_phase'] = 'applied'
                self.save_journal(journal)
                self.checkpoint('applied', journal)
            self.check(manifest={'targets': [w['target'] for w in manifest['writes']]})
            journal['phase'] = journal['last_verified_phase'] = 'reconciled'
            self.save_journal(journal)
            self.checkpoint('reconciled', journal)
            return result('reconciled', 'Se guardaron y comprobaron los archivos de la operación.', artifacts, completed_targets=journal['completed_targets'])
        except (Problem, OSError) as exc:
            journal['phase'] = 'failed'
            journal['error'] = exc.code if isinstance(exc, Problem) else 'storage-failure'
            try:
                self.save_journal(journal)
            except OSError:
                pass
            raise

    def apply_locked(self, manifest):
        operation = manifest['operation_id']
        self.capture_outside(sorted(set(self.content_paths()) | set(parse_json(self.read('.writing/known.json') or b'{}')) | {w['target'] for w in manifest['writes']}))
        if self.read(self.journal_path(operation)) is not None:
            journal = self.load_journal(operation)
            require(journal['manifest_sha256'] == sha(encoded(manifest)), 'La identidad de operación ya pertenece a otra solicitud.', 'invalid-input')
        else:
            journal = self.prepare(manifest)
        return self.run_journal(journal)

    def apply(self, manifest):
        operation = self.validate_apply(manifest)
        try:
            with self.lock(operation):
                return self.apply_locked(manifest)
        except Problem as exc:
            exc.artifacts = [w['candidate_path'] for w in manifest['writes'] if self.read(w['candidate_path']) is not None]
            raise

    def recover(self, manifest=None):
        operation = self.manifest(manifest) if manifest else 'recovery'
        with self.lock(operation, recover=True):
            self.capture_outside(sorted(set(self.content_paths()) | set(parse_json(self.read('.writing/known.json') or b'{}'))))
            operations = [operation] if manifest else [p.stem for p in self.path('.writing/operations').glob('*.json')]
            outcomes = []
            for identifier in operations:
                outcomes.append(self.run_journal(self.load_journal(identifier), recovery=True, authorization=manifest.get('authorized_scope') if manifest else None, allow_apply=manifest is not None))
            return result('recovered', 'Se inspeccionaron las operaciones sin repetir pasos verificados.', outcomes=outcomes)

    def import_material(self, manifest):
        import runtime
        runtime.require_private_initialization(self)
        import adapters
        try:
            return adapters.import_material(self, manifest)
        except Problem as exc:
            operation = self.manifest(manifest)
            ledger = f'.writing/imports/{operation}.json'
            if self.read(ledger) is not None:
                exc.artifacts.append(ledger)
            raise

    def export_material(self, manifest):
        import adapters
        try:
            return adapters.export_material(self, manifest)
        except Problem as exc:
            operation = self.manifest(manifest)
            mapping = self.read(f'.writing/exports/{operation}.json')
            if mapping:
                from maintenance import checked
                exc.artifacts.append(checked(mapping)['directory'])
            raise

    def hook_start(self, event=None):
        import runtime
        return runtime.startup(self)

    def hook_stop(self, event=None):
        import runtime
        return runtime.stop(self, event or {})

    def diff(self, manifest):
        operation = self.manifest(manifest)
        journal = self.load_journal(operation)
        diffs = []
        for entry in journal['entries']:
            before = self.read(entry['before']) if entry['before'] else b''
            after = self.read(entry['candidate'])
            lines = difflib.unified_diff(before.decode().splitlines(keepends=True), after.decode().splitlines(keepends=True), fromfile=entry['target'] + ' (antes)', tofile=entry['target'] + ' (propuesta)')
            diffs.append(''.join(line if line.endswith('\n') else line + '\n\\ No newline at end of file\n' for line in lines))
        return result('diff', 'Comparación entre la versión anterior y la propuesta. La marca "No newline at end of file" indica que la línea anterior no termina con un salto de línea.', diff='\n'.join(diffs))

    def restore(self, manifest):
        operation = self.manifest(manifest)
        with self.lock(operation):
            source = self.load_journal(manifest.get('source_operation_id'))
            scope = manifest.get('authorized_scope')
            require(isinstance(scope, dict) and isinstance(scope.get('request'), str) and scope['request'].strip() and isinstance(scope.get('targets'), list) and set(scope['targets']) == {w['target'] for w in source['manifest']['writes']}, 'Falta el alcance exacto de restauración.', 'invalid-input')
            writes = []
            for entry, write in zip(source['entries'], source['manifest']['writes']):
                require(entry['before'] is not None, 'Deshacer una creación requiere decidir qué conservar; no se elimina el archivo.', 'unsupported-format')
                candidate_path = f'.writing/candidates/{operation}-{len(writes)}.md'
                data = self.read(entry['before'])
                existing = self.read(candidate_path)
                require(existing is None or existing == data, 'Ya existe otra propuesta de restauración.', 'invalid-input')
                if existing is None:
                    self.durable(candidate_path, data, exclusive=True)
                writes.append(dict(target=entry['target'], expected_file_sha256=write['candidate_sha256'], candidate_path=candidate_path, candidate_sha256=sha(data), format=write['format']))
            restore_manifest = dict(schema_version=1, operation_id=operation, kind='restore', authorized_scope=manifest.get('authorized_scope'), writes=writes)
            self.validate_apply(restore_manifest)
            return self.apply_locked(restore_manifest)



def main():
    class SpanishFormatter(argparse.HelpFormatter):
        def add_usage(self, usage, actions, groups, prefix=None):
            return super().add_usage(usage, actions, groups, prefix='Uso: ')
    class SpanishParser(argparse.ArgumentParser):
        def error(self, message):
            print(json.dumps(result('invalid-input', 'La orden no es válida. Use --vault, una operación disponible y --manifest cuando corresponda.', ok=False), ensure_ascii=False))
            raise SystemExit(2)
    parser = SpanishParser(description='Conserva versiones del libro sin ocultar conflictos.', add_help=False, allow_abbrev=False, formatter_class=SpanishFormatter, usage='%(prog)s --vault RUTA OPERACIÓN [--manifest ARCHIVO|-]')
    parser._positionals.title = 'Operación'
    parser._optionals.title = 'Opciones'
    parser.add_argument('-h', '--help', action='help', help='Muestra esta ayuda y termina')
    parser.add_argument('--vault', required=True, metavar='RUTA', help='Ruta de la bóveda libro')
    parser.add_argument('operation', choices=('check', 'readiness', 'snapshot', 'apply', 'diff', 'restore', 'recover', 'hook-start', 'hook-stop', 'import', 'export'))
    parser.add_argument('--manifest', metavar='ARCHIVO|-', help='Archivo JSON de la solicitud')
    args = parser.parse_args()
    manifest = None
    try:
        require(sum(arg == '--vault' or arg.startswith('--vault=') for arg in sys.argv) == 1 and Path(args.vault).resolve() == Path(__file__).resolve().parents[2], 'Esta orden solo puede usar su propia bóveda; no sustituya --vault.', 'path-outside-scope')
        import runtime
        book = Book(args.vault, cooperative_capability=runtime.public_cooperative)
        manifest = parse_json(sys.stdin.buffer.read() if args.manifest == '-' else Path(args.manifest).read_bytes()) if args.manifest else None
        if args.operation.startswith('hook-') and manifest is None:
            manifest = parse_json(sys.stdin.buffer.read() or b'{}')
        require(manifest is None or isinstance(manifest, dict), 'La solicitud debe ser un objeto JSON.', 'invalid-input')
        require(manifest is not None or args.operation in {'check', 'recover', 'readiness'}, 'Esta operación requiere un manifiesto.', 'invalid-input')
        require(manifest is None or args.operation != 'readiness', 'readiness no recibe manifiesto.', 'invalid-input')
        if args.operation == 'readiness':
            output = book.check(dict(action='readiness'))  # Forma sin JSON para sesiones sin hooks.
        else:
            output = getattr(book, {'import':'import_material', 'export':'export_material'}.get(args.operation, args.operation.replace('-', '_')))(manifest)
    except Problem as exc:
        output = result(exc.code, exc.message, exc.artifacts, ok=False)
    except ImportError:
        output = result('missing-dependency', 'Falta un módulo del helper o una dependencia del entorno; repare la instalación antes de continuar.', ok=False)
    except (TypeError, KeyError, ValueError, RecursionError, AttributeError):
        output = result('invalid-input', 'El manifiesto o registro contiene valores inválidos; no continúe sin revisarlo.', ok=False)
    except OSError:
        output = result('storage-failure', 'No se pudo completar el acceso al almacenamiento. Conserve la propuesta y revise el espacio y los permisos.', ok=False)
    if not output['ok'] and not output['artifacts'] and isinstance(manifest, dict):
        for write in manifest.get('writes', []) if isinstance(manifest.get('writes'), list) else []:
            if isinstance(write, dict) and isinstance(write.get('candidate_path'), str) and write['candidate_path'].startswith('.writing/candidates/'):
                try:
                    if book.read(write['candidate_path']) is not None:
                        output['artifacts'].append(write['candidate_path'])
                except (Problem, OSError):
                    pass
        operation = manifest.get('operation_id')
        if isinstance(operation, str) and ID.fullmatch(operation):
            try:
                output['artifacts'] += [p.relative_to(book.root).as_posix() for p in book.path('.writing/candidates').glob(operation + '-*.md') if not p.is_symlink() and p.relative_to(book.root).as_posix() not in output['artifacts']]
            except (Problem, OSError):
                pass
    if not output['ok'] and output['artifacts'] and args.operation in ('apply', 'restore', 'snapshot'):
        output['next_action'] = 'Abra ' + output['artifacts'][0] + ' y compare con el texto actual; prepare una nueva solicitud con su hash vigente.'
        if output['code'] == 'storage-failure':
            output['next_action'] = 'Conserve ' + output['artifacts'][0] + ', revise el espacio y los permisos y ejecute recover antes de otra escritura.'
    if not output['ok'] and output['artifacts'] and args.operation == 'export':
        output['next_action'] = 'Revise manifest.json en ' + output['artifacts'][0] + ' y genere otra exportación cuando los cambios estén resueltos.'
    print(json.dumps(output, ensure_ascii=False, default=str))
    return 0 if output['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
