"""Launch the Waifu-Hoard-Hoarder server (nhentai downloader & browser).

Usage:
    python app.py              # serves frontend + API
    python app.py --dev        # enable auto-reload
    python app.py --port 9000  # custom port (default comes from config.json)
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

    parser = argparse.ArgumentParser(description="Waifu-Hoard-Hoarder")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=config.get("port", 8113))
    parser.add_argument("--dev", action="store_true", help="Enable reload for development")
    args = parser.parse_args()

    backend_dir = ROOT / "backend"
    cmd = [
        sys.executable, "-m", "uvicorn",
        "server:app",
        "--host", args.host,
        "--port", str(args.port),
    ]
    if args.dev:
        cmd.append("--reload")

    print(f"Starting Waifu-Hoard-Hoarder at http://{args.host}:{args.port}")
    subprocess.run(cmd, cwd=backend_dir)


if __name__ == "__main__":
    main()
