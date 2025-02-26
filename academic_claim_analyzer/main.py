# academic_claim_analyzer/main.py

import asyncio
import logging
from typing import List, Dict, Any, Optional, Union

from .analyzer import analyze_request
from .models import RequestAnalysis

logger = logging.getLogger(__name__)

# Main entry point function exposed to external code
async def analyze_research_request(
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
    Main entry point for analyzing a research request.
    Simply delegates to the analyze_request function in analyzer.py.
    
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
    return await analyze_request(
        query=query,
        ranking_guidance=ranking_guidance,
        exclusion_criteria=exclusion_criteria,
        data_extraction_schema=data_extraction_schema,
        num_queries=num_queries,
        papers_per_query=papers_per_query,
        num_papers_to_return=num_papers_to_return,
        config=config
    )

if __name__ == "__main__":
    # Example usage
    import asyncio
    analysis = asyncio.run(analyze_research_request(
        query="Urban green spaces enhance community well-being and mental health in cities.",
        ranking_guidance="Prioritize empirical studies with robust methodologies.",
        num_queries=3,
        papers_per_query=5,
        num_papers_to_return=3
    ))
    print(analysis.to_dict())