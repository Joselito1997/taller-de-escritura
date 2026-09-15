"""Apertura nativa mediante el redirector oficial Obsidian.com, sin WSL."""
import json
import os
from pathlib import Path
import subprocess
import time


def open_and_start_windows(target, executable, profile, timeout):
    from instalar import read_json, write_json, require, register_vault, install_plugins, wait_for_renderer, RESULT
    cli = executable.with_suffix('.com')
    require(cli.is_file(), 'Falta Obsidian.com. El agente debe completar la instalación actual de Obsidian con su instalador oficial.')
    vault = target / 'libro'
    prior = read_json(target / RESULT)
    resuming = prior.get('status') == 'complete' or prior.get('status') == 'checking' and prior.get('previousStatus') == 'complete'
    # Cierre normal, nunca Stop-Process: el editor conserva sus diálogos de guardado.
    if not resuming:
        env = {**os.environ, 'WRITING_OBSIDIAN_EXE': str(executable)}
        code = '$ErrorActionPreference="Stop"; Get-Process Obsidian -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $env:WRITING_OBSIDIAN_EXE -and $_.MainWindowHandle -ne 0 } | ForEach-Object { if (-not $_.CloseMainWindow()) { throw "Obsidian no aceptó el cierre normal" }; if (-not $_.WaitForExit(30000)) { throw "Guarda y cierra Obsidian para terminar la instalación" } }'
        closed = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', code], env=env, capture_output=True, text=True, timeout=45)
        require(closed.returncode == 0, 'Obsidian no terminó su cierre normal. El agente debe resolver el aviso de guardado antes de continuar.')
        identity = register_vault(profile, vault)
        log = target / '.installer/obsidian-start.log'
        with log.open('ab') as output:
            subprocess.Popen([str(executable), '--user-data-dir=' + str(profile)], stdout=output, stderr=output)
    else:
        config = read_json(profile / 'obsidian.json')
        identities = [key for key, value in config.get('vaults', {}).items() if Path(value.get('path', '')) == vault]
        require(len(identities) == 1, 'No se encontró el registro de la bóveda instalada.')
        identity = identities[0]
        write_json(target / '.installer/previous-installation-result.json', prior)
        write_json(target / RESULT, {**prior, 'status': 'checking', 'previousStatus': 'complete'})

    def command(*parts, limit=30):
        completed = subprocess.run([str(cli), 'vault=' + identity, *parts], cwd=vault, stdin=subprocess.DEVNULL,
                                   capture_output=True, text=True, encoding='utf-8', timeout=limit)
        output = completed.stdout.strip()
        require(completed.returncode == 0 and not output.startswith('Error:'), 'Obsidian no pudo ejecutar ' + parts[0] + ': ' + output[:400])
        return output

    def evaluate(code):
        output = command('eval', 'code=' + code, limit=15)
        require(output.startswith('=> '), 'Obsidian todavía no devolvió el resultado solicitado.')
        return output[3:]

    # El transportista siempre selecciona el ID; comprobar también la carpeta real.
    frame = wait_for_renderer(evaluate, str(vault), identity)
    if not resuming:
        if evaluate('localStorage.getItem("language")') != 'es':
            evaluate('(localStorage.setItem("language", "es"), true)')
            command('reload')
            frame = wait_for_renderer(evaluate, str(vault), identity, after=frame['generation'])
        install_plugins(target)
        evaluate('(async()=>{await app.plugins.loadManifests();return true})()')
        if evaluate('app.plugins.isEnabled()') != 'true':
            command('plugins:restrict', 'off')
            frame = wait_for_renderer(evaluate, str(vault), identity, after=frame['generation'])
            evaluate('(async()=>{await app.plugins.loadManifests();return true})()')
        for plugin in ('realclaudian', 'obsidian-kanban'):
            command('plugin:enable', 'id=' + plugin)
    expression = '(async()=>{if(app.vault.adapter.basePath!==' + json.dumps(str(vault)) + ')throw Error("Bóveda incorrecta");return JSON.stringify(await require(' + json.dumps(str(target / 'installation/start.js')) + ')(app,require("obsidian").apiVersion))})()'
    output = command('eval', 'code=' + expression, limit=timeout)
    require(output.startswith('=> '), 'No se recibió el resultado de la preparación dentro de Obsidian.')
    result = read_json(target / RESULT)
    require(result.get('status') == 'complete', result.get('message', 'La preparación todavía no terminó.'))
    return result
