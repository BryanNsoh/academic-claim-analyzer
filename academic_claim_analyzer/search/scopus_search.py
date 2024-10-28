# academic_claim_analyzer/search/scopus_search.py

import aiohttp
import asyncio
import os
from typing import List
from collections import deque
import time
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
            "count": limit,
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
                                
                            return await self._parse_results(data, session)
                            
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

    async def _parse_results(self, data: dict, session: aiohttp.ClientSession) -> List[Paper]:
        """Parse Scopus results with improved error handling and logging."""
        results = []
        scraper = UnifiedWebScraper(session)
        
        try:
            entries = data.get("search-results", {}).get("entry", [])
            logger.info(f"Scopus: Processing {len(entries)} results")
            
            for entry in entries:
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

                    # Attempt to get full text
                    if result.doi:
                        result.full_text = await scraper.scrape(f"https://doi.org/{result.doi}")

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