# src/academic_claim_analyzer/main.py
"""
Main orchestrator for the Academic Claim Analyzer.
"""

import asyncio
import logging
from typing import List, Type
from .query_formulator import formulate_queries
from .paper_scraper import scrape_papers
from .paper_ranker import rank_papers
from .search import OpenAlexSearch, ScopusSearch, CoreSearch, BaseSearch
from .models import ClaimAnalysis, RankedPaper

logger = logging.getLogger(__name__)

SEARCH_MODULES: List[Type[BaseSearch]] = [OpenAlexSearch, ScopusSearch, CoreSearch]

async def analyze_claim(
    claim: str,
    num_queries: int = 5,
    papers_per_query: int = 5,
    num_papers_to_return: int = 1
) -> ClaimAnalysis:
    """
    Analyze a given claim by searching for relevant papers, ranking them,
    and returning the top-ranked papers with supporting evidence.

    Args:
        claim (str): The claim to be analyzed.
        num_queries (int): Number of search queries to generate.
        papers_per_query (int): Number of papers to retrieve per query.
        num_papers_to_return (int): Number of top-ranked papers to return.

    Returns:
        ClaimAnalysis: Analysis result containing top-ranked papers with supporting evidence.
    """
    analysis = ClaimAnalysis(
        claim=claim,
        parameters={
            "num_queries": num_queries,
            "papers_per_query": papers_per_query,
            "num_papers_to_return": num_papers_to_return
        }
    )
    
    try:
        await _perform_analysis(analysis)
    except Exception as e:
        logger.error(f"Error during claim analysis: {str(e)}")
        analysis.metadata["error"] = str(e)
    
    return analysis

async def _perform_analysis(analysis: ClaimAnalysis) -> None:
    """
    Perform the actual analysis steps.
    """
    await _formulate_queries(analysis)
    await _perform_searches(analysis)
    await _scrape_papers(analysis)
    await _rank_papers(analysis)

async def _formulate_queries(analysis: ClaimAnalysis) -> None:
    """
    Formulate queries based on the claim.
    """
    queries = formulate_queries(analysis.claim, analysis.parameters["num_queries"])
    for query in queries:
        analysis.add_query(query, "formulator")

async def _perform_searches(analysis: ClaimAnalysis) -> None:
    """
    Perform searches using all search modules.
    """
    search_tasks = []
    for search_module_class in SEARCH_MODULES:
        search_module = search_module_class()
        for query in analysis.queries:
            search_tasks.append(_search_and_add_results(
                search_module, query.query, analysis.parameters["papers_per_query"], analysis
            ))
    await asyncio.gather(*search_tasks)

async def _search_and_add_results(search_module: BaseSearch, query: str, limit: int, analysis: ClaimAnalysis) -> None:
    """
    Perform a search and add results to the analysis.
    """
    try:
        results = await search_module.search(query, limit)
        for paper in results:
            analysis.add_search_result(paper)
    except Exception as e:
        logger.error(f"Error during search with {search_module.__class__.__name__}: {str(e)}")

async def _scrape_papers(analysis: ClaimAnalysis) -> None:
    """
    Scrape full text content for all papers in the analysis.
    """
    analysis.search_results = await scrape_papers(analysis.search_results)

async def _rank_papers(analysis: ClaimAnalysis) -> None:
    """
    Rank the papers based on relevance to the claim.
    """
    ranked_papers = await rank_papers(analysis.search_results, analysis.claim)
    for paper in ranked_papers:
        analysis.add_ranked_paper(paper)

async def main():
    claim = "Coffee consumption is associated with reduced risk of type 2 diabetes."
    analysis_result = await analyze_claim(claim)
    
    print(f"Claim: {analysis_result.claim}")
    print(f"Number of queries generated: {len(analysis_result.queries)}")
    print(f"Total papers found: {len(analysis_result.search_results)}")
    print(f"Number of ranked papers: {len(analysis_result.ranked_papers)}")
    print("\nTop ranked papers:")
    
    for paper in analysis_result.get_top_papers(analysis_result.parameters["num_papers_to_return"]):
        print(f"\nTitle: {paper.title}")
        print(f"Authors: {', '.join(paper.authors)}")
        print(f"DOI: {paper.doi}")
        print(f"Relevance Score: {paper.relevance_score}")
        print(f"Analysis: {paper.analysis}")
        print("Relevant Quotes:")
        for quote in paper.relevant_quotes:
            print(f"- {quote}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())