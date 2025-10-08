from __future__ import annotations

import difflib
import json
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from .manager import ContainerManager, find_project_root


def _zip_test_case(src_dir: Path, zip_path: Path) -> None:
    """
    Recursively zip the contents of `src_dir` (excluding `golden_results`)
    into `zip_path`.
    """
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as zf:
        for p in src_dir.rglob("*"):
            if "golden_results" in p.parts:
                continue
            if p.is_file():
                arcname = p.relative_to(src_dir)
                zf.write(p, arcname)


def _clean_data_dirs(data_dir: Path) -> None:
    """Remove contents of unzip, results, and scan dirs; recreate them."""
    for name in ("unzip", "results", "scan"):
        d = data_dir / name
        if d.exists():
            for f in sorted(d.rglob("*"), reverse=True):
                try:
                    if f.is_file() or f.is_symlink():
                        f.unlink()
                    else:
                        f.rmdir()
                except Exception:
                    pass
            try:
                d.rmdir()
            except Exception:
                pass
        d.mkdir(parents=True, exist_ok=True)


def _slurp_raw_reports(results_dir: Path) -> list[dict]:
    """
    Emulate: jq -s 'sort_by(.scanned_url)' results/*.json

    Read each per-page JSON report (raw axe report we saved), ensure it has
    a top-level 'scanned_url' (we now write it in PlaywrightAxeService), and
    return a list sorted by that key.
    """
    items: list[dict] = []
    for f in sorted(results_dir.glob("*.json")):
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            if "scanned_url" not in data:
                data["scanned_url"] = data.get("url", "")
            items.append(data)
        except Exception:
            continue

    items.sort(key=lambda d: d.get("scanned_url", ""))
    return items


def _unified_diff_str(a: str, b: str, fromfile: str, tofile: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            a.splitlines(),
            b.splitlines(),
            fromfile=fromfile,
            tofile=tofile,
            lineterm="",
        )
    )


def main() -> int:
    print("--- A11y Scanner: Integration Test Suite (Docker SDK) ---")
    project_root = find_project_root()
    tests_assets = project_root / "tests" / "assets" / "html_sets"
    data_dir = project_root / "data"
    unzip_dir = data_dir / "unzip"
    results_dir = data_dir / "results"

    if not tests_assets.exists():
        print(f"ERROR: Assets directory not found: {tests_assets}", file=sys.stderr)
        return 1

    manager = ContainerManager(project_root=project_root)
    if hasattr(manager, "ensure_image"):
        manager.ensure_image()
    else:
        manager.ensure_base_image()  # type: ignore[attr-defined]

    failures: list[str] = []

    for test_case_dir in sorted(p for p in tests_assets.iterdir() if p.is_dir()):
        test_case_name = test_case_dir.name
        print(f"\n--- Running Test Case: {test_case_name} ---")

        # 1) Prepare inputs
        print("[PREPARE] Cleaning 'data' directories and creating input zip...")
        _clean_data_dirs(data_dir)
        zip_path = unzip_dir / "site.zip"
        _zip_test_case(test_case_dir, zip_path)

        # 2) Execute
        print("[EXECUTE] Running scanner container...")
        exit_code = manager.run_scanner(stream_logs=False)
        if exit_code != 0:
            print(
                f"[ERROR] Scanner exited with code {exit_code}",
                file=sys.stderr,
            )
            failures.append(test_case_name)
            continue

        # 3) Verify
        print("[VERIFY] Comparing results to golden file...")
        golden_file = test_case_dir / "golden_results" / "report.json"
        if not golden_file.exists():
            print(
                f"❌ FAILURE: Golden file not found for '{test_case_name}'.",
                file=sys.stderr,
            )
            failures.append(test_case_name)
            continue

        actual_list = _slurp_raw_reports(results_dir)
        actual_str = json.dumps(actual_list, indent=2, sort_keys=True)

        try:
            with open(golden_file, encoding="utf-8") as fh:
                golden_str = fh.read()
        except Exception as e:
            print(
                f"❌ FAILURE: Could not read golden file for '{test_case_name}': {e}",
                file=sys.stderr,
            )
            failures.append(test_case_name)
            continue

        if actual_str.strip() == golden_str.strip():
            print(f"✅ SUCCESS: '{test_case_name}' matches the golden file.")
        else:
            print(
                f"❌ FAILURE: '{test_case_name}' does not match golden.",
                file=sys.stderr,
            )
            diff = _unified_diff_str(
                golden_str, actual_str, fromfile="golden", tofile="actual"
            )
            print(diff)
            failures.append(test_case_name)

    if failures:
        print("\n--- FAILURES ---")
        for name in failures:
            print(f"- {name}")
        return 1

    print("\n--- ✅ All integration tests passed successfully! ---")
    return 0


if __name__ == "__main__":
    sys.exit(main())
