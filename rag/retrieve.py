"""
Semantic retrieval: cosine similarity + top-k retrieval.
Retrieves most relevant actor configs for a given lead query.
"""

import numpy as np
from typing import List, Tuple
import yaml


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """
    Calculate cosine similarity between two vectors.
    
    Args:
        a, b: Embedding vectors
    
    Returns:
        float: Cosine similarity score (0-1)
    """
    a_norm = np.array(a) / (np.linalg.norm(a) + 1e-10)
    b_norm = np.array(b) / (np.linalg.norm(b) + 1e-10)
    return float(np.dot(a_norm, b_norm))


def retrieve(
    query_embedding: List[float],
    stored_embeddings: List[Tuple[int, List[float]]],
    top_k: int = 20,
    min_similarity: float = 0.7
) -> List[int]:
    """
    Retrieve top-k most similar embeddings using cosine similarity.
    
    Args:
        query_embedding: Query vector (from user's lead request)
        stored_embeddings: List of (id, embedding) tuples
        top_k: Number of top results to return (default 20)
        min_similarity: Minimum similarity threshold (default 0.7)
    
    Returns:
        List[int]: IDs of top-k relevant items, sorted by similarity (descending)
    
    Raises:
        ValueError: If inputs are invalid
    """
    if not stored_embeddings:
        raise ValueError("Stored embeddings cannot be empty")
    
    if len(query_embedding) == 0:
        raise ValueError("Query embedding cannot be empty")
    
    # Calculate similarities
    scores = []
    for idx, (item_id, embedding) in enumerate(stored_embeddings):
        sim = cosine_similarity(query_embedding, embedding)
        
        # Only include if above threshold
        if sim >= min_similarity:
            scores.append((item_id, sim))
    
    # Sort by similarity (descending)
    scores.sort(key=lambda x: x[1], reverse=True)
    
    # Return top-k IDs
    top_ids = [item_id for item_id, _ in scores[:top_k]]
    return top_ids


def retrieve_with_scores(
    query_embedding: List[float],
    stored_embeddings: List[Tuple[int, List[float]]],
    top_k: int = 20,
    min_similarity: float = 0.7
) -> List[Tuple[int, float]]:
    """
    Retrieve top-k results WITH similarity scores (for debugging/evaluation).
    
    Args:
        query_embedding: Query vector
        stored_embeddings: List of (id, embedding) tuples
        top_k: Number of results
        min_similarity: Minimum threshold
    
    Returns:
        List[Tuple[int, float]]: [(item_id, similarity_score), ...]
    """
    scores = []
    for item_id, embedding in stored_embeddings:
        sim = cosine_similarity(query_embedding, embedding)
        if sim >= min_similarity:
            scores.append((item_id, sim))
    
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_k]


def load_config(config_path: str = "config.yaml") -> dict:
    """Load retrieval config from YAML file."""
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        return config.get("retrieval", {})
    except FileNotFoundError:
        # Return defaults
        return {"top_k": 20, "min_similarity_score": 0.7}


if __name__ == "__main__":
    # Test retrieval
    from embed import embed
    
    query = "Find tech startup founders in Silicon Valley"
    query_emb = embed(query)
    
    # Simulate stored embeddings
    samples = [
        (1, embed("Startup database with founder contact info")),
        (2, embed("LinkedIn profiles for executives")),
        (3, embed("Angel investors in Bay Area")),
        (4, embed("Tech founders email list")),
    ]
    
    results = retrieve_with_scores(query_emb, samples, top_k=2)
    print(f"Query: {query}")
    print(f"Top 2 results:")
    for item_id, score in results:
        print(f"  ID {item_id}: {score:.4f}")
