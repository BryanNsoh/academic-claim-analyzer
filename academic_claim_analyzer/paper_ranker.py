# src/academic_claim_analyzer/paper_ranker.py

"""
This module contains the functions for ranking papers based on their relevance to a given claim.

The ranking algorithm is as follows:
To simplify the plan while maintaining output quality, we need to identify which components contribute the most to the robustness and accuracy of the results. We can streamline the process by focusing on the most impactful elements and eliminating steps that add complexity without significantly improving the outcome.

### Simplified Plan: Shuffled Group Ranking with Averaged Scoring

### Key Components to Retain:
1. **Clipping Papers**: Essential for ensuring manageable text lengths.
2. **Initial Group Comparisons**: Necessary for creating an initial ranking.
3. **Adaptive Shuffling**: Ensures diverse comparisons and reduces bias.
4. **Final Scoring and Selection**: Critical for determining the top papers.

### Components to Remove:
1. **Stratified Group Formation**: While helpful, the benefits of stratified sampling are marginal compared to random grouping when multiple rounds of shuffling are used.
2. **Weighted Scoring System**: The improvement from weighting scores is minimal compared to the complexity it adds. Simple averaging can suffice.
3. **Detailed Preprocessing for Relevant Sections**: Using the full text without detailed preprocessing for relevant sections simplifies implementation without a significant loss in quality, especially when using the full text within the 9,000-word limit.

### Final Simplified Plan:

#### Step-by-Step Process:

### Overview:
1. **Clipping Papers**: Ensure papers are clipped to a manageable length.
2. **Initial Group Comparisons**: Rank groups of papers.
3. **Adaptive Shuffling and Re-Comparison**: Shuffle and re-rank papers to ensure diverse comparisons.
4. **Final Selection**: Rank papers based on averaged scores and select the top N.

#### Step 1: Preprocessing - Clipping Papers

**Objective**: Reduce the length of each paper to a maximum of 9,000 words to ensure that the comparison text is manageable.

1. **Clip Papers**: 
   - Use a function to clip each paper to 9,000 words.
   - This ensures the text remains within the LLM's context window and focuses on the most relevant content.

#### Step 2: Initial Group Comparisons

**Objective**: Form initial groups of papers and rank them.

1. **Form Groups**:
   - Divide the clipped papers into groups of four.

2. **Comparison and Ranking**:
   - **Prompt**: "Rank these four papers from most to least relevant to the query: Paper A (summary/abstract), Paper B (summary/abstract), Paper C (summary/abstract), Paper D (summary/abstract)."
   - **Action**: The LLM ranks the four papers in one API call.
   - **Scoring**: Assign scores based on the rank within each group (4 points for the top paper, 3 for the second, 2 for the third, 1 for the fourth).

3. **Repeat for All Groups**:
   - Continue this process for all initial groups of four.

#### Step 3: Adaptive Shuffling and Re-Comparison

**Objective**: Ensure diverse comparisons by shuffling papers and re-ranking them in multiple rounds.

1. **Shuffle Papers**:
   - Randomly reshuffle the papers to form new groups, ensuring diversity and avoiding repeated groupings as much as possible.

2. **New Group Comparisons**:
   - Form new groups of four and repeat the comparison and ranking process.
   - Use the same ranking prompt as in Step 2.

3. **Repeat and Average**:
   - Perform multiple rounds of shuffling and comparisons (e.g., 3-5 rounds).
   - Average the scores for each paper across all rounds to get a final relevance score.

#### Step 4: Final Selection

**Objective**: Rank papers based on averaged scores and select the top N papers.

1. **Rank Based on Averaged Scores**:
   - Rank the papers based on their averaged scores from all comparison rounds.

2. **Select Top N Papers**:
   - Choose the top N papers based on the final ranking.

### Example Workflow for 20 Papers:

1. **Clipping Papers**:
   - Clip each of the 20 papers to a maximum of 9,000 words.

2. **Initial Group Comparisons**:
   - **Form Groups**: 20 papers, groups of 4 → 5 groups.
   - **API Calls**: 5 calls (each call ranks 4 papers).

3. **Shuffle and Re-Compare**:
   - **Shuffle**: Randomly reshuffle papers into new groups.
   - **Repeat Comparisons**: Perform 3 rounds of shuffling and comparisons.
   - **API Calls per Round**: 5 calls (each call ranks 4 papers).
   - **Total API Calls for Shuffling**: 3 rounds × 5 calls = 15 calls.

4. **Final Scoring and Selection**:
   - **Average Scores**: Aggregate and average scores from all rounds.
   - **Select Top Papers**: Based on final averaged scores.

### API Call Analysis for Different Numbers of Papers:

#### For 10 Papers:
- **Initial Group Comparisons**: \( \frac{10}{4} = 2.5 \) (round up to 3 groups) → 3 API calls.
- **Shuffling Rounds**: 3 rounds × 3 calls = 9 API calls.
- **Total**: 3 + 9 = 12 API calls.
- **Ratio**: 12 API calls / 10 papers = 1.2.

#### For 20 Papers:
- **Initial Group Comparisons**: \( \frac{20}{4} = 5 \) groups → 5 API calls.
- **Shuffling Rounds**: 3 rounds × 5 calls = 15 API calls.
- **Total**: 5 + 15 = 20 API calls.
- **Ratio**: 20 API calls / 20 papers = 1.

#### For 50 Papers:
- **Initial Group Comparisons**: \( \frac{50}{4} = 12.5 \) (round up to 13 groups) → 13 API calls.
- **Shuffling Rounds**: 3 rounds × 13 calls = 39 API calls.
- **Total**: 13 + 39 = 52 API calls.
- **Ratio**: 52 API calls / 50 papers = 1.04.

### Final Analysis:

**Pros**:
- **Efficiency**: Significant reduction in API calls compared to pairwise comparisons.
- **Fairness**: Shuffling and multiple rounds ensure that good and bad papers are fairly compared.
- **Precision**: Averaging scores across multiple rounds reduces the impact of any single comparison’s bias.

**Cons**:
- **Complexity**: Reduced from the original plan but still requires implementing shuffling logic.
- **API Cost**: Though reduced, still involves multiple rounds of comparisons.

### Conclusion:

By focusing on essential elements such as clipping papers, initial group comparisons, adaptive shuffling, and final scoring, we maintain a balance of efficiency, fairness, and precision while minimizing complexity and API calls. This streamlined approach should effectively rank academic papers with a high degree of reliability.


"""

# academic_claim_analyzer/paper_ranker.py

import asyncio
import json
import random
from typing import List, Dict
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

async def rank_group(handler: LLMHandler, claim: str, papers: List[Paper]) -> List[Dict[str, any]]:
    """Rank a group of papers using the LLM."""
    paper_summaries = "\n".join([f"Paper ID: {paper.id}\nTitle: {paper.title}\nAbstract: {paper.abstract[:200]}..." for paper in papers])
    prompt = RANKING_PROMPT.format(claim=claim, paper_summaries=paper_summaries, num_papers=len(papers))
    
    response = await handler.query(prompt, model="gpt_4o_mini", sync=False, max_input_tokens=4000)
    
    try:
        rankings = json.loads(response)['rankings']
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
    
    paper_scores = {paper.id: [] for paper in papers}
    
    for round in range(num_rounds):
        logger.info(f"Starting ranking round {round + 1} of {num_rounds}")
        shuffled_papers = random.sample(papers, len(papers))
        
        # Split papers into groups of 5
        paper_groups = [shuffled_papers[i:i+5] for i in range(0, len(shuffled_papers), 5)]
        
        # Rank each group
        ranking_tasks = [rank_group(handler, claim, group) for group in paper_groups]
        group_rankings = await asyncio.gather(*ranking_tasks)
        
        # Accumulate scores
        for rankings in group_rankings:
            for ranking in rankings:
                paper_id = ranking['paper_id']
                rank = ranking['rank']
                score = len(papers) - rank + 1  # Convert rank to score
                paper_scores[paper_id].append(score)
    
    # Calculate average scores
    average_scores = {paper_id: sum(scores) / len(scores) for paper_id, scores in paper_scores.items()}
    
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