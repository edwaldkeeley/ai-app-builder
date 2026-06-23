#!/usr/bin/env python3
"""One-command launcher for the AI Design Sandbox.

Usage::

    python run.py          # start backend only
    python run.py --all    # start backend + frontend (requires Node.js)
"""

from __future__ import annotations

import subprocess
import sys

from backend.app.config import settings


def start_backend():
    print("─" * 50)
    print("  Starting backend…")
    print("─" * 50)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            settings.host,
            "--port",
            str(settings.port),
            "--reload",
        ],
        cwd=settings.sandbox_dir.parent,
    )


def start_frontend():
    print("─" * 50)
    print("  Starting frontend (Next.js)…")
    print("─" * 50)
    subprocess.run(["npm", "run", "dev"], cwd=settings.sandbox_dir.parent / "frontend")


if __name__ == "__main__":
    if "--all" in sys.argv:
        import threading

        t = threading.Thread(target=start_frontend, daemon=True)
        t.start()
        start_backend()
    else:
        start_backend()
