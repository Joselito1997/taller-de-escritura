#!/usr/bin/env python3
"""Preparación local ejecutada por Claude Code; nunca escribe en la fuente clonada."""
import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import socket
import stat
import struct
import subprocess
import sys
import time
import uuid
import venv
import zipfile
from pathlib import Path, PurePosixPath

SOURCE = Path(__file__).resolve().parent
PANDOC_URL = 'https://github.com/jgm/pandoc/releases/download/3.10.2/pandoc-3.10.2-arm64-macOS.zip'
PANDOC_SHA = 'a30bd546062f0b29c25f45a71f951b7a1cf4f998d5b43974ea2c2416133f2e99'
RESULT = 'installation-result.json'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.is_symlink(), 'No se escribe sobre enlaces simbólicos.')
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temp.open('x', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')
    os.replace(temp, path)


def safe_path(root, relative):
    p = PurePosixPath(relative)
    require(not p.is_absolute() and '..' not in p.parts and p.parts, 'Ruta de distribución inválida.')
    target = root.joinpath(*p.parts)
    require(all(not parent.is_symlink() for parent in [target, *target.parents]), 'La distribución contiene un enlace simbólico.')
    return target


def payload(source):
    allow = read_json(source / 'release-allowlist.json')
    names = set(allow['files']) | {e['path'] for e in read_json(source / 'starter-manifest.json')['files']}
    for rule in allow['prefixes']:
        base = safe_path(source, rule['prefix'])
        for p in base.rglob('*' + rule['suffix']):
            names.add(p.relative_to(source).as_posix())
    forbidden = {'.git', '.obsidian', '.claudian', '.writing', '.venv', '.installer', '__pycache__', 'development', 'tests', 'dist'}
    files = {}
    for name in sorted(names):
        require(not (set(PurePosixPath(name).parts) & forbidden), 'El paquete incluye archivos privados o de desarrollo.')
        require(name not in {'plan.md', 'implementation-plan.md', 'credentials.json', 'auth.json', 'tokens.json', 'installation-result.json'} and not any(p.startswith('.env') for p in PurePosixPath(name).parts), 'El paquete incluye un archivo privado.')
        require(not name.startswith(('libro/historia/', 'libro/planes/', 'libro/alternativas/', 'libro/bitacora/', 'libro/exportaciones/', 'libro/importaciones/originales/', 'libro/importaciones/derivados/', 'libro/investigacion/originales/', 'libro/investigacion/derivados/')), 'El paquete incluye material privado.')
        require(not name.startswith('libro/manuscrito/') or name == 'libro/manuscrito/indice.md', 'El paquete incluye un manuscrito.')
        p = safe_path(source, name)
        require(p.is_file(), 'Falta un archivo de distribución: ' + name)
        files[name] = p.read_bytes()
    manifest = {'schema_version': 1, 'release': allow['release'], 'files': [dict(path=n, sha256=sha(b), size=len(b)) for n, b in files.items()]}
    existing = source / 'release-manifest.json'
    if existing.exists():
        require(read_json(existing) == manifest, 'El manifiesto no coincide con los archivos descargados.')
    return files, manifest


def run_json(argv, env, manifest=None):
    command = list(map(str, argv))
    if manifest is not None:
        command += ['--manifest', '-']
    r = subprocess.run(command, input=json.dumps(manifest) if manifest is not None else None,
                       capture_output=True, text=True, env=env, timeout=240)
    try:
        result = json.loads(r.stdout)
    except ValueError:
        raise ValueError('Un ayudante no devolvió un resultado válido: ' + Path(command[1]).name)
    require(r.returncode == 0 and result.get('ok') is True, result.get('message', 'La preparación no pudo completarse.'))
    return result


def ensure_pandoc(target, env):
    existing = shutil.which('pandoc', path=env['PATH'])
    if existing:
        version = subprocess.check_output([existing, '--version'], text=True).splitlines()[0]
        if version == 'pandoc 3.10.2':
            destination = target / '.venv/bin/pandoc'
            if not destination.exists():
                destination.symlink_to(Path(existing).resolve())
            return
    archive = target / '.installer/pandoc.zip'
    if not archive.exists():
        partial = archive.with_suffix('.download')
        subprocess.run(['curl', '--fail', '--location', '--proto', '=https', '--tlsv1.2', '--max-time', '180', PANDOC_URL, '-o', str(partial)], check=True, capture_output=True)
        require(sha(partial.read_bytes()) == PANDOC_SHA, 'La descarga de Pandoc no coincide con su huella.')
        os.replace(partial, archive)
    require(sha(archive.read_bytes()) == PANDOC_SHA, 'La descarga de Pandoc no coincide con su huella.')
    with zipfile.ZipFile(archive) as z:
        candidates = [n for n in z.namelist() if n.endswith('/bin/pandoc')]
        require(len(candidates) == 1, 'El paquete de Pandoc no tiene la estructura esperada.')
        binary = z.read(candidates[0])
    destination = target / '.venv/bin/pandoc'
    require(not destination.exists() and not destination.is_symlink(), 'Ya hay un conversor distinto en el entorno; se conserva.')
    destination.write_bytes(binary)
    destination.chmod(0o755)


def prepare(source, target, model, claude, backup):
    marker = target / '.installer/installation.json'
    if marker.exists():
        old = read_json(marker)
        require(old['vault'] == str(target / 'libro'), 'La marca pertenece a otra instalación.')
        require(old['source_manifest'] == payload(source)[1], 'Hay una versión nueva; requiere actualización, no reinstalación.')
        require(old['model'] == model and old['backup'] == str(backup), 'La instalación existente conserva sus elecciones; no se cambian al reinstalar.')
        if old.get('status') == 'prepared':
            return old
    else:
        require(not (target / 'libro').exists(), 'El destino ya contiene un libro; no se sobrescribe.')
    require(not (target / '.git').exists(), 'El destino privado debe estar fuera de un repositorio Git.')
    files, manifest = payload(source)
    target.mkdir(parents=True, exist_ok=True)
    record = {'schema_version': 1, 'status': 'installing', 'vault': str(target / 'libro'), 'model': model, 'claude': claude, 'backup': str(backup), 'backup_scope': 'local, separado del libro; no es una copia fuera del equipo', 'source_manifest': manifest}
    if not marker.exists():
        write_json(marker, record)
    for name, body in files.items():
        dest = safe_path(target, name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            require(dest.read_bytes() == body, 'Se conserva un archivo cambiado durante la instalación: ' + name)
        else:
            with dest.open('xb') as f:
                f.write(body)
    write_json(target / 'release-manifest.json', manifest)
    backup.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'PIP_CACHE_DIR': str(target / '.installer/pip-cache'), 'PATH': str(target / '.venv/bin') + os.pathsep + str(Path(claude).parent) + os.pathsep + os.environ.get('PATH', '')}
    environment = target / '.venv'
    python = environment / 'bin/python'
    if python.exists():
        check = subprocess.run([str(python), '-c', 'import sys; print(sys.version)'], capture_output=True, text=True)
        if check.returncode != 0:
            environment.rename(target / '.installer' / ('incomplete-venv-' + uuid.uuid4().hex[:8]))
    if not python.exists():
        venv.EnvBuilder(with_pip=True, symlinks=True).create(environment)
    run_json([sys.executable, target / 'libro/.claude/scripts/setup.py', 'initialize'], env,
             {'schema_version': 1, 'operation_id': 'agent-install-' + uuid.uuid4().hex[:12], 'consent': True,
              'model': model, 'backup_destination': str(backup), 'install_dependencies': True, 'release_manifest': manifest})
    ensure_pandoc(target, env)
    vault = target / 'libro'
    write_json(vault / '.obsidian/community-plugins.json', [])
    write_json(vault / '.obsidian/core-plugins.json', {name: True for name in ['file-explorer', 'global-search', 'switcher', 'backlink', 'outgoing-link', 'tag-pane', 'page-preview', 'command-palette', 'editor-status', 'bookmarks', 'outline', 'word-count', 'file-recovery']})
    write_json(vault / '.obsidian/app.json', {})
    write_json(vault / '.claudian/claudian-settings.json', {
        'locale': 'es', 'permissionMode': 'normal', 'model': model, 'settingsProvider': 'claude',
        'savedProviderModel': {'claude': model}, 'savedProviderPermissionMode': {'claude': 'normal'},
        'enableAutoTitleGeneration': False, 'chatViewPlacement': 'right-sidebar', 'restoreTabsOnStartup': True,
        'providerConfigs': {'claude': {'enabled': True, 'safeMode': 'default', 'loadUserSettings': False,
            'cliPath': claude, 'defaultModel': model, 'lastModel': model,
            'environmentVariables': 'PATH=' + env['PATH']}}})
    record = {'schema_version': 1, 'status': 'prepared', 'vault': str(vault), 'model': model, 'claude': claude,
              'backup': str(backup), 'backup_scope': 'local, separado del libro; no es una copia fuera del equipo',
              'source_manifest': manifest, 'created_at': time.time()}
    write_json(marker, record)
    write_json(target / RESULT, {'status': 'prepared', 'vault': str(vault), 'model': model})
    return record


def install_plugins(target):
    vault = target / 'libro'
    for package, plugin in [('claudian', 'realclaudian'), ('kanban', 'obsidian-kanban')]:
        destination = vault / '.obsidian/plugins' / plugin
        destination.mkdir(parents=True, exist_ok=True)
        for name in ['main.js', 'manifest.json', 'styles.css']:
            original = target / 'vendor' / package / 'plugin' / name
            installed = destination / name
            require(not installed.exists() or installed.read_bytes() == original.read_bytes(), 'Se conserva un plugin cambiado durante la preparación.')
            if not installed.exists():
                shutil.copyfile(original, installed)

def register_vault(profile, vault, configure_locale=True):
    registry = profile / 'obsidian.json'
    before = registry.read_bytes() if registry.exists() else None
    config = json.loads(before) if before else {}
    require(isinstance(config, dict) and isinstance(config.get('vaults', {}), dict), 'La configuración de Obsidian no es válida; se conserva.')
    vaults = config.setdefault('vaults', {})
    found = [key for key, value in vaults.items() if value.get('path') == str(vault)]
    require(len(found) <= 1, 'Obsidian tiene registros duplicados para esta bóveda.')
    identity = found[0] if found else uuid.uuid4().hex[:16]
    vaults[identity] = {**vaults.get(identity, {}), 'path': str(vault), 'ts': int(time.time() * 1000), 'open': True}
    if configure_locale:
        config['language'] = 'es'
    config['cli'] = True
    if before is not None:
        archive = vault.parent / '.installer/obsidian-before.json'
        if not archive.exists():
            with archive.open('xb') as f:
                f.write(before)
    # Recheck the preimage rather than overwrite a concurrent settings update.
    require((registry.read_bytes() if registry.exists() else None) == before, 'Obsidian cambió su configuración durante la instalación; vuelva a comprobar.')
    write_json(registry, config)
    return identity


def clear_stale_cli_socket():
    endpoint = Path.home() / '.obsidian-cli.sock'
    try:
        before = endpoint.lstat()
    except FileNotFoundError:
        return
    require(stat.S_ISSOCK(before.st_mode) and before.st_uid == os.getuid(), 'El canal de Obsidian no es un socket propio; se conserva.')
    with socket.socket(socket.AF_UNIX) as probe:
        probe.settimeout(1)
        try:
            probe.connect(str(endpoint))
        except FileNotFoundError:
            return
        except ConnectionRefusedError:
            after = endpoint.lstat()
            require((after.st_dev, after.st_ino, after.st_mtime_ns) == (before.st_dev, before.st_ino, before.st_mtime_ns), 'El canal cambió durante la comprobación; se conserva.')
            endpoint.unlink()
            return
    raise ValueError('Otra instancia de Obsidian todavía utiliza el canal de comandos; se conserva.')


def cli_request(executable, profile, identity, vault, parts, timeout=30, expected_pid=None):
    """Obsidian 1.13.7 local CLI protocol; no repeated app launcher processes.

    The installed main.js accepts a newline-delimited {argv, tty, cwd} header.
    macOS LOCAL_PEERPID (sys/un.h) binds every request to the selected app.
    """
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(timeout)
        client.connect(str(Path.home() / '.obsidian-cli.sock'))
        pid = struct.unpack('i', client.getsockopt(0, 0x002, 4))[0]
        require(expected_pid is None or pid == expected_pid, 'Cambió la instancia de Obsidian; no se envía otra orden.')
        command = subprocess.check_output(['ps', '-p', str(pid), '-o', 'comm='], text=True).strip()
        require(command == str(executable), 'El canal pertenece a otra aplicación; no se envía ninguna orden.')
        arguments = subprocess.check_output(['ps', '-p', str(pid), '-o', 'args='], text=True)
        default_profile = Path.home() / 'Library/Application Support/obsidian'
        require(re.search(re.escape('--user-data-dir=' + str(profile)) + r'(?:\s--|\s*$)', arguments) or profile == default_profile and '--user-data-dir' not in arguments,
                'El canal pertenece a otro perfil; no se envía ninguna orden.')
        header = {'argv': ['vault=' + identity, *parts], 'tty': False, 'cwd': str(vault)}
        client.sendall((json.dumps(header) + '\n').encode())
        chunks = []
        size = 0
        while True:
            chunk = client.recv(65536)
            if not chunk:
                break
            size += len(chunk)
            require(size <= 8 * 1024 * 1024, 'La respuesta de Obsidian supera el límite de instalación.')
            chunks.append(chunk)
        return b''.join(chunks).decode('utf-8'), pid


def wait_for_renderer(evaluate, vault, identity, after=None, timeout=90):
    deadline = time.monotonic() + timeout
    expression = 'JSON.stringify({vault:app.vault.adapter.basePath,id:app.appId,ready:app.workspace.layoutReady,generation:performance.timeOrigin})'
    while True:
        try:
            frame = json.loads(evaluate(expression))
            if frame.get('vault') == vault and frame.get('id') == identity and frame.get('ready') is True and (after is None or frame['generation'] != after):
                return frame
        except (ValueError, OSError, subprocess.SubprocessError):
            pass
        require(time.monotonic() < deadline, 'Obsidian no confirmó un documento preparado para la bóveda exacta.')
        time.sleep(0.2)


def open_and_start(target, app, profile, timeout):
    previous_result = read_json(target / RESULT)
    resuming = previous_result.get('status') == 'complete' or (previous_result.get('status') == 'checking' and previous_result.get('previousStatus') == 'complete')
    if resuming:
        if previous_result.get('status') == 'complete':
            write_json(target / '.installer/previous-installation-result.json', previous_result)
        write_json(target / RESULT, {**previous_result, 'status': 'checking', 'previousStatus': 'complete'})
    executable = app / 'Contents/MacOS/Obsidian'
    require(executable.is_file(), 'No se encuentra Obsidian. Instale la aplicación antes de continuar.')
    # Do not launch an unopened app merely to quit it, or visit its default vaults.
    process_rows = subprocess.check_output(['ps', '-axo', 'pid=,comm='], text=True).splitlines()
    pids = [int(row.strip().split(None, 1)[0]) for row in process_rows
            if len(row.strip().split(None, 1)) == 2 and row.strip().split(None, 1)[1] == str(executable)]
    reuse_running = resuming and bool(pids)
    if reuse_running:
        config = read_json(profile / 'obsidian.json')
        identities = [key for key, value in config.get('vaults', {}).items() if value.get('path') == str(target / 'libro')]
        require(len(identities) == 1, 'No se encontró la bóveda ya instalada; se conserva la configuración existente.')
        identity = identities[0]
        args = [str(executable), '--user-data-dir=' + str(profile)]
    else:
        for pid in pids:
            script = 'ObjC.import("AppKit"); var a=$.NSRunningApplication.runningApplicationWithProcessIdentifier(' + str(pid) + '); if(a) a.terminate;'
            quit_result = subprocess.run(['osascript', '-l', 'JavaScript', '-e', script], capture_output=True, text=True, timeout=15)
            require(quit_result.returncode == 0, 'El sistema no permitió cerrar la aplicación seleccionada; no se fuerza el cierre.')
        deadline = time.monotonic() + 30
        while pids:
            remaining = subprocess.check_output(['ps', '-axo', 'pid=,comm='], text=True).splitlines()
            pids = [pid for pid in pids if any(row.strip().split(None, 1) == [str(pid), str(executable)] for row in remaining)]
            require(not pids or time.monotonic() < deadline, 'Obsidian todavía no cerró; se conserva su configuración y sus documentos.')
            if pids:
                time.sleep(0.2)
        identity = register_vault(profile, target / 'libro', configure_locale=not resuming)
        args = [str(executable), '--user-data-dir=' + str(profile)]
        clear_stale_cli_socket()
        log = target / '.installer/obsidian-start.log'
        subprocess.run(['open', '-n', '-a', str(app), '--stdout', str(log), '--stderr', str(log), '--args', '--user-data-dir=' + str(profile)], check=True, capture_output=True, text=True, timeout=30)
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
    command_log = []
    peer = {'last': None, 'verified': None}

    def command(*parts, timeout=30):
        try:
            output, pid = cli_request(executable, profile, identity, target / 'libro', list(parts), timeout, expected_pid=peer['verified'])
            peer['last'] = pid
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            command_log.append({'command': list(parts), 'error': str(error)})
            write_json(target / '.installer/commands.json', command_log)
            raise
        command_log.append({'command': list(parts), 'output': output})
        write_json(target / '.installer/commands.json', command_log)
        require(not output.startswith('Error:'), 'Falló una orden de Obsidian: ' + ' '.join(parts[:2]))
        return output.strip()

    def evaluate(code):
        text = command('eval', 'code=' + code, timeout=10)
        require(text.startswith('=> '), 'Obsidian todavía no devolvió el resultado de la comprobación.')
        return text[3:]

    frame = wait_for_renderer(evaluate, str(target / 'libro'), identity)
    peer['verified'] = peer['last']
    if not resuming and evaluate('localStorage.getItem("language")') != 'es':
        require(evaluate('(localStorage.setItem("language", "es"), localStorage.getItem("language"))') == 'es', 'Obsidian no guardó el idioma.')
        command('reload')
        frame = wait_for_renderer(evaluate, str(target / 'libro'), identity, after=frame['generation'])
        require(evaluate('localStorage.getItem("language")') == 'es', 'Obsidian no confirmó el idioma.')
    # Both reload and plugins:restrict schedule a renderer reload after returning.
    # Wait for a NEW, ready document rather than sending into the old one.
    if not resuming:
        install_plugins(target)
        evaluate('(async()=>{await app.plugins.loadManifests();return Object.keys(app.plugins.manifests)})()')
        if evaluate('app.plugins.isEnabled()') != 'true':
            command('plugins:restrict', 'off')
            frame = wait_for_renderer(evaluate, str(target / 'libro'), identity, after=frame['generation'])
        evaluate('(async()=>{await app.plugins.loadManifests();return Object.keys(app.plugins.manifests)})()')
        for plugin in ['realclaudian', 'obsidian-kanban']:
            command('plugin:enable', 'id=' + plugin, timeout=60)
            expression = 'Boolean(app.plugins.plugins[' + json.dumps(plugin) + '] && app.plugins.enabledPlugins.has(' + json.dumps(plugin) + '))'
            require(evaluate(expression) == 'true', 'Obsidian no confirmó el plugin cargado: ' + plugin)
    observed_version = command('version').splitlines()[-1].split()[0]
    entry = safe_path(target, 'installation/start.js')
    installed_source = read_json(target / '.installer/installation.json')['source_manifest']
    expected = next(e['sha256'] for e in installed_source['files'] if e['path'] == 'installation/start.js')
    require(sha(entry.read_bytes()) == expected, 'El arranque instalado fue modificado; se conserva y no se ejecuta como si fuera el original.')
    code = '(async()=>await require(' + json.dumps(str(entry)) + ')(app, ' + json.dumps(observed_version) + '))()'
    # One request only. A timeout never resends an attempted onboarding turn.
    output = command('eval', 'code=' + code, timeout=timeout)
    (target / '.installer/start-command.log').write_text(output + '\n')
    result = read_json(target / RESULT)
    require(result.get('status') == 'complete', result.get('message', 'La bienvenida todavía no terminó; conserve el estado y no vuelva a enviar el mensaje.'))
    return result


def main():
    parser = argparse.ArgumentParser(description='Instalación del taller dirigida por Claude Code.')
    parser.add_argument('--consent', action='store_true')
    parser.add_argument('--dest', type=Path, default=Path.home() / 'Taller de escritura')
    parser.add_argument('--model', default='opus')
    parser.add_argument('--backup', type=Path)
    parser.add_argument('--obsidian-app', type=Path, default=Path('/Applications/Obsidian.app'))
    parser.add_argument('--obsidian-profile', type=Path, default=Path.home() / 'Library/Application Support/obsidian')
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--timeout', type=int, default=300)
    args = parser.parse_args()
    try:
        require(args.consent, 'Falta la petición explícita de instalar el taller.')
        require(platform.system() == 'Darwin' and platform.machine() == 'arm64', 'Solo se ha comprobado macOS Apple Silicon.')
        require(platform.python_version() == '3.13.5', 'Ejecute instalar.sh para preparar el Python comprobado.')
        require(args.model and not any(c.isspace() for c in args.model), 'Identificador de modelo inválido.')
        require(not args.dest.is_symlink(), 'El destino no puede ser un enlace simbólico.')
        target = args.dest.expanduser().resolve()
        require(target != SOURCE and SOURCE not in target.parents, 'La copia privada debe quedar fuera del repositorio fuente.')
        claude = shutil.which('claude')
        require(claude is not None, 'No se encuentra el Claude Code del usuario.')
        require(args.obsidian_app.is_dir(), 'Instale Obsidian antes de pedir la preparación.')
        backup = (args.backup or target.with_name(target.name + ' - respaldos')).expanduser().resolve()
        require(backup != target and target not in backup.parents, 'El respaldo debe quedar fuera del libro.')
        print('Preparando ' + str(target) + ' con Claude ' + args.model + '.', flush=True)
        prepare(SOURCE, target, args.model, claude, backup)
        result = read_json(target / RESULT) if args.prepare_only else open_and_start(target, args.obsidian_app.resolve(), args.obsidian_profile.expanduser().resolve(), args.timeout)
        print(json.dumps({'ok': True, 'destination': str(target), 'status': result.get('status'), 'existing_installation': result.get('existingInstallation', False), 'receipt': str(target / RESULT), 'conversation_id': result.get('conversationId')}, ensure_ascii=False))
        return 0
    except (ValueError, OSError, subprocess.SubprocessError, KeyError, json.JSONDecodeError) as error:
        print(json.dumps({'ok': False, 'message': str(error)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
