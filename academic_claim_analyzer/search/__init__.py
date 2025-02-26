# academic_claim_analyzer/search/__init__.py

from .openalex_search import OpenAlexSearch 
from .scopus_search import ScopusSearch
from .core_search import CORESearch
from .base import BaseSearch
from .arxiv_search import ArxivSearch
from .semantic_scholar_search import SemanticScholarSearch

__all__ = [
    "OpenAlexSearch",
    "ScopusSearch",
    "CORESearch",
    "ArxivSearch",
    "SemanticScholarSearch",
    "BaseSearch"
]