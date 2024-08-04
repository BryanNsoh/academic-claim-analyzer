# academic_claim_analyzer/__init__.py

from .main import analyze_claim
from .models import ClaimAnalysis
from .batch_processor import batch_analyze_claims, print_results_summary, print_detailed_result, print_schema
from ._version import __version__