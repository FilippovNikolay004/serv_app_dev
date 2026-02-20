from http.server import HTTPServer, BaseHTTPRequestHandler
import html
import socket
import urllib.parse


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

        query_params = parse_query_string(query_string)
        service, sections = split_route_path(path)

        self_path_display = html.escape(self.path)
        path_display = html.escape(path)
        query_string_display = html.escape(query_string if query_string else 'None')
        query_params_display = html.escape(str(query_params))
        service_display = html.escape(service if service is not None else 'None')
        sections_display = html.escape(str(sections))

        self.send_response(200, 'OK')
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.safe_write(
            f'''<!doctype html>
<html lang="uk">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Аналізатор запитів</title>
    <style>
        p {{
            margin: 0;
            padding: 0;
        }}
    </style>
</head>
<body>
    <div class="wrap">
        <h1>Аналізатор запитів</h1>

        <section class="card">
            <p class="task-label">Маршрути</p>
            <h2>Тестові посилання для розділення маршрутів:</h2>
            <ul>
                <li><a href="/">Без параметрів (/)</a></li>
                <li><a href="/user/">З сервісом (/user/)</a></li>
                <li><a href="/user">З сервісом (/user)</a></li>
                <li><a href="/user/auth">З розділами (/user/auth)</a></li>
                <li><a href="/user/auth/secret">З розділами (/user/auth/secret)</a></li>
                <li><a href="/user/%D0%A3%D0%BD%D1%96%D1%84%D1%96%D0%BA%D0%BE%D0%B2%D0%B0%D0%BD%D0%B8%D0%B9&amp;%D0%BB%D0%BE%D0%BA%D0%B0%D1%82%D0%BE%D1%80=%D1%80%D0%B5%D1%81%D1%83%D1%80%D1%81%D1%96%D0%B2&amp;2+2=4">URL-кодовані значення</a></li>
            </ul>
        </section>

        <section class="card meta">
            <p>self.path: {self_path_display}</p>
            <p>Шлях: {path_display}</p>
            <p>Сервіс: {service_display}</p>
            <p>Розділи: {sections_display}</p>
            <p>Query String: {query_string_display}</p>
            <p>Параметри (словник): {query_params_display}</p>
        </section>

        <button class="btn" onclick="linkClick()">LINK</button>
        <p id="out"></p>
    </div>

    <script>
        function linkClick() {{
            fetch('/', {{ method: 'LINK' }})
                .then(response => response.text())
                .then(text => {{
                    document.getElementById('out').textContent = text;
                }});
        }}
    </script>
</body>
</html>
'''.encode('utf-8')
        )

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
