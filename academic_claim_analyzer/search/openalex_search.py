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

from ..search.search_config import GlobalSearchConfig, calculate_backoff

logger = logging.getLogger(__name__)

class OpenAlexSearch(BaseSearch):
    def __init__(self, email: str):
        self.base_url = "https://api.openalex.org"
        self.email = email
        # concurrency from global config
        self.semaphore = asyncio.Semaphore(GlobalSearchConfig.openalex_concurrency)

    def _validate_url(self, url: str) -> bool:
        parsed = urllib.parse.urlparse(url)
        if not (parsed.scheme and parsed.netloc):
            return False
        if not parsed.path.startswith("/works"):
            return False
        return True

    async def search(self, url: str, limit: int = 30) -> List[Paper]:
        """
        Execute search against OpenAlex API using a full URL.
        """
        if not self._validate_url(url):
            logger.error(f"Invalid OpenAlex API URL: {url}")
            return []

        logger.info("OpenAlex: Starting search")
        logger.debug(f"OpenAlex URL: {url}")

        max_attempts = GlobalSearchConfig.max_retries
        async with aiohttp.ClientSession() as session:
            for attempt in range(max_attempts):
                async with self.semaphore:
                    try:
                        if attempt > 0:
                            backoff_time = calculate_backoff(attempt - 1)
                            logger.warning(f"OpenAlex: Retrying fetch, backoff={backoff_time:.1f}s attempt={attempt}")
                            await asyncio.sleep(backoff_time)

                        async with session.get(url) as response:
                            response_text = await response.text()

                            if response.status != 200:
                                logger.error(f"OpenAlex error {response.status}: {response_text[:500]}")
                                if 500 <= response.status < 600 and attempt < max_attempts - 1:
                                    continue
                                return []

                            try:
                                data = json.loads(response_text)
                            except json.JSONDecodeError as e:
                                logger.error(f"OpenAlex JSON parse error: {str(e)}")
                                if attempt < max_attempts - 1:
                                    continue
                                return []

                            total_results = data.get("meta", {}).get("count", 0)
                            if total_results == 0:
                                logger.info("OpenAlex: No results found")
                                logger.debug(f"Empty response for URL: {url}")
                                return []

                            results = data.get("results", [])
                            logger.info(f"OpenAlex: Found {total_results} matches, processing top {limit} results")

                            sorted_results = sorted(
                                results,
                                key=lambda x: x.get("relevance_score", 0) or 0,
                                reverse=True
                            )
                            top_results = sorted_results[:limit]

                            papers = await self._parse_results(top_results, session)
                            logger.info(f"OpenAlex: Successfully processed {len(papers)} papers")
                            return papers

                    except Exception as e:
                        logger.error(f"OpenAlex search failed: {str(e)}")
                        if attempt < max_attempts - 1:
                            backoff_time = calculate_backoff(attempt)
                            await asyncio.sleep(backoff_time)
                            continue
                        return []
            return []

    async def _parse_results(self, results: List[dict], session: aiohttp.ClientSession) -> List[Paper]:
        papers = []
        scraper = UnifiedWebScraper(session)
        
        try:
            for result in results:
                try:
                    title = result.get("title", "")
                    if not title or not isinstance(title, str):
                        continue
                    title = title.strip()
                    if not title:
                        continue

                    primary_location = result.get("primary_location", {})
                    source_info = primary_location.get("source")
                    if source_info and isinstance(source_info, dict):
                        source_name = source_info.get("display_name", "")
                    else:
                        source_name = ""

                    doi = result.get("doi") or ""
                    if isinstance(doi, str):
                        if doi.startswith("https://doi.org/"):
                            doi = doi[len("https://doi.org/"):]
                        elif doi.startswith("http://doi.org/"):
                            doi = doi[len("http://doi.org/"):]
                        doi = doi.strip()
                    else:
                        doi = ""

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

                    try:
                        if paper.doi:
                            paper.full_text = await scraper.scrape(f"https://doi.org/{paper.doi}")
                        elif paper.pdf_link:
                            paper.full_text = await scraper.scrape(paper.pdf_link)
                    except Exception as e:
                        logger.debug(f"Failed to get full text for {paper.title}: {str(e)}")
                        paper.full_text = None

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
