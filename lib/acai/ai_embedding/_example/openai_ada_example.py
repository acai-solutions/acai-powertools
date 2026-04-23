"""
Example: OpenAI text-embedding-ada-002 adapter
===============================================

Run from this folder::

    python openai_ada_example.py

Or as a module from ``shared/python/``::

    python -m acai.ai_embedding._example.openai_ada_example

Demonstrates configuration, factory wiring, and a **live API call**
when ``OPENAI_API_KEY`` is present in the environment or a ``.env`` file.

Requirements
------------
- ``pip install openai python-dotenv``
- ``OPENAI_API_KEY=sk-…`` in the environment or ``.env``.
"""

import os
import sys
from pathlib import Path

_this_dir = Path(__file__).resolve().parent
_shared_python = _this_dir.parent.parent.parent
if str(_shared_python) not in sys.path:
    sys.path.insert(0, str(_shared_python))

from dotenv import load_dotenv

load_dotenv(_this_dir / ".env")
load_dotenv()

from acai.ai_embedding import create_embedder
from acai.ai_embedding.adapters.outbound.openai_ada_embedder import (
    OpenAIAdaConfig,
)
from acai.logging import LoggerConfig, LogLevel, create_logger


def main() -> None:
    logger = create_logger(
        LoggerConfig(service_name="openai-ada-example", log_level=LogLevel.DEBUG)
    )

    # ── 1. Adapter-specific config ────────────────────────────────────
    print("=== OpenAI Ada — Config ===")
    cfg = OpenAIAdaConfig(openai_api_key="demo-key")
    print(f"  Model:           {cfg.model_name}")
    print(f"  Max text length: {cfg.max_text_length}")

    # ── 2. Factory wiring ─────────────────────────────────────────────
    print("\n=== Factory ===")
    print("  create_embedder(logger, provider='openai_ada', api_key='…')")
    print("  Returns: OpenAIAdaEmbedder (text-embedding-ada-002)")

    # ── 3. Live API call ──────────────────────────────────────────────
    api_key = os.getenv("OPENAI_API_KEY", "")
    if api_key:
        print("\n=== Live API call ===")
        try:
            embedder = create_embedder(logger, provider="openai_ada", api_key=api_key)
            result = embedder.get_embedding("Swiss civil code article 1")
            print(f"  Model:      {result.model}")
            print(f"  Dimension:  {result.dimension}")
            print(f"  Normalized: {result.normalized}")
            print(f"  Tokens:     {result.token_count}")
            print(f"  First 5:    {result.vector[:5]}")
        except Exception as exc:
            print(f"  Error: {exc}")
    else:
        print("\n  [SKIP] OPENAI_API_KEY not set -- skipping live call")
        print("  Set it in .env or the environment to enable.")

    print("\nDone.")


if __name__ == "__main__":
    main()
