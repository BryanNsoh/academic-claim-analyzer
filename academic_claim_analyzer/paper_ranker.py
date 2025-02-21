# academic_claim_analyzer/paper_ranker.py

import os
import random
import math
import json
import logging
from typing import List, Dict, Any, Optional, Type
from pydantic import BaseModel, Field, create_model

from llmhandler.api_handler import UnifiedLLMHandler
logger = logging.getLogger(__name__)

DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL", "google-gla:gemini-2.0-flash-001")
llm_handler = UnifiedLLMHandler(requests_per_minute=2000)

def get_model_or_default(override_model: Optional[str] = None) -> str:
    return override_model if override_model else DEFAULT_LLM_MODEL

# Ranking + Analysis Pydantic
class Ranking(BaseModel):
    paper_id: str = Field(description="Unique ID for the paper")
    rank: int = Field(description="Rank (1 is most relevant)")
    explanation: str = Field(description="Explanation for the ranking")

class RankingResponse(BaseModel):
    rankings: List[Ranking] = Field(description="List of rank objects")

class AnalysisResponse(BaseModel):
    analysis: str = Field(description="Detailed analysis of the paper's relevance")
    relevant_quotes: List[str] = Field(description="List of relevant quotes")

# Models
from .models import Paper, RankedPaper

# Main entry point
async def rank_papers(
    papers: List[Paper],
    query: str,
    ranking_guidance: str,
    exclusion_schema: Optional[Type[BaseModel]] = None,
    data_extraction_schema: Optional[Type[BaseModel]] = None,
    top_n: int = 5
) -> List[RankedPaper]:
    """
    Rank the given papers based on:
    - Relevance to 'query'
    - User-supplied 'ranking_guidance'
    1) Do multi-round partial ranking
    2) Sort by aggregated score
    3) Do a deeper analysis pass for the top papers
    """
    logger.info(f"Starting to rank {len(papers)} papers using model {DEFAULT_LLM_MODEL}.")
    logger.info(f"User ranking guidance: {ranking_guidance!r}")

    valid_papers = [p for p in papers if p.full_text and len(p.full_text.split()) >= 200]
    logger.info(f"{len(valid_papers)} papers have enough text for advanced ranking")

    num_rounds = calculate_ranking_rounds(len(valid_papers))
    logger.info(f"Will run {num_rounds} ranking rounds")

    paper_scores: Dict[str, List[float]] = {}
    for i, p in enumerate(valid_papers):
        p.id = f"paper_{i+1}"
        paper_scores[p.id] = []

    # Conduct multiple ranking rounds
    average_scores = await _conduct_ranking_rounds(valid_papers, query, ranking_guidance, num_rounds, paper_scores)

    # Sort & pick top_n
    sorted_by_score = sorted(
        valid_papers,
        key=lambda pp: average_scores.get(pp.id, 0.0),
        reverse=True
    )
    top_papers = sorted_by_score[:top_n]

    # Detailed analysis
    ranked_results = []
    for paper in top_papers:
        try:
            analysis_obj = await _get_paper_analysis(paper, query, ranking_guidance)
            if not analysis_obj:
                continue

            final_bibtex = await _get_bibtex(paper)
            rp_dict = paper.model_dump()
            rp_dict.update({
                'relevance_score': average_scores.get(paper.id, 0.0),
                'analysis': analysis_obj.analysis,
                'relevant_quotes': analysis_obj.relevant_quotes,
                'bibtex': final_bibtex or rp_dict.get('bibtex', ''),
                'exclusion_criteria_result': {},
                'extraction_result': {}
            })

            ranked_results.append(RankedPaper(**rp_dict))
        except Exception as e:
            logger.error(f"Error processing top paper {paper.title[:100]}: {str(e)}")

    logger.info(f"Returning {len(ranked_results)} ranked papers")
    return ranked_results

def calculate_ranking_rounds(num_papers: int) -> int:
    if num_papers <= 8:
        return 3
    import math
    return min(8, math.floor(math.log(num_papers, 1.4)) + 2)

async def _conduct_ranking_rounds(
    valid_papers: List[Paper],
    query: str,
    ranking_guidance: str,
    num_rounds: int,
    paper_scores: Dict[str, List[float]]
) -> Dict[str, float]:
    for round_idx in range(num_rounds):
        logger.info(f"Ranking round {round_idx+1}/{num_rounds}")
        shuffled = random.sample(valid_papers, len(valid_papers))
        groups = create_balanced_groups(shuffled, 2, 5)
        prompts = [_create_ranking_prompt(g, query, ranking_guidance) for g in groups]

        call_result = await llm_handler.process(
            prompts=prompts,
            model=get_model_or_default(None),
            response_type=RankingResponse
        )
        if not call_result.success or not isinstance(call_result.data, list):
            logger.error(f"Round failed: {call_result.error}")
            continue

        for idx, item in enumerate(call_result.data):
            if item.error:
                logger.error(f"Group {idx} error: {item.error}")
                continue
            ranking_resp = item.data
            if not ranking_resp or not ranking_resp.rankings:
                logger.error("Empty or invalid ranking response")
                continue

            group_size = len(ranking_resp.rankings)
            for rank_obj in ranking_resp.rankings:
                pid = rank_obj.paper_id
                if pid in paper_scores:
                    score = (group_size - rank_obj.rank + 1) / group_size
                    paper_scores[pid].append(score)

    # compute averages
    avg_scores = {}
    for pid, scores in paper_scores.items():
        avg_scores[pid] = sum(scores)/len(scores) if scores else 0.0
    return avg_scores

def create_balanced_groups(papers: List[Paper], min_size: int, max_size: int) -> List[List[Paper]]:
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
        logger.error(f"Error grouping papers: {str(e)}")
        return [papers]

def _create_ranking_prompt(group: List[Paper], query: str, ranking_guidance: str) -> str:
    lines = []
    for p in group:
        lines.append(f"Paper ID: {p.id}\nTitle: {p.title}\nContent: {p.full_text}\n")
    papers_block = "\n".join(lines)

    prompt = f"""
You are an expert academic paper ranker. Your task is to rank the relevance of each paper to a given research query, considering specific ranking guidance provided by the user.

Research Query: "{query}"

User's Ranking Guidance: "{ranking_guidance}"

Papers to rank (provided with Paper ID, Title, and Content excerpt):
{papers_block}

Instructions:
1. Understand the Research Query and User's Ranking Guidance thoroughly.
2. Evaluate each paper in the 'Papers to rank' section for its relevance to the Research Query.
3. Consider the User's Ranking Guidance to prioritize certain aspects of relevance (e.g., methodology, recency, specific findings).
4. Rank the papers from most relevant to least relevant. Assign unique ranks from 1 to N, where N is the number of papers. Rank 1 is the most relevant.
5. Provide a brief explanation for each ranking, justifying why a paper received a particular rank based on its content and the ranking guidance.

Output Format:
Return a valid JSON object of type RankingResponse. Ensure that the JSON contains a list of rankings, with each ranking including the paper_id, rank, and explanation.

Example JSON Output:
{{
  "rankings": [
    {{
      "paper_id": "paper_1",
      "rank": 1,
      "explanation": "Most relevant due to direct focus on query and strong empirical evidence, as per ranking guidance."
    }},
    {{
      "paper_id": "paper_2",
      "rank": 2,
      "explanation": "Relevant but less direct evidence compared to paper_1. Aligns with ranking guidance on methodology."
    }},
    ...
  ]
}}

Ensure unique ranks from 1 to {len(group)} are used. Focus on clear, concise explanations that justify each paper's rank in relation to the query and ranking guidance.
"""
    return prompt.strip()

async def _get_paper_analysis(paper: Paper, query: str, ranking_guidance: str) -> Optional[AnalysisResponse]:
    prompt = f"""
You are an expert in academic literature analysis. Your task is to evaluate the relevance of a given paper to a specific research query and provide a detailed analysis.

Research Query: "{query}"

User's Ranking Guidance: "{ranking_guidance}"

Paper Title: {paper.title}
Paper Full Text: {paper.full_text or ''}

Instructions:
1. Understand the Research Query and User's Ranking Guidance.
2. Read the provided Paper Full Text to determine its relevance to the Research Query.
3. Analyze the paper, focusing on:
    - Methodology: Describe the research methods used in the paper.
    - Evidence Quality: Assess the strength and quality of evidence presented.
    - Limitations: Identify any limitations or weaknesses of the study.
    - Direct Relevance: Explain how directly the paper addresses the Research Query.
4. Based on your analysis, select 3-5 of the most relevant and impactful quotes from the paper that directly relate to the Research Query.

Output Format:
Return a valid JSON object of type AnalysisResponse. Ensure that the JSON contains:
- A detailed "analysis" string summarizing your evaluation of the paper's methodology, evidence, limitations, and direct relevance to the query, considering the Ranking Guidance.
- A list of "relevant_quotes" containing 3-5 key excerpts from the paper that best demonstrate its relevance.

Example JSON Output:
{{
  "analysis": "This paper provides strong empirical evidence using a robust methodology... However, it has limitations in...",
  "relevant_quotes": [
    "Quote 1 directly supporting the query...",
    "Quote 2 explaining the methodology...",
    "Quote 3 highlighting a key finding..."
  ]
}}

Provide a comprehensive analysis and select quotes that best represent the paper's contribution and relevance to the research query, as guided by the user's preferences.
"""
    single_result = await llm_handler.process(
        prompts=prompt,
        model=get_model_or_default(None),
        response_type=AnalysisResponse
    )
    if not single_result.success:
        logger.error(f"Analysis error for {paper.title[:50]}: {single_result.error}")
        return None
    return single_result.data

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
You are an expert in academic paper evaluation. Your task is to assess a given paper against a defined schema that includes exclusion criteria and data extraction requirements.

Paper Title: {paper.title}
Paper Content: {paper.full_text if paper.full_text else ''}

Schema for Evaluation:
{json.dumps(CombinedModel.model_json_schema(), indent=2)}

Instructions:
1. Review the 'Schema for Evaluation' to understand the exclusion criteria and data extraction fields.
2. Read the 'Paper Content' to evaluate it against each criterion in the schema.
3. For each field in the schema:
    - If it is an exclusion criterion, determine if the paper meets the criterion (True/False).
    - If it is a data extraction field, extract the requested information from the paper content. If the information is not available, use default values as defined in schema description.
4. Ensure your output is a valid JSON object that strictly adheres to the schema. Do not include any extraneous fields or text outside the JSON.

Output Format:
Return valid JSON object that conforms to the combined schema provided. For exclusion criteria, use boolean values. For extraction fields, provide the extracted data, using default values if necessary as described in schema.

Example JSON Output (based on schema):
{{
  "exclusion_criterion_1": false,
  "exclusion_criterion_2": true,
  "data_field_1": "Extracted value or default",
  "data_field_2": 123 or -1
  ...
}}
Ensure the JSON output strictly matches the schema with no additional fields or descriptive text. Focus on accuracy and adherence to the schema.
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
    from .search.bibtex import get_bibtex_from_doi, get_bibtex_from_title
    if paper.doi:
        bib = get_bibtex_from_doi(paper.doi)
        if bib:
            return bib

    if paper.title and paper.authors and paper.year:
        bib = get_bibtex_from_title(paper.title, paper.authors, paper.year)
        if bib:
            return bib

    return ""