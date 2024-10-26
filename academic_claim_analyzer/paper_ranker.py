# academic_claim_analyzer/paper_ranker.py

import asyncio
import random
import logging
import math
from typing import List, Dict, Any, Optional, Type
from pydantic import BaseModel, Field, create_model
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

def create_combined_schema(exclusion_schema: Optional[Type[BaseModel]], 
                         extraction_schema: Optional[Type[BaseModel]]) -> Type[BaseModel]:
    """Create a combined schema from exclusion and extraction schemas."""
    fields = {}
    annotations = {}

    # Add fields from exclusion schema
    if exclusion_schema:
        for field_name, field in exclusion_schema.model_fields.items():
            annotations[field_name] = field.annotation
            fields[field_name] = field

    # Add fields from extraction schema
    if extraction_schema:
        for field_name, field in extraction_schema.model_fields.items():
            annotations[field_name] = field.annotation
            fields[field_name] = field

    # Create combined model
    namespace = {
        '__annotations__': annotations,
        **{name: field for name, field in fields.items()},
        'model_config': {
            'json_schema_extra': {
                'type': 'object',
                'required': list(annotations.keys()),
                'additionalProperties': False,
                'properties': {
                    name: {
                        'type': 'boolean' if field.annotation == bool else 'string',
                        'description': field.description
                    } for name, field in fields.items()
                }
            }
        }
    }

    return create_model('CombinedSchema', **namespace)

def calculate_ranking_rounds(num_papers: int) -> int:
    """Calculate optimal number of ranking rounds based on paper count."""
    if num_papers < 5:
        return 3
    rounds = min(10, math.floor(math.log2(num_papers) * 2) + 3)
    return max(3, rounds)

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
            group_size = num_papers
        else:
            inner_division = num_papers // max_group_size
            logger.info(f"Inner division result: {inner_division}")
            group_size = min(max_group_size, max(min_group_size, num_papers // inner_division))
        
        logger.info(f"Calculated group size: {group_size}")
        groups = [papers[i:i + group_size] for i in range(0, num_papers, group_size)]
        
        if len(groups[-1]) < min_group_size and len(groups) > 1:
            last_group = groups.pop()
            for i, paper in enumerate(last_group):
                groups[i % len(groups)].append(paper)
        
        logger.info(f"Created {len(groups)} groups")
        return groups

    except Exception as e:
        logger.error(f"Error in create_balanced_groups: {str(e)}", exc_info=True)
        return [papers]

async def rank_papers(papers: List[Paper], claim: str, exclusion_schema: Optional[Type[BaseModel]] = None,
                     extraction_schema: Optional[Type[BaseModel]] = None, top_n: int = 5) -> List[RankedPaper]:
    """Rank papers based on their relevance to the given claim."""
    handler = LLMAPIHandler()
    logger.info(f"Starting to rank {len(papers)} papers")

    # Create combined schema for evaluation if needed
    combined_schema = None
    if exclusion_schema or extraction_schema:
        combined_schema = create_combined_schema(exclusion_schema, extraction_schema)
        logger.info("Created combined schema for paper evaluation")

    valid_papers = [
        paper for paper in papers 
        if getattr(paper, 'full_text', '') and 
        len(getattr(paper, 'full_text', '').split()) >= 200
    ]
    logger.info(f"After filtering, {len(valid_papers)} valid papers remain")

    num_rounds = calculate_ranking_rounds(len(valid_papers))
    logger.info(f"Using {num_rounds} ranking rounds for {len(valid_papers)} papers")

    paper_scores: Dict[str, List[float]] = {f"paper_{i+1}": [] for i in range(len(valid_papers))}
    
    for i, paper in enumerate(valid_papers):
        setattr(paper, 'id', f"paper_{i+1}")

    # Conduct ranking rounds and calculate scores
    average_scores = await _conduct_ranking_rounds(valid_papers, claim, num_rounds, paper_scores, handler)

    print("\nScores of all papers:")
    for paper in valid_papers:
        print(f"Paper ID: {paper.id}, Title: {paper.title[:100]}..., Average Score: {average_scores.get(paper.id, 0.00):.2f}")

    # Select top papers for analysis
    top_papers = sorted(
        valid_papers,
        key=lambda p: average_scores.get(p.id, 0),
        reverse=True
    )[:top_n]

    # Process detailed analysis and evaluations
    ranked_papers = []
    for paper in top_papers:
        try:
            # Get paper analysis
            analysis_obj = await _get_paper_analysis(paper, claim, handler)
            if not analysis_obj:
                continue

            # Get evaluation results if schemas exist
            evaluation_results = await _evaluate_paper(paper, combined_schema, handler) if combined_schema else {}

            # Get or generate BibTeX
            generated_bibtex = await _get_bibtex(paper)

            # Create clean paper dict and update with new values
            paper_dict = paper.model_dump()
            paper_dict.update({
                'bibtex': generated_bibtex or paper_dict.get('bibtex', ''),
                'relevance_score': average_scores.get(paper.id, 0.0),
                'analysis': analysis_obj.analysis,
                'relevant_quotes': analysis_obj.relevant_quotes,
                'exclusion_criteria_result': evaluation_results.get('exclusion_criteria_result', {}),
                'extraction_result': evaluation_results.get('extraction_result', {})
            })

            # Create ranked paper with clean data
            ranked_paper = RankedPaper(**paper_dict)
            ranked_papers.append(ranked_paper)
            logger.info(f"Successfully created ranked paper for: {paper.title[:100]}")

        except Exception as e:
            logger.error(f"Error processing paper {paper.title[:100]}...: {str(e)}", exc_info=True)

    if not ranked_papers:
        logger.error("No papers were successfully ranked and analyzed")
    else:
        logger.info(f"Successfully ranked and analyzed {len(ranked_papers)} papers")

    return ranked_papers

async def _conduct_ranking_rounds(valid_papers: List[Paper], claim: str, num_rounds: int, 
                                paper_scores: Dict[str, List[float]], handler: LLMAPIHandler) -> Dict[str, float]:
    """Conduct ranking rounds and return average scores."""
    for round in range(num_rounds):
        logger.info(f"Starting ranking round {round + 1} of {num_rounds}")
        shuffled_papers = random.sample(valid_papers, len(valid_papers))
        
        paper_groups = create_balanced_groups([{
            "id": paper.id,
            "full_text": getattr(paper, 'full_text', '')[:500],
            "title": getattr(paper, 'title', ''),
            "abstract": getattr(paper, 'abstract', '')
        } for paper in shuffled_papers])

        prompts = [_create_ranking_prompt(group, claim) for group in paper_groups]
        
        logger.info("Sending ranking prompts to LLM")
        batch_responses = await handler.process(
            prompts=prompts,
            model="gpt-4o-mini",
            mode="openai_batch",
            response_format=RankingResponse
        )

        await _process_ranking_responses(batch_responses, paper_scores)

    # Calculate average scores
    average_scores = {}
    for paper_id, scores in paper_scores.items():
        if scores:
            average_scores[paper_id] = sum(scores) / len(scores)
            logger.info(f"Paper {paper_id} average score: {average_scores[paper_id]:.2f}")
        else:
            logger.warning(f"No scores recorded for paper {paper_id}. Assigning lowest score.")
            average_scores[paper_id] = 0.0

    return average_scores

def _create_ranking_prompt(group: List[Dict[str, Any]], claim: str) -> str:
    """Create a ranking prompt for a group of papers."""
    paper_summaries = "\n".join([
        f"Paper ID: {paper['id']}\n"
        f"Title: {paper['title'][:100]}\n"
        f"Abstract: {paper['abstract'][:200]}...\n"
        f"Full Text Excerpt: {paper['full_text'][:300]}..."
        for paper in group
    ])
    
    return f"""
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

async def _process_ranking_responses(batch_responses: List[Any], paper_scores: Dict[str, List[float]]):
    """Process ranking responses and update paper scores."""
    for response in batch_responses:
        if not response:
            continue
            
        try:
            rankings = None
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

async def _get_paper_analysis(paper: Paper, claim: str, handler: LLMAPIHandler) -> Optional[AnalysisResponse]:
    """Get detailed analysis for a paper."""
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

    response = await handler.process(
        prompts=prompt,
        model="gpt-4o-mini",
        mode="regular",
        response_format=AnalysisResponse
    )

    if isinstance(response, AnalysisResponse):
        return response
    elif isinstance(response, dict):
        if 'response' in response and isinstance(response['response'], AnalysisResponse):
            return response['response']
        elif 'analysis' in response and 'relevant_quotes' in response:
            return AnalysisResponse(**response)
    return None

async def _evaluate_paper(paper: Paper, combined_schema: Type[BaseModel], 
                         handler: LLMAPIHandler) -> Dict[str, Dict[str, Any]]:
    """Evaluate paper against provided schemas."""
    if not combined_schema:
        return {}

    prompt = f"""
Evaluate this paper against the provided criteria:

Title: {paper.title}
Abstract: {paper.abstract or ''}
Full Text: {paper.full_text[:1000] if paper.full_text else ''}...

Provide evaluation results according to the schema.
"""

    response = await handler.process(
        prompts=prompt,
        model="gpt-4o-mini",
        mode="regular",
        response_format=combined_schema
    )

    if not response:
        return {}

    response_dict = response.model_dump()
    
    # Split response into exclusion and extraction results
    exclusion_fields = {name: field for name, field in combined_schema.model_fields.items() 
                       if field.annotation == bool}
    extraction_fields = {name: field for name, field in combined_schema.model_fields.items() 
                        if field.annotation != bool}

    return {
        'exclusion_criteria_result': {k: v for k, v in response_dict.items() if k in exclusion_fields},
        'extraction_result': {k: v for k, v in response_dict.items() if k in extraction_fields}
    }

async def _get_bibtex(paper: Paper) -> str:
    """Get BibTeX for a paper, attempting multiple methods."""
    if paper.doi:
        bibtex = get_bibtex_from_doi(paper.doi)
        if bibtex:
            return bibtex
    
    if paper.title and paper.authors and paper.year:
        bibtex = get_bibtex_from_title(paper.title, paper.authors, paper.year)
        if bibtex:
            return bibtex
    
    return ""

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

        # Create simple test schemas
        class ExclusionCriteria(BaseModel):
            is_relevant: bool = Field(description="Is the paper relevant to the topic?")
            has_sufficient_data: bool = Field(description="Does the paper have sufficient data?")

        class ExtractionSchema(BaseModel):
            key_findings: str = Field(description="Key findings from the paper")
            methodology: str = Field(description="Research methodology used")

        for papers in test_sets:
            logger.info(f"\nTesting with {len(papers)} papers")
            ranked_papers = await rank_papers(
                papers=papers,
                claim="Test claim for ranking papers",
                exclusion_schema=ExclusionCriteria,
                extraction_schema=ExtractionSchema,
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
                assert paper.exclusion_criteria_result, "Missing exclusion criteria results"
                assert paper.extraction_result, "Missing extraction results"

        logger.info("All ranking tests completed successfully")

    import asyncio
    return asyncio.run(run_test())

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_ranking()