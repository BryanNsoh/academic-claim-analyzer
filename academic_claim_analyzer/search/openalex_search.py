# academic_claim_analyzer/search/openalex_search.py
# To run: python -m academic_claim_analyzer.search.openalex_search

import aiohttp
import os
import asyncio
import urllib.parse
from datetime import datetime
from typing import List
from .base import BaseSearch
from ..models import Paper
from ..paper_scraper import UnifiedWebScraper
import logging
import json

logger = logging.getLogger(__name__)

class OpenAlexSearch(BaseSearch):
    def __init__(self, email: str):
        self.base_url = "https://api.openalex.org"
        self.email = email
        self.semaphore = asyncio.Semaphore(5)

    def _validate_url(self, url: str) -> bool:
        """Validate if the provided URL is a valid OpenAlex API URL."""
        parsed = urllib.parse.urlparse(url)
        if not (parsed.scheme and parsed.netloc):
            return False
        if not parsed.path.startswith("/works"):
            return False
        return True

    async def search(self, url: str, limit: int = 30) -> List[Paper]:
        """
        Execute search against OpenAlex API using a full URL.
        
        Args:
            url (str): Full OpenAlex API URL to fetch results from.
            limit (int): Maximum number of papers to return and scrape.
        
        Returns:
            List[Paper]: A list of Paper objects parsed from the results.
        """
        if not self._validate_url(url):
            logger.error(f"Invalid OpenAlex API URL: {url}")
            return []

        logger.info("OpenAlex: Starting search")
        logger.debug(f"OpenAlex URL: {url}")
        
        async with aiohttp.ClientSession() as session:
            async with self.semaphore:
                try:
                    async with session.get(url) as response:
                        response_text = await response.text()
                        
                        if response.status != 200:
                            logger.error(f"OpenAlex error {response.status}: {response_text[:500]}")
                            return []
                            
                        try:
                            data = json.loads(response_text)
                        except json.JSONDecodeError as e:
                            logger.error(f"OpenAlex JSON parse error: {str(e)}")
                            logger.debug(f"Response text: {response_text[:500]}")
                            return []
                        
                        total_results = data.get("meta", {}).get("count", 0)
                        if total_results == 0:
                            logger.info("OpenAlex: No results found")
                            logger.debug(f"Empty response for URL: {url}")
                            return []
                            
                        results = data.get("results", [])
                        logger.info(f"OpenAlex: Found {total_results} matches, processing top {limit} results")
                        
                        # Sort results by relevance score before processing
                        sorted_results = sorted(
                            results,
                            key=lambda x: x.get("relevance_score", 0) or 0,  # Handle None values
                            reverse=True
                        )
                        
                        # Only take top N results based on limit
                        top_results = sorted_results[:limit]
                        
                        papers = await self._parse_results(top_results, session)
                        logger.info(f"OpenAlex: Successfully processed {len(papers)} papers")
                        
                        return papers
                        
                except Exception as e:
                    logger.error(f"OpenAlex search failed: {str(e)}")
                    logger.debug(f"Failed URL: {url}")
                    return []

    async def _parse_results(self, results: List[dict], session: aiohttp.ClientSession) -> List[Paper]:
        """Parse OpenAlex results with improved validation."""
        papers = []
        scraper = UnifiedWebScraper(session)
        
        try:
            for result in results:
                try:
                    # Basic validation
                    title = result.get("title", "")
                    if not title or not isinstance(title, str):
                        continue
                    title = title.strip()
                    if not title:
                        continue

                    # Get nested source info safely
                    primary_location = result.get("primary_location", {})
                    source_info = primary_location.get("source")
                    if source_info and isinstance(source_info, dict):
                        source_name = source_info.get("display_name", "")
                    else:
                        source_name = ""

                    # Extract DOI without https://doi.org/ prefix
                    doi = result.get("doi") or ""
                    if isinstance(doi, str):
                        if doi.startswith("https://doi.org/"):
                            doi = doi[len("https://doi.org/"):]
                        elif doi.startswith("http://doi.org/"):
                            doi = doi[len("http://doi.org/"):]
                        doi = doi.strip()
                    else:
                        doi = ""

                    # Extract authors safely
                    authorships = result.get("authorships", [])
                    authors = []
                    for auth in authorships:
                        if auth and isinstance(auth, dict):
                            author_info = auth.get("author")
                            if author_info and isinstance(author_info, dict):
                                author_name = author_info.get("display_name", "Unknown")
                                if isinstance(author_name, str):
                                    authors.append(author_name.strip())
                    if not authors:
                        authors = ["Unknown Author"]

                    # Create paper object with all available metadata
                    paper = Paper(
                        doi=doi,
                        title=title,
                        authors=authors,
                        year=result.get("publication_year", -1),
                        abstract=result.get("abstract", "") or "",
                        source=source_name,
                        citation_count=result.get("cited_by_count", -1),
                        pdf_link=primary_location.get("pdf_url"),
                        metadata={
                            "openalex_id": result.get("id", ""),
                            "type": result.get("type", "unknown"),
                            "is_oa": result.get("open_access", {}).get("is_oa", False),
                            "citations": result.get("cited_by_count", -1),
                            "concepts": [
                                c.get("display_name") 
                                for c in result.get("concepts", [])[:5]
                                if c and isinstance(c, dict)
                            ]
                        }
                    )

                    # Get full text if available
                    try:
                        if paper.doi:
                            paper.full_text = await scraper.scrape(f"https://doi.org/{paper.doi}")
                        elif paper.pdf_link:
                            paper.full_text = await scraper.scrape(paper.pdf_link)
                    except Exception as e:
                        logger.debug(f"Failed to get full text for {paper.title}: {str(e)}")
                        paper.full_text = None  # Ensure it's set to None on failure

                    papers.append(paper)
                    logger.debug(f"Processed paper: {paper.title}")

                except Exception as e:
                    logger.error(f"Error processing OpenAlex result: {str(e)}")
                    continue

            return papers
            
        except Exception as e:
            logger.error(f"OpenAlex results parsing failed: {str(e)}")
            return []
            
        finally:
            await scraper.close()

if __name__ == "__main__":
    # Configure logging
    log_dir = "logs/openalex"
    os.makedirs(log_dir, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(f"{log_dir}/test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
            logging.StreamHandler()
        ]
    )

    async def run_test():
        # Test queries with different limits to verify limit enforcement
        test_cases = [
            {
                "url": "https://api.openalex.org/works?search=%22precision+irrigation%22+%2B%22soil+moisture+sensors%22&sort=relevance_score:desc&per-page=30",
                "limit": 2,
                "description": "Testing small limit (2 papers)"
            },
            {
                "url": "https://api.openalex.org/works?search=%22machine+learning%22+%2B%22irrigation+management%22&sort=relevance_score:desc&per-page=30",
                "limit": 5,
                "description": "Testing medium limit (5 papers)"
            },
            {
                "url": "https://api.openalex.org/works?search=%22IoT+sensors%22+%2B%22irrigation%22&sort=relevance_score:desc&per-page=30",
                "limit": 1,
                "description": "Testing minimum limit (1 paper)"
            }
        ]

        try:
            email = "bryan.anye.5@gmail.com"
            if not email:
                logger.error("Email not provided")
                return

            searcher = OpenAlexSearch(email=email)
            
            for i, test_case in enumerate(test_cases, 1):
                logger.info(f"\n{'='*50}")
                logger.info(f"Test Case {i}/{len(test_cases)}: {test_case['description']}")
                logger.info(f"Requested limit: {test_case['limit']}")
                logger.info(f"Query URL: {test_case['url']}")
                
                try:
                    start_time = time.time()
                    results = await searcher.search(test_case['url'], limit=test_case['limit'])
                    elapsed_time = time.time() - start_time
                    
                    logger.info(f"\nResults Summary:")
                    logger.info(f"Retrieved {len(results)} papers (limit was {test_case['limit']})")
                    logger.info(f"Processing time: {elapsed_time:.2f} seconds")
                    
                    if len(results) > test_case['limit']:
                        logger.error(f"LIMIT VIOLATION: Got {len(results)} results, expected <= {test_case['limit']}")
                    
                    # Log paper details
                    for j, paper in enumerate(results, 1):
                        logger.info(f"\nPaper {j}:")
                        logger.info(f"Title: {paper.title}")
                        logger.info(f"Authors: {', '.join(paper.authors)}")
                        logger.info(f"Year: {paper.year}")
                        logger.info(f"DOI: {paper.doi}")
                        logger.info(f"Abstract length: {len(paper.abstract)} chars")
                        logger.info(f"Full text length: {len(paper.full_text) if paper.full_text else 0} chars")
                        logger.info(f"Citation count: {paper.citation_count}")
                        
                        # Verify we have either abstract or full text
                        if not paper.abstract and not paper.full_text:
                            logger.warning(f"Paper {j} has no content (neither abstract nor full text)")
                        
                        logger.info("Metadata:")
                        for key, value in paper.metadata.items():
                            logger.info(f"  {key}: {value}")
                    
                except Exception as e:
                    logger.error(f"Error processing test case {i}: {str(e)}", exc_info=True)
                    continue
                
                logger.info(f"\nCompleted test case {i}")
                await asyncio.sleep(2)  # Rate limiting between tests
                
        except Exception as e:
            logger.error(f"Test execution failed: {str(e)}", exc_info=True)

    # Add time tracking
    import time
    start_time = time.time()
    asyncio.run(run_test())
    total_time = time.time() - start_time
    logger.info(f"\nTotal test execution time: {total_time:.2f} seconds")