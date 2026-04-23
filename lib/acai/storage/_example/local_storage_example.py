"""
Example: Local file storage
============================

Run directly::

    python -m acai.storage._example.local_storage_example

Demonstrates read/write, JSON round-trip, extension validation,
context-manager cleanup, and the ``create_storage`` factory.
"""

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from acai.logging import LoggerConfig, LogLevel, create_logger
from acai.storage import StorageConfig, ValidationError, create_storage


@dataclass
class LawRef:
    sr_number: str
    title: str
    language: str


def main() -> None:
    work_dir = Path(tempfile.mkdtemp(prefix="acai_storage_example_"))
    logger = create_logger(
        LoggerConfig(service_name="storage-example", log_level=LogLevel.DEBUG)
    )
    storage = create_storage(logger)

    try:
        # ── 1. Plain text round-trip ──────────────────────────────────
        txt_path = work_dir / "hello.txt"
        storage.save(txt_path, "Hello from acai.storage!")
        print(f"[text]  Wrote: {txt_path}")
        print(f"[text]  Read : {storage.read(txt_path)}")

        # ── 2. JSON round-trip with dataclass deserialisation ─────────
        refs = [
            LawRef("SR 210", "Zivilgesetzbuch", "de"),
            LawRef("SR 220", "Obligationenrecht", "de"),
        ]
        json_path = work_dir / "refs.json"
        storage.save_json(json_path, refs)
        print(f"\n[json]  Wrote {len(refs)} records to {json_path}")

        loaded = storage.read_json(json_path, data_type=LawRef)
        for ref in loaded:
            print(f"[json]  Loaded: {ref}")

        # ── 3. Missing file returns empty defaults ────────────────────
        print(f"\n[miss]  read()      → '{storage.read(work_dir / 'nope.txt')}'")
        print(f"[miss]  read_json() → {storage.read_json(work_dir / 'nope.json')}")
        print(f"[miss]  exists()    → {storage.exists(work_dir / 'nope.txt')}")

        # ── 4. Extension validation ───────────────────────────────────
        restricted_cfg = StorageConfig(allowed_extensions={"txt", "json"})
        restricted = create_storage(logger, restricted_cfg)
        try:
            restricted.save(work_dir / "bad.xml", "<root/>")
            print("\n[ext]   ERROR — should have raised ValidationError")
        except ValidationError as exc:
            print(f"\n[ext]   Blocked as expected: {exc}")

        # ── 5. Context-manager cleanup ────────────────────────────────
        with create_storage(logger) as ctx_store:
            ctx_store.save(work_dir / "ctx.txt", "inside context manager")
            print("\n[ctx]   Written inside context manager")
        print("[ctx]   Context manager exited (temp files cleaned)")

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        print(f"\nCleaned up {work_dir}")


if __name__ == "__main__":
    main()
