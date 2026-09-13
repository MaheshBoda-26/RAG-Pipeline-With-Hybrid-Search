"""Redis-backed semantic cache for query results using redisvl.SemanticCache.

Two-tier cache:
- Exact match: Redis hash key (normalized query + user_id + filters) with 1hr TTL
- Semantic match: Redis vector index with cosine distance threshold 0.1, 4hr TTL
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any

from redisvl.extensions.cache.llm import SemanticCache


class QueryCache:
    """Semantic cache for RAG query responses using RedisVL."""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        exact_ttl: int = 3600,      # 1 hour for exact matches
        semantic_ttl: int = 14400,  # 4 hours for semantic matches
        distance_threshold: float = 0.1,
        name: str = "rag_query_cache",
    ):
        """
        Initialize the semantic cache.

        Args:
            redis_url: Redis connection URL
            exact_ttl: TTL in seconds for exact match entries
            semantic_ttl: TTL in seconds for semantic match entries
            distance_threshold: Cosine distance threshold for semantic matching (0-2, lower=stricter)
            name: Cache index name in Redis
        """
        self.exact_ttl = exact_ttl
        self.semantic_ttl = semantic_ttl

        # Use SemanticCache from redisvl for vector-based semantic matching
        # filterable_fields allows metadata filtering by user_id, source_filter, context_version
        self.semantic_cache = SemanticCache(
            name=name,
            redis_url=redis_url,
            distance_threshold=distance_threshold,
            filterable_fields=[
                {"name": "user_id", "type": "tag"},
                {"name": "source_filter", "type": "tag"},
                {"name": "context_version", "type": "tag"},
            ],
            ttl=semantic_ttl,  # Default TTL for semantic entries
        )

        # Direct Redis client for exact-match hash lookups
        import redis
        self._redis = redis.from_url(redis_url, decode_responses=True)

    def _make_exact_key(self, query: str, user_id: str, source_filter: str | None = None) -> str:
        """Generate deterministic cache key for exact match."""
        normalized = query.strip().lower()
        parts = [normalized, user_id]
        if source_filter:
            parts.append(source_filter)
        return f"exact:{hashlib.sha256('|'.join(parts).encode()).hexdigest()[:32]}"

    def lookup(
        self,
        query: str,
        query_embedding: list[float],
        user_id: str,
        source_filter: str | None = None,
    ) -> dict | None:
        """
        Look up cached response for a query.

        First checks exact match (Redis hash), then semantic match (vector index).
        Returns deserialized AskResponse dict or None if no hit.
        """
        # 1. Exact match via hash key
        exact_key = self._make_exact_key(query, user_id, source_filter)
        exact_data = self._redis.get(exact_key)
        if exact_data:
            try:
                return json.loads(exact_data)
            except json.JSONDecodeError:
                pass  # Fall through to semantic

        # 2. Semantic match via vector index with metadata filters
        filters = {"user_id": user_id}
        if source_filter:
            filters["source_filter"] = source_filter

        results = self.semantic_cache.check(
            vector=query_embedding,
            filter_expression=filters,
            num_results=1,
        )
        if results:
            # Return the first (best) match
            return json.loads(results[0]["response"])

        return None

    def store(
        self,
        query: str,
        response: dict,
        query_embedding: list[float],
        user_id: str,
        source_filter: str | None = None,
        context_version: str | None = None,
    ) -> None:
        """
        Store a query response in both exact and semantic caches.
        """
        # 1. Exact match: store in Redis hash with 1hr TTL
        exact_key = self._make_exact_key(query, user_id, source_filter)
        self._redis.setex(exact_key, self.exact_ttl, json.dumps(response))

        # 2. Semantic match: store in vector index with 4hr TTL and metadata
        filters = {"user_id": user_id}
        if source_filter:
            filters["source_filter"] = source_filter
        if context_version:
            filters["context_version"] = context_version

        self.semantic_cache.store(
            prompt=query,
            response=json.dumps(response),
            vector=query_embedding,
            filters=filters,
            ttl=self.semantic_ttl,
        )

    def clear_user(self, user_id: str) -> int:
        """Clear all cache entries for a specific user. Returns count cleared."""
        # Delete exact match keys for this user
        pattern = "exact:*"
        count = 0
        for key in self._redis.scan_iter(match=pattern):
            # Check if key contains user_id (inefficient but acceptable for admin use)
            data = self._redis.get(key)
            if data and user_id in data:
                self._redis.delete(key)
                count += 1

        # Semantic cache clear with filter
        filters = {"user_id": user_id}
        self.semantic_cache.delete(filters=filters)

        return count

    def close(self):
        """Close Redis connections."""
        self._redis.close()
        # SemanticCache doesn't have explicit close, relies on connection pool