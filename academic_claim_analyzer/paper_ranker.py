# academic_claim_analyzer/paper_ranker.py

import asyncio
import random
import logging
import math
from typing import List, Dict, Any, Optional, Type
from pydantic import BaseModel, Field
from .models import Paper, RankedPaper
from .llm_api_handler import LLMAPIHandler
from .search.bibtex import get_bibtex_from_doi, get_bibtex_from_title

logger = logging.getLogger(__name__)

class Ranking(BaseModel):
    """Individual paper ranking with explanation."""
    paper_id: str = Field(description="Unique identifier for the paper")
    rank: int = Field(description="Rank assigned to the paper")
    explanation: str = Field(description="Explanation for the ranking")

class RankingResponse(BaseModel):
    """Response containing a list of rankings."""
    rankings: List[Ranking] = Field(description="List of rankings for papers")

class AnalysisResponse(BaseModel):
    """Detailed paper analysis with relevant quotes."""
    analysis: str = Field(description="Detailed analysis of the paper's relevance")
    relevant_quotes: List[str] = Field(description="List of relevant quotes from the paper")

def calculate_ranking_rounds(num_papers: int) -> int:
    """
    Calculate optimal number of ranking rounds based on paper count.
    
    Strategy:
    - Minimum 3 rounds for <5 papers to ensure stability
    - Logarithmic scaling up to 10 rounds maximum
    - More rounds for more papers, but with diminishing returns
    """
    if num_papers < 5:
        return 3
    
    # Logarithmic scaling: log2(n) * 2 + 3
    # This gives us:
    # 5 papers = 7 rounds
    # 10 papers = 8 rounds
    # 20 papers = 9 rounds
    # 40+ papers = 10 rounds
    rounds = min(10, math.floor(math.log2(num_papers) * 2) + 3)
    return max(3, rounds)  # Ensure at least 3 rounds

def create_balanced_groups(papers: List[Dict[str, Any]], min_group_size: int = 2, max_group_size: int = 5) -> List[List[Dict[str, Any]]]:
    """Create balanced groups of papers for ranking."""
    num_papers = len(papers)
    logger.info(f"Creating balanced groups for {num_papers} papers")
    logger.info(f"min_group_size: {min_group_size}, max_group_size: {max_group_size}")

    if num_papers < min_group_size:
        logger.warning(f"Too few papers ({num_papers}) to create groups. Returning single group.")
        return [papers]

    try:
        if num_papers < max_group_size:
            logger.info(f"Number of papers ({num_papers}) less than max_group_size ({max_group_size}). Using num_papers as group size.")
            group_size = num_papers
        else:
            # Calculate optimal group size
            inner_division = num_papers // max_group_size
            logger.info(f"Inner division result: {inner_division}")
            if inner_division == 0:
                group_size = max_group_size
            else:
                group_size = min(max_group_size, max(min_group_size, num_papers // inner_division))
        
        logger.info(f"Calculated group size: {group_size}")
        groups = [papers[i:i + group_size] for i in range(0, num_papers, group_size)]
        
        # Handle last group if too small
        if len(groups[-1]) < min_group_size and len(groups) > 1:
            last_group = groups.pop()
            for i, paper in enumerate(last_group):
                groups[i % len(groups)].append(paper)
        
        logger.info(f"Created {len(groups)} groups")
        return groups

    except Exception as e:
        logger.error(f"Error in create_balanced_groups: {str(e)}", exc_info=True)
        return [papers]

async def rank_papers(papers: List[Paper], claim: str, top_n: int = 5) -> List[RankedPaper]:
    """Rank papers based on their relevance to the given claim."""
    handler = LLMAPIHandler()
    logger.info(f"Starting to rank {len(papers)} papers")

    # Filter and validate papers
    valid_papers = [
        paper for paper in papers 
        if getattr(paper, 'full_text', '') and 
        len(getattr(paper, 'full_text', '').split()) >= 200
    ]
    logger.info(f"After filtering, {len(valid_papers)} valid papers remain")

    # Calculate optimal number of ranking rounds
    num_rounds = calculate_ranking_rounds(len(valid_papers))
    logger.info(f"Using {num_rounds} ranking rounds for {len(valid_papers)} papers")

    # Initialize paper scores with paper IDs
    paper_scores: Dict[str, List[float]] = {f"paper_{i+1}": [] for i in range(len(valid_papers))}
    
    # Assign IDs to papers for tracking
    for i, paper in enumerate(valid_papers):
        setattr(paper, 'id', f"paper_{i+1}")

    # Conduct ranking rounds
    for round in range(num_rounds):
        logger.info(f"Starting ranking round {round + 1} of {num_rounds}")
        shuffled_papers = random.sample(valid_papers, len(valid_papers))
        
        # Create paper groups for ranking
        paper_groups = create_balanced_groups([{
            "id": paper.id,
            "full_text": getattr(paper, 'full_text', '')[:500],
            "title": getattr(paper, 'title', ''),
            "abstract": getattr(paper, 'abstract', '')
        } for paper in shuffled_papers])

        # Generate ranking prompts
        prompts = []
        for group in paper_groups:
            paper_summaries = "\n".join([
                f"Paper ID: {paper['id']}\n"
                f"Title: {paper['title'][:100]}\n"
                f"Abstract: {paper['abstract'][:200]}...\n"
                f"Full Text Excerpt: {paper['full_text'][:300]}..."
                for paper in group
            ])
            
            prompt = f"""
Analyze these papers' relevance to the claim: "{claim}"

Papers to analyze:
{paper_summaries}

Rank these papers from most to least relevant based on:
1. Direct relevance to the claim
2. Quality of evidence
3. Methodology strength
4. Overall impact

Your response must be a valid RankingResponse with exactly {len(group)} rankings.
Each paper must be ranked uniquely from 1 to {len(group)}, where 1 is most relevant.
Use the exact paper_id as given.

Format:
{{
    "rankings": [
        {{
            "paper_id": "string (exact paper_id as given)",
            "rank": "integer (1 to {len(group)})",
            "explanation": "string (detailed explanation)"
        }}
    ]
}}
"""
            prompts.append(prompt)

        # Process rankings
        logger.info("Sending ranking prompts to LLM")
        batch_responses = await handler.process(
            prompts=prompts,
            model="gpt-4o-mini",
            mode="async_batch",
            response_format=RankingResponse
        )

        # Process ranking responses
        for response in batch_responses:
            if not response:
                continue
                
            try:
                rankings = None
                # Extract rankings from response
                if isinstance(response, RankingResponse):
                    rankings = response.rankings
                elif isinstance(response, dict):
                    if 'rankings' in response:
                        rankings = response['rankings']
                    elif 'response' in response and isinstance(response['response'], RankingResponse):
                        rankings = response['response'].rankings

                if not rankings:
                    logger.error(f"Invalid rankings format: {response}")
                    continue

                # Process rankings
                group_size = len(rankings)
                for ranking in rankings:
                    paper_id = ranking.paper_id
                    if paper_id in paper_scores:
                        score = (group_size - ranking.rank + 1) / group_size
                        paper_scores[paper_id].append(score)
                        logger.debug(f"Added score {score} for paper {paper_id}")
                    else:
                        logger.warning(f"Unknown paper_id in ranking: {paper_id}")

            except Exception as e:
                logger.error(f"Error processing ranking response: {str(e)}", exc_info=True)

    # Calculate average scores
    average_scores = {}
    for paper_id, scores in paper_scores.items():
        if scores:
            average_scores[paper_id] = sum(scores) / len(scores)
            logger.info(f"Paper {paper_id} average score: {average_scores[paper_id]:.2f}")
        else:
            logger.warning(f"No scores recorded for paper {paper_id}. Assigning lowest score.")
            average_scores[paper_id] = 0.0

    print("\nScores of all papers:")
    for paper in valid_papers:
        print(f"Paper ID: {paper.id}, Title: {paper.title[:100]}..., Average Score: {average_scores.get(paper.id, 0.00):.2f}")

    # Select top papers for detailed analysis
    top_papers = sorted(
        valid_papers,
        key=lambda p: average_scores.get(p.id, 0),
        reverse=True
    )[:top_n]

    # Generate analysis prompts for top papers
    analysis_prompts = []
    logger.info(f"Sending {len(top_papers)} analysis prompts to LLM")
    for paper in top_papers:
        prompt = f"""
Analyze this paper's relevance to the claim: "{claim}"

Paper details:
Title: {paper.title}
Full Text: {getattr(paper, 'full_text', '')[:1000]}...

Provide a super detailed technical analysis focusing on:
1. Direct relevance to the claim
2. Methodology and evidence quality
3. Significance of findings
4. Limitations and potential biases

Your response must be a valid AnalysisResponse object with:
1. A comprehensive technical analysis (minimum 500 words)
2. Three relevant quotes from the paper (100+ words each)

Format:
{{
    "analysis": "Detailed technical analysis here",
    "relevant_quotes": [
        "First detailed quote from paper",
        "Second detailed quote from paper",
        "Third detailed quote from paper"
    ]
}}"""
        analysis_prompts.append(prompt)

    # Process analysis prompts
    analysis_responses = await handler.process(
        prompts=analysis_prompts,
        model="gpt-4o-mini",
        mode="async_batch",
        response_format=AnalysisResponse
    )

    # Create ranked papers from analysis
    ranked_papers = []
    for paper, response in zip(top_papers, analysis_responses):
        try:
            # Extract analysis response
            analysis_obj = None
            if isinstance(response, AnalysisResponse):
                analysis_obj = response
            elif isinstance(response, dict):
                if 'response' in response and isinstance(response['response'], AnalysisResponse):
                    analysis_obj = response['response']
                elif 'analysis' in response and 'relevant_quotes' in response:
                    analysis_obj = AnalysisResponse(**response)

            if not analysis_obj:
                logger.error(f"Could not extract analysis from response: {response}")
                continue

            # Get BibTeX and create ranked paper, with fallback to existing bibtex
            generated_bibtex = ""
            if paper.doi:
                generated_bibtex = get_bibtex_from_doi(paper.doi) or ""
            if not generated_bibtex and paper.title:
                generated_bibtex = get_bibtex_from_title(
                    paper.title,
                    paper.authors,
                    paper.year
                ) or ""

            # Copy the paper dict and prepare it for ranked paper creation
            paper_dict = paper.__dict__.copy()
            paper_dict.pop('id', None)  # Remove ID as it's not needed in final ranked paper
            
            # Use generated bibtex if we got one, otherwise keep existing
            final_bibtex = generated_bibtex if generated_bibtex else paper_dict.get('bibtex', '')
            paper_dict['bibtex'] = final_bibtex

            # Create ranked paper
            ranked_paper = RankedPaper(
                **paper_dict,
                relevance_score=average_scores.get(paper.id, 0.0),
                analysis=analysis_obj.analysis,
                relevant_quotes=analysis_obj.relevant_quotes
            )
            
            ranked_papers.append(ranked_paper)
            logger.info(f"Successfully created ranked paper for: {paper.title[:100]}")

        except Exception as e:
            logger.error(f"Error processing analysis for paper {paper.title[:100]}...: {str(e)}", exc_info=True)
            logger.debug(f"Paper fields: {list(paper_dict.keys())}")  # Just log what fields exist, not their contents
            logger.debug(f"Analysis status: {'Success' if analysis_obj else 'Failed'}")
            logger.debug(f"BibTeX status: {'Generated' if generated_bibtex else 'Missing'}")

    if not ranked_papers:
        logger.error("No papers were successfully ranked and analyzed")
    else:
        logger.info(f"Successfully ranked and analyzed {len(ranked_papers)} papers")

    return ranked_papers

def test_ranking():
    """Test the paper ranking functionality."""
    async def run_test():
        # Create test papers with varying sizes to test scaling
        test_sets = [
            [Paper(
                title=f"Test Paper {i}",
                authors=["Author A", "Author B"],
                year=2024,
                doi=f"10.1234/test.{i}",
                abstract="Test abstract",
                full_text="Test full text " * 100,
                source="Test Source"
            ) for i in range(1, size + 1)]
            for size in [3, 5, 10, 20]
        ]

        for papers in test_sets:
            logger.info(f"\nTesting with {len(papers)} papers")
            ranked_papers = await rank_papers(
                papers=papers,
                claim="Test claim for ranking papers",
                top_n=min(3, len(papers))
            )

            # Verify results
            assert len(ranked_papers) > 0, "No papers were ranked"
            for paper in ranked_papers:
                assert isinstance(paper, RankedPaper), "Invalid paper type"
                assert paper.relevance_score is not None, "Missing relevance score"
                assert paper.analysis, "Missing analysis"
                assert len(paper.relevant_quotes) > 0, "Missing relevant quotes"
                assert isinstance(paper.bibtex, str), "Missing or invalid bibtex"

        logger.info("All ranking tests completed successfully")

    import asyncio
    return asyncio.run(run_test())

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_ranking()