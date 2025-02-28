# academic_claim_analyzer/search/search_config.py

import random
import logging

class GlobalSearchConfig:
    """
    A single place to define concurrency, backoff, retry, and jitter settings
    for all search modules. Adjust these class attributes to override defaults.
    """

    # Concurrency (number of simultaneous requests) per module
    # Arxiv: must remain 1 if you truly want to enforce 1 request per 3s
    scopus_concurrency = 3
    core_concurrency = 2
    openalex_concurrency = 2
    arxiv_concurrency = 1
    semanticscholar_concurrency = 1

    # Exponential backoff & retry behavior
    max_retries = 5            # total retry attempts for transient errors (429/5xx)
    base_backoff_seconds = 2   # base for exponential backoff: 2^attempt
    max_backoff_seconds = 45   # clamp the backoff so it doesn't exceed 45s
    jitter_ratio = 0.5         # up to 50% extra random jitter

    # Special or additional rate-limit intervals
    # e.g., Arxiv states 1 request every ~3 seconds
    # We'll enforce this post-request as well:
    arxiv_request_interval = 3.0

def calculate_backoff(attempt: int) -> float:
    """
    Given a 0-based retry 'attempt' index,
    compute how long to sleep in seconds using exponential backoff + jitter.
    The result is bounded by max_backoff_seconds.
    """
    base = (GlobalSearchConfig.base_backoff_seconds ** attempt)
    # clamp to the configured max
    base = min(base, GlobalSearchConfig.max_backoff_seconds)

    # add random jitter up to 'base * jitter_ratio'
    jitter = random.uniform(0, base * GlobalSearchConfig.jitter_ratio)
    return base + jitter
