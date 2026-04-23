"""
Example: Amazon Bedrock Titan embedding adapter
================================================

Run from this folder::

    python bedrock_titan_example.py

Or as a module from ``shared/python/``::

    python -m acai.ai_embedding._example.bedrock_titan_example

Demonstrates configuration, factory wiring, and a **live API call**
when AWS credentials are available (profile or environment variables).

Requirements
------------
- ``pip install boto3 python-dotenv``
- AWS credentials configured (``AWS_PROFILE`` or standard env vars).
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
from acai.logging import LoggerConfig, LogLevel, create_logger

try:
    from acai.ai_embedding.adapters.outbound.bedrock_titan_embedder import (
        BedrockTitanConfig,
        BedrockTitanEmbedder,
    )

    _HAS_BOTO3 = True
except ModuleNotFoundError:
    _HAS_BOTO3 = False


def main() -> None:
    logger = create_logger(
        LoggerConfig(service_name="bedrock-titan-example", log_level=LogLevel.DEBUG)
    )

    if not _HAS_BOTO3:
        print("=== Bedrock Titan ===")
        print("  [SKIP] boto3 not installed -- skipping Bedrock Titan example")
        print("  Install with: pip install boto3")
        print("\nDone.")
        return

    # ── 1. Adapter-specific config ────────────────────────────────────
    print("=== Bedrock Titan — Config ===")
    cfg = BedrockTitanConfig()
    print(f"  Model ID:          {BedrockTitanEmbedder.MODEL_ID}")
    print(f"  Region:            {cfg.bedrock_service_region}")
    print(f"  Max text length:   {cfg.max_text_length}")
    print(f"  Retry attempts:    {cfg.retry_attempts}")

    # ── 2. Factory wiring ─────────────────────────────────────────────
    print("\n=== Factory ===")
    print("  create_embedder(logger, provider='bedrock_titan')")
    print(
        "  create_embedder(logger, provider='bedrock_titan', aws_profile='my-profile')"
    )
    print("  Returns: BedrockTitanEmbedder (amazon.titan-embed-text-v1)")

    # ── 3. Live API call ──────────────────────────────────────────────
    aws_profile = os.getenv("AWS_PROFILE", "")
    if aws_profile:
        print(f"\n=== Live API call (profile: {aws_profile}) ===")
        try:
            embedder = create_embedder(
                logger,
                provider="bedrock_titan",
                aws_profile=aws_profile,
            )
            vec = embedder.get_embedding("Swiss civil code article 1")
            print(f"  Model:      {vec.model}")
            print(f"  Dimension:  {vec.dimension}")
            print(f"  Normalized: {vec.normalized}")
            print(f"  Tokens:     {vec.token_count}")
            print(f"  First 5:    {vec.vector[:5]}")
        except Exception as exc:
            print(f"  Error: {exc}")
    else:
        print("\n  [SKIP] AWS_PROFILE not set -- skipping live call")
        print("  Set it in .env or the environment to enable.")

    print("\nDone.")


if __name__ == "__main__":
    main()
