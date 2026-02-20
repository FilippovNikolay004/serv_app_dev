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
        :root {{
            --bg: #09090b;
            --bg-elevated: #111114;
            --panel: #121217;
            --panel-soft: #16161d;
            --border: #252530;
            --border-strong: #333346;
            --text: #f4f4f7;
            --muted: #9f9fae;
            --accent: #8b5cf6;
            --accent-soft: rgba(139, 92, 246, 0.18);
            --radius: 14px;
        }}

        * {{
            box-sizing: border-box;
        }}

        html,
        body {{
            margin: 0;
            padding: 0;
            min-height: 100%;
        }}

        body {{
            font-family: "Manrope", "Segoe UI", "Trebuchet MS", sans-serif;
            color: var(--text);
            background:
                radial-gradient(circle at 10% -5%, rgba(139, 92, 246, 0.1), transparent 45%),
                linear-gradient(180deg, #0a0a0c, var(--bg));
        }}

        .page {{
            width: min(1080px, calc(100% - 2rem));
            margin: 1.1rem auto 1.8rem;
        }}

        .top {{
            background: var(--bg-elevated);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 1.1rem 1.25rem 1.2rem;
        }}

        .top-kicker {{
            margin: 0;
            display: inline-block;
            font-size: 0.73rem;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            color: #c7b1ff;
            background: var(--accent-soft);
            border: 1px solid rgba(139, 92, 246, 0.3);
            border-radius: 999px;
            padding: 0.32rem 0.58rem;
        }}

        .top h1 {{
            margin: 0.72rem 0 0;
            font-size: clamp(1.34rem, 2.2vw, 1.92rem);
            line-height: 1.25;
            letter-spacing: -0.015em;
        }}

        .top p {{
            margin: 0.52rem 0 0;
            color: var(--muted);
            line-height: 1.5;
            max-width: 720px;
        }}

        .layout {{
            margin-top: 0.9rem;
            display: grid;
            grid-template-columns: 1.15fr 0.85fr;
            gap: 0.9rem;
        }}

        .panel {{
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 1rem;
        }}

        .panel-label {{
            margin: 0;
            color: var(--muted);
            font-size: 0.72rem;
            letter-spacing: 0.1em;
            text-transform: uppercase;
        }}

        .panel h2 {{
            margin: 0.45rem 0 0.95rem;
            font-size: 1.03rem;
            letter-spacing: -0.01em;
        }}

        .routes {{
            margin: 0;
            padding: 0;
            list-style: none;
            display: grid;
            gap: 0.55rem;
        }}

        .routes a {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 0.7rem;
            text-decoration: none;
            color: var(--text);
            padding: 0.76rem 0.85rem;
            border-radius: 11px;
            border: 1px solid var(--border);
            background: linear-gradient(180deg, rgba(21, 21, 27, 0.88), rgba(16, 16, 21, 0.88));
            transition: border-color 0.2s ease, background-color 0.2s ease;
        }}

        .routes a:hover {{
            border-color: rgba(139, 92, 246, 0.5);
            background: linear-gradient(180deg, rgba(26, 24, 34, 0.96), rgba(18, 17, 24, 0.96));
        }}

        .routes span {{
            font-size: 0.93rem;
            line-height: 1.3;
            color: #e3e3eb;
        }}

        .routes code {{
            color: #c7b1ff;
            font-family: "JetBrains Mono", "Cascadia Code", "Consolas", monospace;
            font-size: 0.79rem;
            word-break: break-all;
            text-align: right;
        }}

        .meta {{
            margin: 0;
            padding: 0;
            list-style: none;
            display: grid;
            gap: 0.55rem;
        }}

        .meta-item {{
            border: 1px solid var(--border);
            border-radius: 11px;
            padding: 0.7rem 0.78rem;
            background: var(--panel-soft);
        }}

        .meta-item b {{
            display: block;
            margin-bottom: 0.26rem;
            font-size: 0.71rem;
            font-weight: 600;
            color: var(--muted);
            letter-spacing: 0.09em;
            text-transform: uppercase;
        }}

        .meta-item code {{
            color: var(--text);
            font-family: "JetBrains Mono", "Cascadia Code", "Consolas", monospace;
            font-size: 0.8rem;
            line-height: 1.4;
            word-break: break-word;
        }}

        .actions {{
            margin-top: 0.9rem;
            display: flex;
            gap: 0.7rem;
            align-items: center;
            flex-wrap: wrap;
        }}

        .btn {{
            border: 1px solid rgba(139, 92, 246, 0.42);
            background: linear-gradient(180deg, #1f1730, #1a1429);
            color: #ddd1fb;
            border-radius: 10px;
            padding: 0.62rem 0.98rem;
            cursor: pointer;
            font-weight: 600;
            letter-spacing: 0.01em;
            transition: border-color 0.2s ease, color 0.2s ease;
        }}

        .btn:hover {{
            border-color: #9a6cff;
            color: #f2eaff;
        }}

        .result {{
            margin: 0;
            flex: 1 1 320px;
            min-height: 2.3rem;
            display: flex;
            align-items: center;
            border-radius: 10px;
            border: 1px solid var(--border-strong);
            background: #101016;
            color: #d7cbf6;
            padding: 0.6rem 0.8rem;
            font-family: "JetBrains Mono", "Cascadia Code", "Consolas", monospace;
            font-size: 0.8rem;
            word-break: break-word;
        }}

        @media (max-width: 900px) {{
            .layout {{
                grid-template-columns: 1fr;
            }}
        }}

        @media (max-width: 640px) {{
            .page {{
                width: min(1120px, calc(100% - 1rem));
                margin-top: 0.75rem;
            }}

            .top,
            .panel {{
                padding: 0.86rem;
            }}

            .routes a {{
                align-items: flex-start;
                flex-direction: column;
            }}

            .routes code {{
                text-align: left;
            }}

            .result {{
                flex-basis: 100%;
            }}
        }}
    </style>
</head>
<body>
    <main class="page">
        <header class="top">
            <p class="top-kicker">HTTP Router Lab</p>
            <h1>Аналізатор маршрутів</h1>
            <p>Строга сторінка для перевірки алгоритму розділення маршруту, секцій та URL-кодованих значень.</p>
        </header>

        <section class="layout">
            <article class="panel">
                <p class="panel-label">Маршрути</p>
                <h2>Тестові посилання</h2>
                <ul class="routes">
                    <li><a href="/"><span>Без параметрів</span><code>/</code></a></li>
                    <li><a href="/user/"><span>З сервісом</span><code>/user/</code></a></li>
                    <li><a href="/user"><span>З сервісом</span><code>/user</code></a></li>
                    <li><a href="/user/auth"><span>З розділом</span><code>/user/auth</code></a></li>
                    <li><a href="/user/auth/secret"><span>З розділами</span><code>/user/auth/secret</code></a></li>
                    <li><a href="/user/%D0%A3%D0%BD%D1%96%D1%84%D1%96%D0%BA%D0%BE%D0%B2%D0%B0%D0%BD%D0%B8%D0%B9&amp;%D0%BB%D0%BE%D0%BA%D0%B0%D1%82%D0%BE%D1%80=%D1%80%D0%B5%D1%81%D1%83%D1%80%D1%81%D1%96%D0%B2&amp;2+2=4"><span>URL-кодовані значення</span><code>/user/%D0%A3%D0%BD%D1%96%D1%84%D1%96%D0%BA%D0%BE%D0%B2%D0%B0%D0%BD%D0%B8%D0%B9&amp;%D0%BB%D0%BE%D0%BA%D0%B0%D1%82%D0%BE%D1%80=%D1%80%D0%B5%D1%81%D1%83%D1%80%D1%81%D1%96%D0%B2&amp;2+2=4</code></a></li>
                </ul>
            </article>

            <article class="panel">
                <p class="panel-label">Дані запиту</p>
                <h2>Поточний розбір</h2>
                <ul class="meta">
                    <li class="meta-item"><b>self.path</b><code>{self_path_display}</code></li>
                    <li class="meta-item"><b>Шлях</b><code>{path_display}</code></li>
                    <li class="meta-item"><b>Сервіс</b><code>{service_display}</code></li>
                    <li class="meta-item"><b>Розділи</b><code>{sections_display}</code></li>
                    <li class="meta-item"><b>Query String</b><code>{query_string_display}</code></li>
                    <li class="meta-item"><b>Параметри</b><code>{query_params_display}</code></li>
                </ul>
            </article>
        </section>

        <section class="actions">
            <button class="btn" onclick="linkClick()">Надіслати LINK</button>
            <output id="out" class="result">Очікування відповіді...</output>
        </section>
    </main>

    <script>
        function linkClick() {{
            const out = document.getElementById('out');
            out.textContent = 'Надсилаємо LINK...';

            fetch('/', {{ method: 'LINK' }})
                .then(response => response.text())
                .then(text => {{
                    out.textContent = text;
                }})
                .catch(error => {{
                    out.textContent = 'Помилка LINK: ' + error;
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
