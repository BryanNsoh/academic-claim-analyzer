# Batch Processing Guide: Analyzing Multiple Academic Claims

## Overview

The batch processor allows you to analyze multiple academic claims simultaneously, providing comprehensive evidence gathering and analysis. For each claim, you can specify:
- Exclusion criteria to systematically filter out irrelevant papers
- Information extraction schemas to pull structured data from relevant papers
- Claim-specific processing parameters

The system will:
1. Generate optimized search queries across academic databases
2. Retrieve and analyze relevant papers
3. Apply your exclusion criteria if specified
4. Extract structured information if requested
5. Rank papers by relevance to the claim
6. Provide both detailed and concise analysis outputs

## Basic Usage

```python
from academic_claim_analyzer import batch_analyze_claims

# Process claims from a YAML file
batch_analyze_claims("path/to/claims.yaml")
```

Results will be automatically organized in a folder named after your YAML file (e.g., `claims_results/`) in the same directory as your YAML file.

## YAML Structure

Your YAML file should contain:
1. Global configuration for processing parameters
2. One or more claims with their associated criteria and schemas

### 1. Global Configuration
```yaml
config:
  processing:
    num_queries: 5         # Number of search queries per claim
    papers_per_query: 7    # Papers to retrieve per query
    num_papers_to_return: 3  # Top papers to include in concise results
  
  logging:
    level: INFO           # Logging detail level (INFO, DEBUG, WARNING, ERROR)
  
  search:
    platforms:           # Search platforms to use
      - openalex
      - scopus
      - core
    min_year: 2010      # Optional year filtering
    max_year: 2024
```

### 2. Simple Claim
```yaml
claims:
  - id: basic_claim      # Optional identifier for result files
    claim: "Machine learning improves crop yield predictions"
```

### 3. Claim with Exclusion Criteria
```yaml
claims:
  - id: ml_yield
    claim: "Machine learning improves crop yield predictions"
    exclusion_criteria:
      no_empirical:
        type: boolean
        description: "Paper contains no empirical evaluation"
      insufficient_data:
        type: boolean
        description: "Study uses less than one year of data"
```

The exclusion criteria are used to filter out papers. Any paper matching ANY of the criteria is excluded. Each criterion must:
- Use a descriptive key (e.g., 'no_empirical')
- Be of type boolean
- Include a clear description of what constitutes exclusion
- Be objectively evaluable from paper content

### 4. Claim with Information Extraction
```yaml
claims:
  - id: ml_yield
    claim: "Machine learning improves crop yield predictions"
    information_extraction:
      accuracy:
        type: float
        description: "Model prediction accuracy in percentage"
      methods_used:
        type: list
        description: "List of machine learning methods used"
      dataset_size:
        type: integer
        description: "Number of samples in dataset"
      includes_uncertainty:
        type: boolean
        description: "Whether uncertainty estimates are provided"
      limitations:
        type: string
        description: "Key limitations of the study"
```

Valid field types for extraction:
- `string`: Textual content without specific structure
- `float`: Decimal numbers (e.g., accuracies, measurements)
- `integer`: Whole numbers (e.g., counts, years)
- `boolean`: True/false values for binary characteristics
- `list`: Arrays of values (e.g., methods used, factors considered)

### 5. Complete Example with All Features
```yaml
config:
  processing:
    num_queries: 5
    papers_per_query: 7
    num_papers_to_return: 3
  
  logging:
    level: INFO
  
  search:
    platforms:
      - openalex
      - scopus
      - core
    min_year: 2010
    max_year: 2024

claims:
  - id: deep_learning_crops
    claim: "Deep learning outperforms traditional methods in crop disease detection"
    config:              # Claim-specific processing overrides
      num_papers_to_return: 5
    exclusion_criteria:
      no_comparison:
        type: boolean
        description: "No comparison with traditional methods"
      small_dataset:
        type: boolean
        description: "Dataset contains fewer than 1000 images"
    information_extraction:
      accuracy:
        type: float
        description: "Model accuracy percentage"
      dataset_size:
        type: integer
        description: "Number of images in dataset"
      methods:
        type: list
        description: "ML methods compared"
      hardware_specs:
        type: string
        description: "Computing resources used"

  - id: iot_irrigation
    claim: "IoT sensor networks improve irrigation efficiency"
    exclusion_criteria:
      theoretical_only:
        type: boolean
        description: "Paper is theoretical without implementation"
      no_metrics:
        type: boolean
        description: "No quantitative efficiency metrics provided"
    information_extraction:
      water_savings:
        type: float
        description: "Percentage reduction in water usage"
      implementation_cost:
        type: float
        description: "Cost per hectare in USD"
      sensor_types:
        type: list
        description: "Types of sensors used"
```

## Output Structure and Organization

The batch processor creates a results folder named after your YAML file and generates two types of JSON files for each claim:

### 1. Concise Results (`{claim_id}_{timestamp}.json`)
Contains only the top N papers (specified by num_papers_to_return) with essential information:
```json
{
  "claim_text": {
    "ranked_papers": [
      {
        "title": "Paper title",
        "authors": ["Author names"],
        "year": 2023,
        "bibtex": "Complete BibTeX citation",
        "relevant_quotes": [
          "Key quote demonstrating relevance",
          "Important finding supporting claim"
        ],
        "analysis": "Detailed analysis of paper's relevance to claim",
        "exclusion_criteria_result": {
          "no_empirical": false,
          "insufficient_data": false
        },
        "extraction_result": {
          "accuracy": 95.7,
          "methods_used": ["CNN", "Random Forest"],
          "dataset_size": 10000
        },
        "relevance_score": 0.95
      }
    ],
    "num_total_papers": 15
  }
}
```

### 2. Full Results (`{claim_id}_{timestamp}_full.json`)
Contains complete analysis data including:
- All papers found, not just top N
- Search queries used
- Complete paper metadata
- Full text extracts
- Processing timestamps
- All analysis details

### Example Directory Structure
For a YAML file named `agriculture_claims.yaml`:
```
agriculture_claims.yaml
agriculture_claims_results/
  ├── batch_process.log
  ├── deep_learning_crops_20241027_123456.json      # Concise results
  ├── deep_learning_crops_20241027_123456_full.json # Full results
  ├── iot_irrigation_20241027_123456.json
  └── iot_irrigation_20241027_123456_full.json
```

## Understanding Exclusion and Extraction

### How Exclusion Works
When you specify exclusion criteria:
1. Each paper is evaluated against all criteria
2. Criteria are evaluated based on paper's full text and metadata
3. Any paper matching ANY criterion is excluded
4. Results include the evaluation outcome for each criterion
5. Use this to systematically filter irrelevant papers

Example thought process for criteria:
```yaml
exclusion_criteria:
  no_empirical:
    type: boolean
    description: "Paper contains no empirical evaluation"  # Excludes theoretical papers
  small_scale:
    type: boolean
    description: "Study area under 1 hectare"  # Excludes small pilot studies
  old_data:
    type: boolean
    description: "Data collected before 2015"  # Excludes outdated studies
```

### How Extraction Works
When you specify an extraction schema:
1. System analyzes full paper text to find requested information
2. Data is extracted and validated against specified types
3. All extracted values are included in results
4. Use this to gather specific evidence for your claim
5. Schema should target key information needed for claim validation

Example thought process for extraction:
```yaml
information_extraction:
  accuracy:
    type: float
    description: "Model prediction accuracy"  # Gets specific performance metrics
  dataset_size:
    type: integer
    description: "Number of samples"  # Validates study scale
  limitations:
    type: string
    description: "Study limitations"  # Captures important caveats
  methods:
    type: list
    description: "Methods compared"  # Lists all approaches tested
```

This structured approach ensures:
- Systematic evaluation of papers
- Consistent criteria application
- Structured evidence gathering
- Reproducible analysis results
- Clear documentation of findings