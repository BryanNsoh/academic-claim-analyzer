# academic_claim_analyzer/search/scopus_search.py
# To run: python -m academic_claim_analyzer.search.scopus_search

import aiohttp
import asyncio
import os
from typing import List
from collections import deque
import time
from datetime import datetime
from dotenv import load_dotenv
from .base import BaseSearch
from ..models import Paper
from ..paper_scraper import UnifiedWebScraper
import logging
import json

logger = logging.getLogger(__name__)

load_dotenv(override=True)

class ScopusSearch(BaseSearch):
    def __init__(self):
        self.api_key = os.getenv("SCOPUS_API_KEY")
        if not self.api_key:
            raise ValueError("SCOPUS_API_KEY not found in environment variables")
        self.base_url = "http://api.elsevier.com/content/search/scopus"
        self.request_times = deque(maxlen=6)
        self.semaphore = asyncio.Semaphore(5)

    def _validate_query(self, query: str) -> bool:
        """Validate Scopus query syntax."""
        invalid_patterns = [
            'W/n W/',  # Multiple proximity operators
            'PRE/n PRE/',  # Multiple precedence operators
            'AND NOT AND',  # Invalid AND NOT usage
            '{*}', '(*)'  # Invalid wildcard usage
        ]
        return not any(pattern in query for pattern in invalid_patterns)

    async def search(self, query: str, limit: int) -> List[Paper]:
        """Execute search against Scopus API with improved error handling and logging."""
        logger.info(f"Scopus: Starting search with limit {limit}")
        
        if not self._validate_query(query):
            logger.error("Scopus: Invalid query syntax detected")
            return []

        headers = {
            "X-ELS-APIKey": self.api_key,
            "Accept": "application/json",
        }
        
        params = {
            "query": query,
            "count": limit,  # Only request the number we need
            "view": "COMPLETE",
            "sort": "-citedby-count"
        }

        async with aiohttp.ClientSession() as session:
            async with self.semaphore:
                try:
                    await self._wait_for_rate_limit()
                    
                    async with session.get(self.base_url, headers=headers, params=params) as response:
                        response_text = await response.text()
                        
                        if response.status == 200:
                            data = json.loads(response_text)
                            total_results = int(data.get("search-results", {}).get("opensearch:totalResults", 0))
                            logger.info(f"Scopus: Found {total_results} total matches")
                            
                            if not total_results:
                                logger.info("Scopus: No results found for query")
                                return []
                                
                            return await self._parse_results(data, session, limit)
                            
                        else:
                            logger.error(f"Scopus: API error {response.status}")
                            logger.error(f"Scopus: Response: {response_text[:500]}")
                            return []
                            
                except json.JSONDecodeError as e:
                    logger.error(f"Scopus: Invalid JSON response - {str(e)}")
                    return []
                except Exception as e:
                    logger.error(f"Scopus: Search failed - {str(e)}")
                    return []

    async def _wait_for_rate_limit(self):
        """Handle rate limiting with improved logging."""
        current_time = time.time()
        if self.request_times and current_time - self.request_times[0] < 1:
            wait_time = 1 - (current_time - self.request_times[0])
            logger.debug(f"Scopus: Rate limit wait {wait_time:.2f}s")
            await asyncio.sleep(wait_time)
        self.request_times.append(current_time)

    async def _parse_results(self, data: dict, session: aiohttp.ClientSession, limit: int) -> List[Paper]:
        """Parse Scopus results with improved error handling and logging."""
        results = []
        scraper = UnifiedWebScraper(session)
        
        try:
            entries = data.get("search-results", {}).get("entry", [])
            logger.info(f"Scopus: Processing {min(len(entries), limit)} results")
            
            # Sort entries by citation count before processing
            sorted_entries = sorted(
                entries,
                key=lambda x: int(x.get("citedby-count", 0)),
                reverse=True
            )[:limit]  # Only take top N entries
            
            for entry in sorted_entries:
                try:
                    # Extract and validate year
                    year = -1
                    cover_date = entry.get("prism:coverDate", "")
                    if cover_date:
                        try:
                            year = int(cover_date.split("-")[0])
                        except (ValueError, IndexError):
                            logger.debug(f"Scopus: Invalid year format: {cover_date}")

                    # Extract citation count
                    try:
                        citation_count = int(entry.get("citedby-count", -1))
                    except (ValueError, TypeError):
                        citation_count = -1

                    # Extract authors
                    authors = []
                    for author in entry.get("author", []):
                        try:
                            author_name = author.get("authname", "").strip()
                            if author_name:
                                authors.append(author_name)
                        except Exception:
                            continue
                    
                    if not authors:
                        authors = ["Unknown Author"]

                    # Create Paper object
                    result = Paper(
                        doi=entry.get("prism:doi", ""),
                        title=entry.get("dc:title", ""),
                        authors=authors,
                        year=year,
                        abstract=entry.get("dc:description", ""),
                        source=entry.get("prism:publicationName", ""),
                        citation_count=citation_count,
                        metadata={
                            "scopus_id": entry.get("dc:identifier", ""),
                            "eid": entry.get("eid", ""),
                            "source_type": entry.get("prism:aggregationType", ""),
                            "subtype": entry.get("subtypeDescription", "")
                        }
                    )

                    # Only attempt to get full text if we have a DOI
                    if result.doi:
                        try:
                            result.full_text = await scraper.scrape(f"https://doi.org/{result.doi}")
                        except Exception as e:
                            logger.debug(f"Failed to get full text for {result.title}: {str(e)}")
                            result.full_text = None

                    # Validate result has minimum required data
                    if result.title and (result.abstract or result.full_text):
                        results.append(result)
                    else:
                        logger.debug(f"Scopus: Skipping paper with insufficient data: {result.title}")

                except Exception as e:
                    logger.error(f"Scopus: Error processing entry - {str(e)}")
                    continue

            logger.info(f"Scopus: Successfully retrieved {len(results)} valid papers")
            
        except Exception as e:
            logger.error(f"Scopus: Results parsing failed - {str(e)}")
        finally:
            await scraper.close()
            
        return results

if __name__ == "__main__":
    # Configure logging
    log_dir = "logs/scopus"
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
        # Test cases with different limits and queries
        test_cases = [
            {
                "query": 'TITLE-ABS-KEY((\"precision agriculture\" OR \"precision farming\") AND (\"machine learning\" OR \"AI\") AND \"water\")',
                "limit": 2,
                "description": "Testing small limit (2 papers)"
            },
            {
                "query": 'TITLE-ABS-KEY((iot OR \"internet of things\") AND (irrigation OR watering) AND sensor*)',
                "limit": 5,
                "description": "Testing medium limit (5 papers)"
            },
            {
                "query": 'TITLE-ABS-KEY((\"precision farming\" OR \"precision agriculture\") AND (\"deep learning\" OR \"neural networks\") AND \"water\")',
                "limit": 1,
                "description": "Testing minimum limit (1 paper)"
            }
        ]

        try:
            searcher = ScopusSearch()
            
            for i, test_case in enumerate(test_cases, 1):
                logger.info(f"\n{'='*50}")
                logger.info(f"Test Case {i}/{len(test_cases)}: {test_case['description']}")
                logger.info(f"Requested limit: {test_case['limit']}")
                logger.info(f"Query: {test_case['query']}")
                
                try:
                    start_time = time.time()
                    results = await searcher.search(test_case['query'], limit=test_case['limit'])
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
    start_time = time.time()
    asyncio.run(run_test())
    total_time = time.time() - start_time
    logger.info(f"\nTotal test execution time: {total_time:.2f} seconds")