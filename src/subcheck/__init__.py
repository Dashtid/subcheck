"""subcheck: decode and validate GitHub Actions OIDC token claims."""

from .decoder import decode_claims, parse_github_sub
from .policy import ClaimRule, Policy, load_policy, load_policy_file
from .report import build_report, to_json, to_text
from .validator import Result, validate

__version__ = "0.1.0"

__all__ = [
    "decode_claims",
    "parse_github_sub",
    "ClaimRule",
    "Policy",
    "load_policy",
    "load_policy_file",
    "Result",
    "validate",
    "build_report",
    "to_json",
    "to_text",
    "__version__",
]
