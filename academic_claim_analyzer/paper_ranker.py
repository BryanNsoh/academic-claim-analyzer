# academic_claim_analyzer/paper_ranker.py

import random
import math
import logging
import asyncio
from typing import List, Dict, Any, Optional, Type
from pydantic import BaseModel, Field

from .llm_handler_config import llm_handler
from .models import Paper, RankedPaper

logger = logging.getLogger(__name__)

# Ranking + Analysis Pydantic models
class Ranking(BaseModel):
    paper_id: str = Field(description="Unique ID for the paper")
    rank: int = Field(description="Rank (1 is most relevant)")
    explanation: str = Field(description="Explanation for the ranking")

class RankingResponse(BaseModel):
    rankings: List[Ranking] = Field(description="List of rank objects")

class AnalysisResponse(BaseModel):
    analysis: str = Field(description="Detailed analysis of the paper's relevance")
    relevant_quotes: List[str] = Field(description="List of relevant quotes")

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
    1) Do multi-round partial ranking (all rounds are run concurrently)
    2) Sort by aggregated score
    3) Do a deeper analysis pass for the top papers (also executed concurrently)
    
    Args:
        papers: List of papers to rank
        query: User query
        ranking_guidance: Guidance for ranking papers
        exclusion_schema: Schema for excluding papers
        data_extraction_schema: Schema for extracting data from papers
        top_n: Number of top papers to return
        
    Returns:
        List of RankedPaper objects
    """
    logger.info(f"Starting to rank {len(papers)} papers")
    logger.info(f"User ranking guidance: {ranking_guidance!r}")

    valid_papers = [p for p in papers if p.full_text and len(p.full_text.split()) >= 200]
    logger.info(f"{len(valid_papers)} papers have enough text for advanced ranking")

    num_rounds = calculate_ranking_rounds(len(valid_papers))
    logger.info(f"Will run {num_rounds} ranking rounds")

    paper_scores: Dict[str, List[float]] = {}
    for i, p in enumerate(valid_papers):
        p.id = f"paper_{i+1}"
        paper_scores[p.id] = []

    # Launch all ranking rounds concurrently
    average_scores = await _conduct_ranking_rounds(valid_papers, query, ranking_guidance, num_rounds, paper_scores)

    # Sort & pick top_n papers
    sorted_by_score = sorted(
        valid_papers,
        key=lambda pp: average_scores.get(pp.id, 0.0),
        reverse=True
    )
    top_papers = sorted_by_score[:top_n]

    # Detailed analysis for each top paper executed concurrently
    analysis_tasks = [_process_top_paper(paper, query, ranking_guidance, average_scores) for paper in top_papers]
    analysis_results = await asyncio.gather(*analysis_tasks, return_exceptions=True)
    ranked_results = []
    for result in analysis_results:
        if isinstance(result, Exception):
            logger.error(f"Error in processing a top paper: {result}")
        elif result is not None:
            ranked_results.append(result)

    logger.info(f"Returning {len(ranked_results)} ranked papers")
    return ranked_results

def calculate_ranking_rounds(num_papers: int) -> int:
    """Calculate the number of ranking rounds based on the number of papers."""
    if num_papers <= 8:
        return 3
    return min(8, math.floor(math.log(num_papers, 1.4)) + 2)

async def _conduct_ranking_rounds(
    valid_papers: List[Paper],
    query: str,
    ranking_guidance: str,
    num_rounds: int,
    paper_scores: Dict[str, List[float]]
) -> Dict[str, float]:
    """
    Conduct multiple rounds of ranking to determine paper relevance.
    
    Args:
        valid_papers: List of papers to rank
        query: User query
        ranking_guidance: Guidance for ranking
        num_rounds: Number of ranking rounds to conduct
        paper_scores: Dictionary to store scores
        
    Returns:
        Dictionary mapping paper IDs to average scores
    """
    async def run_round(round_idx: int) -> Dict[str, List[float]]:
        round_scores = {}
        logger.info(f"Ranking round {round_idx+1}/{num_rounds}")
        shuffled = random.sample(valid_papers, len(valid_papers))
        groups = create_balanced_groups(shuffled, 2, 5)
        prompts = [_create_ranking_prompt(g, query, ranking_guidance) for g in groups]

        call_result = await llm_handler.process(
            prompts=prompts,
            response_type=RankingResponse
        )
        if not call_result.success or not isinstance(call_result.data, list):
            logger.error(f"Round {round_idx+1} failed: {call_result.error}")
            return round_scores

        for idx, item in enumerate(call_result.data):
            if item.error:
                logger.error(f"Round {round_idx+1} Group {idx} error: {item.error}")
                continue
            ranking_resp = item.data
            if not ranking_resp or not ranking_resp.rankings:
                logger.error(f"Round {round_idx+1} empty or invalid ranking response for group {idx}")
                continue

            group_size = len(ranking_resp.rankings)
            for rank_obj in ranking_resp.rankings:
                pid = rank_obj.paper_id
                score = (group_size - rank_obj.rank + 1) / group_size
                round_scores.setdefault(pid, []).append(score)
        return round_scores

    tasks = [run_round(i) for i in range(num_rounds)]
    rounds_scores = await asyncio.gather(*tasks)
    for round_dict in rounds_scores:
        for pid, scores in round_dict.items():
            paper_scores.setdefault(pid, []).extend(scores)
    avg_scores = {pid: (sum(scores) / len(scores)) if scores else 0.0 for pid, scores in paper_scores.items()}
    return avg_scores

def create_balanced_groups(papers: List[Paper], min_size: int, max_size: int) -> List[List[Paper]]:
    """
    Create balanced groups of papers for ranking.
    
    Args:
        papers: List of papers to group
        min_size: Minimum group size
        max_size: Maximum group size
        
    Returns:
        List of paper groups
    """
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
    """
    Create a prompt for ranking a group of papers.
    
    Args:
        group: Group of papers to rank
        query: User query
        ranking_guidance: Guidance for ranking
        
    Returns:
        Prompt for ranking
    """
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

Ensure unique ranks from 1 to {len(group)} are used. Focus on clear, concise explanations that justify each paper's rank in relation to the query and ranking guidance.
"""
    return prompt.strip()

async def _get_paper_analysis(paper: Paper, query: str, ranking_guidance: str) -> Optional[AnalysisResponse]:
    """
    Get a detailed analysis of a paper's relevance to a query.
    
    Args:
        paper: Paper to analyze
        query: User query
        ranking_guidance: Guidance for analysis
        
    Returns:
        AnalysisResponse object or None if analysis fails
    """
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
"""
    single_result = await llm_handler.process(
        prompts=prompt,
        response_type=AnalysisResponse
    )
    if not single_result.success:
        logger.error(f"Analysis error for {paper.title[:50]}: {single_result.error}")
        return None
    return single_result.data

async def _process_top_paper(paper: Paper, query: str, ranking_guidance: str, average_scores: Dict[str, float]) -> Optional[RankedPaper]:
    """
    Process a top paper by analyzing it and creating a RankedPaper object.
    
    Args:
        paper: Paper to process
        query: User query
        ranking_guidance: Guidance for ranking
        average_scores: Dictionary mapping paper IDs to scores
        
    Returns:
        RankedPaper object or None if processing fails
    """
    try:
        analysis_obj = await _get_paper_analysis(paper, query, ranking_guidance)
        if not analysis_obj:
            return None
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
        return RankedPaper(**rp_dict)
    except Exception as e:
        logger.error(f"Error processing top paper {paper.title[:100]}: {str(e)}")
        return None

async def _get_bibtex(paper: Paper) -> str:
    """
    Get BibTeX citation for a paper.
    
    Args:
        paper: Paper to get citation for
        
    Returns:
        BibTeX citation string
    """
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