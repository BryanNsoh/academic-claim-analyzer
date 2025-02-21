# academic_claim_analyzer/__init__.py

def get_analyze_request():
    from .main import analyze_request
    return analyze_request

def get_request_analysis():
    from .models import RequestAnalysis
    return RequestAnalysis

def get_batch_processor_functions():
    from .batch_processor import batch_analyze_requests 
    return batch_analyze_requests 