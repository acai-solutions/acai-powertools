# vector_store_example.py
"""
Minimal example — upsert and search embeddings via the acai vector_store module.

Prerequisites:
    pip install psycopg2-binary pgvector

    A running PostgreSQL instance with the ``vector`` extension enabled.
    Set the connection details below or via environment variables.
"""

import os

from acai.ai_vector_store import VectorRecord, create_vector_store
from acai.logging import LoggerConfig, LogLevel, create_logger
from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    logger = create_logger(
        LoggerConfig(
            service_name="vector_store_example",
            log_level=LogLevel.DEBUG,
        )
    )

    # --- wire infrastructure via factory ---
    store = create_vector_store(
        logger,
        provider="pgvector",
        host=os.getenv("PG_HOST", "localhost"),
        port=int(os.getenv("PG_PORT", "5432")),
        dbname=os.getenv("PG_DBNAME", "postgres"),
        user=os.getenv("PG_USER", "postgres"),
        password=os.getenv("PG_PASSWORD", ""),
        table="example_embeddings",
        schema="public",
        dimension=3,
        distance_metric="cosine",
    )

    with store:
        # bootstrap table (only needed once)
        store.ensure_table()

        # --- upsert ---
        records = [
            VectorRecord(
                id="art-1",
                text="Bundesverfassung Art. 1",
                vector=[0.1, 0.2, 0.3],
                metadata={"sr": "101"},
            ),
            VectorRecord(
                id="art-2",
                text="Obligationenrecht Art. 1",
                vector=[0.4, 0.5, 0.6],
                metadata={"sr": "220"},
            ),
            VectorRecord(
                id="art-3",
                text="Zivilgesetzbuch Art. 1",
                vector=[0.11, 0.21, 0.31],
                metadata={"sr": "210"},
            ),
        ]
        store.upsert(records)

        # --- similarity search ---
        results = store.search([0.1, 0.2, 0.3], top_k=2)
        for r in results:
            logger.info(
                f"  → {r.record.id}  score={r.score:.4f}  text={r.record.text!r}"
            )

        # --- filtered search ---
        results = store.search(
            [0.1, 0.2, 0.3],
            top_k=5,
            filter_metadata={"sr": "210"},
        )
        logger.info(f"Filtered results: {len(results)}")

        # --- delete ---
        store.delete(["art-2"])


if __name__ == "__main__":
    main()
