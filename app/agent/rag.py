"""Qdrant-backed retrieval for OpsPilot operational knowledge.

The RAG layer is intentionally read-only from the investigation workflow's point
of view. It builds a searchable knowledge collection from sanitised runbooks,
previous incidents, and previously persisted RCA results, then retrieves the
most relevant context for the current incident.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from app.knowledge import RUNBOOKS
from app.storage import list_knowledge_documents

DEFAULT_QDRANT_URL = "http://localhost:6333"
DEFAULT_COLLECTION = "opspilot_knowledge"
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"


@dataclass(frozen=True)
class RAGConfig:
    enabled: bool
    qdrant_url: str
    collection_name: str
    embedding_model: str
    limit: int
    score_threshold: float
    timeout_seconds: float


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_rag_config() -> RAGConfig:
    """Resolve local/demo-safe RAG settings from environment variables."""

    return RAGConfig(
        enabled=_env_flag("OPSPILOT_RAG_ENABLED", default=False),
        qdrant_url=os.getenv("OPSPILOT_QDRANT_URL", DEFAULT_QDRANT_URL).rstrip("/"),
        collection_name=os.getenv("OPSPILOT_QDRANT_COLLECTION", DEFAULT_COLLECTION),
        embedding_model=os.getenv("OPSPILOT_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
        limit=max(1, min(10, int(os.getenv("OPSPILOT_RAG_LIMIT", "4")))),
        score_threshold=max(0.0, min(1.0, float(os.getenv("OPSPILOT_RAG_SCORE_THRESHOLD", "0.30")))),
        timeout_seconds=max(0.5, float(os.getenv("OPSPILOT_QDRANT_TIMEOUT_SECONDS", "5.0"))),
    )


def _runbook_documents() -> list[dict]:
    documents: list[dict] = []
    for runbook in RUNBOOKS:
        text = (
            f"Runbook: {runbook['title']}. "
            f"Keywords: {', '.join(runbook['keywords'])}. "
            f"Safe first steps: {' '.join(runbook['safe_first_steps'])}"
        )
        documents.append(
            {
                "knowledge_id": runbook["runbook_id"],
                "source_type": "runbook",
                "title": runbook["title"],
                "text": text,
                "metadata": {"runbook_id": runbook["runbook_id"]},
            }
        )
    return documents


def _all_documents(exclude_incident_id: str | None) -> list[dict]:
    return [
        *_runbook_documents(),
        *list_knowledge_documents(exclude_incident_id=exclude_incident_id, limit=200),
    ]


def _point_id(knowledge_id: str) -> str:
    """Return a stable UUID accepted by Qdrant for the knowledge record."""

    return str(uuid5(NAMESPACE_URL, f"opspilot:{knowledge_id}"))


def retrieve_knowledge(
    query: str,
    *,
    exclude_incident_id: str | None = None,
    config: RAGConfig | None = None,
    client=None,
) -> dict:
    """Index current sanitised knowledge and retrieve semantically similar items.

    Qdrant Client's FastEmbed integration generates embeddings locally. The
    default BGE model is CPU-friendly and keeps the hackathon RAG path independent
    from the selected generative LLM provider.
    """

    resolved = config or load_rag_config()
    if not resolved.enabled:
        return {
            "status": "disabled",
            "collection": resolved.collection_name,
            "embedding_model": resolved.embedding_model,
            "documents_indexed": 0,
            "items": [],
        }

    if not query.strip():
        return {
            "status": "no_query",
            "collection": resolved.collection_name,
            "embedding_model": resolved.embedding_model,
            "documents_indexed": 0,
            "items": [],
        }

    documents = _all_documents(exclude_incident_id)
    if not documents:
        return {
            "status": "no_knowledge",
            "collection": resolved.collection_name,
            "embedding_model": resolved.embedding_model,
            "documents_indexed": 0,
            "items": [],
        }

    try:
        from qdrant_client import QdrantClient, models

        qdrant = client or QdrantClient(
            url=resolved.qdrant_url,
            timeout=resolved.timeout_seconds,
        )

        if not qdrant.collection_exists(resolved.collection_name):
            qdrant.create_collection(
                collection_name=resolved.collection_name,
                vectors_config=models.VectorParams(
                    size=qdrant.get_embedding_size(resolved.embedding_model),
                    distance=models.Distance.COSINE,
                ),
            )

        qdrant.upload_collection(
            collection_name=resolved.collection_name,
            vectors=[
                models.Document(text=document["text"], model=resolved.embedding_model)
                for document in documents
            ],
            payload=documents,
            ids=[_point_id(document["knowledge_id"]) for document in documents],
        )

        response = qdrant.query_points(
            collection_name=resolved.collection_name,
            query=models.Document(text=query, model=resolved.embedding_model),
            limit=resolved.limit,
            score_threshold=resolved.score_threshold,
            with_payload=True,
        )

        items: list[dict] = []
        for point in response.points:
            payload = dict(point.payload or {})
            items.append(
                {
                    "knowledge_id": payload.get("knowledge_id", str(point.id)),
                    "source_type": payload.get("source_type", "unknown"),
                    "title": payload.get("title", "Operational knowledge"),
                    "text": payload.get("text", ""),
                    "score": round(float(point.score), 4),
                    "metadata": payload.get("metadata", {}),
                }
            )

        return {
            "status": "available" if items else "no_matches",
            "collection": resolved.collection_name,
            "embedding_model": resolved.embedding_model,
            "documents_indexed": len(documents),
            "items": items,
        }
    except Exception as exc:  # Qdrant/model failures must not break incident triage.
        return {
            "status": "unavailable",
            "collection": resolved.collection_name,
            "embedding_model": resolved.embedding_model,
            "documents_indexed": 0,
            "items": [],
            "error_type": type(exc).__name__,
        }
