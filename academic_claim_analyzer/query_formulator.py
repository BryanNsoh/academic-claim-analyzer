# academic_claim_analyzer/query_formulator.py

from typing import List
import logging
from pydantic import BaseModel, Field

from .llm_handler_config import llm_handler
logger = logging.getLogger(__name__)

SCOPUS_SEARCH_GUIDE = """
Syntax and Operators

Valid syntax for advanced search queries includes:

Field codes (e.g. TITLE, ABS, KEY, AUTH, AFFIL) to restrict searches to specific parts of documents
Boolean operators (AND, OR, AND NOT) to combine search terms
Proximity operators (W/n, PRE/n) to find words within a specified distance - W/n: Finds terms within \"n\" words of each other, regardless of order. Example: journal W/15 publishing finds articles where \"journal\" and \"publishing\" are within two words of each other. - PRE/n: Finds terms in the specified order and within \"n\" words of each other. Example: data PRE/50 analysis finds articles where \"data\" appears before \"analysis\" within three words. - To find terms in the same sentence, use 15. To find terms in the same paragraph, use 50 -
Quotation marks for loose/approximate phrase searches
Braces \{\} for exact phrase searches
Wildcards (*) to capture variations of search terms

Invalid syntax includes:

Mixing different proximity operators (e.g. W/n and PRE/n) in the same expression
Using wildcards or proximity operators with exact phrase searches
Placing AND NOT before other Boolean operators
Using wildcards on their own without any search terms

Ideal Search Structure

An ideal advanced search query should:

Use field codes to focus the search on the most relevant parts of documents
Combine related concepts using AND and OR
Exclude irrelevant terms with AND NOT at the end
Employ quotation marks and braces appropriately for phrase searching
Include wildcards to capture variations of key terms (while avoiding mixing them with other operators)
Follow the proper order of precedence for operators
Complex searches should be built up systematically, with parentheses to group related expressions as needed. The information from the provided documents on syntax rules and operators should be applied rigorously.

** Critical: all double quotes other than the outermost ones should be preceded by a backslash (\\") to escape them in the JSON format. Failure to do so will result in an error when parsing the JSON string. **

Example Advanced Searches

{
  "queries": [
    "TITLE-ABS-KEY((\\\"precision agriculture\\\" OR \\\"precision farming\\\") AND (\\\"machine learning\\\" OR \\\"AI\\\") AND \\\"water\\\")",
    "TITLE-ABS-KEY((iot OR \\\"internet of things\\\") AND (irrigation OR watering) AND sensor*)",
    "TITLE-ABS-Key((\\\"precision farming\\\" OR \\\"precision agriculture\\\") AND (\\\"deep learning\\\" OR \\\"neural networks\\\") AND \\\"water\\\")",
    "TITLE-ABS-KEY((crop W/5 monitor*) AND \\\"remote sensing\\\" AND (irrigation OR water*))",
    "TITLE(\\\"precision irrigation\\\" OR \\\"variable rate irrigation\\\" AND \\\"machine learning\\\")"
  ]
}
"""

OPENALEX_SEARCH_GUIDE = """
Syntax and Operators
Valid syntax for advanced alex search queries includes:
Using quotation marks %22%22 for exact phrase matches
Adding a minus sign - before terms to exclude them
Employing the OR operator in all caps to find pages containing either term
Using the site%3A operator to limit results to a specific website
Applying the filetype%3A operator to find specific file formats like PDF, DOC, etc.
Adding the * wildcard as a placeholder for unknown words

Invalid syntax includes:
Putting a plus sign + before words (alex stopped supporting this)
Using other special characters like %3F, %24, %26, %23, etc. within search terms
Explicitly using the AND operator (alex's default behavior makes it redundant)

Ideal Search Structure
An effective alex search query should:
Start with the most important search terms
Use specific, descriptive keywords related to irrigation scheduling, management, and precision irrigation
Utilize exact phrases in %22quotes%22 for specific word combinations
Exclude irrelevant terms using the - minus sign
Connect related terms or synonyms with OR
Apply the * wildcard strategically for flexibility

Note:

By following these guidelines and using proper URL encoding, you can construct effective and accurate search queries for alex.

Searches should be concise yet precise, following the syntax rules carefully. 

Example Searches
{
  "queries": [
    "https://api.openalex.org/works?search=%22precision+irrigation%22+%2B%22soil+moisture+sensors%22+%2B%22irrigation+scheduling%22&sort=relevance_score:desc&per-page=30",
    "https://api.openalex.org/works?search=%22machine+learning%22+%2B%22irrigation+management%22+%2B%22crop+water+demand+prediction%22&sort=relevance_score:desc&per-page=30",
    "https://api.openalex.org/works?search=%22IoT+sensors%22+%2B%22real-time%22+%2B%22soil+moisture+monitoring%22+%2B%22crop+water+stress%22&sort=relevance_score:desc&per-page=30",
    "https://api.openalex.org/works?search=%22remote+sensing%22+%2B%22vegetation+indices%22+%2B%22irrigation+scheduling%22&sort=relevance_score:desc&per-page=30",
    "https://api.openalex.org/works?search=%22wireless+sensor+networks%22+%2B%22precision+agriculture%22+%2B%22variable+rate+irrigation%22+%2B%22irrigation+automation%22&sort=relevance_score:desc&per-page=30"
  ]
}
"""

ARXIV_SEARCH_GUIDE = """
ArXiv uses natural language queries in the form of plain strings
Focus on purely natural language or minimal formatting.
ArXiv does not have a deeply complex advanced syntax like Scopus.
We simply want multiple variations or angles on the user's query
to capture different aspects of the topic.
"""

CORE_SEARCH_GUIDE = """
CORE allows a query param like 'title:(...) AND abstract:(...)' etc.
Similar to advanced boolean expressions.
We want multiple angles to discover relevant papers.
Use synonyms, phrases, parentheses, and boolean operators
to generate diverse queries for CORE.
"""

SEMANTIC_SCHOLAR_SEARCH_GUIDE = """
Semantic Scholar accepts natural language search queries.
Focus on creating comprehensive, information-rich queries
that capture the full context and intent of the research
question. Since Semantic Scholar uses advanced AI techniques
for search, rich and comprehensive queries work better than
multiple narrow ones.

Your queries should:
1. Include all key concepts from the original query
2. Add relevant synonyms or related terms
3. Specify important contextual details
4. Maintain focus on the core research question

Example natural language queries:
{
  "queries": [
    "The impact of climate change on agricultural productivity with a focus on drought resilience and adaptation strategies in developing countries",
    "Machine learning applications for precision agriculture focusing on crop yield prediction and disease detection using computer vision and sensor data",
    "Effectiveness of cognitive behavioral therapy compared to medication for treating anxiety disorders in adolescents based on longitudinal studies"
  ]
}
"""

GENERATE_QUERIES = """
You are an expert in academic literature search query formulation. Your task is to generate optimized search queries for academic databases to find research articles relevant to a user's research query.

User Research Query:
{QUERY}

Search Platform Guidance:
{SEARCH_GUIDANCE}

Number of Queries to Generate: {NUM_QUERIES}

Instructions:
1. Understand the User Research Query. Identify the core concepts, keywords, and nuances of the research topic.
2. Review the Search Platform Guidance. This guidance provides specific syntax, operators, and best practices for formulating effective queries on the target database platform (e.g., Scopus, OpenAlex, ArXiv, CORE, Semantic Scholar).
3. Generate {NUM_QUERIES} distinct search queries. Each query should represent a unique approach to searching for relevant articles. Consider variations in:
    - Keywords: Use synonyms, related terms, and broader or narrower concepts.
    - Phrase variations: Explore different phrasing and combinations of keywords.
    - Boolean operators: Strategically use AND, OR, NOT to refine search focus.
    - Field codes (if applicable): Utilize field codes (e.g., TITLE, ABS, KEY) as per the platform guidance to target specific document sections.
4. Ensure each generated query is syntactically correct and optimized for the specified Search Platform, adhering to the Search Platform Guidance.
5. Aim for diversity in the generated queries to comprehensively cover the research topic from multiple angles.
6. Output the queries as a JSON list of strings. If any query string contains double quotes, escape them with backslashes (\\").

Example JSON Output:
{{
  "queries": [
    "query variation 1",
    "query variation 2",
    "query variation 3",
    ...
  ]
}}

Generate {NUM_QUERIES} high-quality, diverse search queries that are optimized for academic literature databases and tailored to the Search Platform Guidance provided. Focus on creating queries that are precise, comprehensive, and effective in retrieving relevant research articles for the User Research Query.
"""

class QueryResponse(BaseModel):
    queries: List[str] = Field(..., description="List of generated search queries")

async def formulate_queries(user_query: str, num_queries: int, query_type: str) -> List[str]:
    """
    Generate search queries for a specific platform (scopus, openalex, arxiv, core, semantic_scholar).
    """
    if query_type.lower() == 'scopus':
        search_guidance = SCOPUS_SEARCH_GUIDE
    elif query_type.lower() == 'openalex':
        search_guidance = OPENALEX_SEARCH_GUIDE
    elif query_type.lower() == 'arxiv':
        search_guidance = ARXIV_SEARCH_GUIDE
    elif query_type.lower() == 'core':
        search_guidance = CORE_SEARCH_GUIDE
    elif query_type.lower() == 'semantic_scholar':
        search_guidance = SEMANTIC_SCHOLAR_SEARCH_GUIDE
    else:
        raise ValueError(f"Unsupported query type: {query_type}")

    prompt = GENERATE_QUERIES.format(
        QUERY=user_query,
        SEARCH_GUIDANCE=search_guidance,
        NUM_QUERIES=num_queries
    )

    result = await llm_handler.process(
        prompts=prompt,

        response_type=QueryResponse
    )

    if not result.success:
        logger.error(f"Failed to formulate queries: {result.error}")
        return []

    return result.data.queries