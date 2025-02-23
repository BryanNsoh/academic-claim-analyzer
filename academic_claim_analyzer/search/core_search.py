import aiohttp
import os
import random  # <-- NEW
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

logger = logging.getLogger(__name__)

load_dotenv(override=True)

class CORESearch(BaseSearch):
    def __init__(self):
        self.api_key = os.getenv("CORE_API_KEY")
        if not self.api_key:
            raise ValueError("CORE_API_KEY not found in environment variables")
        self.base_url = "https://api.core.ac.uk/v3"
        self.semaphore = asyncio.Semaphore(2)  # concurrency of 2, as before

    async def search(self, query: str, limit: int) -> List[Paper]:
        """Execute search against CORE API with exponential backoff retry on 500 errors or JSON parse failures."""
        logger.info(f"CORE: Starting search with limit {limit}")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

        # Over-fetch so we can filter/sort
        params = {
            "q": query,
            "limit": limit * 2,
            "scroll": True,
            "sort": "relevance"
        }

        logger.debug(f"CORE API request parameters: {json.dumps(params, indent=2)}")

        # We'll attempt up to 5 times if the API returns 500 or invalid JSON
        max_attempts = 5

        async with aiohttp.ClientSession() as session:
            for attempt in range(max_attempts):
                try:
                    async with self.semaphore:
                        async with session.post(
                            f"{self.base_url}/search/works",
                            headers=headers,
                            json=params
                        ) as response:
                            resp_text = await response.text()
                            logger.debug(f"CORE API raw response (attempt {attempt+1}): {resp_text[:500]}")

                            if response.status == 200:
                                # Parse JSON
                                try:
                                    data = json.loads(resp_text)
                                except json.JSONDecodeError as e:
                                    logger.error(f"Failed to parse CORE API response: {str(e)}")
                                    raise RuntimeError("JSON parse error")  # triggers retry

                                total_results = data.get("totalHits", 0)
                                logger.info(f"CORE: Found {total_results} total matches")

                                if not total_results:
                                    logger.info("CORE: No results found for query")
                                    return []

                                # success: parse them
                                results = await self._parse_results(data, session, limit)
                                logger.info(f"CORE: Successfully retrieved {len(results)} valid papers")
                                return results

                            else:
                                # 4xx or 5xx
                                logger.error(f"CORE: API error {response.status}")
                                logger.error(f"CORE: Response: {resp_text[:500]}")

                                # We'll only retry on 500.
                                if response.status == 500:
                                    raise RuntimeError(f"CORE 500 error on attempt {attempt+1}")
                                else:
                                    # e.g. 404, 401, 429 => return empty and do not retry
                                    return []

                except Exception as e:
                    # If we fail with 500 or parse error, do an exponential backoff
                    if attempt < max_attempts - 1:
                        backoff = (2 ** attempt) + random.random()  # e.g. 1,2,4,... plus up to 1s jitter
                        logger.warning(f"CORE: Attempt {attempt+1} failed ({e}). Retrying in {backoff:.1f}s...")
                        await asyncio.sleep(backoff)
                    else:
                        logger.error(f"CORE: All retries failed - {str(e)}")
                        return []

            # In theory we never reach here since we return in the loop
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
        """Extract author names with improved validation."""
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
        """Extract publication year with improved validation."""
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
        """Parse CORE API response with improved validation and metrics."""
        results = []
        valid_count = 0
        invalid_count = 0
        scraper = UnifiedWebScraper(session)
        
        try:
            entries = data.get('results', [])
            logger.info(f"CORE: Processing {len(entries)} results")

            # Sort entries by citation count if available
            sorted_entries = sorted(
                entries,
                key=lambda x: int(x.get('citationCount', 0) or 0),
                reverse=True
            )[:limit]  # Only process top N entries

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

                    # Only get full text for the ones we keep
                    try:
                        if paper.doi:
                            paper.full_text = await scraper.scrape(f"https://doi.org/{paper.doi}")
                        elif paper.pdf_link:
                            paper.full_text = await scraper.scrape(paper.pdf_link)
                    except Exception as e:
                        logger.debug(f"Failed to get full text for {paper.title}: {str(e)}")
                        paper.full_text = None

                    # Must have an abstract or full text
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


if __name__ == "__main__":
    # Minimal test code
    import os
    import logging
    from datetime import datetime
    import asyncio

    log_dir = "logs/core"
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
        test_query = 'title:("precision agriculture")'
        searcher = CORESearch()
        results = await searcher.search(test_query, limit=2)
        print(f"Got {len(results)} results.")

    asyncio.run(run_test())
