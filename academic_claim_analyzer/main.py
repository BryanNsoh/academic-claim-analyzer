# academic_claim_analyzer/main.py

import asyncio
import logging
from typing import List, Dict, Any, Optional, Type, Tuple, Union
from .query_formulator import formulate_queries
from .paper_ranker import rank_papers
from .search import OpenAlexSearch, ScopusSearch, CORESearch, BaseSearch
from .models import ClaimAnalysis, Paper, RankedPaper
from .llm_api_handler import LLMAPIHandler
from pydantic import BaseModel, Field

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
            # Create annotations dict first
            annotations = {}
            field_definitions = {}
            
            for field_name, field_info in exclusion_criteria.items():
                # Add type annotation
                annotations[field_name] = bool
                # Add field definition
                field_definitions[field_name] = Field(
                    description=field_info.get('description', ''),
                    default=False  # Provide a default value
                )
            
            # Create the model class with proper annotations
            ExclusionCriteriaModel = type(
                'ExclusionCriteria',
                (BaseModel,),
                {
                    '__annotations__': annotations,
                    **{k: v for k, v in field_definitions.items()},
                    'model_config': {
                        'json_schema_extra': {
                            'type': 'object',
                            'required': list(annotations.keys()),
                            'additionalProperties': False,
                            'properties': {
                                k: {
                                    'type': 'boolean',
                                    'description': v.description
                                } for k, v in field_definitions.items()
                            }
                        }
                    }
                }
            )
            analysis.exclusion_schema = ExclusionCriteriaModel

        if extraction_schema:
            # Create extraction field annotations and definitions
            annotations = {}
            field_definitions = {}
            properties = {}
            
            for field_name, field_info in extraction_schema.items():
                field_type = field_info.get('type', 'string').lower()
                
                # Map schema types to Python types
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
                        'description': field_info.get('description', ''),
                        'items': {'type': 'string'}
                    }
                    continue
                else:
                    python_type = str
                    json_type = 'string'
                    default_value = ""
                
                # Add type annotation
                annotations[field_name] = python_type
                # Add field definition
                field_definitions[field_name] = Field(
                    description=field_info.get('description', ''),
                    default=default_value
                )
                # Add JSON schema property
                if field_name not in properties:
                    properties[field_name] = {
                        'type': json_type,
                        'description': field_info.get('description', '')
                    }

            # Create model with explicit annotations
            ExtractionSchemaModel = type(
                'ExtractionSchema',
                (BaseModel,),
                {
                    '__annotations__': annotations,
                    **{k: v for k, v in field_definitions.items()},
                    'model_config': {
                        'json_schema_extra': {
                            'type': 'object',
                            'required': list(annotations.keys()),
                            'additionalProperties': False,
                            'properties': properties
                        }
                    }
                }
            )
            analysis.extraction_schema = ExtractionSchemaModel
        
        await _perform_analysis(analysis)
    except Exception as e:
        logger.error(f"Error during claim analysis: {str(e)}", exc_info=True)
        analysis.metadata["error"] = str(e)
    
    return analysis

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
    evaluation_tasks = []

    for paper in papers_to_evaluate:
        evaluation_tasks.append(_evaluate_paper(paper, analysis))

    try:
        evaluated_papers = await asyncio.gather(*evaluation_tasks)
        
        # Filter papers based on exclusion criteria
        filtered_papers = []
        for eval_result in evaluated_papers:
            if eval_result:  # Ensure we have a valid result
                paper, exclude = eval_result
                if not exclude and isinstance(paper, Paper):
                    filtered_papers.append(paper)
                else:
                    logger.info(f"Paper excluded based on criteria: {paper.title if paper else 'Unknown'}")

        analysis.search_results = filtered_papers
    except Exception as e:
        logger.error(f"Error during exclusion criteria application: {str(e)}", exc_info=True)
        raise

async def _evaluate_paper(paper: Paper, analysis: ClaimAnalysis) -> Optional[Tuple[RankedPaper, bool]]:
    """Evaluate a single paper against criteria."""
    try:
        handler = LLMAPIHandler()
        
        # Convert Paper to RankedPaper at the start
        ranked_paper = RankedPaper(
            **paper.model_dump(),  # Use model_dump() instead of dict() for Pydantic v2
            relevance_score=None,
            relevant_quotes=[],
            analysis="",  # Removed duplicate bibtex parameter
            exclusion_criteria_result={},
            extraction_result={}
        )
        
        # Create schema components
        namespace = {
            '__module__': __name__,
            '__annotations__': {},
        }
        schema_properties = {}

        # Add exclusion criteria if present
        if analysis.exclusion_schema:
            for field_name, field in analysis.exclusion_schema.model_fields.items():
                namespace['__annotations__'][field_name] = bool
                namespace[field_name] = Field(
                    description=field.description or f"Exclusion criteria: {field_name}",
                    default=False
                )
                schema_properties[field_name] = {
                    'type': 'boolean',
                    'description': field.description or f"Exclusion criteria: {field_name}"
                }

        # Add extraction schema if present
        if analysis.extraction_schema:
            for field_name, field in analysis.extraction_schema.model_fields.items():
                python_type = field.annotation
                
                if python_type == str:
                    json_type = 'string'
                    default_value = ""
                elif python_type == int:
                    json_type = 'integer'
                    default_value = 0
                elif python_type == float:
                    json_type = 'number'
                    default_value = 0.0
                elif python_type == bool:
                    json_type = 'boolean'
                    default_value = False
                elif hasattr(python_type, "__origin__") and python_type.__origin__ == list:
                    json_type = 'array'
                    default_value = []
                    schema_properties[field_name] = {
                        'type': 'array',
                        'description': field.description or f"List field: {field_name}",
                        'items': {'type': 'string'}
                    }
                    namespace['__annotations__'][field_name] = List[str]
                    namespace[field_name] = Field(
                        description=field.description or f"List field: {field_name}",
                        default=default_value
                    )
                    continue
                else:
                    json_type = 'string'
                    default_value = ""
                
                namespace['__annotations__'][field_name] = python_type
                namespace[field_name] = Field(
                    description=field.description or f"Extraction field: {field_name}",
                    default=default_value
                )
                if field_name not in schema_properties:
                    schema_properties[field_name] = {
                        'type': json_type,
                        'description': field.description or f"Extraction field: {field_name}"
                    }

        # Add model configuration
        namespace['model_config'] = {
            'json_schema_extra': {
                'type': 'object',
                'required': list(namespace['__annotations__'].keys()),
                'additionalProperties': False,
                'properties': schema_properties
            }
        }

        # Create combined schema model
        CombinedSchema = type('CombinedSchema', (BaseModel,), namespace)

        # Build evaluation prompt
        prompt = f"""
Evaluate the following paper based on the provided criteria:

Title: {ranked_paper.title or 'Unknown Title'}
Abstract: {ranked_paper.abstract or 'No abstract available'}
Full Text Excerpt: {ranked_paper.full_text[:1000] if ranked_paper.full_text else 'No full text available'}

Provide your response strictly according to the schema requirements.
Your response must be valid JSON matching exactly the required schema.
"""

        # Get evaluation response
        response = await handler.process(
            prompts=prompt,
            model="gpt-4o-mini",
            mode="regular",
            response_format=CombinedSchema
        )

        # Process results
        exclude = False
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

        return ranked_paper, exclude

    except Exception as e:
        logger.error(f"Error evaluating paper: {str(e)}", exc_info=True)
        return None

async def _rank_papers(analysis: ClaimAnalysis) -> None:
    """Rank papers based on relevance."""
    if not analysis.search_results:
        logger.warning("No papers to rank.")
        return
    
    try:
        ranked_papers = await rank_papers(analysis.search_results, analysis.claim)
        for paper in ranked_papers:
            if isinstance(paper, RankedPaper):
                analysis.add_ranked_paper(paper)
    except Exception as e:
        logger.error(f"Error ranking papers: {str(e)}", exc_info=True)
        raise