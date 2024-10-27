# academic_claim_analyzer/main.py

import asyncio
import logging
from typing import List, Dict, Any, Optional, Type, Tuple, Union
from .query_formulator import formulate_queries
from .paper_ranker import rank_papers
from .search import OpenAlexSearch, ScopusSearch, CORESearch, BaseSearch
from .models import ClaimAnalysis, Paper, RankedPaper
from .llm_api_handler import LLMAPIHandler
from pydantic import BaseModel, Field, create_model

logger = logging.getLogger(__name__)

async def analyze_claim(
    claim: str,
    exclusion_criteria: Optional[Dict[str, Any]] = None,
    extraction_schema: Optional[Dict[str, Any]] = None,
    num_queries: int = 2,
    papers_per_query: int = 2,
    num_papers_to_return: int = 2
) -> ClaimAnalysis:
    """Analyze a claim and return results."""
    analysis = ClaimAnalysis(
        claim=claim,
        parameters={
            "num_queries": num_queries,
            "papers_per_query": papers_per_query,
            "num_papers_to_return": num_papers_to_return
        }
    )
    
    try:
        # Create Pydantic models from schemas if provided
        if exclusion_criteria:
            ExclusionCriteriaModel = create_model_from_schema('ExclusionCriteria', exclusion_criteria)
            analysis.exclusion_schema = ExclusionCriteriaModel

        if extraction_schema:
            ExtractionSchemaModel = create_model_from_schema('ExtractionSchema', extraction_schema)
            analysis.extraction_schema = ExtractionSchemaModel
        
        await _perform_analysis(analysis)
    except Exception as e:
        logger.error(f"Error during claim analysis: {str(e)}", exc_info=True)
        analysis.metadata["error"] = str(e)
    
    return analysis

def create_model_from_schema(model_name: str, schema: Dict[str, Any]) -> Type[BaseModel]:
    """Create a Pydantic model from a given schema."""
    annotations = {}
    fields = {}
    properties = {}

    for field_name, field_info in schema.items():
        field_type = field_info.get('type', 'string').lower()
        description = field_info.get('description', '')

        if field_type == 'number':
            python_type = float
            json_type = 'number'
            default_value = 0.0
        elif field_type == 'integer':
            python_type = int
            json_type = 'integer'
            default_value = 0
        elif field_type == 'boolean':
            python_type = bool
            json_type = 'boolean'
            default_value = False
        elif field_type == 'array':
            python_type = List[str]
            json_type = 'array'
            default_value = []
            properties[field_name] = {
                'type': 'array',
                'description': description,
                'items': {'type': 'string'}
            }
            annotations[field_name] = python_type
            fields[field_name] = Field(default=default_value, description=description)
            continue
        else:
            python_type = str
            json_type = 'string'
            default_value = ""

        annotations[field_name] = python_type
        fields[field_name] = Field(default=default_value, description=description)
        if field_name not in properties:
            properties[field_name] = {
                'type': json_type,
                'description': description
            }

    namespace = {
        '__annotations__': annotations,
        **fields,
        'model_config': {
            'json_schema_extra': {
                'type': 'object',
                'required': list(annotations.keys()),
                'additionalProperties': False,
                'properties': properties
            }
        }
    }

    return type(model_name, (BaseModel,), namespace)

async def _perform_analysis(analysis: ClaimAnalysis) -> None:
    """Execute the full analysis pipeline."""
    await _formulate_queries(analysis)
    await _perform_searches(analysis)
    if analysis.search_results:  # Only proceed if we have results
        await _apply_exclusion_criteria(analysis)
        await _rank_papers(analysis)

async def _formulate_queries(analysis: ClaimAnalysis) -> None:
    """Generate search queries for different platforms."""
    try:
        openalex_queries = await formulate_queries(analysis.claim, analysis.parameters["num_queries"], "openalex")
        scopus_queries = await formulate_queries(analysis.claim, analysis.parameters["num_queries"], "scopus")
        
        print(openalex_queries)  # Debug print
        print(scopus_queries)    # Debug print
        
        for query in openalex_queries:
            analysis.add_query(query, "openalex")
        for query in scopus_queries:
            analysis.add_query(query, "scopus")
    except Exception as e:
        logger.error(f"Error formulating queries: {str(e)}", exc_info=True)
        raise

async def _perform_searches(analysis: ClaimAnalysis) -> None:
    """Execute searches across different platforms."""
    search_tasks = []
    
    try:
        # OpenAlex search
        openalex_search = OpenAlexSearch("youremail@example.com")  # Update with actual email
        openalex_queries = [q for q in analysis.queries if q.source == "openalex"]
        for query in openalex_queries:
            search_tasks.append(_search_and_add_results(
                openalex_search, query.query, analysis.parameters["papers_per_query"], analysis
            ))
        
        # Scopus search
        scopus_search = ScopusSearch()
        scopus_queries = [q for q in analysis.queries if q.source == "scopus"]
        for query in scopus_queries:
            search_tasks.append(_search_and_add_results(
                scopus_search, query.query, analysis.parameters["papers_per_query"], analysis
            ))
        
        # CORE search
        core_search = CORESearch()
        search_tasks.append(_search_and_add_results(
            core_search, analysis.claim, analysis.parameters["papers_per_query"], analysis
        ))

        await asyncio.gather(*search_tasks)
    except Exception as e:
        logger.error(f"Error performing searches: {str(e)}", exc_info=True)
        raise

async def _search_and_add_results(search_module: BaseSearch, query: str, limit: int, analysis: ClaimAnalysis) -> None:
    """Execute a single search and add results to analysis."""
    try:
        results = await search_module.search(query, limit)
        if results and isinstance(results, list):  # Verify we have valid results
            for paper in results:
                if isinstance(paper, Paper):  # Verify each result is a Paper object
                    analysis.add_search_result(paper)
                else:
                    logger.warning(f"Invalid paper object returned from search: {type(paper)}")
    except Exception as e:
        logger.error(f"Error during search with {search_module.__class__.__name__}: {str(e)}")

async def _apply_exclusion_criteria(analysis: ClaimAnalysis) -> None:
    """Apply exclusion criteria to search results."""
    if not analysis.search_results:
        logger.warning("No search results to apply exclusion criteria to.")
        return
        
    if not analysis.exclusion_schema and not analysis.extraction_schema:
        logger.info("No exclusion criteria or extraction schema provided. Skipping this step.")
        return

    papers_to_evaluate = analysis.search_results
    handler = LLMAPIHandler()

    # Build prompts for batch processing
    prompts = []
    ranked_papers = []
    CombinedSchema = create_combined_schema(analysis.exclusion_schema, analysis.extraction_schema)
    for paper in papers_to_evaluate:
        # Convert Paper to RankedPaper
        ranked_paper = RankedPaper(
            **paper.model_dump(),
            relevance_score=None,
            relevant_quotes=[],
            analysis="",
            exclusion_criteria_result={},
            extraction_result={}
        )
        prompt = f"""
Evaluate the following paper based on the provided criteria:

Title: {ranked_paper.title or 'Unknown Title'}
Abstract: {ranked_paper.abstract or 'No abstract available'}
Full Text Excerpt: {ranked_paper.full_text[:1000] if ranked_paper.full_text else 'No full text available'}

Provide your response strictly according to the schema requirements.
Your response must be valid JSON matching exactly the required schema.
"""
        prompts.append(prompt)
        ranked_papers.append(ranked_paper)

    # Process prompts in batch
    try:
        responses = await handler.process(
            prompts=prompts,
            model="gpt-4o-mini",
            mode="async_batch",
            response_format=CombinedSchema
        )

        filtered_papers = []
        for idx, response in enumerate(responses):
            ranked_paper = ranked_papers[idx]
            exclude = False

            if isinstance(response, Exception):
                logger.error(f"Error evaluating paper '{ranked_paper.title}': {response}")
                continue

            # Process results
            if analysis.exclusion_schema:
                exclusion_result = {}
                for field_name in analysis.exclusion_schema.model_fields:
                    if hasattr(response, field_name):
                        value = getattr(response, field_name)
                        exclusion_result[field_name] = value
                        if isinstance(value, bool) and value is True:
                            exclude = True
                ranked_paper.exclusion_criteria_result = exclusion_result

            # Extract information
            if analysis.extraction_schema:
                extraction_result = {}
                for field_name in analysis.extraction_schema.model_fields:
                    if hasattr(response, field_name):
                        value = getattr(response, field_name)
                        extraction_result[field_name] = value
                ranked_paper.extraction_result = extraction_result

            if not exclude:
                filtered_papers.append(ranked_paper)
            else:
                logger.info(f"Paper excluded based on criteria: {ranked_paper.title}")

        analysis.search_results = filtered_papers

    except Exception as e:
        logger.error(f"Error during exclusion criteria application: {str(e)}", exc_info=True)
        raise

def create_combined_schema(exclusion_schema: Optional[Type[BaseModel]], extraction_schema: Optional[Type[BaseModel]]) -> Type[BaseModel]:
    """Create a combined schema from exclusion and extraction schemas."""
    fields = {}
    annotations = {}
    properties = {}

    # Add fields from exclusion schema
    if exclusion_schema:
        for field_name, field in exclusion_schema.model_fields.items():
            annotations[field_name] = field.annotation
            fields[field_name] = Field(description=field.description or f"Exclusion criteria: {field_name}")
            properties[field_name] = {
                'type': 'boolean',
                'description': field.description or f"Exclusion criteria: {field_name}"
            }

    # Add fields from extraction schema
    if extraction_schema:
        for field_name, field in extraction_schema.model_fields.items():
            annotations[field_name] = field.annotation
            fields[field_name] = Field(description=field.description or f"Extraction field: {field_name}")
            # Map Python types to JSON types
            json_type = 'string'
            if field.annotation == int:
                json_type = 'integer'
            elif field.annotation == float:
                json_type = 'number'
            elif field.annotation == bool:
                json_type = 'boolean'
            elif field.annotation == List[str]:
                json_type = 'array'
                properties[field_name] = {
                    'type': 'array',
                    'description': field.description or f"List field: {field_name}",
                    'items': {'type': 'string'}
                }
                continue
            properties[field_name] = {
                'type': json_type,
                'description': field.description or f"Extraction field: {field_name}"
            }

    namespace = {
        '__annotations__': annotations,
        **fields,
        'model_config': {
            'json_schema_extra': {
                'type': 'object',
                'required': list(annotations.keys()),
                'additionalProperties': False,
                'properties': properties
            }
        }
    }

    return type('CombinedSchema', (BaseModel,), namespace)

async def _rank_papers(analysis: ClaimAnalysis) -> None:
    """Rank papers based on relevance."""
    if not analysis.search_results:
        logger.warning("No papers to rank.")
        return
    
    try:
        # Pass the schemas to rank_papers
        ranked_papers = await rank_papers(
            papers=analysis.search_results,
            claim=analysis.claim,
            exclusion_schema=analysis.exclusion_schema,
            extraction_schema=analysis.extraction_schema
        )
        for paper in ranked_papers:
            if isinstance(paper, RankedPaper):
                analysis.add_ranked_paper(paper)
    except Exception as e:
        logger.error(f"Error ranking papers: {str(e)}", exc_info=True)
        raise
