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
{ "alex_queries": [
"https://api.openalex.org/works?search=%22precision+irrigation%22+%2B%22soil+moisture+sensors%22+%2B%22irrigation+scheduling%22&sort=relevance_score:desc&per-page=30",
"https://api.openalex.org/works?search=%22machine+learning%22+%2B%22irrigation+management%22+%2B%22crop+water+demand+prediction%22&sort=relevance_score:desc&per-page=30",
"https://api.openalex.org/works?search=%22IoT+sensors%22+%2B%22real-time%22+%2B%22soil+moisture+monitoring%22+%2B%22crop+water+stress%22&sort=relevance_score:desc&per-page=30",
"https://api.openalex.org/works?search=%22remote+sensing%22+%2B%22vegetation+indices%22+%2B%22irrigation+scheduling%22&sort=relevance_score:desc&per-page=30",
"https://api.openalex.org/works?search=%22wireless+sensor+networks%22+%2B%22precision+agriculture%22+%2B%22variable+rate+irrigation%22+%2B%22irrigation+automation%22&sort=relevance_score:desc&per-page=30"
}

These example searches demonstrate how to create targeted, effective alex searches. They focus on specific topics, exclude irrelevant results, allow synonym flexibility, and limit to relevant domains when needed. The search terms are carefully selected to balance relevance and specificity while avoiding being overly restrictive.  By combining relevant keywords, exact phrases, and operators, these searches help generate high-quality results for the given topics.
"""

GENERATE_QUERIES = """
You are tasked with generating optimized search queries to find relevant research articles addressing a specific point. Follow these instructions carefully:

1. Review the following point that needs to be addressed by the literature search:
<point_content>
{{POINT_CONTENT}}
</point_content>

2. Consider the following search guidance:
<search_guidance>
{{SEARCH_GUIDANCE}}
</search_guidance>

3. Generate {{NUM_QUERIES}} highly optimized search queries that would surface the most relevant, insightful, and comprehensive set of research articles to shed light on various aspects of the given point. Your queries should:

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

Replace query_1, query_2, etc. with your actual search queries. The number of queries should match {{NUM_QUERIES}}.

5. If the search guidance specifies a particular platform (e.g., Scopus, Web of Science), ensure your queries are formatted appropriately for that platform.

6. Important: If your queries contain quotation marks, ensure they are properly escaped with a backslash (\") to maintain valid list formatting.

Generate the list of search queries now, following the instructions above.
"""


