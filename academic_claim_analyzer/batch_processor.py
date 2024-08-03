# academic_claim_analyzer/batch_processor.py

import asyncio
import json
import os
from datetime import datetime
from typing import List, Dict
from .main import analyze_claim
from .models import ClaimAnalysis

async def process_claims(claims: List[str], **kwargs) -> Dict[str, ClaimAnalysis]:
    results = {}
    for claim in claims:
        try:
            analysis = await analyze_claim(claim, **kwargs)
            results[claim] = analysis
        except Exception as e:
            print(f"Error analyzing claim: {claim}")
            print(f"Error details: {str(e)}")
    return results

def batch_analyze_claims(claims: List[str], output_dir: str, **kwargs) -> Dict[str, ClaimAnalysis]:
    results = asyncio.run(process_claims(claims, **kwargs))
    
    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate a timestamp for the filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"claim_analysis_results_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)
    
    # Serialize the results to JSON
    serialized_results = {}
    for claim, analysis in results.items():
        serialized_results[claim] = analysis.to_dict()  # Assume ClaimAnalysis has a to_dict method
    
    # Write the results to a JSON file
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(serialized_results, f, ensure_ascii=False, indent=2)
    
    print(f"Results stored in: {filepath}")
    
    return results

def print_results_summary(results: Dict[str, ClaimAnalysis]):
    print("\nResults Summary:")
    for claim, analysis in results.items():
        print(f"\nClaim: {claim}")
        print(f"Number of queries generated: {len(analysis.queries)}")
        print(f"Total papers found: {len(analysis.search_results)}")
        print(f"Number of ranked papers: {len(analysis.ranked_papers)}")

def print_detailed_result(claim: str, analysis: ClaimAnalysis):
    print("\nDetailed Result for Claim:")
    print(f"Claim: {claim}")
    print(f"\nQueries generated:")
    for query in analysis.queries:
        print(f"- {query}")
    print(f"\nTop ranked papers:")
    for paper in analysis.get_top_papers(analysis.parameters["num_papers_to_return"]):
        print(f"\nTitle: {paper.title}")
        print(f"Authors: {', '.join(paper.authors)}")
        print(f"Year: {paper.year}")
        print(f"DOI: {paper.doi}")
        print(f"Relevance Score: {paper.relevance_score}")
        print(f"Analysis: {paper.analysis}")
        print("Relevant Quotes:")
        for quote in paper.relevant_quotes:
            print(f"- {quote}")

def print_schema(results: Dict[str, ClaimAnalysis]):
    sample_analysis = next(iter(results.values()))
    schema = {
        "claim": "string",
        "queries": ["string"],
        "search_results": [
            {
                "title": "string",
                "authors": ["string"],
                "year": "int",
                "doi": "string",
                "abstract": "string",
                "source": "string",
                "full_text": "string (optional)",
                "pdf_link": "string (optional)",
                "metadata": {
                    "key": "value"
                }
            }
        ],
        "ranked_papers": [
            {
                "title": "string",
                "authors": ["string"],
                "year": "int",
                "doi": "string",
                "abstract": "string",
                "source": "string",
                "full_text": "string (optional)",
                "pdf_link": "string (optional)",
                "metadata": {
                    "key": "value"
                },
                "relevance_score": "float",
                "relevant_quotes": ["string"],
                "analysis": "string"
            }
        ],
        "parameters": sample_analysis.parameters
    }
    print("\nSchema of ClaimAnalysis object:")
    print(json.dumps(schema, indent=2))

def main():
    claims = [
        "Coffee consumption is associated with reduced risk of type 2 diabetes.",
        "Regular exercise can lower the risk of cardiovascular disease.",
        "Mindfulness meditation may help reduce symptoms of anxiety and depression.",
    ]

    results = batch_analyze_claims(claims, output_dir=r"C:\Users\bnsoh2\Desktop\test", num_queries=2, papers_per_query=3, num_papers_to_return=2)

    print_results_summary(results)
    first_claim = next(iter(results))
    print_detailed_result(first_claim, results[first_claim])
    print_schema(results)

if __name__ == "__main__":
    main()