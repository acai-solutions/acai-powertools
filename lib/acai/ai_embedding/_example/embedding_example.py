"""
Example: All embedding adapters
================================

Run from this folder::

    python embedding_example.py

Or as a module from ``shared/python/``::

    python -m acai.ai_embedding._example.embedding_example

Runs each per-adapter example in sequence:

- ``openai_large_example.py``  — OpenAI text-embedding-3-large
- ``openai_ada_example.py``    — OpenAI text-embedding-ada-002
- ``bedrock_titan_example.py`` — Amazon Bedrock Titan
- ``voyageai_example.py``      — Voyage AI

Each adapter example can also be run standalone.

.env setup
----------
Create a ``.env`` file in this folder (or any parent) with real keys
to enable the live-call sections::

    OPENAI_API_KEY=sk-...
    VOYAGEAI_API_KEY=pa-...
    AWS_PROFILE=my-profile          # optional, for Bedrock Titan
"""

import sys
from pathlib import Path

_this_dir = Path(__file__).resolve().parent
_shared_python = _this_dir.parent.parent.parent
if str(_shared_python) not in sys.path:
    sys.path.insert(0, str(_shared_python))

from acai.ai_embedding._example.bedrock_titan_example import main as bedrock_titan_main
from acai.ai_embedding._example.openai_ada_example import main as openai_ada_main
from acai.ai_embedding._example.openai_large_example import main as openai_large_main
from acai.ai_embedding._example.voyageai_example import main as voyageai_main


def main() -> None:
    divider = "=" * 60

    print(divider)
    print("  OpenAI text-embedding-3-large")
    print(divider)
    openai_large_main()

    print(f"\n{divider}")
    print("  OpenAI text-embedding-ada-002")
    print(divider)
    openai_ada_main()

    print(f"\n{divider}")
    print("  Amazon Bedrock Titan")
    print(divider)
    bedrock_titan_main()

    print(f"\n{divider}")
    print("  Voyage AI")
    print(divider)
    voyageai_main()


if __name__ == "__main__":
    main()
