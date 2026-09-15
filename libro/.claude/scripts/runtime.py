"""Consulta y contexto local; no decide aceptación ni avanza etapas."""
import json
import re
import uuid
from schemas import validate, BOARD_STATES, require, Problem

SCOPES = {'working': ('manuscrito/',), 'records': ('historia/', 'estado.md', 'direccion-creativa.md'), 'plans': ('planes/',), 'alternatives': ('alternativas/',), 'logs': ('bitacora/',), 'derived': ('importaciones/derivados/', 'investigacion/derivados/')}

# Rutas y resolución reales del artefacto instalado Claudian 2.2.6 es.4 (main.js: `.claudian/claudian-settings.json`,
# heredado `.claude/claudian-settings.json`). `.obsidian/plugins/realclaudian/data.json` solo guarda estado de pestañas.
CLAUDIAN_SETTINGS = '.claudian/claudian-settings.json'
CLAUDIAN_LEGACY_SETTINGS = '.claude/claudian-settings.json'
CLAUDIAN_SAFE_MODES = ('acceptEdits', 'auto', 'default')
CLAUDIAN_DEFAULT_SAFE_MODE = 'acceptEdits'
CLAUDIAN_PERMISSION_MODES = ('normal', 'plan', 'yolo')
CLAUDIAN_DEFAULT_PERMISSION_MODE = 'yolo'


def claudian_modes(book):
    """Lee safeMode y el permissionMode principal de Claudian tal como los resuelve el artefacto instalado.

    resolveSdkPermissionMode convierte yolo en bypassPermissions y plan en plan antes de consultar safeMode,
    así que ambos valores deciden. Solo se observa el archivo, no la memoria del proceso ni cambios por solicitud.
    """
    from book import parse_json
    for relative in (CLAUDIAN_SETTINGS, CLAUDIAN_LEGACY_SETTINGS):
        raw = book.read(relative, max_bytes=4 * 1024 * 1024)
        if raw is None:
            continue  # El artefacto solo lee el archivo heredado cuando no existe el actual.
        config = parse_json(raw)
        if not isinstance(config, dict):
            return CLAUDIAN_DEFAULT_SAFE_MODE, CLAUDIAN_DEFAULT_PERMISSION_MODE, relative
        # projectProviderState: la proyección guardada válida de claude prevalece; si no, queda el valor plano
        # tal cual (ausente vale yolo por los valores por defecto). Un valor inválido se devuelve sin corregir.
        saved = config.get('savedProviderPermissionMode')
        saved = saved.get('claude') if isinstance(saved, dict) else None
        permission_mode = saved if saved in CLAUDIAN_PERMISSION_MODES else config.get('permissionMode', CLAUDIAN_DEFAULT_PERMISSION_MODE)
        providers = config.get('providerConfigs')
        claude = providers.get('claude') if isinstance(providers, dict) else None
        claude = claude if isinstance(claude, dict) else {}
        if 'safeMode' in claude:
            stored = claude['safeMode']
        elif 'claudeSafeMode' in config:
            stored = config['claudeSafeMode']  # Clave plana heredada que el artefacto todavía resuelve.
        else:
            return CLAUDIAN_DEFAULT_SAFE_MODE, permission_mode, relative
        # Un valor presente pero inválido queda en 'default' dentro del artefacto; no se relaja aquí.
        return (stored if stored in CLAUDIAN_SAFE_MODES else 'default'), permission_mode, relative
    return CLAUDIAN_DEFAULT_SAFE_MODE, CLAUDIAN_DEFAULT_PERMISSION_MODE, None


def layout(book):
    from book import result
    from schemas import VAULT_DIRECTORIES
    directories = []
    for name in VAULT_DIRECTORIES:
        path = book.path(name)
        exists = path.is_dir()
        has_files = exists and any(p.is_file() and not p.is_symlink() for p in path.rglob('*'))
        directories.append(dict(path=name, exists=exists, has_files=has_files))
    missing = [row['path'] for row in directories if not row['exists']]
    return result('layout', 'Se consultó el catálogo de carpetas sin modificarlo.', directories=directories, missing=missing, complete=not missing)


def import_coverage(book):
    """Comprueba el cierre declarado contra notas y fuentes reales; no infiere entidades con regex."""
    from book import result, sha
    from schemas import IMPORT_RECORDS, frontmatter, HASH
    from maintenance import checked
    issues, sources = [], {}
    for path in book.path('.writing/imports').glob('*.json'):
        ledger = checked(book.read(path.relative_to(book.root).as_posix()))
        for source in ledger['sources']:
            sources[source['preserved_path']] = source['sha256']
        if ledger.get('failures'):
            issues.append('Hay unidades de importación con fallos o lectura pendiente: ' + path.stem)
    raw = book.read('importaciones/inventario.md')
    metadata = frontmatter(raw)[0] if raw else {}
    coverage = metadata.get('reconstruction')
    coverage = coverage if isinstance(coverage, dict) else {}
    reviewed = coverage.get('reviewed_sources')
    reviewed = reviewed if isinstance(reviewed, dict) else {}
    if not sources:
        issues.append('No hay fuentes conservadas por la importación para comprobar este cierre.')
    if reviewed != sources:
        issues.append('El alcance revisado no coincide con todas las fuentes importadas y sus hashes.')
    for path, digest in sources.items():
        if sha(book.read(path)) != digest:
            issues.append('La fuente conservada cambió: ' + path)
    categories = coverage.get('categories')
    categories = categories if isinstance(categories, dict) else {}
    if set(categories) != set(IMPORT_RECORDS):
        issues.append('Faltan categorías por revisar o hay categorías desconocidas.')
    for name, (prefix, types) in IMPORT_RECORDS.items():
        row = categories.get(name)
        if not isinstance(row, dict) or row.get('status') not in ('recorded', 'no-source'):
            issues.append('Categoría pendiente: ' + name)
            continue
        records = row.get('records')
        if not isinstance(records, list):
            issues.append('Falta la lista de notas de ' + name)
            continue
        if row['status'] == 'no-source':
            if records or not isinstance(row.get('reason'), str) or not row['reason'].strip():
                issues.append('La ausencia de información no está explicada: ' + name)
            continue
        if not records:
            issues.append('Hay información declarada sin notas: ' + name)
        for record in records:
            path = record.get('path') if isinstance(record, dict) else None
            digest = record.get('sha256') if isinstance(record, dict) else None
            if not isinstance(path, str) or not (path.startswith(prefix) if prefix.endswith('/') else path == prefix) or not isinstance(digest, str) or not HASH.fullmatch(digest):
                issues.append('Referencia de nota inválida: ' + name)
                continue
            data = book.read(path, shared=True)
            if data is None or sha(data) != digest:
                issues.append('Nota ausente o cambiada: ' + path)
            elif validate(data)['metadata'].get('type') not in types:
                issues.append('La nota no corresponde a su categoría: ' + path)
    structure = layout(book)
    issues.extend('Falta la carpeta ' + path for path in structure['missing'])
    gaps = checkpoint_gaps(book)
    issues.extend('Falta registrar en bitácora la operación ' + operation for operation in gaps)
    return result('import-coverage', 'La cobertura declarada está comprobada.' if not issues else 'La reconstrucción tiene trabajo pendiente; no declare la importación completa.',
                  complete=not issues, issues=issues, required_categories={k:v[0] for k,v in IMPORT_RECORDS.items()},
                  source_scope=sources, semantic_coverage='Declarada por el asistente; esta comprobación no demuestra que haya detectado todas las menciones.')


def search(book, manifest):
    from book import result, sha
    scope, query = manifest.get('scope'), manifest.get('query')
    require(scope in SCOPES and isinstance(query, str) and query.strip(), 'Indique una frase y un ámbito de búsqueda válido.', 'invalid-input')
    limit = manifest.get('limit', 20)
    require(type(limit) is int and 1 <= limit <= 50, 'El límite debe estar entre 1 y 50.', 'invalid-input')
    matches, scanned = [], []
    for target in book.content_paths():
        if not any(target.startswith(prefix) for prefix in SCOPES[scope]):
            continue
        data = book.read(target, shared=True)
        require(len(data) <= 1024 * 1024, f'El archivo supera el límite de consulta: {target}.', 'invalid-input')
        scanned.append(target)
        offset = 0
        for line, content in enumerate(data.splitlines(keepends=True), 1):
            if query.casefold() in content.decode().casefold():
                matches.append(dict(path=target, line=line, start=offset, end=offset + len(content), sha256=sha(content), text=content.decode().rstrip('\r\n'), scope=scope))
                if len(matches) == limit:
                    return result('search', 'Se alcanzó el límite de resultados; reduzca el ámbito para continuar.', matches=matches, scanned=scanned, limited=True)
            offset += len(content)
    return result('search', 'Búsqueda terminada en el ámbito indicado; ningún resultado no demuestra ausencia en todo el libro.', matches=matches, scanned=scanned, limited=False)


def board(book, normalize=False):
    from book import result, sha, identity_parts, unregistered
    target = 'trabajo-pendiente.md'
    data = book.read(target, shared=True)
    require(data is not None, 'Falta el tablero de trabajo.', 'source-unavailable')
    validate(data, 'kanban')
    text = data.decode()
    active, separator, archive = text.partition('\n***\n')
    section, cards, output = None, [], []
    known = {key.casefold(): value for key, value in BOARD_STATES.items()}
    for line in active.splitlines(keepends=True):
        if line.startswith('## '):
            section = known.get(line[3:].strip().casefold())
        match = re.match(r'^- \[([ xX])\] (.*?)(\r?\n)?$', line)
        if match and section:
            block = re.search(r'\^(task-[a-z0-9-]+)(?:\s|$)', line)
            identity = block[1] if block else None
            if normalize and identity is None:
                identity = 'task-' + str(uuid.uuid4())
                line = line.rstrip('\r\n') + ' ^' + identity + (match[3] or '')
            cards.append(dict(id=identity, state=section, text=match[2], checked=match[1].lower() == 'x', accepts_prose=False, needs_review=section == 'done'))
        output.append(line)
    dependencies, pending = [], []
    for path in book.content_paths():
        if path == target:
            continue
        record = book.read(path)
        if unregistered(identity_parts(record)[0]):
            pending.append(path)  # Sin identidad no es un registro de dependencias; se informa aparte.
            continue
        meta = validate(record)['metadata']
        if meta.get('board_task_id') and meta.get('depends_on'):
            dependencies.append(dict(record=path, task=meta['board_task_id'], depends_on=meta['depends_on'], requires_resolution_review=True))
    if normalize:
        return ''.join(output) + separator + archive
    return result('board', 'El tablero describe trabajo; sus tarjetas no aceptan prosa ni liberan dependencias por sí solas.', [target], cards=cards, dependencies=dependencies, unregistered=pending, automatic_archive=False, archive_present=bool(separator), file_sha256=sha(data))


def checkpoint_gaps(book):
    logs = []
    for target in book.content_paths():
        if target.startswith('bitacora/'):
            data = book.read(target)
            if validate(data)['metadata'].get('role') == 'primary':
                # Una mención en Pendientes o Próximo paso no acredita un guardado.
                section = re.search(r'^## Puntos de guardado[ \t]*\r?\n(.*?)(?=^## |\Z)', data.decode(), re.M | re.S)
                if section:
                    logs.append(section[1])
    text = '\n'.join(logs)
    mentioned = lambda identity: re.search(r'(?<![A-Za-z0-9_-])' + re.escape(identity) + r'(?![A-Za-z0-9_-])', text) is not None
    missing = []
    for path in book.path('.writing/operations').glob('*.json'):
        try:
            journal = book.load_journal(path.stem)
        except Problem:
            continue  # session_context informa el diario dañado; el hook no debe fallar por ello.
        hashes = [w['candidate_sha256'] for w in journal['manifest']['writes'] if w['format'] != 'session-log']
        if not mentioned(path.stem) and hashes and not all(digest in text for digest in hashes):
            missing.append(path.stem)
    for directory in ('imports','research'):
        for path in book.path('.writing/'+directory).glob('*.json'):
            if not mentioned(path.stem):
                missing.append(path.relative_to(book.root).as_posix())
    return missing


def session_context(book, populated):
    """Solo lectura: punteros e incoherencias que cualquier sesión, con o sin hooks, debe ver."""
    from book import parse_json, proven_dead
    notices, operations, logs, texts, phases = [], [], [], [], {}
    for path in book.path('.writing/operations').glob('*.json'):
        try:
            journal = book.load_journal(path.stem)
            phases[path.stem] = journal['phase']
            if journal['phase'] != 'reconciled':
                operations.append(dict(operation_id=path.stem, phase=journal['phase'], completed_targets=journal['completed_targets']))
        except Problem as exc:
            notices.append(exc.message)
    for target in book.content_paths():
        if target.startswith('bitacora/'):
            data = book.read(target)
            doc = validate(data)
            if doc['metadata'].get('role') == 'primary':
                texts.append(data.decode())
                if doc['metadata'].get('status') in ('open', 'interrupted', 'recovered'):
                    logs.append(target)
    pointers = [p for p in ('inicio.md', 'estado.md', 'manuscrito/indice.md', 'trabajo-pendiente.md') if book.read(p) is not None]
    pointers += logs
    if len(logs) > 1:
        notices.append('Hay varias bitácoras primarias abiertas; aclare cuál continúa antes de escribir.')
    marker_missing = book.read('.writing/install.json') is None
    if marker_missing and populated:
        notices.append('Hay material del libro sin marca de instalación: es un caso de recuperación. Ejecute setup con recover_existing; no reinicialice ni vuelva a importar.')
    elif marker_missing:
        notices.append('Falta la marca de instalación; revise setup antes de declarar el espacio listo.')
    if operations:
        notices.append('Hay operaciones pendientes; contraste sus hashes con la bitácora sin repetir texto aplicado.')
    gaps = checkpoint_gaps(book)
    if gaps:
        notices.append('Hay operaciones sin referencia de checkpoint en bitácoras primarias; contraste el diario, sin deshacer texto verificado: ' + ', '.join(gaps))
    # El diario manda sobre el resultado de escritura: una bitácora que cita una operación no conciliada no la da por guardada.
    text = '\n'.join(texts)
    mismatches = sorted(identity for identity, phase in phases.items() if phase != 'reconciled' and identity in text)
    if mismatches:
        notices.append('La bitácora menciona operaciones que el diario no registra como conciliadas; informe la diferencia sin elegir la versión optimista: ' + ', '.join(mismatches))
    writer = None
    raw = book.read('.writing/lock.json')
    if raw is not None:
        try:
            owner = parse_json(raw)
            live = not proven_dead(owner)
        except (Problem, KeyError, TypeError, AttributeError):
            owner, live = {}, True
        if live:
            writer = dict(operation_id=owner.get('operation_id') if isinstance(owner, dict) else None, verified_identity=bool(owner))
            # Observación puntual: un bloqueo vivo al iniciar no fija el permiso de toda la conversación.
            notices.append('En esta consulta, otro escritor conserva el bloqueo del libro o su identidad no se puede comprobar; mientras siga así, esta sesión solo lee, no cambia estado ni asume otro rol. Es una observación puntual: antes de cambiar estado más adelante, vuelva a consultar readiness y recover.')
    return dict(pointers=pointers, notices=notices, pending_operations=operations, uncheckpointed_operations=gaps, log_journal_mismatches=mismatches, writer_lock=writer, recovery_case=marker_missing and bool(populated))


def startup(book):
    from book import result
    import setup
    populated = setup.populated(book.root)  # Antes de recover, que crea registros internos.
    notices = []
    try:
        book.recover()  # Solo conserva fuera de edición y observa pendientes en candidate-only.
    except (Problem, OSError) as exc:
        if not isinstance(exc, Problem) or exc.code != 'lock-busy':  # La contienda se explica en session_context.
            notices.append(exc.message if isinstance(exc, Problem) else 'No se pudo conservar la instantánea de inicio; revise almacenamiento.')
    session = session_context(book, populated)
    session['notices'] = notices + session['notices']
    pointers = session.pop('pointers')
    context = 'Responde siempre en español. Lee estos archivos antes de trabajar: ' + ', '.join(pointers) + '. ' + ' '.join(session['notices'])
    return result('startup', 'Contexto de inicio observado, sin decidir cambios de etapa.', pointers, **session, hookSpecificOutput=dict(hookEventName='SessionStart', additionalContext=context))


def stop(book, event):
    from book import result
    if event.get('stop_hook_active'):
        return result('stop', 'El recordatorio ya se emitió; no se repite.')
    incomplete = []
    for path in book.path('.writing/operations').glob('*.json'):
        try:
            if book.load_journal(path.stem)['phase'] != 'reconciled':
                incomplete.append(path.stem)
        except Problem:
            incomplete.append(path.stem)  # Un diario dañado tampoco está conciliado.
    gaps = checkpoint_gaps(book)
    output = result('stop', 'Se comprobó el cierre sin modificar registros compartidos.', pending_operations=incomplete, uncheckpointed_operations=gaps)
    if gaps:
        output['hookSpecificOutput'] = dict(hookEventName='Stop', additionalContext='Informe las propuestas u operaciones pendientes y el próximo paso exacto; no declare guardados los registros sin verificar. Operaciones: ' + ', '.join(gaps))
    return output


def hook_configuration(book):
    """Hooks declarados en archivos del proyecto; no demuestra que Claude Code o Claudian los ejecuten."""
    from book import parse_json
    declared, disabled = set(), False
    for relative in ('.claude/settings.json', '.claude/settings.local.json'):
        raw = book.read(relative)
        config = parse_json(raw) if raw is not None else None
        if not isinstance(config, dict):
            continue
        disabled |= config.get('disableAllHooks') is True
        hooks = config['hooks'] if isinstance(config.get('hooks'), dict) else {}
        for event, ending in (('SessionStart', ' hook-start'), ('Stop', ' hook-stop'), ('PreToolUse', 'permission_guard.py')):
            for group in hooks.get(event) if isinstance(hooks.get(event), list) else []:
                entries = group['hooks'] if isinstance(group, dict) and isinstance(group.get('hooks'), list) else []
                if any(isinstance(h, dict) and isinstance(h.get('command'), str) and h['command'].rstrip('\'"').endswith(ending) for h in entries):
                    declared.add(event)
    return dict(session_start=('SessionStart' in declared), stop=('Stop' in declared), permission_guard=('PreToolUse' in declared), disabled_in_project=disabled, configured_in_project=len(declared) == 3 and not disabled)


PINNED_PLUGINS = {'realclaudian': 'vendor/claudian/plugin/', 'obsidian-kanban': 'vendor/kanban/plugin/'}


def readiness(book):
    from book import Book, result, parse_json, sha
    import setup
    raw = book.read('.writing/install.json')
    marker = parse_json(raw) if raw else {}
    notes = []
    if marker.get('schema_version') != 1:
        notes.append('Falta una marca de instalación compatible; ejecute setup de forma explícita.')
    session = session_context(book, setup.populated(book.root))
    try:
        hooks = hook_configuration(book)
    except Problem:
        hooks = dict(configured_in_project=False, damaged=True)
    if not hooks['configured_in_project']:
        notes.append('Los hooks de inicio, cierre o guardia no están declarados o están deshabilitados en el proyecto; lea manualmente ' + ', '.join(session['pointers']) + ' y consulte recover antes de escribir.')
    try:
        package = Book(book.root.parent)
    except Problem:
        package = None
    plugins = {}
    for identity in ('realclaudian', 'obsidian-kanban'):
        manifest = book.read(f'.obsidian/plugins/{identity}/manifest.json')
        binary = book.read(f'.obsidian/plugins/{identity}/main.js')
        names = ('manifest.json', 'main.js', 'styles.css')
        pinned = {name: sha(package.read(PINNED_PLUGINS[identity] + name)) for name in names} if package else {}
        installed = {name: sha(book.read(f'.obsidian/plugins/{identity}/{name}')) for name in names}
        # Comparación de bytes con el artefacto español fijado; una actualización no revisada no conserva esa verificación.
        matches = installed == pinned if pinned.get('main.js') else None
        if manifest is not None and matches is False:
            notes.append('El complemento ' + identity + ' instalado no coincide con el artefacto en español de ' + PINNED_PLUGINS[identity] + '; una actualización no revisada puede quitar la interfaz en español. Reinstale el artefacto fijado o verifique la nueva versión antes de darla por válida.')
        if identity == 'realclaudian':
            try:
                safe_mode, permission_mode, source = claudian_modes(book)
            except Problem:
                safe_mode = permission_mode = source = None
                notes.append('No se pudo leer ' + CLAUDIAN_SETTINGS + '; no se deduce el modo de confirmación de Claudian.')
            if permission_mode == 'plan':
                notes.append('Claudian está en PLAN: esta sesión prepara propuestas sin aplicar cambios.')
        plugins[identity] = {'present': manifest is not None and binary is not None, 'version': parse_json(manifest).get('version') if manifest else None, 'main_sha256': sha(binary), 'matches_pinned_spanish_artifact': matches, 'enabled_observed': False}
    profile = profile_status(book)
    registration = marker.get('verified_profile', {})
    available = profile['eligible'] and marker.get('write_mode') == 'cooperative' and all(registration.get(key) == profile.get(key) for key in ('profile_id','compatibility_sha256','release_manifest_sha256'))
    # Solo cuenta lo que setup verify registró desde este mismo perfil aprobado y vigente; el indicador suelto no basta.
    observations = runtime_observations(profile if available else None)
    recorded = marker.get('capabilities', {}).get('runtime', {})
    same = recorded.get('evidence') == observations['evidence']
    hooks['observed'] = same and observations['hooks_observed'] and recorded.get('hooks_observed') is True
    permissions = dict(observed=same and observations['permissions_observed'] and recorded.get('permissions_observed') is True)
    if not permissions['observed']:
        notes.append('No hay evidencia aplicable de denegaciones reales en esta combinación; «Seguro» por sí solo no demuestra permisos restringidos.' + (' Es un límite de la evidencia histórica, no un bloqueo de guardado.' if available else ''))
    return result('readiness', 'Se comprobó la disponibilidad del helper; cada aplicación requiere la pausa actual del autor.', notices=notes, install=marker, hooks=hooks, permissions=permissions, session=session, plugins=plugins, cooperative_profile=profile, write_mode='cooperative' if available else 'candidate-only', ready=available, ready_scope='guarded-apply-only')


def audit_extensions(book):
    from maintenance import checked
    from book import sha, parse_json
    for path in book.path('.writing/imports').glob('*.json'):
        record = checked(book.read(path.relative_to(book.root).as_posix()))
        require(isinstance(record.get('sources'), list) and isinstance(record.get('candidates'), list), 'Inventario de importación dañado.', 'invalid-input')
        for source in record['sources']:
            require(source['preserved_path'].startswith((f"importaciones/originales/{source['sha256']}/",f"investigacion/originales/{source['sha256']}/")) and sha(book.read(source['preserved_path'])) == source['sha256'], 'Original importado dañado.', 'invalid-input')
        for candidate in record['candidates']:
            require(candidate['candidate_path'].startswith('.writing/candidates/') and sha(book.read(candidate['candidate_path'])) == candidate['candidate_sha256'], 'Propuesta importada dañada.', 'invalid-input')
    for path in book.path('.writing/import-targets').glob('*.json'):
        group = checked(book.read(path.relative_to(book.root).as_posix()))
        book.path(group['target'], shared=True)
        for candidate in group['candidates']:
            require(candidate['candidate_path'].startswith('.writing/candidates/') and sha(book.read(candidate['candidate_path'])) == candidate['candidate_sha256'], 'El registro de versiones candidatas está dañado.', 'invalid-input')
    for path in book.path('.writing/research').glob('*.json'):
        record = checked(book.read(path.relative_to(book.root).as_posix()))
        require(isinstance(record.get('requests'), dict), 'Registro de investigación dañado.', 'invalid-input')
        for request in record['requests'].values():
            if request.get('status') == 'saved':
                require(request['artifact'] == f"investigacion/originales/{request['sha256']}/" + ('original.pdf' if request.get('tool') == 'preserve_pdf' else 'respuesta.json') and sha(book.read(request['artifact'])) == request['sha256'], 'Respuesta guardada dañada.', 'invalid-input')
    for path in book.path('.writing/system-updates').glob('*/operation.json'):
        record = checked(book.read(path.relative_to(book.root).as_posix()))
        for entry in record['entries']:
            require(entry['history'].startswith('.writing/system-updates/' + path.parent.name + '/') and sha(book.read(entry['history'] + '.candidate')) == entry['candidate_sha256'], 'Candidato de sistema dañado.', 'invalid-input')
            if entry['before_sha256'] is not None and entry.get('before_saved', True):
                require(sha(book.read(entry['history'] + '.before')) == entry['before_sha256'], 'Preimagen de sistema dañada.', 'invalid-input')
    for path in book.path('.writing/exports').glob('*.json'):
        checked(book.read(path.relative_to(book.root).as_posix()))
    for relative in ('.writing/research-library.json',):
        if book.read(relative):
            checked(book.read(relative))
    for relative in ('.writing/install.json', '.writing/last-backup.json'):
        if book.read(relative):
            require(isinstance(parse_json(book.read(relative)), dict), 'Registro local dañado: ' + relative, 'invalid-input')



def require_private_initialization(book):
    from book import parse_json
    import subprocess
    raw = book.read('.writing/install.json')
    marker = parse_json(raw) if raw else {}
    require(isinstance(marker, dict) and marker.get('schema_version') == 1 and marker.get('private_initialized') is True, 'Complete setup antes de importar material; todavía no se verificó la inicialización privada.', 'validation-failed')
    for directory in (book.root, *book.root.parents):
        git_entry = directory / '.git'
        if git_entry.exists() or git_entry.is_symlink():
            require(directory == book.root.parent and git_entry.is_dir() and not git_entry.is_symlink(), 'La bóveda está dentro de otro repositorio o worktree; conserve ese remoto y use una copia independiente.', 'validation-failed')
            try:
                run = subprocess.run(['git','-C',str(directory),'remote'],capture_output=True,text=True,timeout=10)
            except (OSError, subprocess.SubprocessError) as exc:
                raise Problem('validation-failed', 'No se pudo comprobar la ausencia de remotos; no importe todavía.') from exc
            require(run.returncode == 0 and not run.stdout.strip(), 'Existe un remoto; no importe material privado hasta resolverlo mediante setup.', 'validation-failed')
            break


COOPERATIVE_CHECKS = {'saved-paused-apply', 'unsaved-buffer-candidate', 'drag', 'restore', 'restart'}
RUNTIME_HOOK_EVENTS = {'SessionStart', 'Stop', 'PreToolUse'}


def runtime_observations(status):
    """Hooks y denegaciones reales solo desde evidence.runtime_observations de un perfil elegible; nunca por archivos, flags ni los controles de editor."""
    from schemas import HASH
    eligible = (isinstance(status, dict) and status.get('eligible') is True
                and status.get('evidence', {}).get('approved') is True
                and not status.get('version_differences')
                and status.get('permission_mode', 'normal') == 'normal'
                and status.get('safe_mode', 'default') == 'default')
    observed = status['evidence'].get('runtime_observations') if eligible else None
    observed = observed if isinstance(observed, dict) else {}

    def record(kind, valid):
        entry = observed.get(kind)
        if isinstance(entry, dict) and isinstance(entry.get('id'), str) and entry['id'] and isinstance(entry.get('sha256'), str) and HASH.fullmatch(entry['sha256']) and valid(entry):
            return dict(id=entry['id'], sha256=entry['sha256'])
        return None
    names = lambda value: isinstance(value, list) and value and all(isinstance(v, str) and v for v in value)
    hooks = record('hooks', lambda e: names(e.get('events')) and RUNTIME_HOOK_EVENTS <= set(e['events']))
    permissions = record('permissions', lambda e: e.get('request_permission_mode') == 'default' and names(e.get('denied')))
    source = dict(profile_id=status.get('profile_id'), compatibility_sha256=status.get('compatibility_sha256')) if eligible else dict(profile_id=None, compatibility_sha256=None)
    return dict(hooks_observed=hooks is not None, permissions_observed=permissions is not None, evidence=dict(source, hooks=hooks, permissions=permissions))
# Claves locales que solo cambian presentación; cualquier otra exige volver a verificar el perfil.
LOCAL_SETTINGS_BENIGN = {'spinnerTipsEnabled'}


def profile_status(book, requested=None):
    """Contrasta el perfil aprobado de distribución, sin inventar pruebas UI."""
    from book import Book, parse_json, sha
    from schemas import HASH
    import platform
    import subprocess
    try:
        marker = parse_json(book.read('.writing/install.json') or b'{}')
        identity = requested if requested is not None else marker.get('cooperative_profile')
        require(isinstance(identity, str) and identity, 'No hay un perfil cooperativo seleccionado.', 'cooperative-unavailable')
        require(marker.get('private_initialized') is True, 'Falta inicialización privada.', 'cooperative-unavailable')
        require_private_initialization(book)
        package = Book(book.root.parent)
        compatibility_bytes = package.read('compatibility.json', max_bytes=4*1024*1024)
        release_bytes = package.read('release-manifest.json', max_bytes=4*1024*1024)
        require(compatibility_bytes is not None and release_bytes is not None, 'Falta el registro de compatibilidad de la distribución.', 'cooperative-unavailable')
        compatibility, release = parse_json(compatibility_bytes), parse_json(release_bytes)
        require(type(compatibility.get('schema_version')) is int and compatibility['schema_version'] == 1 and type(release.get('schema_version')) is int and release['schema_version'] == 1, 'La versión del registro no es compatible.', 'cooperative-unavailable')
        files = release.get('files')
        require(isinstance(files, list) and all(isinstance(e, dict) and isinstance(e.get('path'), str) and isinstance(e.get('sha256'), str) and HASH.fullmatch(e['sha256']) for e in files), 'El manifiesto de distribución es inválido.', 'cooperative-unavailable')
        require(len(files) == len({e['path'].casefold() for e in files}), 'El manifiesto repite rutas.', 'cooperative-unavailable')
        distributed = {e['path']:e['sha256'] for e in files}
        require(distributed.get('compatibility.json') == sha(compatibility_bytes), 'El registro de compatibilidad cambió respecto a la distribución.', 'cooperative-unavailable')
        profiles = compatibility.get('cooperative_profiles')
        require(isinstance(profiles, list), 'La lista de perfiles es inválida.', 'cooperative-unavailable')
        matching = [p for p in profiles if isinstance(p, dict) and p.get('id') == identity]
        require(len(matching) == 1, 'El perfil no existe o es ambiguo.', 'cooperative-unavailable')
        profile = matching[0]; evidence = profile.get('evidence', {})
        require(profile.get('enabled') is True and profile.get('platform') == platform.system().lower() and profile['platform'] in ('darwin', 'windows') and profile.get('architecture', '').casefold() == platform.machine().casefold(), 'El perfil no está habilitado para esta plataforma.', 'cooperative-unavailable')
        native_windows = profile['platform'] == 'windows' and profile.get('verification_level') == 'implementation-only'
        require(native_windows or isinstance(evidence, dict) and evidence.get('approved') is True and isinstance(evidence.get('id'), str) and evidence['id'] and isinstance(evidence.get('sha256'), str) and HASH.fullmatch(evidence['sha256']) and isinstance(evidence.get('checks'), list) and COOPERATIVE_CHECKS <= set(evidence['checks']), 'Falta la aprobación de las comprobaciones observadas de UI.', 'cooperative-unavailable')
        if native_windows:
            require(platform.version().split('.')[0] == '10', 'Esta ruta está preparada para Windows 10 y 11.', 'cooperative-unavailable')
        versions = profile.get('versions', {})
        require(isinstance(versions, dict) and all(isinstance(versions.get(k), str) and versions[k] for k in ('python','claude_code','obsidian','claudian','kanban','os_version')), 'El perfil no identifica todas las versiones.', 'cooperative-unavailable')
        installed = profile.get('installed_files')
        require(isinstance(installed, list) and installed and all(isinstance(e, dict) and {'path','release_path','sha256'} <= e.keys() for e in installed), 'Falta el inventario de artefactos instalados.', 'cooperative-unavailable')
        paths = [e['path'] for e in installed]
        require(all(isinstance(p, str) for p in paths) and len(paths) == len(set(p.casefold() for p in paths)), 'El perfil repite rutas instaladas.', 'cooperative-unavailable')
        required = {'.claude/scripts/' + p.name for p in book.path('.claude/scripts').glob('*.py')}
        require({'.claude/scripts/'+name for name in ('book.py','schemas.py','runtime.py','setup.py','permission_guard.py','adapters.py','research.py','maintenance.py')} <= required <= set(paths), 'El perfil omite scripts que sostienen la ruta.', 'cooperative-unavailable')
        for entry in installed:
            require(isinstance(entry['sha256'], str) and HASH.fullmatch(entry['sha256']) and distributed.get(entry['release_path']) == entry['sha256'], 'Un artefacto no coincide con el manifiesto de distribución.', 'cooperative-unavailable')
            require(sha(package.read(entry['release_path'])) == entry['sha256'] and sha(book.read(entry['path'])) == entry['sha256'], 'Los bytes instalados o distribuidos cambiaron.', 'cooperative-unavailable')
        actual = {'python': platform.python_version(), 'os_version': platform.version() if native_windows else platform.mac_ver()[0]}
        # La versión global es procedencia, no autorización para guardar el libro.
        try:
            run = subprocess.run(['claude','--version'], capture_output=True, text=True, timeout=10)
            actual['claude_code'] = run.stdout.split()[0] if run.returncode == 0 and run.stdout.strip() else None
        except (OSError, subprocess.SubprocessError):
            actual['claude_code'] = None
        for name in ('claudian','kanban'):
            manifests = [e for e in installed if e['release_path'].startswith('vendor/'+name+'/') and e['path'].endswith('/manifest.json')]
            require(len(manifests) == 1, 'Falta el manifiesto instalado de ' + name + '.', 'cooperative-unavailable')
            data = parse_json(book.read(manifests[0]['path']))
            base = '.obsidian/plugins/' + data['id'] + '/'
            require(manifests[0]['path'] == base+'manifest.json' and base+'main.js' in paths and (book.read(base+'styles.css') is None or base+'styles.css' in paths), 'El perfil omite un artefacto del plugin.', 'cooperative-unavailable')
            actual[name] = data['version']
            if name == 'claudian':
                safe_mode, permission_mode, source = claudian_modes(book)
                require(source is not None, 'Falta la configuración real de Claudian; no se deduce el modo desde los valores por defecto.', 'cooperative-unavailable')
                require(permission_mode in ('normal', 'yolo'), 'El modo permissionMode de Claudian es PLAN o no se reconoce; se conserva la propuesta sin aplicar.', 'cooperative-unavailable')
        differences = {key: {'observed': versions[key], 'current': value} for key, value in actual.items() if value != versions[key]}
        settings = book.read('.claude/settings.json')
        require(settings is not None and sha(settings) == marker.get('generated_files', {}).get('.claude/settings.json'), 'La configuración local cambió.', 'cooperative-unavailable')
        config = parse_json(settings)
        import setup
        expected_settings = setup.settings_for(book.root, book.root.parent / ('.venv/Scripts/python.exe' if native_windows else '.venv/bin/python'), marker.get('model'))
        require(all(config.get(key) == value for key, value in expected_settings.items()), 'La configuración no coincide con la ruta generada del helper.', 'cooperative-unavailable')
        requirements = package.read('requirements.lock')
        require(requirements is not None and distributed.get('requirements.lock') == sha(requirements), 'El archivo de dependencias no coincide con la distribución.', 'cooperative-unavailable')
        import importlib.metadata
        for line in requirements.decode().splitlines():
            if line.strip():
                name, version = line.split('==')
                require(name in ('PyYAML','pypdf') and importlib.metadata.version(name) == version, 'Una dependencia cambió respecto a la versión fijada.', 'cooperative-unavailable')
        # Claudian 2.2.6 carga siempre las fuentes project y local (PZe en main.js), y local tiene precedencia sobre project.
        local = book.read('.claude/settings.local.json')
        if local is not None:
            overrides = parse_json(local)
            require(isinstance(overrides, dict) and set(overrides) <= LOCAL_SETTINGS_BENIGN, '.claude/settings.local.json cambia ajustes que el perfil no verificó (' + ', '.join(sorted(set(overrides) - LOCAL_SETTINGS_BENIGN)) + '); se conservan las propuestas por separado. Retire esos ajustes o vuelva a verificar la combinación.' if isinstance(overrides, dict) else '.claude/settings.local.json no es un objeto de configuración; se conservan las propuestas por separado.', 'cooperative-unavailable')
        require(config.get('autoMemoryEnabled') is False and config.get('disableAllHooks') is not True and config.get('permissions', {}).get('defaultMode') == 'default' and {'Edit','Write','NotebookEdit'} <= set(config.get('permissions', {}).get('deny', [])) and config.get('hooks', {}).get('PreToolUse'), 'La configuración no conserva el contrato de permisos.', 'cooperative-unavailable')
        return dict(eligible=True, profile_id=identity, compatibility_sha256=sha(compatibility_bytes), release_manifest_sha256=sha(release_bytes), checked_versions=actual, version_differences=differences, permission_mode=permission_mode, safe_mode=safe_mode, ui_observed_versions={'obsidian':versions['obsidian']}, current_renderer_checked=False, evidence=evidence)
    except (Problem, OSError, ValueError, TypeError, KeyError, AttributeError, ImportError, subprocess.SubprocessError) as exc:
        return dict(eligible=False, reason=exc.message if isinstance(exc, Problem) else 'No se pudo verificar el perfil; se conserva la propuesta por separado.')


def public_cooperative(root, manifest):
    from book import Book, parse_json
    from schemas import timestamp
    from datetime import datetime, timezone
    try:
        book = Book(root)
        marker = parse_json(book.read('.writing/install.json') or b'{}')
        status = profile_status(book)
        registration = marker.get('verified_profile', {})
        if not status['eligible'] or marker.get('write_mode') != 'cooperative':
            return False
        if any(registration.get(key) != status[key] for key in ('profile_id','compatibility_sha256','release_manifest_sha256')):
            return False
        scope = manifest.get('authorized_scope', {})
        boundary = scope.get('editing_boundary', {})
        if not isinstance(boundary, dict) or not isinstance(boundary.get('statement'), str) or not boundary['statement'].strip() or not isinstance(boundary.get('confirmed_at'), str) or not timestamp(boundary['confirmed_at']):
            return False
        targets = boundary.get('targets')
        if not isinstance(targets, list) or len(targets) != len(set(targets)) or set(targets) != set(scope.get('targets', [])):
            return False
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(boundary['confirmed_at'].replace('Z','+00:00'))).total_seconds()
        return -5 <= age <= 300
    except (Problem, OSError, ValueError, TypeError, KeyError, AttributeError):
        return False
