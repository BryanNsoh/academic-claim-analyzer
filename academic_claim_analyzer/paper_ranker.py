# academic_claim_analyzer/paper_ranker.py

import os
import random
import math
import json
import logging
from typing import List, Dict, Any, Optional, Type
from pydantic import BaseModel, Field, create_model

# ------------------------------------------------------
# 1) CREATE OUR SINGLE SHARED HANDLER + DEFAULT MODEL
# ------------------------------------------------------
from llmhandler.api_handler import UnifiedLLMHandler

logger = logging.getLogger(__name__)

DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL", "google-gla:gemini-2.0-flash-001")

# Instantiate the global LLM handler with desired rate limit
# All code below references this single shared handler
llm_handler = UnifiedLLMHandler(requests_per_minute=2000)

def get_model_or_default(override_model: Optional[str] = None) -> str:
    """
    Decide which model to use:
      1) If override_model is provided, use that.
      2) Otherwise use the global DEFAULT_LLM_MODEL.
    """
    return override_model if override_model else DEFAULT_LLM_MODEL


# ------------------------------------------------------
# 2) Pydantic models for ranking & analysis
# ------------------------------------------------------
class Ranking(BaseModel):
    paper_id: str = Field(description="Unique identifier for the paper")
    rank: int = Field(description="Rank assigned (1 is most relevant)")
    explanation: str = Field(description="Explanation for the ranking")

class RankingResponse(BaseModel):
    rankings: List[Ranking] = Field(description="List of rankings for these papers")

class AnalysisResponse(BaseModel):
    analysis: str = Field(description="Detailed analysis of the paper's relevance")
    relevant_quotes: List[str] = Field(description="List of relevant quotes")


# ------------------------------------------------------
# 3) MAIN FUNCTION: rank_papers()
# ------------------------------------------------------
from .models import Paper, RankedPaper
from .search.bibtex import get_bibtex_from_doi, get_bibtex_from_title

async def rank_papers(
    papers: List[Paper],
    claim: str,
    exclusion_schema: Optional[Type[BaseModel]] = None,
    data_extraction_schema: Optional[Type[BaseModel]] = None,
    top_n: int = 5
) -> List[RankedPaper]:
    """
    Rank the given papers based on their relevance to the claim:
      1) Filter or determine scoring in multiple "rounds"
      2) Do a final pass to get top_n
      3) For each top paper, do a deeper analysis + potential schema extraction
    """
    logger.info(f"Starting to rank {len(papers)} papers using model {DEFAULT_LLM_MODEL}")

    # Filter out or keep only "valid" papers
    valid_papers = [p for p in papers if p.full_text and len(p.full_text.split()) >= 200]
    logger.info(f"{len(valid_papers)} papers have enough text for further analysis")

    num_rounds = calculate_ranking_rounds(len(valid_papers))
    logger.info(f"Will run {num_rounds} ranking rounds on these papers")

    # Prepare a data structure to hold scores
    paper_scores: Dict[str, List[float]] = {}
    for i, p in enumerate(valid_papers):
        p.id = f"paper_{i+1}"
        paper_scores[p.id] = []

    # 1) Conduct multiple ranking rounds
    average_scores = await _conduct_ranking_rounds(valid_papers, claim, num_rounds, paper_scores)

    # 2) Sort & pick top_n
    sorted_by_score = sorted(
        valid_papers,
        key=lambda pp: average_scores.get(pp.id, 0),
        reverse=True
    )
    top_papers = sorted_by_score[:top_n]

    # 3) Detailed analysis + gather BibTeX
    ranked_results = []
    for paper in top_papers:
        try:
            analysis_obj = await _get_paper_analysis(paper, claim)
            if not analysis_obj:
                continue

            # Possibly evaluate additional schema in a single pass
            # e.g. combining extraction + exclusion if needed
            evaluation_results = {}
            if exclusion_schema or data_extraction_schema:
                evaluation_results = await _evaluate_paper(paper, exclusion_schema, data_extraction_schema)

            # Acquire bibtex
            final_bibtex = await _get_bibtex(paper)

            # Build a final RankedPaper
            rp_dict = paper.model_dump()
            rp_dict.update({
                'relevance_score': average_scores.get(paper.id, 0.0),
                'analysis': analysis_obj.analysis,
                'relevant_quotes': analysis_obj.relevant_quotes,
                'bibtex': final_bibtex or rp_dict.get('bibtex', ''),
                'exclusion_criteria_result': evaluation_results.get('exclusion_criteria_result', {}),
                'extraction_result': evaluation_results.get('extracted_data', {})
            })
            ranked_results.append(RankedPaper(**rp_dict))
        except Exception as e:
            logger.error(f"Error processing paper {paper.title[:100]}: {str(e)}")

    logger.info(f"Returning {len(ranked_results)} ranked papers")
    return ranked_results


# ------------------------------------------------------
# 4) Helpers for multi-round ranking
# ------------------------------------------------------
def calculate_ranking_rounds(num_papers: int) -> int:
    if num_papers <= 8:
        return 3
    # simple logarithmic approach for demonstration
    import math
    return min(8, math.floor(math.log(num_papers, 1.4)) + 2)

async def _conduct_ranking_rounds(
    valid_papers: List[Paper],
    claim: str,
    num_rounds: int,
    paper_scores: Dict[str, List[float]]
) -> Dict[str, float]:
    """Run multiple 'ranking' rounds with the LLM."""
    for round_idx in range(num_rounds):
        logger.info(f"Ranking round {round_idx+1}/{num_rounds}")
        # shuffle the papers
        shuffled = random.sample(valid_papers, len(valid_papers))

        # break them into groups
        groups = create_balanced_groups(shuffled, 2, 5)
        prompts = [_create_ranking_prompt(g, claim) for g in groups]

        # Now call the LLM for each prompt (multi-prompt)
        call_result = await llm_handler.process(
            prompts=prompts,
            model=get_model_or_default(None),
            response_type=RankingResponse
        )
        if not call_result.success or not isinstance(call_result.data, list):
            logger.error(f"Round failed: {call_result.error}")
            continue

        # Each item corresponds to one group
        for idx, item in enumerate(call_result.data):
            if item.error:
                logger.error(f"Group {idx} error: {item.error}")
                continue
            ranking_resp = item.data  # RankingResponse object
            if not ranking_resp or not ranking_resp.rankings:
                logger.error("Empty or invalid ranking response")
                continue

            group_size = len(ranking_resp.rankings)
            for rank_obj in ranking_resp.rankings:
                pid = rank_obj.paper_id
                if pid in paper_scores:
                    # higher rank => lower # => higher score
                    # e.g. rank=1 => score=1.0
                    score = (group_size - rank_obj.rank + 1) / group_size
                    paper_scores[pid].append(score)

    # compute averages
    avg_scores = {}
    for pid, scores in paper_scores.items():
        if scores:
            avg_scores[pid] = sum(scores) / len(scores)
        else:
            avg_scores[pid] = 0.0

    return avg_scores

def create_balanced_groups(papers: List[Paper], min_size: int, max_size: int) -> List[List[Paper]]:
    """Simple grouping logic to keep group sizes in [min_size..max_size]."""
    num_papers = len(papers)
    if num_papers <= min_size:
        return [papers]

    try:
        if num_papers < max_size:
            group_sz = num_papers
        else:
            div = num_papers // max_size
            group_sz = min(max_size, max(min_size, num_papers // max(1, div)))

        groups = [papers[i:i+group_sz] for i in range(0, num_papers, group_sz)]
        if len(groups[-1]) < min_size and len(groups) > 1:
            leftover = groups.pop()
            idx = 0
            while leftover:
                groups[idx].append(leftover.pop())
                idx = (idx + 1) % len(groups)

        return groups
    except Exception as e:
        logger.error(f"Error grouping: {str(e)}")
        return [papers]

def _create_ranking_prompt(group: List[Paper], claim: str) -> str:
    """Build a multi-paper prompt for a single 'ranking' call."""
    lines = []
    for p in group:
        lines.append(
            f"Paper ID: {p.id}\nTitle: {p.title}\Content: {p.full_text}\n"
        )
    papers_block = "\n".join(lines)
    prompt = f"""
Analyze relevance to the claim: "{claim}"

Papers to rank:
{papers_block}

Return a valid JSON with the schema of RankingResponse:
{{
  "rankings": [
    {{
      "paper_id": "string (exact ID)",
      "rank": "integer (1..N)",
      "explanation": "string"
    }}
  ]
}}
where 1 = most relevant. Ensure unique ranks from 1..{len(group)}.
"""
    return prompt.strip()


# ------------------------------------------------------
# 5) Detailed Analysis & Additional Evaluations
# ------------------------------------------------------
async def _get_paper_analysis(paper: Paper, claim: str) -> Optional[AnalysisResponse]:
    """Get a deeper analysis of a single paper."""
    prompt = f"""
Analyze this paper's relevance to the claim: "{claim}"

Paper Title: {paper.title}
Full Text: {paper.full_text if paper.full_text else ''}

Explain methodology, evidence quality, limitations, and direct relevance.
Also provide 3 relevant quotes from the text.

Return valid JSON with fields:
{{
  "analysis": "string with summary",
  "relevant_quotes": [
    "quote #1",
    "quote #2",
    "quote #3"
  ]
}}
"""
    single_result = await llm_handler.process(
        prompts=prompt,
        model=get_model_or_default(None),
        response_type=AnalysisResponse
    )
    if not single_result.success:
        logger.error(f"Analysis error for {paper.title[:50]}: {single_result.error}")
        return None
    return single_result.data  # AnalysisResponse object


async def _evaluate_paper(
    paper: Paper,
    exclusion_schema: Optional[Type[BaseModel]],
    extraction_schema: Optional[Type[BaseModel]]
) -> Dict[str, Dict[str, Any]]:
    """Evaluate paper with combined schema, if needed."""
    if not (exclusion_schema or extraction_schema):
        return {}

    # We'll create a combined schema on the fly
    CombinedModel = _create_combined_model(exclusion_schema, extraction_schema)

    prompt = f"""
Given this paper:
Title: {paper.title}
Content: {paper.full_text if paper.full_text else ''}

Return valid JSON for the combined schema:
{json.dumps(CombinedModel.model_json_schema(), indent=2)}

No extraneous fields, no text outside the JSON.
"""

    result = await llm_handler.process(
        prompts=prompt,
        model=get_model_or_default(None),
        response_type=CombinedModel
    )
    if not result.success:
        logger.error(f"Evaluation error for {paper.title[:50]}: {result.error}")
        return {
            'exclusion_criteria_result': {},
            'extracted_data': {}
        }

    # The typed object
    obj = result.data
    exclusion_part = {}
    extraction_part = {}

    if exclusion_schema:
        for f in exclusion_schema.model_fields:
            val = getattr(obj, f, None)
            if isinstance(val, bool):
                exclusion_part[f] = val

    if extraction_schema:
        for f in extraction_schema.model_fields:
            extraction_part[f] = getattr(obj, f, None)

    return {
        'exclusion_criteria_result': exclusion_part,
        'extracted_data': extraction_part
    }

def _create_combined_model(
    exclusion_schema: Optional[Type[BaseModel]],
    extraction_schema: Optional[Type[BaseModel]]
) -> Type[BaseModel]:
    """Combine two pydantic models into a single ephemeral model."""
    if not exclusion_schema and not extraction_schema:
        return create_model("EmptyModel")

    ann = {}
    fields = {}
    from pydantic import Field

    if exclusion_schema:
        for name, f in exclusion_schema.model_fields.items():
            ann[name] = f.annotation
            fields[name] = Field(..., description=f.description or "Exclusion")

    if extraction_schema:
        for name, f in extraction_schema.model_fields.items():
            ann[name] = f.annotation
            fields[name] = Field(..., description=f.description or "Extraction")

    new_model = create_model(
        "CombinedModel",
        __annotations__=ann,
        **fields
    )
    return new_model


async def _get_bibtex(paper: Paper) -> str:
    """Get or generate BibTeX info."""
    if paper.doi:
        bib = get_bibtex_from_doi(paper.doi)
        if bib:
            return bib

    if paper.title and paper.authors and paper.year:
        bib = get_bibtex_from_title(paper.title, paper.authors, paper.year)
        if bib:
            return bib

    return ""
