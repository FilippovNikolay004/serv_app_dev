from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import html
import importlib
import json
import math
from pathlib import Path
import socket
from string import Template
import sys
import urllib.parse


DEV_MODE = True
BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = BASE_DIR / "templates" / "index.html"
STATIC_DIR = BASE_DIR / "static"
DEFAULT_PER_PAGE = 5
MAX_PER_PAGE = 25
STATIC_ALLOWED_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "svg": "image/svg+xml",
    "css": "text/css; charset=utf-8",
    "js": "application/javascript; charset=utf-8",
    "ico": "image/x-icon",
}
STATIC_FALLBACK_DIRS = {
    "css": "css",
    "js": "js",
    "png": "img",
    "jpg": "img",
    "jpeg": "img",
    "gif": "img",
    "webp": "img",
    "svg": "img",
    "ico": "img",
}

USERS = [
    {"id": 1, "name": "Alice", "email": "alice@example.com"},
    {"id": 2, "name": "Bob", "email": "bob@example.com"},
    {"id": 3, "name": "Carol", "email": "carol@example.com"},
    {"id": 4, "name": "Dave", "email": "dave@example.com"},
    {"id": 5, "name": "Eve", "email": "eve@example.com"},
    {"id": 6, "name": "Frank", "email": "frank@example.com"},
    {"id": 7, "name": "Grace", "email": "grace@example.com"},
    {"id": 8, "name": "Heidi", "email": "heidi@example.com"},
    {"id": 9, "name": "Ivan", "email": "ivan@example.com"},
    {"id": 10, "name": "Judy", "email": "judy@example.com"},
    {"id": 11, "name": "Karl", "email": "karl@example.com"},
    {"id": 12, "name": "Liam", "email": "liam@example.com"},
]


def render_index_html(context: dict[str, str]) -> str:
    template = Template(TEMPLATE_PATH.read_text(encoding="utf-8"))
    return template.safe_substitute(context)


def url_decode(input_str: str | None) -> str | None:
    return None if input_str is None else urllib.parse.unquote_plus(input_str)


def parse_query_string(query_string: str) -> dict[str, str | None | list[str | None]]:
    query_params: dict[str, str | None | list[str | None]] = {}

    for item in query_string.split("&"):
        if not item:
            continue

        raw_key, raw_value = item.split("=", 1) if "=" in item else (item, None)
        key = url_decode(raw_key)
        value = url_decode(raw_value)
        if key is None:
            continue

        if key in query_params:
            current = query_params[key]
            if isinstance(current, list):
                current.append(value)
            else:
                query_params[key] = [current, value]
        else:
            query_params[key] = value

    return query_params


def split_route_path(path: str) -> tuple[str | None, list[str]]:
    cleaned = path.strip("/")
    if not cleaned:
        return None, []

    parts = [urllib.parse.unquote(part) for part in cleaned.split("/") if part]
    if not parts:
        return None, []

    return parts[0], parts[1:]


def normalize_controller_name(service: str) -> tuple[str, str]:
    service_key = service.lower().replace("-", "_")
    class_key = "".join(part.capitalize() for part in service_key.split("_") if part)
    if not class_key:
        class_key = "Home"
    return f"{service_key}_controller", f"{class_key}Controller"


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
        if key in ("page", "per_page"):
            continue

        if isinstance(value, list):
            values = [item for item in value if item is not None]
            if values:
                clean_params[key] = values
        elif value is not None:
            clean_params[key] = value

    clean_params["page"] = str(page)
    clean_params["per_page"] = str(per_page)

    encoded = urllib.parse.urlencode(clean_params, doseq=True)
    return f"{path}?{encoded}"


class AccessManagerRequestHandler(BaseHTTPRequestHandler):
    def handle_one_request(self) -> None:
        try:
            self.raw_requestline = self.rfile.readline(65537)
            if len(self.raw_requestline) > 65536:
                self.send_error(414)
                return
            if not self.raw_requestline:
                self.close_connection = True
                return
            if not self.parse_request():
                return

            self.access_manager()
            try:
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, socket.error):
                self.close_connection = True
        except socket.timeout as ex:
            self.log_error("Request timed out: %r", ex)
            self.close_connection = True

    def safe_write(self, payload: bytes) -> None:
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, socket.error):
            self.close_connection = True

    def safe_send_error(self, code: int, message: str) -> None:
        try:
            self.send_error(code, message)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, socket.error):
            self.close_connection = True

    def access_manager(self) -> None:
        self.send_error(501, "Method 'access_manager' not implemented")


class RequestHandler(AccessManagerRequestHandler):
    def __init__(self, *args, **kwargs):
        self.query_params: dict[str, str | None | list[str | None]] = {}
        self.api: dict[str, str | None] = {"method": None, "service": None, "section": None}
        super().__init__(*args, **kwargs)

    def access_manager(self) -> None:
        self.query_params = {}
        self.api = {"method": self.command, "service": None, "section": None}

        parts = self.path.split("?", 1)
        request_path = parts[0] or "/"
        query_string = parts[1] if len(parts) > 1 else ""

        if request_path in ("/favicon.ico", "/.well-known/appspecific/com.chrome.devtools.json"):
            self.send_response(204, "No Content")
            self.end_headers()
            return

        if self.check_static_asset(request_path):
            return

        self.query_params = parse_query_string(query_string)

        if request_path == "/api" or request_path.startswith("/api/"):
            if self.command != "GET":
                self.send_error_json(405, f'Method "{self.command}" is not supported for API')
                return
            self.handle_api_get(request_path, self.query_params)
            return

        if request_path == "/" and self.command == "GET":
            self.render_analyzer_page(request_path, query_string, self.query_params)
            return

        if request_path == "/" and self.command == "LINK":
            self.send_response(200, "OK")
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.safe_write("LINK method response".encode("utf-8"))
            return

        if self.dispatch_to_controller(request_path):
            return

        if self.command == "GET":
            self.render_analyzer_page(request_path, query_string, self.query_params)
            return

        self.safe_send_error(404, f"Route '{request_path}' not found")

    def dispatch_to_controller(self, request_path: str) -> bool:
        service_raw, sections = split_route_path(request_path)
        service = service_raw if service_raw else "home"
        section = "/".join(sections) if sections else None
        self.api["service"] = service
        self.api["section"] = section

        if str(BASE_DIR) not in sys.path:
            sys.path.insert(0, str(BASE_DIR))

        module_name, class_name = normalize_controller_name(service)
        module_ref = f"controllers.{module_name}"

        try:
            controller_module = importlib.import_module(module_ref)
        except ModuleNotFoundError as ex:
            if ex.name in (module_ref, module_name):
                return False
            message = str(ex) if DEV_MODE else "Internal Server Error"
            self.safe_send_error(500, f"Import error: {message}")
            return True
        except Exception as ex:
            message = str(ex) if DEV_MODE else "Internal Server Error"
            self.safe_send_error(500, f"Import error: {message}")
            return True

        controller_class = getattr(controller_module, class_name, None)
        if controller_class is None:
            return False

        try:
            controller_object = controller_class(self)
            method_name = f"do_{self.command}"
            if hasattr(controller_object, method_name):
                getattr(controller_object, method_name)()
            elif hasattr(controller_object, "serve"):
                controller_object.serve()
            else:
                self.safe_send_error(405, f"Method {self.command} not supported by {class_name}")
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, socket.error):
            self.close_connection = True
        except Exception as ex:
            message = str(ex) if DEV_MODE else "Internal Server Error"
            self.safe_send_error(500, f"Routing error: {message}")
        return True

    def render_analyzer_page(
        self,
        path: str,
        query_string: str,
        query_params: dict[str, str | None | list[str | None]],
    ) -> None:
        service, sections = split_route_path(path)
        self.api["service"] = service
        self.api["section"] = "/".join(sections) if sections else None

        try:
            page_html = render_index_html(
                {
                    "self_path_display": html.escape(self.path),
                    "path_display": html.escape(path),
                    "query_string_display": html.escape(query_string if query_string else "None"),
                    "query_params_display": html.escape(str(query_params)),
                    "service_display": html.escape(service if service is not None else "None"),
                    "sections_display": html.escape(str(sections)),
                }
            )
        except FileNotFoundError:
            self.safe_send_error(500, f"Template not found: {TEMPLATE_PATH}")
            return
        except Exception as ex:
            message = str(ex) if DEV_MODE else "Internal Server Error"
            self.safe_send_error(500, f"Template render error: {message}")
            return

        self.send_response(200, "OK")
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.safe_write(page_html.encode("utf-8"))

    def send_json(self, status_code: int, payload: dict | list) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.safe_write(body)

    def send_error_json(self, status_code: int, message: str) -> None:
        self.send_json(status_code, {"error": {"status": status_code, "message": message}})

    def handle_api_get(self, path: str, query_params: dict[str, str | None | list[str | None]]) -> None:
        service, sections = split_route_path(path)
        if service != "api":
            self.send_error_json(404, "Resource not found")
            return

        if len(sections) == 0:
            self.send_json(200, {"data": [{"resource": "users", "href": "/api/users"}], "meta": {"count": 1}})
            return

        resource = sections[0]
        if resource != "users":
            self.send_error_json(404, f'Resource "{resource}" not found')
            return

        if len(sections) == 1:
            self.handle_users_collection(path, query_params)
            return

        if len(sections) == 2:
            self.handle_users_item(sections[1])
            return

        self.send_error_json(404, "Resource not found")

    def handle_users_collection(
        self,
        path: str,
        query_params: dict[str, str | None | list[str | None]],
    ) -> None:
        try:
            page = parse_int_param(get_query_param(query_params, "page"), "page", 1, minimum=1, maximum=1000000)
            per_page = parse_int_param(
                get_query_param(query_params, "per_page"),
                "per_page",
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
            "self": build_page_link(path, query_params, page, per_page),
            "first": build_page_link(path, query_params, 1, per_page),
            "last": build_page_link(path, query_params, max(total_pages, 1), per_page),
            "prev": build_page_link(path, query_params, page - 1, per_page) if has_prev else None,
            "next": build_page_link(path, query_params, page + 1, per_page) if has_next else None,
        }

        payload = {
            "data": data,
            "meta": {
                "count": len(data),
                "total_items": total_items,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total_pages": total_pages,
                    "has_prev": has_prev,
                    "has_next": has_next,
                },
            },
            "links": links,
        }
        self.send_json(200, payload)

    def handle_users_item(self, user_id_raw: str) -> None:
        try:
            user_id = int(user_id_raw)
        except ValueError:
            self.send_error_json(400, '"id" must be an integer')
            return

        user = next((item for item in USERS if item["id"] == user_id), None)
        if user is None:
            self.send_error_json(404, f"User with id={user_id} not found")
            return

        self.send_json(200, {"data": user})

    def check_static_asset(self, req_path: str) -> bool:
        if self.command != "GET":
            return False

        decoded_path = urllib.parse.unquote(req_path)
        rel_path = decoded_path.lstrip("/")

        if not rel_path or rel_path.endswith("/"):
            return False

        is_static_prefix = rel_path.startswith(("static/", "css/", "js/", "img/"))
        has_file_suffix = "." in Path(rel_path).name
        if not (is_static_prefix or has_file_suffix):
            return False

        if rel_path.startswith("static/"):
            rel_path = rel_path[7:]

        ext = Path(rel_path).suffix.lower().lstrip(".")
        if not ext:
            self.safe_send_error(400, f"Invalid static asset path: '{req_path}'")
            return True
        if ext not in STATIC_ALLOWED_TYPES:
            self.safe_send_error(415, f"Unsupported media type '.{ext}' for static asset")
            return True

        static_root = STATIC_DIR.resolve()
        file_candidates = [STATIC_DIR / rel_path]
        if "/" not in rel_path:
            fallback_dir = STATIC_FALLBACK_DIRS.get(ext)
            if fallback_dir:
                file_candidates.append(STATIC_DIR / fallback_dir / rel_path)

        file_path = None
        for candidate in file_candidates:
            resolved = candidate.resolve()
            try:
                resolved.relative_to(static_root)
            except ValueError:
                continue

            if resolved.exists() and resolved.is_file():
                file_path = resolved
                break

        if file_path is None:
            self.safe_send_error(404, f"Static asset '{req_path}' not found")
            return True

        try:
            payload = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", STATIC_ALLOWED_TYPES[ext])
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.safe_write(payload)
            return True
        except Exception:
            return False


def main() -> None:
    host, port = "127.0.0.1", 8080
    server = HTTPServer((host, port), RequestHandler)
    print(f"Server started at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
