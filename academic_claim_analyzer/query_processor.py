# academic_claim_analyzer/query_processor.py

import asyncio
import logging
from typing import List

from .models import RequestAnalysis
from .query_formulator import formulate_queries

logger = logging.getLogger(__name__)

async def formulate_queries_for_platforms(analysis: RequestAnalysis) -> None:
    """
    Formulate queries for each platform based on the user query.
    
    Args:
        analysis: The RequestAnalysis object containing the user query
    """
    chosen_platforms = analysis.parameters.get(
        "platforms", 
        ["openalex", "scopus", "core", "arxiv", "semantic_scholar"]
    )
    tasks = []
    num_queries = analysis.parameters["num_queries"]

    if "openalex" in chosen_platforms:
        tasks.append(formulate_queries(analysis.query, num_queries, "openalex"))
    if "scopus" in chosen_platforms:
        tasks.append(formulate_queries(analysis.query, num_queries, "scopus"))
    if "core" in chosen_platforms:
        tasks.append(formulate_queries(analysis.query, num_queries, "core"))
    if "arxiv" in chosen_platforms:
        tasks.append(formulate_queries(analysis.query, num_queries, "arxiv"))
    if "semantic_scholar" in chosen_platforms:
        tasks.append(formulate_queries(analysis.query, num_queries, "semantic_scholar"))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Get the platforms we're actually using
    appended_platforms = [p for p in chosen_platforms 
                         if p in ["openalex", "scopus", "core", "arxiv", "semantic_scholar"]]

    for platform, result in zip(appended_platforms, results):
        if isinstance(result, Exception):
            logger.error(f"Error formulating queries for {platform}: {str(result)}")
        else:
            for q in result:
                analysis.add_query(q, platform)