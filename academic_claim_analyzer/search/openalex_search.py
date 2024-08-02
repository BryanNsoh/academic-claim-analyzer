# academic_claim_analyzer/search/openalex_search.py

import aiohttp
import asyncio
import urllib.parse
from typing import List
from .base import BaseSearch
from ..models import Paper
from ..paper_scraper import UnifiedWebScraper
import logging

logger = logging.getLogger(__name__)

class OpenAlexSearch(BaseSearch):
    def __init__(self, email: str):
        self.base_url = "https://api.openalex.org"
        self.email = email
        self.semaphore = asyncio.Semaphore(5)  # Limit to 5 concurrent requests

    async def search(self, query: str, limit: int) -> List[Paper]:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600)) as session:
            encoded_query = urllib.parse.quote(query)
            search_url = f"{self.base_url}/works?search={encoded_query}&per_page={limit}&mailto={self.email}"

            async with self.semaphore:
                try:
                    await asyncio.sleep(0.2)  # Rate limiting
                    async with session.get(search_url) as response:
                        if response.status == 200:
                            data = await response.json()
                            return await self._parse_results(data, session)
                        else:
                            logger.error(f"Unexpected status code from OpenAlex API: {response.status}")
                            return []
                except Exception as e:
                    logger.error(f"Error occurred while making request to OpenAlex API: {str(e)}")
                    return []

    async def _parse_results(self, data: dict, session: aiohttp.ClientSession) -> List[Paper]:
        results = []
        scraper = UnifiedWebScraper(session)
        for work in data.get("results", []):
            result = Paper(
                doi=work.get("doi", ""),
                title=work.get("title", ""),
                authors=[author["author"]["display_name"] for author in work.get("authorships", [])],
                year=work.get("publication_year", 0),
                abstract=work.get("abstract"),
                pdf_link=work.get("primary_location", {}).get("pdf_url"),
                source=work.get("primary_location", {}).get("source", {}).get("display_name", ""),
                metadata={
                    "citation_count": work.get("cited_by_count", 0),
                    "openalex_id": work.get("id", "")
                }
            )
            try:
                if result.doi:
                    result.full_text = await scraper.scrape(f"https://doi.org/{result.doi}")
                if not result.full_text and result.pdf_link:
                    result.full_text = await scraper.scrape(result.pdf_link)
            except Exception as e:
                logger.error(f"Error scraping full text for {result.doi or result.pdf_link}: {str(e)}")
            results.append(result)
        await scraper.close()
        return results