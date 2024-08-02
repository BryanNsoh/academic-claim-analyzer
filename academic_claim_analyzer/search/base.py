# src/academic_claim_analyzer/search/base.py

from abc import ABC, abstractmethod
from typing import List
from ..models import Paper

class BaseSearch(ABC):
    @abstractmethod
    async def search(self, query: str, limit: int) -> List[Paper]:
        """
        Perform a search using the given query and return a list of search results.

        Args:
            query (str): The search query.
            limit (int): The maximum number of results to return.

        Returns:
            List[Paper]: A list of search results.
        """
        pass