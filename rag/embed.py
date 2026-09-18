"""
Semantic embedding function for lead queries and actor configurations.
Uses OpenAI's text-embedding-3-small model.
"""

import os
from typing import List
import openai

# Load API key from environment
openai.api_key = os.getenv("OPENAI_API_KEY")


def embed(text: str) -> List[float]:
    """
    Generate semantic embedding for a single text.
    
    Args:
        text: Input text (query or actor config description)
    
    Returns:
        List[float]: Embedding vector (1536 dimensions)
    
    Raises:
        ValueError: If text is empty or API call fails
    """
    if not text or len(text.strip()) == 0:
        raise ValueError("Text cannot be empty")
    
    try:
        response = openai.Embedding.create(
            input=text,
            model="text-embedding-3-small"
        )
        return response["data"][0]["embedding"]
    except Exception as e:
        raise RuntimeError(f"Embedding failed: {str(e)}")


def embed_batch(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for multiple texts (more efficient).
    
    Args:
        texts: List of texts to embed
    
    Returns:
        List[List[float]]: List of embedding vectors
    
    Raises:
        ValueError: If texts list is empty
    """
    if not texts:
        raise ValueError("Texts list cannot be empty")
    
    try:
        response = openai.Embedding.create(
            input=texts,
            model="text-embedding-3-small"
        )
        # Sort by index to maintain order
        embeddings = sorted(response["data"], key=lambda x: x["index"])
        return [emb["embedding"] for emb in embeddings]
    except Exception as e:
        raise RuntimeError(f"Batch embedding failed: {str(e)}")


if __name__ == "__main__":
    # Test embedding
    test_text = "Find leads in tech industry with >100 employees"
    emb = embed(test_text)
    print(f"Query: {test_text}")
    print(f"Embedding dimension: {len(emb)}")
    print(f"First 5 values: {emb[:5]}")
