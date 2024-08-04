# academic_claim_analyzer/batch_processor.py

import asyncio
import json
import os
from datetime import datetime
from typing import List, Dict, Any
from .main import analyze_claim
from .models import ClaimAnalysis, RankedPaper

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

def batch_analyze_claims(claims: List[str], output_dir: str, num_top_papers: int = 5, **kwargs) -> Dict[str, List[Dict[str, Any]]]:
    results = asyncio.run(process_claims(claims, **kwargs))
    
    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate a timestamp for the filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"claim_analysis_results_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)
    
    # Process and serialize the results
    processed_results = {}
    for claim, analysis in results.items():
        top_papers = analysis.get_top_papers(num_top_papers)
        processed_results[claim] = [
            {
                "title": paper.title,
                "authors": paper.authors,
                "year": paper.year,
                "doi": paper.doi,
                "relevance_score": paper.relevance_score,
                "relevant_quotes": paper.relevant_quotes,
                "analysis": paper.analysis,
                "bibtex": paper.bibtex
            }
            for paper in top_papers
        ]
    
    # Write the results to a JSON file
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(processed_results, f, ensure_ascii=False, indent=2)
    
    print(f"Results stored in: {filepath}")
    
    return processed_results

def print_results_summary(results: Dict[str, List[Dict[str, Any]]]):
    print("\nResults Summary:")
    for claim, papers in results.items():
        print(f"\nClaim: {claim}")
        print(f"Number of top papers: {len(papers)}")

def print_detailed_result(claim: str, papers: List[Dict[str, Any]]):
    print("\nDetailed Result for Claim:")
    print(f"Claim: {claim}")
    print(f"\nTop ranked papers:")
    for paper in papers:
        print(f"\nTitle: {paper['title']}")
        print(f"Authors: {', '.join(paper['authors'])}")
        print(f"Year: {paper['year']}")
        print(f"DOI: {paper['doi']}")
        print(f"Relevance Score: {paper['relevance_score']}")
        print(f"Analysis: {paper['analysis']}")
        print("Relevant Quotes:")
        for quote in paper['relevant_quotes']:
            print(f"- {quote}")
        print("BibTeX:")
        print(paper['bibtex'])

def print_schema(results: Dict[str, List[Dict[str, Any]]]):
    sample_paper = next(iter(results.values()))[0]
    schema = {
        "claim": "string",
        "papers": [
            {
                "title": "string",
                "authors": ["string"],
                "year": "int",
                "doi": "string",
                "relevance_score": "float",
                "relevant_quotes": ["string"],
                "analysis": "string",
                "bibtex": "string"
            }
        ]
    }
    print("\nSchema of result object:")
    print(json.dumps(schema, indent=2))

def main():
    claims = [
        "Coffee consumption is associated with reduced risk of type 2 diabetes.",
        "Regular exercise can lower the risk of cardiovascular disease.",
        "Mindfulness meditation may help reduce symptoms of anxiety and depression.",
    ]

    results = batch_analyze_claims(claims, output_dir=r"C:\Users\bnsoh2\Desktop\test", num_queries=2, papers_per_query=3, num_top_papers=2)

    print_results_summary(results)
    first_claim = next(iter(results))
    print_detailed_result(first_claim, results[first_claim])
    print_schema(results)

if __name__ == "__main__":
    main()