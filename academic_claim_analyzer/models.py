# academic_claim_analyzer/models.py

from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any, Optional, Type, Union
from datetime import datetime

class FlexibleNumericField:
    """Mixin for handling numeric fields that may come back as text."""
    @classmethod
    def convert_to_int(cls, v: Any) -> int:
        if isinstance(v, int):
            return v
        return -1

class SearchQuery(BaseModel):
    query: str
    source: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class Paper(BaseModel, FlexibleNumericField):
    title: str
    authors: List[str]
    year: Union[int, str, None] = Field(default=None)
    doi: str
    abstract: Optional[str] = None
    source: str = ""
    full_text: Optional[str] = None
    pdf_link: Optional[str] = None
    bibtex: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    id: Optional[str] = None
    dataset_size: Optional[Union[int, str]] = Field(default=None)
    citation_count: Optional[Union[int, str]] = Field(default=None)

    @field_validator('year', mode='before')
    def validate_year(cls, v):
        if v is None:
            return -1
        val = cls.convert_to_int(v)
        if val < 1900 or val > 2100:
            return -1
        return val

    @field_validator('dataset_size', 'citation_count', mode='before')
    def validate_numeric_fields(cls, v):
        return cls.convert_to_int(v)

    class Config:
        arbitrary_types_allowed = True
        validate_assignment = True

class RankedPaper(Paper):
    relevance_score: Optional[float] = None
    analysis: Optional[str] = None
    relevant_quotes: List[str] = Field(default_factory=list)
    extraction_result: Optional[Dict[str, Any]] = None
    exclusion_criteria_result: Optional[Dict[str, bool]] = None

    @field_validator('relevance_score')
    def validate_score(cls, v):
        if v is None:
            return 0.0
        try:
            score = float(v)
            return max(0.0, min(1.0, score))  # clamp to [0..1]
        except (ValueError, TypeError):
            return 0.0

class RequestAnalysis(BaseModel):
    """Replaces the old 'ClaimAnalysis' with a more general request-based approach."""
    query: str
    ranking_guidance: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    queries: List[SearchQuery] = Field(default_factory=list)
    search_results: List[Paper] = Field(default_factory=list)
    ranked_papers: List[RankedPaper] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    exclusion_schema: Optional[Type[BaseModel]] = None
    data_extraction_schema: Optional[Type[BaseModel]] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        arbitrary_types_allowed = True

    def add_query(self, query: str, source: str):
        self.queries.append(SearchQuery(query=query, source=source))

    def add_search_result(self, paper: Paper):
        """Add search result with deduplication (by title)."""
        existing_titles = {p.title.lower().strip() for p in self.search_results}
        if paper.title.lower().strip() not in existing_titles:
            self.search_results.append(paper)

    def add_ranked_paper(self, paper: RankedPaper):
        """Add ranked paper with deduplication."""
        existing_titles = {p.title.lower().strip() for p in self.ranked_papers}
        if paper.title.lower().strip() not in existing_titles:
            self.ranked_papers.append(paper)

    def get_top_papers(self, n: int) -> List[RankedPaper]:
        """Get top n papers sorted by relevance score."""
        return sorted(
            self.ranked_papers,
            key=lambda x: x.relevance_score or 0.0,
            reverse=True
        )[:n]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with relevant fields."""
        return {
            'query': self.query,
            'ranking_guidance': self.ranking_guidance,
            'timestamp': self.timestamp.isoformat(),
            'parameters': self.parameters,
            'queries': [q.model_dump() for q in self.queries],
            'ranked_papers': [
                {
                    'title': p.title,
                    'authors': p.authors,
                    'year': p.year,
                    'relevance_score': p.relevance_score,
                    'analysis': p.analysis,
                    'relevant_quotes': p.relevant_quotes,
                    'extraction_result': {
                        field: {
                            'value': value,
                            'description': self.data_extraction_schema.model_fields[field].description
                        } for field, value in p.extraction_result.items()
                    } if self.data_extraction_schema and p.extraction_result else None,
                    'exclusion_criteria_result': {
                        field: {
                            'value': value,
                            'description': self.exclusion_schema.model_fields[field].description
                        } for field, value in p.exclusion_criteria_result.items()
                    } if self.exclusion_schema and p.exclusion_criteria_result else None,
                }
                for p in self.get_top_papers(5)
            ],
            'metadata': self.metadata
        }