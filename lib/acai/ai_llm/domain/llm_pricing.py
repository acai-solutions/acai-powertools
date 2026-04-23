"""LLM pricing lookup — a simple value object for consumer-defined model prices."""

from __future__ import annotations


class LlmPricingTable:
    """Consumer-defined model pricing lookup.

    Stores ``(input_price_per_token, output_price_per_token)`` tuples keyed
    by model name.  Supports exact match and prefix match (e.g.
    ``"gpt-5.4-nano-2026-03-05"`` matches a ``"gpt-5.4-nano"`` entry).

    Usage::

        pricing = LlmPricingTable({
            "gpt-5.4":      (2.50 / 1_000_000, 15.00 / 1_000_000),
            "gpt-5.4-nano": (0.20 / 1_000_000,  1.25 / 1_000_000),
        })
        price_in, price_out = pricing.get("gpt-5.4-nano")
    """

    def __init__(self, pricing: dict[str, tuple[float, float]] | None = None) -> None:
        self._pricing: dict[str, tuple[float, float]] = dict(pricing) if pricing else {}

    def get(self, model_name: str) -> tuple[float, float]:
        """Return ``(input_price, output_price)`` per token, or ``(0.0, 0.0)``."""
        if model_name in self._pricing:
            return self._pricing[model_name]
        for key in self._pricing:
            if model_name.startswith(key):
                return self._pricing[key]
        return (0.0, 0.0)
