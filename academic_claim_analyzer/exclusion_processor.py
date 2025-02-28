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
You are analyzing the following academic paper to (1) evaluate certain Exclusion Criteria (boolean flags) and (2) extract structured data fields. Read the entire text carefully and then produce a single JSON object with **exactly** the fields specified in the schema below. Do not add extra keys, text, or commentary.

---

**Paper to Analyze**

Title: {rp.title}

Full Text:
{rp.full_text}

---

**Task Requirements**

1. **Exclusion Criteria** (boolean fields):  
   - Each field asks whether the paper meets some condition that would exclude it from further analysis.  
   - If the paper’s text clearly indicates the condition is true, set that field to `true`.  
   - If the text either contradicts it or does not mention it, set that field to `false`.  
   - If **any** boolean exclusion criterion is `true`, the paper is considered excluded.

2. **Data Extraction Fields** (string, float, integer, boolean, or list):  
   - Provide the requested information from the paper.  
   - If the paper does not specify a requested piece of data (e.g., no mention of water savings), use the fallback indicated by the schema:  
     - For strings: `"N/A"`  
     - For floats or integers: `-1` (or `-1.0`)  
     - For booleans: `false`  
     - For lists: `[]`  

3. **Schema**  
   - Here is a JSON schema describing all required fields and the expected data types.  
   - **You must** return a JSON object matching this schema exactly—no extra keys or wrappers.  
   - For example, if the schema says a field is a `float`, you must return a numeric literal like `3.14`, `0.0`, or `-1.0`.

Schema Definition:
{CombinedSchema.model_json_schema()}

---

**Output Format Requirements**

1. Return only a single **valid JSON object** (no markdown, no code block fences, no extra commentary).  
2. Every field in the schema must be present in the JSON output.  
3. For each Exclusion Criterion, output `true` or `false`.  
4. For each Extraction Field, fill in the best possible value or the fallback default if missing.  
5. Do not include any text or disclaimers—just the raw JSON.

---

### Important Clarifications

- If the paper’s text is ambiguous or silent about a particular boolean exclusion criterion, set that criterion to `false` (i.e., we assume it does **not** meet that exclusion).  
- If the text is ambiguous or silent about a requested numeric or string field, apply the fallback (`-1`/`-1.0` for numbers, `"N/A"` for strings, `[]` for lists, `false` for booleans).  
- Do not guess or fabricate data.  
- **Do not** add any fields that are not in the schema.  

**Now produce the JSON output.** Do not include any extra text before or after the JSON.
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