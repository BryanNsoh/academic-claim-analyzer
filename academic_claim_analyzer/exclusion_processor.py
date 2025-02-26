# academic_claim_analyzer/exclusion_processor.py

import logging
from typing import Type
from pydantic import BaseModel

from .models import RequestAnalysis, RankedPaper
from .schema_manager import create_combined_schema
from .llm_handler_config import llm_handler

logger = logging.getLogger(__name__)

async def apply_exclusion_criteria(analysis: RequestAnalysis) -> None:
    """
    Apply exclusion criteria and extract data from papers.
    
    Args:
        analysis: The RequestAnalysis object containing papers and schemas
    """
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