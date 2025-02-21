# academic_claim_analyzer/main.py

import asyncio
import logging
from typing import List, Dict, Any, Optional, Type
from pydantic import BaseModel, Field, create_model

from .query_formulator import formulate_queries
from .paper_ranker import rank_papers, llm_handler, get_model_or_default, DEFAULT_LLM_MODEL
from .search import OpenAlexSearch, ScopusSearch, CORESearch, ArxivSearch, BaseSearch
from .models import RequestAnalysis, Paper, RankedPaper

logger = logging.getLogger(__name__)

async def analyze_request(
    query: str,
    ranking_guidance: str = "",
    exclusion_criteria: Optional[Dict[str, Any]] = None,
    data_extraction_schema: Optional[Dict[str, Any]] = None,
    num_queries: int = 2,
    papers_per_query: int = 2,
    num_papers_to_return: int = 2
) -> RequestAnalysis:
    """
    Analyze a user's research request. This includes:
      1) Formulating queries for multiple platforms (Scopus, OpenAlex, arXiv, etc.)
      2) Searching and fetching papers
      3) Applying exclusion criteria
      4) Ranking papers using the provided ranking guidance
      5) Extracting requested information
    """
    logger.info(f"Analyzing request with exclusion criteria: {exclusion_criteria}")
    logger.info(f"Data extraction schema: {data_extraction_schema}")
    logger.info(f"Ranking guidance: {ranking_guidance}")

    analysis = RequestAnalysis(
        query=query,
        ranking_guidance=ranking_guidance,
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

        if data_extraction_schema:
            ExtractionSchemaModel = create_model_from_schema('DataExtractionSchema', data_extraction_schema)
            analysis.data_extraction_schema = ExtractionSchemaModel

        await _perform_analysis(analysis)
    except Exception as e:
        logger.error(f"Error during request analysis: {str(e)}", exc_info=True)
        analysis.metadata["error"] = str(e)

    return analysis

def create_model_from_schema(model_name: str, schema: Dict[str, Any]) -> Type[BaseModel]:
    """
    Dynamically create a Pydantic model from a dictionary schema describing fields
    and their types.
    """
    annotations = {}
    fields = {}
    properties = {}

    for field_name, field_info in schema.items():
        field_type = field_info.get('type', 'string').lower()
        description = field_info.get('description', '')

        if field_type == 'number':
            python_type = float
            description += " (Use -1.0 if unknown)"
            default_value = -1.0
            json_type = 'number'
        elif field_type == 'integer':
            python_type = int
            description += " (Use -1 if unknown)"
            default_value = -1
            json_type = 'integer'
        elif field_type == 'boolean':
            python_type = bool
            description += " (Must be true/false)"
            default_value = False
            json_type = 'boolean'
        elif field_type == 'array' or field_type == 'list':
            from typing import List as PyList
            python_type = PyList[str]
            description += " (List of strings, empty if none)"
            default_value = []
            json_type = 'array'
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
            description += " (String, use 'N/A' if unknown)"
            default_value = "N/A"
            json_type = 'string'

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

async def _perform_analysis(analysis: RequestAnalysis) -> None:
    """Execute the full analysis pipeline: queries -> search -> exclusion -> rank."""
    await _formulate_queries(analysis)
    await _perform_searches(analysis)
    if analysis.search_results:
        await _apply_exclusion_criteria(analysis)
        await _rank_papers(analysis)

async def _formulate_queries(analysis: RequestAnalysis) -> None:
    """Generate search queries for different platforms (OpenAlex, Scopus, Arxiv)."""
    try:
        # OpenAlex
        openalex_queries = await formulate_queries(
            analysis.query,
            analysis.parameters["num_queries"],
            "openalex"
        )
        for q in openalex_queries:
            analysis.add_query(q, "openalex")

        # Scopus
        scopus_queries = await formulate_queries(
            analysis.query,
            analysis.parameters["num_queries"],
            "scopus"
        )
        for q in scopus_queries:
            analysis.add_query(q, "scopus")

        # arXiv
        arxiv_queries = await formulate_queries(
            analysis.query,
            analysis.parameters["num_queries"],
            "arxiv"
        )
        for q in arxiv_queries:
            analysis.add_query(q, "arxiv")

        # CORE (optionally, some want to pass raw or do the same approach)
        # For consistency, let's also do re-formulation for CORE:
        core_queries = await formulate_queries(
            analysis.query,
            analysis.parameters["num_queries"],
            "core"
        )
        for q in core_queries:
            analysis.add_query(q, "core")

    except Exception as e:
        logger.error(f"Error formulating queries: {str(e)}", exc_info=True)
        raise

async def _perform_searches(analysis: RequestAnalysis) -> None:
    """Execute searches across different platforms: openalex, scopus, core, arxiv."""
    search_tasks = []
    papers_per_query = analysis.parameters["papers_per_query"]

    try:
        # OpenAlex
        openalex_search = OpenAlexSearch("youremail@example.com")
        openalex_queries = [q for q in analysis.queries if q.source == "openalex"]
        for query in openalex_queries:
            search_tasks.append(
                _search_and_add_results(openalex_search, query.query, papers_per_query, analysis)
            )

        # Scopus
        scopus_search = ScopusSearch()
        scopus_queries = [q for q in analysis.queries if q.source == "scopus"]
        for query in scopus_queries:
            search_tasks.append(
                _search_and_add_results(scopus_search, query.query, papers_per_query, analysis)
            )

        # CORE
        core_search = CORESearch()
        core_queries = [q for q in analysis.queries if q.source == "core"]
        for query in core_queries:
            search_tasks.append(
                _search_and_add_results(core_search, query.query, papers_per_query, analysis)
            )

        # arXiv
        arxiv_search = ArxivSearch()
        arxiv_queries = [q for q in analysis.queries if q.source == "arxiv"]
        for query in arxiv_queries:
            search_tasks.append(
                _search_and_add_results(arxiv_search, query.query, papers_per_query, analysis)
            )

        await asyncio.gather(*search_tasks)

    except Exception as e:
        logger.error(f"Error performing searches: {str(e)}", exc_info=True)
        raise

async def _search_and_add_results(
    search_module: BaseSearch,
    query: str,
    limit: int,
    analysis: RequestAnalysis
) -> None:
    """Run a single search and add results to the analysis."""
    try:
        results = await search_module.search(query, limit)
        if results and isinstance(results, list):
            for paper in results:
                if isinstance(paper, Paper):
                    analysis.add_search_result(paper)
    except Exception as e:
        logger.error(f"Error during search with {search_module.__class__.__name__}: {str(e)}")

async def _apply_exclusion_criteria(analysis: RequestAnalysis) -> None:
    """Apply LLM-based exclusion criteria and data extraction to search results."""
    if not analysis.exclusion_schema and not analysis.data_extraction_schema:
        logger.info("No exclusion or extraction schema provided. Skipping.")
        return

    papers_to_evaluate = analysis.search_results
    CombinedSchema = create_combined_schema(
        analysis.exclusion_schema,
        analysis.data_extraction_schema
    )

    prompts = []
    ranked_papers = []
    for paper in papers_to_evaluate:
        rp = RankedPaper(
            **paper.model_dump(),
            relevance_score=None,
            relevant_quotes=[],
            analysis="",
            exclusion_criteria_result={},
            extraction_result={}
        )
        prompt_text = f"""
Assess the following academic paper against the specified exclusion criteria and data extraction requirements.

Title: {rp.title}
Full Text: {rp.full_text}

Return a JSON object that exactly matches these fields:
Exclusion criteria fields (boolean) => exclude if any is true.
Extraction fields => fill with appropriate data.

Here is the schema: {CombinedSchema.model_json_schema()}
"""
        prompts.append(prompt_text)
        ranked_papers.append(rp)

    results = await llm_handler.process(
        prompts=prompts,
        model=get_model_or_default(None),
        response_type=CombinedSchema
    )

    if not results.success or not isinstance(results.data, list):
        logger.error(f"Exclusion/data-extraction call failed: {results.error}")
        return

    filtered = []
    for i, item in enumerate(results.data):
        ranked_paper = ranked_papers[i]
        exclude = False

        if item.error:
            logger.error(f"Error evaluating paper '{ranked_paper.title}': {item.error}")
            continue

        schema_obj = item.data
        exclusion_result = {}
        extraction_result = {}

        if analysis.exclusion_schema:
            for f in analysis.exclusion_schema.model_fields:
                if hasattr(schema_obj, f):
                    val = getattr(schema_obj, f)
                    exclusion_result[f] = val
                    if isinstance(val, bool) and val:
                        exclude = True

        if analysis.data_extraction_schema:
            for f in analysis.data_extraction_schema.model_fields:
                if hasattr(schema_obj, f):
                    extraction_result[f] = getattr(schema_obj, f)

        ranked_paper.exclusion_criteria_result = exclusion_result
        ranked_paper.extraction_result = extraction_result

        if not exclude:
            filtered.append(ranked_paper)
        else:
            logger.info(f"Paper excluded: {ranked_paper.title}")

    analysis.search_results = filtered

def create_combined_schema(
    exclusion_schema: Optional[Type[BaseModel]],
    extraction_schema: Optional[Type[BaseModel]]
) -> Type[BaseModel]:
    """Combine two Pydantic models (exclusion, extraction) into one for LLM parsing."""
    from pydantic import Field

    fields = {}
    annotations = {}
    properties = {}

    if exclusion_schema:
        for name, field in exclusion_schema.model_fields.items():
            annotations[name] = field.annotation
            fields[name] = Field(description=field.description or f"Exclusion: {name}")
            properties[name] = {
                'type': 'boolean',
                'description': field.description or f"Exclusion: {name}"
            }

    if extraction_schema:
        for name, field in extraction_schema.model_fields.items():
            annotations[name] = field.annotation
            fields[name] = Field(description=field.description or f"Extraction: {name}")
            # map to JSON types
            if field.annotation == int:
                json_type = 'integer'
            elif field.annotation == float:
                json_type = 'number'
            elif field.annotation == bool:
                json_type = 'boolean'
            else:
                json_type = 'string'
            properties[name] = {
                'type': json_type,
                'description': field.description or f"Extraction: {name}"
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

    return type("CombinedSchema", (BaseModel,), namespace)

async def _rank_papers(analysis: RequestAnalysis) -> None:
    """Rank the papers using the paper_ranker module."""
    if not analysis.search_results:
        logger.warning("No papers to rank.")
        return
    try:
        ranked_list = await rank_papers(
            papers=analysis.search_results,
            query=analysis.query,
            ranking_guidance=analysis.ranking_guidance,
            exclusion_schema=analysis.exclusion_schema,
            data_extraction_schema=analysis.data_extraction_schema,
            top_n=analysis.parameters["num_papers_to_return"]
        )
        for rp in ranked_list:
            analysis.add_ranked_paper(rp)
    except Exception as e:
        logger.error(f"Error ranking papers: {str(e)}", exc_info=True)