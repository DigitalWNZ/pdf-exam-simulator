"""serve: run the local Exam Sim server and open the browser."""
from __future__ import annotations

import argparse
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

from .app import WEB_DIR, create_app


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="serve", description=__doc__)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--banks", type=Path, default=Path("banks"))
    ap.add_argument("--data", type=Path, default=Path("data"))
    ap.add_argument("--web", type=Path, default=WEB_DIR)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args(argv)

    app = create_app(args.banks, args.data, args.web)
    server = uvicorn.Server(uvicorn.Config(app, host=args.host, port=args.port, log_level="info"))
    url = f"http://{args.host}:{args.port}/"
    if not args.no_browser:
        def _open_when_ready() -> None:
            while not server.started:
                time.sleep(0.1)
            webbrowser.open(url)
        threading.Thread(target=_open_when_ready, daemon=True).start()
    print(f"Exam Sim: {url}  (banks={args.banks}, data={args.data}, web={args.web})")
    server.run()
    return 0
