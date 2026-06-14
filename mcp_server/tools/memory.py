"""ChromaDB vector memory tool for storing and retrieving competitive research."""

from __future__ import annotations

import json
import os
from typing import Any

import structlog
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from constants import (
    DEFAULT_CHROMA_HOST,
    DEFAULT_CHROMA_PORT,
    MEMORY_COLLECTION_NAME,
    DEFAULT_MEMORY_RETRIES,
)

logger = structlog.get_logger(__name__)

# Lazy-initialized client
_chroma_client = None
_collection = None

COLLECTION_NAME = MEMORY_COLLECTION_NAME


def _get_chroma_client() -> Any:
    """Get or create the ChromaDB HTTP client."""
    global _chroma_client
    if _chroma_client is None:
        import chromadb

        host = os.environ.get("CHROMA_HOST", DEFAULT_CHROMA_HOST)
        port = int(os.environ.get("CHROMA_PORT", str(DEFAULT_CHROMA_PORT)))
        logger.info("chroma_client_init", host=host, port=port)
        _chroma_client = chromadb.HttpClient(host=host, port=port)
    return _chroma_client


def _get_collection() -> Any:
    """Get or create the competitive research collection."""
    global _collection
    if _collection is None:
        client = _get_chroma_client()
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"description": "Competitive intelligence research data"},
        )
        logger.info("chroma_collection_ready", collection=COLLECTION_NAME)
    return _collection


@retry(
    stop=stop_after_attempt(DEFAULT_MEMORY_RETRIES),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((Exception,)),
    reraise=True,
)
def store_research(company: str, data: dict[str, Any]) -> str:
    """
    Store research data for a company in ChromaDB.

    Args:
        company: Company name (used as document ID prefix)
        data: Serialized ResearchOutput dict

    Returns:
        Document ID of stored research
    """
    collection = _get_collection()

    doc_id = f"{company.lower().replace(' ', '_')}_{data.get('timestamp', 'latest')}"
    document = json.dumps(data, default=str)

    logger.info("store_research", company=company, doc_id=doc_id)

    collection.upsert(
        ids=[doc_id],
        documents=[document],
        metadatas=[{"company": company, "type": "research"}],
    )

    return doc_id


@retry(
    stop=stop_after_attempt(DEFAULT_MEMORY_RETRIES),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((Exception,)),
    reraise=True,
)
def retrieve_research(company: str, n_results: int = 5) -> list[dict[str, Any]]:
    """
    Retrieve past research for a company from ChromaDB.

    Args:
        company: Company name to search for
        n_results: Max number of results to return

    Returns:
        List of past research documents
    """
    collection = _get_collection()

    logger.info("retrieve_research", company=company, n_results=n_results)

    results = collection.query(
        query_texts=[f"{company} competitive analysis"],
        n_results=n_results,
        where={"company": company},
    )

    documents = []
    if results and results.get("documents"):
        for doc_list in results["documents"]:
            for doc in doc_list:
                try:
                    documents.append(json.loads(doc))
                except json.JSONDecodeError:
                    documents.append({"raw": doc})

    logger.info("retrieve_research_done", company=company, found=len(documents))
    return documents


def check_health() -> bool:
    """Check if ChromaDB is reachable."""
    try:
        client = _get_chroma_client()
        client.heartbeat()
        return True
    except Exception:
        logger.exception("chroma_health_check_failed")
        return False


def reset_client() -> None:
    """Reset the cached client and collection (for testing)."""
    global _chroma_client, _collection
    _chroma_client = None
    _collection = None
