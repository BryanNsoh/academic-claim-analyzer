# academic_claim_analyzer/__init__.py

def get_analyze_claim():
    from .main import analyze_claim
    return analyze_claim

def get_claim_analysis():
    from .models import ClaimAnalysis
    return ClaimAnalysis

def get_batch_processor_functions():
    from .batch_processor import batch_analyze_claims, print_results_summary, print_detailed_result, print_schema
    return batch_analyze_claims, print_results_summary, print_detailed_result, print_schema
