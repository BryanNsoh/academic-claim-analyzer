# academic_claim_analyzer/search/core_search.py
# To run: python -m academic_claim_analyzer.search.core_search

import aiohttp
import os
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
        self.semaphore = asyncio.Semaphore(5)

    async def search(self, query: str, limit: int) -> List[Paper]:
        """Execute search against CORE API with improved logging."""
        logger.info(f"CORE: Starting search with limit {limit}")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

        # Fixed sort parameter format
        params = {
            "q": query,
            "limit": limit * 2,  # Request extra to allow for filtering
            "scroll": True,
            "sort": "citations:desc"  # Correct string format
        }

        logger.debug(f"CORE API request parameters: {json.dumps(params, indent=2)}")

        async with aiohttp.ClientSession() as session:
            try:
                async with self.semaphore, session.post(
                    f"{self.base_url}/search/works", 
                    headers=headers, 
                    json=params
                ) as response:
                    response_text = await response.text()
                    logger.debug(f"CORE API raw response: {response_text[:500]}")
                    
                    if response.status == 200:
                        try:
                            data = json.loads(response_text)
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse CORE API response: {str(e)}")
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
                        logger.error(f"CORE: Response: {response_text[:500]}")
                        return []
                        
            except Exception as e:
                logger.error(f"CORE: Search failed - {str(e)}")
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
                        if 1900 <= year <= 2100:  # Basic sanity check
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

                    # Extract all required fields
                    title = self._extract_string_value(entry.get('title', ''))
                    if not title:
                        logger.debug("CORE: Skipping entry without title")
                        invalid_count += 1
                        continue

                    authors = self._safe_extract_authors(entry)
                    year = self._safe_extract_year(entry)
                    abstract = self._extract_string_value(entry.get('abstract', ''))
                    
                    # Create Paper object with validated fields
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

                    # Only get full text for papers we're keeping
                    try:
                        if paper.doi:
                            paper.full_text = await scraper.scrape(f"https://doi.org/{paper.doi}")
                        elif paper.pdf_link:
                            paper.full_text = await scraper.scrape(paper.pdf_link)
                    except Exception as e:
                        logger.debug(f"Failed to get full text for {paper.title}: {str(e)}")
                        paper.full_text = None

                    # Validate minimum content requirements
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
    # Configure logging
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
        # Test queries optimized for CORE API
        test_queries = [
            'title:("precision agriculture" OR "precision farming") AND abstract:(machine learning irrigation)',
            'title:(IoT OR "Internet of Things") AND abstract:(agriculture sensors monitoring)',
            'title:("deep learning") AND abstract:(crop irrigation prediction)',
            'title:(sensors) AND abstract:("real-time monitoring" AND agriculture)',
            'title:("smart farming") AND abstract:(automation AND irrigation)'
        ]

        try:
            searcher = CORESearch()
            
            for i, query in enumerate(test_queries, 1):
                logger.info(f"\nTest {i}/{len(test_queries)}")
                logger.info(f"Query: {query}")
                
                try:
                    results = await searcher.search(query, limit=2)  # Test with small limit
                    logger.info(f"Retrieved {len(results)} results")
                    
                    for j, paper in enumerate(results, 1):
                        logger.info(f"\nResult {j}:")
                        logger.info(f"Title: {paper.title}")
                        logger.info(f"Authors: {', '.join(paper.authors)}")
                        logger.info(f"Year: {paper.year}")
                        logger.info(f"DOI: {paper.doi}")
                        logger.info(f"Abstract length: {len(paper.abstract)} chars")
                        logger.info(f"Full text length: {len(paper.full_text)} chars")
                        logger.info(f"PDF Link: {paper.pdf_link}")
                        logger.info("Metadata:")
                        for key, value in paper.metadata.items():
                            logger.info(f"  {key}: {value}")
                        
                except Exception as e:
                    logger.error(f"Error processing query {i}: {str(e)}")
                    continue
                    
                await asyncio.sleep(1)  # Rate limiting
                
        except Exception as e:
            logger.error(f"Test execution failed: {str(e)}")

    asyncio.run(run_test())