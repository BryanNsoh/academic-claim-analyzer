# src/academic_claim_analyzer/models.py

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

@dataclass
class SearchQuery:
    query: str
    source: str
    timestamp: datetime = field(default_factory=datetime.utcnow)

@dataclass
class Paper:
    title: str
    authors: List[str]
    year: int
    doi: str
    abstract: Optional[str] = None
    source: str = ""
    full_text: Optional[str] = None
    pdf_link: Optional[str] = None
    bibtex: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RankedPaper(Paper):
    relevance_score: float
    relevant_quotes: List[str]
    analysis: str

@dataclass
class ClaimAnalysis:
    claim: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    parameters: Dict[str, Any] = field(default_factory=dict)
    queries: List[SearchQuery] = field(default_factory=list)
    search_results: List[Paper] = field(default_factory=list)
    ranked_papers: List[RankedPaper] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_query(self, query: str, source: str):
        self.queries.append(SearchQuery(query, source))

    def add_search_result(self, paper: Paper):
        self.search_results.append(paper)

    def add_ranked_paper(self, paper: RankedPaper):
        self.ranked_papers.append(paper)

    def get_top_papers(self, n: int) -> List[RankedPaper]:
        return sorted(self.ranked_papers, key=lambda x: x.relevance_score, reverse=True)[:n]