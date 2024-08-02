# academic_claim_analyzer/main.py

import asyncio
import logging
from typing import List
from .query_formulator import formulate_queries
from .paper_ranker import rank_papers
from .search import OpenAlexSearch, ScopusSearch, CORESearch, BaseSearch
from .models import ClaimAnalysis, Paper

logger = logging.getLogger(__name__)

async def analyze_claim(
    claim: str,
    num_queries: int = 5,
    papers_per_query: int = 5,
    num_papers_to_return: int = 1
) -> ClaimAnalysis:
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
    await _formulate_queries(analysis)
    await _perform_searches(analysis)
    await _rank_papers(analysis)

async def _formulate_queries(analysis: ClaimAnalysis) -> None:
    openalex_queries = await formulate_queries(analysis.claim, analysis.parameters["num_queries"], "openalex")
    scopus_queries = await formulate_queries(analysis.claim, analysis.parameters["num_queries"], "scopus")
    
    for query in openalex_queries:
        analysis.add_query(query, "openalex")
    for query in scopus_queries:
        analysis.add_query(query, "scopus")

async def _perform_searches(analysis: ClaimAnalysis) -> None:
    search_modules = [OpenAlexSearch("bnsoh2@huskers.unl.edu"), ScopusSearch(), CORESearch()]
    search_tasks = []
    for search_module in search_modules:
        for query in analysis.queries:
            search_tasks.append(_search_and_add_results(
                search_module, query.query, analysis.parameters["papers_per_query"], analysis
            ))
    await asyncio.gather(*search_tasks)

async def _search_and_add_results(search_module: BaseSearch, query: str, limit: int, analysis: ClaimAnalysis) -> None:
    try:
        results = await search_module.search(query, limit)
        for paper in results:
            analysis.add_search_result(paper)
    except Exception as e:
        logger.error(f"Error during search with {search_module.__class__.__name__}: {str(e)}")

async def _rank_papers(analysis: ClaimAnalysis) -> None:
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