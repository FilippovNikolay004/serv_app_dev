from http.server import HTTPServer, BaseHTTPRequestHandler
import html
from pathlib import Path
import socket
from string import Template
import urllib.parse


BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = BASE_DIR / 'templates' / 'index.html'
STYLES_PATH = BASE_DIR / 'static' / 'styles.css'


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
