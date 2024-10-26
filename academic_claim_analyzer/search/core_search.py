# academic_claim_analyzer/search/core_search.py

import aiohttp
import os
from typing import List, Optional, Union, Dict, Any
from dotenv import load_dotenv
from .base import BaseSearch
from ..models import Paper
import logging

logger = logging.getLogger(__name__)

load_dotenv(override=True)

class CORESearch(BaseSearch):
    def __init__(self):
        self.api_key = os.getenv("CORE_API_KEY")
        if not self.api_key:
            raise ValueError("CORE_API_KEY not found in environment variables")
        self.base_url = "https://api.core.ac.uk/v3"

    async def search(self, query: str, limit: int) -> List[Paper]:
        """Execute search against CORE API."""
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
                async with session.post(f"{self.base_url}/search/works", headers=headers, json=params) as response:
                    if response.status == 200:
                        logger.info("CORE API request successful.")
                        data = await response.json()
                        return self._parse_results(data)
                    else:
                        error_text = await response.text()
                        logger.error(f"CORE API request failed with status code: {response.status}")
                        logger.error(f"Error response: {error_text}")
                        return []
            except Exception as e:
                logger.error(f"Error occurred while making CORE API request: {str(e)}")
                return []

    def _extract_string_value(self, data: Any) -> str:
        """Safely extract string value from various data types."""
        if isinstance(data, str):
            return data
        elif isinstance(data, (list, tuple)) and data:
            return str(data[0])
        elif isinstance(data, dict) and 'name' in data:
            return str(data['name'])
        elif data is None:
            return ""
        return str(data)

    def _safe_extract_authors(self, entry: Dict[str, Any]) -> List[str]:
        """Safely extract author names from various response formats."""
        authors = []
        author_data = entry.get('authors', [])
        
        if isinstance(author_data, list):
            for author in author_data:
                if isinstance(author, dict):
                    name = author.get('name')
                    if name:
                        authors.append(str(name))
                elif isinstance(author, str):
                    authors.append(author)
                    
        elif isinstance(author_data, dict):
            name = author_data.get('name')
            if name:
                authors.append(str(name))
                
        return authors or ["Unknown Author"]

    def _safe_extract_year(self, entry: Dict[str, Any]) -> int:
        """Safely extract publication year from various date formats."""
        try:
            # Try different date fields
            for field in ['yearPublished', 'publishedDate', 'createdDate']:
                value = entry.get(field)
                if value:
                    if isinstance(value, int):
                        return value
                    elif isinstance(value, str):
                        # Handle ISO format dates
                        return int(value.split('-')[0])
            return 0
        except (ValueError, IndexError, TypeError):
            return 0

    def _safe_extract_doi(self, entry: Dict[str, Any]) -> str:
        """Safely extract DOI from various formats."""
        try:
            # Check direct doi field
            doi = entry.get('doi')
            if doi:
                return self._extract_string_value(doi)
            
            # Check identifiers list
            identifiers = entry.get('identifiers', [])
            if isinstance(identifiers, list):
                for identifier in identifiers:
                    if isinstance(identifier, dict) and identifier.get('type') == 'DOI':
                        return str(identifier.get('identifier', ''))
                        
            return ""
        except Exception as e:
            logger.debug(f"Error extracting DOI: {str(e)}")
            return ""

    def _safe_extract_fulltext(self, entry: Dict[str, Any]) -> str:
        """Safely extract full text content."""
        try:
            # Try direct fullText field
            fulltext = entry.get('fullText', '')
            if fulltext:
                return str(fulltext)
            
            # Try abstract as fallback
            abstract = entry.get('abstract', '')
            if abstract:
                return str(abstract)
                
            return ""
        except Exception as e:
            logger.debug(f"Error extracting full text: {str(e)}")
            return ""

    def _safe_extract_source(self, entry: Dict[str, Any]) -> str:
        """Safely extract source/publisher information."""
        try:
            # Try various source fields
            for field in ['publisher', 'journal', 'source']:
                value = entry.get(field)
                if value:
                    return self._extract_string_value(value)
            return ""
        except Exception as e:
            logger.debug(f"Error extracting source: {str(e)}")
            return ""

    def _parse_results(self, data: Dict[str, Any]) -> List[Paper]:
        """Parse CORE API response with improved error handling."""
        results = []
        
        # Handle different response structures
        entries = []
        if isinstance(data, dict):
            entries = data.get('results', [])
        elif isinstance(data, list):
            entries = data
            
        for entry in entries:
            try:
                if not isinstance(entry, dict):
                    continue

                # Extract all required fields with safe methods
                doi = self._safe_extract_doi(entry)
                title = self._extract_string_value(entry.get('title', 'Untitled'))
                authors = self._safe_extract_authors(entry)
                year = self._safe_extract_year(entry)
                fulltext = self._safe_extract_fulltext(entry)
                source = self._safe_extract_source(entry)

                # Construct metadata
                metadata = {
                    'core_id': str(entry.get('id', '')),
                    'oai_id': self._extract_string_value(entry.get('oaiIds', [''])),
                    'language': self._extract_string_value(entry.get('language', {}).get('code', 'en'))
                }

                # Create Paper object with validated fields
                paper = Paper(
                    doi=doi,
                    title=title,
                    authors=authors,
                    year=year,
                    abstract=str(entry.get('abstract', '')),
                    pdf_link=str(entry.get('downloadUrl', '')),
                    source=source,
                    full_text=fulltext,
                    metadata=metadata
                )
                results.append(paper)

            except Exception as e:
                logger.error(f"Error parsing entry: {str(e)}")
                continue

        logger.info(f"Successfully parsed {len(results)} results from CORE API")
        return results