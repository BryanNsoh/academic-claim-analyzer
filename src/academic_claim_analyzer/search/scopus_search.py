# src/academic_claim_analyzer/search/scopus_search.py

import aiohttp
import asyncio
import os
from typing import List
from collections import deque
import time
from dotenv import load_dotenv
from .base import BaseSearch, SearchResult
import logging

logger = logging.getLogger(__name__)

load_dotenv()

class ScopusSearch(BaseSearch):
    def __init__(self):
        self.api_key = os.getenv("SCOPUS_API_KEY")
        if not self.api_key:
            raise ValueError("SCOPUS_API_KEY not found in environment variables")
        self.base_url = "http://api.elsevier.com/content/search/scopus"
        self.request_times = deque(maxlen=6)
        self.semaphore = asyncio.Semaphore(5)  # Limit to 5 concurrent requests

    async def search(self, query: str, limit: int) -> List[SearchResult]:
        headers = {
            "X-ELS-APIKey": self.api_key,
            "Accept": "application/json",
        }

        params = {
            "query": query,
            "count": limit,
            "view": "COMPLETE",
        }

        async with aiohttp.ClientSession() as session:
            async with self.semaphore:
                try:
                    # Ensure compliance with the rate limit
                    await self._wait_for_rate_limit()

                    async with session.get(self.base_url, headers=headers, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            return self._parse_results(data)
                        else:
                            logger.error(f"Scopus API request failed with status code: {response.status}")
                            return []
                except Exception as e:
                    logger.error(f"Error occurred while making Scopus API request: {str(e)}")
                    return []

    async def _wait_for_rate_limit(self):
        while True:
            current_time = time.time()
            if not self.request_times or current_time - self.request_times[0] >= 1:
                self.request_times.append(current_time)
                break
            else:
                await asyncio.sleep(0.2)

    def _parse_results(self, data: dict) -> List[SearchResult]:
        results = []
        for entry in data.get("search-results", {}).get("entry", []):
            result = SearchResult(
                doi=entry.get("prism:doi", ""),
                title=entry.get("dc:title", ""),
                authors=[author.get("authname", "") for author in entry.get("author", [])],
                year=int(entry.get("prism:coverDate", "").split("-")[0]),
                abstract=entry.get("dc:description", ""),
                pdf_link="",  # Scopus API doesn't provide direct PDF links
                source=entry.get("prism:publicationName", ""),
                metadata={
                    "citation_count": int(entry.get("citedby-count", 0)),
                    "scopus_id": entry.get("dc:identifier", ""),
                    "eid": entry.get("eid", "")
                }
            )
            results.append(result)
        return results