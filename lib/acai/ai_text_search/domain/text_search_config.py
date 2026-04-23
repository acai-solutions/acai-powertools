from dataclasses import dataclass


@dataclass(frozen=True)
class TextSearchConfig:
    """Configuration for PostgreSQL full-text search.

    Attributes
    ----------
    language:
        PostgreSQL text-search dictionary (e.g. ``"german"``, ``"english"``).
    table:
        Fully-qualified table name (e.g. ``"app.law_embeddings"``).
    content_column:
        Column containing the searchable text.
    id_column:
        Column used as the unique record identifier.
    """

    language: str = "german"
    table: str = "app.law_embeddings"
    content_column: str = "embedding_text"
    id_column: str = "external_id"
