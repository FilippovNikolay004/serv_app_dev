from http.server import HTTPServer, BaseHTTPRequestHandler
import html
import json
import math
from pathlib import Path
import socket
from string import Template
import urllib.parse


BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = BASE_DIR / 'templates' / 'index.html'
STYLES_PATH = BASE_DIR / 'static' / 'styles.css'
DEFAULT_PER_PAGE = 5
MAX_PER_PAGE = 25

# In-memory resource for demonstrating REST collection/item endpoints.
USERS = [
    {'id': 1, 'name': 'Alice', 'email': 'alice@example.com'},
    {'id': 2, 'name': 'Bob', 'email': 'bob@example.com'},
    {'id': 3, 'name': 'Carol', 'email': 'carol@example.com'},
    {'id': 4, 'name': 'Dave', 'email': 'dave@example.com'},
    {'id': 5, 'name': 'Eve', 'email': 'eve@example.com'},
    {'id': 6, 'name': 'Frank', 'email': 'frank@example.com'},
    {'id': 7, 'name': 'Grace', 'email': 'grace@example.com'},
    {'id': 8, 'name': 'Heidi', 'email': 'heidi@example.com'},
    {'id': 9, 'name': 'Ivan', 'email': 'ivan@example.com'},
    {'id': 10, 'name': 'Judy', 'email': 'judy@example.com'},
    {'id': 11, 'name': 'Karl', 'email': 'karl@example.com'},
    {'id': 12, 'name': 'Liam', 'email': 'liam@example.com'},
]


def render_index_html(context: dict[str, str]) -> str:
    template = Template(TEMPLATE_PATH.read_text(encoding='utf-8'))
    return template.safe_substitute(context)


def url_decode(value: str | None) -> str | None:
    return None if value is None else urllib.parse.unquote_plus(value)


def parse_query_string(query_string: str) -> dict[str, str | None | list[str | None]]:
    query_params: dict[str, str | None | list[str | None]] = {}

    for item in query_string.split('&'):
        if len(item) == 0:
            continue

        raw_key, raw_value = item.split('=', 1) if '=' in item else (item, None)
        key = url_decode(raw_key)
        value = url_decode(raw_value)

        if key is None:
            continue

        if key in query_params:
            current_value = query_params[key]
            if isinstance(current_value, list):
                current_value.append(value)
            else:
                query_params[key] = [current_value, value]
        else:
            query_params[key] = value

    return query_params


def split_route_path(path: str) -> tuple[str | None, list[str]]:
    cleaned_path = path.strip('/')
    if len(cleaned_path) == 0:
        return None, []

    parts = [urllib.parse.unquote(part) for part in cleaned_path.split('/') if len(part) > 0]
    if len(parts) == 0:
        return None, []

    return parts[0], parts[1:]


def get_query_param(query_params: dict[str, str | None | list[str | None]], key: str) -> str | None:
    value = query_params.get(key)
    if isinstance(value, list):
        return value[0]
    return value


def parse_int_param(value: str | None, name: str, default: int, *, minimum: int, maximum: int) -> int:
    if value is None:
        return default

    try:
        parsed = int(value)
    except ValueError as ex:
        raise ValueError(f'"{name}" must be an integer') from ex

    if parsed < minimum:
        raise ValueError(f'"{name}" must be >= {minimum}')
    if parsed > maximum:
        raise ValueError(f'"{name}" must be <= {maximum}')

    return parsed


def build_page_link(
    path: str,
    query_params: dict[str, str | None | list[str | None]],
    page: int,
    per_page: int,
) -> str:
    clean_params: dict[str, str | list[str]] = {}

    for key, value in query_params.items():
        if key in ('page', 'per_page'):
            continue

        if isinstance(value, list):
            clean_list = [item for item in value if item is not None]
            if len(clean_list) > 0:
                clean_params[key] = clean_list
        elif value is not None:
            clean_params[key] = value

    clean_params['page'] = str(page)
    clean_params['per_page'] = str(per_page)

    encoded = urllib.parse.urlencode(clean_params, doseq=True)
    return f'{path}?{encoded}'


class RequestHandler(BaseHTTPRequestHandler):
    def safe_write(self, payload: bytes) -> None:
        """Write response body and ignore client-side disconnects."""
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, socket.error):
            return

    def serve_file(self, file_path: Path, content_type: str) -> None:
        try:
            payload = file_path.read_bytes()
        except FileNotFoundError:
            self.send_response(404, 'Not Found')
            self.end_headers()
            return

        self.send_response(200, 'OK')
        self.send_header('Content-Type', content_type)
        self.end_headers()
        self.safe_write(payload)

    def send_json(self, status_code: int, payload: dict | list) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')

        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.safe_write(body)

    def send_error_json(self, status_code: int, message: str) -> None:
        self.send_json(status_code, {'error': {'status': status_code, 'message': message}})

    def handle_users_collection(
        self,
        path: str,
        query_params: dict[str, str | None | list[str | None]],
    ) -> None:
        try:
            page = parse_int_param(
                get_query_param(query_params, 'page'),
                'page',
                1,
                minimum=1,
                maximum=1000000,
            )
            per_page = parse_int_param(
                get_query_param(query_params, 'per_page'),
                'per_page',
                DEFAULT_PER_PAGE,
                minimum=1,
                maximum=MAX_PER_PAGE,
            )
        except ValueError as ex:
            self.send_error_json(400, str(ex))
            return

        total_items = len(USERS)
        total_pages = math.ceil(total_items / per_page) if total_items > 0 else 0

        if total_pages == 0:
            if page != 1:
                self.send_error_json(400, '"page" is out of range. Allowed value: 1')
                return
        elif page > total_pages:
            self.send_error_json(400, f'"page" is out of range. Allowed values: 1..{total_pages}')
            return

        offset = (page - 1) * per_page
        data = USERS[offset:offset + per_page]

        has_prev = page > 1
        has_next = total_pages > 0 and page < total_pages
        links = {
            'self': build_page_link(path, query_params, page, per_page),
            'first': build_page_link(path, query_params, 1, per_page),
            'last': build_page_link(path, query_params, max(total_pages, 1), per_page),
            'prev': build_page_link(path, query_params, page - 1, per_page) if has_prev else None,
            'next': build_page_link(path, query_params, page + 1, per_page) if has_next else None,
        }

        payload = {
            'data': data,
            'meta': {
                'count': len(data),
                'total_items': total_items,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total_pages': total_pages,
                    'has_prev': has_prev,
                    'has_next': has_next,
                },
            },
            'links': links,
        }
        self.send_json(200, payload)

    def handle_users_item(self, user_id_raw: str) -> None:
        try:
            user_id = int(user_id_raw)
        except ValueError:
            self.send_error_json(400, '"id" must be an integer')
            return

        user = next((item for item in USERS if item['id'] == user_id), None)
        if user is None:
            self.send_error_json(404, f'User with id={user_id} not found')
            return

        self.send_json(200, {'data': user})

    def handle_api_get(self, path: str, query_params: dict[str, str | None | list[str | None]]) -> None:
        service, sections = split_route_path(path)
        if service != 'api':
            self.send_error_json(404, 'Resource not found')
            return

        if len(sections) == 0:
            self.send_json(
                200,
                {
                    'data': [{'resource': 'users', 'href': '/api/users'}],
                    'meta': {'count': 1},
                },
            )
            return

        resource = sections[0]
        if resource != 'users':
            self.send_error_json(404, f'Resource "{resource}" not found')
            return

        if len(sections) == 1:
            self.handle_users_collection(path, query_params)
            return

        if len(sections) == 2:
            self.handle_users_item(sections[1])
            return

        self.send_error_json(404, 'Resource not found')

    def do_GET(self):
        print(self.path)
        print(self.command)

        # MVC: /controller/action/id?
        # API: METHOD /service/section?
        # Example: /user/auth?x=10&y=20
        parts = self.path.split('?', 1)
        path = parts[0]
        query_string = parts[1] if len(parts) > 1 else ''

        # Browser service requests (icon/devtools manifest) are irrelevant for this task.
        if path in ('/favicon.ico', '/.well-known/appspecific/com.chrome.devtools.json'):
            self.send_response(204, 'No Content')
            self.end_headers()
            return

        if path == '/static/styles.css':
            self.serve_file(STYLES_PATH, 'text/css; charset=utf-8')
            return

        query_params = parse_query_string(query_string)

        if path == '/api' or path.startswith('/api/'):
            self.handle_api_get(path, query_params)
            return

        service, sections = split_route_path(path)

        page_html = render_index_html(
            {
                'self_path_display': html.escape(self.path),
                'path_display': html.escape(path),
                'query_string_display': html.escape(query_string if query_string else 'None'),
                'query_params_display': html.escape(str(query_params)),
                'service_display': html.escape(service if service is not None else 'None'),
                'sections_display': html.escape(str(sections)),
            }
        )

        self.send_response(200, 'OK')
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.safe_write(page_html.encode('utf-8'))

    def do_LINK(self):
        self.send_response(200, 'OK')
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.safe_write('LINK method response'.encode('utf-8'))


def main():
    host = '127.0.0.1'
    port = 8000
    endpoint = (host, port)
    http_server = HTTPServer(endpoint, RequestHandler)

    try:
        print(f'Try start server http://{host}:{port}')
        http_server.serve_forever()
    except KeyboardInterrupt:
        print('Server stopped')
    finally:
        http_server.server_close()


if __name__ == '__main__':
    main()

'''
Модуль HTTP
Альтернативний до CGI підхід у створенні серверних застосунків
полягає у створенні власного (програмного)
сервера, що є частиною загального проєкту.
+ використовуємо єдину мову програмування (не потрібна конфігурація
  стороннього сервера окремою мовою)
+ уніфікуються ліцензійні умови
- дотримання стандартів і протоколів перекладається на проєкт
- частіше за все, програмні сервери більш повільні і не сертифіковані

У Python такі засоби надає пакет http.server
HTTPServer - клас управління сервером (слухання порту, прийом запитів)
BaseHTTPRequestHandler - продовження оброблення, формування відповіді
'''
