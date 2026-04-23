__all__ = [
    "BedrockTitanEmbedder",
    "OpenAILargeEmbedder",
    "OpenAIAdaEmbedder",
    "VoyageAIEmbedder",
]


def __getattr__(name: str):
    if name == "OpenAILargeEmbedder":
        from .openai_large_embedder import OpenAILargeEmbedder

        return OpenAILargeEmbedder
    if name == "OpenAIAdaEmbedder":
        from .openai_ada_embedder import OpenAIAdaEmbedder

        return OpenAIAdaEmbedder
    if name == "BedrockTitanEmbedder":
        from .bedrock_titan_embedder import BedrockTitanEmbedder

        return BedrockTitanEmbedder
    if name == "VoyageAIEmbedder":
        from .voyageai_embedder import VoyageAIEmbedder

        return VoyageAIEmbedder
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
