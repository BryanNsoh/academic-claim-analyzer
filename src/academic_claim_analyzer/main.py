# src/academic_claim_analyzer/main.py
"""
Main orchestrator for the Academic Claim Analyzer.
"""

import asyncio
from typing import List, Dict
from .query_formulator import formulate_queries
from .paper_scraper import scrape_papers
from .paper_ranker import rank_papers
from .search import OpenAlexSearch, ScopusSearch, CoreSearch
from .models import RankedPaper

async def analyze_claim(
    claim: str,
    num_queries: int = 5,
    papers_per_query: int = 5,
    num_papers_to_return: int = 1
) -> List[RankedPaper]:
    """
    Analyze a given claim by searching for relevant papers, ranking them,
    and returning the top-ranked papers with supporting evidence.

    Args:
        claim (str): The claim to be analyzed.
        num_queries (int): Number of search queries to generate.
        papers_per_query (int): Number of papers to retrieve per query.
        num_papers_to_return (int): Number of top-ranked papers to return.

    Returns:
        List[RankedPaper]: List of top-ranked papers with supporting evidence.
    """
    # Formulate queries
    queries = formulate_queries(claim, num_queries)
    
    # Perform searches
    search_modules = [OpenAlexSearch(), ScopusSearch(), CoreSearch()]
    all_papers = []
    for search_module in search_modules:
        for query in queries:
            results = await search_module.search(query, papers_per_query)
            all_papers.extend(results)
    
    # Scrape full text
    scraped_papers = await scrape_papers(all_papers)
    
    # Rank papers
    ranked_papers = await rank_papers(scraped_papers, claim)
    
    # Return top N papers
    return ranked_papers[:num_papers_to_return]

if __name__ == "__main__":
    claim = "Coffee consumption is associated with reduced risk of type 2 diabetes."
    results = asyncio.run(analyze_claim(claim))
    for paper in results:
        print(f"Title: {paper.title}")
        print(f"Authors: {', '.join(paper.authors)}")
        print(f"DOI: {paper.doi}")
        print(f"Paper Rank: {paper.rank}")
        print(f"Analysis: {paper.analysis}")
        print("Relevant Quotes:")
        for quote in paper.relevant_quotes:
            print(f"- {quote}")
        print("\n")