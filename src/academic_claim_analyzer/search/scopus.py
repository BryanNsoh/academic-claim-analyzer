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

[
"TITLE-ABS-KEY(("precision agriculture" OR "precision farming") AND ("machine learning" OR "AI") AND "water")",
"TITLE-ABS-KEY((iot OR \"internet of things\") AND (irrigation OR watering) AND sensor*)",
"TITLE-ABS-Key((\"precision farming\" OR \"precision agriculture\") AND (\"deep learning\" OR \"neural networks\") AND \"water\")",
"TITLE-ABS-KEY((crop W/5 monitor*) AND \"remote sensing\" AND (irrigation OR water*))",
"TITLE(\"precision irrigation\" OR \"variable rate irrigation\" AND \"machine learning\")"
]


** Critical: all double quotes other than the outermost ones should be preceded by a backslash (") to escape them in the JSON format. Failure to do so will result in an error when parsing the JSON string. **. 

These example searches demonstrate different ways to effectively combine key concepts related to precision agriculture, irrigation, real-time monitoring, IoT, machine learning and related topics using advanced search operators. They make use of field codes, Boolean and proximity operators, phrase searching, and wildcards to construct targeted, comprehensive searches to surface the most relevant research. The topic focus is achieved through carefully chosen search terms covering the desired themes.
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