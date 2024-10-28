# academic_claim_analyzer/search/openalex_search.py

import aiohttp
import asyncio
import urllib.parse
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

    def _build_search_url(self, query: str, limit: int) -> str:
        """Build OpenAlex search URL with proper encoding."""
        # Remove any existing URL encoding
        query = urllib.parse.unquote(query)
        # Remove explicit + signs
        query = query.replace('+', ' ')
        
        params = {
            'search': query,
            'per-page': str(limit),
            'mailto': self.email,
            'sort': 'relevance_score:desc'
        }
        
        url = f"{self.base_url}/works?{urllib.parse.urlencode(params)}"
        logger.debug(f"OpenAlex URL: {url}")
        return url

    async def search(self, query: str, limit: int) -> List[Paper]:
        """Execute search against OpenAlex API with improved logging."""
        logger.info(f"OpenAlex: Starting search")
        logger.debug(f"OpenAlex query: {query}")
        
        async with aiohttp.ClientSession() as session:
            search_url = self._build_search_url(query, limit)
            
            async with self.semaphore:
                try:
                    async with session.get(search_url) as response:
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
                            logger.debug(f"Empty response for URL: {search_url}")
                            return []
                            
                        results = data.get("results", [])
                        logger.info(f"OpenAlex: Found {total_results} matches, processing {len(results)} results")
                        
                        papers = await self._parse_results(results, session)
                        logger.info(f"OpenAlex: Successfully processed {len(papers)} papers")
                        
                        return papers
                        
                except Exception as e:
                    logger.error(f"OpenAlex search failed: {str(e)}")
                    logger.debug(f"Failed URL: {search_url}")
                    return []

    async def _parse_results(self, results: List[dict], session: aiohttp.ClientSession) -> List[Paper]:
        """Parse OpenAlex results with improved validation."""
        papers = []
        scraper = UnifiedWebScraper(session)
        
        try:
            for result in results:
                try:
                    # Basic validation
                    title = result.get("title", "").strip()
                    if not title:
                        continue

                    # Get nested source info
                    source_info = result.get("primary_location", {}).get("source", {})
                    source_name = source_info.get("display_name", "")
                    
                    # Extract DOI without https://doi.org/ prefix
                    doi = result.get("doi", "")
                    if doi.startswith("https://doi.org/"):
                        doi = doi[len("https://doi.org/"):]

                    # Create paper object with all available metadata
                    paper = Paper(
                        doi=doi,
                        title=title,
                        authors=[
                            auth.get("author", {}).get("display_name", "Unknown")
                            for auth in result.get("authorships", [])
                        ] or ["Unknown Author"],
                        year=result.get("publication_year", -1),
                        abstract=result.get("abstract", ""),
                        source=source_name,
                        citation_count=result.get("cited_by_count", -1),
                        pdf_link=result.get("primary_location", {}).get("pdf_url"),
                        metadata={
                            "openalex_id": result.get("id", ""),
                            "type": result.get("type", "unknown"),
                            "is_oa": result.get("open_access", {}).get("is_oa", False),
                            "citations": result.get("cited_by_count", -1),
                            "concepts": [
                                c.get("display_name") 
                                for c in result.get("concepts", [])[:5]
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