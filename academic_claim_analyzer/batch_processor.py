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

class BatchProcessorConfig:
    """Configuration container for batch processing settings."""
    def __init__(self, config_data: Dict[str, Any]):
        # Processing settings
        processing = config_data.get('processing', {})
        self.num_queries = processing.get('num_queries', 5)
        self.papers_per_query = processing.get('papers_per_query', 5)
        self.num_papers_to_return = processing.get('num_papers_to_return', 3)
        
        # Logging settings
        logging_config = config_data.get('logging', {})
        self.log_level = logging_config.get('level', 'INFO')
        
        # Search settings
        search = config_data.get('search', {})
        self.search_platforms = search.get('platforms', ['openalex', 'scopus', 'core'])
        self.min_year = search.get('min_year', None)
        self.max_year = search.get('max_year', None)

def load_batch_config(yaml_file: str) -> BatchProcessorConfig:
    """Load batch processing configuration from YAML file."""
    try:
        with open(yaml_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            
        # Look for global configuration section
        config_data = {}
        if isinstance(data, list):
            # Check first item for global config
            if data and isinstance(data[0], dict):
                config_data = data[0].get('config', {})
        elif isinstance(data, dict):
            config_data = data.get('config', {})
            
        return BatchProcessorConfig(config_data)
        
    except Exception as e:
        logger.error(f"Error loading batch configuration: {str(e)}")
        # Return default configuration
        return BatchProcessorConfig({})

def load_claims_from_yaml(yaml_file: str) -> List[Dict[str, Any]]:
    """Load claims and their associated configurations from YAML file."""
    logger.info(f"Loading claims from YAML file: {yaml_file}")
    try:
        with open(yaml_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            
        claims_data = []
        if isinstance(data, list):
            claims_data = [item for item in data if 'claim' in item]
        elif isinstance(data, dict):
            if 'claim' in data:
                claims_data = [data]
            elif 'claims' in data:
                claims_data = data['claims']
                
        if not claims_data:
            logger.warning("No valid claims found in YAML file.")
            
        return claims_data
        
    except Exception as e:
        logger.error(f"Error loading claims from YAML: {str(e)}")
        raise

async def process_claims(claims_data: List[Dict[str, Any]], config: BatchProcessorConfig) -> Dict[str, Any]:
    """Process a list of claims using the provided configuration."""
    results = {}
    
    if not isinstance(claims_data, list):
        logger.error("Claims data must be a list")
        return results
        
    for claim_data in claims_data:
        if not isinstance(claim_data, dict):
            logger.warning(f"Skipping invalid claim data format: {type(claim_data)}")
            continue
            
        claim_text = claim_data.get('claim')
        if not claim_text:
            logger.warning("No 'claim' found in claim data. Skipping.")
            continue
            
        exclusion_criteria = claim_data.get('exclusion_criteria')
        extraction_schema = claim_data.get('information_extraction')
        
        # Apply any claim-specific overrides
        claim_config = claim_data.get('config', {})
        num_queries = claim_config.get('num_queries', config.num_queries)
        papers_per_query = claim_config.get('papers_per_query', config.papers_per_query)
        num_papers = claim_config.get('num_papers_to_return', config.num_papers_to_return)

        logger.info(f"Processing claim: {claim_text[:100]}...")
        
        try:
            # Process the claim
            analysis = await analyze_claim(
                claim=claim_text,
                exclusion_criteria=exclusion_criteria,
                extraction_schema=extraction_schema,
                num_queries=num_queries,
                papers_per_query=papers_per_query,
                num_papers_to_return=num_papers
            )
            
            if isinstance(analysis, ClaimAnalysis):
                results[claim_text] = analysis.to_dict()
            else:
                results[claim_text] = analysis
                
        except Exception as e:
            logger.error(f"Error analyzing claim '{claim_text[:100]}...': {str(e)}", exc_info=True)
            results[claim_text] = {"error": str(e)}
            
    return results

def extract_concise_results(full_results: Dict[str, Any], num_papers: int) -> Dict[str, Any]:
    """Extract the essential analysis results from the full analysis, keeping only top N papers."""
    concise_results = {}
    
    for claim, result in full_results.items():
        if isinstance(result, dict):
            # Sort papers by relevance score and take top N
            ranked_papers = result.get('ranked_papers', [])
            sorted_papers = sorted(
                ranked_papers,
                key=lambda x: x.get('relevance_score', 0),
                reverse=True
            )[:num_papers]
            
            concise_papers = []
            for paper in sorted_papers:
                concise_paper = {
                    'title': paper.get('title', ''),
                    'authors': paper.get('authors', []),
                    'year': paper.get('year'),
                    'bibtex': paper.get('bibtex', ''),
                    'relevant_quotes': paper.get('relevant_quotes', []),
                    'analysis': paper.get('analysis', ''),
                    'exclusion_criteria_result': paper.get('exclusion_criteria_result', {}),
                    'extraction_result': paper.get('extraction_result', {}),
                    'relevance_score': paper.get('relevance_score')
                }
                concise_papers.append(concise_paper)
                
            concise_results[claim] = {
                'ranked_papers': concise_papers,
                'num_total_papers': len(ranked_papers)
            }
            
    return concise_results

def sanitize_filename(name: str) -> str:
    """Convert a string into a valid filename."""
    import re
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'[\s_]+', '_', name)
    name = name.strip('. ')
    return name if name else 'unnamed_claim'

def batch_analyze_claims(yaml_file: str) -> None:
    """Process multiple claims in batch using configuration from YAML file."""
    try:
        # Get YAML directory and create output folder
        yaml_dir = os.path.dirname(os.path.abspath(yaml_file))
        yaml_name = os.path.splitext(os.path.basename(yaml_file))[0]
        output_dir = os.path.join(yaml_dir, f"{yaml_name}_results")
        os.makedirs(output_dir, exist_ok=True)
        
        # Load configuration
        config = load_batch_config(yaml_file)
        
        # Configure logging
        configure_logging(
            log_file=os.path.join(output_dir, 'batch_process.log'),
            console_level=config.log_level
        )
        
        logger.info("Starting batch analysis of claims.")
        logger.info(f"Results will be saved in: {output_dir}")
        
        claims_data = load_claims_from_yaml(yaml_file)
        if not claims_data:
            logger.warning("No claims to process. Exiting.")
            return
            
        results = asyncio.run(process_claims(claims_data, config))
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Process each claim's results
        for claim_data in claims_data:
            claim_text = claim_data.get('claim', '')
            if not claim_text:
                continue
                
            # Get claim identifier
            claim_id = claim_data.get('id', '')
            if not claim_id:
                claim_id = sanitize_filename(' '.join(claim_text.split()[:5]))
            
            # Get number of papers to return for concise results
            claim_config = claim_data.get('config', {})
            num_papers = claim_config.get('num_papers_to_return', 
                                        config.num_papers_to_return)
            
            # Extract this claim's results
            claim_results = {claim_text: results[claim_text]} if claim_text in results else {}
            concise_results = extract_concise_results(claim_results, num_papers)
            
            # Generate filenames with claim ID
            base_filename = f"{claim_id}_{timestamp}"
            
            # Save results
            with open(os.path.join(output_dir, f"{base_filename}_full.json"), 'w', encoding='utf-8') as f:
                json.dump(claim_results, f, ensure_ascii=False, indent=2, default=str)
            
            with open(os.path.join(output_dir, f"{base_filename}.json"), 'w', encoding='utf-8') as f:
                json.dump(concise_results, f, ensure_ascii=False, indent=2, default=str)
                
            logger.info(f"Saved results for claim '{claim_id}'")
        
    except Exception as e:
        logger.error(f"Batch processing failed: {str(e)}", exc_info=True)
    finally:
        logger.info("Batch processing completed.")


if __name__ == "__main__":
    batch_analyze_claims(r"C:\Users\bnsoh2\OneDrive - University of Nebraska-Lincoln\Documents\Projects\ACADEMIC LITERATURE UTILITIES\academic-claim-analyzer\reviewer_run\all_comments.yaml")