# src/academic_claim_analyzer/search/base.py

from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass, field

@dataclass
class SearchResult:
    doi: str
    title: str
    authors: List[str]
    year: int
    abstract: Optional[str] = None
    pdf_link: Optional[str] = None
    source: str = ""
    full_text: Optional[str] = None  # Add full_text field
    metadata: dict = field(default_factory=dict)

class BaseSearch(ABC):
    @abstractmethod
    async def search(self, query: str, limit: int) -> List[SearchResult]:
        """
        Perform a search using the given query and return a list of search results.

        Args:
            query (str): The search query.
            limit (int): The maximum number of results to return.

        Returns:
            List[SearchResult]: A list of search results.
        """
        pass