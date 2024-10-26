# academic_claim_analyzer/models.py

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Type
from datetime import datetime

class SearchQuery(BaseModel):
    query: str
    source: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
        
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class Paper(BaseModel):
    title: str
    authors: List[str]
    year: Optional[int] = None
    doi: str
    abstract: Optional[str] = None
    source: str = ""
    full_text: Optional[str] = None
    pdf_link: Optional[str] = None
    bibtex: str = ""  # Change to non-optional with empty string default
    metadata: Dict[str, Any] = Field(default_factory=dict)
    id: Optional[str] = None

class RankedPaper(Paper):
    relevance_score: Optional[float] = None
    relevant_quotes: List[str] = Field(default_factory=list)
    analysis: str = ""
    exclusion_criteria_result: Optional[Dict[str, Any]] = Field(default_factory=dict)
    extraction_result: Optional[Dict[str, Any]] = Field(default_factory=dict)

class ClaimAnalysis(BaseModel):
    claim: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    queries: List[SearchQuery] = Field(default_factory=list)
    search_results: List[Paper] = Field(default_factory=list)
    ranked_papers: List[RankedPaper] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    exclusion_schema: Optional[Type[BaseModel]] = None          # New field for exclusion schema
    extraction_schema: Optional[Type[BaseModel]] = None         # New field for extraction schema

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    def add_query(self, query: str, source: str):
        self.queries.append(SearchQuery(query=query, source=source))

    def add_search_result(self, paper: Paper):
        self.search_results.append(paper)

    def add_ranked_paper(self, paper: RankedPaper):
        self.ranked_papers.append(paper)

    def get_top_papers(self, n: int) -> List[RankedPaper]:
        return sorted(self.ranked_papers, key=lambda x: x.relevance_score or 0, reverse=True)[:n]

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
