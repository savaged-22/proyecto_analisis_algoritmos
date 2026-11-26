"""La API local de la interfaz responde y la traza trae lo que la página necesita."""

import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from src.ui.server import make_handler

SCENARIOS = Path(__file__).resolve().parent.parent / "data" / "scenarios"


class UiServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(SCENARIOS))
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def get(self, path: str):
        with urllib.request.urlopen(self.base + path) as res:
            return res.status, res.read()

    def post(self, payload: dict):
        req = urllib.request.Request(self.base + "/api/run", data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req) as res:
                return res.status, json.loads(res.read())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read())

    def test_serves_page_and_scenarios(self) -> None:
        status, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn(b"app.js", body)
        status, body = self.get("/api/scenarios")
        names = json.loads(body)["scenarios"]
        self.assertEqual(names[0], "inicial")
        self.assertIn("F_imposible", names)

    def test_run_returns_full_trace(self) -> None:
        scenario = json.loads((SCENARIOS / "inicial.json").read_text(encoding="utf-8"))
        status, trace = self.post({"scenario": scenario, "mode": "exacto"})
        self.assertEqual(status, 200)
        self.assertEqual(trace["result"]["metrics"]["violations_total"], 0)
        self.assertEqual(len(trace["graph"]["nodes"]), 8)
        self.assertTrue(trace["phase1"]["dsatur_steps"][0]["candidates"])
        self.assertTrue(trace["phase1"]["search_trace"])
        dp = trace["phase2"]["dp"]["E01"]
        self.assertEqual(len(dp["opt"]), len(dp["items"]) + 1)
        self.assertTrue(all(c["passed"] for c in trace["expectations"]))

    def test_invalid_scenario_returns_clear_error(self) -> None:
        scenario = json.loads((SCENARIOS / "inicial.json").read_text(encoding="utf-8"))
        scenario["students"][0]["requests"][0]["priority"] = 5
        status, body = self.post({"scenario": scenario, "mode": "auto"})
        self.assertEqual(status, 400)
        self.assertIn("Prioridad 5", body["error"])

    def test_static_files_cannot_escape_their_folder(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.get("/static/../server.py")
        self.assertEqual(ctx.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
