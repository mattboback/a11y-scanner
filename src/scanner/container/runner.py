from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .manager import ContainerManager


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the a11y-scanner in a Playwright container "
            "using the Docker SDK (with caching)."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # prepare cache image
    prep = subparsers.add_parser(
        "prepare", help="Build or rebuild the cached image (python3-venv + deps)."
    )
    prep.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help=(
            "Path to the project root (where pyproject.toml lives). "
            "Defaults to auto-discovery."
        ),
    )

    # run scan (one-off)
    run = subparsers.add_parser(
        "run", help="Run a one-off scan (site.zip -> results) in a container."
    )
    run.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help=(
            "Path to the project root (where pyproject.toml lives). "
            "Defaults to auto-discovery."
        ),
    )
    run.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable cache (run slow path: apt-get + pip every time).",
    )
    run.add_argument(
        "--rebuild-cache",
        action="store_true",
        help="Force rebuild of the cached image before running.",
    )

    # serve API (long-running)
    serve = subparsers.add_parser(
        "serve", help="Run the FastAPI server in a container and expose port 8008."
    )
    serve.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help=(
            "Path to the project root (where pyproject.toml lives). "
            "Defaults to auto-discovery."
        ),
    )
    serve.add_argument(
        "--port",
        type=int,
        default=8008,
        help="Host port to bind to the container's 8008/tcp (default: 8008).",
    )
    serve.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable cache (run slow path: apt-get + pip every time).",
    )
    serve.add_argument(
        "--rebuild-cache",
        action="store_true",
        help="Force rebuild of the cached image before running.",
    )

    args = parser.parse_args(argv)

    if args.command == "prepare":
        mgr = ContainerManager(project_root=args.project_root)
        try:
            ref = mgr.prepare_cached_image()
            print(ref)
            return 0
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1

    if args.command == "run":
        mgr = ContainerManager(project_root=args.project_root)
        try:
            return mgr.run_scanner(
                use_cache=not args.no_cache,
                rebuild_cache=args.rebuild_cache,
                stream_logs=True,
            )
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1

    if args.command == "serve":
        mgr = ContainerManager(project_root=args.project_root)
        try:
            return mgr.run_api_server(
                host_port=args.port,
                use_cache=not args.no_cache,
                rebuild_cache=args.rebuild_cache,
                stream_logs=True,
            )
        except KeyboardInterrupt:
            print("\nInterrupted by user.")
            return 130
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
