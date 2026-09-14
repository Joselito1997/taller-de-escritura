"""Controles operativos para investigación pública sin credenciales heredadas."""
import ipaddress
import http.client
import ssl
import json
import os
import re
import socket
import time
from email.utils import parsedate_to_datetime
import urllib.error
import urllib.parse
import urllib.request

from book import encoded, parse_json, result, sha, ID
from schemas import Problem, require
from maintenance import sealed, checked

BUDGETS = {'quick': (2, 3, 300), 'standard': (4, 8, 900), 'extended': (8, 15, 1800)}
ENDPOINTS = {'exa': 'https://mcp.exa.ai/mcp?tools=web_search_exa,web_fetch_exa', 'firecrawl': 'https://mcp.firecrawl.dev/v2/mcp'}
TOOLS = {'web_search_exa': ('exa', 'search'), 'web_fetch_exa': ('exa', 'fetch'), 'firecrawl_scrape': ('firecrawl', 'fetch'), 'preserve_pdf': ('public-pdf', 'fetch')}


def url_identity(url):
    require(isinstance(url, str), 'La URL debe ser texto.', 'invalid-input')
    parsed = urllib.parse.urlsplit(url)
    require(parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password and parsed.port in (None, 443), 'Use una URL HTTPS pública sin credenciales ni puertos privados.', 'path-outside-scope')
    host = parsed.hostname.lower()
    require('.' in host and not host.endswith(('.local', '.internal', '.localhost', '.test')) and host != 'localhost', 'Los recursos privados pertenecen a Importar, no a investigación web.', 'path-outside-scope')
    require(not any(word in parsed.path.casefold() for word in ('/private/', '/share/', '/sharing/')) and not any(key.lower() in {'token', 'key', 'auth', 'password', 'signature', 'x-amz-signature'} for key, _ in urllib.parse.parse_qsl(parsed.query)), 'El enlace parece privado o autenticado; impórtelo localmente.', 'path-outside-scope')
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    require(literal is None or literal.is_global, 'No se permiten direcciones privadas ni reservadas.', 'path-outside-scope')
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path or '/', parsed.query, ''))


def public_url(url, resolver=socket.getaddrinfo):
    normalized = url_identity(url)
    try:
        addresses = resolver(urllib.parse.urlsplit(normalized).hostname, 443, type=socket.SOCK_STREAM)
        require(addresses and all(ipaddress.ip_address(item[4][0]).is_global for item in addresses), 'La URL resuelve a una red privada o reservada.', 'path-outside-scope')
    except socket.gaierror as exc:
        raise Problem('source-unavailable', 'No se pudo resolver el sitio público.') from exc
    return normalized



class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Problem('source-unavailable', 'El endpoint cambió de dirección; compruebe su configuración antes de reenviar datos.')


def preserve_pdf(url):
    normalized = public_url(url)
    parsed = urllib.parse.urlsplit(normalized)
    addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
    require(addresses and all(ipaddress.ip_address(item[4][0]).is_global for item in addresses), 'La dirección cambió a una red privada; no se descarga.', 'path-outside-scope')
    address = addresses[0][4][0]
    class PinnedConnection(http.client.HTTPSConnection):
        def connect(self):
            raw = socket.create_connection((address, 443), self.timeout)
            try:
                self.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=self.host)
            except BaseException:
                raw.close()
                raise
    connection = PinnedConnection(parsed.hostname, timeout=45)
    try:
        connection.request('GET', urllib.parse.urlunsplit(('', '', parsed.path, parsed.query, '')), headers={'Accept':'application/pdf','User-Agent':'escritura-local/1'})
        response = connection.getresponse()
        if response.status != 200:
            raise urllib.error.HTTPError(normalized, response.status, 'La fuente no entregó el PDF completo.', response.headers, None)
        length = response.getheader('Content-Length')
        require(length is None or length.isdigit() and int(length) <= 100 * 1024 * 1024, 'El PDF supera el límite de 100 MB o declara un tamaño inválido.', 'invalid-input')
        data = response.read(100 * 1024 * 1024 + 1)
        require(len(data) <= 100 * 1024 * 1024 and data.startswith(b'%PDF-'), 'La respuesta no es un PDF admitido; no se presenta como original PDF.', 'unsupported-format')
        require(length is None or len(data) == int(length), 'La descarga PDF quedó incompleta.', 'partial-save')
        return data
    except urllib.error.HTTPError:
        raise
    except (OSError, http.client.HTTPException) as exc:
        raise urllib.error.URLError('No se pudo completar la descarga pública del PDF.') from exc
    finally:
        connection.close()


def mcp_call(provider, tool, arguments):
    if tool == 'preserve_pdf':
        return preserve_pdf(arguments['url'])
    endpoint = ENDPOINTS[provider]
    opener = urllib.request.build_opener(NoRedirect())
    session = None
    def rpc(payload):
        nonlocal session
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'}
        if session:
            headers['Mcp-Session-Id'] = session
        request = urllib.request.Request(endpoint, encoded(payload), headers=headers)
        with opener.open(request, timeout=45) as response:
            session = response.headers.get('Mcp-Session-Id', session)
            raw = response.read(10 * 1024 * 1024 + 1)
            require(len(raw) <= 10 * 1024 * 1024, 'La respuesta excede el límite; conserve cobertura parcial.', 'partial-save')
        if not raw.strip():
            return {}
        if raw.lstrip().startswith(b'data:') or b'\ndata:' in raw:
            events = [parse_json(line[5:].strip()) for line in raw.splitlines() if line.startswith(b'data:')]
            return next((event for event in reversed(events) if event.get('id') == payload.get('id')), {})
        return parse_json(raw)
    initialized = rpc({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-03-26', 'capabilities': {}, 'clientInfo': {'name': 'escritura-local', 'version': '1'}}})
    require('result' in initialized, 'El proveedor no pudo iniciar MCP.', 'source-unavailable')
    rpc({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
    inventory = rpc({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'})
    available = [entry.get('name') for entry in inventory.get('result', {}).get('tools', [])]
    require(tool in available, 'El proveedor no ofrece la herramienta acordada.', 'missing-dependency')
    response = rpc({'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': tool, 'arguments': arguments}})
    require('result' in response and not response['result'].get('isError'), 'La herramienta informó un resultado incompleto o fallido.', 'source-unavailable')
    return response['result']


def execute(book, manifest, transport=mcp_call):
    operation = book.manifest(manifest)
    mode, tool = manifest.get('mode', 'quick'), manifest.get('tool')
    require(mode in BUDGETS and tool in TOOLS, 'Modo o herramienta de investigación no permitido.', 'invalid-input')
    require(mode != 'extended' or manifest.get('extended_authorized') is True, 'El modo extendido requiere una solicitud explícita.', 'invalid-input')
    provider, category = TOOLS[tool]
    require(provider == 'public-pdf' or not any(os.environ.get(name) for name in ('EXA_API_KEY', 'FIRECRAWL_API_KEY')), 'Hay credenciales heredadas; no se puede afirmar modo gratuito. Use un entorno sin esas credenciales o una configuración de pago autorizada.', 'authentication-failed')
    arguments = manifest.get('arguments')
    require(isinstance(arguments, dict), 'Faltan argumentos de investigación.', 'invalid-input')
    if category == 'fetch':
        require(set(arguments) <= {'url', 'urls', 'formats', 'onlyMainContent'} and ('url' in arguments) != ('urls' in arguments), 'Solo se admiten URLs públicas y opciones de lectura.', 'invalid-input')
        require('formats' not in arguments or isinstance(arguments['formats'], list) and 1 <= len(arguments['formats']) <= 2 and all(value in ('markdown','html') for value in arguments['formats']), 'Solo se permite extraer texto Markdown o HTML, sin capturas ni acciones adicionales.', 'invalid-input')
        require('onlyMainContent' not in arguments or type(arguments['onlyMainContent']) is bool, 'onlyMainContent debe ser booleano.', 'invalid-input')
        require(tool != 'preserve_pdf' or set(arguments) == {'url'}, 'Conserve un PDF seleccionado por solicitud, sin acciones ni opciones adicionales.', 'invalid-input')
        urls = arguments.get('urls', [arguments.get('url')])
        require(isinstance(urls, list) and 1 <= len(urls) <= 15, 'Lista de URLs inválida.', 'invalid-input')
        normalized = [url_identity(url) for url in urls]
        require(len(normalized) == len(set(normalized)), 'No solicite dos veces la misma URL en un lote.', 'invalid-input')
        max_age = manifest.get('max_age_seconds', 86400)
        require(type(max_age) is int and 0 <= max_age <= 2592000, 'La antigüedad permitida debe estar entre 0 y 30 días.', 'invalid-input')
        catalog_raw = book.read('.writing/research-library.json')
        catalog = checked(catalog_raw) if catalog_raw else {'entries': {}}
        cached = [catalog['entries'].get(url) for url in normalized]
        if all(cached) and not manifest.get('refresh'):
            for item in cached:
                require(sha(book.read(item['artifact'])) == item['sha256'], 'Una fuente guardada cambió; no se usa como evidencia verificada.', 'invalid-input')
            if manifest.get('offline') or all(time.time() - item['captured_at'] <= max_age for item in cached):
                return result('research-cache', 'Se reutilizaron respuestas guardadas con sus fechas; revise su antigüedad y cobertura parcial.', [item['artifact'] for item in cached], sources=cached, ages_seconds=[time.time()-item['captured_at'] for item in cached])
        if manifest.get('offline'):
            return result('source-unavailable', 'No hay respuesta guardada para esta URL; solicite una respuesta expresamente sin fuentes o reintente con conexión.', ok=False)
        normalized = [public_url(url) for url in urls]
        cost = len(urls)
    else:
        require(set(arguments) <= {'query', 'numResults'} and isinstance(arguments.get('query'), str) and 0 < len(arguments['query']) <= 500 and manifest.get('public_query_confirmed') is True, 'Confirme una consulta pública genérica de hasta 500 caracteres.', 'invalid-input')
        require('numResults' not in arguments or type(arguments['numResults']) is int and 1 <= arguments['numResults'] <= 10, 'Solicite entre 1 y 10 resultados por búsqueda.', 'invalid-input')
        query = arguments['query'].casefold()
        for path in book.content_paths():
            if path.startswith('historia/personajes/'):
                from schemas import validate
                name = validate(book.read(path))['metadata'].get('name')
                require(not isinstance(name, str) or len(name) < 3 or re.search(r'(?<!\w)' + re.escape(name.casefold()) + r'(?!\w)', query) is None, 'La consulta contiene un nombre privado del manuscrito.', 'path-outside-scope')
            if path.startswith('manuscrito/'):
                words = book.read(path).decode().casefold().split()
                require(not any(' '.join(words[i:i+8]) in query for i in range(max(0, len(words)-7))), 'La consulta contiene prosa del manuscrito; use términos generales.', 'path-outside-scope')
        cost = 1
    brief = manifest.get('brief_id', operation)
    require(isinstance(brief, str) and ID.fullmatch(brief), 'Identidad de informe inválida.', 'invalid-input')
    state_path = f'.writing/research/{brief}.json'
    fingerprint = sha(encoded(manifest))
    with book.lock(operation):
        raw = book.read(state_path)
        state = checked(raw) if raw else dict(mode=mode, started=time.time(), search=0, fetch=0, requests={}, blocked_providers=[])
        require(state.get('mode') == mode and isinstance(state.get('requests'), dict), 'El informe cambió de modo o su registro está dañado.', 'invalid-input')
        require(all(type(state.get(k)) is int and 0 <= state[k] <= BUDGETS[mode][i] for i,k in enumerate(('search','fetch'))) and isinstance(state.get('started'), (int,float)) and state['started'] <= time.time(), 'Los contadores o fechas de investigación están dañados.', 'invalid-input')
        for old in state['requests'].values():
            if old.get('status') == 'saved':
                require(old.get('artifact') == f"investigacion/originales/{old.get('sha256')}/" + ('original.pdf' if old.get('tool') == 'preserve_pdf' else 'respuesta.json') and sha(book.read(old['artifact'])) == old['sha256'], 'La respuesta de investigación está dañada.', 'invalid-input')
        if operation in state['requests']:
            previous = state['requests'][operation]
            require(previous.get('request_sha256') == fingerprint, 'La solicitud ya tiene otra identidad.', 'invalid-input')
            return result('research-recorded', 'Esta solicitud ya tiene un intento registrado; no se repite automáticamente.', [state_path], request=previous)
        require(provider not in state['blocked_providers'], 'Este proveedor está detenido por un fallo de autenticación.', 'authentication-failed')
        request = dict(request_sha256=fingerprint, status='prepared', attempts=0, provider=provider, tool=tool)
        state['requests'][operation] = request
        for attempt in range(2):
            search_limit, fetch_limit, seconds = BUDGETS[mode]
            limit = search_limit if category == 'search' else fetch_limit
            require(state[category] + cost <= limit and time.time() - state['started'] < seconds, 'Se agotó el presupuesto del informe; entregue lo obtenido antes de ampliar el alcance.', 'budget-exhausted')
            state[category] += cost
            request['attempts'] += 1
            request['status'] = 'attempted'
            book.durable(state_path, sealed(state))
            try:
                response = transport(provider, tool, arguments)
                require(tool != 'preserve_pdf' or isinstance(response, bytes) and response.startswith(b'%PDF-'), 'La captura no devolvió bytes PDF.', 'unsupported-format')
                content = response if tool == 'preserve_pdf' else encoded(response)
                digest = sha(content)
                original_path = f'investigacion/originales/{digest}/' + ('original.pdf' if tool == 'preserve_pdf' else 'respuesta.json')
                if book.read(original_path) is None:
                    book.durable(original_path, content, exclusive=True)
                require(sha(book.read(original_path)) == digest, 'La respuesta conservada cambió.', 'invalid-input')
                request.update(status='saved', artifact=original_path, sha256=digest, coverage='partial', captured_at=time.time())
                if category == 'fetch':
                    catalog_raw = book.read('.writing/research-library.json')
                    catalog = checked(catalog_raw) if catalog_raw else {'entries': {}}
                    for url in normalized:
                        catalog['entries'][url] = dict(url=url, artifact=original_path, sha256=digest, captured_at=request['captured_at'], coverage='partial')
                    book.durable('.writing/research-library.json', sealed(catalog))
                book.durable(state_path, sealed(state))
                return result('research-saved', 'Se conservó la respuesta pública; verifique cobertura y fuentes antes de sintetizarla.', [original_path, state_path], request=request, budget=dict(search=state['search'], fetch=state['fetch']), limitations=['La respuesta del proveedor no demuestra captura íntegra del documento ni convierte sus afirmaciones en hechos del libro.'])
            except urllib.error.HTTPError as exc:
                code = 'authentication-failed' if exc.code in (401, 403) else 'rate-limited' if exc.code == 429 else 'source-unavailable'
                request.update(status='failed', code=code, http_status=exc.code)
                if exc.code in (401, 403):
                    state['blocked_providers'].append(provider)
                retry_after = exc.headers.get('Retry-After', '0') if exc.headers else '0'
                try:
                    wait = float(retry_after) if retry_after.isdigit() else max(0, parsedate_to_datetime(retry_after).timestamp() - time.time())
                except (TypeError, ValueError, AttributeError):
                    wait = 0
                transient = exc.code in (429, 500, 502, 503, 504)
            except (urllib.error.URLError, TimeoutError):
                request.update(status='failed', code='source-unavailable')
                transient, wait = True, 0
            except Problem as exc:
                request.update(status='failed', code=exc.code)
                transient, wait = False, 0
            book.durable(state_path, sealed(state))
            if not transient or attempt or wait > 30 or time.time() - state['started'] + wait >= seconds or state[category] + cost > limit:
                break
            time.sleep(wait)
    output = result(request['code'], 'El proveedor no completó la consulta. Use fuentes guardadas con sus fechas o solicite una respuesta expresamente sin fuentes.', [state_path], ok=False, request=request)
    output['next_action'] = 'Revise ' + state_path + '; use fuentes locales fechadas o solicite una respuesta sin investigación, sin ampliar permisos ni activar pago automáticamente.'
    return output
