# academic_claim_analyzer/search/core_search.py

import aiohttp
import os
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv
from .base import BaseSearch
from ..models import Paper
import logging
import json

logger = logging.getLogger(__name__)

load_dotenv(override=True)

class CORESearch(BaseSearch):
    def __init__(self):
        self.api_key = os.getenv("CORE_API_KEY")
        if not self.api_key:
            raise ValueError("CORE_API_KEY not found in environment variables")
        self.base_url = "https://api.core.ac.uk/v3"

    async def search(self, query: str, limit: int) -> List[Paper]:
        """Execute search against CORE API with improved logging."""
        logger.info(f"CORE: Starting search with limit {limit}")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

        params = {
            "q": query,
            "limit": limit,
            "scroll": True
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(f"{self.base_url}/search/works", 
                                      headers=headers, json=params) as response:
                    response_text = await response.text()
                    
                    if response.status == 200:
                        data = json.loads(response_text)
                        total_results = data.get("totalHits", 0)
                        logger.info(f"CORE: Found {total_results} total matches")
                        
                        if not total_results:
                            logger.info("CORE: No results found for query")
                            return []
                            
                        results = self._parse_results(data)
                        logger.info(f"CORE: Successfully retrieved {len(results)} valid papers")
                        return results
                        
                    else:
                        logger.error(f"CORE: API error {response.status}")
                        logger.error(f"CORE: Response: {response_text[:500]}")
                        return []
                        
            except json.JSONDecodeError as e:
                logger.error(f"CORE: Invalid JSON response - {str(e)}")
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

    def _parse_results(self, data: Dict[str, Any]) -> List[Paper]:
        """Parse CORE API response with improved validation and metrics."""
        results = []
        valid_count = 0
        invalid_count = 0
        
        entries = data.get('results', [])
        logger.info(f"CORE: Processing {len(entries)} results")
        
        for entry in entries:
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
                full_text = self._extract_string_value(entry.get('fullText', ''))
                
                # Validate minimum content requirements
                if not (abstract or full_text):
                    logger.debug(f"CORE: Skipping paper without content: {title}")
                    invalid_count += 1
                    continue

                # Create Paper object with validated fields
                paper = Paper(
                    doi=self._extract_string_value(entry.get('doi', '')),
                    title=title,
                    authors=authors,
                    year=year,
                    abstract=abstract,
                    full_text=full_text,
                    source=self._extract_string_value(entry.get('publisher', '')),
                    pdf_link=self._extract_string_value(entry.get('downloadUrl', '')),
                    metadata={
                        'core_id': str(entry.get('id', '')),
                        'language': self._extract_string_value(
                            entry.get('language', {}).get('code', 'en')
                        ),
                        'repositories': len(entry.get('repositories', []))
                    }
                )
                
                results.append(paper)
                valid_count += 1

            except Exception as e:
                logger.error(f"CORE: Error processing entry - {str(e)}")
                invalid_count += 1
                continue

        logger.info(f"CORE: Processing complete - {valid_count} valid, {invalid_count} invalid")
        return results