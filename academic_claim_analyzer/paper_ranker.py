# academic_claim_analyzer/paper_ranker.py

import asyncio
import json
import random
from typing import List, Dict, Tuple
from .models import Paper, RankedPaper
from async_llm_handler import LLMHandler
import logging

logger = logging.getLogger(__name__)

# Global variables for prompts
RANKING_PROMPT = """
Analyze the relevance of the following papers to the claim: "{claim}"

Papers:
{paper_summaries}

Rank these papers from most to least relevant. Provide a brief explanation for each ranking.

Your response should be in the following JSON format:
{{
  "rankings": [
    {{
      "paper_id": "string",
      "rank": integer,
      "explanation": "string"
    }},
    ...
  ]
}}

Ensure that each paper is assigned a unique rank from 1 to {num_papers}, where 1 is the most relevant.
"""

ANALYSIS_PROMPT = """
For the following paper, provide a detailed analysis of its relevance to the claim: "{claim}"

Paper Title: {title}
Abstract: {abstract}
Full Text: {full_text}

Your response should be in the following JSON format:
{{
  "analysis": "string",
  "relevant_quotes": [
    "string",
    "string",
    "string"
  ]
}}

Provide a thorough analysis and extract up to three relevant quotes that support the paper's relevance to the claim.
"""

def create_balanced_groups(papers: List[Paper], min_group_size: int = 2, max_group_size: int = 5) -> List[List[Paper]]:
    """Create balanced groups of papers, ensuring each group has at least min_group_size papers."""
    num_papers = len(papers)
    if num_papers < min_group_size:
        return [papers]  # Return all papers as a single group if there are too few

    # Calculate the optimal group size
    group_size = min(max_group_size, max(min_group_size, num_papers // (num_papers // max_group_size)))
    
    # Create initial groups
    groups = [papers[i:i+group_size] for i in range(0, num_papers, group_size)]
    
    # Redistribute papers from the last group if it's too small
    if len(groups[-1]) < min_group_size:
        last_group = groups.pop()
        for i, paper in enumerate(last_group):
            groups[i % len(groups)].append(paper)
    
    return groups

async def rank_group(handler: LLMHandler, claim: str, papers: List[Paper]) -> List[Dict[str, any]]:
    """Rank a group of papers using the LLM."""
    paper_summaries = "\n".join([f"Paper ID: {paper.id}\nTitle: {paper.title}\nAbstract: {paper.abstract[:200]}..." for paper in papers])
    prompt = RANKING_PROMPT.format(claim=claim, paper_summaries=paper_summaries, num_papers=len(papers))
    
    response = await handler.query(prompt, model="gpt_4o_mini", sync=False, max_input_tokens=4000)
    
    try:
        rankings = json.loads(response)['rankings']
        if len(rankings) != len(papers):
            logger.warning(f"Incomplete rankings received. Expected {len(papers)}, got {len(rankings)}")
        return rankings
    except json.JSONDecodeError:
        logger.error(f"Failed to parse LLM response: {response}")
        return []

async def analyze_paper(handler: LLMHandler, claim: str, paper: Paper) -> Dict[str, any]:
    """Analyze a single paper for relevance and extract quotes."""
    prompt = ANALYSIS_PROMPT.format(claim=claim, title=paper.title, abstract=paper.abstract, full_text=paper.full_text)
    
    response = await handler.query(prompt, model="gpt_4o_mini", sync=False, max_input_tokens=4000)
    
    try:
        analysis = json.loads(response)
        return analysis
    except json.JSONDecodeError:
        logger.error(f"Failed to parse LLM response for paper analysis: {response}")
        return {"analysis": "", "relevant_quotes": []}

async def rank_papers(papers: List[Paper], claim: str, num_rounds: int = 3, top_n: int = 5) -> List[RankedPaper]:
    """Rank papers based on their relevance to the given claim."""
    handler = LLMHandler()
    
    # Assign unique IDs to papers if not already present
    for i, paper in enumerate(papers):
        if not hasattr(paper, 'id'):
            setattr(paper, 'id', f"paper_{i}")
    
    paper_scores: Dict[str, List[float]] = {paper.id: [] for paper in papers}
    
    for round in range(num_rounds):
        logger.info(f"Starting ranking round {round + 1} of {num_rounds}")
        shuffled_papers = random.sample(papers, len(papers))
        
        # Create balanced groups
        paper_groups = create_balanced_groups(shuffled_papers)
        
        # Rank each group
        ranking_tasks = [rank_group(handler, claim, group) for group in paper_groups]
        group_rankings = await asyncio.gather(*ranking_tasks)
        
        # Accumulate scores
        for rankings in group_rankings:
            group_size = len(rankings)
            for ranking in rankings:
                paper_id = ranking['paper_id']
                rank = ranking['rank']
                # Normalize score based on group size
                score = (group_size - rank + 1) / group_size
                paper_scores[paper_id].append(score)
    
    # Calculate average scores, handling potential division by zero
    average_scores = {}
    for paper_id, scores in paper_scores.items():
        if scores:
            average_scores[paper_id] = sum(scores) / len(scores)
        else:
            logger.warning(f"No scores recorded for paper {paper_id}. Assigning lowest score.")
            average_scores[paper_id] = 0
    
    # Sort papers by average score
    sorted_papers = sorted(papers, key=lambda p: average_scores[p.id], reverse=True)
    
    # Analyze top N papers
    top_papers = sorted_papers[:top_n]
    analysis_tasks = [analyze_paper(handler, claim, paper) for paper in top_papers]
    paper_analyses = await asyncio.gather(*analysis_tasks)
    
    # Create RankedPaper objects
    ranked_papers = []
    for paper, analysis in zip(top_papers, paper_analyses):
        ranked_paper = RankedPaper(
            **{**paper.__dict__},
            relevance_score=average_scores[paper.id],
            analysis=analysis['analysis'],
            relevant_quotes=analysis['relevant_quotes']
        )
        ranked_papers.append(ranked_paper)
    
    logger.info(f"Completed paper ranking. Top score: {ranked_papers[0].relevance_score:.2f}, Bottom score: {ranked_papers[-1].relevance_score:.2f}")
    return ranked_papers