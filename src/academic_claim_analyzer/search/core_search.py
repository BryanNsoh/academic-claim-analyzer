# src/academic_claim_analyzer/search/core_search.py

import aiohttp
import os
from typing import List
from dotenv import load_dotenv
from .base import BaseSearch, SearchResult
import logging

logger = logging.getLogger(__name__)

load_dotenv()

class CORESearch(BaseSearch):
    def __init__(self):
        self.api_key = os.getenv("CORE_API_KEY")
        if not self.api_key:
            raise ValueError("CORE_API_KEY not found in environment variables")
        self.base_url = "https://api.core.ac.uk/v3"

    async def search(self, query: str, limit: int) -> List[SearchResult]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

        params = {
            "q": query,
            "limit": limit,
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(f"{self.base_url}/search/works", headers=headers, json=params) as response:
                    if response.status == 200:
                        logger.info("CORE API request successful.")
                        data = await response.json()
                        return self._parse_results(data)
                    else:
                        logger.error(f"CORE API request failed with status code: {response.status}")
                        return []
            except Exception as e:
                logger.error(f"Error occurred while making CORE API request: {str(e)}")
                return []

    def _parse_results(self, data: dict) -> List[SearchResult]:
        results = []
        for entry in data.get("results", []):
            result = SearchResult(
                doi=entry.get("doi", ""),
                title=entry.get("title", ""),
                authors=[author["name"] for author in entry.get("authors", [])],
                year=entry.get("publicationYear", 0),
                abstract=entry.get("abstract", ""),
                pdf_link=entry.get("downloadUrl", ""),
                source=entry.get("publisher", ""),
                full_text=entry.get("fullText", ""),  # Directly assign full_text
                metadata={
                    "citation_count": entry.get("citationCount", 0),
                    "core_id": entry.get("id", "")
                }
            )
            results.append(result)
        return results