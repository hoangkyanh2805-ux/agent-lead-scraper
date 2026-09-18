"""
Error fix generation: propose fixes based on detected errors and version them.
Stores prompt versions in prompt_history/ for reproducibility.
"""

import json
import os
from datetime import datetime
from typing import Dict
from detect import ErrorDetector, ErrorType


class PromptFixer:
    """Generate and version prompt fixes for detected errors."""
    
    def __init__(self, history_dir: str = "prompt_history"):
        self.history_dir = history_dir
        os.makedirs(history_dir, exist_ok=True)
        self.detector = ErrorDetector()
    
    def propose_fix(
        self,
        error_message: str,
        current_prompt: str,
        current_config: Dict
    ) -> Dict:
        """
        Propose a fix for detected error.
        
        Args:
            error_message: Raw error string
            current_prompt: Current actor prompt/config
            current_config: Current actor configuration dict
        
        Returns:
            Dict with proposed_fix, reasoning, confidence
        """
        error_info = self.detector.detect(error_message)
        error_type = error_info["error_type"]
        
        fixes = {
            ErrorType.RATE_LIMIT_ERROR.value: self._fix_rate_limit,
            ErrorType.ACTOR_CONFIG_ERROR.value: self._fix_config,
            ErrorType.PARSING_ERROR.value: self._fix_parsing,
            ErrorType.VALIDATION_ERROR.value: self._fix_validation,
        }
        
        fix_func = fixes.get(error_type)
        if fix_func:
            return fix_func(error_info, current_prompt, current_config)
        else:
            return self._fix_unknown(error_info, current_prompt, current_config)
    
    def _fix_rate_limit(self, error_info: Dict, prompt: str, config: Dict) -> Dict:
        """Fix rate limit errors."""
        new_config = config.copy()
        new_config["retry_strategy"] = {
            "max_retries": 5,
            "backoff_base": 2,
            "max_wait_seconds": 60,
        }
        new_config["batch_size"] = max(1, config.get("batch_size", 10) // 2)
        
        return {
            "error_type": ErrorType.RATE_LIMIT_ERROR.value,
            "proposed_fix": {
                "action": "reduce_batch_size_and_add_backoff",
                "new_config": new_config,
            },
            "reasoning": "Implement exponential backoff and reduce batch size to avoid hitting rate limits",
            "confidence": 0.95,
        }
    
    def _fix_config(self, error_info: Dict, prompt: str, config: Dict) -> Dict:
        """Fix actor config errors."""
        return {
            "error_type": ErrorType.ACTOR_CONFIG_ERROR.value,
            "proposed_fix": {
                "action": "validate_schema",
                "required_review": True,
                "check_items": [
                    "Verify all required fields are present",
                    "Review field mapping against actor schema",
                    "Validate data types",
                ],
            },
            "reasoning": "Actor configuration is invalid. Manual schema review required.",
            "confidence": 0.85,
        }
    
    def _fix_parsing(self, error_info: Dict, prompt: str, config: Dict) -> Dict:
        """Fix parsing errors."""
        new_config = config.copy()
        new_config["error_handling"] = {
            "malformed_response": "skip_and_log",
            "missing_fields": "use_fallback",
            "fallback_values": {
                "email": "unknown@example.com",
                "phone": "N/A",
                "company": "Unknown",
            },
        }
        
        return {
            "error_type": ErrorType.PARSING_ERROR.value,
            "proposed_fix": {
                "action": "add_error_handling",
                "new_config": new_config,
            },
            "reasoning": "Add fallback handling for malformed responses",
            "confidence": 0.9,
        }
    
    def _fix_validation(self, error_info: Dict, prompt: str, config: Dict) -> Dict:
        """Fix validation errors."""
        new_config = config.copy()
        new_config["validation"] = {
            "deduplication": True,
            "required_fields": ["email", "company", "name"],
            "remove_nulls": True,
        }
        
        return {
            "error_type": ErrorType.VALIDATION_ERROR.value,
            "proposed_fix": {
                "action": "enable_validation",
                "new_config": new_config,
            },
            "reasoning": "Enable deduplication and null removal",
            "confidence": 0.92,
        }
    
    def _fix_unknown(self, error_info: Dict, prompt: str, config: Dict) -> Dict:
        """Handle unknown errors."""
        return {
            "error_type": ErrorType.UNKNOWN.value,
            "proposed_fix": {
                "action": "manual_review_required",
            },
            "reasoning": f"Unknown error. Manual investigation needed. Raw message: {error_info['raw_message']}",
            "confidence": 0.3,
        }
    
    def version_and_commit(
        self,
        proposed_fix: Dict,
        run_id: str,
        current_config: Dict
    ) -> str:
        """
        Version the proposed fix and save to history.
        
        Returns:
            version_id (timestamped)
        """
        timestamp = datetime.now().isoformat()
        version_id = f"fix_{run_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        version_record = {
            "version_id": version_id,
            "timestamp": timestamp,
            "run_id": run_id,
            "error_type": proposed_fix["error_type"],
            "confidence": proposed_fix["confidence"],
            "proposed_fix": proposed_fix["proposed_fix"],
            "reasoning": proposed_fix["reasoning"],
            "previous_config": current_config,
            "status": "proposed",  # Can be: proposed, applied, reverted
        }
        
        # Save to history
        version_file = os.path.join(
            self.history_dir,
            f"{version_id}.json"
        )
        
        with open(version_file, 'w') as f:
            json.dump(version_record, f, indent=2)
        
        return version_id
    
    def load_version(self, version_id: str) -> Dict:
        """Load a specific version from history."""
        version_file = os.path.join(self.history_dir, f"{version_id}.json")
        
        if not os.path.exists(version_file):
            raise FileNotFoundError(f"Version {version_id} not found")
        
        with open(version_file, 'r') as f:
            return json.load(f)
    
    def list_versions(self, run_id: str = None) -> list:
        """List all versions, optionally filtered by run_id."""
        versions = []
        
        for filename in os.listdir(self.history_dir):
            if not filename.endswith(".json"):
                continue
            
            version_file = os.path.join(self.history_dir, filename)
            with open(version_file, 'r') as f:
                version = json.load(f)
            
            if run_id is None or version["run_id"] == run_id:
                versions.append(version)
        
        return sorted(versions, key=lambda x: x["timestamp"], reverse=True)


if __name__ == "__main__":
    fixer = PromptFixer()
    
    # Test error fix proposal
    error = "429: Too many requests. API rate limit exceeded."
    prompt = "Find all leads in tech industry"
    config = {"batch_size": 100, "timeout": 30}
    
    fix = fixer.propose_fix(error, prompt, config)
    print(f"Error: {error}")
    print(f"Proposed fix: {fix['proposed_fix']}")
    print(f"Confidence: {fix['confidence']}\n")
    
    # Version and commit
    version_id = fixer.version_and_commit(fix, "run_001", config)
    print(f"Versioned as: {version_id}")
    
    # Retrieve version
    loaded = fixer.load_version(version_id)
    print(f"Loaded version: {loaded['version_id']}")
