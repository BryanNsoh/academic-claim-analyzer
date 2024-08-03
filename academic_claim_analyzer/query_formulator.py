# src/academic_claim_analyzer/query_formulator.py

from typing import List
import json
from async_llm_handler import Handler

SCOPUS_SEARCH_GUIDE = """
Syntax and Operators

Valid syntax for advanced search queries includes:

Field codes (e.g. TITLE, ABS, KEY, AUTH, AFFIL) to restrict searches to specific parts of documents
Boolean operators (AND, OR, AND NOT) to combine search terms
Proximity operators (W/n, PRE/n) to find words within a specified distance - W/n: Finds terms within "n" words of each other, regardless of order. Example: journal W/15 publishing finds articles where "journal" and "publishing" are within two words of each other. - PRE/n: Finds terms in the specified order and within "n" words of each other. Example: data PRE/50 analysis finds articles where "data" appears before "analysis" within three words. - To find terms in the same sentence, use 15. To find terms in the same paragraph, use 50 -
Quotation marks for loose/approximate phrase searches
Braces {} for exact phrase searches
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

** Critical: all double quotes other than the outermost ones should be preceded by a backslash (") to escape them in the JSON format. Failure to do so will result in an error when parsing the JSON string. **

Example Advanced Searches

{
  "queries": [
    "TITLE-ABS-KEY((\"precision agriculture\" OR \"precision farming\") AND (\"machine learning\" OR \"AI\") AND \"water\")",
    "TITLE-ABS-KEY((iot OR \"internet of things\") AND (irrigation OR watering) AND sensor*)",
    "TITLE-ABS-Key((\"precision farming\" OR \"precision agriculture\") AND (\"deep learning\" OR \"neural networks\") AND \"water\")",
    "TITLE-ABS-KEY((crop W/5 monitor*) AND \"remote sensing\" AND (irrigation OR water*))",
    "TITLE(\"precision irrigation\" OR \"variable rate irrigation\" AND \"machine learning\")"
  ]
}


** Critical: all double quotes other than the outermost ones should be preceded by a backslash (") to escape them in the JSON format. Failure to do so will result in an error when parsing the JSON string. **. 

These example searches demonstrate different ways to effectively combine key concepts related to precision agriculture, irrigation, real-time monitoring, IoT, machine learning and related topics using advanced search operators. They make use of field codes, Boolean and proximity operators, phrase searching, and wildcards to construct targeted, comprehensive searches to surface the most relevant research. The topic focus is achieved through carefully chosen search terms covering the desired themes.
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
`
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

These example searches demonstrate how to create targeted, effective alex searches. They focus on specific topics, exclude irrelevant results, allow synonym flexibility, and limit to relevant domains when needed. The search terms are carefully selected to balance relevance and specificity while avoiding being overly restrictive.  By combining relevant keywords, exact phrases, and operators, these searches help generate high-quality results for the given topics.
"""

GENERATE_QUERIES = """
You are tasked with generating optimized search queries to find relevant research articles addressing a specific point. Follow these instructions carefully:

1. Review the following claim that needs to be addressed by the literature search:
<claim>
{CLAIM}
</claim>

2. Consider the following search guidance:
<search_guidance>
{SEARCH_GUIDANCE}
</search_guidance>

3. Generate {NUM_QUERIES} highly optimized search queries that would surface the most relevant, insightful, and comprehensive set of research articles to shed light on various aspects of the given point. Your queries should:

- Directly address the key issues and nuances of the point content
- Demonstrate creativity and variety to capture different dimensions of the topic
- Use precise terminology and logical operators for high-quality results
- Cover a broad range of potential subtopics, perspectives, and article types related to the point
- Strictly adhere to any specific requirements provided in the search guidance

4. Provide your response as a list of strings in the following format:

[
  "query_1",
  "query_2",
  "query_3",
  ...
]

Replace query_1, query_2, etc. with your actual search queries. The number of queries should match {NUM_QUERIES}.

5. If the search guidance specifies a particular platform (e.g., Scopus, Web of Science), ensure your queries are formatted appropriately for that platform.

6. Important: If your queries contain quotation marks, ensure they are properly escaped with a backslash (\") to maintain valid list formatting.

Generate the list of search queries now, following the instructions above.
"""




async def formulate_queries(claim: str, num_queries: int, query_type: str) -> List[str]:
    """
    Generate search queries based on the given claim.

    Args:
        claim (str): The claim to generate queries for.
        num_queries (int): The number of queries to generate.
        query_type (str): The type of query to generate ('scopus' or 'openalex').

    Returns:
        List[str]: A list of generated search queries.
    """
    handler = Handler()

    if query_type.lower() == 'scopus':
        search_guidance = SCOPUS_SEARCH_GUIDE
    elif query_type.lower() == 'openalex':
        search_guidance = OPENALEX_SEARCH_GUIDE
    else:
        raise ValueError(f"Unsupported query type: {query_type}")

    prompt = GENERATE_QUERIES.format(
        CLAIM=claim,
        SEARCH_GUIDANCE=search_guidance,
        NUM_QUERIES=num_queries,
        QUERY_TYPE=query_type
    )

    response = await handler.query(prompt, model="gpt_4o_mini", json_mode=True)
    
    if isinstance(response, str):
        try:
            parsed_response = json.loads(response)
        except json.JSONDecodeError:
            raise ValueError("Failed to parse LLM response as JSON")
    elif isinstance(response, dict):
        parsed_response = response
    else:
        raise ValueError("Unexpected response format from LLM")

    if "queries" not in parsed_response or not isinstance(parsed_response["queries"], list):
        raise ValueError("Invalid response format: 'queries' list not found")

    queries = parsed_response["queries"]
    print(queries)  

    if len(queries) != num_queries:
        raise ValueError(f"Expected {num_queries} queries, but got {len(queries)}")

    return queries