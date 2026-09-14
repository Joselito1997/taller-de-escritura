"""Contratos de documentos españoles. Valida sin reescribir los bytes."""
import datetime as dt
import hashlib
import re
import uuid

import yaml

STAGES = {'setup', 'import', 'reconstruct', 'assess', 'revise-existing', 'continue', 'finished'}
BOARD_STATES = dict(zip(('Por hacer', 'En curso', 'Esperando al autor', 'En espera de otra tarea', 'Para después', 'Terminado'), ('up-next', 'in-progress', 'awaiting-author', 'waiting', 'later', 'done')))
LOG_HEADINGS = ('Resumen', 'Trabajo realizado', 'Cambios y motivos', 'Aceptado por el autor', 'Alternativas', 'Registros actualizados', 'Pendientes', 'Etapa y aceptación', 'Próximo paso', 'Notas del autor', 'Puntos de guardado')
PATH_MAP = {'book': 'libro', 'index.md': 'inicio.md', 'status.md': 'estado.md', 'creative-direction.md': 'direccion-creativa.md', 'revision-backlog.md': 'trabajo-pendiente.md', 'manuscript': 'manuscrito', 'story': 'historia', 'characters': 'personajes', 'relationships': 'relaciones', 'locations': 'lugares', 'factions': 'facciones', 'world-rules.md': 'reglas-del-mundo.md', 'timeline.md': 'cronologia.md', 'plans': 'planes', 'alternatives': 'alternativas', 'logs': 'bitacora', 'imports': 'importaciones', 'inventory.md': 'inventario.md', 'research': 'investigacion', 'sources': 'fuentes', 'topics': 'temas', 'briefs': 'informes', 'originals': 'originales', 'derived': 'derivados', 'exports': 'exportaciones'}
TYPES = {'status', 'creative-direction', 'chapter', 'character', 'relationship', 'location', 'faction', 'world-rule', 'timeline-event', 'plan', 'alternative', 'finding', 'source', 'topic', 'research-brief', 'import-inventory', 'session-log', 'index'}
KNOWN_FIELDS = {'index_kind', 'schema_version', 'id', 'type', 'tags', 'aliases', 'title', 'name', 'subject', 'scope', 'language', 'narrative_choices', 'stage', 'focus', 'active_log', 'next_action', 'role', 'started', 'closed', 'status', 'previous', 'workflows', 'targets', 'stage_at_start', 'stage_at_close', 'acceptances', 'participants', 'story_date', 'precision', 'order_before', 'order_after', 'decision_status', 'target', 'selection_status', 'based_on', 'applied_to', 'kind', 'severity', 'board_task_id', 'author', 'URL', 'url', 'publication_date', 'captured_at', 'source_kind', 'original', 'coverage', 'sha256', 'reuse_status', 'sources', 'question', 'limits', 'entries', 'basis', 'provenance', 'as_of', 'disposition', 'depends_on', 'predecessors'}
HASH = re.compile(r'^[0-9a-f]{64}$')
KANBAN_SETTINGS = re.compile(r'%% kanban:settings\s*```(?:json)?\s*(.*?)\s*```\s*%%', re.S)
BLOCK = re.compile(r'\^((?:sc-|task-|claim-)[A-Za-z0-9-]+)(?=\s|$)')

class Problem(Exception):
    def __init__(self, code, message, artifacts=None):
        self.code, self.message, self.artifacts = code, message, artifacts or []
        super().__init__(message)


def require(condition, message, code='validation-failed'):
    if not condition:
        raise Problem(code, message)


def reading_order(body):
    """Rutas del Orden de lectura en su orden exacto; viñetas (-, * o +) o números (1. o 1)) con enlace al inicio."""
    require('## Orden de lectura' in body.splitlines(), 'Falta Orden de lectura.')
    section = body.split('## Orden de lectura', 1)[1].split('\n## ', 1)[0]
    order = []
    for line in section.splitlines():
        item = re.match(r'\s*(?:[-*+]|\d+[.)])\s+(.*)', line)
        if item:
            link = re.match(r'\[\[([^\]|#]+)(?:\|[^\]]+)?\]\]', item[1])
            require(link, 'El orden de lectura contiene una entrada que no es un enlace a capítulo compatible.')
            order.append(link[1] if link[1].endswith('.md') else link[1] + '.md')
    return order


class UniqueLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        require(isinstance(key, str), 'Las claves YAML deben ser texto.')
        require(key not in result, f'Clave YAML duplicada: {key}.')
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def frontmatter(data):
    try:
        text = data.decode('utf-8')
        lines = text.splitlines(keepends=True)
        require(lines and lines[0].strip() == '---', 'Falta la cabecera YAML.', 'unsupported-format')
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == '---')
        meta = yaml.load(''.join(lines[1:end]), Loader=UniqueLoader)
        require(isinstance(meta, dict), 'La cabecera debe ser un objeto.')
        return meta, ''.join(lines[end + 1:])
    except (UnicodeError, StopIteration, yaml.YAMLError) as exc:
        raise Problem('validation-failed', 'No se puede leer la cabecera UTF-8/YAML.') from exc


def timestamp(value):
    if isinstance(value, dt.datetime):
        return value.tzinfo is not None
    if not isinstance(value, str):
        return False
    try:
        return dt.datetime.fromisoformat(value.replace('Z', '+00:00')).tzinfo is not None
    except ValueError:
        return False


def acceptance_hash(data):
    """Solo normaliza saltos y excluye cabecera e identificadores del sistema."""
    _, body = frontmatter(data)
    body = BLOCK.sub('', body.replace('\r\n', '\n').replace('\r', '\n'))
    return hashlib.sha256(body.encode()).hexdigest()


def validate(data, declared=None):
    meta, body = frontmatter(data)
    if meta.get('kanban-plugin') == 'board':
        detected = 'kanban'
    else:
        require(type(meta.get('schema_version')) is int and meta['schema_version'] == 1, 'Versión de esquema no compatible.', 'unsupported-schema')
        require(isinstance(meta.get('id'), str) and bool(meta['id']), 'Falta una identidad de documento.')
        require(isinstance(meta.get('type'), str) and meta['type'] in TYPES, 'Tipo de documento no compatible.', 'unsupported-schema')
        detected = {'chapter': 'chapter', 'index': 'index', 'session-log': 'session-log'}.get(meta['type'], 'record')
    require(declared is None or declared == detected, 'El formato declarado no coincide con el documento.', 'unsupported-format')
    ids = BLOCK.findall(body)
    require(len(ids) == len(set(ids)), 'Hay identificadores de bloque duplicados.')
    for block in ids:
        if block.startswith(('sc-', 'task-')):
            try:
                parsed = uuid.UUID(block.split('-', 1)[1])
                require(parsed.version == 4 and str(parsed) == block.split('-', 1)[1], 'El bloque requiere UUID4 canónico.')
            except ValueError as exc:
                raise Problem('validation-failed', 'Identificador de bloque inválido.') from exc
    for key in ('tags', 'aliases', 'workflows', 'targets', 'participants', 'sources', 'depends_on', 'order_before', 'order_after'):
        if key in meta and meta[key] is not None:
            require(isinstance(meta[key], list) and all(isinstance(v, str) for v in meta[key]), f'{key} debe ser una lista de textos.')
    for key in ('title', 'name', 'subject', 'next_action', 'language', 'focus', 'active_log', 'previous', 'target', 'board_task_id', 'URL', 'url', 'original', 'reuse_status'):
        if key in meta and meta[key] is not None:
            require(isinstance(meta[key], str), f'{key} debe ser texto.')
    for key in ('started', 'closed', 'captured_at'):
        if meta.get(key) is not None:
            require(timestamp(meta[key]), f'{key} necesita fecha y hora con zona.')
    enums = {'stage': STAGES, 'stage_at_start': STAGES, 'stage_at_close': STAGES, 'decision_status': {'proposed', 'accepted', 'rejected', 'superseded'}, 'selection_status': {'proposed', 'selected', 'rejected', 'superseded'}, 'severity': {'blocker', 'major', 'minor'}, 'coverage': {'complete', 'partial', 'unavailable'}, 'basis': {'working-text', 'author-decision', 'planned', 'interpretation', 'unresolved', 'superseded'}, 'provenance': {'imported', 'ai-draft-unreviewed', 'author-edited'}}
    for key, values in enums.items():
        if meta.get(key) is not None:
            require(isinstance(meta[key], str) and meta[key] in values, f'Valor no compatible en {key}.')
    if meta.get('sha256') is not None:
        require(isinstance(meta['sha256'], str) and HASH.fullmatch(meta['sha256']), 'Hash de fuente inválido.')
    if detected == 'chapter':
        require(re.fullmatch(r'ch-\d{3,}', meta['id']), 'El capítulo requiere una identidad ch-NNN.')
        require(isinstance(meta.get('title'), str), 'El capítulo necesita título, aunque esté vacío.')
    elif detected == 'index':
        require(meta.get('index_kind', 'manuscript') in ('navigation', 'manuscript'), 'Clase de índice no compatible.')
        if meta.get('index_kind', 'manuscript') == 'manuscript':
            order = reading_order(body)
            require(len(order) == len(set(order)), 'El orden de lectura repite capítulos.')
    elif detected == 'session-log':
        fields = {'role', 'started', 'closed', 'status', 'previous', 'workflows', 'targets', 'stage_at_start', 'stage_at_close'}
        require(fields <= meta.keys(), 'La bitácora no contiene todos los campos obligatorios.')
        require(meta['role'] in ('primary', 'isolated-review') and meta['status'] in ('open', 'closed', 'interrupted', 'recovered'), 'Rol o estado de bitácora inválido.')
        require(all('## ' + heading in body.splitlines() for heading in LOG_HEADINGS), 'Falta una sección obligatoria de la bitácora.')
        require(isinstance(meta.get('acceptances', []), list), 'Las aceptaciones deben ser una lista.')
        for entry in meta.get('acceptances', []):
            require(isinstance(entry, dict) and {'target', 'sha256', 'author_statement', 'timestamp'} <= entry.keys(), 'Aceptación sin versión o declaración del autor.')
            require(all(isinstance(entry[k], str) and entry[k] for k in ('target', 'sha256', 'author_statement')), 'Aceptación inválida.')
            require(HASH.fullmatch(entry['sha256']) and timestamp(entry['timestamp']), 'Hash o fecha de aceptación inválidos.')
    elif detected == 'kanban':
        import json
        require(all('## ' + heading.casefold() in body.casefold().splitlines() for heading in BOARD_STATES), 'Faltan columnas del tablero español.')
        match = KANBAN_SETTINGS.search(body)
        require(match is not None, 'Falta la configuración del tablero.', 'unsupported-format')
        try:
            settings = json.loads(match[1])
        except ValueError as exc:
            raise Problem('unsupported-format', 'Configuración del tablero ilegible.') from exc
        require(isinstance(settings, dict) and settings.get('max-archive-size') == -1, 'El archivo del tablero debe conservar todas las tarjetas.')
    return {'format': detected, 'metadata': meta, 'body': body, 'ids': ids}


def scene_locators(data, path):
    """Localizadores de escenas existentes; nunca inventa anclas eliminadas."""
    document = validate(data, 'chapter')
    body = document['body']
    offset = len(data) - len(body.encode())
    boundaries = [m.start() for m in re.finditer(r'(?m)^(?:#{1,6} .+|\* \* \*)\r?$', body)]
    boundaries = sorted(set([0, *boundaries, len(body)]))
    locators = []
    for left, right in zip(boundaries, boundaries[1:]):
        text = body[left:right]
        scene_ids = [value for value in BLOCK.findall(text) if value.startswith('sc-')]
        if not scene_ids:
            continue
        require(len(scene_ids) == 1, 'Una escena contiene varias anclas; resuelva sus límites.')
        paragraphs = re.split(r'\r?\n\s*\r?\n', text.strip())
        prose = next((p for p in paragraphs if not p.startswith('#') and p != '* * *'), '')
        require('^' + scene_ids[0] in prose, 'El ancla debe estar en el primer párrafo de la escena.')
        start, end = offset + len(body[:left].encode()), offset + len(body[:right].encode())
        locators.append(dict(path=path, scene_id=scene_ids[0], heading=text.splitlines()[0] if text.startswith('#') else '', start=start, end=end, sha256=hashlib.sha256(data[start:end]).hexdigest(), quote=BLOCK.sub('', prose)[:120]))
    return locators


def validate_locator(locator):
    require(isinstance(locator, dict) and {'path', 'start', 'end', 'sha256', 'quote'} <= locator.keys(), 'Localizador de fuente incompleto.')
    require(isinstance(locator['path'], str) and isinstance(locator['quote'], str) and locator['quote'], 'Ruta o cita de localizador inválida.')
    require(type(locator['start']) is int and type(locator['end']) is int and 0 <= locator['start'] < locator['end'], 'Intervalo de localizador inválido.')
    require(isinstance(locator['sha256'], str) and HASH.fullmatch(locator['sha256']), 'Hash de localizador inválido.')
    if 'scene_id' in locator:
        require(isinstance(locator['scene_id'], str) and locator['scene_id'].startswith('sc-'), 'Ancla de escena inválida.')


def acceptance_state(data, accepted_hash):
    require(isinstance(accepted_hash, str) and HASH.fullmatch(accepted_hash), 'Hash de aceptación inválido.')
    return 'accepted' if acceptance_hash(data) == accepted_hash else 'accepted-version-edited'
