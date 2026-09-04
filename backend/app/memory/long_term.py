import asyncio
import logging
from typing import Any, Dict, List

import chromadb
from google import genai

from app.core.config import settings

logger = logging.getLogger(__name__)

_chroma_client = None

def get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        import os
        host = os.environ.get("CHROMA_HOST", settings.CHROMA_HOST)
        port = int(os.environ.get("CHROMA_PORT", settings.CHROMA_PORT))
        _chroma_client = chromadb.HttpClient(host=host, port=port)
    return _chroma_client

def get_collection(name: str):
    return get_chroma_client().get_or_create_collection(name)

async def get_embedding(text: str) -> List[float]:
    """
    Generate semantic embedding vector via Gemini or fallback mock.
    """
    if settings.MOCK_PROVIDERS or not settings.GEMINI_API_KEY:
        import random
        h = hash(text)
        random.seed(h)
        return [random.uniform(-0.1, 0.1) for _ in range(768)]

    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        response = await client.aio.models.embed_content(
            model="text-embedding-004",
            contents=text
        )
        if response.embedding and response.embedding.values:
            return response.embedding.values
    except Exception as e:
        logger.error(f"Error generating embedding via Gemini API: {str(e)}")

    import random
    h = hash(text)
    random.seed(h)
    return [random.uniform(-0.1, 0.1) for _ in range(768)]

async def add_to_collection(collection_name: str, doc_id: str, document: str, embedding: List[float], metadata: Dict[str, Any]):
    """
    Add a document with its pre-computed embedding and metadata to ChromaDB collection.
    """
    try:
        col = get_collection(collection_name)
        await asyncio.wait_for(
            asyncio.to_thread(
                col.add,
                ids=[doc_id],
                embeddings=[embedding],
                documents=[document],
                metadatas=[metadata]
            ),
            timeout=3.0
        )
        logger.info(f"Successfully added document {doc_id} to ChromaDB collection '{collection_name}'")
    except Exception as e:
        logger.error(f"Error adding to ChromaDB collection '{collection_name}': {str(e)}")

async def query_collection(collection_name: str, query_embedding: List[float], n_results: int = 3) -> Dict[str, Any] | None:
    """
    Query a ChromaDB collection using a query embedding vector.
    """
    try:
        col = get_collection(collection_name)
        results = await asyncio.wait_for(
            asyncio.to_thread(
                col.query,
                query_embeddings=[query_embedding],
                n_results=n_results
            ),
            timeout=3.0
        )
        return results
    except Exception as e:
        logger.error(f"Error querying ChromaDB collection '{collection_name}': {str(e)}")
    return None

async def delete_from_collection(collection_name: str, doc_id: str):
    """
    Delete a document from ChromaDB collection.
    """
    try:
        col = get_collection(collection_name)
        await asyncio.wait_for(
            asyncio.to_thread(
                col.delete,
                ids=[doc_id]
            ),
            timeout=3.0
        )
        logger.info(f"Successfully deleted document {doc_id} from ChromaDB collection '{collection_name}'")
    except Exception as e:
        logger.error(f"Error deleting from ChromaDB collection '{collection_name}': {str(e)}")
