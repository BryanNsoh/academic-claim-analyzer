# academic_claim_analyzer/analyzer.py

import asyncio
import logging
from typing import List, Dict, Any, Optional, Union

from .models import RequestAnalysis, Paper, RankedPaper
from .schema_manager import create_model_from_schema
from .query_processor import formulate_queries_for_platforms
from .search_coordinator import perform_searches
from .exclusion_processor import apply_exclusion_criteria
from .paper_ranker import rank_papers

logger = logging.getLogger(__name__)

async def analyze_request(
    query: Union[str, List[str]],
    ranking_guidance: str = "",
    exclusion_criteria: Optional[Dict[str, Any]] = None,
    data_extraction_schema: Optional[Dict[str, Any]] = None,
    num_queries: int = 2,
    papers_per_query: int = 2,
    num_papers_to_return: int = 2,
    config: Optional[Dict[str, Any]] = None
) -> RequestAnalysis:
    """
    Analyze a user's research request. This includes:
      1) Formulating queries for selected platforms
      2) Searching and fetching papers
      3) Applying exclusion criteria
      4) Ranking papers using the provided ranking guidance
      5) Extracting requested information

    If a config is provided and includes a "search.platforms" list, only those platforms are used.
    Otherwise, the default is to use all platforms: openalex, scopus, core, arxiv, and semantic_scholar.

    This function supports multiple user queries if `query` is provided as a list.
    
    Args:
        query: Single query string or list of query strings
        ranking_guidance: Guidance for ranking papers
        exclusion_criteria: Criteria for excluding papers
        data_extraction_schema: Schema for extracting data from papers
        num_queries: Number of queries to generate per platform
        papers_per_query: Number of papers to retrieve per query
        num_papers_to_return: Number of top papers to return
        config: Configuration dictionary
        
    Returns:
        RequestAnalysis object containing search results and ranked papers
    """
    logger.info(f"Analyzing request with exclusion criteria: {exclusion_criteria}")
    logger.info(f"Data extraction schema: {data_extraction_schema}")
    logger.info(f"Ranking guidance: {ranking_guidance}")

    # Determine which platforms to use.
    default_platforms = ["openalex", "scopus", "core", "arxiv", "semantic_scholar"]
    if config and "search" in config and "platforms" in config["search"]:
        default_platforms = config["search"]["platforms"]

    # Handle multiple queries vs single query
    if isinstance(query, list):
        # Multi-query scenario
        analysis = RequestAnalysis(
            query="(multiple user queries)",
            ranking_guidance=ranking_guidance,
            parameters={
                "num_queries": num_queries,
                "papers_per_query": papers_per_query,
                "num_papers_to_return": num_papers_to_return,
                "platforms": default_platforms
            }
        )

        if exclusion_criteria:
            ExclusionModel = create_model_from_schema('ExclusionCriteria', exclusion_criteria)
            analysis.exclusion_schema = ExclusionModel
        if data_extraction_schema:
            ExtractionModel = create_model_from_schema('DataExtractionSchema', data_extraction_schema)
            analysis.data_extraction_schema = ExtractionModel

        # For each user query, set analysis.query and perform search and exclusion
        for q in query:
            analysis.query = q
            await _search_and_exclude(analysis)

        # Once all queries are processed, perform ranking on aggregated results
        await _rank_papers(analysis)
        return analysis
    else:
        # Single query scenario
        analysis = RequestAnalysis(
            query=query,
            ranking_guidance=ranking_guidance,
            parameters={
                "num_queries": num_queries,
                "papers_per_query": papers_per_query,
                "num_papers_to_return": num_papers_to_return,
                "platforms": default_platforms
            }
        )

        if exclusion_criteria:
            ExclusionModel = create_model_from_schema('ExclusionCriteria', exclusion_criteria)
            analysis.exclusion_schema = ExclusionModel
        if data_extraction_schema:
            ExtractionModel = create_model_from_schema('DataExtractionSchema', data_extraction_schema)
            analysis.data_extraction_schema = ExtractionModel

        await _perform_analysis(analysis)
        return analysis

async def _search_and_exclude(analysis: RequestAnalysis) -> None:
    """Helper function to perform query formulation, searching, and applying exclusion criteria."""
    await formulate_queries_for_platforms(analysis)
    await perform_searches(analysis)
    await apply_exclusion_criteria(analysis)

async def _perform_analysis(analysis: RequestAnalysis) -> None:
    """Perform the complete analysis pipeline."""
    await _search_and_exclude(analysis)
    await _rank_papers(analysis)

async def _rank_papers(analysis: RequestAnalysis) -> None:
    """Rank papers based on relevance to the query."""
    if not analysis.search_results:
        logger.warning("No papers to rank.")
        return
    try:
        ranked_list = await rank_papers(
            papers=analysis.search_results,
            query=analysis.query,
            ranking_guidance=analysis.ranking_guidance,
            exclusion_schema=analysis.exclusion_schema,
            data_extraction_schema=analysis.data_extraction_schema,
            top_n=analysis.parameters["num_papers_to_return"]
        )
        for rp in ranked_list:
            analysis.add_ranked_paper(rp)
    except Exception as e:
        logger.error(f"Error ranking papers: {str(e)}", exc_info=True)