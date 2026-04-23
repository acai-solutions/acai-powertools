#!/usr/bin/env python3
"""Build a Lambda layer ZIP from selected acai modules.

Usage
-----
# Include all modules (default):
    python build_layer.py

# Include only specific modules:
    python build_layer.py --modules logging storage python_helper

# Include specific modules + auto-resolve dependencies:
    python build_layer.py --modules ai_embedding --resolve-deps

# List available modules and their dependencies:
    python build_layer.py --list

# Custom output path:
    python build_layer.py --output my_layer.zip
"""

from __future__ import annotations

import argparse
import json
import os
import platform as _platform
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

# ── Module dependency map (production-code imports only) ─────────────────────
# logging <-> storage is a circular dep; both are always included together.
DEPENDENCY_MAP: dict[str, list[str]] = {
    "ai_embedding": ["logging"],
    "ai_hybrid_search": ["logging"],
    "ai_llm": ["logging"],
    "ai_text_search": ["logging"],
    "ai_tools": [],
    "ai_vector_store": ["logging"],
    "aws_helper": ["logging"],
    "logging": ["storage"],
    "python_helper": [],
    "storage": ["logging"],
    "webcrawler": ["logging"],
    "xml_parser": ["logging"],
}

ALL_MODULES = sorted(DEPENDENCY_MAP)

LIB_DIR = Path(__file__).resolve().parent.parent.parent / "lib"
ACAI_PACKAGE_DIR = LIB_DIR / "acai"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "10-layer-source"
DEFAULT_ZIP_DIR = Path(__file__).resolve().parent / "20-zipped"
DEFAULT_ZIP_PATH = DEFAULT_ZIP_DIR / "acai_powertools_layer.zip"


def resolve_dependencies(modules: list[str]) -> list[str]:
    """Transitively resolve all dependencies for the given modules."""
    resolved: set[str] = set()
    queue = list(modules)
    while queue:
        mod = queue.pop()
        if mod in resolved:
            continue
        resolved.add(mod)
        for dep in DEPENDENCY_MAP.get(mod, []):
            if dep not in resolved:
                queue.append(dep)
    return sorted(resolved)


def validate_modules(modules: list[str]) -> None:
    """Raise SystemExit if any module name is invalid."""
    unknown = [m for m in modules if m not in DEPENDENCY_MAP]
    if unknown:
        print(f"ERROR: Unknown module(s): {', '.join(unknown)}", file=sys.stderr)
        print(f"Available: {', '.join(ALL_MODULES)}", file=sys.stderr)
        sys.exit(1)


def list_modules() -> None:
    """Print available modules and their dependencies."""
    print("Available acai modules:\n")
    max_name = max(len(m) for m in ALL_MODULES)
    for mod in ALL_MODULES:
        deps = DEPENDENCY_MAP[mod]
        dep_str = ", ".join(deps) if deps else "(none)"
        print(f"  {mod:<{max_name}}  deps: {dep_str}")
    print()


def collect_module_files(module_name: str) -> list[Path]:
    """Return all .py files in a module, excluding test/example dirs."""
    module_dir = ACAI_PACKAGE_DIR / module_name
    if not module_dir.is_dir():
        print(f"WARNING: Module directory not found: {module_dir}", file=sys.stderr)
        return []

    skip_dirs = {"_test", "_example", "_example_test", "__pycache__", ".pytest_cache"}
    files: list[Path] = []
    for root, dirs, filenames in os.walk(module_dir):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for fname in filenames:
            if fname.endswith(".py"):
                files.append(Path(root) / fname)
    return files


def build_layer_source(modules: list[str], output_dir: Path) -> None:
    """Copy selected modules into the Lambda layer directory structure."""
    output_dir = output_dir.resolve()

    # Validate that ACAI_PACKAGE_DIR exists
    if not ACAI_PACKAGE_DIR.exists():
        print(
            f"ERROR: ACAI package directory not found: {ACAI_PACKAGE_DIR}",
            file=sys.stderr,
        )
        print(
            "Expected structure: repo/lib/acai/",
            file=sys.stderr,
        )
        sys.exit(1)

    # Safety: never delete the actual source tree
    if output_dir == ACAI_PACKAGE_DIR or ACAI_PACKAGE_DIR.is_relative_to(output_dir):
        print(
            f"ERROR: output_dir ({output_dir}) overlaps with source ({ACAI_PACKAGE_DIR}). Aborting.",
            file=sys.stderr,
        )
        sys.exit(1)

    layer_acai_dir = output_dir / "python" / "acai"

    # Clean previous build
    if output_dir.exists():
        shutil.rmtree(output_dir)

    layer_acai_dir.mkdir(parents=True, exist_ok=True)

    # Copy package-level __init__.py
    pkg_init = ACAI_PACKAGE_DIR / "__init__.py"
    if pkg_init.exists():
        shutil.copy2(pkg_init, layer_acai_dir / "__init__.py")

    # Copy each selected module
    for mod in modules:
        src_dir = ACAI_PACKAGE_DIR / mod
        dst_dir = layer_acai_dir / mod
        if not src_dir.is_dir():
            print(f"WARNING: Skipping missing module: {mod}", file=sys.stderr)
            continue

        skip_dirs = {
            "_test",
            "_example",
            "_example_test",
            "__pycache__",
            ".pytest_cache",
        }

        def ignore_fn(_dir: str, entries: list[str]) -> list[str]:
            return [e for e in entries if e in skip_dirs or e.endswith(".pyc")]

        shutil.copytree(src_dir, dst_dir, ignore=ignore_fn)
        print(f"  + {mod}")

    print(f"\nLayer source written to: {output_dir}")


def create_zip(source_dir: Path, zip_path: Path) -> None:
    """Create a ZIP file from the layer source directory."""
    zip_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(source_dir):
            for fname in files:
                file_path = Path(root) / fname
                arcname = file_path.relative_to(source_dir)
                zf.write(file_path, arcname)

    size_kb = zip_path.stat().st_size / 1024
    print(f"ZIP created: {zip_path} ({size_kb:.1f} KB)")


def install_pip_packages(
    requirements: list[Path],
    source_dir: Path,
    platform: str | None = None,
    python_version: str | None = None,
) -> None:
    """Install pip packages from one or more requirements files into the layer source."""
    if not requirements:
        return

    target_dir = source_dir / "python"
    target_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "-t",
        str(target_dir),
        "--no-cache-dir",
        "--disable-pip-version-check",
    ]
    for req in requirements:
        cmd.extend(["-r", str(req)])

    if platform:
        cmd.extend(["--platform", platform, "--only-binary", ":all:"])
        # Cross-platform builds on non-Linux hosts can silently skip packages
        # that have no matching wheel for the target platform. Warn loudly.
        host = _platform.system().lower()
        if host != "linux":
            print(
                f"WARNING: building layer for '{platform}' from a {host!r} host. "
                "Packages with C extensions may be missing or unusable at runtime. "
                "For production builds, run this on Linux or inside a "
                "public.ecr.aws/sam/build-python<ver> container.",
                file=sys.stderr,
            )
    if python_version:
        cmd.extend(["--python-version", python_version, "--implementation", "cp"])

    print(f"\nInstalling pip packages from {len(requirements)} requirements file(s):")
    for req in requirements:
        print(f"  - {req}")
    if platform:
        print(f"  Target platform: {platform}")
    if python_version:
        print(f"  Python version:  {python_version}")

    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        print("ERROR: pip install failed.", file=sys.stderr)
        sys.exit(1)

    print("Pip packages installed successfully.")


def write_inline_files(inline_files: dict[str, str], source_dir: Path) -> None:
    """Write inline file content into source_dir/python/<key>.

    Keys must be relative paths (e.g. 'acme/logging_factory.py').
    Parent directories are created as needed.
    """
    if not inline_files:
        return

    target_root = source_dir / "python"
    target_root.mkdir(parents=True, exist_ok=True)

    print(f"\nWriting {len(inline_files)} inline file(s) into: {target_root}")
    for rel_path, content in inline_files.items():
        # Reject absolute paths and parent-directory escapes
        rel_path_obj = Path(rel_path)
        if rel_path_obj.is_absolute() or ".." in rel_path_obj.parts:
            print(f"ERROR: Invalid inline file path: {rel_path}", file=sys.stderr)
            sys.exit(1)

        target = target_root / rel_path_obj
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

        # Auto-create __init__.py for any new package directories
        for parent in target.parents:
            if parent == target_root:
                break
            init_file = parent / "__init__.py"
            if not init_file.exists():
                init_file.write_text("", encoding="utf-8")

        print(f"  + {rel_path}")


def _create_parser() -> argparse.ArgumentParser:
    """Create and return the argument parser."""
    parser = argparse.ArgumentParser(
        description="Build a Lambda layer ZIP from selected acai modules.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--modules",
        nargs="+",
        metavar="MODULE",
        help=f"Modules to include. Available: {', '.join(ALL_MODULES)}",
    )
    parser.add_argument(
        "--resolve-deps",
        action="store_true",
        default=False,
        help="Automatically include transitive dependencies of selected modules.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_ZIP_PATH,
        help=f"Output ZIP file path (default: {DEFAULT_ZIP_PATH})",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Intermediate layer source directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        default=False,
        help="List available modules and exit.",
    )
    parser.add_argument(
        "--no-zip",
        action="store_true",
        default=False,
        help="Only build the layer source directory, skip ZIP creation.",
    )
    parser.add_argument(
        "--requirements",
        action="store_true",
        default=False,
        help="Install pip packages from one or more requirements files. "
        "Paths are read as a JSON list from the PIP_REQUIREMENTS_JSON env var.",
    )
    parser.add_argument(
        "--pip-platform",
        type=str,
        default=None,
        help="Target platform for pip install (e.g., manylinux2014_aarch64). Enables cross-compilation with --only-binary :all:.",
    )
    parser.add_argument(
        "--pip-python-version",
        type=str,
        default=None,
        help="Target Python version for pip install (e.g., 312 for Python 3.12).",
    )
    parser.add_argument(
        "--no-acai",
        action="store_true",
        default=False,
        help="Skip acai module collection. Use with --requirements for pip-only layers.",
    )
    parser.add_argument(
        "--inline-files",
        action="store_true",
        default=False,
        help="Write inline files from the INLINE_FILES_JSON env var into the layer.",
    )
    return parser


def _select_modules(args: argparse.Namespace) -> list[str] | None:
    """Determine which modules to include. Return None if --list was used."""
    if args.list:
        return None

    if args.modules:
        try:
            validate_modules(args.modules)
        except SystemExit:
            sys.exit(1)

        modules = list(args.modules)
        if args.resolve_deps:
            original = set(modules)
            modules = resolve_dependencies(modules)
            added = sorted(set(modules) - original)
            if added:
                print(f"Auto-resolved dependencies: {', '.join(added)}")
    else:
        modules = list(ALL_MODULES)

    if not modules:
        print("ERROR: No modules to build.", file=sys.stderr)
        sys.exit(1)

    return modules


def _validate_no_acai_args(args: argparse.Namespace) -> None:
    """Validate --no-acai flag combinations."""
    if args.no_acai and args.modules:
        print(
            "ERROR: --no-acai cannot be combined with --modules.",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.no_acai and not args.requirements and not args.inline_files:
        print(
            "ERROR: --no-acai requires --requirements and/or --inline-files.",
            file=sys.stderr,
        )
        sys.exit(1)


def _process_inline_files(args: argparse.Namespace) -> None:
    """Parse INLINE_FILES_JSON env var and write files into the layer."""
    if not args.inline_files:
        return

    inline_json = os.environ.get("INLINE_FILES_JSON", "")
    if not inline_json:
        return

    try:
        inline_files_map = json.loads(inline_json)
    except json.JSONDecodeError as exc:
        print(
            f"ERROR: INLINE_FILES_JSON is not valid JSON: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    if not isinstance(inline_files_map, dict):
        print(
            "ERROR: INLINE_FILES_JSON must decode to a JSON object.",
            file=sys.stderr,
        )
        sys.exit(1)

    write_inline_files(inline_files_map, args.source_dir)


def _resolve_requirements_paths(source_dir: Path) -> list[Path]:
    """Materialise pip requirement specs into a single requirements.txt file.

    PIP_REQUIREMENTS_JSON is expected to be a JSON array of pip requirement
    spec strings (e.g. ["requests==2.32.3", "aws-lambda-powertools==2.43.1"]).
    They are written verbatim to a temp file (outside ``source_dir`` so the
    file does not end up inside the layer ZIP) so pip can consume them via
    ``-r``.
    """
    raw_json = os.environ.get("PIP_REQUIREMENTS_JSON", "").strip()
    if not raw_json:
        print(
            "ERROR: --requirements was passed but PIP_REQUIREMENTS_JSON is not set.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        specs = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        print(
            f"ERROR: PIP_REQUIREMENTS_JSON is not valid JSON: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)
    if not isinstance(specs, list) or not all(isinstance(s, str) for s in specs):
        print(
            "ERROR: PIP_REQUIREMENTS_JSON must decode to a JSON array of strings.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Write outside source_dir so it is NOT included in the layer ZIP.
    tmp_dir = Path(tempfile.mkdtemp(prefix="acai_layer_pip_"))
    req_file = tmp_dir / "requirements.txt"
    req_file.write_text("\n".join(specs) + "\n", encoding="utf-8")
    print(f"Wrote {len(specs)} pip requirement spec(s) to: {req_file}")
    return [req_file]


def main() -> None:
    parser = _create_parser()
    args = parser.parse_args()

    if args.list:
        list_modules()
        return

    _validate_no_acai_args(args)

    try:
        if not args.no_acai:
            modules = _select_modules(args)
            if modules is None:
                return
            print(f"Building Lambda layer with {len(modules)} module(s):\n")
            build_layer_source(modules, args.source_dir)
        else:
            print("Building Lambda layer (pip packages only):\n")
            if args.source_dir.exists():
                shutil.rmtree(args.source_dir)
            (args.source_dir / "python").mkdir(parents=True, exist_ok=True)

        if args.requirements:
            install_pip_packages(
                _resolve_requirements_paths(args.source_dir),
                args.source_dir,
                args.pip_platform,
                args.pip_python_version,
            )

        _process_inline_files(args)

        if not args.no_zip:
            create_zip(args.source_dir, args.output)

        print("\nDone.")
    except Exception as e:
        print(f"ERROR: Build failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
