# academic_claim_analyzer/batch_processor.py

import asyncio
import json
import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
import yaml

from .debug_utils import configure_logging
from .models import ClaimAnalysis

logger = logging.getLogger(__name__)

# Initialize with default configuration
configure_logging()

def analyze_claim(*args, **kwargs):
    from . import get_analyze_claim
    return get_analyze_claim()(*args, **kwargs)

def load_claims_from_yaml(yaml_file: str) -> List[Dict[str, Any]]:
    logger.info(f"Loading claims from YAML file: {yaml_file}")
    try:
        with open(yaml_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            
        # Ensure we have a list of dictionaries
        if isinstance(data, list):
            claims_data = data
        elif isinstance(data, dict):
            claims_data = [data]  # Convert single dict to list
        else:
            logger.warning("YAML file structure not recognized. Expected list or dict.")
            claims_data = []

        if not claims_data:
            logger.warning("YAML file is empty or not properly formatted.")
        else:
            logger.info(f"Loaded {len(claims_data)} claims from YAML.")
            
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

async def process_claims(claims_data: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
    """Process a list of claims with improved error handling."""
    results = {}
    
    if not isinstance(claims_data, list):
        logger.error("Claims data must be a list")
        return results
        
    for claim_data in claims_data:
        if not isinstance(claim_data, dict):
            logger.warning(f"Skipping invalid claim data format: {type(claim_data)}")
            continue
            
        # Handle both possible formats - direct string or dict with 'claim' key
        if isinstance(claim_data, str):
            claim_text = claim_data
            exclusion_criteria = None
            extraction_schema = None
        else:
            claim_text = claim_data.get('claim')
            if not claim_text:
                logger.warning("No 'claim' found in claim data. Skipping.")
                continue
            exclusion_criteria = claim_data.get('exclusion_criteria')
            extraction_schema = claim_data.get('information_extraction')

        logger.info(f"Processing claim: {claim_text[:100]}...")
        
        try:
            # Process the claim
            analysis = await analyze_claim(
                claim=claim_text,
                exclusion_criteria=exclusion_criteria,
                extraction_schema=extraction_schema,
                **kwargs
            )
            
            # Convert ClaimAnalysis object to dict if necessary
            if isinstance(analysis, ClaimAnalysis):
                results[claim_text] = analysis.to_dict()
            else:
                results[claim_text] = analysis
                
            logger.debug(f"Analysis result for claim '{claim_text[:100]}...': {str(analysis)[:100]}...")
            
        except Exception as e:
            logger.error(f"Error analyzing claim '{claim_text[:100]}...': {str(e)}", exc_info=True)
            results[claim_text] = {"error": str(e)}
            
    return results

def batch_analyze_claims(claims_data: List[Dict[str, Any]], output_dir: str, num_queries: int = 5, 
                        papers_per_query: int = 5, num_papers_to_return: int = 3, 
                        log_level: str = 'INFO', **kwargs) -> None:
    """
    Process multiple claims in batch with improved error handling.
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
        logger.error(f"Failed to create or access output directory '{output_dir}': {str(e)}")
        raise

    try:
        results = asyncio.run(process_claims(
            claims_data,
            num_queries=num_queries,
            papers_per_query=papers_per_query,
            num_papers_to_return=num_papers_to_return,
            **kwargs
        ))
    except Exception as e:
        logger.error(f"Failed to process claims: {str(e)}", exc_info=True)
        return

    # Generate timestamp for the filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"analysis_results_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"Results stored in: {filepath}")
    except Exception as e:
        logger.error(f"Failed to write results to file '{filepath}': {str(e)}", exc_info=True)

def main():
    logger.info("Batch Processor started.")
    yaml_file = r"C:\Users\bnsoh2\OneDrive - University of Nebraska-Lincoln\Documents\Projects\ACADEMIC LITERATURE UTILITIES\academic-claim-analyzer\batch_test\test_yaml.yaml"
    output_dir = r"C:\Users\bnsoh2\OneDrive - University of Nebraska-Lincoln\Documents\Projects\ACADEMIC LITERATURE UTILITIES\academic-claim-analyzer\batch_test"
    
    try:
        claims_data = load_claims_from_yaml(yaml_file)
        if not claims_data:
            logger.warning("No claims to process. Exiting.")
            return
            
        batch_analyze_claims(
            claims_data,
            output_dir,
            num_queries=2,
            papers_per_query=2,
            num_papers_to_return=1,
            log_level='INFO'
        )
        
    except Exception as e:
        logger.critical(f"Batch Processor encountered a critical error: {str(e)}", exc_info=True)
    finally:
        logger.info("Batch Processor finished execution.")

if __name__ == "__main__":
    main()