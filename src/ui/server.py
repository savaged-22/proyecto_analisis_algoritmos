"""Servidor local de la interfaz (solo biblioteca estándar).

    python main.py --ui            -> http://127.0.0.1:8000

Rutas:
    GET  /                       página de la interfaz (static/index.html)
    GET  /static/<archivo>       archivos de la interfaz
    GET  /api/scenarios          escenarios disponibles en data/scenarios
    GET  /api/scenario?name=X    contenido de un escenario
    POST /api/run                {"scenario": {...}, "mode": "auto"} -> traza de la ejecución

Solo escucha en 127.0.0.1: no queda expuesto a la red.
"""

import json
import mimetypes
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .. import config
from ..data.scenario import ScenarioError
from ..phase1.brute_force import InstanceTooLargeError
from ..solver.orchestrator import TimetableOrchestrator
from .trace import build_trace

STATIC_DIR = Path(__file__).resolve().parent / "static"


def make_handler(scenarios_dir: Path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            url = urlparse(self.path)
            if url.path in ("/", "/index.html"):
                return self._file(STATIC_DIR / "index.html")
            if url.path.startswith("/static/"):
                target = (STATIC_DIR / url.path[len("/static/"):]).resolve()
                if STATIC_DIR in target.parents and target.is_file():
                    return self._file(target)
                return self._json({"error": "No encontrado"}, HTTPStatus.NOT_FOUND)
            if url.path == "/api/scenarios":
                names = sorted(p.stem for p in scenarios_dir.glob("*.json"))
                names.sort(key=lambda n: (n != "demo", n))
                return self._json({"scenarios": names, "modes": list(config.PHASE1_MODES),
                                   "default_mode": config.DEFAULT_PHASE1_MODE})
            if url.path == "/api/scenario":
                name = parse_qs(url.query).get("name", [""])[0]
                path = (scenarios_dir / f"{name}.json").resolve()
                if path.parent != scenarios_dir.resolve() or not path.is_file():
                    return self._json({"error": f"No existe el escenario '{name}'"}, HTTPStatus.NOT_FOUND)
                return self._json(json.loads(path.read_text(encoding="utf-8")))
            return self._json({"error": "No encontrado"}, HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            if urlparse(self.path).path != "/api/run":
                return self._json({"error": "No encontrado"}, HTTPStatus.NOT_FOUND)
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length) or b"{}")
                orch = TimetableOrchestrator()
                orch.load_scenario_dict(body.get("scenario", {}))
                result = orch.run(phase1_mode=body.get("mode", config.DEFAULT_PHASE1_MODE))
                return self._json(build_trace(orch, result))
            except (ScenarioError, InstanceTooLargeError, ValueError, KeyError, TypeError) as exc:
                return self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

        def _file(self, path: Path) -> None:
            data = path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", (mimetypes.guess_type(path.name)[0] or "text/plain") + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _json(self, payload, status: HTTPStatus = HTTPStatus.OK) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, fmt: str, *args) -> None:   # consola limpia durante la demostración
            pass

    return Handler


def serve(scenarios_dir: Path, port: int = 8000, open_browser: bool = True) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(scenarios_dir))
    url = f"http://127.0.0.1:{port}"
    print(f"Interfaz en {url}  (Ctrl+C para detener)")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nInterfaz detenida.")
    finally:
        server.server_close()
