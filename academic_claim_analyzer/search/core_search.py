# academic_claim_analyzer/search/core_search.py

import aiohttp
import os
import random
from typing import List, Optional, Dict, Any
from datetime import datetime
from dotenv import load_dotenv
from .base import BaseSearch
from ..models import Paper
from ..paper_scraper import UnifiedWebScraper
import logging
import json
import asyncio
import time

from ..search.search_config import GlobalSearchConfig, calculate_backoff

logger = logging.getLogger(__name__)

load_dotenv(override=True)

class CORESearch(BaseSearch):
    def __init__(self):
        self.api_key = os.getenv("CORE_API_KEY")
        if not self.api_key:
            raise ValueError("CORE_API_KEY not found in environment variables")
        self.base_url = "https://api.core.ac.uk/v3"
        # concurrency from global config
        self.semaphore = asyncio.Semaphore(GlobalSearchConfig.core_concurrency)

    async def search(self, query: str, limit: int) -> List[Paper]:
        """Execute search against CORE API with exponential backoff on 500 or JSON parse failures."""
        logger.info(f"CORE: Starting search with limit {limit}")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }
        params = {
            "q": query,
            "limit": limit * 2,
            "scroll": True,
            "sort": "relevance"
        }

        logger.debug(f"CORE API request parameters: {json.dumps(params, indent=2)}")

        max_attempts = GlobalSearchConfig.max_retries

        async with aiohttp.ClientSession() as session:
            for attempt in range(max_attempts):
                async with self.semaphore:
                    try:
                        async with session.post(
                            f"{self.base_url}/search/works",
                            headers=headers,
                            json=params
                        ) as response:
                            resp_text = await response.text()
                            logger.debug(f"CORE API raw response (attempt {attempt+1}): {resp_text[:500]}")

                            if response.status == 200:
                                try:
                                    data = json.loads(resp_text)
                                except json.JSONDecodeError as e:
                                    logger.error(f"Failed to parse CORE API response: {str(e)}")
                                    if attempt < max_attempts - 1:
                                        backoff = calculate_backoff(attempt)
                                        logger.warning(f"CORE: JSON parse error. backoff={backoff:.1f}s attempt={attempt}")
                                        await asyncio.sleep(backoff)
                                        continue
                                    return []

                                total_results = data.get("totalHits", 0)
                                logger.info(f"CORE: Found {total_results} total matches")

                                if not total_results:
                                    logger.info("CORE: No results found for query")
                                    return []

                                results = await self._parse_results(data, session, limit)
                                logger.info(f"CORE: Successfully retrieved {len(results)} valid papers")
                                return results

                            else:
                                logger.error(f"CORE: API error {response.status}")
                                logger.error(f"CORE: Response: {resp_text[:500]}")
                                # Retry if 5xx
                                if 500 <= response.status < 600 and attempt < max_attempts - 1:
                                    backoff = calculate_backoff(attempt)
                                    logger.warning(f"CORE: 5xx error. backoff={backoff:.1f}s attempt={attempt}")
                                    await asyncio.sleep(backoff)
                                    continue
                                else:
                                    return []
                    except Exception as e:
                        logger.error(f"CORE: Unexpected error - {str(e)}")
                        if attempt < max_attempts - 1:
                            backoff = calculate_backoff(attempt)
                            logger.warning(f"CORE: Exception, backoff={backoff:.1f}s attempt={attempt}")
                            await asyncio.sleep(backoff)
                            continue
                        return []
            return []

    def _extract_string_value(self, data: Any) -> str:
        """Safely extract string value from various data types."""
        if isinstance(data, str):
            return data.strip()
        elif isinstance(data, (list, tuple)) and data:
            return str(data[0]).strip()
        elif isinstance(data, dict) and 'name' in data:
            return str(data['name']).strip()
        return ""

    def _safe_extract_authors(self, entry: Dict[str, Any]) -> List[str]:
        authors = []
        author_data = entry.get('authors', [])
        
        if isinstance(author_data, list):
            for author in author_data:
                if isinstance(author, dict):
                    name = author.get('name', '').strip()
                    if name:
                        authors.append(name)
                elif isinstance(author, str):
                    name = author.strip()
                    if name:
                        authors.append(name)
        elif isinstance(author_data, dict):
            name = author_data.get('name', '').strip()
            if name:
                authors.append(name)
                
        return authors or ["Unknown Author"]

    def _safe_extract_year(self, entry: Dict[str, Any]) -> int:
        try:
            for field in ['yearPublished', 'publishedDate', 'createdDate']:
                value = entry.get(field)
                if value:
                    if isinstance(value, int):
                        return value
                    elif isinstance(value, str):
                        year = int(value.split('-')[0])
                        if 1900 <= year <= 2100:
                            return year
            return -1
        except (ValueError, IndexError, TypeError):
            return -1

    async def _parse_results(self, data: Dict[str, Any], session: aiohttp.ClientSession, limit: int) -> List[Paper]:
        results = []
        valid_count = 0
        invalid_count = 0
        scraper = UnifiedWebScraper(session)
        
        try:
            entries = data.get('results', [])
            logger.info(f"CORE: Processing {len(entries)} results")

            sorted_entries = sorted(
                entries,
                key=lambda x: int(x.get('citationCount', 0) or 0),
                reverse=True
            )[:limit]

            for entry in sorted_entries:
                try:
                    if not isinstance(entry, dict):
                        invalid_count += 1
                        continue

                    title = self._extract_string_value(entry.get('title', ''))
                    if not title:
                        logger.debug("CORE: Skipping entry without title")
                        invalid_count += 1
                        continue

                    authors = self._safe_extract_authors(entry)
                    year = self._safe_extract_year(entry)
                    abstract = self._extract_string_value(entry.get('abstract', ''))

                    paper = Paper(
                        doi=self._extract_string_value(entry.get('doi', '')),
                        title=title,
                        authors=authors,
                        year=year,
                        abstract=abstract,
                        source=self._extract_string_value(entry.get('publisher', '')),
                        pdf_link=self._extract_string_value(entry.get('downloadUrl', '')),
                        metadata={
                            'core_id': str(entry.get('id', '')),
                            'language': self._extract_string_value(
                                entry.get('language', {}).get('code', 'en')
                            ),
                            'repositories': len(entry.get('repositories', [])),
                            'citation_count': entry.get('citationCount', -1)
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

                    if paper.abstract or paper.full_text:
                        results.append(paper)
                        valid_count += 1
                        if valid_count >= limit:
                            break
                    else:
                        logger.debug(f"CORE: Skipping paper without content: {title}")
                        invalid_count += 1

                except Exception as e:
                    logger.error(f"CORE: Error processing entry - {str(e)}")
                    invalid_count += 1
                    continue

            logger.info(f"CORE: Processing complete - {valid_count} valid, {invalid_count} invalid")
            return results

        except Exception as e:
            logger.error(f"CORE: Results parsing failed - {str(e)}")
            return []
        finally:
            await scraper.close()
