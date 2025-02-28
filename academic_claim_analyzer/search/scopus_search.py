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

from ..search.search_config import GlobalSearchConfig, calculate_backoff

logger = logging.getLogger(__name__)

load_dotenv(override=True)

class ScopusSearch(BaseSearch):
    def __init__(self):
        self.api_key = os.getenv("SCOPUS_API_KEY")
        if not self.api_key:
            raise ValueError("SCOPUS_API_KEY not found in environment variables")
        self.base_url = "http://api.elsevier.com/content/search/scopus"
        # concurrency from global config
        self.semaphore = asyncio.Semaphore(GlobalSearchConfig.scopus_concurrency)
        self.request_times = deque(maxlen=6)

    def _validate_query(self, query: str) -> bool:
        invalid_patterns = [
            'W/n W/',
            'PRE/n PRE/',
            'AND NOT AND',
            '{*}', '(*)'
        ]
        return not any(pattern in query for pattern in invalid_patterns)

    async def search(self, query: str, limit: int) -> List[Paper]:
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

        max_attempts = GlobalSearchConfig.max_retries
        async with aiohttp.ClientSession() as session:
            for attempt in range(max_attempts):
                async with self.semaphore:
                    try:
                        if attempt > 0:
                            backoff_time = calculate_backoff(attempt - 1)
                            logger.warning(f"Scopus: Retrying search, backoff={backoff_time:.1f}s attempt={attempt}")
                            await asyncio.sleep(backoff_time)

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
                                # Retry if 5xx
                                if 500 <= response.status < 600 and attempt < max_attempts - 1:
                                    continue
                                return []
                    except json.JSONDecodeError as e:
                        logger.error(f"Scopus: Invalid JSON response - {str(e)}")
                        if attempt < max_attempts - 1:
                            continue
                        return []
                    except Exception as e:
                        logger.error(f"Scopus: Search failed - {str(e)}")
                        if attempt < max_attempts - 1:
                            continue
                        return []
            return []

    async def _wait_for_rate_limit(self):
        """Handle rate limiting with improved logging; keep shape from original code."""
        current_time = time.time()
        if self.request_times and current_time - self.request_times[0] < 1:
            wait_time = 1 - (current_time - self.request_times[0])
            logger.debug(f"Scopus: Rate limit wait {wait_time:.2f}s")
            await asyncio.sleep(wait_time)
        self.request_times.append(current_time)

    async def _parse_results(self, data: dict, session: aiohttp.ClientSession, limit: int) -> List[Paper]:
        results = []
        scraper = UnifiedWebScraper(session)
        
        try:
            entries = data.get("search-results", {}).get("entry", [])
            logger.info(f"Scopus: Processing {min(len(entries), limit)} results")
            
            sorted_entries = sorted(
                entries,
                key=lambda x: int(x.get("citedby-count", 0)),
                reverse=True
            )[:limit]

            for entry in sorted_entries:
                try:
                    year = -1
                    cover_date = entry.get("prism:coverDate", "")
                    if cover_date:
                        try:
                            year = int(cover_date.split("-")[0])
                        except (ValueError, IndexError):
                            logger.debug(f"Scopus: Invalid year format: {cover_date}")

                    try:
                        citation_count = int(entry.get("citedby-count", -1))
                    except (ValueError, TypeError):
                        citation_count = -1

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

                    if result.doi:
                        try:
                            result.full_text = await scraper.scrape(f"https://doi.org/{result.doi}")
                        except Exception as e:
                            logger.debug(f"Failed to get full text for {result.title}: {str(e)}")
                            result.full_text = None

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
