"""Solo admite el helper instalado y JSON literal por stdin, sin shell general."""
import json
from pathlib import Path
import re
import shlex
import sys

POWERSHELL_UTF8 = '$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new();\n'

def powershell_prefix(python, script, vault):
    return '& ' + ' '.join("'" + value.replace("'", "''") + "'" for value in (python, script, '--vault', vault))


def allowed_powershell(command, python, script, vault):
    if not isinstance(command, str):
        return False
    command = command.replace('\r\n', '\n')
    if not command.startswith(POWERSHELL_UTF8):
        return False
    command = command[len(POWERSHELL_UTF8):]
    prefix = powershell_prefix(python, script, vault)
    if command in (prefix + ' ' + operation for operation in ('readiness', 'check', 'recover')):
        return True
    match = re.fullmatch(r"@'\n(.*)\n'@ \| " + re.escape(prefix) + r" (check|snapshot|apply|diff|restore|recover|import|export) --manifest -", command, re.S)
    if not match or any(line.startswith("'@") for line in match[1].splitlines()):
        return False
    try:
        return isinstance(json.loads(match[1]), dict)
    except ValueError:
        return False


def allowed(command, python, script, vault):
    if not isinstance(command, str):
        return False
    header = command
    if '\n' in command:
        match = re.fullmatch(r"([^\n]+) <<'BOOK_JSON'\n(.*)\nBOOK_JSON\n?", command, re.S)
        if not match:
            return False
        header = match[1]
        try:
            if not isinstance(json.loads(match[2]), dict):
                return False
        except ValueError:
            return False
    try:
        tokens = shlex.split(header)
    except ValueError:
        return False
    base = [python, script, '--vault', vault]
    if tokens[:4] != base or len(tokens) not in (5, 7):
        return False
    if tokens[4] not in ('check', 'readiness', 'snapshot', 'apply', 'diff', 'restore', 'recover', 'import', 'export'):
        return False
    if len(tokens) == 7 and tokens[5:] != ['--manifest', '-']:
        return False
    # readiness no lleva JSON: sin hooks, Claude Code bloquea por sí mismo los heredocs con llaves y comillas.
    return ('\n' not in command and len(tokens) == 5 and tokens[4] in ('check', 'recover', 'readiness')) or ('\n' in command and len(tokens) == 7 and tokens[4] != 'readiness')


def main():
    vault = str(Path(__file__).resolve().parents[2])
    script = str(Path(vault) / '.claude/scripts/book.py')
    try:
        event = json.load(sys.stdin)
        if sys.platform == 'win32':
            permit = event.get('tool_name') == 'PowerShell' and allowed_powershell(event.get('tool_input', {}).get('command'), sys.executable, script, vault)
        else:
            permit = event.get('tool_name') == 'Bash' and allowed(event.get('tool_input', {}).get('command'), sys.executable, script, vault)
    except (ValueError, TypeError, AttributeError):
        permit = False
    print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'allow' if permit else 'deny', 'permissionDecisionReason': 'Use únicamente el helper de esta bóveda con un manifiesto JSON literal; no se permite escritura directa ni shell general.'}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
