from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from scanner.container.manager import ContainerManager
from scanner.reporting.jinja_report import build_report


def _project_root(path: Path | None) -> Path:
    return (path or Path.cwd()).resolve()


def cmd_prepare(args: argparse.Namespace) -> int:
    mgr = ContainerManager(project_root=args.project_root)
    mgr.prepare_cached_image()
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    root = _project_root(args.project_root)
    data_unzip = root / "data" / "unzip"
    data_unzip.mkdir(parents=True, exist_ok=True)

    # If a ZIP is provided, copy it into data/unzip/site.zip for the pipeline
    if args.zip_path:
        src = Path(args.zip_path).expanduser().resolve()
        if not src.exists():
            print(f"ERROR: ZIP not found: {src}", file=sys.stderr)
            return 2
        dest = data_unzip / "site.zip"
        shutil.copyfile(src, dest)
        print(f"Copied {src} -> {dest}")

    mgr = ContainerManager(project_root=root)
    return mgr.run_scanner(
        use_cache=not args.no_cache, rebuild_cache=args.rebuild_cache, stream_logs=True
    )


def cmd_live(args: argparse.Namespace) -> int:
    mgr = ContainerManager(project_root=args.project_root)
    env = {}
    if args.base_url:
        env["A11Y_BASE_URL"] = args.base_url
    if args.pages:
        env["A11Y_PAGES"] = args.pages
    return mgr.run_live_scan(
        use_cache=not args.no_cache, rebuild_cache=args.rebuild_cache, extra_env=env
    )


def cmd_report(args: argparse.Namespace) -> int:
    root = _project_root(args.project_root)
    results_dir = (args.results_dir or (root / "data" / "results")).resolve()
    output_html = (args.output or (root / "data" / "reports" / "latest.html")).resolve()
    build_report(results_dir, output_html, title=args.title)
    print(f"HTML: {output_html}")
    print(f"JSON: {output_html.with_suffix('.json')}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="a11y", description="a11y-scanner CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    # prepare
    sp = sub.add_parser("prepare", help="Build the cached container image")
    sp.add_argument("--project-root", type=Path, default=None)
    sp.set_defaults(func=cmd_prepare)

    # scan (zip)
    sp = sub.add_parser("scan", help="Scan a static site ZIP in a container")
    sp.add_argument("--zip-path", type=Path, default=None, help="Path to site.zip")
    sp.add_argument("--project-root", type=Path, default=None)
    sp.add_argument("--no-cache", action="store_true")
    sp.add_argument("--rebuild-cache", action="store_true")
    sp.set_defaults(func=cmd_scan)

    # live
    sp = sub.add_parser("live", help="Scan live URLs (set base URL and optional pages)")
    sp.add_argument("--base-url", type=str, required=True, help="Base URL e.g. https://example.com")
    sp.add_argument(
        "--pages",
        type=str,
        default="/",
        help="Comma-separated list of paths (e.g. /,/about,/contact)",
    )
    sp.add_argument("--project-root", type=Path, default=None)
    sp.add_argument("--no-cache", action="store_true")
    sp.add_argument("--rebuild-cache", action="store_true")
    sp.set_defaults(func=cmd_live)

    # report (local build)
    sp = sub.add_parser("report", help="Build a consolidated HTML+JSON report from results/")
    sp.add_argument("--project-root", type=Path, default=None)
    sp.add_argument("--results-dir", type=Path, default=None)
    sp.add_argument("--output", type=Path, default=None)
    sp.add_argument("--title", type=str, default="Accessibility Report")
    sp.set_defaults(func=cmd_report)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

