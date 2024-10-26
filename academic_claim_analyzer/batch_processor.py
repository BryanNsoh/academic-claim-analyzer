# academic_claim_analyzer/batch_processor.py

import asyncio
import json
import os
import logging
from datetime import datetime
from typing import List, Dict, Any
import yaml

from .debug_utils import debug_decorator, configure_logging

# Configure default logging
logger = logging.getLogger(__name__)

# Initialize with default configuration
configure_logging()

def analyze_claim(*args, **kwargs):
    from . import get_analyze_claim
    return get_analyze_claim()(*args, **kwargs)

def ClaimAnalysis(*args, **kwargs):
    from . import get_claim_analysis
    return get_claim_analysis()(*args, **kwargs)

async def process_claims(claims: List[str], **kwargs) -> Dict[str, Any]:
    results = {}
    for claim in claims:
        logger.info(f"Processing claim: {claim[:100]}...")
        try:
            analysis = await analyze_claim(claim, **kwargs)
            results[claim] = analysis
            logger.debug(f"Analysis result for claim '{claim[:100]}...': {str(analysis)[:100]}...")
        except Exception as e:
            logger.error(f"Error analyzing claim '{claim[:100]}...': {str(e)[:100]}", exc_info=True)
            results[claim] = {"error": str(e)[:100]}
    return results

def load_claims_from_yaml(yaml_file: str) -> List[Dict[str, Any]]:
    logger.info(f"Loading claims from YAML file: {yaml_file}")
    try:
        with open(yaml_file, 'r', encoding='utf-8') as f:
            claims_data = yaml.safe_load(f)
        if not claims_data:
            logger.warning("YAML file is empty or not properly formatted.")
        else:
            logger.info(f"Loaded {len(claims_data)} claim sets from YAML.")
        return claims_data
    except FileNotFoundError:
        logger.error(f"YAML file not found: {yaml_file}")
        raise
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML file: {str(e)[:100]}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error loading YAML file: {str(e)[:100]}", exc_info=True)
        raise

def batch_analyze_claims(claims_data: List[Dict[str, Any]], output_dir: str, num_queries: int = 5, 
                        papers_per_query: int = 5, num_papers_to_return: int = 3, 
                        log_level: str = 'INFO', **kwargs) -> None:
    """
    Add log_level parameter to control verbosity
    """
    # Reconfigure logging with specified level
    configure_logging(
        log_file=os.path.join(output_dir, 'batch_process.log'),
        console_level=log_level
    )
    
    logger.info("Starting batch analysis of claims.")
    
    # Ensure the output directory exists
    try:
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"Output directory verified/created: {output_dir}")
    except Exception as e:
        logger.error(f"Failed to create or access output directory '{output_dir}': {str(e)[:100]}", exc_info=True)
        raise

    for claim_set in claims_data:
        claim_set_id = claim_set.get('claim_set_id', 'default_set')
        claims = claim_set.get('claims', [])
        
        if not claims:
            logger.warning(f"No claims found in claim set '{claim_set_id}'. Skipping.")
            continue
        
        logger.info(f"Processing claim set '{claim_set_id}' with {len(claims)} claims.")
        
        try:
            results = asyncio.run(process_claims(claims, num_queries=num_queries, papers_per_query=papers_per_query, num_papers_to_return=num_papers_to_return))
        except Exception as e:
            logger.error(f"Failed to process claim set '{claim_set_id}': {str(e)[:100]}", exc_info=True)
            continue
        
        # Generate a timestamp for the filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{claim_set_id}_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)
        
        try:
            # Serialize the results to JSON by converting ClaimAnalysis objects to dicts
            serializable_results = {claim[:100]: analysis.to_dict() for claim, analysis in results.items()}
            
            # **Handle datetime objects by converting them to ISO-formatted strings**
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(serializable_results, f, ensure_ascii=False, indent=2, default=str)  # Added default=str
            logger.info(f"Results for claim set '{claim_set_id}' stored in: {filepath}")
        except Exception as e:
            logger.error(f"Failed to write results to file '{filepath}': {str(e)[:100]}", exc_info=True)

def print_results_summary(results: Dict[str, Any]) -> None:
    logger.info("\nResults Summary:")
    for claim, analysis in results.items():
        if isinstance(analysis, dict) and "error" in analysis:
            logger.warning(f"Claim: {claim[:100]}...\nError: {analysis['error'][:100]}...\n")
        else:
            logger.info(f"\nClaim: {claim[:100]}...\nNumber of top papers: {len(analysis.get_top_papers(1))}")

def print_detailed_result(claim: str, papers: List[Dict[str, Any]], verbose: bool = False) -> None:
    if not verbose:
        logger.info(f"\nClaim: {claim[:100]}...")
        logger.info(f"Number of papers: {len(papers)}")
        return
        
    # Rest of the detailed printing only happens if verbose=True
    logger.info("\nDetailed Result for Claim:")
    logger.info(f"Claim: {claim[:100]}...")
    logger.info(f"\nTop ranked papers:")
    for paper in papers:
        logger.info(f"\nTitle: {paper['title'][:100]}...")
        logger.info(f"Authors: {', '.join(paper['authors'])[:100]}...")
        logger.info(f"Year: {paper['year']}")
        logger.info(f"DOI: {paper['doi'][:100]}...")
        logger.info(f"Relevance Score: {paper['relevance_score']}")
        logger.info(f"Analysis: {paper['analysis'][:100]}...")
        logger.info("Relevant Quotes:")
        for quote in paper['relevant_quotes']:
            logger.info(f"- {quote[:100]}...")
        logger.info("BibTeX:")
        logger.info(f"{paper['bibtex'][:100]}...")

def print_schema(results: Dict[str, Any]) -> None:
    try:
        sample_paper = next(iter(results.values()))['top_papers'][0]
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
        logger.info("\nSchema of result object:")
        logger.info(json.dumps(schema, indent=2))
    except StopIteration:
        logger.warning("No papers available to generate schema.")
    except Exception as e:
        logger.error(f"Error generating schema: {str(e)[:100]}", exc_info=True)


def main():
    logger.info("Batch Processor started.")
    yaml_file = r"C:\Users\bnsoh2\OneDrive - University of Nebraska-Lincoln\Documents\Projects\ACADEMIC LITERATURE UTILITIES\academic-claim-analyzer\batch_test\test_yaml.yaml"
    output_dir = r"C:\Users\bnsoh2\OneDrive - University of Nebraska-Lincoln\Documents\Projects\ACADEMIC LITERATURE UTILITIES\academic-claim-analyzer\batch_test"
    
    try:
        claims_data = load_claims_from_yaml(yaml_file)
        if not claims_data:
            logger.warning("No claim sets to process. Exiting.")
            return
        batch_analyze_claims(claims_data, output_dir, num_queries=2, papers_per_query=2, num_papers_to_return=1, log_level='INFO')
    except Exception as e:
        logger.critical(f"Batch Processor encountered a critical error: {str(e)[:100]}", exc_info=True)
    finally:
        logger.info("Batch Processor finished execution.")

if __name__ == "__main__":
    main()
