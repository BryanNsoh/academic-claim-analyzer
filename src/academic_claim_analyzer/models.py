# src/academic_claim_analyzer/models.py

from dataclasses import dataclass
from typing import List

@dataclass
class Paper:
    title: str
    authors: List[str]
    year: int
    doi: str
    bibtex: str
    full_text: str = ""

@dataclass
class RankedPaper(Paper):
    relevant_quotes: List[str]
    analysis: str
    rank: int
    
    