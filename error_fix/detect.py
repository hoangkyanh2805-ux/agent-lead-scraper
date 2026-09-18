"""
Error detection: identify validation, config, rate-limit, and parsing errors.
Categorizes errors for fix_prompt to handle.
"""

from typing import Dict, List, Optional
from enum import Enum
import re


class ErrorType(Enum):
    """Classification of errors."""
    VALIDATION_ERROR = "validation_error"
    ACTOR_CONFIG_ERROR = "actor_config_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    PARSING_ERROR = "parsing_error"
    UNKNOWN = "unknown"


class ErrorDetector:
    """Detect and classify lead scraping errors."""
    
    def __init__(self):
        self.error_patterns = {
            ErrorType.RATE_LIMIT_ERROR: [
                r"rate.?limit",
                r"quota",
                r"429",
                r"too many requests",
                r"api.*limit",
            ],
            ErrorType.ACTOR_CONFIG_ERROR: [
                r"invalid.*input",
                r"required field",
                r"schema.*mismatch",
                r"actor.*config",
                r"missing.*parameter",
            ],
            ErrorType.PARSING_ERROR: [
                r"parse.*fail",
                r"json.*error",
                r"malformed",
                r"unexpected.*format",
                r"invalid.*field",
            ],
            ErrorType.VALIDATION_ERROR: [
                r"validation.*fail",
                r"invalid.*lead",
                r"duplicate.*record",
                r"null.*field",
            ],
        }
    
    def detect(self, error_message: str) -> Dict:
        """
        Detect error type from error message.
        
        Args:
            error_message: Error string from actor or validation
        
        Returns:
            Dict with error_type, confidence, matched_pattern
        """
        if not error_message:
            return {
                "error_type": ErrorType.UNKNOWN.value,
                "confidence": 0.0,
                "matched_pattern": None,
            }
        
        error_lower = error_message.lower()
        best_match = (ErrorType.UNKNOWN, 0.0, None)
        
        for error_type, patterns in self.error_patterns.items():
            for pattern in patterns:
                if re.search(pattern, error_lower):
                    confidence = 0.9 if error_type != ErrorType.UNKNOWN else 0.5
                    if confidence > best_match[1]:
                        best_match = (error_type, confidence, pattern)
        
        error_type, confidence, pattern = best_match
        
        return {
            "error_type": error_type.value,
            "confidence": confidence,
            "matched_pattern": pattern,
            "raw_message": error_message,
        }
    
    def batch_detect(self, errors: List[str]) -> List[Dict]:
        """Detect multiple errors at once."""
        return [self.detect(err) for err in errors]
    
    def suggest_fix_strategy(self, error_info: Dict) -> str:
        """Suggest fix strategy based on error type."""
        error_type = error_info["error_type"]
        
        strategies = {
            ErrorType.RATE_LIMIT_ERROR.value: "Implement exponential backoff. Reduce batch size. Check Apify quota.",
            ErrorType.ACTOR_CONFIG_ERROR.value: "Review actor input schema. Validate all required fields. Check field mapping.",
            ErrorType.PARSING_ERROR.value: "Add error handling for malformed responses. Implement field fallbacks.",
            ErrorType.VALIDATION_ERROR.value: "Add duplicate detection. Implement field validators. Remove null records.",
            ErrorType.UNKNOWN.value: "Manual review required. Check actor logs.",
        }
        
        return strategies.get(error_type, "Unknown error type")


if __name__ == "__main__":
    detector = ErrorDetector()
    
    test_errors = [
        "429: Too many requests. API rate limit exceeded.",
        "Invalid actor input: 'search_query' is required",
        "Error parsing JSON response: Unexpected token at line 5",
        "Validation failed: Duplicate lead record detected",
    ]
    
    for error in test_errors:
        result = detector.detect(error)
        strategy = detector.suggest_fix_strategy(result)
        print(f"Error: {error[:50]}...")
        print(f"  Type: {result['error_type']} (confidence: {result['confidence']:.2f})")
        print(f"  Strategy: {strategy}\n")
