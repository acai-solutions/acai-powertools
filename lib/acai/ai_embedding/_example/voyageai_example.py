"""
Example: Voyage AI embedding adapter
=====================================

Run from this folder::

    python voyageai_example.py

Or as a module from ``shared/python/``::

    python -m acai.ai_embedding._example.voyageai_example

Demonstrates configuration, normalization, input types, factory wiring,
and a **live API call** when ``VOYAGEAI_API_KEY`` is present.

Requirements
------------
- ``pip install voyageai python-dotenv``
- ``VOYAGEAI_API_KEY=pa-…`` in the environment or ``.env``.
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
from acai.ai_embedding.adapters.outbound.voyageai_embedder import (
    VoyageAIConfig,
    VoyageAIEmbedder,
)
from acai.logging import LoggerConfig, LogLevel, create_logger


def main() -> None:
    logger = create_logger(
        LoggerConfig(service_name="voyageai-example", log_level=LogLevel.DEBUG)
    )

    # ── 1. Adapter-specific config ────────────────────────────────────
    print("=== VoyageAI — Config ===")
    cfg = VoyageAIConfig(
        api_key="demo-key",
        model_name="voyage-3",
        normalize=True,
        input_type="document",
    )
    print(f"  Model:      {cfg.model_name}")
    print(f"  Normalize:  {cfg.normalize}")
    print(f"  Input type: {cfg.input_type}")
    print(f"  Max batch:  {cfg.max_batch_size}")

    # ── 2. Normalization (pure math, no API call) ─────────────────────
    print("\n=== Vector normalization ===")
    raw = [3.0, 4.0]
    normalized = VoyageAIEmbedder._normalize(raw)
    print(f"  Raw:        {raw}")
    print(f"  Normalized: {normalized}")
    print(f"  L2 norm:    {sum(x * x for x in normalized) ** 0.5:.6f}")

    zero = [0.0, 0.0, 0.0]
    print(f"  Zero vec:   {VoyageAIEmbedder._normalize(zero)}  (unchanged)")

    # ── 3. Factory wiring ─────────────────────────────────────────────
    print("\n=== Factory ===")
    print("  create_embedder(logger, provider='voyageai', api_key='…')")
    print(
        "  create_embedder(logger, provider='voyageai', api_key='…', model_name='voyage-3')"
    )
    print("  Returns: VoyageAIEmbedder")

    # ── 4. Live API call ──────────────────────────────────────────────
    api_key = os.getenv("VOYAGEAI_API_KEY", "")
    if api_key:
        print("\n=== Live API call ===")
        embedder = create_embedder(logger, provider="voyageai", api_key=api_key)
        result = embedder.get_embedding("Swiss civil code article 1")
        print(f"  Model:      {result.model}")
        print(f"  Dimension:  {result.dimension}")
        print(f"  Normalized: {result.normalized}")
        print(f"  Input type: {result.input_type}")
        print(f"  Tokens:     {result.token_count}")
        print(f"  First 5:    {result.vector[:5]}")

        results = embedder.get_embeddings(["Hello", "World"])
        print(f"  Batch:      {len(results)} results, dim={results[0].dimension}")
    else:
        print("\n  [SKIP] VOYAGEAI_API_KEY not set -- skipping live call")
        print("  Set it in .env or the environment to enable.")

    print("\nDone.")


if __name__ == "__main__":
    main()
