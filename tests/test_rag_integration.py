from qdrant_client import QdrantClient

from app.agent.rag import RAGConfig, retrieve_knowledge
from app.database import initialise_database


def test_qdrant_fastembed_retrieves_relevant_runbook():
    """Exercise real FastEmbed inference and Qdrant semantic search in memory."""

    initialise_database()
    client = QdrantClient(":memory:")
    config = RAGConfig(
        enabled=True,
        qdrant_url="http://unused-in-memory",
        collection_name="opspilot_test_knowledge",
        embedding_model="BAAI/bge-small-en-v1.5",
        limit=4,
        score_threshold=0.0,
        timeout_seconds=10.0,
    )

    result = retrieve_knowledge(
        "CPU load is high and application requests are becoming slow; inspect processes and latency",
        exclude_incident_id="DOES-NOT-EXIST",
        config=config,
        client=client,
    )

    assert result["status"] == "available"
    assert result["documents_indexed"] >= 7
    assert result["items"]
    assert any(
        item["knowledge_id"] == "RB-CPU-001"
        for item in result["items"]
    )
