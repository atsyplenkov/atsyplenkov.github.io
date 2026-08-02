#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# ///

"""Clean production-equivalent build + black-box site audit.

This is the single local/CI acceptance entrypoint for the migration work.
It never reuses a previous `_site` tree: the output directory is removed
before the forced production build runs.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SITE_DIR = REPO_ROOT / "_site"
BUILD_PY = REPO_ROOT / "build.py"
AUDIT_PY = REPO_ROOT / "scripts" / "audit_site.py"


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-self-test",
        action="store_true",
        help="Skip the audit's controlled-failure self-test",
    )
    args = parser.parse_args(argv)

    if not args.skip_self_test:
        run([sys.executable, str(AUDIT_PY), "--self-test"])

    if SITE_DIR.exists():
        print(f"removing stale site directory: {SITE_DIR}", flush=True)
        shutil.rmtree(SITE_DIR)

    run([sys.executable, str(BUILD_PY), "build", "--force"])
    run([sys.executable, str(AUDIT_PY), "--site", str(SITE_DIR)])
    print("acceptance passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"acceptance failed with exit code {exc.returncode}", file=sys.stderr)
        raise SystemExit(exc.returncode) from exc
