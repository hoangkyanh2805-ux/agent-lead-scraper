"""
Apify API integration: wrapper for Apify Python client.
Includes real client and mock client for testing.
"""

import os
import json
import random
from typing import Dict, Optional
from datetime import datetime


class ApifyClient:
    """Wrapper for real Apify Python client."""
    
    def __init__(self, api_token: Optional[str] = None):
        """
        Initialize Apify client.
        
        Args:
            api_token: Apify API token (default: $APIFY_API_TOKEN env var)
        """
        self.api_token = api_token or os.getenv("APIFY_API_TOKEN")
        if not self.api_token:
            raise ValueError("APIFY_API_TOKEN not set")
        
        try:
            import apify_client
            self.client = apify_client.ApifyClient(self.api_token)
        except ImportError:
            raise ImportError("apify-client package not installed. Install with: pip install apify-client")
    
    def run_actor(
        self,
        actor_name: str,
        config: Dict
    ) -> Dict:
        """
        Run an Apify actor and return results.
        
        Args:
            actor_name: Actor name or ID (e.g., "apollo_google_search")
            config: Actor configuration dict
        
        Returns:
            Dict with lead_count, deduplication_rate, validation_rate, etc.
        
        Raises:
            Exception: If actor run fails
        """
        try:
            # Call Apify actor
            run = self.client.actor(actor_name).call(run_input=config)
            
            # Parse results
            results = run.get("output", {}).get("data", [])
            
            # Calculate metrics
            lead_count = len(results)
            deduplication_rate = self._calculate_dedup_rate(results)
            validation_rate = self._calculate_validation_rate(results)
            processing_time = run.get("meta", {}).get("duration", 0) / 1000  # Convert to seconds
            
            return {
                "status": "success",
                "lead_count": lead_count,
                "deduplication_rate": deduplication_rate,
                "lead_validation_rate": validation_rate,
                "processing_time": processing_time,
                "error": None,
                "error_count": 0,
                "raw_results": results,
            }
            
        except Exception as e:
            # Handle errors
            error_msg = str(e)
            error_type = self._classify_error(error_msg)
            
            return {
                "status": "failed",
                "error": error_msg,
                "error_type": error_type,
                "lead_count": 0,
                "deduplication_rate": 0.0,
                "lead_validation_rate": 0.0,
                "processing_time": 0.0,
                "error_count": 1,
            }
    
    def _calculate_dedup_rate(self, results: list) -> float:
        """Calculate deduplication rate (1 - duplicates/total)."""
        if not results:
            return 0.0
        
        emails = [r.get("email") for r in results if r.get("email")]
        unique_emails = len(set(emails))
        
        return unique_emails / len(results) if results else 0.0
    
    def _calculate_validation_rate(self, results: list) -> float:
        """Calculate validation rate (records with all required fields)."""
        if not results:
            return 0.0
        
        required_fields = ["name", "email", "company"]
        valid_count = sum(
            1 for r in results
            if all(r.get(field) for field in required_fields)
        )
        
        return valid_count / len(results)
    
    def _classify_error(self, error_msg: str) -> str:
        """Classify error type."""
        if "rate limit" in error_msg.lower() or "429" in error_msg:
            return "rate_limit"
        elif "invalid" in error_msg.lower():
            return "config_error"
        elif "timeout" in error_msg.lower():
            return "timeout"
        else:
            return "unknown"


class MockApifyClient:
    """
    Mock Apify client for testing.
    Simulates actor runs with synthetic data.
    """
    
    def __init__(self, failure_rate: float = 0.1):
        """
        Initialize mock client.
        
        Args:
            failure_rate: Probability of failure (0-1)
        """
        self.failure_rate = failure_rate
        self.run_count = 0
    
    def run_actor(
        self,
        actor_name: str,
        config: Dict
    ) -> Dict:
        """
        Simulate Apify actor run with synthetic data.
        
        Returns:
            Dict with metrics (can include errors)
        """
        self.run_count += 1
        
        # Simulate occasional failures
        if random.random() < self.failure_rate:
            return self._generate_error_result()
        
        # Simulate improvement over iterations
        base_leads = config.get("batch_size", 100)
        iteration_bonus = min(self.run_count * 50, 300)  # Up to 300 bonus leads
        lead_count = base_leads + iteration_bonus + random.randint(-20, 50)
        
        # Quality improves with iterations
        dedup_rate = 0.92 + (self.run_count * 0.01)  # Starts at 92%, improves by 1% per run
        validation_rate = 0.95 + (self.run_count * 0.01)  # Starts at 95%
        
        # Cap at 99%
        dedup_rate = min(dedup_rate, 0.99)
        validation_rate = min(validation_rate, 0.99)
        
        return {
            "status": "success",
            "lead_count": int(lead_count),
            "deduplication_rate": dedup_rate,
            "lead_validation_rate": validation_rate,
            "processing_time": random.uniform(4.5, 6.0),
            "error": None,
            "error_count": 0,
            "raw_results": self._generate_mock_leads(int(lead_count)),
        }
    
    def _generate_error_result(self) -> Dict:
        """Generate a simulated error result."""
        errors = [
            {
                "error": "429: Too many requests. API rate limit exceeded.",
                "error_type": "rate_limit",
            },
            {
                "error": "Invalid actor input: 'search_query' is required",
                "error_type": "config_error",
            },
            {
                "error": "Timeout: Actor exceeded maximum execution time",
                "error_type": "timeout",
            },
        ]
        
        selected_error = random.choice(errors)
        
        return {
            "status": "failed",
            "error": selected_error["error"],
            "error_type": selected_error["error_type"],
            "lead_count": 0,
            "deduplication_rate": 0.0,
            "lead_validation_rate": 0.0,
            "processing_time": random.uniform(0.5, 2.0),
            "error_count": 1,
        }
    
    def _generate_mock_leads(self, count: int) -> list:
        """Generate mock lead data."""
        companies = [
            "TechCorp", "StartupXYZ", "InnovateLabs", "DataSystems",
            "CloudVentures", "AI Solutions", "FinTech Hub", "DevOps Plus"
        ]
        domains = ["gmail.com", "company.com", "startup.io", "tech.co"]
        
        leads = []
        for i in range(count):
            leads.append({
                "name": f"Lead {i+1}",
                "email": f"contact{i}@{random.choice(companies).lower()}.{random.choice(domains)}",
                "company": random.choice(companies),
                "title": "Founder",
                "phone": f"+1-555-{random.randint(1000, 9999)}",
            })
        
        return leads


class ApifyBatchRunner:
    """
    Utility to run multiple actors in sequence or parallel.
    Useful for testing multiple strategies simultaneously.
    """
    
    def __init__(self, apify_client):
        self.client = apify_client
        self.batch_results = []
    
    def run_batch(
        self,
        actors: list,
        configs: Dict
    ) -> list:
        """
        Run multiple actors with given configs.
        
        Args:
            actors: List of actor names
            configs: Config dict (applies to all actors)
        
        Returns:
            List of results
        """
        results = []
        for actor in actors:
            result = self.client.run_actor(actor, configs)
            results.append({
                "actor": actor,
                "result": result
            })
        
        self.batch_results = results
        return results
    
    def get_best_actor(self) -> str:
        """Get actor with best quality score."""
        if not self.batch_results:
            return None
        
        best = max(
            self.batch_results,
            key=lambda x: (
                x["result"].get("deduplication_rate", 0) +
                x["result"].get("lead_validation_rate", 0)
            ) / 2
        )
        
        return best["actor"]


if __name__ == "__main__":
    # Test mock client
    print("Testing MockApifyClient...")
    mock_client = MockApifyClient(failure_rate=0.2)
    
    config = {
        "search_query": "tech founders",
        "batch_size": 100,
        "timeout": 30,
    }
    
    for i in range(5):
        result = mock_client.run_actor("apollo_google_search", config)
        print(f"\nRun {i+1}:")
        print(f"  Status: {result['status']}")
        
        if result['status'] == 'success':
            print(f"  Leads: {result['lead_count']}")
            print(f"  Dedup: {result['deduplication_rate']:.2%}")
            print(f"  Valid: {result['lead_validation_rate']:.2%}")
        else:
            print(f"  Error: {result['error']}")
