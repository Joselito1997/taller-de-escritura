"""Importación acotada y exportación sobre copias inmutables."""
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import uuid
import zipfile
from html.parser import HTMLParser

from schemas import Problem, require, BLOCK, validate, acceptance_hash, timestamp, reading_order
from book import Book, encoded, parse_json, result, sha

from maintenance import sealed, checked

VERSION = 'writing-converters-1'
MAX_BYTES = 100 * 1024 * 1024


class InertHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.output = []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'iframe', 'object'):
            self.hidden += 1
        elif tag in ('p', 'div', 'br', 'h1', 'h2', 'h3', 'li') and not self.hidden:
            self.output.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'iframe', 'object'):
            self.hidden = max(0, self.hidden - 1)
        elif tag in ('p', 'div', 'li') and not self.hidden:
            self.output.append('\n')

    def handle_data(self, data):
        if not self.hidden:
            self.output.append(data)


def conversations(data, selected):
    document = parse_json(data)
    require(isinstance(document, dict) and document.get('format') == 'writing-conversation-v1', 'Esquema de conversación no reconocido; conserve el original y use writing-conversation-v1 o texto legible.', 'unsupported-schema')
    messages = document.get('messages')
    require(isinstance(messages, list), 'La conversación debe contener messages.', 'invalid-input')
    units, ids = [], set()
    for i, message in enumerate(messages):
        require(isinstance(message, dict) and isinstance(message.get('id'), str) and message['id'] and message['id'] not in ids, 'Identificador de mensaje inválido o duplicado.', 'invalid-input')
        ids.add(message['id'])
        require(message.get('role') in ('human', 'assistant') and isinstance(message.get('text'), str), 'Rol o texto de mensaje inválidos.', 'invalid-input')
        require(isinstance(message.get('attachment_paths', []), list) and all(isinstance(p, str) for p in message.get('attachment_paths', [])), 'Rutas de adjuntos inválidas.', 'invalid-input')
        require(message.get('timestamp') is None or timestamp(message['timestamp']), 'La fecha del mensaje debe incluir zona o ser null.', 'invalid-input')
        units.append(dict(id=message['id'], kind='message', text=message['text'], source_role=message['role'], timestamp=message.get('timestamp'), attachment_paths=message.get('attachment_paths', []), order=i))
    return units


def convert(path, kind):
    data = path.read_bytes()
    require(len(data) <= MAX_BYTES, 'El original supera 100 MB.', 'invalid-input')
    warnings = []
    details = {'tool': 'stdlib', 'python': sys.version.split()[0], 'format': kind, 'options': []}
    if kind in ('txt', 'md'):
        units = [dict(id='text-1', kind='text', text=data.decode('utf-8'))]
    elif kind in ('html', 'htm'):
        parser = InertHTML()
        parser.feed(data.decode('utf-8'))
        units = [dict(id='html-1', kind='text', text=''.join(parser.output))]
        warnings = ['HTML convertido sin scripts, estilos ni recursos enlazados; revise imágenes y tablas en el original.']
    elif kind == 'json':
        units = conversations(data, None)
    elif kind == 'pdf':
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise Problem('missing-dependency', 'Falta pypdf en el entorno; instale las dependencias fijadas para leer PDF.') from exc
        import importlib.metadata
        details = {'tool':'pypdf','version':importlib.metadata.version('pypdf'),'options':['extract_text']}
        reader = PdfReader(io.BytesIO(data))
        require(not reader.is_encrypted, 'PDF cifrado no compatible; proporcione una copia legible.', 'unsupported-format')
        require(len(reader.pages) > 0, 'El PDF no contiene páginas legibles.', 'unsupported-format')
        units = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ''
            units.append(dict(id=f'page-{i + 1}', page=i + 1, kind='page', text=text, status='complete' if text.strip() else 'needs-ocr'))
        warnings = ['La extracción PDF no prueba fidelidad de imágenes, tablas ni orden visual; revise el original.']
    elif kind == 'docx':
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            require(sum(info.file_size for info in archive.infolist()) <= MAX_BYTES, 'El DOCX expandido supera 100 MB.', 'invalid-input')
            require('word/document.xml' in archive.namelist(), 'DOCX sin documento principal.', 'unsupported-format')
        try:
            run = subprocess.run(['pandoc', '--sandbox', '--from=docx', '--to=markdown', '--wrap=none', str(path)], capture_output=True, timeout=60)
        except FileNotFoundError as exc:
            raise Problem('missing-dependency', 'Falta Pandoc; instálelo para convertir DOCX.') from exc
        require(run.returncode == 0, 'Pandoc no pudo leer el DOCX; conserve el original.', 'unsupported-format')
        details = {'tool':'pandoc','version':subprocess.check_output(['pandoc','--version'],text=True).splitlines()[0],'options':['--sandbox','--from=docx','--to=markdown','--wrap=none']}
        units = [dict(id='docx-1', kind='text', text=run.stdout.decode())]
        warnings = ['Revise imágenes, tablas, notas y cambios controlados en el DOCX original.']
    else:
        raise Problem('unsupported-format', 'Formato no compatible; conserve el original y proporcione TXT, Markdown, HTML, DOCX, PDF legible o JSON acordado.')
    require(sum(len(u['text'].encode()) for u in units) <= MAX_BYTES, 'El texto extraído supera el límite; procese una fuente menor.', 'invalid-input')
    return dict(units=units, warnings=warnings, converter_version=VERSION, conversion_details=details)


def bounded_units(units):
    output = []
    for unit in units:
        words = list(re.finditer(r'\S+', unit['text']))
        boundaries = [0] + [words[i].start() for i in range(8000, len(words), 8000)] + [len(unit['text'])]
        for i, (start, end) in enumerate(zip(boundaries, boundaries[1:])):
            output.append({**unit, 'id': unit['id'] + (f'-part-{i + 1}' if len(boundaries) > 2 else ''), 'text': unit['text'][start:end], 'character_start': start, 'character_end': end})
    return output


def conversion_process(path, kind):
    try:
        run = subprocess.run([sys.executable, str(Path(__file__).resolve()), '_convert', str(path), kind], capture_output=True, timeout=60)
    except subprocess.TimeoutExpired as exc:
        raise Problem('partial-save', 'La conversión excedió 60 segundos; el original permanece conservado.') from exc
    try:
        payload = parse_json(run.stdout)
    except Problem as exc:
        raise Problem('unsupported-format', 'El conversor no pudo producir una extracción legible.') from exc
    if not payload.get('ok'):
        raise Problem(payload.get('code', 'unsupported-format'), payload.get('message', 'No se pudo convertir el original.'))
    return payload['conversion']


def original(book, input_root, relative):
    source = Book(input_root)
    require(source.path(relative).stat().st_size <= MAX_BYTES, 'El original supera 100 MB.', 'invalid-input')
    data = source.read(relative, max_bytes=MAX_BYTES)
    require(data is not None and len(data) <= MAX_BYTES, 'La fuente falta o supera 100 MB.', 'source-unavailable')
    name = re.sub(r'[^\w .-]', '_', Path(relative).name).lstrip('.') or 'original'
    digest = sha(data)
    destination = f'importaciones/originales/{digest}/{name}'
    for area in ('importaciones', 'investigacion'):
        directory = book.path(f'{area}/originales/{digest}')
        if directory.exists():
            matches = list(directory.iterdir())
            require(len(matches) == 1 and matches[0].is_file(), 'El almacén de originales es ambiguo.', 'invalid-input')
            destination = matches[0].relative_to(book.root).as_posix()
            break
    existing = book.read(destination)
    require(existing is None or existing == data, 'El original conservado está alterado.', 'invalid-input')
    if existing is None:
        book.durable(destination, data, exclusive=True)
    require(source.read(relative, max_bytes=MAX_BYTES) == data, 'La fuente cambió mientras se conservaba; seleccione su versión exacta.', 'stale-base')
    return dict(original_name=relative, preserved_path=destination, sha256=digest, bytes=len(data), format=Path(relative).suffix.lower().lstrip('.'))


def import_material(book, manifest):
    operation = book.manifest(manifest)
    if manifest.get('kind') == 'research':
        import research
        return research.execute(book, manifest)
    require(set(manifest) <= {'schema_version','operation_id','input_root','files','target_map','kind','authorized_scope'}, 'El manifiesto de importación contiene campos no admitidos.', 'invalid-input')
    root = manifest.get('input_root')
    files = manifest.get('files')
    require(isinstance(root, str) and isinstance(files, list) and files and len(files) <= 100 and all(isinstance(p, str) for p in files), 'Indique input_root y hasta 100 archivos seleccionados.', 'invalid-input')
    require(Path(root).is_absolute(), 'Seleccione una carpeta local absoluta de entrada.', 'invalid-input')
    require(isinstance(manifest.get('target_map', {}), dict), 'target_map debe ser un objeto.', 'invalid-input')
    request_hash = sha(encoded(manifest))
    ledger_path = f'.writing/imports/{operation}.json'
    with book.lock(operation):
        previous = book.read(ledger_path)
        if previous:
            ledger = checked(previous)
            require(isinstance(ledger, dict) and ledger.get('request_sha256') == request_hash, 'La operación de importación ya pertenece a otra solicitud.', 'invalid-input')
            require(isinstance(ledger.get('sources'), list) and isinstance(ledger.get('candidates'), list) and isinstance(ledger.get('completed_units'), list), 'El inventario de importación está dañado.', 'invalid-input')
            for candidate in ledger['candidates']:
                require(candidate['candidate_path'].startswith(f'.writing/candidates/{operation}-') and sha(book.read(candidate['candidate_path'])) == candidate['candidate_sha256'], 'El candidato importado ya no coincide con el registro.', 'invalid-input')
            for entry in ledger.get('sources', []):
                require(entry['preserved_path'].startswith((f"importaciones/originales/{entry['sha256']}/", f"investigacion/originales/{entry['sha256']}/")), 'Ruta original de importación inválida.', 'invalid-input')
                require(sha(book.read(entry['preserved_path'])) == entry['sha256'], 'El original conservado cambió.', 'invalid-input')
        else:
            ledger = dict(request_sha256=request_hash, request=manifest, sources=[], failures=[], completed_units=[], candidates=[])
            book.durable(ledger_path, sealed(ledger), exclusive=True)
        for relative in files:
            if any(item['original_name'] == relative for item in ledger['sources']):
                # Cambiar bytes bajo el mismo operation_id nunca selecciona una versión nueva.
                entry = next(e for e in ledger['sources'] if e['original_name'] == relative)
                try:
                    external = Book(root).read(relative, max_bytes=MAX_BYTES)
                except (Problem, OSError):
                    external = None
                require(external is None or sha(external) == entry['sha256'], 'La fuente cambió; use una nueva operación para conservar otra versión.', 'stale-base')
                continue
            try:
                entry = original(book, root, relative)
                ledger['sources'].append(entry)
            except (Problem, OSError) as exc:
                failure = dict(original_name=relative, code=exc.code if isinstance(exc, Problem) else 'source-unavailable', message=exc.message if isinstance(exc, Problem) else 'No se pudo conservar esta fuente.')
                if failure not in ledger['failures']:
                    ledger['failures'].append(failure)
            book.durable(ledger_path, sealed(ledger))
    proposals, total_words, pages, messages = [], 0, 0, 0
    for entry in ledger['sources']:
        try:
            conversion = conversion_process(book.path(entry['preserved_path']), entry['format'])
            if 'conversion_details' in entry:
                require(entry['conversion_details'] == conversion['conversion_details'], 'El conversor cambió entre lotes; conserve la extracción anterior y use una operación nueva.', 'stale-base')
            else:
                entry['conversion_details'] = conversion['conversion_details']
                with book.lock(operation):
                    book.durable(ledger_path, sealed(ledger))
            units = bounded_units(conversion['units'])
            for unit in units:
                key = entry['sha256'] + ':' + unit['id']
                if key in ledger['completed_units']:
                    continue
                words = len(re.findall(r'\S+', unit['text']))
                if total_words + words > 8000 or pages + (unit['kind'] == 'page') > 20 or messages + (unit['kind'] == 'message') > 100:
                    return result('import-partial', 'El lote alcanzó su límite; repita la misma solicitud para continuar por unidades conservadas.', [ledger_path], ledger=ledger)
                attachments = []
                for attachment in unit.get('attachment_paths', []):
                    with book.lock(operation):
                        attachments.append(original(book, root, attachment))
                if unit.get('status') == 'needs-ocr':
                    ledger['failures'].append(dict(source=entry['sha256'], unit=unit['id'], code='needs-ocr', message='Página sin texto; OCR no disponible.'))
                import yaml
                metadata = dict(schema_version=1, id='derived-' + sha(key.encode())[:24], type='source', title=entry['original_name'], original='[[' + entry['preserved_path'] + ']]', sha256=entry['sha256'], coverage='partial' if conversion['warnings'] or unit.get('status') == 'needs-ocr' else 'complete', provenance='imported', source_role=unit.get('source_role'), content_role='imported-ai-candidate-unreviewed' if unit.get('source_role') == 'assistant' else 'unclassified-human-input' if unit.get('source_role') == 'human' else 'supplied-text-unreviewed', source_timestamp=unit.get('timestamp'), source_unit=unit['id'], conversion_version=VERSION, conversion_details=conversion['conversion_details'])
                text = '---\n' + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) + '---\n' + unit['text']
                candidate = f'.writing/candidates/{operation}-{sha(key.encode())[:16]}.md'
                with book.lock(operation):
                    existing = book.read(candidate)
                    require(existing is None or existing == text.encode(), 'El candidato importado cambió.', 'invalid-input')
                    if existing is None:
                        book.durable(candidate, text.encode(), exclusive=True)
                    area = 'investigacion' if entry['preserved_path'].startswith('investigacion/') else 'importaciones'
                    item = dict(target=f"{area}/derivados/{entry['sha256']}/{VERSION}/{sha(key.encode())[:16]}.md", expected_file_sha256=None, candidate_path=candidate, candidate_sha256=sha(text.encode()), format='record', source_sha256=entry['sha256'], unit=unit['id'], coverage_unit={key:unit[key] for key in ('kind','page','order','character_start','character_end','source_role','timestamp') if key in unit}, span_sha256=sha(unit['text'].encode()), attachments=attachments, warnings=conversion['warnings'])
                    target_map = manifest.get('target_map', {})
                    require(isinstance(target_map, dict), 'target_map debe ser un mapa de archivos a destinos.', 'invalid-input')
                    proposed_target = target_map.get(entry['original_name'])
                    if proposed_target is not None:
                        book.path(proposed_target, shared=True)
                        item['proposed_target'] = proposed_target
                        group_path = '.writing/import-targets/' + sha(proposed_target.encode()) + '.json'
                        group_raw = book.read(group_path)
                        group = checked(group_raw) if group_raw else dict(target=proposed_target, candidates=[])
                        reference = dict(operation_id=operation, source_sha256=entry['sha256'], unit=unit['id'], candidate_path=candidate, candidate_sha256=item['candidate_sha256'])
                        if reference not in group['candidates']:
                            group['candidates'].append(reference)
                        book.durable(group_path, sealed(group))
                    ledger['candidates'].append(item)
                    ledger['completed_units'].append(key)
                    book.durable(ledger_path, sealed(ledger))
                proposals.append(item)
                total_words += words
                pages += unit['kind'] == 'page'
                messages += unit['kind'] == 'message'
        except (Problem, UnicodeError, OSError) as exc:
            failure = dict(source=entry['sha256'], code=exc.code if isinstance(exc, Problem) else 'unsupported-format', message=exc.message if isinstance(exc, Problem) else 'No se pudo leer esta fuente; el original permanece conservado.')
            if failure not in ledger['failures']:
                ledger['failures'].append(failure)
            with book.lock(operation):
                book.durable(ledger_path, sealed(ledger))
    return result('imported-candidates' if ledger['candidates'] else 'import-partial', 'Se conservaron originales y propuestas; la reconstrucción y aceptación corresponden al autor.' if ledger['candidates'] else 'Revise las fuentes pendientes; no se obtuvo una propuesta legible.', [ledger_path] + [c['candidate_path'] for c in ledger['candidates']], ledger=ledger, coverage='partial' if ledger['failures'] else 'complete', ok=bool(ledger['sources']))


EXPORT_OPTIONS = ('docx', 'numbering', 'contents', 'preliminaries')
PRELIMINARIES = 'manuscrito/preliminares.md'


def export_material(book, manifest):
    operation = book.manifest(manifest)
    unknown = sorted(set(manifest) - {'schema_version', 'operation_id', 'targets', 'title', 'author', *EXPORT_OPTIONS})
    require(not unknown, 'La exportación no admite estas claves: ' + ', '.join(unknown) + '.', 'invalid-input')
    options = {key: manifest.get(key, key == 'docx') for key in EXPORT_OPTIONS}
    require(all(type(value) is bool for value in options.values()), 'docx, numbering, contents y preliminaries deben ser true o false.', 'invalid-input')
    requested = manifest.get('targets')
    index = book.read('manuscrito/indice.md', shared=True)
    require(index is not None, 'Falta el índice del manuscrito.', 'source-unavailable')
    validate(index, 'index')
    order = reading_order(validate(index)['body'])
    require(order and len(order) == len(set(order)), 'El orden de lectura está vacío o contiene duplicados.', 'invalid-input')
    require(requested is None or isinstance(requested, list) and requested and len(requested) == len(set(requested)) and all(p in order for p in requested), 'La selección debe pertenecer al orden de lectura.', 'invalid-input')
    selected = [p for p in order if requested is None or p in requested]
    if options['preliminaries']:
        require(PRELIMINARIES not in order, 'Los preliminares no pertenecen al orden de lectura; quítelos del índice para seleccionarlos aparte.', 'invalid-input')
        require(book.read(PRELIMINARIES, shared=True) is not None, 'Falta manuscrito/preliminares.md; créelo o no pida preliminares.', 'source-unavailable')
        selected = [PRELIMINARIES, *selected]
    from datetime import datetime, timezone
    directory = f"exportaciones/{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{operation}"
    with book.lock(operation):
        require(book.read(f'.writing/exports/{operation}.json') is None, 'Esta operación de exportación ya tiene un intento conservado.', 'invalid-input')
        book.durable(f'.writing/exports/{operation}.json', sealed(dict(directory=directory, request_sha256=sha(encoded(manifest)))), exclusive=True)
        require(not book.path(directory).exists(), 'La exportación ya existe; no se reemplaza.', 'invalid-input')
        book.new_directory(directory)
        book.check({'targets':['manuscrito/indice.md', *selected]})
        entries, bodies, contents = [], [], []
        for i, target in enumerate(selected):
            chapter = target != PRELIMINARIES
            require(target.startswith('manuscrito/'), 'El índice incluye contenido ajeno al manuscrito.', 'path-outside-scope')
            data = book.read(target, shared=True)
            require(data is not None, f'Falta el capítulo {target}.', 'source-unavailable')
            doc = validate(data, 'chapter')
            body = doc['body']
            require('[[' not in body and '<!--' not in body and '%%' not in body, f'Hay notas o enlaces ambiguos en {target}; resuélvalos antes de exportar.', 'validation-failed')
            require(not re.search(r'!\[[^\]]*\]\(', body), f'Hay imágenes en {target}; revise su exportación de forma explícita.', 'validation-failed')
            require(not re.search(r'<[^>]+>', body), f'Hay contenido HTML ambiguo en {target}; revise su representación antes de exportar.', 'validation-failed')
            body = BLOCK.sub('', body)
            if chapter and doc['metadata'].get('title') and not re.match(r'^\s*# ', body):
                body = '# ' + doc['metadata']['title'] + '\n\n' + body
            book.durable(f'{directory}/inputs/{i}.md', data, exclusive=True)
            accepted = []
            for log in book.content_paths():
                if log.startswith('bitacora/'):
                    for acceptance in validate(book.read(log))['metadata'].get('acceptances', []):
                        # Mismo enlace que check/read_reference; un ancla o tramo no acepta el capítulo entero.
                        reference = acceptance['target'][2:-2].split('|')[0] if acceptance['target'].startswith('[[') and acceptance['target'].endswith(']]') else acceptance['target']
                        if '#' not in reference and (reference if PurePosixPath(reference).suffix else reference + '.md') == target and 'start' not in acceptance:
                            accepted.append(acceptance['sha256'])
            status = 'accepted' if acceptance_hash(data) in accepted else 'accepted-version-edited' if accepted else 'unreviewed'
            position = order.index(target) + 1 if chapter else None
            entries.append(dict(path=target, role='chapter' if chapter else 'preliminaries', position=position, sha256=sha(data), prose_sha256=acceptance_hash(data), words=len(re.findall(r'\S+', body)), status=status))
            # Numeración por posición actual en el Orden de lectura; solo toca el título inicial del capítulo.
            heading = re.match(r'(\s*)# (.*)', body)
            if chapter and options['numbering']:
                label = f'Capítulo {position}' + ('. ' + heading[2].strip() if heading and heading[2].strip() else '')
                body = heading[1] + '# ' + label + body[heading.end():] if heading else '# ' + label + '\n\n' + body
                heading = re.match(r'(\s*)# (.*)', body)
            if chapter and options['contents']:
                require(heading and heading[2].strip(), f'{target} no tiene título para el índice; añada un título o pida numeración.', 'invalid-input')
                contents.append('- ' + re.sub(r'^(\d+)([.)])', r'\1\\\2', heading[2].strip()) + '\n')
            bodies.append(body)
        if options['contents']:
            bodies.insert(int(options['preliminaries']), '# Índice\n\n' + ''.join(contents))
        combined = '\n\n'.join(bodies).encode()
        book.durable(f'{directory}/manuscrito.md', combined, exclusive=True)
        export_record = dict(schema_version=1, operation_id=operation, options=options, sources=entries, index_sha256=sha(index), valid=False, outputs={'manuscrito.md': sha(combined)}, language='es', limitations=[])
        book.durable(f'{directory}/manifest.json', encoded(export_record), exclusive=True)
        for entry in entries:
            require(sha(book.read(entry['path'])) == entry['sha256'], 'El manuscrito cambió durante la captura; esta exportación queda inválida.', 'stale-base')
        if options['docx']:
            try:
                command = ['pandoc', '--sandbox', '--from=markdown-smart+hard_line_breaks', '--to=docx', '--wrap=none', '--metadata=lang:es']
                for field in ('title', 'author'):
                    if manifest.get(field) is not None:
                        require(isinstance(manifest[field], str), f'{field} debe ser texto confirmado.', 'invalid-input')
                        command += ['--metadata', field + '=' + manifest[field]]
                run = subprocess.run(command, input=combined, capture_output=True, timeout=60)
                require(run.returncode == 0, 'Pandoc no pudo producir DOCX; conserve el Markdown.', 'missing-dependency')
                book.durable(f'{directory}/manuscrito.docx', run.stdout, exclusive=True)
                export_record['outputs']['manuscrito.docx'] = sha(book.read(f'{directory}/manuscrito.docx'))
                export_record['converter_options'] = command[1:]
                export_record['converter'] = subprocess.check_output(['pandoc', '--version'], text=True).splitlines()[0]
            except (FileNotFoundError, subprocess.TimeoutExpired, Problem):
                export_record['limitations'].append('DOCX no disponible; se conserva la exportación Markdown.')
        export_record['valid'] = sha(book.read('manuscrito/indice.md')) == sha(index) and all(sha(book.read(e['path'])) == e['sha256'] for e in entries)
        book.durable(f'{directory}/manifest.json', encoded(export_record))
    return result('exported' if export_record['valid'] else 'stale-base', 'Exportación preparada; exportar no significa aceptar ni terminar el libro.' if export_record['valid'] else 'El índice o manuscrito cambió; no use esta exportación.', [directory], ok=export_record['valid'], manifest=export_record)


if __name__ == '__main__':
    try:
        require(len(sys.argv) == 4 and sys.argv[1] == '_convert', 'Invocación de conversor inválida.', 'invalid-input')
        output = dict(ok=True, conversion=convert(Path(sys.argv[2]), sys.argv[3]))
    except Exception as exc:
        output = dict(ok=False, code=exc.code if isinstance(exc, Problem) else 'unsupported-format', message=exc.message if isinstance(exc, Problem) else 'El formato no se pudo leer; conserve el original.')
    print(json.dumps(output, ensure_ascii=False))
