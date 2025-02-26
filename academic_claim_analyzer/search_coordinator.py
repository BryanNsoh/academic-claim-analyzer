# academic_claim_analyzer/search_coordinator.py

import asyncio
import logging
from typing import List

from .models import RequestAnalysis, Paper
from .search import (
    OpenAlexSearch, 
    ScopusSearch, 
    CORESearch, 
    ArxivSearch, 
    SemanticScholarSearch, 
    BaseSearch
)

logger = logging.getLogger(__name__)

async def perform_searches(analysis: RequestAnalysis) -> None:
    """
    Perform searches across all enabled platforms and add results to the analysis object.
    
    Args:
        analysis: The RequestAnalysis object containing search queries and configuration
    """
    chosen_platforms = analysis.parameters.get(
        "platforms", 
        ["openalex", "scopus", "core", "arxiv", "semantic_scholar"]
    )
    search_tasks = []
    papers_per_query = analysis.parameters["papers_per_query"]

    if "openalex" in chosen_platforms:
        openalex_search = OpenAlexSearch("youremail@example.com")
        openalex_queries = [q for q in analysis.queries if q.source == "openalex"]
        for query in openalex_queries:
            search_tasks.append(
                _search_and_add_results(openalex_search, query.query, papers_per_query, analysis)
            )

    if "scopus" in chosen_platforms:
        scopus_search = ScopusSearch()
        scopus_queries = [q for q in analysis.queries if q.source == "scopus"]
        for query in scopus_queries:
            search_tasks.append(
                _search_and_add_results(scopus_search, query.query, papers_per_query, analysis)
            )

    if "core" in chosen_platforms:
        core_search = CORESearch()
        core_queries = [q for q in analysis.queries if q.source == "core"]
        for query in core_queries:
            search_tasks.append(
                _search_and_add_results(core_search, query.query, papers_per_query, analysis)
            )

    if "arxiv" in chosen_platforms:
        arxiv_search = ArxivSearch()
        arxiv_queries = [q for q in analysis.queries if q.source == "arxiv"]
        for query in arxiv_queries:
            search_tasks.append(
                _search_and_add_results(arxiv_search, query.query, papers_per_query, analysis)
            )
            
    if "semantic_scholar" in chosen_platforms:
        semantic_scholar_search = SemanticScholarSearch()
        semantic_scholar_queries = [q for q in analysis.queries if q.source == "semantic_scholar"]
        for query in semantic_scholar_queries:
            search_tasks.append(
                _search_and_add_results(semantic_scholar_search, query.query, papers_per_query, analysis)
            )

    await asyncio.gather(*search_tasks)

async def _search_and_add_results(
    search_module: BaseSearch,
    query: str,
    limit: int,
    analysis: RequestAnalysis
) -> None:
    """
    Execute a search using the specified module and add results to the analysis.
    
    Args:
        search_module: The search module to use
        query: The query string
        limit: Maximum number of results to retrieve
        analysis: The RequestAnalysis object to store results in
    """
    try:
        results = await search_module.search(query, limit)
        if results and isinstance(results, list):
            for paper in results:
                if isinstance(paper, Paper):
                    analysis.add_search_result(paper)
    except Exception as e:
        logger.error(f"Error during search with {search_module.__class__.__name__}: {str(e)}")